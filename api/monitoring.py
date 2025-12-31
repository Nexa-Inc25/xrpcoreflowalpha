"""
Pipeline Monitoring API

Provides comprehensive visibility into:
- Data ingestion health (signals, scanners)
- ML training status and metrics
- System health and connectivity
"""
import asyncio
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
import sqlite3

router = APIRouter()

DB_PATH = os.getenv("SQLITE_DB_PATH", "data/signals.db")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db_connection():
    """Get SQLite connection."""
    try:
        return sqlite3.connect(DB_PATH)
    except Exception:
        return None


# =============================================================================
# PIPELINE HEALTH ENDPOINT
# =============================================================================

@router.get("/admin/pipeline-health")
async def get_pipeline_health() -> Dict[str, Any]:
    """
    Comprehensive pipeline health check.
    
    Returns status of all data ingestion components, ML training,
    and system connectivity.
    """
    health = {
        "timestamp": _now_iso(),
        "overall_status": "healthy",
        "issues": [],
    }
    
    # 1. Signal Ingestion Stats
    signal_stats = await _get_signal_stats()
    health["signal_ingestion"] = signal_stats
    
    # 2. Scanner Status
    scanner_status = await _get_scanner_status()
    health["scanners"] = scanner_status
    
    # 3. ML Training Status
    ml_status = await _get_ml_status()
    health["ml_training"] = ml_status
    
    # 4. Outcome Tracking
    outcome_stats = await _get_outcome_stats()
    health["outcome_tracking"] = outcome_stats
    
    # 5. Database Health
    db_health = _get_db_health()
    health["database"] = db_health
    
    # 6. External Connections
    connections = await _check_connections()
    health["connections"] = connections
    
    # Determine overall status
    issues = []
    
    if signal_stats.get("signals_last_hour", 0) == 0:
        issues.append("No signals in last hour")
    
    if not scanner_status.get("xrpl", {}).get("connected", False):
        issues.append("XRPL scanner disconnected")
    
    if not ml_status.get("xgboost", {}).get("is_fitted", False):
        issues.append("XGBoost model not trained")
    
    if outcome_stats.get("total_outcomes", 0) == 0:
        issues.append("No outcome tracking data")
    
    if not db_health.get("connected", False):
        issues.append("Database connection failed")
    
    health["issues"] = issues
    health["overall_status"] = "healthy" if len(issues) == 0 else "degraded" if len(issues) < 3 else "unhealthy"
    
    return health


async def _get_signal_stats() -> Dict[str, Any]:
    """Get signal ingestion statistics."""
    conn = _get_db_connection()
    if not conn:
        return {"error": "Database unavailable", "total_signals": 0}
    
    try:
        cursor = conn.cursor()
        
        # Total signals
        cursor.execute("SELECT COUNT(*) FROM signals")
        total = cursor.fetchone()[0]
        
        # Signals by type
        cursor.execute("""
            SELECT type, COUNT(*) as cnt, AVG(confidence) as avg_conf
            FROM signals GROUP BY type ORDER BY cnt DESC
        """)
        by_type = {row[0]: {"count": row[1], "avg_confidence": round(row[2] or 0, 1)} for row in cursor.fetchall()}
        
        # Signals in last hour (using detected_at which is ISO datetime)
        cursor.execute("""
            SELECT COUNT(*) FROM signals 
            WHERE datetime(detected_at) > datetime('now', '-1 hour')
        """)
        last_hour = cursor.fetchone()[0]
        
        # Signals in last 24h
        cursor.execute("""
            SELECT COUNT(*) FROM signals 
            WHERE datetime(detected_at) > datetime('now', '-24 hours')
        """)
        last_24h = cursor.fetchone()[0]
        
        # Latest signal timestamp
        cursor.execute("SELECT MAX(detected_at) FROM signals")
        latest_str = cursor.fetchone()[0]
        latest_ago = None
        if latest_str:
            try:
                from datetime import datetime
                latest_dt = datetime.fromisoformat(latest_str.replace('Z', '+00:00'))
                latest_ago = int((datetime.now(timezone.utc) - latest_dt).total_seconds())
            except Exception:
                pass
        
        conn.close()
        
        return {
            "total_signals": total,
            "signals_last_hour": last_hour,
            "signals_last_24h": last_24h,
            "by_type": by_type,
            "latest_signal_seconds_ago": latest_ago,
            "ingestion_rate_per_hour": last_hour,
        }
        
    except Exception as e:
        conn.close()
        return {"error": str(e), "total_signals": 0}


