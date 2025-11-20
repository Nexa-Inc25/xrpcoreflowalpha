import asyncio
import logging
import random
from functools import wraps

logger = logging.getLogger(__name__)


def async_retry(max_attempts: int = 5, delay: float = 1.0, backoff: float = 2.0):
    def decorator(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            attempt = 0
            while attempt < max_attempts:
                try:
                    return await f(*args, **kwargs)
                except Exception as e:  # broad by design for production hardening
                    attempt += 1
                    if attempt >= max_attempts:
                        try:
                            logger.error(f"[RETRY] {f.__name__} failed after {max_attempts} attempts: {e}")
                        except Exception:
                            pass
                        raise
                    sleep = delay * (backoff ** (attempt - 1)) + random.uniform(0, 1)
                    try:
                        logger.warning(f"[RETRY] {f.__name__} attempt {attempt}/{max_attempts} failed, retrying in {sleep:.1f}s")
                    except Exception:
                        pass
                    await asyncio.sleep(sleep)
        return wrapper
    return decorator
