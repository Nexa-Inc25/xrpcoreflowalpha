from datetime import datetime, timezone
from typing import Dict


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
    return {
        "layout_version": "1.0",
        "timestamp": _now_iso(),
        "components": [comp],
        "predictive_actions": [{"type": "prefetch_chart", "symbol": "XRP-USD", "timeframe": "15m"}],
    }
