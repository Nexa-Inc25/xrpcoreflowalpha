import asyncio
from typing import Any, Dict

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
import time


async def start_xrpl_scanner():
    if not XRPL_WSS:
        return
    assert ("xrplcluster.com" in XRPL_WSS) or ("ripple.com" in XRPL_WSS), "NON-MAINNET WSS – FATAL ABORT"
    async with AsyncWebsocketClient(XRPL_WSS) as client:
        @async_retry(max_attempts=5, delay=1, backoff=2)
        async def _req(payload):
            return await client.request(payload)
        # Server info log on startup
        try:
            info = await _req(ServerInfo())
            vi = (info.result.get("info", {}).get("validated_ledger", {}) or {}).get("seq") or (info.result.get("info", {}).get("validated_ledger", {}) or {}).get("ledger_index")
            print(f"[XRPL] Connected. validated_ledger={vi}")
        except Exception:
            print("[XRPL] Connected. server_info unavailable")
        await _req(Subscribe(streams=["transactions"]))
        async def _keepalive():
            while True:
                try:
                    await _req(ServerInfo())
                except Exception:
                    pass
                await asyncio.sleep(20)
        asyncio.create_task(_keepalive())
        processed = 0
        async for msg in client:
            if isinstance(msg, dict) and msg.get("status") == "success":
                continue
            await process_xrpl_transaction(msg)
            processed += 1
            if processed % 100 == 0:
                try:
                    info = await client.request(ServerInfo())
                    vi = (info.result.get("info", {}).get("validated_ledger", {}) or {}).get("seq") or (info.result.get("info", {}).get("validated_ledger", {}) or {}).get("ledger_index")
                    print(f"[XRPL] Heartbeat. validated_ledger={vi} processed={processed}")
                except Exception:
                    print(f"[XRPL] Heartbeat. processed={processed}")


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
                print(f"[XRPL] Large payment: {xrp:,.0f} XRP hash={flow.tx_hash}")
                usd = 0.0
                try:
                    px = await get_price_usd("xrp")
                    usd = float(px) * xrp
                except Exception:
                    usd = 0.0
                # Format summary based on size
                if xrp >= 1_000_000_000:
                    summary = f"{xrp/1_000_000_000:.1f}B XRP → {txn.get('Destination','')[:6]}..."
                elif xrp >= 1_000_000:
                    summary = f"{xrp/1_000_000:.1f}M XRP → {txn.get('Destination','')[:6]}..."
                else:
                    summary = f"{xrp:,.0f} XRP → {txn.get('Destination','')[:6]}..."
                dest_tag = txn.get("DestinationTag")
                tags = ["xrpl", "xrpl payment"]
                await publish_signal({
                    "type": "xrp",
                    "sub_type": "payment",
                    "amount_xrp": xrp,
                    "usd_value": round(usd, 2),
                    "tx_hash": flow.tx_hash,
                    "timestamp": flow.timestamp,
                    "summary": summary,
                    "destination": flow.destination,
                    "source": flow.source,
                    "destination_tag": dest_tag,
                    "tags": tags,
                })
                await send_slack_alert(build_rich_slack_payload({"type": "xrp", "flow": flow}))
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
