import math
from typing import Any, Dict, Optional

import numpy as np


class XRPMarkovPredictor:
    """Lightweight Markov-style predictor for XRPL / ISO flows.

    This is a compact version suitable for inline scoring. It does not try to
    reproduce your full training loop, but provides a stable API that can be
    swapped with the production matrix/checkpoints on the droplet.
    """

    states = [
        "idle",
        "escrow_unlock",
        "odl_priming",
        "pump",
        "dump",
        "liquidity_injection",
    ]

    # Simple hand-tuned transition matrix; can be replaced with a trained one.
    _TRANSITION = np.array(
        [
            # idle
            [0.88, 0.03, 0.06, 0.01, 0.01, 0.01],
            # escrow_unlock
            [0.20, 0.60, 0.05, 0.02, 0.13, 0.00],
            # odl_priming
            [0.05, 0.02, 0.04, 0.79, 0.05, 0.05],
            # pump
            [0.15, 0.05, 0.10, 0.60, 0.05, 0.05],
            # dump
            [0.25, 0.05, 0.05, 0.05, 0.55, 0.05],
            # liquidity_injection
            [0.05, 0.02, 0.20, 0.60, 0.03, 0.10],
        ],
        dtype=float,
    )

    def __init__(self) -> None:
        self._index = {s: i for i, s in enumerate(self.states)}
        self._pump_idx = self._index["pump"]

    def predict_pump_prob(self, current_state: str, steps: int = 8) -> float:
        """Return probability of being in the "pump" state after N steps.

        This is intentionally simple: it is a deterministic matrix power on a
        small state space and can be swapped out with a trained matrix without
        changing callers.
        """

        steps_i = max(1, int(steps))
        start = np.zeros(len(self.states), dtype=float)
        idx = self._index.get(str(current_state or "idle"), 0)
        start[idx] = 1.0
        try:
            trans_n = np.linalg.matrix_power(self._TRANSITION, steps_i)
            future = start @ trans_n
            p = float(future[self._pump_idx])
        except Exception:
            p = 0.0
        if not math.isfinite(p):
            p = 0.0
        return float(max(0.0, min(1.0, p)))


_predictor = XRPMarkovPredictor()


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _infer_amount_usd(signal: Dict[str, Any]) -> float:
    """Best-effort USD notional for ISO flows.

    Uses usd_value when present (XRP flows, some orderbook events) and falls
    back to raw limit_value for obvious stable-style trustlines.
    """

    stype = str(signal.get("type") or "").lower()
    if stype == "xrp":
        return _safe_float(signal.get("usd_value"), 0.0)
    if stype == "orderbook":
        bid = _safe_float(signal.get("bid_depth_usd"), 0.0)
        ask = _safe_float(signal.get("ask_depth_usd"), 0.0)
        return max(bid, ask)
    if stype == "trustline":
        # Trustlines limit_value can be absurdly large (100T+ for institutional limits)
        # Only treat as USD-equivalent if it looks like a stablecoin AND is reasonable
        currency = str(signal.get("currency", "")).upper()
        limit = _safe_float(signal.get("limit_value"), 0.0)
        # Stablecoin currencies that are USD-denominated
        is_stable = currency in ("USD", "USDT", "USDC", "RLUSD", "XUSD", "FUSD")
        # Cap at $10B max for any trustline - anything higher is clearly not USD value
        if is_stable and limit <= 10_000_000_000:
            return limit
        # For non-stables or huge limits, don't treat as USD value
        return 0.0
    if stype == "rwa_amm":
        chg = (signal.get("amm_liquidity_change") or {}).get("lp_change_pct")
        base = _safe_float(chg, 0.0)
        # Represent as pseudo-notional; caller only compares thresholds.
        return abs(base) * 100_000_000.0
    return 0.0


