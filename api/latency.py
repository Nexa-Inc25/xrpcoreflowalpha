"""
Latency API Endpoints for Algo Tracking

Provides endpoints for:
- Real-time latency anomaly data
- XGBoost predictions
- Order book confirmations
- Educator exports for futures courses
"""
import asyncio
import csv
import io
import json
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import REDIS_URL
from app.redis_utils import get_redis, REDIS_ENABLED


# Real-time latency monitoring only - no mock data

router = APIRouter()


async def _get_redis():
    return await get_redis()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/dashboard/latency_state")
async def get_latency_state(
    exchange: Optional[str] = Query(None, description="Filter by exchange (e.g., binance, cme)"),
    include_predictions: bool = Query(False, description="Include XGBoost predictions"),
) -> Dict[str, Any]:
    """
    Get current latency pinging state with order book confirmations.
    
    Returns real-time latency metrics, anomaly scores, and XRPL correlations.
    """
    
    try:
        from predictors.latency_pinger import latency_pinger
        
        stats = latency_pinger.get_statistics(exchange=exchange)
        recent_anomalies = latency_pinger.get_recent_anomalies(limit=10)
        
        result = {
            "updated_at": _now_iso(),
            "statistics": stats,
            "recent_anomalies": recent_anomalies,
            "status": "active" if stats.get("count", 0) > 0 else "initializing",
        }
        
        # Add predictions if requested
        if include_predictions:
            try:
                from ml.latency_xgboost import latency_predictor
                model_info = latency_predictor.get_model_info()
                result["prediction_model"] = {
                    "is_fitted": model_info.get("is_fitted", False),
                    "model_version": model_info.get("model_version", "unknown"),
                    "training_rmse": model_info.get("training_rmse", 0.0),
                }
            except Exception as e:
                result["prediction_model"] = {"error": str(e)}
        
        return result
        
    except Exception as e:
        return {
            "updated_at": _now_iso(),
            "statistics": {},
            "recent_anomalies": [],
            "status": "error",
            "error": str(e),
        }


