"""
Stripe Billing Handler - Subscription management for ZK Alpha Flow
"""
import os
import stripe
from typing import Optional, Dict, Any

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Price IDs (will be created on first run)
PRICE_IDS = {
    "basic": os.getenv("STRIPE_PRICE_BASIC"),
    "pro": os.getenv("STRIPE_PRICE_PRO"),
}

# Plan features
PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "signals_per_day": 50,
        "features": [
            "50 signals/day",
            "XRPL scanner only",
            "15-min delay",
            "Web dashboard",
        ]
    },
    "basic": {
        "name": "Basic",
        "price": 79,
        "signals_per_day": 500,
        "features": [
            "500 signals/day",
            "All scanners",
            "Real-time alerts",
            "Slack integration",
            "Email support",
        ]
    },
    "pro": {
        "name": "Pro",
        "price": 199,
        "signals_per_day": -1,  # Unlimited
        "features": [
            "Unlimited signals",
            "All scanners + priority",
            "Instant alerts",
            "API access",
            "Correlation engine",
            "Priority support",
            "Custom webhooks",
        ]
    }
}


async def create_checkout_session(
    user_id: str,
    user_email: str,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    """Create a Stripe Checkout session for subscription."""
    if plan not in ["basic", "pro"]:
        raise ValueError(f"Invalid plan: {plan}")
    
    price_id = PRICE_IDS.get(plan)
    if not price_id:
        raise ValueError(f"Price ID not configured for plan: {plan}")
    
    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=user_email,
        metadata={"user_id": user_id, "plan": plan},
        subscription_data={
            "metadata": {"user_id": user_id, "plan": plan}
        },
    )
    
    return {
        "session_id": session.id,
        "url": session.url,
    }


async def create_portal_session(customer_id: str, return_url: str) -> str:
    """Create a Stripe Customer Portal session for managing subscription."""
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


async def get_subscription_status(customer_id: str) -> Optional[Dict[str, Any]]:
    """Get current subscription status for a customer."""
    try:
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status="active",
            limit=1,
        )
        
        if not subscriptions.data:
            return {"plan": "free", "status": "active"}
        
        sub = subscriptions.data[0]
        price_id = sub["items"]["data"][0]["price"]["id"]
        
        # Determine plan from price ID
        plan = "free"
        for plan_name, pid in PRICE_IDS.items():
            if pid == price_id:
                plan = plan_name
                break
        
        return {
            "plan": plan,
            "status": sub["status"],
            "current_period_end": sub["current_period_end"],
            "cancel_at_period_end": sub.get("cancel_at_period_end", False),
        }
    except Exception as e:
        print(f"[Stripe] Error getting subscription: {e}")
        return {"plan": "free", "status": "active"}


def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """Handle Stripe webhook events."""
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise ValueError("Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid signature")
    
    event_type = event["type"]
    data = event["data"]["object"]
    
    if event_type == "checkout.session.completed":
        # Subscription created
        user_id = data["metadata"].get("user_id")
        plan = data["metadata"].get("plan")
        customer_id = data["customer"]
        return {
            "action": "subscription_created",
            "user_id": user_id,
            "plan": plan,
            "customer_id": customer_id,
        }
    
    elif event_type == "customer.subscription.updated":
        # Subscription changed
        user_id = data["metadata"].get("user_id")
        status = data["status"]
        return {
            "action": "subscription_updated",
            "user_id": user_id,
            "status": status,
        }
    
    elif event_type == "customer.subscription.deleted":
        # Subscription cancelled
        user_id = data["metadata"].get("user_id")
        return {
            "action": "subscription_cancelled",
            "user_id": user_id,
        }
    
    return {"action": "ignored", "event_type": event_type}