def _flow_to_state(signal: Dict[str, Any]) -> str:
    """Map a raw XRPL/ISO signal into a coarse Markov state.

    Uses signal characteristics to determine market state.
    """

    stype = str(signal.get("type") or "").lower()
    sub = str(signal.get("sub_type") or "").lower()
    tags = [str(t).lower() for t in (signal.get("tags") or [])]
    dest = str(signal.get("destination") or "").lower()
    source = str(signal.get("source") or "").lower()
    issuer = str(signal.get("issuer") or "").lower()
    amt_usd = _infer_amount_usd(signal)
    limit_value = _safe_float(signal.get("limit_value"), 0.0)

    # Escrow operations - supply unlocks/locks
    if sub.startswith("escrow") or "escrow" in " ".join(tags):
        if sub == "escrowfinish":
            return "escrow_unlock"
        return "liquidity_injection"

    # AMM operations indicate liquidity changes
    if sub.startswith("amm") or "amm" in " ".join(tags):
        if sub == "ammdeposit":
            return "liquidity_injection"
        elif sub == "ammwithdraw":
            return "dump"  # Liquidity removal can signal selling

    # Large XRP payments - check for institutional patterns
    if stype == "xrp":
        if amt_usd >= 50_000_000:
            return "odl_priming"  # Major institutional flow
        elif amt_usd >= 10_000_000:
            return "liquidity_injection"
        elif amt_usd >= 1_000_000:
            return "pump"  # Significant activity

    # Trustlines - size matters a lot
    if stype == "trustline":
        if limit_value >= 1_000_000_000_000:  # Trillion+
            return "liquidity_injection"
        elif limit_value >= 100_000_000_000:  # 100B+
            return "odl_priming"
        elif limit_value >= 1_000_000_000:  # 1B+
            return "pump"
        elif limit_value >= 100_000_000:  # 100M+
            return "escrow_unlock"

    # ZK proofs and dark pool activity
    if stype == "zk":
        gas = _safe_float(signal.get("features", {}).get("gas_used", 0), 0.0)
        if gas >= 500_000:  # High gas = complex/large operation
            return "odl_priming"
        elif gas >= 200_000:
            return "pump"

    # Whale transfers
    if stype == "whale":
        if amt_usd >= 100_000_000:
            direction = str(signal.get("direction") or "").upper()
            if direction == "BULLISH":
                return "odl_priming"
            elif direction == "BEARISH":
                return "dump"
            return "liquidity_injection"
        elif amt_usd >= 10_000_000:
            return "pump"

    # Futures correlation signals
    if stype == "futures":
        change_pct = abs(_safe_float(signal.get("change_pct"), 0.0))
        if change_pct >= 1.0:
            return "pump" if signal.get("direction") == "up" else "dump"

    return "idle"


