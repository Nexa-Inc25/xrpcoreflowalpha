import asyncio
from typing import Iterable

from app.redis_utils import get_redis, REDIS_ENABLED

from app.config import (
    REDIS_URL,
    GODARK_XRPL_PARTNERS,
    GODARK_ETH_PARTNERS,
    GODARK_DYNAMIC_REFRESH_SECONDS,
)


async def _sadd_all(r: redis.Redis, key: str, vals: Iterable[str]) -> int:
    items = [v.strip() for v in vals if v and v.strip()]
    if not items:
        return 0
    return await r.sadd(key, *items)


async def run_dynamic_ingest():
    r = await get_redis()
    while True:
        try:
            await _sadd_all(r, "godark:partners:xrpl", [a.lower() for a in GODARK_XRPL_PARTNERS])
            await _sadd_all(r, "godark:partners:ethereum", [a.lower() for a in GODARK_ETH_PARTNERS])
            print("[GODARK] Dynamic ingest sync completed")
        except Exception as e:
            print("[GODARK] dynamic ingest error:", repr(e))
        await asyncio.sleep(GODARK_DYNAMIC_REFRESH_SECONDS)
