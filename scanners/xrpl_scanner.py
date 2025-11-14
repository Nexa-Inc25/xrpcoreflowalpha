import asyncio
from typing import Any, Dict

from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models.requests import Subscribe

from app.config import XRPL_WSS
from alerts.slack import send_slack_alert, build_rich_slack_payload
from models.types import XRPFlow
from observability.metrics import xrpl_tx_processed
from bus.signal_bus import publish_signal
from utils.price import get_price_usd
import time


async def start_xrpl_scanner():
    if not XRPL_WSS:
        return
    async with AsyncWebsocketClient(XRPL_WSS) as client:
        await client.request(Subscribe(streams=["transactions"]))
        async for msg in client:
            if isinstance(msg, dict) and msg.get("status") == "success":
                continue
            await process_xrpl_transaction(msg)


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
                print(f"[XRPL] Large payment: {xrp:,.0f} XRP hash={flow.tx_hash}")
                await send_slack_alert(build_rich_slack_payload({"type": "xrp", "flow": flow}))
                usd = 0.0
                try:
                    px = await get_price_usd("xrp")
                    usd = float(px) * xrp
                except Exception:
                    usd = 0.0
                summary = f"{xrp/1_000_000:.1f}M XRP → {txn.get('Destination','')[:6]}..."
                await publish_signal({
                    "type": "xrp",
                    "sub_type": "payment",
                    "amount_xrp": xrp,
                    "usd_value": round(usd, 2),
                    "tx_hash": flow.tx_hash,
                    "timestamp": flow.timestamp,
                    "summary": summary,
                })
                return

    # Other institutional signals to extend in Phase 1
    if ttype in {"AMMDeposit", "AMMWithdraw", "EscrowCreate", "EscrowFinish", "TrustSet"}:
        xrpl_tx_processed.labels(type=ttype.lower()).inc()
        print(f"[XRPL] Institutional signal: {ttype}")
        await publish_signal({
            "type": "xrp",
            "sub_type": ttype.lower(),
            "timestamp": int(time.time()),
            "summary": f"XRPL {ttype}",
            "usd_value": None,
        })
