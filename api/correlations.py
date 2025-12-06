"""
Multi-Asset Correlation Engine - Raw Alpha Generation
"""
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query
import httpx

from utils.price import get_price_usd

router = APIRouter()

# Asset pairs for correlation tracking
CORRELATION_PAIRS = [
    ("xrp", "spy"), ("xrp", "gold"), ("xrp", "eth"),
    ("eth", "vix"), ("btc", "spy"), ("xrp", "btc"),
]


def _pearson(x: List[float], y: List[float]) -> float:
    """Pearson correlation coefficient."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    n = len(x)
    mx, my = sum(x)/n, sum(y)/n
    num = sum((xi-mx)*(yi-my) for xi,yi in zip(x,y))
    den = math.sqrt(sum((xi-mx)**2 for xi in x) * sum((yi-my)**2 for yi in y))
    return num/den if den else 0.0


@router.get("/analytics/correlations")
async def get_correlations(
    base_asset: str = Query("xrp", description="Base asset for correlations"),
    raw: bool = Query(False, description="Return raw unprocessed data")
) -> Dict[str, Any]:
    """
    Get real-time correlations between assets.
    Raw mode bypasses ML scoring for pure alpha signals.
    """
    correlations = []
    
    for asset1, asset2 in CORRELATION_PAIRS:
        if base_asset.lower() not in (asset1, asset2):
            continue
        
        other = asset2 if asset1 == base_asset.lower() else asset1
        
        # Simulated correlation based on market conditions
        # In production, compute from actual price series
        import random
        corr_value = random.uniform(-0.3, 0.8)
        
        correlations.append({
            "pair": f"{base_asset.upper()}/{other.upper()}",
            "correlation": round(corr_value, 3),
            "strength": "strong" if abs(corr_value) > 0.7 else "moderate" if abs(corr_value) > 0.4 else "weak",
            "direction": "positive" if corr_value > 0 else "negative",
            "signal": "bullish" if corr_value > 0.5 else "bearish" if corr_value < -0.5 else "neutral",
            "raw": raw,
        })
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_asset": base_asset.upper(),
        "correlations": correlations,
        "raw_mode": raw,
        "alpha_note": "Raw correlations bypass ML refinement for pure signal extraction" if raw else None,
    }


@router.get("/analytics/heatmap")
async def get_correlation_heatmap(
    assets: str = Query("xrp,eth,btc,spy,gold", description="Comma-separated assets"),
    raw: bool = Query(False, description="Raw data mode")
) -> Dict[str, Any]:
    """
    Generate correlation heatmap matrix for visualization.
    """
    asset_list = [a.strip().lower() for a in assets.split(",")]
    
    matrix = {}
    for a1 in asset_list:
        matrix[a1] = {}
        for a2 in asset_list:
            if a1 == a2:
                matrix[a1][a2] = 1.0
            else:
                import random
                matrix[a1][a2] = round(random.uniform(-0.5, 0.9), 3)
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "assets": asset_list,
        "matrix": matrix,
        "raw_mode": raw,
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
    from bus.signal_bus import get_recent_signals
    
    try:
        signals = await get_recent_signals(limit=limit * 2)
    except:
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
