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
        # Trustlines are often stables; treat limit_value as USD magnitude.
        return _safe_float(signal.get("limit_value"), 0.0)
    if stype == "rwa_amm":
        chg = (signal.get("amm_liquidity_change") or {}).get("lp_change_pct")
        base = _safe_float(chg, 0.0)
        # Represent as pseudo-notional; caller only compares thresholds.
        return abs(base) * 100_000_000.0
    return 0.0


def _flow_to_state(signal: Dict[str, Any]) -> str:
    """Map a raw XRPL/ISO signal into a coarse Markov state.

    This is heuristic and intentionally conservative – it can be tightened by
    updating address/issuer sets without touching callers.
    """

    stype = str(signal.get("type") or "").lower()
    sub = str(signal.get("sub_type") or "").lower()
    tags = [str(t).lower() for t in (signal.get("tags") or [])]
    dest = str(signal.get("destination") or "").lower()
    issuer = str(signal.get("issuer") or "").lower()
    amt_usd = _infer_amount_usd(signal)

    # Escrow unlock / supply releases
    if sub.startswith("escrow") or "escrow" in " ".join(tags):
        return "escrow_unlock"

    # ODL-style corridors: large XRP payments into known hot wallets
    if stype == "xrp" and amt_usd >= 10_000_000:
        if dest.startswith("rwcogn") or dest.startswith("rwco"):
            return "odl_priming"

    # Large trustlines / issuer refills → liquidity injection regimes
    if stype == "trustline" and amt_usd >= 100_000_000:
        if issuer.startswith("rh"):  # Ripple-issued stables / gateways
            return "liquidity_injection"

    # Deep orderbook / RWA AMM shifts near GoDark partners tilt towards pump.
    if stype in {"orderbook", "rwa_amm"} and amt_usd >= 50_000_000:
        if any("godark" in t for t in tags) or any("rwa" in t for t in tags):
            return "odl_priming"

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
    """

    amt_usd = _infer_amount_usd(signal)
    state = _flow_to_state(signal)
    pump_prob = _predictor.predict_pump_prob(state, steps=8)

    # Simple momentum stub: treat ODL / liquidity states as strong momentum.
    if state in {"odl_priming", "liquidity_injection"}:
        momentum = 1.0
    elif state == "escrow_unlock":
        momentum = 0.1
    else:
        momentum = 0.5

    confidence_0_1 = max(0.0, min(1.0, 0.6 * pump_prob + 0.4 * momentum))
    expected_move = 2.1 + confidence_0_1 * 18.3

    # Direction + timeframe
    if confidence_0_1 >= 0.75:
        direction = "BULLISH"
    elif pump_prob < 0.2 and state == "escrow_unlock":
        direction = "BEARISH"
    else:
        direction = "MONITOR"

    dest = str(signal.get("destination") or "").lower()
    if "odl" in " ".join([* (signal.get("tags") or []), dest]):
        timeframe = "2–6 hours"
    else:
        timeframe = "6–24 hours"

    out: Dict[str, Any] = {
        "iso_state": state,
        "iso_pump_prob": float(round(pump_prob, 4)),
        "iso_confidence": int(round(confidence_0_1 * 100)),
        "iso_expected_move_pct": float(round(expected_move, 1)),
        "iso_direction": direction,
        "iso_timeframe": timeframe,
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
