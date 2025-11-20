import json
import time
from typing import Optional

import httpx
import redis.asyncio as redis

from app.config import COINGECKO_API_BASE, COINGECKO_API_KEY, REDIS_URL
from utils.retry import async_retry

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


@async_retry(max_attempts=5, delay=1, backoff=2)
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
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{COINGECKO_API_BASE}/simple/price", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            usd = float(data.get(coin_id, {}).get("usd", 0.0))
    except Exception:
        usd = 0.0
    if usd > 0:
        await r.set(cache_key, str(usd), ex=ttl_seconds)
    return usd


@async_retry(max_attempts=5, delay=1, backoff=2)
async def get_price_usd_at(symbol: str, ts_sec: int, ttl_seconds: int = 300) -> float:
    """Fetch historical USD price for a symbol at a specific Unix timestamp (seconds).
    Uses Coingecko market_chart/range and caches results in Redis.
    """
    symbol = symbol.lower()
    coin_id = _COINGECKO_IDS.get(symbol)
    if not coin_id:
        return 0.0
    r = await _get_redis()
    bucket = int(ts_sec // 60)  # minute bucket to reduce API calls
    cache_key = f"price_at:{symbol}:{bucket}"
    cached = await r.get(cache_key)
    if cached:
        try:
            return float(cached)
        except Exception:
            pass
    start = max(0, ts_sec - 600)
    end = ts_sec + 600
    params = {"vs_currency": "usd", "from": start, "to": end}
    headers = {"accept": "application/json"}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(f"{COINGECKO_API_BASE}/coins/{coin_id}/market_chart/range", params=params, headers=headers)
            if resp.status_code != 200:
                return 0.0
            data = resp.json()
    except Exception:
        return 0.0
    prices = data.get("prices") or []
    if not prices:
        return 0.0
    target_ms = ts_sec * 1000
    best = min(prices, key=lambda p: abs((p[0] if isinstance(p, list) else 0) - target_ms))
    try:
        val = float(best[1])
    except Exception:
        val = 0.0
    if val > 0:
        await r.set(cache_key, str(val), ex=ttl_seconds)
    return val
