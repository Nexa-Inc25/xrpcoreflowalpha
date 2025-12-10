import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.redis_utils import get_redis, REDIS_ENABLED
from observability.metrics import replay_requests_total

router = APIRouter()


async def _r():
    return await get_redis()


def _now_ms() -> int:
    return int(time.time() * 1000)


@router.get("/history/replay")
async def replay(request: Request, days: int = 7, types: Optional[str] = None, order: str = "desc") -> StreamingResponse:
    r = await _r()
    window_s = max(1, int(days)) * 86400
    start_id = f"{_now_ms() - window_s * 1000}-0"
    type_list: Optional[List[str]] = None
    if types:
        type_list = [t.strip().lower() for t in types.split(",") if t.strip()]
    try:
        replay_requests_total.labels(days=str(days)).inc()
    except Exception:
        pass

    async def stream():
        # Fetch both streams
        rows_a = []
        rows_b = []
        try:
            rows_a = await r.xrange("signals", min=start_id, max="+")
        except Exception:
            rows_a = []
        try:
            rows_b = await r.xrange("cross_signals", min="-", max="+")
        except Exception:
            rows_b = []
        merged: List[Dict[str, Any]] = []
        for _, fields in rows_a:
            raw = fields.get("json")
            if not raw:
                continue
            try:
                s = json.loads(raw)
                if type_list and (s.get("type") or "").lower() not in type_list:
                    continue
                merged.append(s)
            except Exception:
                continue
        for _, fields in rows_b:
            raw = fields.get("json")
            if not raw:
                continue
            try:
                s = json.loads(raw)
                if type_list and (s.get("type") or "").lower() not in type_list:
                    continue
                merged.append(s)
            except Exception:
                continue
        try:
            merged.sort(key=lambda s: int(s.get("timestamp", 0)), reverse=(order.lower() == "desc"))
        except Exception:
            pass
        for s in merged:
            if await request.is_disconnected():
                break
            try:
                yield (json.dumps(s, separators=(",", ":")) + "\n").encode("utf-8")
            except Exception:
                continue
    return StreamingResponse(stream(), media_type="application/x-ndjson")
