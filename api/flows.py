from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from bus.signal_bus import fetch_recent_signals
from api.ui import _format_event

router = APIRouter()


@router.get("/flows")
async def list_flows(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    window_seconds: int = Query(86400, ge=1),
    types: Optional[str] = None,
    min_confidence: Optional[int] = Query(None, ge=0, le=100),
    network: Optional[str] = None,
    tx_hash: Optional[str] = None,
    raw: bool = Query(False, description="Return raw unprocessed data for alpha extraction"),
    correlation_asset: Optional[str] = Query(None, description="Filter by correlated asset (e.g., SPY)"),
) -> Dict[str, Any]:
    type_list: Optional[List[str]] = None
    if types:
        type_list = [t.strip().lower() for t in types.split(",") if t.strip()]
    signals = await fetch_recent_signals(window_seconds=window_seconds, types=type_list)
    filtered: List[Dict[str, Any]] = []
    net_norm = (network or "").strip().lower() if network else None
    tx_norm = (tx_hash or "").strip().lower() if tx_hash else None
    for s in signals:
        if net_norm:
            sn = str(s.get("network") or "").strip().lower()
            if sn != net_norm:
                continue
        if tx_norm:
            th = str(s.get("tx_hash") or "").strip().lower()
            if th != tx_norm:
                continue
        if min_confidence is not None:
            try:
                c = int(s.get("confidence", 0))
            except Exception:
                c = 0
            if c < min_confidence:
                continue
        filtered.append(s)
    try:
        filtered.sort(key=lambda x: int(x.get("timestamp", 0)), reverse=True)
    except Exception:
        pass
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]
    
    # Raw mode: return unprocessed data for alpha extraction
    if raw:
        items = page_items  # No formatting/scoring
    else:
        items = [_format_event(s) for s in page_items]
    
    response = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": items,
        "raw_mode": raw,
    }
    
    if raw:
        response["alpha_note"] = "Raw data bypasses ML scoring. Use for custom alpha strategies."
    if correlation_asset:
        response["correlation_filter"] = correlation_asset.upper()
    
    return response
