import time
from typing import Optional, Dict, Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.redis_utils import get_redis, REDIS_ENABLED


async def _r():
    return await get_redis()


async def api_key_middleware(request: Request, call_next):
    # Default plan hints from headers
    plan_hdr = (request.headers.get("X-Plan") or "").lower().strip()
    email_hdr = (request.headers.get("X-User-Email") or "").strip().lower()
    if plan_hdr:
        request.state.user_tier = plan_hdr
    if email_hdr:
        request.state.user_email = email_hdr

    api_key = (request.headers.get("X-API-Key") or "").strip()
    if not api_key:
        return await call_next(request)

    if not REDIS_ENABLED:
        # When Redis is disabled, skip API key validation
        return await call_next(request)

    r = await _r()
    data = await r.hgetall(f"api:key:{api_key}")
    if not data:
        # Unknown key: proceed without tier (client may still use billing headers)
        return await call_next(request)

    tier = (data.get("tier") or "").lower()
    email = (data.get("email") or "").lower()
    request.state.user_tier = tier or getattr(request.state, "user_tier", None)
    request.state.user_email = email or getattr(request.state, "user_email", None)
    request.state.api_key_authenticated = True

    # Simple per-key rate limit for non-institutional: 10 req/sec
    if tier != "institutional" and REDIS_ENABLED:
        now_bucket = int(time.time())
        key = f"ratelimit:{api_key}:{now_bucket}"
        try:
            cnt = await r.incr(key)
            if cnt == 1:
                await r.expire(key, 1)
            if cnt > 10:
                return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        except Exception:
            pass

    return await call_next(request)
