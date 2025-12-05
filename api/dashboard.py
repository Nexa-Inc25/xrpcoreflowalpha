from datetime import datetime, timezone
from typing import Any, Dict, List

import asyncio
import httpx
from fastapi import APIRouter

from app.config import ALPHA_VANTAGE_API_KEY
from observability.metrics import (
    zk_dominant_frequency_hz,
    zk_wavelet_urgency_score,
    zk_flow_confidence_score,
)
from utils.price import get_price_usd

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_gauge_value(metric, **labels: Any) -> float:
    try:
        return float(metric.labels(**labels)._value.get())  # type: ignore[attr-defined]
    except Exception:
        return 0.0


def _risk_tier(prob: float) -> str:
    if prob >= 0.85:
        return "critical"
    if prob >= 0.6:
        return "high"
    if prob >= 0.3:
        return "elevated"
    return "normal"


def _macro_regime(urg: float) -> str:
    if urg >= 90:
        return "panic"
    if urg >= 70:
        return "trending"
    if urg >= 40:
        return "active"
    if urg > 0:
        return "calm"
    return "idle"


async def _get_alpha_last_close(symbol: str) -> float:
    """Fetch last close for an equity (e.g., SPY, QQQ) via Alpha Vantage.

    Best-effort helper for dashboard tiles; falls back to 0.0 on any error or
    if ALPHA_VANTAGE_API_KEY is not configured.
    """

    if not ALPHA_VANTAGE_API_KEY:
        return 0.0

    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": "1min",
        "outputsize": "compact",
        "apikey": ALPHA_VANTAGE_API_KEY,
    }
    url = "https://www.alphavantage.co/query"

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return 0.0
            data = resp.json()
    except Exception:
        return 0.0

    try:
        series_key = next((k for k in data.keys() if "Time Series" in k), None)
        if not series_key:
            return 0.0
        series = data.get(series_key) or {}
        if not series:
            return 0.0
        # Take the latest timestamp entry
        latest_ts = sorted(series.keys())[-1]
        bar = series.get(latest_ts) or {}
        close_str = bar.get("4. close") or bar.get("4. Close") or "0"
        return float(close_str)
    except Exception:
        return 0.0


@router.get("/dashboard/flow_state")
async def flow_state() -> Dict[str, Any]:
    godark_conf = _get_gauge_value(zk_flow_confidence_score, protocol="godark")
    macro_conf = _get_gauge_value(zk_flow_confidence_score, protocol="macro")
    es_urg = _get_gauge_value(zk_wavelet_urgency_score, source="macro_es")
    nq_urg = _get_gauge_value(zk_wavelet_urgency_score, source="macro_nq")
    es_freq = _get_gauge_value(zk_dominant_frequency_hz, source="macro_es")
    nq_freq = _get_gauge_value(zk_dominant_frequency_hz, source="macro_nq")

    avg_urg = max(es_urg, nq_urg)
    macro_regime = _macro_regime(avg_urg)

    return {
        "updated_at": _now_iso(),
        "godark": {
            "confidence": godark_conf,
            "risk_level": _risk_tier(godark_conf),
            "label": "GoDark Imminent Risk",
            "summary": "Probability of imminent dark pool or ZK-style execution based on on-chain flow.",
        },
        "macro": {
            "urgency": avg_urg,
            "confidence": macro_conf,
            "risk_level": _risk_tier(macro_conf),
            "regime": macro_regime,
            "label": f"Macro Regime: {macro_regime.title()}",
            "summary": "Wavelet-based urgency of ES/NQ futures notional flow.",
            "sources": {
                "macro_es": {"freq_hz": es_freq, "urgency": es_urg},
                "macro_nq": {"freq_hz": nq_freq, "urgency": nq_urg},
            },
        },
    }


@router.get("/dashboard/market_prices")
async def market_prices() -> Dict[str, Any]:
    """Return a simple snapshot of real market prices for key assets.

    Currently supports XRP and ETH via Coingecko, using the shared pricing utility.
    Additional assets can be added later without breaking the response shape.
    """

    assets: List[Dict[str, Any]] = [
        {"id": "xrp", "symbol": "XRP", "name": "XRP", "asset_class": "crypto"},
        {"id": "eth", "symbol": "ETH", "name": "Ethereum", "asset_class": "crypto"},
    ]

    markets: List[Dict[str, Any]] = []

    # Crypto legs via Coingecko
    for asset in assets:
        symbol = str(asset["symbol"]).lower()
        price = await get_price_usd(symbol)
        markets.append(
            {
                "id": asset["id"],
                "symbol": asset["symbol"],
                "name": asset["name"],
                "price": float(price) if price and price > 0 else 0.0,
                "change_24h": 0.0,
                "volume": "N/A",
                "market_cap": "N/A",
                "asset_class": asset["asset_class"],
                "price_history": [],
            }
        )

    # S&P 500 and Nasdaq 100 exposure via highly liquid ETFs (SPY, QQQ)
    spy_price = await _get_alpha_last_close("SPY")
    qqq_price = await _get_alpha_last_close("QQQ")

    markets.append(
        {
            "id": "spy",
            "symbol": "SPY",
            "name": "S&P 500 (SPY ETF)",
            "price": float(spy_price) if spy_price and spy_price > 0 else 0.0,
            "change_24h": 0.0,
            "volume": "N/A",
            "market_cap": "N/A",
            "asset_class": "etf",
            "price_history": [],
        }
    )
    markets.append(
        {
            "id": "qqq",
            "symbol": "QQQ",
            "name": "Nasdaq 100 (QQQ ETF)",
            "price": float(qqq_price) if qqq_price and qqq_price > 0 else 0.0,
            "change_24h": 0.0,
            "volume": "N/A",
            "market_cap": "N/A",
            "asset_class": "etf",
            "price_history": [],
        }
    )

    return {
        "updated_at": _now_iso(),
        "markets": markets,
    }


@router.get("/dashboard/whale_transfers")
async def whale_transfers(chain: str = None, min_value: int = 1000000, limit: int = 50) -> Dict[str, Any]:
    """Return recent whale transfers for the wallets tracking page.
    
    Uses Whale Alert API to fetch large transactions across chains.
    """
    try:
        from scanners.whale_alert_scanner import get_recent_whale_transfers
        transfers = await get_recent_whale_transfers(chain=chain, min_value=min_value, limit=limit)
    except Exception as e:
        print(f"[Dashboard] Error fetching whale transfers: {e}")
        transfers = []
    
    return {
        "updated_at": _now_iso(),
        "transfers": transfers,
        "count": len(transfers),
    }
