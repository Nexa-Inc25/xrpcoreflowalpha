#!/usr/bin/env python3
"""
DEBUG: Find out why frequency detection is ACTUALLY broken
No fake results - real debugging
"""

import numpy as np
import time
from scipy import signal
from scipy.signal import periodogram, welch, find_peaks
import matplotlib.pyplot as plt


def test_simple_fft():
    """Test if basic FFT even works on a known signal"""
    print("="*80)
    print("BASIC FFT TEST - Can we detect a 41-second period?")
    print("="*80)
    
    # Generate perfect 41-second period signal
    duration = 3600  # 1 hour
    dt = 1.0  # 1 second sampling
    t = np.arange(0, duration, dt)
    
    # Create signal with 41-second period
    period = 41.0
    frequency = 1.0 / period  # 0.02439 Hz
    signal_clean = np.sin(2 * np.pi * frequency * t)
    
    # Add realistic noise
    signal_noisy = signal_clean + 0.1 * np.random.randn(len(t))
    
    # Method 1: Simple FFT
    fft_vals = np.abs(np.fft.rfft(signal_noisy))
    fft_freqs = np.fft.rfftfreq(len(signal_noisy), d=dt)
    
    # Find peak
    peak_idx = np.argmax(fft_vals[1:]) + 1  # Skip DC
    detected_freq = fft_freqs[peak_idx]
    
    print(f"\nMethod 1 - Simple FFT:")
    print(f"  True frequency: {frequency:.6f} Hz (period: {period:.1f}s)")
    print(f"  Detected frequency: {detected_freq:.6f} Hz")
    print(f"  Error: {abs(detected_freq - frequency)/frequency * 100:.2f}%")
    
    # Method 2: Welch's method
    f_welch, psd_welch = welch(signal_noisy, fs=1/dt, nperseg=256)
    peak_idx_welch = np.argmax(psd_welch[1:]) + 1
    detected_freq_welch = f_welch[peak_idx_welch]
    
    print(f"\nMethod 2 - Welch's method:")
    print(f"  Detected frequency: {detected_freq_welch:.6f} Hz")
    print(f"  Error: {abs(detected_freq_welch - frequency)/frequency * 100:.2f}%")
    
    # Method 3: Periodogram
    f_period, psd_period = periodogram(signal_noisy, fs=1/dt)
    peak_idx_period = np.argmax(psd_period[1:]) + 1
    detected_freq_period = f_period[peak_idx_period]
    
    print(f"\nMethod 3 - Periodogram:")
    print(f"  Detected frequency: {detected_freq_period:.6f} Hz")
    print(f"  Error: {abs(detected_freq_period - frequency)/frequency * 100:.2f}%")
    
    return detected_freq


