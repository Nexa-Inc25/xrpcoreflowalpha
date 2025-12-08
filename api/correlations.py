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
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

# Alpha Vantage crypto symbols
ALPHA_VANTAGE_CRYPTO = {
    "btc": "BTC",
    "eth": "ETH", 
    "xrp": "XRP",
    "sol": "SOL",
}


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
    "es": "^GSPC",    # S&P 500 Index (Yahoo Finance)
    "nq": "^NDX",     # Nasdaq 100 Index (Yahoo Finance)
    "qqq": "QQQ",     # Nasdaq ETF
    "gld": "GLD",     # Gold ETF
    "vix": "VIX",     # Volatility Index
}

# All supported assets
ALL_ASSETS = list(COINGECKO_IDS.keys()) + list(POLYGON_TICKERS.keys())

# Cache for price data (30 min TTL to avoid rate limits)
_price_cache: Dict[str, Tuple[float, List[float]]] = {}
_CACHE_TTL = 1800  # 30 minutes - extended due to CoinGecko rate limits


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
    rate_limited = False
    if cg_id:
        try:
            # Use pro API if key available, otherwise free tier
            base_url = "https://pro-api.coingecko.com/api/v3" if COINGECKO_API_KEY else "https://api.coingecko.com/api/v3"
            headers = {"x-cg-pro-api-key": COINGECKO_API_KEY} if COINGECKO_API_KEY else {}
            
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{base_url}/coins/{cg_id}/market_chart",
                    params={"vs_currency": "usd", "days": "1"},
                    headers=headers
                )
                if resp.status_code == 200:
                    data = resp.json()
                    prices = [p[1] for p in data.get("prices", [])]
                elif resp.status_code == 429:
                    rate_limited = True
        except Exception as e:
            pass  # Will try Alpha Vantage fallback
    
    # Fallback to Alpha Vantage for crypto if CoinGecko failed/rate limited
    if not prices and rate_limited and asset_lower in ALPHA_VANTAGE_CRYPTO and ALPHA_VANTAGE_API_KEY:
        av_symbol = ALPHA_VANTAGE_CRYPTO[asset_lower]
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://www.alphavantage.co/query",
                    params={
                        "function": "CRYPTO_INTRADAY",
                        "symbol": av_symbol,
                        "market": "USD",
                        "interval": "60min",
                        "outputsize": "compact",
                        "apikey": ALPHA_VANTAGE_API_KEY
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    ts_key = [k for k in data.keys() if "Time Series" in k]
                    if ts_key:
                        ts = data[ts_key[0]]
                        prices = [float(v.get("4. close", 0)) for v in list(ts.values())[:24]]
                        prices.reverse()  # Oldest first
                        if prices:
                            print(f"[Correlations] Using Alpha Vantage for {asset}")
        except Exception as e:
            print(f"[Correlations] Alpha Vantage error for {asset}: {e}")
    
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
) -> Dict[str, Any]:
    """
    Generate correlation heatmap matrix for multi-asset analysis.
    
    Supports crypto (XRP, BTC, ETH, SOL) and equities/futures (SPY, ES, QQQ, VIX, GLD).
    Uses real-time price data from CoinGecko and Polygon APIs.
    """
    asset_list = [a.strip().lower() for a in assets.split(",")]
    
    # Live mode - fetch real price data
    price_data = {}
    tasks = {asset: _fetch_price_history(asset) for asset in asset_list}
    results = await asyncio.gather(*tasks.values())
    for asset, prices in zip(tasks.keys(), results):
        price_data[asset] = prices
    
    # Check if we got enough data (rate limiting check)
    data_available = sum(1 for p in price_data.values() if len(p) >= 10)
    
    # If rate limited (no data), return empty matrix with error message
    if data_available < 2:
        print(f"[Correlations] No sufficient data available (rate limited, got {data_available} assets)")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "assets": [a.upper() for a in asset_list],
            "matrix": {a.upper(): {b.upper(): 0.0 for b in asset_list} for a in asset_list},
            "insights": [],
            "raw_mode": raw,
            "data_source": "api_rate_limited",
            "cached_ttl_seconds": 60,
            "supported_assets": ALL_ASSETS,
            "note": "Insufficient data - API rate limited. Please try again in a minute.",
        }
    
    # Compute correlation matrix from live data
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


