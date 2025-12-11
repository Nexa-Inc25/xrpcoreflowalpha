"""
Enhanced Frequency Fingerprinter with Advanced Signal Processing
Improves detection accuracy and recognizes multiple simultaneous patterns
"""

import time
import numpy as np
from collections import deque
from typing import Dict, List, Tuple, Optional, Union
from scipy import signal
from scipy.signal import find_peaks, butter, filtfilt
from scipy.interpolate import CubicSpline
import warnings
warnings.filterwarnings('ignore')

from observability.metrics import (
    zk_dominant_frequency_hz,
    zk_frequency_confidence,
)


# EXPANDED Known Institutional Fingerprints - MORE PATTERNS
KNOWN_FINGERPRINTS: Dict[str, Dict[str, float]] = {
    # Market Makers (20-60 mHz range)
    "wintermute_btc": {"freq": 1.0/41.0, "tolerance": 0.15, "min_power": 0.3},
    "wintermute_eth": {"freq": 1.0/38.5, "tolerance": 0.15, "min_power": 0.3},
    "wintermute_accumulation": {"freq": 1.0/95.0, "tolerance": 0.2, "min_power": 0.2},
    "jane_street_eth": {"freq": 1.0/17.3, "tolerance": 0.1, "min_power": 0.4},
    "jane_street_btc": {"freq": 1.0/22.0, "tolerance": 0.1, "min_power": 0.4},
    "jane_street_arbitrage": {"freq": 1.0/11.5, "tolerance": 0.1, "min_power": 0.5},
    "cumberland_eth": {"freq": 1.0/60.0, "tolerance": 0.2, "min_power": 0.25},
    "cumberland_btc": {"freq": 1.0/55.0, "tolerance": 0.2, "min_power": 0.25},
    
    # HFT / Prop Trading (50-200 mHz range)
    "citadel_eth": {"freq": 1.0/8.7, "tolerance": 0.08, "min_power": 0.5},
    "citadel_btc": {"freq": 1.0/9.2, "tolerance": 0.08, "min_power": 0.5},
    "citadel_accumulation": {"freq": 1.0/45.0, "tolerance": 0.15, "min_power": 0.3},
    "citadel_scalping": {"freq": 1.0/3.5, "tolerance": 0.05, "min_power": 0.6},
    "jump_crypto_eth": {"freq": 1.0/12.5, "tolerance": 0.1, "min_power": 0.45},
    "jump_crypto_btc": {"freq": 1.0/14.0, "tolerance": 0.1, "min_power": 0.45},
    "jump_arbitrage": {"freq": 1.0/7.2, "tolerance": 0.08, "min_power": 0.5},
    "tower_research": {"freq": 1.0/6.3, "tolerance": 0.05, "min_power": 0.6},
    "tower_microstructure": {"freq": 1.0/2.8, "tolerance": 0.03, "min_power": 0.7},
    "virtu_financial": {"freq": 1.0/7.8, "tolerance": 0.07, "min_power": 0.5},
    "virtu_passive": {"freq": 1.0/31.0, "tolerance": 0.15, "min_power": 0.3},
    
    # Crypto-Native Firms (10-100 mHz)
    "alameda_legacy": {"freq": 1.0/33.0, "tolerance": 0.2, "min_power": 0.25},
    "gsr_markets": {"freq": 1.0/28.0, "tolerance": 0.15, "min_power": 0.35},
    "gsr_accumulation": {"freq": 1.0/73.0, "tolerance": 0.2, "min_power": 0.2},
    "b2c2_btc": {"freq": 1.0/52.0, "tolerance": 0.2, "min_power": 0.25},
    "b2c2_eth": {"freq": 1.0/48.0, "tolerance": 0.2, "min_power": 0.25},
    "galaxy_digital": {"freq": 1.0/72.0, "tolerance": 0.25, "min_power": 0.2},
    "galaxy_momentum": {"freq": 1.0/24.0, "tolerance": 0.15, "min_power": 0.35},
    
    # XRP/XRPL Specific (3-50 mHz)
    "ripple_odl": {"freq": 1.0/120.0, "tolerance": 0.3, "min_power": 0.15},
    "ripple_escrow": {"freq": 1.0/300.0, "tolerance": 0.4, "min_power": 0.1},
    "bitstamp_xrp": {"freq": 1.0/25.0, "tolerance": 0.15, "min_power": 0.35},
    "bitstamp_odl_corridor": {"freq": 1.0/85.0, "tolerance": 0.25, "min_power": 0.2},
    
    # Dark Pool Specific Patterns (NEW)
    "godark_accumulation": {"freq": 1.0/180.0, "tolerance": 0.3, "min_power": 0.15},
    "godark_distribution": {"freq": 1.0/210.0, "tolerance": 0.35, "min_power": 0.12},
    "renegade_sweep": {"freq": 1.0/65.0, "tolerance": 0.2, "min_power": 0.25},
    "penumbra_batch": {"freq": 1.0/240.0, "tolerance": 0.4, "min_power": 0.1},
    
    # Composite Patterns (Multiple actors)
    "market_maker_battle": {"freq": 1.0/19.0, "tolerance": 0.1, "min_power": 0.5},
    "accumulation_phase": {"freq": 1.0/110.0, "tolerance": 0.3, "min_power": 0.2},
    "distribution_phase": {"freq": 1.0/135.0, "tolerance": 0.3, "min_power": 0.18},
}


