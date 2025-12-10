import asyncio
import time
import uuid
from itertools import combinations
from typing import Dict, List

from app.redis_utils import get_redis, REDIS_ENABLED

from alerts.slack import send_slack_alert, build_cross_slack_payload
from app.config import REDIS_URL, CROSS_SIGNAL_DEDUP_TTL
from utils.retry import async_retry
from bus.signal_bus import fetch_recent_signals, publish_cross_signal
from ml.impact_predictor import predict_xrp_impact
try:
    from ml.flow_predictor import predict_impact_ml
except Exception:
    def predict_impact_ml(cross: Dict) -> None:  # type: ignore[func-returns-value]
        return None
from app.config import EXECUTION_ENABLED
from execution.engine import XRPFlowAlphaExecution


def _pair_ok(a: Dict, b: Dict) -> bool:
    if a.get("type") == b.get("type"):
        return False
    # At least one must be crypto-like and one may be equity
    types = {a.get("type"), b.get("type")}
    crypto_types = {"xrp", "zk", "trustline", "godark_prep", "rwa_amm", "orderbook", "penumbra", "secret"}
    crypto_present = any(t in crypto_types for t in types)
    return crypto_present and ("equity" in types or crypto_present)


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
    cross = {
        "id": str(uuid.uuid4()),
        "signals": [a, b],
        "confidence": conf,
        "predicted_impact_pct": round(float(impact), 2),
        "time_delta": dt,
        "timestamp": int(time.time()),
    }
    try:
        ml_pred = predict_impact_ml(cross)
        if ml_pred is not None:
            cross["predicted_impact_pct"] = round(float(ml_pred), 2)
    except Exception:
        pass
    return cross


@async_retry(max_attempts=10, delay=2, backoff=1.5)
async def _dedup_allow(cross: Dict) -> bool:
    r = await get_redis()
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
        try:
            ta = {str(t).lower() for t in (a.get("tags") or [])}
            tb = {str(t).lower() for t in (b.get("tags") or [])}
            all_tags = ta.union(tb)
            godark_any = any("godark" in t for t in all_tags)
            boost = 1.0
            reason = None
            if any("godark xrpl settlement" in t for t in all_tags):
                boost *= 1.30
                reason = "settlement"
            elif any("godark partner" in t for t in all_tags):
                boost *= 1.15
                reason = "partner"
            tset = {a.get("type"), b.get("type")}
            if godark_any and "equity" in tset and abs(int(a.get("timestamp", 0)) - int(b.get("timestamp", 0))) <= 600:
                boost *= 1.25
                if reason is None:
                    reason = "cross"
            # GoDark settlement pattern boosts (cluster / batch / cross-chain / equity rotation)
            if any("godark cluster" in t for t in all_tags):
                boost *= 1.55
                if reason is None:
                    reason = "cluster"
            if any("godark batch" in t for t in all_tags):
                boost *= 1.60
                if reason is None:
                    reason = "batch"
            if any("godark cross-chain" in t for t in all_tags):
                boost *= 1.65
                if reason is None:
                    reason = "cross_chain"
            if any("godark equity rotation" in t for t in all_tags):
                boost *= 1.70
                if reason is None:
                    reason = "equity_rotation"
            # Penumbra unshield / settlement clusters (proxy for shielded pool exits)
            if any("penumbra unshield" in t for t in all_tags):
                boost *= 1.20
                if reason is None:
                    reason = "penumbra_unshield"
            if any("penumbra settlement cluster" in t for t in all_tags):
                boost *= 1.40
                if reason is None:
                    reason = "penumbra_cluster"
            # Secret Network unshield / settlement clusters (shielded exits via SNIP-20)
            if any("secret unshield" in t for t in all_tags):
                boost *= 1.25
                if reason is None:
                    reason = "secret_unshield"
            if any("secret settlement cluster" in t for t in all_tags):
                boost *= 1.45
                if reason is None:
                    reason = "secret_cluster"
            # Trustline boosts
            if any("rwa prep" in t for t in ta.union(tb)):
                boost *= 1.20
            if any("godark trustline" in t for t in ta.union(tb)):
                boost *= 1.35
                cross["godark"] = True
            if any("monster trustline" in t for t in ta.union(tb)):
                boost *= 1.40
            # Prep -> Settlement confirmation boost within 30 min
            a_is_prep = (a.get("type") == "godark_prep") or any("godark prep" in t for t in ta)
            b_is_prep = (b.get("type") == "godark_prep") or any("godark prep" in t for t in tb)
            a_is_settle = any("godark xrpl settlement" in t for t in ta)
            b_is_settle = any("godark xrpl settlement" in t for t in tb)
            if ((a_is_prep and b_is_settle) or (b_is_prep and a_is_settle)):
                dt = abs(int(a.get("timestamp", 0)) - int(b.get("timestamp", 0)))
                if dt <= 1800:
                    boost *= 1.50
                    cross["godark"] = True
                    cross["godark_reason"] = "prep_settlement"
            if boost != 1.0:
                cross["confidence"] = min(99, int(cross["confidence"] * boost))
                if godark_any and "equity" in tset:
                    try:
                        cross["predicted_impact_pct"] = round(float(cross["predicted_impact_pct"]) * 1.25, 2)
                    except Exception:
                        pass
                cross["godark"] = True
                cross["godark_reason"] = reason
            # RWA AMM and Orderbook influences
            amm_deposit = any("rwa amm deposit" in t for t in ta.union(tb))
            amm_withdraw = any("rwa amm withdrawal" in t for t in ta.union(tb))
            ob_depth = any("ob depth surge" in t for t in ta.union(tb))
            ob_imbalance = any("ob imbalance" in t for t in ta.union(tb))
            ob_whale = any("ob whale move" in t for t in ta.union(tb))
            godark_ext = any("godark rwa amm" in t or "godark ob shift" in t for t in ta.union(tb))
            try:
                base_impact = float(cross["predicted_impact_pct"])
            except Exception:
                base_impact = 0.0
            if amm_deposit:
                cross["predicted_impact_pct"] = round(abs(base_impact) * 1.7 or 1.7, 2)
            if amm_withdraw:
                cross["predicted_impact_pct"] = round(-abs(base_impact) * 1.5 or -1.5, 2)
            if ob_depth:
                try:
                    cross["predicted_impact_pct"] = round(float(cross["predicted_impact_pct"]) * 1.8, 2)
                except Exception:
                    pass
            if ob_imbalance or ob_whale:
                try:
                    cross["predicted_impact_pct"] = round(float(cross["predicted_impact_pct"]) * 1.5, 2)
                except Exception:
                    pass
            if godark_ext or godark_any:
                cross["godark"] = True
        except Exception:
            pass
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
                # Optional execution trigger (disabled by default)
                if EXECUTION_ENABLED and c.get("godark"):
                    try:
                        conf_ok = int(c.get("confidence", 0)) >= 95
                        imp = float(c.get("predicted_impact_pct") or 0.0)
                        imp_ok = abs(imp) >= 2.5
                    except Exception:
                        conf_ok = False
                        imp_ok = False
                    if conf_ok and imp_ok:
                        async def _exec():
                            try:
                                engine = XRPFlowAlphaExecution()
                                await engine.counter_trade(c)
                            except Exception as e:
                                print("[EXECUTION] error:", repr(e))
                        asyncio.create_task(_exec())
        except Exception as e:
            print("[CROSS] error:", repr(e))
        await asyncio.sleep(60)
