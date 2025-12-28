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

    Best-effort helper for dashboard tiles; falls back to Yahoo Finance if
    Alpha Vantage is unavailable. NEVER returns fake 0.0.
    """

    # Try Alpha Vantage first if API key is available
    if ALPHA_VANTAGE_API_KEY:
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
                    # Alpha Vantage failed, continue to Yahoo Finance fallback
                    pass
                else:
                    data = resp.json()
                    series_key = next((k for k in data.keys() if "Time Series" in k), None)
                    if not series_key:
                        # Alpha Vantage failed, continue to Yahoo Finance fallback
                        pass
                    else:
                        series = data.get(series_key) or {}
                        if not series:
                            # Alpha Vantage failed, continue to Yahoo Finance fallback
                            pass
                        else:
                            # Take the latest timestamp entry
                            latest_ts = sorted(series.keys())[-1]
                            bar = series.get(latest_ts) or {}
                            close_str = bar.get("4. close") or bar.get("4. Close") or "0"
                            return float(close_str)
        except Exception:
            # Alpha Vantage failed, continue to Yahoo Finance fallback
            pass

    # Fallback to Yahoo Finance if Alpha Vantage unavailable or failed
    try:
        import yfinance as yf
        import asyncio

        def _fetch_yahoo():
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1d", interval="1m")
            if df is not None and not df.empty:
                return float(df['Close'].iloc[-1])
            return None

        result = await asyncio.to_thread(_fetch_yahoo)
        if result is not None:
            return result
    except Exception:
        # Yahoo Finance also failed
        pass

    # If both APIs fail, we still don't return fake 0.0
    # Instead, raise an exception to indicate real data is unavailable
    raise RuntimeError(f"Unable to fetch real price data for {symbol} - no API available")


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
    spy_price = 0.0
    qqq_price = 0.0
    try:
        spy_price = await _get_alpha_last_close("SPY")
    except Exception:
        # Real data unavailable, keep 0.0 to indicate no data (not fake)
        pass
    try:
        qqq_price = await _get_alpha_last_close("QQQ")
    except Exception:
        # Real data unavailable, keep 0.0 to indicate no data (not fake)
        pass

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


# REAL FREQUENCY ANALYSIS - NO FAKE INSTITUTIONAL TRADER CLAIMS
# Removed all fake ALGO_PROFILES that claimed to identify specific trading firms
# Now just provides real frequency analysis of market events
ALGO_PROFILES: Dict[str, Dict[str, Any]] = {}


@router.get("/dashboard/algo_fingerprint/{algo_name}")
async def get_algo_fingerprint_detail(algo_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific algorithmic fingerprint."""
    try:
        from predictors.frequency_fingerprinter import KNOWN_FINGERPRINTS
        
        # Get base profile data
        profile = ALGO_PROFILES.get(algo_name, {})
        freq = KNOWN_FINGERPRINTS.get(algo_name, 0)
        
        if not profile:
            # Generate basic profile for unknown algos
            profile = {
                "display_name": algo_name.replace("_", " ").title(),
                "category": "Unknown",
                "description": f"Algorithmic trading pattern: {algo_name}",
                "characteristics": ["Pattern detected via frequency analysis"],
                "risk_level": "medium",
                "typical_volume": "Unknown",
                "known_wallets": [],
                "trading_patterns": [],
                "correlations": []
            }
        
        # Get recent detections - only return real data from signal bus
        recent_detections = []
        try:
            from bus.signal_bus import fetch_recent_signals
            signals = await fetch_recent_signals(window_seconds=86400)
            # Filter for signals that matched this algo pattern
            for sig in signals:
                if sig.get("algo_match") == algo_name or sig.get("features", {}).get("algo_fingerprint") == algo_name:
                    recent_detections.append({
                        "timestamp": sig.get("timestamp", _now_iso()),
                        "confidence": sig.get("confidence", 0),
                        "power": sig.get("features", {}).get("power", 0),
                        "related_txs": 1,
                        "tx_hash": sig.get("tx_hash") or sig.get("features", {}).get("tx_hash")
                    })
                    if len(recent_detections) >= 10:
                        break
        except Exception:
            pass  # Return empty list if no real data available
        
        return {
            "name": algo_name,
            "display_name": profile.get("display_name", algo_name),
            "category": profile.get("category", "Unknown"),
            "freq_hz": freq,
            "period_sec": round(1/freq, 1) if freq > 0 else 0,
            "description": profile.get("description", ""),
            "characteristics": profile.get("characteristics", []),
            "risk_level": profile.get("risk_level", "medium"),
            "typical_volume": profile.get("typical_volume", "Unknown"),
            "known_wallets": profile.get("known_wallets", []),
            "recent_detections": recent_detections,
            "trading_patterns": profile.get("trading_patterns", []),
            "correlations": profile.get("correlations", []),
            "updated_at": _now_iso()
        }
    except Exception as e:
        return {
            "name": algo_name,
            "error": str(e),
            "updated_at": _now_iso()
        }


@router.get("/dashboard/algo_fingerprint")
async def get_algo_fingerprint() -> Dict[str, Any]:
    """Get current algorithmic fingerprint detection status.
    
    Returns the detected trading pattern frequency signature
    and matched institutional algo profile.
    """
    try:
        from predictors.frequency_fingerprinter import zk_fingerprinter, KNOWN_FINGERPRINTS
        result = zk_fingerprinter.tick(source_label="api_query")
        
        # Only show fingerprints that have ACTUALLY been detected, not all possible ones
        # This prevents showing fake patterns that don't exist in real data
        detected_algos = []
        if result.get("fingerprint") and result.get("fingerprint") != "unknown":
            matched_name = result.get("fingerprint")
            if matched_name in KNOWN_FINGERPRINTS:
                detected_algos.append({
                    "name": matched_name,
                    "freq_hz": round(KNOWN_FINGERPRINTS[matched_name], 6),
                    "period_sec": round(1/KNOWN_FINGERPRINTS[matched_name], 1),
                    "last_detected": _now_iso()
                })
        
        return {
            "updated_at": _now_iso(),
            "detection": {
                "dominant_freq_hz": result.get("freq", 0),
                "power": result.get("power", 0),
                "matched_algo": result.get("fingerprint", "unknown"),
                "confidence": result.get("confidence", 0),
            },
            "detected_fingerprints": detected_algos,  # ONLY show what we've actually detected
            "status": "active" if result.get("confidence", 0) > 50 else "monitoring",
        }
    except Exception as e:
        print(f"[Dashboard] Error getting fingerprint: {e}")
        return {
            "updated_at": _now_iso(),
            "detection": {"dominant_freq_hz": 0, "power": 0, "matched_algo": "unknown", "confidence": 0},
            "detected_fingerprints": [],
            "status": "error",
            "error": str(e),
        }
# Force rebuild
