from datetime import datetime, timezone
from typing import List, Dict, Any

from fastapi import APIRouter

from bus.signal_bus import fetch_recent_signals

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/debug/recent_signals")
async def recent_signals() -> Dict[str, Any]:
    # fetch last hour of signals and return the last 10 with tx hashes
    sigs: List[Dict[str, Any]] = await fetch_recent_signals(window_seconds=3600)
    with_hash = [s for s in sigs if isinstance(s, dict) and s.get("tx_hash")]
    # sort by timestamp (if present)
    with_hash.sort(key=lambda s: int(s.get("timestamp", 0)), reverse=True)
    out = [{
        "type": s.get("type"),
        "tx_hash": s.get("tx_hash"),
        "timestamp": s.get("timestamp"),
        "summary": s.get("summary"),
    } for s in with_hash[:10]]
    return {"recent": out, "count": len(out), "updated_at": _now_iso()}
