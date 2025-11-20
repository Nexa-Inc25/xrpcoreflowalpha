from datetime import datetime, timezone
import time
from typing import Dict, Any, List
from fastapi import APIRouter

from bus.signal_bus import fetch_recent_cross_signals, fetch_recent_signals
from sdui.generator import (
    generate_sdui_payload,
    generate_trustline_payload,
    generate_rwa_amm_payload,
    generate_orderbook_payload,
    generate_redis_monitor_payload,
)
from api.health import redis_stats

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/sdui/feed")
async def get_sdui_feed():
    crosses = await fetch_recent_cross_signals(limit=10)
    trustlines = await fetch_recent_signals(window_seconds=3600, types=["trustline"])  # last hour
    rwa_amms = await fetch_recent_signals(window_seconds=1800, types=["rwa_amm"])  # last 30m
    orderbooks = await fetch_recent_signals(window_seconds=900, types=["orderbook"])  # last 15m
    items = []
    for c in crosses:
        p = generate_sdui_payload(c)
        items.append((p.get("timestamp"), p))
    for t in trustlines[-10:]:  # cap trustlines considered
        p = generate_trustline_payload(t)
        items.append((p.get("timestamp"), p))
    for a in rwa_amms[-10:]:
        p = generate_rwa_amm_payload(a)
        items.append((p.get("timestamp"), p))
    for ob in orderbooks[-10:]:
        p = generate_orderbook_payload(ob)
        items.append((p.get("timestamp"), p))
    # Redis observability card (best-effort; ignore on failure)
    try:
        stats = await redis_stats()
        rp = generate_redis_monitor_payload(stats)
        items.append((rp.get("timestamp"), rp))
    except Exception:
        pass
    # sort by timestamp desc
    items.sort(key=lambda x: x[0] or "", reverse=True)
    feed = [p for _, p in items[:12]]
    return {"feed": feed, "updated_at": _now_iso()}


def _event_message(c: Dict[str, Any]) -> str:
    try:
        s1, s2 = c.get("signals", [{}])[0], (c.get("signals", [{}])[1] if len(c.get("signals", [])) > 1 else {})
        def _sum(sig: Dict[str, Any]) -> str:
            return sig.get("summary") or sig.get("type", "").upper()
        return f"{_sum(s1)} → {_sum(s2)} | conf {int(c.get('confidence', 0))} | impact {float(c.get('predicted_impact_pct') or 0.0):+.2f}%"
    except Exception:
        return "Cross signal"


@router.get("/ui")
async def ui_payload():
    # Build a SwiftUI-friendly SDUI root payload from real crosses
    crosses: List[Dict[str, Any]] = await fetch_recent_cross_signals(limit=50)
    now = int(time.time())
    # High-confidence crosses in last 5 minutes
    recent_hi = [c for c in crosses if (now - int(c.get("timestamp", 0)) <= 300) and int(c.get("confidence", 0)) >= 90]
    surge_mode = len(recent_hi) > 3
    events = [{
        "timestamp": datetime.fromtimestamp(int(c.get("timestamp", now)), timezone.utc).isoformat(),
        "message": _event_message(c),
        "confidence": int(c.get("confidence", 0)),
    } for c in crosses[-20:]]
    root = {
        "type": "VStack",
        "spacing": 20,
        "children": [
            {"type": "Header", "title": "DarkFlow Tracker", "subtitle": f"Surge Mode: {'🟥 ACTIVE' if surge_mode else '🟢 Normal'}"},
            {"type": "LiveCounter", "label": "Events Last 5min", "value": len(recent_hi)},
            {"type": "EventList", "events": events},
            {"type": "PredictiveBanner", "visible": surge_mode, "text": "🔥 High-volume flow detected – preparing market impact forecast"},
            {"type": "Footer", "text": f"Real-time • Public data • {datetime.now(timezone.utc).strftime('%b %d %Y')}"},
        ],
    }
    return root
