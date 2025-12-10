from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.redis_utils import get_redis, REDIS_ENABLED

router = APIRouter()


class RegisterRequest(BaseModel):
    token: str
    platform: str
    preferences: Optional[List[str]] = None
    email: Optional[str] = None


async def _r():
    return await get_redis()


@router.post("/notify/register")
async def register(body: RegisterRequest) -> Dict[str, Any]:
    t = body.token.strip()
    plat = body.platform.strip().lower()
    if not t or plat not in ("ios", "android"):
        raise HTTPException(status_code=400, detail="invalid token or platform")
    
    if not REDIS_ENABLED:
        return {"status": "ok", "token": t, "platform": plat, "redis": "disabled"}
    
    prefs = ",".join(sorted(set((body.preferences or []))))
    email = (body.email or "").strip().lower()
    r = await _r()
    await r.hset(f"push:device:{t}", mapping={"platform": plat, "preferences": prefs, "email": email})
    await r.sadd("push:tokens", t)
    await r.sadd(f"push:tokens:{plat}", t)
    return {"status": "ok", "token": t, "platform": plat}


class UnregisterRequest(BaseModel):
    token: str


@router.post("/notify/unregister")
async def unregister(body: UnregisterRequest) -> Dict[str, Any]:
    t = body.token.strip()
    if not t:
        raise HTTPException(status_code=400, detail="invalid token")
    
    if not REDIS_ENABLED:
        return {"status": "ok", "redis": "disabled"}
    
    r = await _r()
    await r.delete(f"push:device:{t}")
    await r.srem("push:tokens", t)
    await r.srem("push:tokens:ios", t)
    await r.srem("push:tokens:android", t)
    return {"status": "ok"}