def score_iso_flow(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Compute model-style ISO signal summary for a single XRPL flow.

    Returns a dict with keys:
      - iso_state
      - iso_pump_prob (0–1)
      - iso_confidence (0–100)
      - iso_expected_move_pct (float, signed)
      - iso_direction (BULLISH/BEARISH/MONITOR)
      - iso_timeframe (human-readable window)
      - iso_amount_usd (best-effort notional)
      - iso_explanation (human-readable reasoning)
      - iso_factors (breakdown of scoring factors)
    """

    amt_usd = _infer_amount_usd(signal)
    state = _flow_to_state(signal)
    pump_prob = _predictor.predict_pump_prob(state, steps=8)
    stype = str(signal.get("type") or "").lower()
    sub = str(signal.get("sub_type") or "").lower()
    
    # Track factors for explanation
    factors = []

    # Dynamic momentum based on state AND signal characteristics
    if state == "odl_priming":
        momentum = 0.95
        factors.append(("State: ODL Priming", "+38%", "Major institutional flow pattern detected"))
    elif state == "liquidity_injection":
        momentum = 0.85
        factors.append(("State: Liquidity Injection", "+34%", "Large liquidity being added to market"))
    elif state == "pump":
        momentum = 0.75
        factors.append(("State: Pump Signal", "+30%", "Bullish accumulation pattern"))
    elif state == "dump":
        momentum = 0.25
        factors.append(("State: Distribution", "-30%", "Selling pressure detected"))
    elif state == "escrow_unlock":
        momentum = 0.4
        factors.append(("State: Escrow Activity", "+16%", "Supply unlock/lock event"))
    else:
        import random
        base_noise = random.uniform(0.15, 0.45)
        momentum = base_noise
        factors.append(("State: Monitoring", f"+{int(momentum*40)}%", "Standard market activity"))

    # Size factor - larger signals = higher confidence
    size_factor = 0.0
    if amt_usd >= 100_000_000:
        size_factor = 0.3
        factors.append(("Size: $100M+", "+30%", "Whale-tier transaction"))
    elif amt_usd >= 10_000_000:
        size_factor = 0.2
        factors.append(("Size: $10M+", "+20%", "Institutional-size flow"))
    elif amt_usd >= 1_000_000:
        size_factor = 0.1
        factors.append(("Size: $1M+", "+10%", "Significant capital movement"))

    # Limit value factor for trustlines
    limit_value = _safe_float(signal.get("limit_value"), 0.0)
    if limit_value >= 1_000_000_000_000:  # Trillion+
        size_factor = max(size_factor, 0.35)
        factors.append(("Trustline: Trillion+", "+35%", "Maximum institutional limit"))
    elif limit_value >= 100_000_000_000:  # 100B+
        size_factor = max(size_factor, 0.25)
        factors.append(("Trustline: 100B+", "+25%", "Major institutional limit"))
    elif limit_value >= 1_000_000_000:  # 1B+
        size_factor = max(size_factor, 0.15)
        factors.append(("Trustline: 1B+", "+15%", "Large trustline setup"))

    # Gas factor for ZK proofs
    if stype == "zk":
        gas = _safe_float(signal.get("features", {}).get("gas_used", 0), 0.0)
        if gas >= 500_000:
            size_factor = max(size_factor, 0.25)
            factors.append(("ZK Complexity: High", "+25%", "Complex ZK proof (500K+ gas)"))
        elif gas >= 200_000:
            size_factor = max(size_factor, 0.15)
            factors.append(("ZK Complexity: Medium", "+15%", "Moderate ZK proof (200K+ gas)"))

    # Calculate final confidence with variability
    confidence_0_1 = max(0.0, min(1.0, 0.4 * pump_prob + 0.35 * momentum + 0.25 * size_factor))
    
    # Expected move based on confidence and state
    base_move = 1.5 if state == "idle" else 3.0
    if state == "dump":
        expected_move = -(base_move + confidence_0_1 * 12.0)
    else:
        expected_move = base_move + confidence_0_1 * 15.0

    # Direction based on state and confidence
    if state == "dump":
        direction = "BEARISH"
    elif confidence_0_1 >= 0.70:
        direction = "BULLISH"
    elif confidence_0_1 >= 0.50:
        direction = "MONITOR"
    elif state == "escrow_unlock" and pump_prob < 0.3:
        direction = "BEARISH"
    else:
        direction = "MONITOR"

    # Timeframe based on signal type and state
    if state in {"odl_priming", "pump"} or stype == "whale":
        timeframe = "2–6 hours"
    elif state == "liquidity_injection":
        timeframe = "6–12 hours"
    elif stype == "trustline":
        timeframe = "12–48 hours"
    else:
        timeframe = "6–24 hours"

    # Build human-readable explanation
    conf_pct = int(round(confidence_0_1 * 100))
    if direction == "BULLISH":
        explanation = f"High-conviction bullish signal. {state.replace('_', ' ').title()} pattern with {conf_pct}% confidence suggests +{abs(expected_move):.1f}% move likely within {timeframe}."
    elif direction == "BEARISH":
        explanation = f"Bearish pressure detected. {state.replace('_', ' ').title()} pattern indicates potential -{abs(expected_move):.1f}% downside within {timeframe}."
    else:
        explanation = f"Monitor this signal. {state.replace('_', ' ').title()} activity with {conf_pct}% confidence. Expected ±{abs(expected_move):.1f}% volatility within {timeframe}."

    out: Dict[str, Any] = {
        "iso_state": state,
        "iso_pump_prob": float(round(pump_prob, 4)),
        "iso_confidence": int(round(confidence_0_1 * 100)),
        "iso_expected_move_pct": float(round(expected_move, 1)),
        "iso_direction": direction,
        "iso_timeframe": timeframe,
        "iso_explanation": explanation,
        "iso_factors": [{"name": f[0], "impact": f[1], "reason": f[2]} for f in factors],
    }
    if amt_usd > 0:
        out["iso_amount_usd"] = float(round(amt_usd, 2))
    return out


def enrich_iso_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Attach ISO predictor fields to a signal in-place.

    Safe no-op on failure or unsupported signal types.
    """

    try:
        stype = str(signal.get("type") or "").lower()
        if stype not in {"xrp", "trustline", "rwa_amm", "orderbook"}:
            return signal
        iso = score_iso_flow(signal)
        signal.update(iso)
        return signal
    except Exception:
        return signal
