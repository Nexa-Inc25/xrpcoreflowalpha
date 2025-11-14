from typing import Dict

# Lightweight heuristic predictor for XRP 15-min impact (%).
# Uses live signal features only; no external model deps.

def _type_bonus(a: Dict, b: Dict) -> float:
    types = {a.get("type"), b.get("type")}
    bonus = 0.0
    if "equity" in types and "xrp" in types:
        bonus += 0.6
    if "zk" in types:
        bonus += 0.3
    return bonus


def predict_xrp_impact(a: Dict, b: Dict) -> float:
    try:
        v = float(a.get("usd_value") or 0.0) + float(b.get("usd_value") or 0.0)
    except Exception:
        v = 0.0
    try:
        dt = abs(int(a.get("timestamp", 0)) - int(b.get("timestamp", 0)))
    except Exception:
        dt = 900

    # Size-driven base effect (cap at ~5%)
    base = 0.0
    if v >= 100_000_000:
        base = 3.0
    elif v >= 50_000_000:
        base = 2.2
    elif v >= 25_000_000:
        base = 1.6
    elif v >= 10_000_000:
        base = 1.0
    elif v >= 5_000_000:
        base = 0.6

    # Time proximity bonus (closer = stronger effect)
    if dt <= 120:
        base += 0.6
    elif dt <= 300:
        base += 0.4
    elif dt <= 900:
        base += 0.2

    # Type bonuses
    base += _type_bonus(a, b)

    # Clamp and round
    if base < 0:
        base = 0.0
    if base > 5.0:
        base = 5.0
    return round(base, 2)
