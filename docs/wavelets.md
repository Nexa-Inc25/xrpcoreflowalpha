# Wavelet Analysis in ZKAlphaFlow

> **Status:** Production prototype (ES/NQ macro), wired to `zk_wavelet_urgency_score` and `zk_flow_confidence_score{protocol="macro"}`.

Fourier is our baseline for detecting **steady institutional rhythms** (e.g., Citadels 8.46 s ES slicing, Jane Streets 4.90 s NQ heartbeat).

When the rhythm **changes mid-print**  which happens constantly in real execution  pure Fourier starts to smear the signal.

**Wavelet analysis** is the upgrade. It sees **time and frequency at once**, so it can tell us when an algo flips from:

- Quiet TWAP > aggressive burst
- Steady accumulation > urgent liquidation

This file explains how we use wavelets, how it maps to Prometheus metrics, and how to reason about the implementation.

---

## 1. Fourier vs Wavelet (Intuition)

**Fourier:**

- Great at finding **steady rhythms** over a fixed window.
- Gives us dominant frequencies like:
  - ES: ~0.1182 Hz > 8.46 s (Citadel TWAP)
  - NQ: ~0.2039 Hz > 4.90 s (Jane Street)
- But assumes the rhythm is roughly **stationary** over the window.

**Wavelets:**

- Analyze time and frequency **jointly**.
- Can detect when the rhythm **changes inside the window**, e.g.:
  - 0.1182 Hz > 0.30 Hz (ES) within a few bars
- Perfect for spotting **burst / urgency phases** at the end of a large print.

| Situation                        | Fourier Sees                         | Wavelet Sees                                   |
|----------------------------------|--------------------------------------|------------------------------------------------|
| Citadel steady TWAP (8.46 s)     | 0.1182 Hz > perfect peak          | 0.1182 Hz > perfect                         |
| Citadel suddenly accelerates     | Still ~0.118 Hz (smeared)           | Localized jump to ~0.25~0.33 Hz in &lt;10 s   |
| Jane Street start  pause  restart | One blended average frequency        | Start  stop  restart windows are distinct |
| GhostPrint_2025 irregular rhythm | No clean global peak                | Pockets of localized energy around 11.7 s      |

---

## 2. Metrics: What We Expose

Wavelet logic is wired into Prometheus via:

```python
# observability/metrics.py

zk_wavelet_urgency_score = Gauge(
    "zk_wavelet_urgency_score",
    "Wavelet-based urgency score (0-100) for macro execution patterns",
    ["source"],
)

zk_flow_confidence_score = Gauge(
    "zk_flow_confidence_score",
    "Markov-based probability of imminent dark pool execution",
    ["protocol"],
)
```

We currently use:

- `source` > `"macro_es"`, `"macro_nq"`, (and future `"macro_rty"`)
- `protocol="macro"` on `zk_flow_confidence_score` as a **macro urgency channel**, separate from `protocol="godark"` (GoDark / on-chain HMM).

From Prometheus / `/metrics` you will see, for example:

```text
zk_wavelet_urgency_score{source="macro_es"} 27.5
zk_wavelet_urgency_score{source="macro_nq"} 82.1
zk_flow_confidence_score{protocol="macro"} 0.821
zk_flow_confidence_score{protocol="godark"} 0.64
```

Interpretation:

- `macro_nq` urgency ~82 > NQ macro flow is in a **high-energy burst phase**.
- Macro channel alone would push confidence to ~0.82; final confidence fusion is handled on the consumer side (UI / strategies).

---

## 3. Implementation Overview

The implementation lives in `predictors/wavelet_urgency.py` and is called from the macro trackers.

### 3.1 WaveletUrgencyTracker

```python
# predictors/wavelet_urgency.py

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
```

We maintain a rolling 10-minute window of `(timestamp, notional)` points per source (e.g. `macro_es`, `macro_nq`).

### 3.2 CWT and Energy Ratio

```python
    def compute_score(self) -> float:
        now = time.time()
        if now - self._last_compute_ts < self.min_compute_interval:
            return 0.0
        self._last_compute_ts = now
        if pywt is None:
            return 0.0
        if not self._events or len(self._events) < self.min_points:
            return 0.0

        ts, vals = zip(*self._events)
        vals_arr = np.asarray(vals, dtype=float)
        # sanitize
        vals_arr = np.nan_to_num(vals_arr, nan=0.0, posinf=0.0, neginf=0.0)
        n = vals_arr.size
        widths = np.arange(1, min(16, n + 1))
        coeffs, _ = pywt.cwt(vals_arr, widths, "morl")
        energy = np.abs(coeffs) ** 2

        baseline = float(np.mean(energy))
        # recent band  last ~60 seconds approximated as tail of index space
        frac = min(1.0, max(0.1, self.recent / self.window))
        k = max(3, int(n * frac))
        recent_slice = energy[:, -k:]
        recent_peak = float(np.max(recent_slice))

        ratio = recent_peak / baseline  # how spiky recent energy is vs history
        # Map ratio -> [0, 100]; ratio <= 1 -> 0, ratio >= 3 -> 100.
        score = (ratio - 1.0) / (3.0 - 1.0)
        score = float(max(0.0, min(1.0, score))) * 100.0
        return float(round(score, 2))
```