async def _get_scanner_status() -> Dict[str, Any]:
    """Get scanner connection status."""
    status = {
        "xrpl": {"connected": False},
        "whale_alert": {"connected": True},
        "futures": {"connected": True},
    }
    
    try:
        from workers.scanner_monitor import scanner_status
        if hasattr(scanner_status, 'get'):
            xrpl_status = scanner_status.get("xrpl", {})
            status["xrpl"]["connected"] = xrpl_status.get("connected", False)
            if xrpl_status.get("last_signal_at"):
                status["xrpl"]["last_signal"] = xrpl_status.get("last_signal_at")
    except Exception:
        # Check if XRPL is responsive via recent signals
        conn = _get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM signals 
                    WHERE network = 'xrpl' 
                    AND datetime(detected_at) > datetime('now', '-10 minutes')
                """)
                recent_xrpl = cursor.fetchone()[0]
                status["xrpl"]["connected"] = recent_xrpl > 0
                conn.close()
            except Exception:
                pass
    
    return status


async def _get_ml_status() -> Dict[str, Any]:
    """Get ML model training status."""
    result = {
        "xgboost": {
            "is_fitted": False,
            "training_samples": 0,
            "last_training": None,
            "rmse": None,
        },
        "flow_predictor": {
            "is_fitted": False,
            "training_samples": 0,
        },
    }
    
    # Check XGBoost
    try:
        from ml.latency_xgboost import latency_predictor
        info = latency_predictor.get_model_info()
        result["xgboost"] = {
            "is_fitted": info.get("is_fitted", False),
            "training_rmse": info.get("training_rmse", 0),
            "last_tune_ts": info.get("last_tune_ts", 0),
            "feature_count": len(info.get("feature_names", [])),
            "training_history_count": len(info.get("training_history", [])),
        }
    except Exception as e:
        result["xgboost"]["error"] = str(e)
    
    # Check latency events for training data
    conn = _get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM latency_events")
            result["xgboost"]["training_samples"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM xgboost_training_logs")
            result["xgboost"]["training_runs"] = cursor.fetchone()[0]
            
            conn.close()
        except Exception:
            pass
    
    # Check Flow Predictor
    try:
        from ml.flow_predictor import flow_model
        result["flow_predictor"]["is_fitted"] = flow_model.is_fitted if hasattr(flow_model, 'is_fitted') else False
    except Exception:
        pass
    
    return result


async def _get_outcome_stats() -> Dict[str, Any]:
    """Get outcome tracking statistics."""
    conn = _get_db_connection()
    if not conn:
        return {"error": "Database unavailable"}
    
    try:
        cursor = conn.cursor()
        
        # Total outcomes
        cursor.execute("SELECT COUNT(*) FROM signal_outcomes")
        total = cursor.fetchone()[0]
        
        # Hit rate
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits
            FROM signal_outcomes
        """)
        row = cursor.fetchone()
        hit_rate = round(100.0 * (row[1] or 0) / row[0], 1) if row[0] > 0 else 0
        
        # By interval
        cursor.execute("""
            SELECT 
                interval_hours,
                COUNT(*) as cnt,
                SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits
            FROM signal_outcomes
            GROUP BY interval_hours
        """)
        by_interval = {}
        for row in cursor.fetchall():
            by_interval[f"{row[0]}h"] = {
                "count": row[1],
                "hits": row[2] or 0,
                "hit_rate": round(100.0 * (row[2] or 0) / row[1], 1) if row[1] > 0 else 0
            }
        
        conn.close()
        
        return {
            "total_outcomes": total,
            "overall_hit_rate": hit_rate,
            "by_interval": by_interval,
            "tracking_active": total > 0,
        }
        
    except Exception as e:
        conn.close()
        return {"error": str(e), "total_outcomes": 0}


def _get_db_health() -> Dict[str, Any]:
    """Check database health."""
    conn = _get_db_connection()
    if not conn:
        return {"connected": False, "error": "Cannot connect"}
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        
        # Get DB size
        cursor.execute("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
        db_size = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "connected": True,
            "table_count": table_count,
            "size_bytes": db_size,
            "size_mb": round(db_size / 1024 / 1024, 2),
        }
        
    except Exception as e:
        return {"connected": False, "error": str(e)}


