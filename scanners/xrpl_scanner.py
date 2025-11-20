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
            if xrp >= 5_000_000:
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
                summary = f"{xrp/1_000_000:.1f}M XRP → {txn.get('Destination','')[:6]}..."
                dest_tag = txn.get("DestinationTag")
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
                })
                await send_slack_alert(build_rich_slack_payload({"type": "xrp", "flow": flow}))
                return

    # Other institutional signals to extend in Phase 1
    if ttype in {"AMMDeposit", "AMMWithdraw", "EscrowCreate", "EscrowFinish", "TrustSet"}:
        xrpl_tx_processed.labels(type=ttype.lower()).inc()
        tx_hash = txn.get("hash", "")
        if not tx_hash:
            return
        ok = await validate_tx("xrpl", tx_hash, timeout_sec=10)
        if not ok:
            return
        print(f"[XRPL] Institutional signal: {ttype}")
        await publish_signal({
            "type": "xrp",
            "sub_type": ttype.lower(),
            "timestamp": int(time.time()),
            "summary": f"XRPL {ttype}",
            "usd_value": None,
            "tx_hash": tx_hash,
        })
