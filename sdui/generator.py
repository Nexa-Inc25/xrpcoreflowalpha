from datetime import datetime, timezone
from typing import Dict, Any


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
    ts = cross.get("timestamp")
    ts_iso = datetime.fromtimestamp(ts, timezone.utc).isoformat() if isinstance(ts, (int, float)) and ts > 0 else _now_iso()
    return {
        "layout_version": "1.0",
        "timestamp": ts_iso,
        "components": [comp],
        "predictive_actions": [{"type": "prefetch_chart", "symbol": "XRP-USD", "timeframe": "15m"}],
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
