import asyncio
import csv
import io
import time
from typing import AsyncGenerator, Dict, Any, List, Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from bus.signal_bus import fetch_recent_signals, fetch_recent_cross_signals

router = APIRouter()


def _now_s() -> int:
    return int(time.time())


def _row_from_signal(sig: Dict[str, Any]) -> List[str]:
    ts = sig.get("timestamp")
    try:
        ts = int(ts)
    except Exception:
        ts = 0
    type_ = str(sig.get("type") or "").lower()
    tx = str(sig.get("tx_hash") or sig.get("hash") or sig.get("tx_sig") or "")
    usd = sig.get("usd_value")
    try:
        usd = float(usd)
    except Exception:
        usd = ""
    conf = sig.get("confidence")
    try:
        conf = int(conf)
    except Exception:
        conf = ""
    impact = sig.get("predicted_impact_pct")
    try:
        impact = float(impact)
    except Exception:
        impact = ""
    summary = sig.get("summary") or ""
    return [str(ts), type_, tx, str(usd), str(conf), str(impact), summary.replace("\n", " ")]


@router.get("/export/signals.csv")
async def export_signals(request: Request, window_seconds: int = 86400, types: Optional[str] = None) -> StreamingResponse:
    # Require authenticated API key and institutional tier
    if not getattr(request.state, "api_key_authenticated", False):
        raise HTTPException(status_code=401, detail="API key required")
    tier = (getattr(request.state, "user_tier", "") or "").lower()
    if tier != "institutional":
        raise HTTPException(status_code=403, detail="institutional tier required")

    type_list: Optional[List[str]] = None
    if types:
        type_list = [t.strip().lower() for t in types.split(",") if t.strip()]

    # Fetch recent signals
    sigs = await fetch_recent_signals(window_seconds=window_seconds, types=type_list)  # type: ignore[arg-type]
    # Optionally include cross signals as well
    crosses = await fetch_recent_cross_signals(limit=1000)
    # merge limited window for crosses
    now = _now_s()
    for c in crosses:
        try:
            if now - int(c.get("timestamp", 0)) <= window_seconds:
                sigs.append(c)
        except Exception:
            pass

    # Sort by timestamp ascending
    try:
        sigs.sort(key=lambda s: int(s.get("timestamp", 0)))
    except Exception:
        pass

    header = ["timestamp", "type", "tx_hash", "usd_value", "confidence", "predicted_impact_pct", "summary"]

    async def streamer() -> AsyncGenerator[bytes, None]:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate(0)
        # Stream rows in chunks
        for sig in sigs:
            writer.writerow(_row_from_signal(sig))
            if buf.tell() > 64 * 1024:
                yield buf.getvalue().encode("utf-8")
                buf.seek(0)
                buf.truncate(0)
            # be friendly to event loop
            await asyncio.sleep(0)
        # flush remainder
        if buf.tell() > 0:
            yield buf.getvalue().encode("utf-8")

    return StreamingResponse(
        streamer(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=darkflow_signals.csv"},
    )
