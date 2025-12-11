"""
ULTRA-HARDENED FINGERPRINTER - PART 2
Additional methods for the UltraHardenedFingerprinter class
"""

# Add these methods to the UltraHardenedFingerprinter class:

    def _detect_spoofing_attempt(self, t: np.ndarray, v: np.ndarray, 
                                 detected_patterns: List[Dict]) -> bool:
        """
        Detect potential spoofing using multiple indicators:
        1. Too perfect periodicity (real trading has jitter)
        2. Missing harmonics that should be present
        3. Unusual amplitude distribution
        4. Anomaly detection on feature vector
        """
        if not self.enable_anti_spoof:
            return False
        
        indicators = []
        
        # 1. Check periodicity perfection (real algos have 2-5% jitter)
        if len(t) > 50:
            intervals = np.diff(t)
            if len(intervals) > 0:
                cv = np.std(intervals) / np.mean(intervals)  # Coefficient of variation
                if cv < 0.01:  # Less than 1% variation is suspicious
                    indicators.append('too_perfect')
        
        # 2. Check for missing expected harmonics (handled in _validate_harmonics)
        
        # 3. Check amplitude distribution
        if len(v) > 30:
            # Real trading has log-normal or power-law distribution
            log_v = np.log(v + 1e-10)
            skewness = stats.skew(log_v)
            kurtosis = stats.kurtosis(log_v)
            
            # Normal distribution would have skew ~0, kurtosis ~3
            if abs(skewness) < 0.1 and abs(kurtosis - 3) < 0.5:
                indicators.append('artificial_distribution')
        
        # 4. Anomaly detection using Isolation Forest
        if self.anomaly_detector and SKLEARN_AVAILABLE and len(v) > 20:
            # Extract features
            features = []
            features.append(np.mean(v))
            features.append(np.std(v))
            features.append(stats.skew(v))
            features.append(stats.kurtosis(v))
            features.append(np.percentile(v, 95) / np.percentile(v, 50))  # Tail ratio
            features.append(len(find_peaks(v)[0]) / len(v))  # Peak density
            
            features = np.array(features).reshape(1, -1)
            
            if self._anomaly_trained:
                features_scaled = self.scaler.transform(features)
                anomaly_score = self.anomaly_detector.decision_function(features_scaled)[0]
                if anomaly_score < -0.1:  # Anomaly threshold
                    indicators.append('anomaly_detected')
            else:
                # Train the model if we have enough history
                if len(self.validation_history) > 100:
                    historical_features = []
                    for h in self.validation_history[-100:]:
                        if 'features' in h:
                            historical_features.append(h['features'])
                    
                    if len(historical_features) > 50:
                        historical_features = np.array(historical_features)
                        self.scaler.fit(historical_features)
                        self.anomaly_detector.fit(self.scaler.transform(historical_features))
                        self._anomaly_trained = True
        
        # 5. Check for synthetic patterns (too many detected at once)
        if len(detected_patterns) > 7:  # Unusual to have 7+ algos at once
            indicators.append('too_many_patterns')
        
        # Decision
        is_spoofing = len(indicators) >= 2  # Need multiple indicators
        
        if is_spoofing:
            self.metrics['spoofing_attempts'] += 1
            print(f"[ANTI-SPOOF] Potential spoofing detected: {indicators}")
        
        return is_spoofing
    
    def _apply_drift_compensation(self, freq: float, pattern_name: str) -> float:
        """
        Compensate for frequency drift over time.
        Market conditions change, algos adapt - we need to track this.
        """
        if not self.enable_drift_compensation:
            return freq
        
        if pattern_name not in self.baseline_frequencies:
            self.baseline_frequencies[pattern_name] = freq
            self.drift_factors[pattern_name] = 1.0
            return freq
        
        # Get Kalman filtered frequency
        if pattern_name not in self.freq_trackers:
            self.freq_trackers[pattern_name] = KalmanFilter()
        
        filtered_freq = self.freq_trackers[pattern_name].update(freq)
        
        # Calculate drift
        baseline = self.baseline_frequencies[pattern_name]
        drift_ratio = filtered_freq / baseline
        
        # Update drift factor (exponential moving average)
        alpha = 0.05  # Adaptation rate
        self.drift_factors[pattern_name] = (1 - alpha) * self.drift_factors[pattern_name] + alpha * drift_ratio
        
        # Apply compensation
        compensated_freq = freq / self.drift_factors[pattern_name]
        
        return compensated_freq
    
    def _advanced_preprocessing(self, t: np.ndarray, v: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Advanced preprocessing with outlier removal and adaptive filtering"""
        
        # 1. Remove outliers using RANSAC-style approach
        z_scores = np.abs(stats.zscore(v))
        mask = z_scores < 3  # Keep within 3 standard deviations
        t_clean = t[mask]
        v_clean = v[mask]
        
        if len(t_clean) < self.min_events:
            return t, v
        
        # 2. Adaptive resampling with edge preservation
        target_samples = int((t_clean[-1] - t_clean[0]) * self.sample_rate)
        if target_samples < len(t_clean):
            target_samples = len(t_clean)
        
        t_uniform = np.linspace(t_clean[0], t_clean[-1], target_samples)
        
        # Use PCHIP interpolation (preserves monotonicity better than cubic)
        try:
            interp = PchipInterpolator(t_clean, v_clean)
            v_resampled = interp(t_uniform)
        except:
            v_resampled = np.interp(t_uniform, t_clean, v_clean)
        
        # 3. Advanced detrending with Savitzky-Golay filter
        if len(v_resampled) > 51:
            from scipy.signal import savgol_filter
            window = min(51, len(v_resampled) // 2 * 2 - 1)  # Ensure odd window
            trend = savgol_filter(v_resampled, window, 3)
            v_detrended = v_resampled - trend
        else:
            v_detrended = v_resampled - np.mean(v_resampled)
        
        # 4. Adaptive noise filtering
        # Estimate noise level using Median Absolute Deviation
        mad = np.median(np.abs(v_detrended - np.median(v_detrended)))
        noise_threshold = 1.4826 * mad  # Scale factor for normal distribution
        
        # Apply soft thresholding (wavelet denoising style)
        v_filtered = np.sign(v_detrended) * np.maximum(np.abs(v_detrended) - noise_threshold, 0)
        
        return t_uniform, v_filtered
    
    def _extract_features(self, v: np.ndarray) -> List[float]:
        """Extract statistical features for ML validation"""
        features = []
        
        # Basic statistics
        features.append(np.mean(v))
        features.append(np.std(v))
        features.append(stats.skew(v))
        features.append(stats.kurtosis(v))
        
        # Percentiles
        features.append(np.percentile(v, 25))
        features.append(np.percentile(v, 50))
        features.append(np.percentile(v, 75))
        features.append(np.percentile(v, 95))
        
        # Ratios
        if np.percentile(v, 50) > 0:
            features.append(np.percentile(v, 95) / np.percentile(v, 50))
        else:
            features.append(0)
        
        # Peak statistics
        peaks, _ = find_peaks(v)
        features.append(len(peaks) / len(v))  # Peak density
        
        # Autocorrelation at lag 1
        if len(v) > 1:
            autocorr = np.corrcoef(v[:-1], v[1:])[0, 1]
            features.append(autocorr)
        else:
            features.append(0)
        
        return features
    
    def _combine_ensemble_results(self, ensemble_results: Dict) -> List[Dict]:
        """
        Combine results from multiple spectrum analysis methods
        using weighted voting based on method reliability
        """
        combined = {}
        
        # Method weights based on empirical performance
        weights = {
            'welch': 0.3,      # Good noise reduction
            'multitaper': 0.35, # Best frequency resolution
            'music': 0.25,      # Super-resolution but sensitive
            'autocorr': 0.1     # Direct period detection
        }
        
        # Collect all detected frequencies from all methods
        all_detections = []
        
        for method, result in ensemble_results.items():
            if result is None:
                continue
            
            weight = weights.get(method, 0.1)
            
            if method == 'autocorr' and result:
                # Autocorrelation gives direct frequencies
                for freq in result.get('freqs', []):
                    all_detections.append({
                        'frequency': freq,
                        'confidence': weight * 100,
                        'method': method
                    })
            elif 'freqs' in result and 'psd' in result:
                # Find peaks in spectrum
                freqs = result['freqs']
                spectrum = result['psd'] if method == 'welch' else result.get('spectrum', result['psd'])
                
                # Normalize spectrum
                if np.max(spectrum) > 0:
                    spectrum = spectrum / np.max(spectrum)
                
                # Find peaks
                peaks, properties = find_peaks(spectrum, height=0.1, distance=5)
                
                for peak_idx in peaks[:10]:  # Top 10 peaks per method
                    if peak_idx < len(freqs):
                        all_detections.append({
                            'frequency': freqs[peak_idx],
                            'confidence': weight * spectrum[peak_idx] * 100,
                            'method': method,
                            'spectrum': spectrum,
                            'freqs': freqs
                        })
        
        # Group detections by similar frequencies (within 5% tolerance)
        grouped = []
        for det in all_detections:
            freq = det['frequency']
            found_group = False
            
            for group in grouped:
                group_freq = group['frequency']
                if abs(freq - group_freq) / group_freq < 0.05:  # 5% tolerance
                    # Add to existing group
                    group['detections'].append(det)
                    group['total_confidence'] += det['confidence']
                    found_group = True
                    break
            
            if not found_group:
                # Create new group
                grouped.append({
                    'frequency': freq,
                    'detections': [det],
                    'total_confidence': det['confidence']
                })
        
        # Sort by total confidence
        grouped.sort(key=lambda x: x['total_confidence'], reverse=True)
        
        # Match to known patterns
        final_detections = []
        for group in grouped[:10]:  # Top 10 frequency groups
            freq = group['frequency']
            confidence = group['total_confidence']
            
            # Find best matching pattern
            best_pattern = None
            best_error = float('inf')
            
            for name, signature in self.pattern_signatures.items():
                error = abs(freq - signature.primary_freq) / signature.primary_freq
                if error < 0.1 and error < best_error:  # 10% tolerance
                    best_error = error
                    best_pattern = name
            
            if best_pattern:
                # Get spectrum from best method detection
                spectrum_data = None
                freqs_data = None
                for det in group['detections']:
                    if 'spectrum' in det:
                        spectrum_data = det['spectrum']
                        freqs_data = det['freqs']
                        break
                
                final_detections.append({
                    'pattern': best_pattern,
                    'frequency': freq,
                    'confidence': min(100, confidence),
                    'methods_detected': len(group['detections']),
                    'spectrum': spectrum_data,
                    'freqs': freqs_data
                })
        
        return final_detections
    
    def compute_ultra_hardened(self) -> Dict[str, Any]:
        """
        Ultra-hardened computation with full statistical validation
        """
        if len(self._vals) < self.min_events:
            return {
                'status': 'insufficient_data',
                'events': len(self._vals),
                'required': self.min_events,
                'patterns': [],
                'confidence': 0.0
            }
        
        t = np.array(self._ts, dtype=float)
        v = np.array(self._vals, dtype=float)
        
        # Advanced preprocessing
        t_clean, v_clean = self._advanced_preprocessing(t, v)
        
        # Ensemble spectrum analysis
        ensemble_results = self._ensemble_spectrum_analysis(t_clean, v_clean)
        
        # Combine ensemble results with weighted voting
        combined_detections = self._combine_ensemble_results(ensemble_results)
        
        # Validate each detection
        validated_patterns = []
        for detection in combined_detections:
            pattern_name = detection['pattern']
            freq = detection['frequency']
            confidence = detection['confidence']
            
            # Apply drift compensation
            freq = self._apply_drift_compensation(freq, pattern_name)
            
            # Get pattern signature
            if pattern_name in self.pattern_signatures:
                signature = self.pattern_signatures[pattern_name]
                
                # Validate harmonics (anti-spoofing)
                if 'spectrum' in detection and detection['spectrum'] is not None:
                    valid, harmonic_score = self._validate_harmonics(
                        detection['freqs'], detection['spectrum'], signature
                    )
                    if not valid:
                        continue
                    confidence *= harmonic_score
            
            # Statistical validation
            stat_validation = self._statistical_validation(freq, confidence, pattern_name)
            
            # Combined confidence
            final_confidence = confidence * stat_validation['statistical_confidence']
            
            if final_confidence > 0.5:  # Minimum threshold
                validated_patterns.append({
                    'pattern': pattern_name,
                    'frequency': freq,
                    'confidence': final_confidence * 100,
                    'statistical_validation': stat_validation,
                    'drift_compensated': abs(self.drift_factors.get(pattern_name, 1.0) - 1.0) > 0.05,
                    'methods_detected': detection.get('methods_detected', 1)
                })
            
            # Update history
            self.validation_history.append({
                'timestamp': time.time(),
                'pattern': pattern_name,
                'frequency': freq,
                'confidence': confidence,
                'features': self._extract_features(v_clean)
            })
        
        # Check for spoofing
        is_spoofing = self._detect_spoofing_attempt(t_clean, v_clean, validated_patterns)
        
        # Update metrics
        self.metrics['total_detections'] += len(combined_detections)
        self.metrics['confirmed_detections'] += len(validated_patterns)
        if self.metrics['total_detections'] > 0:
            self.metrics['accuracy_rate'] = self.metrics['confirmed_detections'] / self.metrics['total_detections']
        
        result = {
            'status': 'success',
            'patterns': validated_patterns[:5],  # Top 5
            'spoofing_detected': is_spoofing,
            'ensemble_methods_used': [k for k, v in ensemble_results.items() if v is not None],
            'statistical_confidence': np.mean([p['confidence'] for p in validated_patterns]) if validated_patterns else 0,
            'metrics': self.metrics.copy(),
            'events_analyzed': len(v_clean)
        }
        
        return result
    
    def tick(self, source_label: str = "ultra_hardened") -> Dict[str, Any]:
        """Main tick method with full hardening"""
        now = time.time()
        if now - self._last_compute_ts < 0.5:  # Higher frequency allowed
            return {"status": "rate_limited", "patterns": []}
        
        self._last_compute_ts = now
        return self.compute_ultra_hardened()


# Global instance
ultra_fingerprinter = UltraHardenedFingerprinter()
