import asyncio
import logging
import random
from functools import wraps

logger = logging.getLogger(__name__)


def async_retry(max_attempts: int = 5, delay: float = 1.0, backoff: float = 2.0):
    def decorator(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            for i in range(max_attempts):
                try:
                    return await f(*args, **kwargs)
                except Exception as e:
                    # Check for WebSocket connection errors that shouldn't retry
                    error_msg = str(e).lower()
                    if "websocket is not open" in error_msg or "connection closed" in error_msg:
                        # These errors need reconnection, not retry
                        logger.error(f"[RETRY] {f.__name__} failed: {e}")
                        raise ConnectionError(f"WebSocket connection lost: {e}")
                    
                    if i == max_attempts - 1:
                        logger.error(f"[RETRY] {f.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    wait = delay * (backoff ** i)
                    logger.warning(f"[RETRY] {f.__name__} attempt {i+1}/{max_attempts} failed, retrying in {wait:.1f}s")
                    await asyncio.sleep(wait)
        return wrapper
    return decorator
