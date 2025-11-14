import asyncio
import time
import uuid
from itertools import combinations
from typing import Dict, List

import redis.asyncio as redis

from alerts.slack import send_slack_alert, build_cross_slack_payload
from app.config import REDIS_URL, CROSS_SIGNAL_DEDUP_TTL
from bus.signal_bus import fetch_recent_signals, publish_cross_signal
from ml.impact_predictor import predict_xrp_impact


def _pair_ok(a: Dict, b: Dict) -> bool:
    if a.get("type") == b.get("type"):
        return False
    # At least one must be crypto (xrp or zk) and one may be equity
    types = {a.get("type"), b.get("type")}
    return ("xrp" in types or "zk" in types) and ("equity" in types or "xrp" in types or "zk" in types)


def _confidence(a: Dict, b: Dict) -> int:
    # Base confidence from USD size and recency
    try:
        v = float(a.get("usd_value") or 0) + float(b.get("usd_value") or 0)
    except Exception:
        v = 0.0
    dt = abs(int(a.get("timestamp", 0)) - int(b.get("timestamp", 0)))
    base = 60
    if v >= 25_000_000:
        base += 25
    elif v >= 10_000_000:
        base += 18
    elif v >= 5_000_000:
        base += 12
    # Time decay within 15 minutes
    if dt <= 120:
        base += 15
    elif dt <= 300:
        base += 10
    elif dt <= 900:
        base += 5
    # Type bonuses
    t = {a.get("type"), b.get("type")}
    if "xrp" in t and "equity" in t:
        base += 10
    if "zk" in t:
        base += 5
    return min(99, base)


def _mk_cross(a: Dict, b: Dict) -> Dict:
    dt = abs(int(a.get("timestamp", 0)) - int(b.get("timestamp", 0)))
    conf = _confidence(a, b)
    impact = predict_xrp_impact(a, b)
    return {
        "id": str(uuid.uuid4()),
        "signals": [a, b],
        "confidence": conf,
        "predicted_impact_pct": round(float(impact), 2),
        "time_delta": dt,
        "timestamp": int(time.time()),
    }


async def _dedup_allow(cross: Dict) -> bool:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    s1 = cross.get("signals", [{}])[0]
    s2 = cross.get("signals", [{}])[1]
    key = f"cross:dedup:{s1.get('type')}:{s2.get('type')}:{s1.get('tx_hash') or s1.get('id')}:{s2.get('tx_hash') or s2.get('id')}"
    added = await r.set(key, "1", ex=CROSS_SIGNAL_DEDUP_TTL, nx=True)
    return bool(added)


async def correlate_signals(signals: List[Dict]) -> List[Dict]:
    out: List[Dict] = []
    # Only consider signals in last 15 minutes
    now = int(time.time())
    recent = [s for s in signals if now - int(s.get("timestamp", 0)) <= 900]
    for a, b in combinations(recent, 2):
        if not _pair_ok(a, b):
            continue
        cross = _mk_cross(a, b)
        if cross["confidence"] >= 85 and await _dedup_allow(cross):
            out.append(cross)
    return out


async def run_correlation_loop():
    while True:
        try:
            signals = await fetch_recent_signals(window_seconds=900)
            crosses = await correlate_signals(signals)
            for c in crosses:
                await publish_cross_signal(c)
                payload = build_cross_slack_payload(c)
                await send_slack_alert(payload)
                print(f"[CROSS] Correlated {c['signals'][0].get('type')} + {c['signals'][1].get('type')} | conf {c['confidence']} | impact {c['predicted_impact_pct']}%")
        except Exception as e:
            print("[CROSS] error:", repr(e))
        await asyncio.sleep(60)
