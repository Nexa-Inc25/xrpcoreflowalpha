import secrets
import time
from typing import Optional, Dict, Any

import redis.asyncio as redis
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import (
    REDIS_URL,
    SOL_TREASURY,
    ETH_TREASURY,
    SOL_USDC_MINT,
    ETH_USDC_ADDRESS,
    ONCHAIN_PRO_SOL_MONTHLY,
    ONCHAIN_PRO_SOL_ANNUAL,
    ONCHAIN_INST_SOL_MONTHLY,
    ONCHAIN_INST_SOL_ANNUAL,
    ONCHAIN_PRO_ETH_MONTHLY,
    ONCHAIN_PRO_ETH_ANNUAL,
    ONCHAIN_INST_ETH_MONTHLY,
    ONCHAIN_INST_ETH_ANNUAL,
    ONCHAIN_PRO_USDC_MONTHLY,
    ONCHAIN_INST_USDC_MONTHLY,
)
from observability.metrics import pending_payment_total

router = APIRouter()


class OnchainStartRequest(BaseModel):
    tier: str  # "pro" | "institutional"
    asset: str  # "sol" | "eth" | "usdc"
    duration: str  # "monthly" | "annual"
    email: Optional[str] = None


async def _r() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def _price_for(tier: str, asset: str, duration: str) -> float:
    t = tier.lower(); a = asset.lower(); d = duration.lower()
    if t not in ("pro", "institutional"):
        raise HTTPException(status_code=400, detail="invalid tier")
    if a not in ("sol", "eth", "usdc"):
        raise HTTPException(status_code=400, detail="invalid asset")
    if d not in ("monthly", "annual"):
        raise HTTPException(status_code=400, detail="invalid duration")
    if a == "sol":
        if t == "pro":
            return ONCHAIN_PRO_SOL_ANNUAL if d == "annual" else ONCHAIN_PRO_SOL_MONTHLY
        return ONCHAIN_INST_SOL_ANNUAL if d == "annual" else ONCHAIN_INST_SOL_MONTHLY
    if a == "eth":
        if t == "pro":
            return ONCHAIN_PRO_ETH_ANNUAL if d == "annual" else ONCHAIN_PRO_ETH_MONTHLY
        return ONCHAIN_INST_ETH_ANNUAL if d == "annual" else ONCHAIN_INST_ETH_MONTHLY
    # usdc
    if t == "pro":
        return ONCHAIN_PRO_USDC_MONTHLY
    return ONCHAIN_INST_USDC_MONTHLY


def _address_for(asset: str) -> str:
    a = asset.lower()
    if a == "sol":
        if not SOL_TREASURY:
            raise HTTPException(status_code=400, detail="solana treasury not configured")
        return SOL_TREASURY
    if a == "eth":
        if not ETH_TREASURY:
            raise HTTPException(status_code=400, detail="ethereum treasury not configured")
        return ETH_TREASURY
    # usdc: prefer SOL if available, else ETH treasury
    if SOL_TREASURY:
        return SOL_TREASURY
    if ETH_TREASURY:
        return ETH_TREASURY
    raise HTTPException(status_code=400, detail="no treasury configured")


@router.post("/billing/onchain/start")
async def onchain_start(body: OnchainStartRequest, request: Request) -> Dict[str, Any]:
    amount = _price_for(body.tier, body.asset, body.duration)
    addr = _address_for(body.asset)
    # pull email from body or header
    email = (body.email or request.headers.get("X-User-Email") or "").strip().lower()
    if not email:
        # allow starting without email, but upgrade will require mapping via admin later
        pass
    ref = f"pay_{body.tier}_{secrets.token_urlsafe(10)}"
    r = await _r()
    await r.hset(f"onchain:pending:{ref}", mapping={
        "tier": body.tier.lower(),
        "asset": body.asset.lower(),
        "duration": body.duration.lower(),
        "amount": str(amount),
        "address": addr,
        "email": email,
        "status": "pending",
        "created_at": str(int(time.time())),
    })
    try:
        pending_payment_total.labels(source="onchain_start").inc()
    except Exception:
        pass
    # Basic payment URI hint (best-effort)
    payment_uri = {
        "sol": f"solana:{addr}?amount={amount}&memo={ref}",
        "eth": f"ethereum:{addr}?value={amount}&data={ref.encode().hex()}",
        "usdc": f"usdc:{addr}?amount={amount}&memo={ref}",
    }.get(body.asset.lower(), f"pay:{addr}?amount={amount}&ref={ref}")
    return {
        "address": addr,
        "amount": amount,
        "asset": body.asset.lower(),
        "tier": body.tier.lower(),
        "duration": body.duration.lower(),
        "payment_ref": ref,
        "memo": ref,
        "payment_uri": payment_uri,
        "qr_url": payment_uri,
    }
