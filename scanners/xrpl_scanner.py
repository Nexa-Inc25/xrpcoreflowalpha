import asyncio
from typing import Any, Dict, Optional

from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models.requests import Subscribe, ServerInfo

from app.config import XRPL_WSS
from alerts.slack import send_slack_alert, build_rich_slack_payload
from models.types import XRPFlow
from observability.metrics import xrpl_tx_processed
from bus.signal_bus import publish_signal
from utils.price import get_price_usd
from utils.retry import async_retry
from utils.tx_validate import validate_tx
from predictors.signal_scorer import enrich_signal_with_score, identify_institution
from workers.scanner_monitor import mark_scanner_connected, mark_scanner_reconnecting, record_scanner_signal, mark_scanner_error
from workers.ledger_monitor import update_local_ledger
import time


# Known XRPL institutional addresses for enhanced detection
XRPL_INSTITUTIONS = {
    # Ripple corporate
    "rN7n3473SaZBCG4dFL83w7a1RXtXtbk2D9": "ripple_ops",
    "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh": "genesis",
    "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe": "ripple_treasury",
    # Major exchanges
    "rEy8TFcrAPvhpKrwyrscNYyqBGUkE9hKaJ": "binance",
    "rJb5KsHsDHF1YS5B5DU6QCkH5NsPaKQTcy": "bitstamp",
    "rLHzPsX6oXkzU2qL12kHCH8G8cnZv1rBJh": "kraken",
    "r9cZA1mLK5R5Am25ArfXFmqgNwjZgnfk59": "bitfinex",
    "rUobSiUpYH2S97Mgb4E489gFKv46rPjXAK": "coinbase",
    # Known market makers / OTC
    "rDsbeomae4FXwgQTJp9Rs64Qg9vDiTCdBv": "b2c2",
    "rDBhLJc4VJzpWN6v8a7h8K5fvFfHcN7nVk": "galaxy_digital",
}


def get_address_label(address: str) -> str:
    """Get human-readable label for XRPL address."""
    return XRPL_INSTITUTIONS.get(address, "unknown")


def is_institutional_flow(source: str, dest: str) -> tuple[bool, Optional[str], Optional[str]]:
    """Check if flow involves institutional addresses."""
    src_label = XRPL_INSTITUTIONS.get(source)
    dst_label = XRPL_INSTITUTIONS.get(dest)
    is_institutional = bool(src_label or dst_label)
    return (is_institutional, src_label, dst_label)


def _err_str(e: Exception) -> str:
    s = str(e)
    return f"{e.__class__.__name__}: {s}" if s else repr(e)


