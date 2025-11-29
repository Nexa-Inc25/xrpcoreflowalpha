from typing import Dict

from fastapi import APIRouter, HTTPException, Query
import aiohttp
import datetime as _dt

from app.config import POLYGON_API_KEY
from ml.eth_close_forecast import predict_eth_close_payload

router = APIRouter()


@router.get("/analytics/eth_close_forecast")
async def eth_close_forecast(
    open: float = Query(0.0, alias="open"),
    high: float = Query(0.0, alias="high"),
    low: float = Query(0.0, alias="low"),
    volume: float = Query(0.0, alias="volume"),
) -> Dict[str, float]:
    """Return a simple ETH next-close forecast based on OHLCV features.

    The model is a fixed linear regression trained offline on Polygon data.
    """
    return predict_eth_close_payload({
        "open": open,
        "high": high,
        "low": low,
        "volume": volume,
    })


@router.get("/analytics/eth_ohlcv_latest")
async def eth_ohlcv_latest() -> Dict[str, float]:
    """Fetch latest daily ETH/USD OHLCV from Polygon.

    Uses Polygon's aggregates endpoint and POLYGON_API_KEY; best-effort with
    simple fallback from today to yesterday if needed.
    """
    if not POLYGON_API_KEY:
        raise HTTPException(status_code=503, detail="POLYGON_API_KEY not configured")

    base = "https://api.polygon.io/v2/aggs/ticker/X:ETHUSD/range/1/day"

    async def _fetch_range(session: aiohttp.ClientSession, start: str, end: str) -> Dict[str, float]:
        url = f"{base}/{start}/{end}?adjusted=true&sort=desc&limit=1&apiKey={POLYGON_API_KEY}"
        async with session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise HTTPException(status_code=resp.status, detail=f"polygon_error: {text}")
            data = await resp.json()
            results = data.get("results") or []
            if not results:
                raise HTTPException(status_code=502, detail="No results from Polygon")
            agg = results[-1]
            return {
                "open": float(agg.get("o") or agg.get("open") or 0.0),
                "high": float(agg.get("h") or agg.get("high") or 0.0),
                "low": float(agg.get("l") or agg.get("low") or 0.0),
                "volume": float(agg.get("v") or agg.get("volume") or 0.0),
            }

    today = _dt.date.today()
    start = today.isoformat()
    yesterday = (today - _dt.timedelta(days=1)).isoformat()

    timeout = aiohttp.ClientTimeout(total=8)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            return await _fetch_range(session, start, start)
        except HTTPException:
            # Fallback to yesterday's bar if today's not yet available
            return await _fetch_range(session, yesterday, yesterday)
