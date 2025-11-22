from datetime import datetime, timezone
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException

from bus.signal_bus import fetch_recent_signals
from bus.signal_bus import publish_signal, publish_cross_signal
import time
from app.config import APP_ENV

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/debug/recent_signals")
async def recent_signals() -> Dict[str, Any]:
    # fetch last hour of signals and return the last 10 with tx hashes
    sigs: List[Dict[str, Any]] = await fetch_recent_signals(window_seconds=3600)
    with_hash = [s for s in sigs if isinstance(s, dict) and (s.get("tx_hash") or s.get("tx_sig"))]
    # sort by timestamp (if present)
    with_hash.sort(key=lambda s: int(s.get("timestamp", 0)), reverse=True)
    out = [{
        "type": s.get("type"),
        "tx_hash": s.get("tx_hash") or s.get("tx_sig"),
        "timestamp": s.get("timestamp"),
        "summary": s.get("summary"),
    } for s in with_hash[:10]]
    return {"recent": out, "count": len(out), "updated_at": _now_iso()}


@router.post("/debug/trigger_test_event")
async def trigger_test_event() -> Dict[str, Any]:
    """Publishes synthetic cross signals to flip surge_mode and one zk event with large inferred USD.
    Safe in dev; ignored by production logic beyond the normal signal bus.
    """
    if str(APP_ENV).lower() in ("prod", "production"):  # safety
        raise HTTPException(status_code=403, detail="disabled in production")
    now = int(time.time())
    # 4 high-confidence cross events within window to trigger surge
    for i in range(4):
        cross = {
            "id": f"cross:test:{now}:{i}",
            "timestamp": now - (i * 10),
            "confidence": 95,
            "predicted_impact_pct": 1.8,
            "signals": [
                {"type": "zk", "summary": "Verifier call", "timestamp": now},
                {"type": "orderbook", "summary": "Depth shift", "timestamp": now},
            ],
            "tags": ["GoDark"],
        }
        try:
            await publish_cross_signal(cross)
        except Exception:
            pass
    # One zk proof-like event with large inferred USD to drive impact card
    zk = {
        "type": "zk",
        "sub_type": "verifier_call",
        "network": "eth",
        "tx_hash": f"0xTEST{now}",
        "gas_used": 850_000,
        "to": "0x010ffc9a",
        "from": "0xcd531ae9efcce479654c4926dec5f6209531ca7b",
        "gas_price_wei": 45_000_000_000,
        "value_wei": 0,
        "input_len": 560,
        "selector": "0x010ffc9a",
        "calldata_entropy": 7.6,
        "zero_value": 1,
        "partner_from": 1,
        "partner_to": 0,
        "usd_value": 50_000_000.0,
        "timestamp": now,
        "summary": "TEST ZK verify",
        "tags": ["Renegade Proof"],
    }
    try:
        await publish_signal(zk)
    except Exception:
        pass
    return {"status": "ok", "surge_seeded": 4, "zk_seeded": True, "updated_at": _now_iso()}


@router.get("/sentry-debug")
async def sentry_debug(verify: str = ""):
    """Temporary endpoint to verify Sentry. Append ?verify=sentry to trigger.
    Remove this after confirming events appear in Sentry.
    """
    if verify != "sentry":
        raise HTTPException(status_code=404, detail="Not Found")
    # This will be captured by Sentry as an unhandled exception
    _ = 1 / 0
    return {"ok": True}

