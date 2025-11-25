import time
from collections import deque
from typing import Deque, Dict, Tuple

import numpy as np

try:  # pragma: no cover
    import pywt  # type: ignore
except Exception:  # pragma: no cover
    pywt = None  # type: ignore

from observability.metrics import (
    zk_wavelet_urgency_score,
    zk_flow_confidence_score,
)


class WaveletUrgencyTracker:
    def __init__(
        self,
        window_seconds: float = 600.0,
        recent_seconds: float = 60.0,
        min_points: int = 10,
        min_compute_interval: float = 5.0,
    ) -> None:
        self.window = float(window_seconds)
        self.recent = float(recent_seconds)
        self.min_points = int(min_points)
        self.min_compute_interval = float(min_compute_interval)
        self._events: Deque[Tuple[float, float]] = deque()
        self._last_compute_ts: float = 0.0

    def add_point(self, ts: float, value: float) -> None:
        t = float(ts or time.time())
        v = float(max(0.0, value))
        self._events.append((t, v))
        cutoff = t - self.window
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    def compute_score(self) -> float:
        now = time.time()
        if now - self._last_compute_ts < self.min_compute_interval:
            return 0.0
        self._last_compute_ts = now
        if pywt is None:  # wavelet lib not available
            return 0.0
        if not self._events or len(self._events) < self.min_points:
            return 0.0
        ts, vals = zip(*self._events)
        vals_arr = np.asarray(vals, dtype=float)
        if not np.all(np.isfinite(vals_arr)):
            vals_arr = np.nan_to_num(vals_arr, nan=0.0, posinf=0.0, neginf=0.0)
        if vals_arr.size < self.min_points:
            return 0.0
        # Use index space as proxy for time to avoid irregular spacing issues.
        n = vals_arr.size
        widths = np.arange(1, min(16, n + 1))
        try:
            coeffs, _ = pywt.cwt(vals_arr, widths, "morl")  # type: ignore[arg-type]
        except Exception:
            return 0.0
        energy = np.abs(coeffs) ** 2
        if not np.isfinite(energy).any():
            return 0.0
        baseline = float(np.mean(energy))
        if baseline <= 0 or not np.isfinite(baseline):
            return 0.0
        # Approximate recent window as last K points in index space.
        frac = min(1.0, max(0.1, self.recent / self.window))
        k = max(3, int(n * frac))
        recent_slice = energy[:, -k:]
        recent_peak = float(np.max(recent_slice))
        if not np.isfinite(recent_peak):
            return 0.0
        ratio = recent_peak / baseline
        # Map ratio -> [0, 100]; ratio <= 1 -> 0, ratio >= 3 -> 100.
        score = (ratio - 1.0) / (3.0 - 1.0)
        score = float(max(0.0, min(1.0, score))) * 100.0
        return float(round(score, 2))


_trackers: Dict[str, WaveletUrgencyTracker] = {}


def _get_tracker(source_label: str) -> WaveletUrgencyTracker:
    lbl = str(source_label or "macro").strip() or "macro"
    if lbl not in _trackers:
        # 10-minute window, 60-second recent band, tuned for macro cadence.
        _trackers[lbl] = WaveletUrgencyTracker(window_seconds=600.0, recent_seconds=60.0)
    return _trackers[lbl]


def update_wavelet_urgency(source_label: str, timestamp: float, notional: float) -> float:
    """Update internal buffers and Prometheus metrics for wavelet urgency.

    Returns the latest urgency score (0-100).
    """
    lbl = str(source_label or "macro").strip() or "macro"
    tracker = _get_tracker(lbl)
    try:
        tracker.add_point(float(timestamp), float(notional))
        score = tracker.compute_score()
    except Exception:
        score = 0.0
    try:
        zk_wavelet_urgency_score.labels(source=lbl).set(float(score))
    except Exception:
        pass
    # Expose a macro-oriented confidence channel alongside GoDark.
    try:
        zk_flow_confidence_score.labels(protocol="macro").set(float(score) / 100.0)
    except Exception:
        pass
    return float(score)
