from datetime import datetime, timezone
from fastapi import APIRouter

from bus.signal_bus import fetch_recent_cross_signals, fetch_recent_signals
from sdui.generator import (
    generate_sdui_payload,
    generate_trustline_payload,
    generate_rwa_amm_payload,
    generate_orderbook_payload,
)

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
    # sort by timestamp desc
    items.sort(key=lambda x: x[0] or "", reverse=True)
    feed = [p for _, p in items[:12]]
    return {"feed": feed, "updated_at": _now_iso()}
