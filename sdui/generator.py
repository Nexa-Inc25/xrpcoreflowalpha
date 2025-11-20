from datetime import datetime, timezone
from typing import Dict, Any
from app.config import EXECUTION_ENABLED


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt_delta(seconds: int) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    return f"{m}m {s}s"


def generate_sdui_payload(cross: Dict) -> dict:
    confidence = int(cross.get("confidence", 0))
    impact = float(cross.get("predicted_impact_pct", 0.0))
    delta = int(cross.get("time_delta", 0))
    godark = bool(cross.get("godark"))
    urgency = "CRITICAL" if godark else ("HIGH" if impact >= 1.5 else "MEDIUM")
    color = "#8b5cf6" if godark else ("#ff0000" if urgency == "HIGH" else "#ffa500")
    s1, s2 = cross.get("signals", [{}])[0], (cross.get("signals", [{}])[1] if len(cross.get("signals", [])) > 1 else {})
    def _sum(sig: Dict) -> str:
        return sig.get("summary") or sig.get("type", "").upper()
    actions = []
    # Add XRPL tx links if present; add equity ticker link if present
    for s in (s1, s2):
        try:
            if s.get("type") == "xrp" and s.get("tx_hash"):
                tx = s.get("tx_hash")
                actions.append({"label": "XRPL Tx", "url": f"https://livenet.xrpl.org/transactions/{tx}"})
            if s.get("type") == "equity" and s.get("symbol"):
                sym = s.get("symbol")
                actions.append({"label": f"{sym} Quote", "url": f"https://finance.yahoo.com/quote/{sym}"})
        except Exception:
            pass
    # Title and type for GoDark
    ctype = "godark_signal_card" if godark else "cross_signal_card"
    reason = (cross.get("godark_reason") or "").lower()
    if godark:
        if reason == "settlement":
            title = "GODARK XRPL SETTLEMENT: CRITICAL"
        elif reason == "partner":
            title = "GODARK PARTNER FLOW: CRITICAL"
        elif reason == "cross":
            title = "GODARK ROTATION: CRITICAL"
        else:
            title = "GODARK SIGNAL: CRITICAL"
    else:
        title = f"CROSS-MARKET SIGNAL: {urgency}"

    comp = {
        "type": ctype,
        "id": f"cross_{cross.get('id','')}",
        "title": title,
        "urgency": urgency,
        "color": color,
        "summary": f"{_sum(s1)} → {_sum(s2)}",
        "time_delta": _fmt_delta(delta),
        "confidence": confidence,
        "predicted_impact": f"{impact:+.2f}% XRP in 15m",
        "actions": actions,
        "auto_expand": confidence >= 90,
    }
    if godark:
        comp["badge"] = "GoDark"
        if confidence >= 95:
            if EXECUTION_ENABLED:
                comp.setdefault("actions", []).append({"label": "Execute Counter-Trade", "url": "", "enabled": True})
            else:
                comp.setdefault("actions", []).append({"label": "Execute Counter-Trade", "url": "", "enabled": False})
    ts = cross.get("timestamp")
    ts_iso = datetime.fromtimestamp(ts, timezone.utc).isoformat() if isinstance(ts, (int, float)) and ts > 0 else _now_iso()
    return {
        "layout_version": "1.0",
        "timestamp": ts_iso,
        "components": [comp],
        "predictive_actions": [{"type": "prefetch_chart", "symbol": "XRP-USD", "timeframe": "15m"}],
    }


def generate_rwa_amm_payload(sig: Dict[str, Any]) -> dict:
    chg = sig.get("amm_liquidity_change", {}).get("lp_change_pct")
    pct = round(float(chg) * 100.0, 2) if isinstance(chg, (int, float)) else None
    tags = [str(t) for t in (sig.get("tags") or [])]
    # Color mapping
    if any("GoDark" in t for t in tags):
        color = "#8b5cf6"
    elif any("Withdrawal" in t for t in tags):
        color = "#ff0000"
    elif any("Deposit" in t for t in tags):
        color = "#10b981"
    else:
        color = "#ffa500"
    badge = None
    if pct is not None:
        arrow = "+" if pct > 0 else ""
        badge = f"AMM {arrow}{pct}%"
    comp = {
        "type": "rwa_amm_liquidity_card",
        "id": f"rwa_amm_{sig.get('tx_hash','')}",
        "title": "RWA AMM LIQUIDITY",
        "urgency": sig.get("urgency") or "MEDIUM",
        "color": color,
        "summary": sig.get("summary") or "RWA AMM Liquidity Shift",
        "time_delta": "",
        "confidence": None,
        "predicted_impact": None,
        "actions": [],
        "auto_expand": False,
    }
    if sig.get("tx_hash"):
        comp["actions"].append({"label": "XRPL Tx", "url": f"https://livenet.xrpl.org/transactions/{sig['tx_hash']}"})
    if badge:
        comp["badge"] = badge
    ts = sig.get("timestamp")
    ts_iso = datetime.fromtimestamp(ts, timezone.utc).isoformat() if isinstance(ts, (int, float)) and ts > 0 else _now_iso()
    return {
        "layout_version": "1.0",
        "timestamp": ts_iso,
        "components": [comp],
        "predictive_actions": [],
    }


