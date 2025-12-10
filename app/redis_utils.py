"""
Redis utility functions with graceful fallback for optional Redis
"""

import os
from typing import Optional
import redis.asyncio as redis
from app.config import REDIS_URL

# Global flag to indicate if Redis is available
REDIS_ENABLED = bool(REDIS_URL and REDIS_URL.startswith(('redis://', 'rediss://', 'unix://')))

class FakeRedis:
    """Fake Redis client that returns None/empty for all operations"""
    
    async def get(self, key: str) -> Optional[str]:
        return None
    
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        pass
    
    async def hset(self, name: str, key: Optional[str] = None, value: Optional[str] = None, mapping: Optional[dict] = None) -> None:
        pass
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        return None
    
    async def hgetall(self, name: str) -> dict:
        return {}
    
    async def sadd(self, key: str, *values) -> None:
        pass
    
    async def srem(self, key: str, *values) -> None:
        pass
    
    async def smembers(self, key: str) -> set:
        return set()
    
    async def delete(self, *keys) -> None:
        pass
    
    async def exists(self, *keys) -> int:
        return 0
    
    async def expire(self, key: str, time: int) -> None:
        pass
    
    async def ttl(self, key: str) -> int:
        return -1
    
    async def publish(self, channel: str, message: str) -> None:
        pass
    
    def pubsub(self):
        """Return a fake pubsub object"""
        return FakePubSub()
    
    async def close(self):
        pass

class FakePubSub:
    """Fake PubSub client"""
    
    async def subscribe(self, *channels):
        pass
    
    async def unsubscribe(self, *channels):
        pass
    
    async def get_message(self, timeout: Optional[float] = None):
        return None
    
    async def listen(self):
        # Never yield anything
        return
        yield  # Make it a generator
    
    async def close(self):
        pass

_redis_client = None  # Redis client instance

async def get_redis():
    """
    Get Redis client with graceful fallback to FakeRedis if Redis is not available
    """
    global _redis_client
    
    if not REDIS_ENABLED:
        print("[Redis] Redis is disabled, using in-memory fallback")
        return FakeRedis()
    
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            # Test the connection
            await _redis_client.ping()
            print(f"[Redis] Connected to Redis at {REDIS_URL}")
        except Exception as e:
            print(f"[Redis] Failed to connect to Redis: {e}")
            print("[Redis] Falling back to in-memory mode")
            return FakeRedis()
    
    return _redis_client

async def close_redis():
    """Close Redis connection if it exists"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
