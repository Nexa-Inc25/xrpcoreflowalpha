import asyncio
import time
from typing import Any, Dict

from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models.requests import Subscribe

from app.config import (
    XRPL_WSS,
    TRUSTLINE_WATCHED_ISSUERS,
    GODARK_XRPL_PARTNERS,
    REDIS_URL,
    GODARK_TRUSTLINE_MIN_VALUE,
    MONSTER_TRUSTLINE_THRESHOLD,
)
from bus.signal_bus import publish_signal
import redis.asyncio as redis
from alerts.slack import send_slack_alert, build_rich_slack_payload
from utils.xrpl_verify import validate_xrpl_tx


async def _get_dyn_partners() -> set[str]:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    xs = await r.smembers("godark:partners:xrpl")
    return {x for x in (xs or [])}


async def start_trustline_watcher():
    if not XRPL_WSS:
        return
    assert ("s1.ripple.com" in XRPL_WSS) or ("ripple.com" in XRPL_WSS), "TESTNET – FATAL ABORT"
    dyn_partners = await _get_dyn_partners()
    partners = {a.lower() for a in GODARK_XRPL_PARTNERS} | {a.lower() for a in dyn_partners}
    async with AsyncWebsocketClient(XRPL_WSS) as client:
        await client.request(Subscribe(streams=["transactions"]))
        processed = 0
        async for msg in client:
            try:
                tx = msg.get("transaction") or {}
                if tx.get("TransactionType") != "TrustSet":
                    continue
                limit = tx.get("LimitAmount") or {}
                if not isinstance(limit, dict):
                    continue
                try:
                    value = float(limit.get("value") or 0.0)
                except Exception:
                    value = 0.0
                issuer = (limit.get("issuer") or "").lower()
                account = (tx.get("Account") or "").lower()
                currency = limit.get("currency")
                tags: list[str] = []
                boost = 0.0
                if issuer in set(TRUSTLINE_WATCHED_ISSUERS):
                    tags.append("RWA Prep")
                    boost = max(boost, 0.20)
                if account in partners or issuer in partners:
                    tags.append("GoDark Trustline")
                    boost = max(boost, 0.35)
                if value >= MONSTER_TRUSTLINE_THRESHOLD:
                    tags.append("Monster Trustline")
                    boost = max(boost, 0.40)
                if value < GODARK_TRUSTLINE_MIN_VALUE:
                    # ignore small lines
                    continue
                signal: Dict[str, Any] = {
                    "type": "trustline",
                    "chain": "xrpl",
                    "account": account,
                    "issuer": issuer,
                    "currency": currency,
                    "limit_value": value,
                    "timestamp": int(time.time()),
                    "tx_hash": tx.get("hash"),
                    "tags": tags,
                    "summary": f"TrustSet {value:,.0f} {currency} issuer {issuer[:8]}...",
                    "confidence_boost": boost if boost > 0 else None,
                }
                # Validate tx exists on livenet.xrpl.org
                ok = await validate_xrpl_tx(signal["tx_hash"], timeout_sec=10)
                if not ok:
                    continue
                await publish_signal(signal)
                await send_slack_alert(build_rich_slack_payload(signal))
                processed += 1
                if processed % 100 == 0:
                    print(f"[TRUSTLINES] Heartbeat. processed={processed}")
            except Exception:
                await asyncio.sleep(0.1)