def generate_redis_monitor_payload(stats: Dict[str, Any]) -> dict:
    status = stats.get("status") or "unreachable"
    color = "#10b981" if status == "ok" else "#ef4444"
    used_memory = stats.get("used_memory") or ""
    connected = stats.get("connected_clients")
    ops = stats.get("ops_per_sec")
    windows = stats.get("windows") or {}
    godark = windows.get("godark:settlements", 0)
    penumbra = windows.get("penumbra:unshields", 0)
    secret = windows.get("secret:unshields", 0)
    comp = {
        "type": "redis_monitor_card",
        "id": "redis_state",
        "title": "Redis State",
        "urgency": "INFO" if status == "ok" else "CRITICAL",
        "color": color,
        "summary": f"Memory: {used_memory} | Ops/sec: {ops}",
        "time_delta": "",
        "confidence": None,
        "predicted_impact": None,
        "actions": [],
        "auto_expand": status != "ok",
        "memory_used": used_memory,
        "connected_clients": connected,
        "ops_per_sec": ops,
        "godark_cluster": godark,
        "penumbra_cluster": penumbra,
        "secret_cluster": secret,
        "status": status,
    }
    ts_iso = _now_iso()
    return {
        "layout_version": "1.0",
        "timestamp": ts_iso,
        "components": [comp],
        "predictive_actions": [],
    }


def generate_orderbook_payload(sig: Dict[str, Any]) -> dict:
    tags = [str(t) for t in (sig.get("tags") or [])]
    pair = sig.get("pair") or "XRPL Pair"
    bid = float(sig.get("bid_depth_usd") or 0.0)
    ask = float(sig.get("ask_depth_usd") or 0.0)
    sp = sig.get("spread_bps")
    if any("GoDark" in t for t in tags):
        color = "#8b5cf6"
    elif any("Imbalance" in t for t in tags) or any("Whale" in t for t in tags):
        color = "#ff0000"
    elif any("Depth Surge" in t for t in tags):
        color = "#10b981"
    else:
        color = "#ffa500"
    badge = None
    if sig.get("change"):
        bc = sig["change"].get("bid_change_pct")
        ac = sig["change"].get("ask_change_pct")
        try:
            if abs(float(bc or 0)) >= abs(float(ac or 0)):
                badge = f"OB {('+' if (bc or 0)>0 else '')}{round(float(bc or 0)*100,1)}%"
            else:
                badge = f"OB {('+' if (ac or 0)>0 else '')}{round(float(ac or 0)*100,1)}%"
        except Exception:
            badge = None
    comp = {
        "type": "orderbook_card",
        "id": f"ob_{pair}",
        "title": "ORDERBOOK LIQUIDITY",
        "urgency": sig.get("urgency") or "MEDIUM",
        "color": color,
        "summary": f"{pair}: bid ${bid:,.0f} | ask ${ask:,.0f} | spread {sp if sp is not None else 'n/a'} bps",
        "time_delta": "",
        "confidence": None,
        "predicted_impact": None,
        "actions": [],
        "auto_expand": False,
    }
    if badge:
        comp["badge"] = badge
    ts = sig.get("timestamp")
    ts_iso = datetime.fromtimestamp(ts, timezone.utc).isoformat() if isinstance(ts, (int, float)) and ts > 0 else _now_iso()
    return {
        "layout_version": "1.0",
        "timestamp": ts_iso,
        "components": [comp],
        "predictive_actions": [],
    }


def generate_trustline_payload(sig: Dict[str, Any]) -> dict:
    tags = [str(t) for t in (sig.get("tags") or [])]
    val = float(sig.get("limit_value") or 0.0)
    currency = sig.get("currency") or "IOU"
    issuer = (sig.get("issuer") or "")
    urgency = "CRITICAL" if "GoDark Trustline" in tags else ("HIGH" if ("Monster Trustline" in tags or "RWA Prep" in tags) else "MEDIUM")
    color = "#8b5cf6" if urgency == "CRITICAL" else ("#ff0000" if urgency == "HIGH" else "#ffa500")
    badge = "GoDark Trustline" if "GoDark Trustline" in tags else ("Trustline" if tags else None)
    actions = []
    if sig.get("tx_hash"):
        actions.append({"label": "XRPL Tx", "url": f"https://livenet.xrpl.org/transactions/{sig['tx_hash']}"})
    if issuer:
        actions.append({"label": "Issuer", "url": f"https://livenet.xrpl.org/accounts/{issuer}"})
    comp = {
        "type": "trustline_card",
        "id": f"trustline_{sig.get('tx_hash','')}",
        "title": f"NEW TRUSTLINE: {urgency}",
        "urgency": urgency,
        "color": color,
        "summary": f"{val:,.0f} {currency} issuer {issuer[:8]}...",
        "time_delta": "",
        "confidence": None,
        "predicted_impact": "Potential XRP flow in 1–3 days",
        "actions": actions,
        "auto_expand": urgency == "CRITICAL",
    }
    if badge:
        comp["badge"] = badge
    ts = sig.get("timestamp")
    ts_iso = datetime.fromtimestamp(ts, timezone.utc).isoformat() if isinstance(ts, (int, float)) and ts > 0 else _now_iso()
    return {
        "layout_version": "1.0",
        "timestamp": ts_iso,
        "components": [comp],
        "predictive_actions": [],
    }