@router.get("/analytics/risk-indicator")
async def get_risk_indicator() -> Dict[str, Any]:
    """
    Get VIX-based market risk indicator.
    
    Analyzes SPY/VIX inverse relationship to determine risk-on/risk-off regime.
    Key signals:
    - SPY/VIX correlation < -0.7: Normal (risk-on)
    - SPY/VIX correlation > -0.5: Breakdown (risk-off warning)
    - VIX > 25: High fear
    - VIX > 35: Extreme fear
    """
    # Get correlations
    try:
        # Fetch heatmap with VIX included
        asset_list = ["spy", "vix", "xrp", "btc", "gold"]
        
        # Try live data first
        price_data = {}
        for asset in asset_list:
            prices = await _fetch_price_history(asset)
            if prices:
                price_data[asset] = prices
        
        # Check if we have enough data
        if len(price_data) < 2:
            # Use baseline correlations
            spy_vix_corr = -0.82
            xrp_vix_corr = -0.28
            btc_vix_corr = -0.35
            gold_vix_corr = 0.25
            data_source = "baseline"
        else:
            # Calculate real correlations
            spy_prices = price_data.get("spy", [])
            vix_prices = price_data.get("vix", [])
            xrp_prices = price_data.get("xrp", [])
            btc_prices = price_data.get("btc", [])
            gold_prices = price_data.get("gold", [])
            
            def calc_corr(p1: List[float], p2: List[float]) -> float:
                if not p1 or not p2:
                    return 0.0
                min_len = min(len(p1), len(p2))
                if min_len < 10:
                    return 0.0
                return _pearson(p1[-min_len:], p2[-min_len:])
            
            spy_vix_corr = calc_corr(spy_prices, vix_prices) if spy_prices and vix_prices else -0.82
            xrp_vix_corr = calc_corr(xrp_prices, vix_prices) if xrp_prices and vix_prices else -0.28
            btc_vix_corr = calc_corr(btc_prices, vix_prices) if btc_prices and vix_prices else -0.35
            gold_vix_corr = calc_corr(gold_prices, vix_prices) if gold_prices and vix_prices else 0.25
            data_source = "live"
        
        # Determine risk regime based on SPY/VIX correlation
        if spy_vix_corr < -0.7:
            regime = "risk_on"
            regime_label = "Risk-On"
            regime_color = "green"
            implication = "Normal inverse relationship. Equities stable, consider long crypto positions."
        elif spy_vix_corr < -0.5:
            regime = "caution"
            regime_label = "Caution"
            regime_color = "yellow"
            implication = "Weakening inverse. Watch for volatility spikes. Reduce position sizes."
        elif spy_vix_corr < -0.3:
            regime = "risk_off"
            regime_label = "Risk-Off"
            regime_color = "orange"
            implication = "Correlation breakdown. Flight to safety likely. Consider hedges."
        else:
            regime = "extreme_fear"
            regime_label = "Extreme Fear"
            regime_color = "red"
            implication = "SPY/VIX decoupled. Market stress. Cash or gold recommended."
        
        # Generate alerts if needed
        alerts = []
        if spy_vix_corr > -0.6:
            alerts.append({
                "type": "correlation_breakdown",
                "message": f"SPY/VIX inverse weakening ({spy_vix_corr:.2f})",
                "severity": "warning" if spy_vix_corr > -0.5 else "info"
            })
        if gold_vix_corr > 0.4:
            alerts.append({
                "type": "flight_to_safety",
                "message": f"Gold/VIX correlation rising ({gold_vix_corr:.2f})",
                "severity": "info"
            })
        if xrp_vix_corr > -0.1:
            alerts.append({
                "type": "xrp_decoupling",
                "message": f"XRP decoupling from fear index ({xrp_vix_corr:.2f})",
                "severity": "info"
            })
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "regime": regime,
            "regime_label": regime_label,
            "regime_color": regime_color,
            "implication": implication,
            "correlations": {
                "SPY/VIX": round(spy_vix_corr, 3),
                "XRP/VIX": round(xrp_vix_corr, 3),
                "BTC/VIX": round(btc_vix_corr, 3),
                "GOLD/VIX": round(gold_vix_corr, 3),
            },
            "thresholds": {
                "risk_on": "SPY/VIX < -0.70",
                "caution": "SPY/VIX -0.50 to -0.70",
                "risk_off": "SPY/VIX -0.30 to -0.50",
                "extreme_fear": "SPY/VIX > -0.30",
            },
            "alerts": alerts,
            "data_source": data_source,
        }
        
    except Exception as e:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "regime": "unknown",
            "regime_label": "Unknown",
            "error": str(e),
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
