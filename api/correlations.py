"""
Multi-Asset Correlation Engine - Real Price Data
Computes actual Pearson correlations from live CoinGecko price history.
"""
import math
import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Query
import httpx

router = APIRouter()

# CoinGecko ID mapping
COINGECKO_IDS = {
    "xrp": "ripple",
    "eth": "ethereum", 
    "btc": "bitcoin",
    "gold": "tether-gold",  # XAUT as gold proxy
    "spy": "spdr-s-p-500-etf-trust",  # May not exist, fallback
}

# Cache for price data (5 min TTL)
_price_cache: Dict[str, Tuple[float, List[float]]] = {}
_CACHE_TTL = 300  # 5 minutes


def _pearson(x: List[float], y: List[float]) -> float:
    """Pearson correlation coefficient."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    n = len(x)
    mx, my = sum(x)/n, sum(y)/n
    num = sum((xi-mx)*(yi-my) for xi, yi in zip(x, y))
    den = math.sqrt(sum((xi-mx)**2 for xi in x) * sum((yi-my)**2 for yi in y))
    return num/den if den else 0.0


async def _fetch_price_history(asset: str) -> List[float]:
    """Fetch 24h price history from CoinGecko. Returns list of prices."""
    # Check cache
    now = time.time()
    if asset in _price_cache:
        cached_time, cached_data = _price_cache[asset]
        if now - cached_time < _CACHE_TTL:
            return cached_data
    
    cg_id = COINGECKO_IDS.get(asset.lower())
    if not cg_id:
        return []
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart",
                params={"vs_currency": "usd", "days": "1"}
            )
            if resp.status_code == 200:
                data = resp.json()
                prices = [p[1] for p in data.get("prices", [])]
                if prices:
                    _price_cache[asset] = (now, prices)
                return prices
    except Exception as e:
        print(f"[Correlations] Error fetching {asset}: {e}")
    
    return []


async def _compute_correlation(asset1: str, asset2: str) -> float:
    """Compute correlation between two assets using real price data."""
    prices1, prices2 = await asyncio.gather(
        _fetch_price_history(asset1),
        _fetch_price_history(asset2)
    )
    
    if not prices1 or not prices2:
        return 0.0
    
    # Align to same length (use shorter)
    min_len = min(len(prices1), len(prices2))
    if min_len < 10:
        return 0.0
    
    # Use last N points for correlation
    p1 = prices1[-min_len:]
    p2 = prices2[-min_len:]
    
    return _pearson(p1, p2)


@router.get("/analytics/correlations")
async def get_correlations(
    base_asset: str = Query("xrp", description="Base asset for correlations"),
    raw: bool = Query(False, description="Return raw unprocessed data")
) -> Dict[str, Any]:
    """
    Get real-time correlations between assets using live price data.
    """
    others = ["eth", "btc", "gold"]
    if base_asset.lower() in others:
        others.remove(base_asset.lower())
    if base_asset.lower() != "xrp":
        others.append("xrp")
    
    correlations = []
    for other in others:
        corr_value = await _compute_correlation(base_asset.lower(), other)
        
        correlations.append({
            "pair": f"{base_asset.upper()}/{other.upper()}",
            "correlation": round(corr_value, 3),
            "strength": "strong" if abs(corr_value) > 0.7 else "moderate" if abs(corr_value) > 0.4 else "weak",
            "direction": "positive" if corr_value > 0 else "negative",
            "signal": "bullish" if corr_value > 0.5 else "bearish" if corr_value < -0.5 else "neutral",
            "raw": raw,
            "data_source": "coingecko_24h"
        })
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_asset": base_asset.upper(),
        "correlations": correlations,
        "raw_mode": raw,
        "data_points": "24h hourly prices",
        "alpha_note": "Real correlations from live price data" if raw else None,
    }


@router.get("/analytics/heatmap")
async def get_correlation_heatmap(
    assets: str = Query("xrp,eth,btc,gold", description="Comma-separated assets"),
    raw: bool = Query(False, description="Raw data mode")
) -> Dict[str, Any]:
    """
    Generate correlation heatmap matrix using real price data.
    """
    asset_list = [a.strip().lower() for a in assets.split(",")]
    
    # Fetch all price histories in parallel
    price_data = {}
    tasks = {asset: _fetch_price_history(asset) for asset in asset_list}
    results = await asyncio.gather(*tasks.values())
    for asset, prices in zip(tasks.keys(), results):
        price_data[asset] = prices
    
    # Compute correlation matrix
    matrix = {}
    for a1 in asset_list:
        matrix[a1] = {}
        for a2 in asset_list:
            if a1 == a2:
                matrix[a1][a2] = 1.0
            else:
                p1, p2 = price_data.get(a1, []), price_data.get(a2, [])
                if p1 and p2:
                    min_len = min(len(p1), len(p2))
                    corr = _pearson(p1[-min_len:], p2[-min_len:]) if min_len >= 10 else 0.0
                    matrix[a1][a2] = round(corr, 3)
                else:
                    matrix[a1][a2] = 0.0
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "assets": asset_list,
        "matrix": matrix,
        "raw_mode": raw,
        "data_source": "coingecko_24h",
        "cached_ttl_seconds": _CACHE_TTL,
    }


@router.get("/analytics/raw-alpha")
async def get_raw_alpha(
    asset: str = Query("xrp", description="Target asset"),
    limit: int = Query(20, description="Number of signals")
) -> Dict[str, Any]:
    """
    Extract raw alpha signals - unfiltered flow data before ML scoring.
    Pro-tier feature for deriving custom trading edges.
    """
    signals = []
    try:
        from bus.signal_bus import get_recent_signals
        signals = await get_recent_signals(limit=limit * 2)
    except Exception as e:
        print(f"[RawAlpha] Error fetching signals: {e}")
        signals = []
    
    # Filter for target asset and return raw
    raw_signals = []
    for sig in signals:
        net = str(sig.get("network", "")).lower()
        typ = str(sig.get("type", "")).lower()
        
        if asset.lower() in (net, typ) or (asset == "xrp" and net == "xrpl"):
            raw_signals.append({
                "id": sig.get("id"),
                "type": sig.get("type"),
                "network": sig.get("network"),
                "timestamp": sig.get("timestamp"),
                "usd_value": sig.get("features", {}).get("usd_value"),
                "tx_hash": sig.get("features", {}).get("tx_hash"),
                "raw_features": sig.get("features", {}),
                "ml_score": sig.get("rule_score"),
                "alpha_potential": "high" if sig.get("rule_score", 0) > 70 else "medium" if sig.get("rule_score", 0) > 40 else "low",
            })
        
        if len(raw_signals) >= limit:
            break
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset": asset.upper(),
        "raw_signals": raw_signals,
        "count": len(raw_signals),
        "note": "Raw alpha signals bypass ML refinement. Use for custom strategy development.",
    }
