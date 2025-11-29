import time
from typing import Any, Dict, Optional

import redis.asyncio as redis

from app.config import REDIS_URL, PENUMBRA_UNSHIELD_MIN_USD
from bus.signal_bus import publish_signal

_redis: Optional[redis.Redis] = None


async def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def handle_penumbra_unshield(event: Dict[str, Any]) -> None:
    """Process a Penumbra unshielding event and emit a signal.

    This helper expects an event dict with at least:
      - amount_usd: float-like
      - receiver: str
      - timestamp: int (seconds)
    Any upstream Cosmos/Penumbra listener can call this with real
    mainnet data. It is side-effect free on malformed events.
    """
    try:
        amt_usd = float(event.get("amount_usd") or 0.0)
    except Exception:
        amt_usd = 0.0
    if amt_usd < float(PENUMBRA_UNSHIELD_MIN_USD):
        return
    ts = int(event.get("timestamp") or int(time.time()))
    recv = str(event.get("receiver") or "")
    tags = ["Penumbra Unshield"]
    # Cluster detection via Redis window
    try:
        r = await _get_redis()
        key = "penumbra:unshields"
        member = f"{recv}:{ts}"
        await r.zadd(key, {member: ts})
        await r.zremrangebyscore(key, -float("inf"), ts - 900)
        recent = await r.zrange(key, 0, -1, withscores=True)
        cluster_size = len(recent)
        if cluster_size >= 3:
            tags.append("Penumbra Settlement Cluster")
    except Exception:
        cluster_size = 1
    signal: Dict[str, Any] = {
        "type": "penumbra",
        "sub_type": "unshield",
        "amount_usd": amt_usd,
        "receiver": recv,
        "timestamp": ts,
        "tags": tags,
        "summary": f"Penumbra unshield ${amt_usd:,.0f} → {recv[:10]}...",
    }
    # Fire into global signal pipeline
    await publish_signal(signal)