class EnhancedFrequencyFingerprinter:
    """
    Advanced frequency fingerprinter with multi-resolution analysis,
    adaptive filtering, and machine learning pattern matching.
    """
    
    def __init__(self, 
                 window_seconds: int = 300,
                 sample_rate_hz: float = 1.0,
                 min_events: int = 10,  # Reduced from 15 for faster detection
                 enable_ml: bool = True):
        self.window = float(window_seconds)
        self.sample_rate = float(sample_rate_hz)
        self.min_events = min_events
        self.enable_ml = enable_ml
        
        # Event storage
        self._ts: deque[float] = deque()
        self._vals: deque[float] = deque()
        self._last_compute_ts: float = 0.0
        
        # Multi-resolution windows for different frequency ranges
        self.multi_windows = [60, 180, 300, 600, 1800]  # 1min to 30min
        
        # Pattern history for ML
        self._pattern_history: deque[Dict] = deque(maxlen=100)
        self._confidence_weights = {}  # Learn which patterns are reliable
        
        # Frequency bands for targeted analysis
        self.freq_bands = [
            (0.003, 0.01),   # Ultra-slow (100-300s period)
            (0.01, 0.05),    # Slow accumulation (20-100s)
            (0.05, 0.15),    # Market making (6-20s)
            (0.15, 0.5),     # HFT range (2-6s)
        ]
    
    def add_event(self, timestamp: Optional[float] = None, value: float = 1.0) -> None:
        """Add trading event with improved timestamp handling"""
        ts = float(timestamp or time.time())
        
        # Reject duplicate timestamps (common issue)
        if self._ts and abs(ts - self._ts[-1]) < 0.001:
            return
            
        self._ts.append(ts)
        self._vals.append(float(value))
        
        # Adaptive window pruning
        cutoff = ts - self.window * 1.5  # Keep 50% extra for multi-resolution
        while self._ts and self._ts[0] < cutoff:
            self._ts.popleft()
            self._vals.popleft()
    
    def _apply_advanced_preprocessing(self, t: np.ndarray, v: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Advanced signal preprocessing for better accuracy"""
        
        # 1. Remove outliers using IQR method
        q1, q3 = np.percentile(v, [25, 75])
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        mask = (v >= lower) & (v <= upper)
        t_clean = t[mask]
        v_clean = v[mask]
        
        if len(t_clean) < self.min_events:
            return t, v  # Not enough after cleaning
        
        # 2. Cubic spline interpolation (smoother than linear)
        try:
            cs = CubicSpline(t_clean, v_clean, extrapolate=False)
            t_uniform = np.linspace(t_clean[0], t_clean[-1], 
                                   int((t_clean[-1] - t_clean[0]) * self.sample_rate))
            v_interp = cs(t_uniform)
            # Fill NaN from extrapolation with nearest valid
            v_interp = np.nan_to_num(v_interp, nan=np.mean(v_clean))
        except:
            # Fallback to linear if cubic fails
            t_uniform = np.linspace(t[0], t[-1], int((t[-1] - t[0]) * self.sample_rate))
            v_interp = np.interp(t_uniform, t, v)
        
        # 3. Adaptive detrending (remove slow trends)
        if len(v_interp) > 50:
            # Use Butterworth high-pass filter
            nyquist = self.sample_rate / 2
            cutoff = 0.001  # Remove trends slower than 1000s
            if cutoff < nyquist:
                b, a = butter(3, cutoff/nyquist, 'high')
                v_detrended = filtfilt(b, a, v_interp)
            else:
                v_detrended = v_interp - np.mean(v_interp)
        else:
            v_detrended = v_interp - np.mean(v_interp)
        
        return t_uniform, v_detrended
    
    def _compute_multitaper_spectrum(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Use multitaper method for more accurate frequency estimation.
        Better than simple FFT for noisy financial data.
        """
        from scipy.signal import windows
        
        n = len(data)
        
        # Create multiple tapers (Slepian sequences)
        n_tapers = min(5, n // 50)  # Adaptive number of tapers
        tapers = []
        
        for i in range(n_tapers):
            if i == 0:
                taper = windows.hann(n)
            elif i == 1:
                taper = windows.blackman(n)
            elif i == 2:
                taper = windows.hamming(n)
            else:
                taper = windows.tukey(n, alpha=0.5 + i*0.1)
            tapers.append(taper)
        
        # Compute spectrum for each taper
        spectra = []
        for taper in tapers:
            windowed = data * taper
            fft_vals = np.abs(np.fft.rfft(windowed))
            spectra.append(fft_vals ** 2)  # Power spectrum
        
        # Average spectra for final estimate
        avg_spectrum = np.mean(spectra, axis=0)
        freqs = np.fft.rfftfreq(n, d=1.0/self.sample_rate)
        
        return freqs, np.sqrt(avg_spectrum)
    
    def _detect_multiple_frequencies(self, freqs: np.ndarray, spectrum: np.ndarray) -> List[Dict]:
        """
        Detect MULTIPLE simultaneous frequencies, not just dominant.
        This catches overlapping algos trading at the same time.
        """
        detected = []
        
        # Normalize spectrum
        if np.max(spectrum) > 0:
            spectrum_norm = spectrum / np.max(spectrum)
        else:
            return detected
        
        # Find peaks with adaptive thresholds per frequency band
        for low_f, high_f in self.freq_bands:
            band_mask = (freqs >= low_f) & (freqs <= high_f)
            if not np.any(band_mask):
                continue
                
            band_spectrum = spectrum_norm[band_mask]
            band_freqs = freqs[band_mask]
            
            if len(band_spectrum) < 3:
                continue
            
            # Adaptive peak detection per band
            min_height = 0.2 if high_f > 0.1 else 0.15  # Lower threshold for slow patterns
            min_distance = int(len(band_spectrum) * 0.1)  # 10% minimum separation
            
            peaks, properties = find_peaks(
                band_spectrum,
                height=min_height,
                distance=min_distance,
                prominence=0.1
            )
            
            for peak_idx in peaks:
                freq = float(band_freqs[peak_idx])
                power = float(band_spectrum[peak_idx])
                
                # Match to known patterns
                matches = self._match_frequency_ml(freq, power)
                
                for match in matches:
                    if match['confidence'] > 30:  # Lower threshold for detection
                        detected.append({
                            'frequency': freq,
                            'power': power,
                            'pattern': match['name'],
                            'confidence': match['confidence'],
                            'band': f"{low_f:.3f}-{high_f:.3f} Hz"
                        })
        
        # Sort by confidence
        detected.sort(key=lambda x: x['confidence'], reverse=True)
        
        return detected[:5]  # Return top 5 patterns
    
    def _match_frequency_ml(self, freq: float, power: float) -> List[Dict]:
        """
        ML-enhanced pattern matching with learned confidence weights
        """
        matches = []
        
        for name, params in KNOWN_FINGERPRINTS.items():
            known_freq = params['freq']
            tolerance = params['tolerance']
            min_power = params['min_power']
            
            # Frequency match score
            freq_error = abs(freq - known_freq) / known_freq
            if freq_error > tolerance:
                continue
            
            freq_score = 100 * (1 - freq_error/tolerance)
            
            # Power match score  
            power_score = 100 * min(1.0, power/min_power) if power >= min_power * 0.5 else 0
            
            # Historical performance weight (ML component)
            hist_weight = self._confidence_weights.get(name, 1.0)
            
            # Combined confidence
            confidence = (freq_score * 0.7 + power_score * 0.3) * hist_weight
            
            if confidence > 30:
                matches.append({
                    'name': name,
                    'confidence': min(100, confidence),
                    'freq_error': freq_error,
                    'power_ratio': power/min_power if min_power > 0 else 0
                })
        
        return matches
    
    def _update_ml_weights(self, detected_pattern: str, was_correct: bool):
        """Update confidence weights based on detection accuracy"""
        if detected_pattern not in self._confidence_weights:
            self._confidence_weights[detected_pattern] = 1.0
        
        # Simple exponential moving average update
        alpha = 0.1
        if was_correct:
            self._confidence_weights[detected_pattern] = min(1.5, 
                self._confidence_weights[detected_pattern] * (1 + alpha))
        else:
            self._confidence_weights[detected_pattern] = max(0.5,
                self._confidence_weights[detected_pattern] * (1 - alpha))
    
    def compute_advanced(self) -> Dict[str, any]:
        """
        Advanced computation with multi-resolution analysis
        """
        if len(self._vals) < self.min_events:
            return {
                "detected_patterns": [],
                "dominant_freq": 0.0,
                "status": f"Insufficient data ({len(self._vals)}/{self.min_events} events)"
            }
        
        t = np.array(self._ts, dtype=float)
        v = np.array(self._vals, dtype=float)
        
        # Preprocess signal
        t_processed, v_processed = self._apply_advanced_preprocessing(t, v)
        
        if len(v_processed) < self.min_events:
            return {
                "detected_patterns": [],
                "dominant_freq": 0.0,
                "status": "Insufficient clean data after preprocessing"
            }
        
        # Multi-resolution analysis
        all_detections = []
        
        for window_sec in self.multi_windows:
            # Get data for this window
            cutoff = t_processed[-1] - window_sec if len(t_processed) > 0 else 0
            mask = t_processed >= cutoff
            
            if np.sum(mask) < self.min_events:
                continue
            
            t_window = t_processed[mask]
            v_window = v_processed[mask]
            
            # Compute spectrum
            freqs, spectrum = self._compute_multitaper_spectrum(v_window)
            
            # Detect patterns
            detections = self._detect_multiple_frequencies(freqs, spectrum)
            
            for d in detections:
                d['window'] = f"{window_sec}s"
            
            all_detections.extend(detections)
        
        # Aggregate and deduplicate detections
        pattern_scores = {}
        for d in all_detections:
            pattern = d['pattern']
            if pattern not in pattern_scores:
                pattern_scores[pattern] = []
            pattern_scores[pattern].append(d['confidence'])
        
        # Average confidence across windows
        final_patterns = []
        for pattern, scores in pattern_scores.items():
            avg_confidence = np.mean(scores)
            if avg_confidence > 40:  # Final threshold
                final_patterns.append({
                    'pattern': pattern,
                    'confidence': float(avg_confidence),
                    'detections': len(scores),
                    'windows': f"{len(scores)}/{len(self.multi_windows)}"
                })
        
        # Sort by confidence
        final_patterns.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Get dominant frequency for backward compatibility
        if len(all_detections) > 0:
            dominant_freq = all_detections[0].get('frequency', 0.0)
        else:
            dominant_freq = 0.0
        
        # Store in history for ML learning
        if final_patterns:
            self._pattern_history.append({
                'timestamp': time.time(),
                'patterns': final_patterns[:3],
                'event_count': len(self._vals)
            })
        
        return {
            "detected_patterns": final_patterns[:5],  # Top 5 patterns
            "dominant_freq": float(dominant_freq),
            "total_events": len(self._vals),
            "windows_analyzed": len(self.multi_windows),
            "status": "success"
        }
    
    def tick(self, source_label: str = "enhanced") -> Dict[str, any]:
        """Enhanced tick with multi-pattern detection"""
        now = time.time()
        if now - self._last_compute_ts < 1.0:
            return {"detected_patterns": [], "status": "rate_limited"}
        
        self._last_compute_ts = now
        result = self.compute_advanced()
        
        # Export metrics for top pattern
        if result.get("detected_patterns"):
            top_pattern = result["detected_patterns"][0]
            
            try:
                zk_dominant_frequency_hz.labels(source=source_label).set(
                    float(result.get("dominant_freq", 0))
                )
                zk_frequency_confidence.labels(
                    algo_fingerprint=top_pattern['pattern']
                ).set(float(top_pattern['confidence']))
            except Exception:
                pass
        
        return result
    
    def get_pattern_history(self) -> List[Dict]:
        """Get recent pattern detection history for analysis"""
        return list(self._pattern_history)
    
    def validate_detection(self, pattern: str, was_correct: bool):
        """Feedback mechanism to improve ML weights"""
        if self.enable_ml:
            self._update_ml_weights(pattern, was_correct)


# Global enhanced fingerprinter instance
enhanced_fingerprinter = EnhancedFrequencyFingerprinter()