def test_event_based_detection():
    """Test detection from discrete events (like trades)"""
    print("\n" + "="*80)
    print("EVENT-BASED DETECTION - Simulating trades every 41 seconds")
    print("="*80)
    
    # Generate events at 41-second intervals
    period = 41.0
    duration = 3600  # 1 hour
    num_events = int(duration / period)
    
    # Create event times with small jitter
    event_times = []
    current_time = 0
    for i in range(num_events):
        jitter = np.random.normal(0, period * 0.03)  # 3% jitter
        event_times.append(current_time + jitter)
        current_time += period
    
    event_times = np.array(event_times)
    
    # Method 1: Inter-event interval analysis
    intervals = np.diff(event_times)
    mean_interval = np.mean(intervals)
    std_interval = np.std(intervals)
    
    print(f"\nInter-event analysis:")
    print(f"  Mean interval: {mean_interval:.2f}s")
    print(f"  Std deviation: {std_interval:.2f}s")
    print(f"  Detected period: {mean_interval:.2f}s")
    print(f"  Error: {abs(mean_interval - period)/period * 100:.2f}%")
    
    # Method 2: Autocorrelation
    # Create time series from events
    max_time = int(event_times[-1]) + 100
    time_series = np.zeros(max_time)
    for t in event_times:
        idx = int(t)
        if idx < len(time_series):
            time_series[idx] = 1.0
    
    # Compute autocorrelation
    autocorr = np.correlate(time_series, time_series, mode='same')
    autocorr = autocorr[len(autocorr)//2:]  # Take positive lags
    
    # Find peaks in autocorrelation
    peaks, _ = find_peaks(autocorr, height=0.5*np.max(autocorr), distance=30)
    
    if len(peaks) > 0:
        detected_period = peaks[0]
        print(f"\nAutocorrelation analysis:")
        print(f"  Detected period: {detected_period}s")
        print(f"  Error: {abs(detected_period - period)/period * 100:.2f}%")
    
    # Method 3: Lomb-Scargle periodogram (good for unevenly sampled data)
    from scipy.signal import lombscargle
    
    # Create signal values (all 1.0 for events)
    event_values = np.ones(len(event_times))
    
    # Frequency grid to search
    frequencies = np.linspace(0.001, 0.5, 1000)
    
    # Compute Lomb-Scargle periodogram
    pgram = lombscargle(event_times, event_values, frequencies)
    
    # Find peak
    peak_idx = np.argmax(pgram)
    detected_freq_ls = frequencies[peak_idx]
    detected_period_ls = 1.0 / detected_freq_ls
    
    print(f"\nLomb-Scargle periodogram:")
    print(f"  Detected frequency: {detected_freq_ls:.6f} Hz")
    print(f"  Detected period: {detected_period_ls:.2f}s")
    print(f"  Error: {abs(detected_period_ls - period)/period * 100:.2f}%")
    
    return detected_period_ls


def test_ultra_hardened_fingerprinter():
    """Test what's wrong with our ultra-hardened fingerprinter"""
    print("\n" + "="*80)
    print("DEBUGGING ULTRA-HARDENED FINGERPRINTER")
    print("="*80)
    
    from predictors.ultra_hardened_fingerprinter import UltraHardenedFingerprinter
    
    fp = UltraHardenedFingerprinter(
        window_seconds=3600,
        sample_rate_hz=1.0,
        min_events=20,
        enable_anti_spoof=False,
        enable_drift_compensation=False
    )
    
    # Generate perfect pattern
    period = 41.0
    base_time = time.time() - 3600
    
    print(f"Adding events with {period}s period...")
    for i in range(100):
        timestamp = base_time + i * period
        value = 1000000
        fp.add_event(timestamp=timestamp, value=value)
    
    print(f"Events in deque: {len(fp._vals)}")
    
    # Check the raw data
    if len(fp._vals) > 0:
        t = np.array(fp._ts)
        v = np.array(fp._vals)
        
        # Check intervals
        intervals = np.diff(t)
        print(f"Mean interval: {np.mean(intervals):.2f}s")
        print(f"Expected: {period}s")
        
        # Simple FFT on the values
        dt = np.mean(intervals)
        if dt > 0:
            fs = 1.0 / dt
            f, psd = periodogram(v, fs=fs)
            
            # Find peak (skip DC)
            if len(psd) > 1:
                peak_idx = np.argmax(psd[1:]) + 1
                peak_freq = f[peak_idx] if peak_idx < len(f) else 0
                print(f"Peak frequency from raw FFT: {peak_freq:.6f} Hz")
                print(f"Expected: {1.0/period:.6f} Hz")
    
    # Now try the actual detection
    result = fp.compute_ultra_hardened()
    
    print(f"\nDetection result:")
    print(f"  Status: {result['status']}")
    print(f"  Events analyzed: {result.get('events_analyzed', 0)}")
    print(f"  Patterns found: {len(result.get('patterns', []))}")
    
    # Debug the ensemble results
    print(f"\nEnsemble methods used: {result.get('ensemble_methods_used', [])}")
    
    # The problem might be in pattern matching
    # Let's check what frequencies are being detected before pattern matching
    print("\nDEBUG: Need to check _combine_ensemble_results to see raw frequencies")
    
    return result


def main():
    """Run all debugging tests to find the real problem"""
    print("="*80)
    print("DEBUGGING FREQUENCY DETECTION - FINDING THE REAL PROBLEM")
    print("="*80)
    
    # Test 1: Can basic FFT detect 41-second period?
    print("\n📊 TEST 1: BASIC FFT")
    freq1 = test_simple_fft()
    
    # Test 2: Can we detect from discrete events?
    print("\n📊 TEST 2: EVENT-BASED DETECTION")
    period2 = test_event_based_detection()
    
    # Test 3: What's wrong with ultra-hardened?
    print("\n📊 TEST 3: ULTRA-HARDENED DEBUGGING")
    result3 = test_ultra_hardened_fingerprinter()
    
    print("\n" + "="*80)
    print("DIAGNOSIS:")
    print("="*80)
    
    if freq1 is not None and abs(freq1 - 1.0/41.0) / (1.0/41.0) < 0.01:
        print("✅ Basic FFT works fine")
    else:
        print("❌ Basic FFT is broken")
    
    if period2 is not None and abs(period2 - 41.0) / 41.0 < 0.05:
        print("✅ Event-based detection works")
    else:
        print("❌ Event-based detection is broken")
    
    if result3['status'] == 'success' and len(result3.get('patterns', [])) > 0:
        print("✅ Ultra-hardened detection works")
    else:
        print("❌ Ultra-hardened has a problem - likely in pattern matching or thresholds")
        print("\nThe issue is probably:")
        print("1. Pattern matching tolerance is too strict")
        print("2. Confidence thresholds are too high")
        print("3. The ensemble combination is discarding valid detections")
    
    print("\nREAL ACCURACY: Based on actual detection, not fabricated")


if __name__ == "__main__":
    main()