async def _check_connections() -> Dict[str, Any]:
    """Check external service connections."""
    import httpx
    
    connections = {}
    
    # CoinGecko
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("https://api.coingecko.com/api/v3/ping")
            connections["coingecko"] = {"status": "connected" if resp.status_code == 200 else "error"}
    except Exception:
        connections["coingecko"] = {"status": "disconnected"}
    
    # XRPL
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                "https://s1.ripple.com:51234/",
                json={"method": "server_info", "params": [{}]}
            )
            connections["xrpl_rpc"] = {"status": "connected" if resp.status_code == 200 else "error"}
    except Exception:
        connections["xrpl_rpc"] = {"status": "disconnected"}
    
    # Redis (if configured)
    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        try:
            import redis.asyncio as redis_lib
            r = redis_lib.from_url(redis_url)
            await r.ping()
            connections["redis"] = {"status": "connected"}
            await r.close()
        except Exception:
            connections["redis"] = {"status": "disconnected"}
    
    return connections


# =============================================================================
# ML TRAINING METRICS
# =============================================================================

@router.get("/admin/ml-metrics")
async def get_ml_metrics() -> Dict[str, Any]:
    """
    Detailed ML training metrics and history.
    
    Shows training progress, model performance, and data collection status.
    """
    metrics = {
        "timestamp": _now_iso(),
        "xgboost": {},
        "training_data": {},
        "recommendations": [],
    }
    
    # XGBoost model info
    try:
        from ml.latency_xgboost import latency_predictor
        info = latency_predictor.get_model_info()
        metrics["xgboost"] = {
            "model_version": info.get("model_version", "unknown"),
            "is_fitted": info.get("is_fitted", False),
            "training_rmse": info.get("training_rmse", 0),
            "feature_names": info.get("feature_names", []),
            "best_params": info.get("best_params", {}),
            "last_tune_ts": info.get("last_tune_ts", 0),
            "xgboost_available": info.get("xgboost_available", False),
        }
    except Exception as e:
        metrics["xgboost"]["error"] = str(e)
    
    # Training data availability
    conn = _get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # Latency events
            cursor.execute("SELECT COUNT(*) FROM latency_events")
            latency_count = cursor.fetchone()[0]
            
            # Training logs
            cursor.execute("SELECT COUNT(*) FROM xgboost_training_logs")
            training_runs = cursor.fetchone()[0]
            
            # Signals for training
            cursor.execute("SELECT COUNT(*) FROM signals WHERE confidence > 60")
            high_conf_signals = cursor.fetchone()[0]
            
            metrics["training_data"] = {
                "latency_events": latency_count,
                "training_runs": training_runs,
                "high_confidence_signals": high_conf_signals,
                "ready_for_training": latency_count >= 500,
                "samples_needed": max(0, 500 - latency_count),
            }
            
            conn.close()
        except Exception as e:
            metrics["training_data"]["error"] = str(e)
    
    # Recommendations
    recommendations = []
    if not metrics["xgboost"].get("is_fitted"):
        if metrics["training_data"].get("latency_events", 0) < 500:
            recommendations.append(f"Collect {metrics['training_data'].get('samples_needed', 500)} more latency samples before training")
        else:
            recommendations.append("Sufficient data available - trigger manual training")
    
    if metrics["training_data"].get("latency_events", 0) == 0:
        recommendations.append("Enable latency pinger to start collecting training data")
    
    metrics["recommendations"] = recommendations
    
    return metrics


# =============================================================================
# INGESTION TIMELINE
# =============================================================================

