from datetime import datetime, timezone
from fastapi import APIRouter

from bus.signal_bus import fetch_recent_cross_signals, fetch_recent_signals
from sdui.generator import generate_sdui_payload, generate_trustline_payload

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/sdui/feed")
async def get_sdui_feed():
    crosses = await fetch_recent_cross_signals(limit=10)
    trustlines = await fetch_recent_signals(window_seconds=3600, types=["trustline"])  # last hour
    items = []
    for c in crosses:
        p = generate_sdui_payload(c)
        items.append((p.get("timestamp"), p))
    for t in trustlines[-10:]:  # cap trustlines considered
        p = generate_trustline_payload(t)
        items.append((p.get("timestamp"), p))
    # sort by timestamp desc
    items.sort(key=lambda x: x[0] or "", reverse=True)
    feed = [p for _, p in items[:12]]
    return {"feed": feed, "updated_at": _now_iso()}
