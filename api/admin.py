import secrets
from typing import Optional, Dict, Any

import redis.asyncio as redis
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.config import REDIS_URL, ADMIN_PASSWORD

router = APIRouter()


async def _r() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def _require_admin(req: Request) -> None:
    pw = (req.headers.get("X-Admin-Password") or "").strip()
    if not ADMIN_PASSWORD or pw != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="forbidden")


class CreateKeyRequest(BaseModel):
    email: str
    tier: str  # "pro" | "institutional"


@router.post("/admin/keys")
async def create_key(req: Request, body: CreateKeyRequest) -> Dict[str, Any]:
    _require_admin(req)
    tier = body.tier.lower()
    if tier not in ("pro", "institutional"):
        raise HTTPException(status_code=400, detail="invalid tier")
    email = body.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="invalid email")
    api_key = secrets.token_urlsafe(24)
    r = await _r()
    await r.set(f"billing:user:{email}", tier)
    await r.hset(f"api:key:{api_key}", mapping={"email": email, "tier": tier})
    await r.set(f"api:key:by_email:{email}", api_key)
    return {"email": email, "tier": tier, "api_key": api_key}


@router.get("/admin/keys")
async def get_key(req: Request, email: Optional[str] = None) -> Dict[str, Any]:
    _require_admin(req)
    r = await _r()
    if email:
        email_l = email.strip().lower()
        k = await r.get(f"api:key:by_email:{email_l}")
        if not k:
            return {"email": email_l, "found": False}
        data = await r.hgetall(f"api:key:{k}")
        return {"email": email_l, "api_key": k, "tier": data.get("tier")}
    # Without email, list summary count only to avoid dumping secrets
    return {"status": "ok"}


@router.delete("/admin/keys")
async def delete_key(req: Request, email: str) -> Dict[str, Any]:
    _require_admin(req)
    email_l = email.strip().lower()
    r = await _r()
    k = await r.get(f"api:key:by_email:{email_l}")
    if not k:
        return {"email": email_l, "deleted": False}
    await r.delete(f"api:key:{k}")
    await r.delete(f"api:key:by_email:{email_l}")
    return {"email": email_l, "deleted": True}
