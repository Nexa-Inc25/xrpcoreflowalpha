import time
from collections import deque
from typing import Dict, Tuple, Optional, Union

import numpy as np

from observability.metrics import (
    zk_dominant_frequency_hz,
    zk_frequency_confidence,
)


# Known institutional algo fingerprints (frequency signatures)
# Format: "firm_asset": 1/period_seconds (Hz)
KNOWN_FINGERPRINTS: Dict[str, float] = {
    # Market Makers
    "wintermute_btc": 1.0 / 41.0,       # ~24.4 mHz - Wintermute BTC accumulation
    "wintermute_eth": 1.0 / 38.5,       # ~26.0 mHz - Wintermute ETH
    "jane_street_eth": 1.0 / 17.3,      # ~57.8 mHz - Jane Street ETH high-freq
    "jane_street_btc": 1.0 / 22.0,      # ~45.5 mHz - Jane Street BTC
    "cumberland_eth": 1.0 / 60.0,       # ~16.7 mHz - Cumberland OTC style
    "cumberland_btc": 1.0 / 55.0,       # ~18.2 mHz - Cumberland BTC
    
    # HFT / Prop Trading
    "citadel_eth": 1.0 / 8.7,           # ~115 mHz - Citadel high-freq bursts
    "citadel_btc": 1.0 / 9.2,           # ~109 mHz - Citadel BTC
    "citadel_accumulation": 1.0 / 45.0, # ~22.2 mHz - Citadel slow accumulation
    "jump_crypto_eth": 1.0 / 12.5,      # ~80 mHz - Jump Trading ETH
    "jump_crypto_btc": 1.0 / 14.0,      # ~71.4 mHz - Jump Trading BTC
    "tower_research": 1.0 / 6.3,        # ~159 mHz - Tower ultra high-freq
    "virtu_financial": 1.0 / 7.8,       # ~128 mHz - Virtu pattern
    
    # Crypto-Native
    "alameda_legacy": 1.0 / 33.0,       # ~30.3 mHz - Alameda-style (historical)
    "gsr_markets": 1.0 / 28.0,          # ~35.7 mHz - GSR OTC flow
    "b2c2_btc": 1.0 / 52.0,             # ~19.2 mHz - B2C2 institutional
    "galaxy_digital": 1.0 / 72.0,       # ~13.9 mHz - Galaxy slow accumulation
    
    # XRP/XRPL Specific
    "ripple_odl": 1.0 / 120.0,          # ~8.3 mHz - Ripple ODL corridor
    "ripple_escrow": 1.0 / 300.0,       # ~3.3 mHz - Monthly escrow releases
    "bitstamp_xrp": 1.0 / 25.0,         # ~40 mHz - Bitstamp XRP market making
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
        if len(self._vals) < 15:
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
        target_vals = fft_vals[start_idx:]
        if target_vals.size == 0:
            return 0.0, 0.0, "unknown", 0.0
        peak_idx_rel = int(np.argmax(target_vals))
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

    def tick(self, source_label: str = "zk_events") -> Dict[str, Union[float, str]]:
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
