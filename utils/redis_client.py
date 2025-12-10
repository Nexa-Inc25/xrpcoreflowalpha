"""
Shared Redis client with graceful degradation when Redis is unavailable.
This module now redirects to app.redis_utils for consistent Redis handling.
"""
from app.redis_utils import get_redis, REDIS_ENABLED

# Export the same interface for backward compatibility
__all__ = ['get_redis', 'redis_available']


def redis_available() -> bool:
    """Check if Redis is available (URL is valid)."""
    return REDIS_ENABLED
