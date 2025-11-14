import json
import time
from typing import Optional

import httpx
import redis.asyncio as redis

from app.config import COINGECKO_API_BASE, COINGECKO_API_KEY, REDIS_URL

_redis: Optional[redis.Redis] = None


async def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


_COINGECKO_IDS = {
    "xrp": "ripple",
    "eth": "ethereum",
}


async def get_price_usd(symbol: str, ttl_seconds: int = 15) -> float:
    """Fetch USD price for a symbol (xrp|eth), with Redis caching."""
    symbol = symbol.lower()
    coin_id = _COINGECKO_IDS.get(symbol)
    if not coin_id:
        return 0.0
    r = await _get_redis()
    cache_key = f"price:{symbol}:usd"
    cached = await r.get(cache_key)
    if cached:
        try:
            return float(cached)
        except Exception:
            pass
    params = {"ids": coin_id, "vs_currencies": "usd"}
    headers = {"accept": "application/json"}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(f"{COINGECKO_API_BASE}/simple/price", params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        usd = float(data.get(coin_id, {}).get("usd", 0.0))
    if usd > 0:
        await r.set(cache_key, str(usd), ex=ttl_seconds)
    return usd
