import json
import time
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from app.config import REDIS_URL
from godark.detector import annotate_godark
from godark.pattern_monitor import detect_godark_patterns
from utils.retry import async_retry
from predictors.markov_predictor import zk_hmm, classify_observation
from predictors.frequency_fingerprinter import zk_fingerprinter
from observability.metrics import zk_flow_confidence_score
from predictors.xrp_iso_predictor import enrich_iso_signal

_redis: Optional[redis.Redis] = None


async def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    try:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
    except Exception:
        return default


async def publish_signal(signal: Dict[str, Any]) -> None:
    r = await _get_redis()
    try:
        signal = await annotate_godark(signal)
    except Exception:
        pass
    try:
        if _safe_get(signal, "type") == "xrp":
            amt = _safe_get(signal, "amount_xrp")
            if amt is not None and float(amt) > 5_000_000_000:
                return
    except Exception:
        return
    # Higher-order GoDark patterns (clusters, batches, cross-chain, equity rotation)
    try:
        signal = await detect_godark_patterns(signal)
    except Exception:
        pass
    # Ensure required fields
    if "timestamp" not in signal:
        signal["timestamp"] = int(time.time())
    if "id" not in signal:
        signal["id"] = f"{_safe_get(signal,'type','unknown')}:{signal['timestamp']}:{int(time.time()*1000)}"
    # Validate minimal structure
    if not validate_signal(signal):
        try:
            print(f"[VALIDATION] Dropped invalid signal: {signal.get('id','?')}")
        except Exception:
            print("[VALIDATION] Dropped invalid signal")
        return
    try:
        stype = str(_safe_get(signal, "type") or "").lower()
        ts = int(_safe_get(signal, "timestamp") or int(time.time()))
        if stype == "zk":
            zk_fingerprinter.add_event(timestamp=float(ts), value=1.0)
            zk_fingerprinter.tick(source_label="zk_events")
        elif stype == "xrp":
            tags = [str(t).lower() for t in (signal.get("tags") or [])]
            usd = 0.0
            try:
                usd = float(_safe_get(signal, "usd_value") or 0.0)
            except Exception:
                usd = 0.0
            if ("godark xrpl settlement" in tags or "godark settlement" in tags) and usd > 0:
                zk_fingerprinter.add_event(timestamp=float(ts), value=(usd / 1e6))
                zk_fingerprinter.tick(source_label="xrpl_settlements")
    except Exception:
        pass
    try:
        obs = classify_observation(signal)
        prob = await zk_hmm.update(obs)
        try:
            zk_flow_confidence_score.labels(protocol="godark").set(float(prob))
        except Exception:
            pass
        signal["zk_markov_imminent_prob"] = float(round(float(prob), 4))
    except Exception:
        pass
    # ISO / XRPL predictor enrichment (XRPL payments, trustlines, RWA AMMs, OB)
    try:
        stype = str(_safe_get(signal, "type") or "").lower()
        if stype in ("xrp", "trustline", "rwa_amm", "orderbook"):
            signal = enrich_iso_signal(signal)
    except Exception:
        pass
    
    # Add explorer links for transaction verification
    try:
        from workers.ledger_monitor import enrich_signal_with_explorer_links
        signal = enrich_signal_with_explorer_links(signal)
    except Exception:
        pass
    
    data = json.dumps(signal, separators=(",", ":"))
    try:
        await r.xadd("signals", {"json": data}, maxlen=5000, approximate=True)
    except Exception as e:
        print("[REDIS] xadd failed:", repr(e))
    
    # Store signal to database for analytics tracking
    try:
        from db.signals import store_signal
        await store_signal(signal)
    except ImportError:
        pass  # DB module not available
    except Exception as e:
        print(f"[DB] Signal storage failed: {e}")
    
    # Send Slack alert for high-confidence signals
    try:
        from workers.slack_alerts import process_signal_for_alerts
        await process_signal_for_alerts(signal)
    except ImportError:
        pass
    except Exception as e:
        print(f"[SlackAlert] Failed: {e}")


async def fetch_recent_signals(window_seconds: int = 900, types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    r = await _get_redis()
    now_ms = int(time.time() * 1000)
    start = now_ms - window_seconds * 1000
    start_id = f"{start}-0"
    try:
        rows = await r.xrange("signals", min=start_id, max="+")
    except Exception as e:
        print("[REDIS] xrange failed:", repr(e))
        rows = []
    out: List[Dict[str, Any]] = []
    for _, fields in rows:
        raw = fields.get("json")
        if not raw:
            continue
        try:
            s = json.loads(raw)
        except Exception:
            continue
        if types and s.get("type") not in types:
            continue
        out.append(s)
    return out


# Cross-signal helpers (for SDUI feed and alerts)
async def publish_cross_signal(cross: Dict[str, Any]) -> None:
    r = await _get_redis()
    if "timestamp" not in cross:
        cross["timestamp"] = int(time.time())
    data = json.dumps(cross, separators=(",", ":"))
    await r.xadd("cross_signals", {"json": data}, maxlen=1000, approximate=True)


async def fetch_recent_cross_signals(limit: int = 10) -> List[Dict[str, Any]]:
    r = await _get_redis()
    try:
        rows = await r.xrevrange("cross_signals", max="+", min="-", count=limit)
    except Exception as e:
        print("[REDIS] xrevrange failed:", repr(e))
        rows = []
    out: List[Dict[str, Any]] = []
    for _, fields in rows:
        raw = fields.get("json")
        if not raw:
            continue
        try:
            s = json.loads(raw)
        except Exception:
            continue
        out.append(s)
    out.reverse()
    return out


def validate_signal(sig: Dict[str, Any]) -> bool:
    try:
        if not isinstance(sig, dict):
            return False
        req = ["type", "timestamp", "tags"]
        for k in req:
            if k not in sig:
                return False
        return isinstance(sig.get("tags"), list)
    except Exception:
        return False
