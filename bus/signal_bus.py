import json
import time
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from app.config import REDIS_URL

_redis: Optional[redis.Redis] = None


async def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def publish_signal(signal: Dict[str, Any]) -> None:
    r = await _get_redis()
    # Ensure required fields
    if "timestamp" not in signal:
        signal["timestamp"] = int(time.time())
    if "id" not in signal:
        signal["id"] = f"{signal.get('type','unknown')}:{signal['timestamp']}:{int(time.time()*1000)}"
    data = json.dumps(signal, separators=(",", ":"))
    await r.xadd("signals", {"json": data}, maxlen=5000, approximate=True)


async def fetch_recent_signals(window_seconds: int = 900, types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    r = await _get_redis()
    now_ms = int(time.time() * 1000)
    start = now_ms - window_seconds * 1000
    start_id = f"{start}-0"
    rows = await r.xrange("signals", min=start_id, max="+")
    out: List[Dict[str, Any]] = []
    for _, fields in rows:
        raw = fields.get("json")
        if not raw:
            continue
        try:
            s = json.loads(raw)
        except Exception:
            continue
        if types and s.get("type") not in types:
            continue
        out.append(s)
    return out
