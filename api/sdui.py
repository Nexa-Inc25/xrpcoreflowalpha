from datetime import datetime, timezone
from fastapi import APIRouter

from bus.signal_bus import fetch_recent_cross_signals
from sdui.generator import generate_sdui_payload

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/sdui/feed")
async def get_sdui_feed():
    crosses = await fetch_recent_cross_signals(limit=10)
    payloads = [generate_sdui_payload(c) for c in crosses]
    return {"feed": payloads, "updated_at": _now_iso()}
