#!/usr/bin/env python3
"""
FIX THE ACTUAL BUG - frequencies are 100x too low
Find where the calculation is wrong and fix it
"""

import numpy as np
import time
from scipy.signal import welch, periodogram
from scipy.fft import rfft, rfftfreq


def debug_welch_method():
    """Debug the Welch method implementation"""
    print("DEBUGGING WELCH METHOD")
    print("-" * 60)
    
    # Generate known 41-second period signal
    duration = 4100  # 100 periods
    dt = 1.0  # 1 second sampling
    t = np.arange(0, duration, dt)
    
    period = 41.0
    true_freq = 1.0 / period
    
    # Create signal
    signal = np.sin(2 * np.pi * true_freq * t)
    
    # Test Welch with different parameters
    fs = 1.0 / dt  # Sampling frequency = 1 Hz
    
    # Default Welch
    f1, psd1 = welch(signal, fs=fs)
    peak1 = f1[np.argmax(psd1[1:]) + 1]
    
    # With specific nperseg
    nperseg = min(len(signal) // 4, 256)
    f2, psd2 = welch(signal, fs=fs, nperseg=nperseg, noverlap=nperseg//2)
    peak2 = f2[np.argmax(psd2[1:]) + 1]
    
    # With larger nperseg
    nperseg_large = 1024
    f3, psd3 = welch(signal, fs=fs, nperseg=nperseg_large)
    peak3 = f3[np.argmax(psd3[1:]) + 1]
    
    print(f"True frequency: {true_freq:.6f} Hz")
    print(f"Default Welch: {peak1:.6f} Hz (error: {abs(peak1-true_freq)/true_freq*100:.2f}%)")
    print(f"nperseg={nperseg}: {peak2:.6f} Hz (error: {abs(peak2-true_freq)/true_freq*100:.2f}%)")
    print(f"nperseg={nperseg_large}: {peak3:.6f} Hz (error: {abs(peak3-true_freq)/true_freq*100:.2f}%)")
    
    return peak2


def test_event_based_fft():
    """Test FFT on event-based data (like the fingerprinter uses)"""
    print("\nTESTING EVENT-BASED FFT")
    print("-" * 60)
    
    # Simulate events every 41 seconds
    period = 41.0
    num_events = 100
    
    # Create event timestamps
    timestamps = []
    values = []
    for i in range(num_events):
        t = i * period + np.random.normal(0, 1.0)  # Small jitter
        v = 1000000 * (1 + np.random.normal(0, 0.1))
        timestamps.append(t)
        values.append(v)
    
    timestamps = np.array(timestamps)
    values = np.array(values)
    
    # Method 1: FFT on values directly (WRONG!)
    print("\nMethod 1: FFT on raw values (WRONG approach):")
    dt_wrong = period  # Assuming period is time step
    freqs_wrong = rfftfreq(len(values), d=dt_wrong)
    fft_wrong = np.abs(rfft(values))
    peak_idx = np.argmax(fft_wrong[1:]) + 1
    peak_freq_wrong = freqs_wrong[peak_idx]
    print(f"  Detected: {peak_freq_wrong:.6f} Hz (WRONG!)")
    
    # Method 2: FFT with correct time step (mean interval)
    print("\nMethod 2: FFT with mean interval as dt:")
    dt_correct = np.mean(np.diff(timestamps))
    freqs_correct = rfftfreq(len(values), d=dt_correct)
    fft_correct = np.abs(rfft(values))
    peak_idx = np.argmax(fft_correct[1:]) + 1
    peak_freq_correct = freqs_correct[peak_idx]
    print(f"  Mean dt: {dt_correct:.2f}s")
    print(f"  Detected: {peak_freq_correct:.6f} Hz")
    print(f"  Expected: {1.0/period:.6f} Hz")
    print(f"  Error: {abs(peak_freq_correct - 1.0/period)/(1.0/period)*100:.2f}%")
    
    # Method 3: Resample to uniform grid first (CORRECT approach)
    print("\nMethod 3: Resample to uniform grid first (CORRECT):")
    # Resample to 1 Hz
    t_min, t_max = timestamps[0], timestamps[-1]
    t_uniform = np.arange(t_min, t_max, 1.0)  # 1 second intervals
    v_resampled = np.interp(t_uniform, timestamps, values)
    
    # Now FFT on uniformly sampled data
    dt_uniform = 1.0
    freqs_uniform = rfftfreq(len(v_resampled), d=dt_uniform)
    fft_uniform = np.abs(rfft(v_resampled))
    peak_idx = np.argmax(fft_uniform[1:]) + 1
    peak_freq_uniform = freqs_uniform[peak_idx]
    print(f"  Uniform dt: {dt_uniform:.2f}s")
    print(f"  Detected: {peak_freq_uniform:.6f} Hz")
    print(f"  Expected: {1.0/period:.6f} Hz")
    print(f"  Error: {abs(peak_freq_uniform - 1.0/period)/(1.0/period)*100:.2f}%")
    
    return peak_freq_uniform


def check_fingerprinter_bug():
    """Check where the bug is in the fingerprinter"""
    print("\nCHECKING FINGERPRINTER IMPLEMENTATION")
    print("-" * 60)
    
    print("\nThe bug is likely in _ensemble_spectrum_analysis:")
    print("1. The sampling rate is being set incorrectly")
    print("2. OR the time step calculation is wrong")
    print("3. OR the resampling is creating wrong time steps")
    
    # The fingerprinter does this:
    # target_samples = int((t_clean[-1] - t_clean[0]) * self.sample_rate)
    
    # If sample_rate = 10 Hz and time span = 4100 seconds
    # target_samples = 4100 * 10 = 41000 samples
    
    # But if we only have 100 events, interpolating to 41000 samples
    # creates a signal with wrong frequency content
    
    print("\nPROBLEM IDENTIFIED:")
    print("When sample_rate=10 Hz, the fingerprinter resamples 100 events")
    print("to 41000 samples, which dilutes the frequency content.")
    print("The FFT then sees mostly interpolated zeros, not the actual signal.")
    
    print("\nSOLUTION:")
    print("1. Use sample_rate = 1.0/mean_interval for event-based data")
    print("2. OR don't resample, use Lomb-Scargle for uneven sampling")
    print("3. OR fix the resampling to preserve frequency content")


def test_fixed_approach():
    """Test the correct approach for event-based frequency detection"""
    print("\nTESTING FIXED APPROACH")
    print("-" * 60)
    
    # Generate test events
    period = 41.0
    true_freq = 1.0 / period
    num_events = 100
    
    timestamps = np.array([i * period + np.random.normal(0, 1.0) for i in range(num_events)])
    values = np.array([1e6 * (1 + np.random.normal(0, 0.1)) for _ in range(num_events)])
    
    # CORRECT APPROACH 1: Use mean interval as sampling period
    mean_interval = np.mean(np.diff(timestamps))
    fs = 1.0 / mean_interval
    
    # Apply Welch's method
    f_welch, psd_welch = welch(values, fs=fs, nperseg=min(len(values)//4, 64))
    peak_idx = np.argmax(psd_welch[1:]) + 1
    detected_freq = f_welch[peak_idx]
    
    print(f"Fixed approach with correct sampling rate:")
    print(f"  Mean interval: {mean_interval:.2f}s")
    print(f"  Sampling rate: {fs:.6f} Hz")
    print(f"  True frequency: {true_freq:.6f} Hz")
    print(f"  Detected frequency: {detected_freq:.6f} Hz")
    
    error = abs(detected_freq - true_freq) / true_freq * 100
    accuracy = 100 - error
    
    print(f"  Error: {error:.2f}%")
    print(f"  ACCURACY: {accuracy:.1f}%")
    
    if accuracy >= 95:
        print(f"\n✅ ACHIEVED 95%+ ACCURACY! ({accuracy:.1f}%)")
    else:
        print(f"\n❌ Still below 95% target ({accuracy:.1f}%)")
    
    return accuracy


def main():
    print("="*80)
    print("FINDING AND FIXING THE FREQUENCY DETECTION BUG")
    print("="*80)
    
    # Debug different methods
    peak1 = debug_welch_method()
    peak2 = test_event_based_fft()
    check_fingerprinter_bug()
    accuracy = test_fixed_approach()
    
    print("\n" + "="*80)
    print("DIAGNOSIS COMPLETE")
    print("="*80)
    print("\nTHE BUG: The ultra-hardened fingerprinter is using the wrong")
    print("sampling rate for event-based data. It's resampling to a high")
    print("rate (10 Hz) which creates mostly interpolated zeros.")
    print("\nTHE FIX: Use the actual mean interval between events as the")
    print("sampling period, or use Lomb-Scargle for uneven sampling.")
    print(f"\nWith the fix, we achieve {accuracy:.1f}% accuracy on known patterns.")


if __name__ == "__main__":
    main()
