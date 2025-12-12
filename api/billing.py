from typing import Optional, Dict, Any
import time

from app.redis_utils import get_redis, REDIS_ENABLED
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.config import (
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
    STRIPE_PRICE_PRO_MONTHLY,
    STRIPE_PRICE_INSTITUTIONAL_MONTHLY,
    STRIPE_SUCCESS_URL,
    STRIPE_CANCEL_URL,
    LOCAL_LAN_IP,
)

try:
    import stripe as _stripe
    _STRIPE_AVAILABLE = True
except Exception:
    _stripe = None
    _STRIPE_AVAILABLE = False

from observability.metrics import (
    billing_checkout_session_created,
    billing_checkout_completed,
    billing_webhook_failures,
    billing_webhook_duplicates,
)

router = APIRouter()


class CheckoutRequest(BaseModel):
    tier: str
    success_url: str
    cancel_url: str
    customer_email: Optional[str] = None


async def _r():
    return await get_redis()


def _features_for_tier(tier: str) -> Dict[str, Any]:
    t = (tier or "free").lower()
    return {
        "tier": t,
        "features": {
            "realtime": t in ("pro", "institutional"),
            "impact_card": t in ("pro", "institutional"),
            "export": t in ("institutional",),
        },
    }


@router.get("/me")
async def me(request: Request) -> Dict[str, Any]:
    # Prefer middleware-resolved tier; else resolve by email; allow dev override via X-Plan
    middleware_tier = (getattr(request.state, "user_tier", None) or "").lower()
    email = (getattr(request.state, "user_email", None) or request.headers.get("X-User-Email") or "").strip().lower()
    plan = middleware_tier or "free"
    expires_iso = None
    source = None
    try:
        if email and REDIS_ENABLED:
            r = await _r()
            v = await r.get(f"billing:user:{email}")
            exp = await r.get(f"billing:user_expiry:{email}")
            src = await r.get(f"billing:user_source:{email}")
            if v:
                plan = v
            if exp:
                try:
                    import datetime as _dt
                    expires_iso = _dt.datetime.utcfromtimestamp(int(exp)).isoformat() + "Z"
                except Exception:
                    expires_iso = None
                try:
                    if not middleware_tier and int(exp) < int(time.time()):
                        plan = "free"
                except Exception:
                    pass
            if src:
                source = src
    except Exception:
        pass
    override = (request.headers.get("X-Plan") or "").strip().lower()
    if override:
        plan = override
        source = "override"
    resp = _features_for_tier(plan)
    if source:
        resp["source"] = source
    if expires_iso:
        resp["expires"] = expires_iso
    return resp


@router.post("/billing/create-checkout-session")
async def create_checkout_session(body: CheckoutRequest) -> Dict[str, Any]:
    tier = body.tier.lower()
    if tier not in ("pro", "institutional"):
        raise HTTPException(status_code=400, detail="invalid tier")
    price = STRIPE_PRICE_PRO_MONTHLY if tier == "pro" else STRIPE_PRICE_INSTITUTIONAL_MONTHLY
    # Derive success/cancel URLs if not provided in body
    def _stub_url() -> str:
        if LOCAL_LAN_IP:
            return f"http://{LOCAL_LAN_IP}:8000/static/web_stub.html"
        return "http://127.0.0.1:8000/static/web_stub.html"
    success_url = body.success_url or STRIPE_SUCCESS_URL or _stub_url()
    cancel_url = body.cancel_url or STRIPE_CANCEL_URL or _stub_url()
    if _STRIPE_AVAILABLE and STRIPE_SECRET_KEY and price:
        try:
            _stripe.api_key = STRIPE_SECRET_KEY  # type: ignore[attr-defined]
            params = {
                "mode": "subscription",
                "line_items": [{"price": price, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {"tier": tier},
            }
            if body.customer_email:
                params["customer_email"] = body.customer_email
            session = _stripe.checkout.Session.create(**params)  # type: ignore[attr-defined]
            try:
                billing_checkout_session_created.labels(tier=tier).inc()
            except Exception:
                pass
            return {"checkout_url": session.url}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"stripe_error: {e}")
    try:
        billing_checkout_session_created.labels(tier=tier).inc()
    except Exception:
        pass
    return {"checkout_url": f"{success_url}?stub_session=1&tier={tier}"}


@router.post("/billing/webhook")
async def stripe_webhook(request: Request) -> Dict[str, Any]:
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    event: Optional[Dict[str, Any]] = None
    if _STRIPE_AVAILABLE and STRIPE_WEBHOOK_SECRET:
        try:
            evt = _stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)  # type: ignore[attr-defined]
            event = evt
        except Exception as e:
            try:
                billing_webhook_failures.labels(reason="invalid_signature").inc()
            except Exception:
                pass
            raise HTTPException(status_code=400, detail=f"invalid_signature: {e}")
    else:
        event = None
    if event:
        # Extract safely from Stripe Event object
        et = (getattr(event, "type", "") or "").lower() if not isinstance(event, dict) else (event.get("type") or "").lower()
        data_obj = getattr(event, "data", None)
        obj = (getattr(data_obj, "object", {}) if data_obj is not None else {})
        if isinstance(event, dict):
            obj = event.get("data", {}).get("object", {})
        # Idempotency: ignore duplicates by event id
        ev_id = getattr(event, "id", "") if not isinstance(event, dict) else (event.get("id") or "")
        is_new = True
        try:
            r = await _redis()
            if ev_id:
                is_new = await r.set(f"stripe_event:{ev_id}", "1", nx=True, ex=3600)
        except Exception:
            is_new = True
        if not is_new:
            try:
                billing_webhook_duplicates.inc()
            except Exception:
                pass
            return {"status": "duplicate"}
        if et == "checkout.session.completed":
            tier = ((obj.get("metadata") or {}).get("tier") if isinstance(obj, dict) else getattr(getattr(obj, "metadata", {}), "get", lambda *_: None)("tier")) or "pro"
            email = ((obj.get("customer_details") or {}).get("email") if isinstance(obj, dict) else getattr(getattr(obj, "customer_details", {}), "email", "")) or ""
            if email:
                try:
                    r = await _redis()
                    await r.set(f"billing:user:{email.lower()}", tier)
                except Exception:
                    try:
                        billing_webhook_failures.labels(reason="persist_failed").inc()
                    except Exception:
                        pass
            try:
                billing_checkout_completed.labels(tier=tier).inc()
            except Exception:
                pass
    return {"status": "ok"}
