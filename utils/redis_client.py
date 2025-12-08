"""
Shared Redis client with graceful degradation when Redis is unavailable.
"""
import os
from typing import Optional

import redis.asyncio as redis

from app.config import REDIS_URL

_redis: Optional[redis.Redis] = None
_redis_disabled: bool = False
_redis_warned: bool = False


async def get_redis() -> Optional[redis.Redis]:
    """
    Get Redis client. Returns None if Redis URL is invalid or connection fails.
    This allows the app to run in degraded mode without Redis.
    """
    global _redis, _redis_disabled, _redis_warned
    
    if _redis_disabled:
        return None
    
    if _redis is None:
        if not REDIS_URL:
            if not _redis_warned:
                print("[REDIS] REDIS_URL not configured - running without Redis")
                _redis_warned = True
            _redis_disabled = True
            return None
        try:
            _redis = redis.from_url(REDIS_URL, decode_responses=True)
            # Test connection
            await _redis.ping()
        except Exception as e:
            if not _redis_warned:
                print(f"[REDIS] Connection failed: {e} - running without Redis")
                _redis_warned = True
            _redis_disabled = True
            _redis = None
            return None
    
    return _redis


def redis_available() -> bool:
    """Check if Redis is available (URL is valid)."""
    return bool(REDIS_URL) and not _redis_disabled