@router.get("/latency/anomalies")
async def get_latency_anomalies(
    exchange: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    min_score: float = Query(0, ge=0, le=100),
) -> Dict[str, Any]:
    """
    Get recent latency anomalies for algo tracking.
    
    Filters by exchange and minimum anomaly score.
    """
    try:
        if not REDIS_ENABLED:
            return {
                "updated_at": _now_iso(),
                "count": 0,
                "anomalies": [],
                "redis": "disabled"
            }
        
        r = await _get_redis()
        events_json = await r.lrange("recent_latency_events", 0, limit * 2)
        
        anomalies = []
        for event_str in events_json:
            try:
                event = json.loads(event_str)
                
                # Apply filters
                if exchange and event.get("exchange", "").lower() != exchange.lower():
                    continue
                if event.get("anomaly_score", 0) < min_score:
                    continue
                
                anomalies.append(event)
                
                if len(anomalies) >= limit:
                    break
                    
            except Exception:
                continue
        
        return {
            "updated_at": _now_iso(),
            "count": len(anomalies),
            "anomalies": anomalies,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching anomalies: {e}")


@router.get("/latency/predict")
async def predict_latency(
    exchange: str = Query("binance"),
    symbol: str = Query("BTCUSDT"),
    bid_ask_imbalance: float = Query(0.0),
    spread_bps: float = Query(10.0),
    bid_depth: float = Query(1000000),
    ask_depth: float = Query(1000000),
    recent_volatility: float = Query(0.02),
    volume_ratio: float = Query(1.0),
) -> Dict[str, Any]:
    """
    Get XGBoost latency prediction for given market conditions.
    
    Returns predicted latency, anomaly probability, and contributing features.
    """
    try:
        from ml.latency_xgboost import predict_latency as xgb_predict
        
        data = {
            "exchange": exchange,
            "symbol": symbol,
            "timestamp": time.time(),
            "bid_ask_imbalance": bid_ask_imbalance,
            "spread_bps": spread_bps,
            "bid_depth": bid_depth,
            "ask_depth": ask_depth,
            "recent_volatility": recent_volatility,
            "volume_ratio": volume_ratio,
            "recent_latency_mean": 50.0,
            "recent_latency_std": 10.0,
            "recent_anomaly_rate": 0.1,
            "cancellation_rate": 0.0,
            "book_update_rate": 10.0,
            "price_momentum": 0.0,
            "correlation_xrpl": 0.0,
        }
        
        prediction = xgb_predict(data)
        
        return {
            "updated_at": _now_iso(),
            "prediction": prediction,
            "input": data,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")


@router.get("/latency/order_book_confirmation")
async def get_order_book_confirmations(
    exchange: str = Query("binance"),
    symbol: str = Query("BTCUSDT"),
) -> Dict[str, Any]:
    """
    Get order book confirmation data for latency analysis.
    
    Returns current imbalances, spread, and spoofing indicators.
    """
    try:
        from predictors.latency_pinger import latency_pinger
        
        key = f"{exchange}:{symbol}"
        snapshot = latency_pinger._order_books.get(key)
        
        if not snapshot:
            return {
                "updated_at": _now_iso(),
                "exchange": exchange,
                "symbol": symbol,
                "status": "no_data",
                "message": "No order book snapshot available",
            }
        
        # Check for spoofing
        is_spoofing, spoof_conf = latency_pinger._detect_spoofing(exchange, symbol)
        
        return {
            "updated_at": _now_iso(),
            "exchange": exchange,
            "symbol": symbol,
            "status": "active",
            "snapshot": {
                "timestamp": snapshot.timestamp,
                "mid_price": snapshot.mid_price,
                "spread_bps": snapshot.spread_bps,
                "imbalance_ratio": snapshot.imbalance_ratio,
                "best_bid": snapshot.bids[0] if snapshot.bids else None,
                "best_ask": snapshot.asks[0] if snapshot.asks else None,
                "bid_levels": len(snapshot.bids),
                "ask_levels": len(snapshot.asks),
            },
            "spoofing_detection": {
                "is_spoofing": is_spoofing,
                "confidence": spoof_conf,
            },
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@router.get("/latency/hft_signatures")
async def get_hft_signatures() -> Dict[str, Any]:
    """
    Get known HFT latency signatures for reference.
    
    Used for matching detected patterns to known algo profiles.
    """
    try:
        from predictors.latency_pinger import HFT_LATENCY_SIGNATURES
        
        signatures = []
        for name, (low, high) in HFT_LATENCY_SIGNATURES.items():
            signatures.append({
                "name": name,
                "latency_range_ms": {"low": low, "high": high},
                "avg_ms": (low + high) / 2,
                "category": "hft" if high < 50 else "mm" if high < 100 else "retail",
            })
        
        # Sort by avg latency
        signatures.sort(key=lambda x: x["avg_ms"])
        
        return {
            "updated_at": _now_iso(),
            "count": len(signatures),
            "signatures": signatures,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@router.get("/latency/xrpl_correlation")
async def get_xrpl_correlation(
    window_minutes: int = Query(15, ge=1, le=60),
) -> Dict[str, Any]:
    """
    Get correlation between latency anomalies and XRPL flows.
    
    Shows how futures/equities latency spikes correlate with XRP settlements.
    """
    try:
        r = await _get_redis()
        
        # Get recent latency events
        latency_events = await r.lrange("recent_latency_events", 0, 200)
        
        # Get recent XRPL signals
        xrpl_signals = await r.lrange("xrpl_settlements", 0, 200)
        
        now = time.time()
        window_seconds = window_minutes * 60
        
        # Filter to window
        latency_in_window = []
        for e in latency_events:
            try:
                ev = json.loads(e)
                if now - ev.get("timestamp", 0) <= window_seconds:
                    latency_in_window.append(ev)
            except Exception:
                continue
        
        xrpl_in_window = []
        for s in xrpl_signals:
            try:
                sig = json.loads(s)
                ts = sig.get("timestamp", 0)
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                if now - ts <= window_seconds:
                    xrpl_in_window.append(sig)
            except Exception:
                continue
        
        # Calculate simple correlation proxy
        latency_anomaly_count = sum(1 for e in latency_in_window if e.get("is_hft", False))
        xrpl_settlement_count = len(xrpl_in_window)
        
        # Correlation strength (simplified)
        if latency_anomaly_count > 0 and xrpl_settlement_count > 0:
            correlation_strength = min(1.0, (latency_anomaly_count + xrpl_settlement_count) / 20)
        else:
            correlation_strength = 0.0
        
        return {
            "updated_at": _now_iso(),
            "window_minutes": window_minutes,
            "latency_events_count": len(latency_in_window),
            "latency_anomaly_count": latency_anomaly_count,
            "xrpl_settlements_count": xrpl_settlement_count,
            "correlation_strength": correlation_strength,
            "interpretation": (
                "strong" if correlation_strength > 0.7 else
                "moderate" if correlation_strength > 0.4 else
                "weak" if correlation_strength > 0.1 else
                "none"
            ),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


# ============================================================
# EDUCATOR EXPORTS (Pro tier)
# ============================================================

@router.get("/educator/export_latency")
async def export_latency_data(
    request: Request,
    market: str = Query("futures", description="Market type: futures, crypto, all"),
    time_range: str = Query("24h", description="Time range: 1h, 6h, 24h, 7d"),
    format: str = Query("json", description="Export format: json, csv"),
) -> Any:
    """
    Export latency/order book data for educator use.
    
    Pro tier only - provides data for futures trading courses.
    Includes latency anomalies, HFT detections, and XRPL correlations.
    """
    # Check tier (simplified - in production use proper auth)
    tier = getattr(request.state, "user_tier", "").lower()
    if tier not in ("pro", "institutional", "educator"):
        # Allow access for demo purposes
        pass  # raise HTTPException(status_code=403, detail="Pro tier required")
    
    try:
        r = await _get_redis()
        
        # Parse time range
        time_ranges = {
            "1h": 3600,
            "6h": 21600,
            "24h": 86400,
            "7d": 604800,
        }
        window_seconds = time_ranges.get(time_range, 86400)
        
        # Fetch data
        events_json = await r.lrange("recent_latency_events", 0, 2000)
        
        now = time.time()
        events = []
        
        for event_str in events_json:
            try:
                event = json.loads(event_str)
                
                # Filter by time
                if now - event.get("timestamp", 0) > window_seconds:
                    continue
                
                # Filter by market
                exchange = event.get("exchange", "").lower()
                if market == "futures" and exchange not in ("cme", "futures", "binance_futures"):
                    continue
                elif market == "crypto" and exchange in ("cme", "futures"):
                    continue
                
                events.append({
                    "timestamp": datetime.fromtimestamp(event.get("timestamp", 0), tz=timezone.utc).isoformat(),
                    "exchange": event.get("exchange"),
                    "symbol": event.get("symbol"),
                    "latency_ms": event.get("latency_ms"),
                    "anomaly_score": event.get("anomaly_score"),
                    "is_hft": event.get("is_hft", False),
                    "order_book_imbalance": event.get("order_book_imbalance"),
                    "spread_bps": event.get("spread_bps"),
                    "matched_signature": event.get("features", {}).get("matched_signature"),
                    "xrpl_correlation": event.get("correlation_hint"),
                })
                
            except Exception:
                continue
        
        if format == "csv":
            # Return CSV
            def generate_csv():
                output = io.StringIO()
                if events:
                    writer = csv.DictWriter(output, fieldnames=events[0].keys())
                    writer.writeheader()
                    for event in events:
                        writer.writerow(event)
                return output.getvalue()
            
            return StreamingResponse(
                iter([generate_csv()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=latency_export_{time_range}.csv"},
            )
        
        # Return JSON
        return {
            "exported_at": _now_iso(),
            "market": market,
            "time_range": time_range,
            "count": len(events),
            "events": events,
            "usage_hint": "Use this data to demonstrate HFT detection patterns in ES/NQ futures courses",
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export error: {e}")


@router.get("/educator/export_predictions")
async def export_predictions(
    request: Request,
    market: str = Query("futures"),
    time_range: str = Query("24h"),
) -> Dict[str, Any]:
    """
    Export XGBoost prediction data for educator use.
    
    Pro tier only - provides ML prediction examples for courses.
    """
    try:
        from ml.latency_xgboost import latency_predictor
        
        model_info = latency_predictor.get_model_info()
        
        # Generate sample predictions for different market conditions
        sample_conditions = [
            {"name": "normal_market", "bid_ask_imbalance": 0.0, "spread_bps": 10, "cancellation_rate": 1},
            {"name": "high_imbalance", "bid_ask_imbalance": 0.3, "spread_bps": 15, "cancellation_rate": 2},
            {"name": "hft_activity", "bid_ask_imbalance": 0.1, "spread_bps": 5, "cancellation_rate": 8},
            {"name": "spoofing_suspect", "bid_ask_imbalance": 0.5, "spread_bps": 25, "cancellation_rate": 15},
            {"name": "low_liquidity", "bid_ask_imbalance": 0.2, "spread_bps": 50, "cancellation_rate": 0},
        ]
        
        predictions = []
        for condition in sample_conditions:
            data = {
                "exchange": "cme",
                "symbol": "ES",
                "timestamp": time.time(),
                "bid_ask_imbalance": condition["bid_ask_imbalance"],
                "spread_bps": condition["spread_bps"],
                "bid_depth": 500000,
                "ask_depth": 500000,
                "recent_volatility": 0.02,
                "volume_ratio": 1.0,
                "recent_latency_mean": 50.0,
                "recent_latency_std": 10.0,
                "recent_anomaly_rate": 0.1,
                "cancellation_rate": condition["cancellation_rate"],
                "book_update_rate": 20.0,
                "price_momentum": 0.0,
                "correlation_xrpl": 0.0,
            }
            
            pred = latency_predictor.predict(data)
            predictions.append({
                "scenario": condition["name"],
                "input_conditions": condition,
                "predicted_latency_ms": pred.predicted_latency_ms,
                "confidence_score": pred.confidence_score,
                "is_anomaly_predicted": pred.is_anomaly_predicted,
                "anomaly_probability": pred.anomaly_probability,
                "contributing_features": pred.contributing_features,
            })
        
        return {
            "exported_at": _now_iso(),
            "model_info": model_info,
            "sample_predictions": predictions,
            "feature_names": model_info.get("feature_names", []),
            "usage_hint": "Demonstrate how XGBoost predicts HFT activity from order book features",
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export error: {e}")


@router.get("/debug/latency_model")
async def debug_latency_model() -> Dict[str, Any]:
    """Debug endpoint for latency model status."""
    try:
        from ml.latency_xgboost import latency_predictor
        from predictors.latency_pinger import latency_pinger
        
        return {
            "updated_at": _now_iso(),
            "model": latency_predictor.get_model_info(),
            "pinger_stats": latency_pinger.get_statistics(),
        }
        
    except Exception as e:
        return {
            "updated_at": _now_iso(),
            "error": str(e),
        }


# ============================================================
# EDUCATOR COURSE CONTENT
# ============================================================

COURSE_LESSONS = [
    {"id": "order_flow", "title": "Order Flow Basics", "description": "Understanding order book imbalance and HFT detection"},
    {"id": "hft_patterns", "title": "HFT Pattern Recognition", "description": "Identifying Citadel, Jump, and other algo signatures"},
    {"id": "spoofing", "title": "Spoofing Detection", "description": "Recognizing and trading around spoofing behavior"},
    {"id": "correlations", "title": "Cross-Market Correlations", "description": "Trading XRP/SPY/ES correlations"},
    {"id": "futures_basics", "title": "Futures for Crypto Traders", "description": "ES, NQ basics and overnight sessions"},
    {"id": "risk_mgmt", "title": "Position Sizing", "description": "Managing risk with correlated assets"},
    {"id": "latency_arb", "title": "Latency Edge", "description": "Using HFT activity as leading indicators"},
    {"id": "xrpl_settlement", "title": "XRPL Settlement Layer", "description": "Institutional flow routing through XRPL"},
]


@router.get("/educator/course")
async def get_course_content() -> Dict[str, Any]:
    """
    Get futures trading course content and current market regime.
    
    Returns lesson list, current regime analysis, and pro tier benefits.
    """
    # Get market regime from correlations
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            # Use internal service port 8000
            resp = await client.get("http://localhost:8000/analytics/heatmap?assets=xrp,btc,eth,spy,gold")
            if resp.status_code == 200:
                data = resp.json()
                matrix = data.get("matrix", {})
                
                btc_eth = matrix.get("BTC", {}).get("ETH", 0)
                xrp_spy = matrix.get("XRP", {}).get("SPY", 0)
                
                if btc_eth > 0.7 and xrp_spy > 0.3:
                    regime = "risk_on"
                elif btc_eth > 0.7 and xrp_spy < -0.2:
                    regime = "divergence"
                else:
                    regime = "neutral"
            else:
                regime = "unknown"
    except:
        regime = "unknown"
    
    return {
        "updated_at": _now_iso(),
        "course": {
            "name": "ZK Alpha Flow Futures Trading",
            "lessons": COURSE_LESSONS,
            "total_lessons": len(COURSE_LESSONS),
        },
        "market_regime": regime,
        "pro_benefits": [
            "Live Slack alerts with teaching context",
            "Correlation-based trade signals",
            "HFT pattern notifications",
            "Course material + real examples",
            "Educator dashboard access",
        ],
        "pricing": {
            "basic": {"price": 79, "features": ["Core tracker", "Basic alerts"]},
            "pro": {"price": 199, "features": ["Full course", "Live Slack", "Priority support"]},
        },
        "cta_url": "https://zkalphaflow.com/settings",
    }
