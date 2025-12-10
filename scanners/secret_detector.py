import time
from typing import Any, Dict, Optional

from app.redis_utils import get_redis, REDIS_ENABLED

from app.config import REDIS_URL, SECRET_UNSHIELD_MIN_USD
from bus.signal_bus import publish_signal

_redis = None  # Redis client instance


async def _get_redis() :
    global _redis
    if _redis is None:
        _redis = await get_redis()
    return _redis


async def handle_secret_unshield(event: Dict[str, Any]) -> None:
    """Process a Secret Network unshielding event and emit a signal.

    This helper expects an event dict with at least:
      - amount_usd: float-like
      - receiver: str
      - timestamp: int (seconds)
    Any upstream Secret/Cosmos listener can call this with real
    mainnet data. It is side-effect free on malformed events.
    """
    try:
        amt_usd = float(event.get("amount_usd") or 0.0)
    except Exception:
        amt_usd = 0.0
    if amt_usd < float(SECRET_UNSHIELD_MIN_USD):
        return
    ts = int(event.get("timestamp") or int(time.time()))
    recv = str(event.get("receiver") or "")
    tags = ["Secret Unshield"]
    # Cluster detection via Redis window
    try:
        r = await _get_redis()
        key = "secret:unshields"
        member = f"{recv}:{ts}"
        await r.zadd(key, {member: ts})
        await r.zremrangebyscore(key, -float("inf"), ts - 600)
        recent = await r.zrange(key, 0, -1, withscores=True)
        cluster_size = len(recent)
        if cluster_size >= 3:
            tags.append("Secret Settlement Cluster")
    except Exception:
        cluster_size = 1
    signal: Dict[str, Any] = {
        "type": "secret",
        "sub_type": "unshield",
        "amount_usd": amt_usd,
        "receiver": recv,
        "timestamp": ts,
        "tags": tags,
        "summary": f"Secret unshield ${amt_usd:,.0f} → {recv[:10]}...",
    }
    await publish_signal(signal)