async def start_xrpl_scanner():
    if not XRPL_WSS:
        print("[XRPL] Scanner disabled - XRPL_WSS not configured")
        return
    if not XRPL_WSS.startswith(("ws://", "wss://")):
        raise ValueError(f"XRPL_WSS must be a WebSocket URL (ws:// or wss://). Got: {XRPL_WSS}")
    assert ("xrplcluster.com" in XRPL_WSS) or ("ripple.com" in XRPL_WSS), "NON-MAINNET WSS – FATAL ABORT"
    
    reconnect_count = 0
    while True:
        try:
            if reconnect_count > 0:
                await mark_scanner_reconnecting("xrpl")
                print(f"[XRPL] Reconnecting (attempt {reconnect_count})...")
            
            async with AsyncWebsocketClient(XRPL_WSS) as client:
                # Track connection state
                _connection_dead = False
                
                @async_retry(max_attempts=3, delay=1, backoff=2)
                async def _req(payload):
                    nonlocal _connection_dead
                    if _connection_dead:
                        raise ConnectionError("Connection marked dead")
                    try:
                        return await client.request(payload)
                    except Exception as e:
                        if "not open" in str(e).lower() or "closed" in str(e).lower():
                            _connection_dead = True
                        raise
                
                # Server info log on startup
                try:
                    info = await _req(ServerInfo())
                    vi = (info.result.get("info", {}).get("validated_ledger", {}) or {}).get("seq") or (info.result.get("info", {}).get("validated_ledger", {}) or {}).get("ledger_index")
                    print(f"[XRPL] Connected. validated_ledger={vi}")
                except Exception:
                    print("[XRPL] Connected. server_info unavailable")
                
                # Mark as connected
                await mark_scanner_connected("xrpl")
                reconnect_count = 0  # Reset on successful connect
                
                await _req(Subscribe(streams=["transactions"]))
                
                async def _keepalive():
                    nonlocal _connection_dead
                    consecutive_fails = 0
                    while not _connection_dead:
                        try:
                            await _req(ServerInfo())
                            consecutive_fails = 0
                        except Exception as e:
                            consecutive_fails += 1
                            if consecutive_fails >= 3 or "not open" in str(e).lower():
                                _connection_dead = True
                                print(f"[XRPL] Keepalive detected dead connection")
                                break
                        await asyncio.sleep(20)
                asyncio.create_task(_keepalive())
                
                processed = 0
                async for msg in client:
                    # Check if connection died
                    if _connection_dead:
                        print("[XRPL] Connection dead, breaking loop for reconnect")
                        break
                    
                    if isinstance(msg, dict) and msg.get("status") == "success":
                        continue
                    await process_xrpl_transaction(msg)
                    await record_scanner_signal("xrpl")
                    processed += 1
                    if processed % 100 == 0:
                        try:
                            info = await client.request(ServerInfo())
                            vi = (info.result.get("info", {}).get("validated_ledger", {}) or {}).get("seq") or (info.result.get("info", {}).get("validated_ledger", {}) or {}).get("ledger_index")
                            if vi:
                                update_local_ledger(vi)  # Report to ledger monitor
                            print(f"[XRPL] Heartbeat. validated_ledger={vi} processed={processed}")
                        except Exception as e:
                            if "not open" in str(e).lower():
                                _connection_dead = True
                                break
                            print(f"[XRPL] Heartbeat. processed={processed}")
        
        except Exception as e:
            reconnect_count += 1
            err = _err_str(e)
            await mark_scanner_error("xrpl", err)
            print(f"[XRPL] Connection error: {err}")
            # Exponential backoff up to 5 minutes
            backoff = min(300, 5 * (2 ** min(reconnect_count, 6)))
            print(f"[XRPL] Reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)


async def process_xrpl_transaction(msg: Dict[str, Any]):
    txn = msg.get("transaction") or msg
    if not isinstance(txn, dict):
        return
    ttype = txn.get("TransactionType")

    if ttype == "Payment":
        amount = txn.get("Amount")
        # XRP native payments have "Amount" as drops string
        if isinstance(amount, str) and amount.isdigit():
            drops = int(amount)
            xrp = drops / 1_000_000
            # Hard reject unrealistic amounts (drop silently)
            if xrp > 5_000_000_000:
                return
            # Skip self-payments (spam/noise)
            source = txn.get("Account", "")
            dest = txn.get("Destination", "")
            if source == dest:
                return
            # Only report significant payments (>= 1M XRP = ~$2M USD)
            if xrp >= 1_000_000:
                flow = XRPFlow(
                    amount_xrp=xrp,
                    usd_value=0.0,
                    tx_hash=txn.get("hash", ""),
                    timestamp=int(time.time()),
                    destination=txn.get("Destination", ""),
                    source=txn.get("Account", ""),
                )
                xrpl_tx_processed.labels(type="payment_large").inc()
                ok = await validate_tx("xrpl", flow.tx_hash, timeout_sec=10)
                if not ok:
                    # Drop silently to avoid noise from fake data
                    return
                
                # Get USD value
                usd = 0.0
                try:
                    px = await get_price_usd("xrp")
                    usd = float(px) * xrp
                except Exception:
                    usd = 0.0
                
                # Check for institutional flow
                is_inst, src_label, dst_label = is_institutional_flow(source, dest)
                src_name = src_label or source[:8]
                dst_name = dst_label or dest[:8]
                
                # Format summary based on size and institutions
                if xrp >= 1_000_000_000:
                    summary = f"{xrp/1_000_000_000:.1f}B XRP | {src_name} → {dst_name}"
                elif xrp >= 1_000_000:
                    summary = f"{xrp/1_000_000:.1f}M XRP | {src_name} → {dst_name}"
                else:
                    summary = f"{xrp:,.0f} XRP | {src_name} → {dst_name}"
                
                dest_tag = txn.get("DestinationTag")
                tags = ["xrpl", "xrpl_payment"]
                if is_inst:
                    tags.append("institutional")
                if xrp >= 10_000_000:
                    tags.append("whale")
                
                # Build signal and enrich with scoring
                signal = {
                    "type": "xrpl_payment",
                    "sub_type": "payment",
                    "network": "xrpl",
                    "amount_xrp": xrp,
                    "amount": xrp,
                    "amount_usd": round(usd, 2),
                    "usd_value": round(usd, 2),
                    "tx_hash": flow.tx_hash,
                    "timestamp": flow.timestamp,
                    "summary": summary,
                    "destination": flow.destination,
                    "source": flow.source,
                    "from_owner": src_label or "unknown",
                    "to_owner": dst_label or "unknown",
                    "destination_tag": dest_tag,
                    "is_institutional": is_inst,
                    "tags": tags,
                }
                
                # Apply ML-driven scoring
                signal = enrich_signal_with_score(signal)
                
                print(f"[XRPL] Payment: {xrp/1e6:.1f}M XRP | {src_name} → {dst_name} | conf={signal.get('confidence', 50)}%")
                
                await publish_signal(signal)
                
                # High-confidence signals get Slack alerts
                if signal.get("confidence", 0) >= 70 or xrp >= 10_000_000:
                    await send_slack_alert(build_rich_slack_payload({"type": "xrp", "flow": flow, "signal": signal}))
                return

    # TrustSet - institutional trustline activity
    if ttype == "TrustSet":
        limit_amount = txn.get("LimitAmount", {})
        if isinstance(limit_amount, dict):
            currency = limit_amount.get("currency", "")
            issuer = limit_amount.get("issuer", "")
            value = limit_amount.get("value", "0")
            try:
                limit_value = float(value)
            except (ValueError, TypeError):
                limit_value = 0
            # Only report significant trustlines (>1M value)
            if limit_value >= 1_000_000:
                xrpl_tx_processed.labels(type="trustset").inc()
                tx_hash = txn.get("hash", "")
                if not tx_hash:
                    return
                print(f"[XRPL] TrustSet: {limit_value:,.0f} {currency[:8]} issuer={issuer[:8]}...")
                tags = ["xrpl", "trustset"]
                # Format summary based on size
                if limit_value >= 1_000_000_000:
                    summary = f"TrustLine {limit_value/1_000_000_000:.1f}B {currency[:8]}"
                else:
                    summary = f"TrustLine {limit_value/1_000_000:.1f}M {currency[:8]}"
                await publish_signal({
                    "type": "trustline",
                    "sub_type": "trustset",
                    "timestamp": int(time.time()),
                    "summary": summary,
                    "usd_value": 0,
                    "tx_hash": tx_hash,
                    "limit_value": limit_value,
                    "currency": currency,
                    "issuer": issuer,
                    "account": txn.get("Account", ""),
                    "tags": tags,
                })
        return

    # Other institutional signals
    if ttype in {"AMMDeposit", "AMMWithdraw", "EscrowCreate", "EscrowFinish"}:
        xrpl_tx_processed.labels(type=ttype.lower()).inc()
        tx_hash = txn.get("hash", "")
        if not tx_hash:
            return
        
        # Extract amount from transaction
        amount_xrp = 0.0
        if ttype in {"EscrowCreate", "EscrowFinish"}:
            # Escrow amounts are in drops
            amt = txn.get("Amount")
            if isinstance(amt, str) and amt.isdigit():
                amount_xrp = int(amt) / 1_000_000
        elif ttype in {"AMMDeposit", "AMMWithdraw"}:
            # AMM can have Amount or Amount2 (drops for XRP)
            amt = txn.get("Amount")
            if isinstance(amt, str) and amt.isdigit():
                amount_xrp = int(amt) / 1_000_000
            amt2 = txn.get("Amount2")
            if isinstance(amt2, str) and amt2.isdigit():
                amount_xrp = max(amount_xrp, int(amt2) / 1_000_000)
        
        # Skip small amounts
        if amount_xrp < 100_000:  # < 100K XRP
            return
            
        print(f"[XRPL] Institutional signal: {ttype} {amount_xrp:,.0f} XRP")
        tags = ["xrpl", ttype.lower()]
        
        # Get USD value
        usd = 0.0
        try:
            px = await get_price_usd("xrp")
            usd = float(px) * amount_xrp
        except Exception:
            pass
        
        # Format summary
        if amount_xrp >= 1_000_000:
            summary = f"{ttype} {amount_xrp/1_000_000:.1f}M XRP"
        else:
            summary = f"{ttype} {amount_xrp/1_000:.0f}K XRP"
            
        await publish_signal({
            "type": "xrp",
            "sub_type": ttype.lower(),
            "amount_xrp": amount_xrp,
            "usd_value": round(usd, 2),
            "timestamp": int(time.time()),
            "summary": summary,
            "tx_hash": tx_hash,
            "source": txn.get("Account", ""),
            "destination": txn.get("Destination", ""),
            "tags": tags,
        })