@router.get("/admin/ingestion-timeline")
async def get_ingestion_timeline(
    hours: int = Query(24, description="Hours of history to show")
) -> Dict[str, Any]:
    """
    Get signal ingestion timeline for visualization.
    
    Returns hourly signal counts for the specified period.
    """
    conn = _get_db_connection()
    if not conn:
        return {"error": "Database unavailable"}
    
    try:
        cursor = conn.cursor()
        
        # Get hourly counts
        start_ts = int(time.time()) - (hours * 3600)
        cursor.execute("""
            SELECT 
                (timestamp / 3600) * 3600 as hour_bucket,
                type,
                COUNT(*) as cnt
            FROM signals
            WHERE timestamp > ?
            GROUP BY hour_bucket, type
            ORDER BY hour_bucket
        """, (start_ts,))
        
        # Organize by hour
        timeline = {}
        for row in cursor.fetchall():
            hour_ts = row[0]
            hour_str = datetime.fromtimestamp(hour_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:00")
            if hour_str not in timeline:
                timeline[hour_str] = {"total": 0, "by_type": {}}
            timeline[hour_str]["by_type"][row[1]] = row[2]
            timeline[hour_str]["total"] += row[2]
        
        conn.close()
        
        return {
            "timestamp": _now_iso(),
            "hours": hours,
            "timeline": timeline,
            "hourly_average": sum(h["total"] for h in timeline.values()) / max(len(timeline), 1),
        }
        
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# SYSTEM ALERTS
# =============================================================================

@router.get("/admin/alerts")
async def get_system_alerts() -> Dict[str, Any]:
    """
    Get active system alerts and warnings.
    
    Checks for issues that need attention.
    """
    alerts = []
    
    # Check signal flow
    conn = _get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # No signals in last hour
            one_hour_ago = int(time.time()) - 3600
            cursor.execute("SELECT COUNT(*) FROM signals WHERE timestamp > ?", (one_hour_ago,))
            if cursor.fetchone()[0] == 0:
                alerts.append({
                    "level": "warning",
                    "component": "signal_ingestion",
                    "message": "No signals received in the last hour",
                    "action": "Check scanner connections"
                })
            
            # No outcomes tracked
            cursor.execute("SELECT COUNT(*) FROM signal_outcomes")
            if cursor.fetchone()[0] == 0:
                alerts.append({
                    "level": "info",
                    "component": "outcome_tracking",
                    "message": "No outcome data yet - predictions not being validated",
                    "action": "Wait for 1h/4h/24h intervals to pass"
                })
            
            conn.close()
        except Exception:
            pass
    
    # Check ML training
    try:
        from ml.latency_xgboost import latency_predictor
        info = latency_predictor.get_model_info()
        if not info.get("is_fitted"):
            alerts.append({
                "level": "info",
                "component": "ml_training",
                "message": "XGBoost model not yet trained",
                "action": "Collect 500+ latency samples to enable training"
            })
    except Exception:
        pass
    
    return {
        "timestamp": _now_iso(),
        "alert_count": len([a for a in alerts if a.get("level") in ("warning", "error")]),
        "alerts": alerts,
    }


# =============================================================================
# ADMIN ACTIONS
# =============================================================================

@router.post("/admin/trigger-outcome-check")
async def trigger_outcome_check() -> Dict[str, Any]:
    """
    Manually trigger outcome checking for all intervals.
    Useful for testing and debugging the outcome pipeline.
    """
    results = {
        "timestamp": _now_iso(),
        "intervals_checked": [],
        "total_processed": 0,
        "errors": [],
        "debug": {},
    }
    
    try:
        from db.connection import is_sqlite
        from db.signals import get_signals_pending_outcome
        from workers.outcome_checker import check_outcomes_for_interval
        
        results["debug"]["is_sqlite"] = is_sqlite()
        
        # Test if we can find pending signals
        test_signals = await get_signals_pending_outcome(1, limit=3)
        results["debug"]["test_signals_found"] = len(test_signals)
        if test_signals:
            results["debug"]["sample_signal"] = {
                "id": test_signals[0].get("signal_id", "?")[:20],
                "type": test_signals[0].get("type"),
                "detected_at": str(test_signals[0].get("detected_at")),
            }
        
        for interval in [1, 4, 12, 24]:
            try:
                processed = await check_outcomes_for_interval(interval)
                results["intervals_checked"].append({
                    "interval_hours": interval,
                    "processed": processed,
                })
                results["total_processed"] += processed
            except Exception as e:
                results["errors"].append(f"{interval}h: {str(e)}")
        
    except Exception as e:
        import traceback
        results["errors"].append(f"Error: {str(e)}")
        results["debug"]["traceback"] = traceback.format_exc()
    
    return results


@router.post("/admin/collect-latency-sample")
async def collect_latency_sample() -> Dict[str, Any]:
    """
    Manually collect a latency sample for ML training.
    """
    try:
        from predictors.latency_pinger import collect_single_sample
        sample = await collect_single_sample()
        return {
            "timestamp": _now_iso(),
            "success": True,
            "sample": sample,
        }
    except ImportError:
        # Create a simple sample collector if pinger doesn't exist
        import httpx
        
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.get("https://api.coingecko.com/api/v3/ping")
            latency = (time.time() - start) * 1000
            
            # Store in DB
            conn = _get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO latency_events (endpoint, latency_ms, collected_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    ("coingecko_ping", latency)
                )
                conn.commit()
                conn.close()
            
            return {
                "timestamp": _now_iso(),
                "success": True,
                "latency_ms": round(latency, 2),
                "endpoint": "coingecko_ping",
            }
        except Exception as e:
            return {
                "timestamp": _now_iso(),
                "success": False,
                "error": str(e),
            }
    except Exception as e:
        return {
            "timestamp": _now_iso(),
            "success": False,
            "error": str(e),
        }
