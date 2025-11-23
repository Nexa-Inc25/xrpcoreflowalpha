import time
from collections import deque
from typing import Dict, Tuple, Optional

import numpy as np

from observability.metrics import (
    zk_dominant_frequency_hz,
    zk_frequency_confidence,
)


KNOWN_FINGERPRINTS: Dict[str, float] = {
    "wintermute_btc": 1.0 / 41.0,
    "jane_street_eth": 1.0 / 17.3,
    "cumberland_eth": 1.0 / 60.0,
    "ghostprint_2025": 1.0 / 11.7,
}


class FrequencyFingerprinter:
    def __init__(self, window_seconds: int = 300, sample_rate_hz: float = 1.0):
        self.window = float(window_seconds)
        self.sample_rate = float(sample_rate_hz)
        self._ts: deque[float] = deque()
        self._vals: deque[float] = deque()
        self._last_compute_ts: float = 0.0

    def add_event(self, timestamp: Optional[float] = None, value: float = 1.0) -> None:
        ts = float(timestamp or time.time())
        self._ts.append(ts)
        self._vals.append(float(value))
        cutoff = ts - self.window
        while self._ts and self._ts[0] < cutoff:
            self._ts.popleft()
            self._vals.popleft()

    def _compute(self) -> Tuple[float, float, str, float]:
        if len(self._vals) < 50:
            return 0.0, 0.0, "unknown", 0.0
        t = np.array(self._ts, dtype=float)
        v = np.array(self._vals, dtype=float)
        t0 = float(np.min(t))
        t1 = float(np.max(t))
        if not np.isfinite(t0) or not np.isfinite(t1) or t1 <= t0:
            return 0.0, 0.0, "unknown", 0.0
        step = 1.0 / self.sample_rate
        grid = np.arange(t0, t1 + step, step)
        resampled = np.interp(grid, t, v)
        if resampled.size < 8:
            return 0.0, 0.0, "unknown", 0.0
        detrended = resampled - float(np.mean(resampled))
        window = np.hanning(len(detrended))
        x = detrended * window
        # rFFT
        fft_vals = np.abs(np.fft.rfft(x))
        freqs = np.fft.rfftfreq(x.size, d=step)
        if freqs.size <= 2:
            return 0.0, 0.0, "unknown", 0.0
        # ignore DC and very low frequency bins
        start_idx = max(1, int(0.01 / (freqs[1] - freqs[0])) if freqs.size > 1 else 1)
        peak_idx_rel = int(np.argmax(fft_vals[start_idx:]))
        peak_idx = start_idx + peak_idx_rel
        dom_freq = float(freqs[peak_idx]) if peak_idx < freqs.size else 0.0
        power = float(fft_vals[peak_idx]) if peak_idx < fft_vals.size else 0.0
        # fingerprint match
        if not KNOWN_FINGERPRINTS:
            return dom_freq, power, "unknown", 0.0
        best_name = "unknown"
        best_freq = 0.0
        best_err = float("inf")
        for name, f in KNOWN_FINGERPRINTS.items():
            err = abs(dom_freq - float(f))
            if err < best_err:
                best_err = err
                best_name = name
                best_freq = float(f)
        confidence = 0.0
        if best_freq > 0:
            rel = best_err / best_freq
            confidence = max(0.0, 100.0 - rel * 1000.0)
            confidence = float(min(confidence, 100.0))
        return dom_freq, power, best_name, confidence

    def tick(self, source_label: str = "zk_events") -> Dict[str, float | str]:
        now = time.time()
        if now - self._last_compute_ts < 1.0:
            return {"freq": 0.0, "power": 0.0, "fingerprint": "", "confidence": 0.0}
        self._last_compute_ts = now
        freq, power, fp, conf = self._compute()
        try:
            zk_dominant_frequency_hz.labels(source=source_label).set(float(freq))
        except Exception:
            pass
        try:
            zk_frequency_confidence.labels(algo_fingerprint=fp or "unknown").set(float(conf))
        except Exception:
            pass
        return {
            "freq": round(float(freq), 6),
            "power": round(float(power), 3),
            "fingerprint": fp or "unknown",
            "confidence": round(float(conf), 2),
        }


zk_fingerprinter = FrequencyFingerprinter()
