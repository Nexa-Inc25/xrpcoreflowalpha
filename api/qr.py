import secrets
import urllib.parse
import time
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse

from api.onchain import _r as _redis, _price_for, _address_for
from observability.metrics import pending_payment_total

router = APIRouter()


def _chart_qr(url: str, size: int = 200) -> str:
    encoded = urllib.parse.quote(url, safe="")
    return f"https://chart.googleapis.com/chart?chs={size}x{size}&cht=qr&chl={encoded}"


@router.get("/qr/current_user_pro_sol")
async def qr_current_user_pro_sol(request: Request, duration: str = "monthly") -> RedirectResponse:
    email = (request.headers.get("X-User-Email") or "").strip().lower()
    # Build pending payment identical to /billing/onchain/start
    amount = _price_for("pro", "sol", duration)
    addr = _address_for("sol")
    r = await _redis()
    # QR cache key per-user for 30 minutes
    cache_key = f"onchain:last_ref:{email or 'anon'}:pro:sol"
    ref = await r.get(cache_key)
    reuse = False
    if ref:
        p = await r.hgetall(f"onchain:pending:{ref}")
        if p and (p.get("status") or "") == "pending":
            reuse = True
    if not reuse:
        ref = f"pay_pro_{secrets.token_urlsafe(10)}"
        await r.hset(f"onchain:pending:{ref}", mapping={
            "tier": "pro",
            "asset": "sol",
            "duration": duration.lower(),
            "amount": str(amount),
            "address": addr,
            "email": email,
            "status": "pending",
            "created_at": str(int(time.time())),
        })
        try:
            pending_payment_total.labels(source="qr").inc()
        except Exception:
            pass
        await r.set(cache_key, ref, ex=1800)  # 30 minutes
    payment_uri = f"solana:{addr}?amount={amount}&memo={ref}"
    return RedirectResponse(_chart_qr(payment_uri))


@router.get("/qr/pay/{ref}")
async def qr_for_ref(ref: str) -> RedirectResponse:
    r = await _redis()
    p = await r.hgetall(f"onchain:pending:{ref}")
    if not p:
        raise HTTPException(status_code=404, detail="unknown payment ref")
    asset = (p.get("asset") or "sol").lower()
    addr = p.get("address") or _address_for(asset)
    amount = p.get("amount") or ""
    if not addr or not amount:
        raise HTTPException(status_code=400, detail="invalid payment record")
    if asset == "eth":
        payment_uri = f"ethereum:{addr}?value={amount}&data={ref.encode().hex()}"
    elif asset == "usdc":
        payment_uri = f"usdc:{addr}?amount={amount}&memo={ref}"
    else:
        payment_uri = f"solana:{addr}?amount={amount}&memo={ref}"
    return RedirectResponse(_chart_qr(payment_uri))
