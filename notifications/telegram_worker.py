import asyncio
import json
from typing import Any, Dict, Optional

import httpx
import redis.asyncio as redis

from app.config import REDIS_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_MIN_CONFIDENCE


_redis: Optional[redis.Redis] = None


async def _r() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def _send_telegram_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(url, json=payload)
    except Exception:
        return


def _format_alert(data: Dict[str, Any]) -> Optional[str]:
    try:
        t = (data.get("type") or "").upper()
        conf = int(data.get("confidence", 0))
        tx = data.get("tx_hash") or data.get("tx") or ""
        usd = float(data.get("usd_value") or 0.0)
        val_eth = data.get("value_eth")
        lines = []
        if t:
            lines.append(f"{t} DARK FLOW")
        else:
            lines.append("ZK DARK FLOW")
        if val_eth is not None:
            try:
                ve = float(val_eth)
                lines.append(f"{ve:.2f} ETH │ {conf}%")
            except Exception:
                lines.append(f"{usd/1e6:.1f}m USD │ {conf}%")
        else:
            lines.append(f"~${usd/1e6:.1f}m │ {conf}%")
        if tx:
            lines.append(f"https://zkalpha.live/flow/{tx}")
        return "\n".join(lines)
    except Exception:
        return None


async def start_telegram_worker() -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    r = await _r()
    try:
        pubsub = r.pubsub()
        await pubsub.subscribe("zk_alpha_flow")
    except Exception:
        return
    min_conf = TELEGRAM_MIN_CONFIDENCE
    while True:
        try:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if not message:
                await asyncio.sleep(0.5)
                continue
            if message.get("type") != "message":
                continue
            try:
                data = json.loads(message.get("data") or "{}")
            except Exception:
                continue
            try:
                conf = int(data.get("confidence", 0))
            except Exception:
                conf = 0
            if conf < min_conf:
                continue
            text = _format_alert(data)
            if not text:
                continue
            await _send_telegram_message(text)
        except Exception:
            await asyncio.sleep(2)
