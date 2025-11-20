from typing import Optional, Dict, Any, List

import redis.asyncio as redis
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.config import REDIS_URL

router = APIRouter()


async def _r() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


class UserPreferences(BaseModel):
    alert_usd_min: Optional[float] = None
    networks: Optional[List[str]] = None  # e.g., ["ethereum","solana"]
    event_types: Optional[List[str]] = None  # e.g., ["zk","solana_amm","surge"]


def _email_from(req: Request) -> str:
    return (getattr(req.state, "user_email", None) or req.headers.get("X-User-Email") or "").strip().lower()


@router.post("/user/preferences")
async def set_preferences(request: Request, body: UserPreferences) -> Dict[str, Any]:
    email = _email_from(request)
    if not email:
        raise HTTPException(status_code=400, detail="email required via X-User-Email header or API key")
    r = await _r()
    data: Dict[str, Any] = {}
    if body.alert_usd_min is not None:
        data["alert_usd_min"] = str(float(body.alert_usd_min))
    if body.networks is not None:
        data["networks"] = ",".join([n.strip().lower() for n in body.networks if n.strip()])
    if body.event_types is not None:
        data["event_types"] = ",".join([t.strip().lower() for t in body.event_types if t.strip()])
    if not data:
        raise HTTPException(status_code=400, detail="no preferences provided")
    await r.hset(f"user:prefs:{email}", mapping=data)
    out = await r.hgetall(f"user:prefs:{email}")
    return {"email": email, "preferences": out}


@router.get("/user/preferences")
async def get_preferences(request: Request) -> Dict[str, Any]:
    email = _email_from(request)
    if not email:
        raise HTTPException(status_code=400, detail="email required via X-User-Email header or API key")
    r = await _r()
    out = await r.hgetall(f"user:prefs:{email}")
    return {"email": email, "preferences": out}
