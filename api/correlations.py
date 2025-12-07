"""
Multi-Asset Correlation Engine - Real Price Data
Computes actual Pearson correlations from live CoinGecko price history.
"""
import math
import asyncio
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Query, Request, HTTPException
import httpx
import os

router = APIRouter()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")


async def require_pro_tier(request: Request) -> bool:
    """Check if user has Pro tier subscription. Returns True if allowed."""
    # Check middleware-resolved tier
    tier = getattr(request.state, "user_tier", None) or ""
    if tier.lower() in ("pro", "institutional"):
        return True
    
    # Check header override for dev
    header_tier = request.headers.get("X-Plan", "").lower()
    if header_tier in ("pro", "institutional"):
        return True
    
    return False

# CoinGecko ID mapping for crypto
COINGECKO_IDS = {
    "xrp": "ripple",
    "eth": "ethereum", 
    "btc": "bitcoin",
    "gold": "tether-gold",  # XAUT as gold proxy
    "sol": "solana",
}

# Polygon tickers for equities/futures
POLYGON_TICKERS = {
    "spy": "SPY",     # S&P 500 ETF
    "es": "ES=F",     # S&P 500 Futures (proxy)
    "nq": "NQ=F",     # Nasdaq Futures (proxy)
    "qqq": "QQQ",     # Nasdaq ETF
    "gld": "GLD",     # Gold ETF
    "vix": "VIX",     # Volatility Index
}

# All supported assets
ALL_ASSETS = list(COINGECKO_IDS.keys()) + list(POLYGON_TICKERS.keys())

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
    """Fetch 24h price history from CoinGecko or Polygon. Returns list of prices."""
    asset_lower = asset.lower()
    
    # Check cache
    now = time.time()
    if asset_lower in _price_cache:
        cached_time, cached_data = _price_cache[asset_lower]
        if now - cached_time < _CACHE_TTL:
            return cached_data
    
    prices = []
    
    # Try CoinGecko for crypto
    cg_id = COINGECKO_IDS.get(asset_lower)
    if cg_id:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart",
                    params={"vs_currency": "usd", "days": "1"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    prices = [p[1] for p in data.get("prices", [])]
        except Exception as e:
            print(f"[Correlations] CoinGecko error for {asset}: {e}")
    
    # Try Polygon for equities/futures
    if not prices and asset_lower in POLYGON_TICKERS and POLYGON_API_KEY:
        ticker = POLYGON_TICKERS[asset_lower]
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/hour/2024-01-01/2025-12-31",
                    params={"apiKey": POLYGON_API_KEY, "limit": 24, "sort": "desc"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    prices = [r.get("c", 0) for r in reversed(results)]  # Close prices
        except Exception as e:
            print(f"[Correlations] Polygon error for {asset}: {e}")
    
    # Cache if we got data
    if prices:
        _price_cache[asset_lower] = (now, prices)
    
    return prices


def _generate_mock_correlation() -> float:
    """Generate realistic mock correlation value."""
    # Biased towards moderate correlations
    base = random.gauss(0.3, 0.4)
    return max(-1.0, min(1.0, base))


def _generate_mock_matrix(assets: List[str]) -> Dict[str, Dict[str, float]]:
    """Generate mock correlation matrix with realistic values."""
    # Predefined realistic correlations for known pairs
    known_correlations = {
        ("xrp", "btc"): 0.72,
        ("xrp", "eth"): 0.68,
        ("btc", "eth"): 0.85,
        ("xrp", "spy"): 0.35,
        ("xrp", "es"): 0.38,
        ("xrp", "gold"): 0.15,
        ("btc", "spy"): 0.42,
        ("btc", "gold"): 0.22,
        ("eth", "spy"): 0.48,
        ("spy", "es"): 0.98,
        ("spy", "qqq"): 0.92,
        ("spy", "gold"): -0.15,
        ("spy", "vix"): -0.82,
        ("gold", "vix"): 0.25,
    }
    
    matrix = {}
    for a1 in assets:
        matrix[a1] = {}
        for a2 in assets:
            if a1 == a2:
                matrix[a1][a2] = 1.0
            else:
                # Check known correlations
                key = tuple(sorted([a1.lower(), a2.lower()]))
                if key in known_correlations:
                    corr = known_correlations[key]
                    # Add small noise
                    corr += random.uniform(-0.05, 0.05)
                else:
                    corr = _generate_mock_correlation()
                matrix[a1][a2] = round(corr, 3)
    
    return matrix


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
    assets: str = Query("xrp,eth,btc,spy,gold", description="Comma-separated assets"),
    raw: bool = Query(False, description="Raw data mode"),
    mock: bool = Query(False, description="Return mock data for testing"),
) -> Dict[str, Any]:
    """
    Generate correlation heatmap matrix for multi-asset analysis.
    
    Supports crypto (XRP, BTC, ETH, SOL) and equities/futures (SPY, ES, QQQ, VIX, GLD).
    Use ?mock=true for testing/demo data with realistic correlation values.
    """
    asset_list = [a.strip().lower() for a in assets.split(",")]
    
    # Mock mode - return predefined realistic correlations
    if mock:
        matrix = _generate_mock_matrix(asset_list)
        
        # Generate insights
        insights = []
        for a1 in asset_list:
            for a2 in asset_list:
                if a1 < a2:  # Avoid duplicates
                    corr = matrix[a1][a2]
                    if abs(corr) > 0.7:
                        insights.append({
                            "pair": f"{a1.upper()}/{a2.upper()}",
                            "correlation": corr,
                            "strength": "strong",
                            "signal": "Moves together" if corr > 0 else "Inverse relationship",
                        })
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "assets": [a.upper() for a in asset_list],
            "matrix": {k.upper(): {k2.upper(): v2 for k2, v2 in v.items()} for k, v in matrix.items()},
            "insights": insights[:5],
            "raw_mode": raw,
            "data_source": "mock",
            "cached_ttl_seconds": 0,
            "supported_assets": ALL_ASSETS,
        }
    
    # Live mode - fetch real price data
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
    
    # Generate insights from strong correlations
    insights = []
    for a1 in asset_list:
        for a2 in asset_list:
            if a1 < a2:
                corr = matrix[a1][a2]
                if abs(corr) > 0.6:
                    insights.append({
                        "pair": f"{a1.upper()}/{a2.upper()}",
                        "correlation": corr,
                        "strength": "strong" if abs(corr) > 0.7 else "moderate",
                        "signal": "Positive correlation" if corr > 0 else "Negative correlation",
                    })
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "assets": [a.upper() for a in asset_list],
        "matrix": {k.upper(): {k2.upper(): v2 for k2, v2 in v.items()} for k, v in matrix.items()},
        "insights": sorted(insights, key=lambda x: abs(x["correlation"]), reverse=True)[:5],
        "raw_mode": raw,
        "data_source": "coingecko_polygon",
        "cached_ttl_seconds": _CACHE_TTL,
        "supported_assets": ALL_ASSETS,
    }


@router.get("/analytics/raw-alpha")
async def get_raw_alpha(
    request: Request,
    asset: str = Query("xrp", description="Target asset"),
    limit: int = Query(20, description="Number of signals")
) -> Dict[str, Any]:
    """
    Extract raw alpha signals - unfiltered flow data before ML scoring.
    Pro-tier feature for deriving custom trading edges.
    """
    # Check Pro tier access
    is_pro = await require_pro_tier(request)
    if not is_pro:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Pro subscription required",
                "message": "Raw alpha signals are available to Pro tier subscribers only.",
                "upgrade_url": "https://zkalphaflow.com/settings"
            }
        )
    
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