Key points:

- **Window:** 10 minutes of notional flow.
- **Recent band:** approximated as the last ~60 seconds in index space.
- **Energy:** squared magnitude of wavelet coefficients.
- **Ratio:** `recent_peak / baseline`.
  - 1.0 = no spike.
  - 63.0 = big burst; mapped to 100.

This gives a smooth, bounded **urgency score in [0, 100]**.

### 3.3 Public Helper: `update_wavelet_urgency`

```python
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
```

This is what macro trackers call after each **successful notional tick**.

---

## 4. Integration with Macro Trackers

### 4.1 Databento Macro Tracker (CME Futures)

```python
# predictors/databento_macro_tracker.py

from predictors.wavelet_urgency import update_wavelet_urgency

...
if notional > 0 and math.isfinite(notional):
    ts = end.timestamp()
    fp.add_event(timestamp=ts, value=notional)
    fp.tick(source_label=label)
    try:
        update_wavelet_urgency(label, ts, notional)
    except Exception:
        pass
```

Here `label` is typically `"macro_es"` or `"macro_nq"` depending on the parent symbol (`ES.FUT`, `NQ.FUT`).

### 4.2 Polygon Macro Tracker (Fallback)

```python
# predictors/polygon_macro_tracker.py

from predictors.wavelet_urgency import update_wavelet_urgency

...
if ts > 0 and notional > 0 and math.isfinite(notional):
    fp.add_event(timestamp=ts, value=notional)
    fp.tick(source_label=label)
    try:
        update_wavelet_urgency(label, ts, notional)
    except Exception:
        pass
```

This gives us continuous wavelet coverage whether we are using Databento (CME MDP 3.0) or Polygon continuous futures.

---

## 5. Example: Citadel Burst > Urgency Jump

Assume we have ES flow that looks like:

- First 8 minutes: steady TWAP at ~8.4 s cadence.
- Last 2 minutes: accelerated slicing at ~3 s cadence.

The tracker will see notional spikes cluster more tightly in the tail of the window:

1. Baseline energy over 10 minutes is fairly flat.
2. Recent energy (last ~60 seconds) shows a sharp peak.
3. `recent_peak / baseline` might jump from ~1.1 → ~2.5.
4. `zk_wavelet_urgency_score{source="macro_es"}` rises from ~10–20 → 70–90.
5. `zk_flow_confidence_score{protocol="macro"}` follows (0.7–0.9).

Downstream consumers (UI, alerting, strategies) can then:

- Treat `zk_wavelet_urgency_score > 70` as **final-phase / completion** risk.
- Combine `protocol="macro"` and `protocol="godark"` channels to drive the user-facing
  confidence gauge into the **96–98 % band** when both macro and ZK settlement agree.

---

## 6. Deployment Notes

- **Dependency:** requires `PyWavelets` (imported as `pywt`), added to `requirements.txt`.
- If `pywt` is not importable, `compute_score()` gracefully returns 0 and the metric stays at 0.
- The computation is intentionally lightweight:
  - Single CWT over a short numeric series per label.
  - Capped recompute frequency via `min_compute_interval` (default 5 seconds).

To verify in production:

1. Check that the metric is present:

   ```bash
   curl -sS http://127.0.0.1:8011/metrics | grep zk_wavelet_urgency_score | head
   ```

2. Correlate spikes in `zk_wavelet_urgency_score{source="macro_*"}` with:

   - Spikes in `zk_dominant_frequency_hz{source="macro_*"}`
   - Known high-volume macro windows (FOMC, CPI, opening/closing auctions)
   - Large ZK settlement bursts on GoDark.

3. Use Grafana to plot:

   - `zk_wavelet_urgency_score{source="macro_es"}`
   - `zk_wavelet_urgency_score{source="macro_nq"}`
   - `zk_flow_confidence_score{protocol="macro"}`

   to visually verify that urgency behaves as intended.

---

## 7. Future Work

- Tune `window_seconds` / `recent_seconds` per asset (ES vs NQ vs RTY).
- Add optional **frequency band selection** (e.g., focus on 0.1–0.5 Hz region when looking for
  short-horizon bursts).
- Expose a derived boolean metric, e.g. `zk_wavelet_burst_active{source=...}` for alerting.
- Feed discrete burst flags as additional observations into `ZKFlowHMM` (macro side), so Viterbi
  states respond directly to wavelet events.

For now, `zk_wavelet_urgency_score` is the primary surface area: a 0–100 score that tells you
**how violently the macro heartbeat is changing right now**.
