"""
Fourier Transform Analysis for Dark Flow Patterns
Frequency-domain analysis for multi-asset correlations
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from scipy import signal
from scipy.fft import fft, fftfreq, ifft
from scipy.signal import welch, find_peaks
import logging

logger = logging.getLogger(__name__)

class FourierFlowAnalyzer:
    """
    Fourier analysis for detecting periodic patterns in dark flows
    Optimized for crypto volatility cycles and correlation with traditional assets
    """
    
    def __init__(self, 
                 sampling_rate: float = 1.0,  # 1 sample per minute
                 window_size: int = 1440,      # 24 hours of minute data
                 overlap_ratio: float = 0.5):
        
        self.sampling_rate = sampling_rate
        self.window_size = window_size
        self.overlap_ratio = overlap_ratio
        
        # Frequency bands of interest (in cycles per day)
        self.frequency_bands = {
            'ultra_high': (100, 720),   # Sub-minute patterns
            'high': (24, 100),          # Hourly patterns  
            'medium': (4, 24),          # 4-6 hour cycles
            'low': (1, 4),              # Daily patterns
            'ultra_low': (0.1, 1)       # Multi-day cycles
        }
        
        # Harmonic detection parameters
        self.harmonic_threshold = 0.7  # Correlation threshold
        self.min_peak_prominence = 0.1
        
    def extract_frequency_features(self, data: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Extract frequency domain features using optimized FFT
        """
        features = {}
        
        # Apply Hann window to reduce spectral leakage
        window = signal.windows.hann(len(data))
        windowed_data = data * window
        
        # Compute FFT
        fft_values = fft(windowed_data)
        frequencies = fftfreq(len(data), 1/self.sampling_rate)
        
        # Get positive frequencies only
        positive_freq_idx = frequencies > 0
        frequencies = frequencies[positive_freq_idx]
        fft_magnitude = np.abs(fft_values[positive_freq_idx])
        
        # Extract power spectral density
        features['frequencies'] = frequencies
        features['magnitude'] = fft_magnitude
        features['phase'] = np.angle(fft_values[positive_freq_idx])
        
        # Power spectral density using Welch's method
        freqs_welch, psd = welch(
            data,
            fs=self.sampling_rate,
            window='hann',
            nperseg=min(256, len(data)),
            noverlap=128
        )
        features['psd_frequencies'] = freqs_welch
        features['psd'] = psd
        
        # Dominant frequencies
        features['dominant_freqs'] = self._find_dominant_frequencies(
            frequencies, fft_magnitude
        )
        
        # Band power features
        features['band_powers'] = self._calculate_band_powers(
            frequencies, fft_magnitude
        )
        
        # Spectral entropy (measure of complexity)
        features['spectral_entropy'] = self._calculate_spectral_entropy(psd)
        
        return features
    
    def detect_harmonic_patterns(self, 
                                  data: np.ndarray,
                                  fundamental_freq: Optional[float] = None) -> Dict:
        """
        Detect harmonic patterns indicating coordinated dark pool activity
        """
        features = self.extract_frequency_features(data)
        frequencies = features['frequencies']
        magnitude = features['magnitude']
        
        # Find fundamental frequency if not provided
        if fundamental_freq is None:
            peaks, properties = find_peaks(
                magnitude,
                prominence=magnitude.max() * self.min_peak_prominence
            )
            if len(peaks) > 0:
                fundamental_idx = peaks[np.argmax(properties['prominences'])]
                fundamental_freq = frequencies[fundamental_idx]
            else:
                return {'harmonics': [], 'harmonic_score': 0.0}
        
        # Detect harmonics
        harmonics = []
        for n in range(2, 11):  # Check up to 10th harmonic
            harmonic_freq = fundamental_freq * n
            
            # Find closest frequency in spectrum
            idx = np.argmin(np.abs(frequencies - harmonic_freq))
            
            if idx < len(magnitude):
                # Check if there's significant power at this harmonic
                local_max_idx = self._find_local_maximum(magnitude, idx, window=5)
                
                if local_max_idx is not None:
                    harmonic_power = magnitude[local_max_idx]
                    fundamental_power = magnitude[np.argmin(np.abs(frequencies - fundamental_freq))]
                    
                    if harmonic_power > fundamental_power * 0.1:  # At least 10% of fundamental
                        harmonics.append({
                            'order': n,
                            'frequency': frequencies[local_max_idx],
                            'expected_frequency': harmonic_freq,
                            'power': float(harmonic_power),
                            'power_ratio': float(harmonic_power / fundamental_power)
                        })
        
        # Calculate harmonic score (indicates coordination)
        harmonic_score = len(harmonics) / 9.0  # Normalize by max possible harmonics
        
        # Boost score if harmonics are well-aligned
        if harmonics:
            freq_errors = [
                abs(h['frequency'] - h['expected_frequency']) / h['expected_frequency']
                for h in harmonics
            ]
            alignment_score = 1.0 - np.mean(freq_errors)
            harmonic_score = (harmonic_score + alignment_score) / 2
        
        return {
            'fundamental_frequency': float(fundamental_freq) if fundamental_freq else 0.0,
            'harmonics': harmonics,
            'harmonic_score': float(harmonic_score),
            'coordination_detected': harmonic_score > 0.5
        }
    
    def cross_asset_frequency_correlation(self,
                                           asset1_data: np.ndarray,
                                           asset2_data: np.ndarray) -> Dict:
        """
        Calculate frequency-domain correlation between assets
        Critical for detecting ETH/BTC manipulation affecting XRP
        """
        # Extract frequency features for both assets
        features1 = self.extract_frequency_features(asset1_data)
        features2 = self.extract_frequency_features(asset2_data)
        
        # Ensure same frequency bins
        min_len = min(len(features1['magnitude']), len(features2['magnitude']))
        mag1 = features1['magnitude'][:min_len]
        mag2 = features2['magnitude'][:min_len]
        phase1 = features1['phase'][:min_len]
        phase2 = features2['phase'][:min_len]
        freqs = features1['frequencies'][:min_len]
        
        # Magnitude correlation
        mag_correlation = np.corrcoef(mag1, mag2)[0, 1]
        
        # Phase coherence (important for synchronized movements)
        phase_diff = np.abs(phase1 - phase2)
        phase_coherence = np.mean(np.cos(phase_diff))
        
        # Frequency-specific correlations
        band_correlations = {}
        for band_name, (low_freq, high_freq) in self.frequency_bands.items():
            band_mask = (freqs >= low_freq) & (freqs <= high_freq)
            if np.any(band_mask):
                band_corr = np.corrcoef(mag1[band_mask], mag2[band_mask])[0, 1]
                band_correlations[band_name] = float(band_corr) if not np.isnan(band_corr) else 0.0
        
        # Cross-spectrum analysis
        cross_spectrum = mag1 * mag2 * np.exp(1j * (phase1 - phase2))
        coherence = np.abs(cross_spectrum) / (mag1 * mag2 + 1e-10)
        
        # Find frequencies with high coherence (potential manipulation points)
        high_coherence_mask = coherence > 0.8
        manipulation_frequencies = freqs[high_coherence_mask].tolist()
        
        return {
            'magnitude_correlation': float(mag_correlation) if not np.isnan(mag_correlation) else 0.0,
            'phase_coherence': float(phase_coherence),
            'band_correlations': band_correlations,
            'mean_coherence': float(np.mean(coherence)),
            'manipulation_frequencies': manipulation_frequencies,
            'synchronized': phase_coherence > 0.7 and mag_correlation > 0.6
        }
    
    def decompose_multi_timescale_patterns(self, data: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Decompose signal into multiple timescales using wavelet-like approach
        Essential for identifying patterns at different time horizons
        """
        decomposed = {}
        
        # Design filters for different timescales
        filters = {
            'micro': (720, None),     # < 2 minutes (HFT)
            'short': (60, 720),       # 2 min - 1 hour
            'medium': (12, 60),       # 1 - 5 hours  
            'long': (2, 12),          # 5 - 24 hours
            'macro': (None, 2)        # > 24 hours
        }
        
        nyquist = self.sampling_rate / 2
        
        for scale_name, (low_cut, high_cut) in filters.items():
            if low_cut is None:
                # Low-pass filter
                sos = signal.butter(4, high_cut/nyquist, btype='low', output='sos')
            elif high_cut is None:
                # High-pass filter
                sos = signal.butter(4, low_cut/nyquist, btype='high', output='sos')
            else:
                # Band-pass filter
                sos = signal.butter(4, [low_cut/nyquist, high_cut/nyquist], 
                                    btype='band', output='sos')
            
            filtered = signal.sosfiltfilt(sos, data)
            decomposed[scale_name] = filtered
        
        return decomposed
    
    def predict_volatility_cycles(self, data: np.ndarray, forecast_periods: int = 100) -> Dict:
        """
        Predict future volatility cycles using Fourier extrapolation
        """
        features = self.extract_frequency_features(data)
        
        # Get dominant frequencies
        dominant_freqs = features['dominant_freqs'][:5]  # Top 5 frequencies
        
        # Reconstruct signal using dominant frequencies
        t = np.arange(len(data))
        t_future = np.arange(len(data), len(data) + forecast_periods)
        
        # FFT of original data
        fft_values = fft(data)
        frequencies = fftfreq(len(data), 1/self.sampling_rate)
        
        # Keep only dominant frequency components
        fft_filtered = np.zeros_like(fft_values)
        for freq in dominant_freqs:
            idx = np.argmin(np.abs(frequencies - freq['frequency']))
            window = 3  # Keep nearby frequencies
            fft_filtered[max(0, idx-window):min(len(fft_filtered), idx+window+1)] = \
                fft_values[max(0, idx-window):min(len(fft_values), idx+window+1)]
        
        # Inverse FFT for filtered signal
        filtered_signal = np.real(ifft(fft_filtered))
        
        # Extrapolate using dominant frequencies
        prediction = np.zeros(forecast_periods)
        for freq_info in dominant_freqs:
            freq = freq_info['frequency']
            amp = freq_info['amplitude']
            phase = freq_info['phase']
            
            prediction += amp * np.sin(2 * np.pi * freq * t_future / self.sampling_rate + phase)
        
        # Calculate prediction confidence based on how well dominant frequencies explain variance
        explained_variance = np.var(filtered_signal) / np.var(data)
        
        return {
            'prediction': prediction,
            'confidence': float(explained_variance),
            'dominant_periods': [self.sampling_rate / f['frequency'] for f in dominant_freqs],
            'next_peak_time': self._find_next_peak_time(prediction),
            'next_trough_time': self._find_next_trough_time(prediction)
        }
    
    def _find_dominant_frequencies(self, frequencies: np.ndarray, 
                                    magnitude: np.ndarray, 
                                    n_dominant: int = 10) -> List[Dict]:
        """Find dominant frequencies in spectrum"""
        # Find peaks
        peaks, properties = find_peaks(
            magnitude,
            prominence=magnitude.max() * self.min_peak_prominence,
            distance=5
        )
        
        if len(peaks) == 0:
            return []
        
        # Sort by prominence
        sorted_idx = np.argsort(properties['prominences'])[::-1]
        top_peaks = peaks[sorted_idx[:n_dominant]]
        
        dominant = []
        for peak_idx in top_peaks:
            dominant.append({
                'frequency': float(frequencies[peak_idx]),
                'amplitude': float(magnitude[peak_idx]),
                'phase': float(np.angle(fft(magnitude)[peak_idx])),
                'period': float(1.0 / frequencies[peak_idx]) if frequencies[peak_idx] > 0 else np.inf,
                'prominence': float(properties['prominences'][sorted_idx[len(dominant)]])
            })
        
        return dominant
    
    def _calculate_band_powers(self, frequencies: np.ndarray, 
                                magnitude: np.ndarray) -> Dict[str, float]:
        """Calculate power in frequency bands"""
        band_powers = {}
        
        for band_name, (low_freq, high_freq) in self.frequency_bands.items():
            band_mask = (frequencies >= low_freq) & (frequencies <= high_freq)
            if np.any(band_mask):
                power = np.sum(magnitude[band_mask] ** 2)
                band_powers[band_name] = float(power)
            else:
                band_powers[band_name] = 0.0
        
        # Normalize by total power
        total_power = sum(band_powers.values())
        if total_power > 0:
            band_powers = {k: v/total_power for k, v in band_powers.items()}
        
        return band_powers
    
    def _calculate_spectral_entropy(self, psd: np.ndarray) -> float:
        """Calculate spectral entropy as measure of signal complexity"""
        # Normalize PSD to get probability distribution
        psd_norm = psd / np.sum(psd)
        
        # Calculate entropy
        entropy = -np.sum(psd_norm * np.log2(psd_norm + 1e-10))
        
        # Normalize by maximum possible entropy
        max_entropy = np.log2(len(psd))
        
        return float(entropy / max_entropy) if max_entropy > 0 else 0.0
    
    def _find_local_maximum(self, data: np.ndarray, center: int, window: int) -> Optional[int]:
        """Find local maximum around a center point"""
        start = max(0, center - window)
        end = min(len(data), center + window + 1)
        
        if start >= end:
            return None
        
        local_data = data[start:end]
        local_max_idx = np.argmax(local_data)
        
        # Check if it's actually a peak
        if local_max_idx == 0 or local_max_idx == len(local_data) - 1:
            return None
        
        return start + local_max_idx
    
    def _find_next_peak_time(self, prediction: np.ndarray) -> int:
        """Find time of next peak in prediction"""
        peaks, _ = find_peaks(prediction)
        return int(peaks[0]) if len(peaks) > 0 else -1
    
    def _find_next_trough_time(self, prediction: np.ndarray) -> int:
        """Find time of next trough in prediction"""
        troughs, _ = find_peaks(-prediction)
        return int(troughs[0]) if len(troughs) > 0 else -1


class FourierNeuralIntegrator:
    """
    Integrates Fourier features with neural networks for enhanced prediction
    """
    
    def __init__(self, fourier_analyzer: FourierFlowAnalyzer):
        self.fourier = fourier_analyzer
        self.feature_cache = {}
        
    def prepare_neural_features(self, data: pd.DataFrame) -> np.ndarray:
        """
        Prepare Fourier-transformed features for neural network input
        """
        # Extract price data
        prices = data['close'].values
        volumes = data['volume'].values
        
        # Get Fourier features
        price_features = self.fourier.extract_frequency_features(prices)
        volume_features = self.fourier.extract_frequency_features(volumes)
        
        # Decompose into timescales
        price_decomposed = self.fourier.decompose_multi_timescale_patterns(prices)
        volume_decomposed = self.fourier.decompose_multi_timescale_patterns(volumes)
        
        # Combine features
        neural_features = []
        
        # Add band powers
        for band_name, power in price_features['band_powers'].items():
            neural_features.append(power)
        
        for band_name, power in volume_features['band_powers'].items():
            neural_features.append(power)
        
        # Add spectral entropy
        neural_features.append(price_features['spectral_entropy'])
        neural_features.append(volume_features['spectral_entropy'])
        
        # Add decomposed signal statistics
        for scale_name, signal in price_decomposed.items():
            neural_features.extend([
                np.mean(signal),
                np.std(signal),
                np.max(signal) - np.min(signal)
            ])
        
        return np.array(neural_features)
    
    def detect_dark_pool_signature(self, data: pd.DataFrame) -> Dict:
        """
        Detect frequency signatures characteristic of dark pool activity
        """
        prices = data['close'].values
        volumes = data['volume'].values
        
        # Analyze price-volume frequency correlation
        correlation_analysis = self.fourier.cross_asset_frequency_correlation(
            prices, volumes
        )
        
        # Look for harmonic patterns (coordinated trading)
        harmonic_analysis = self.fourier.detect_harmonic_patterns(volumes)
        
        # Volatility cycle prediction
        volatility = data['close'].pct_change().rolling(20).std().values
        volatility_clean = volatility[~np.isnan(volatility)]
        cycle_prediction = self.fourier.predict_volatility_cycles(volatility_clean)
        
        # Dark pool signature scoring
        signature_score = 0.0
        
        # High price-volume coherence at specific frequencies
        if correlation_analysis['phase_coherence'] > 0.8:
            signature_score += 0.3
        
        # Presence of harmonics in volume (algorithmic trading)
        if harmonic_analysis['coordination_detected']:
            signature_score += 0.3
        
        # Predictable volatility cycles
        if cycle_prediction['confidence'] > 0.7:
            signature_score += 0.2
        
        # Abnormal frequency distribution
        price_features = self.fourier.extract_frequency_features(prices)
        if price_features['spectral_entropy'] < 0.5:  # Low entropy = structured
            signature_score += 0.2
        
        return {
            'dark_pool_probability': min(signature_score, 1.0),
            'price_volume_coherence': correlation_analysis['phase_coherence'],
            'algorithmic_trading_detected': harmonic_analysis['coordination_detected'],
            'volatility_predictability': cycle_prediction['confidence'],
            'next_volatility_spike': cycle_prediction['next_peak_time'],
            'manipulation_frequencies': correlation_analysis['manipulation_frequencies']
        }
