#!/usr/bin/env python3
"""
MUS-03: Filter Cutoff Accuracy Test
Requirement: -3dB at cutoff frequency (±2% tolerance)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
from scipy import signal
from music_chronus.modules.biquad_filter import BiquadFilter

def test_filter_cutoff_accuracy():
    """Test that filter has -3dB attenuation at cutoff frequency"""
    print("MUS-03: Filter Cutoff Accuracy Test")
    print("=" * 40)
    
    sample_rate = 44100
    buffer_size = 256
    
    # Test multiple cutoff frequencies
    test_freqs = [100, 500, 1000, 2000, 5000, 10000]
    tolerance = 0.02  # 2% frequency tolerance
    db_target = -3.0
    db_tolerance = 0.5  # ±0.5dB tolerance at cutoff
    
    all_passed = True
    
    for cutoff_freq in test_freqs:
        print(f"\nTesting cutoff at {cutoff_freq}Hz...")
        
        # Create filter
        filter_module = BiquadFilter(sample_rate, buffer_size)
        filter_module.set_param("mode", 0, immediate=True)  # Lowpass
        filter_module.set_param("cutoff", cutoff_freq, immediate=True)
        filter_module.set_param("q", 0.707, immediate=True)  # Standard Q
        
        # Generate test signal: sweep from 10Hz to Nyquist
        duration = 1.0  # 1 second sweep
        num_samples = int(sample_rate * duration)
        num_buffers = num_samples // buffer_size
        
        # Measure frequency response
        # We'll use white noise and measure power spectrum
        noise_input = np.random.randn(num_samples)
        filtered_output = np.zeros(num_samples)
        
        # Process through filter
        for i in range(num_buffers):
            start_idx = i * buffer_size
            end_idx = start_idx + buffer_size
            
            input_buffer = noise_input[start_idx:end_idx].astype(np.float32)
            output_buffer = filter_module.process(input_buffer)
            filtered_output[start_idx:end_idx] = output_buffer
        
        # Calculate frequency response using Welch's method
        freqs, input_psd = signal.welch(noise_input, sample_rate, nperseg=4096)
        freqs, output_psd = signal.welch(filtered_output, sample_rate, nperseg=4096)
        
        # Avoid division by zero and calculate transfer function
        epsilon = 1e-10
        transfer = output_psd / (input_psd + epsilon)
        
        # Convert to dB
        transfer_db = 10 * np.log10(transfer + epsilon)
        
        # Find response at cutoff frequency
        cutoff_idx = np.argmin(np.abs(freqs - cutoff_freq))
        actual_freq = freqs[cutoff_idx]
        response_at_cutoff = transfer_db[cutoff_idx]
        
        # Also measure response well below cutoff (should be ~0dB)
        ref_freq = cutoff_freq / 10  # One decade below
        ref_idx = np.argmin(np.abs(freqs - ref_freq))
        response_at_ref = transfer_db[ref_idx]
        
        # Normalize to passband response
        normalized_response = response_at_cutoff - response_at_ref
        
        # Check if within tolerance
        freq_error = abs(actual_freq - cutoff_freq) / cutoff_freq
        db_error = abs(normalized_response - db_target)
        
        if freq_error <= tolerance and db_error <= db_tolerance:
            print(f"  ✅ PASS: {normalized_response:.2f}dB at {actual_freq:.1f}Hz")
            print(f"    (Target: {db_target}dB ±{db_tolerance}dB at {cutoff_freq}Hz ±{tolerance*100}%)")
        else:
            print(f"  ❌ FAIL: {normalized_response:.2f}dB at {actual_freq:.1f}Hz")
            print(f"    (Target: {db_target}dB ±{db_tolerance}dB at {cutoff_freq}Hz ±{tolerance*100}%)")
            all_passed = False
        
        # Additional check: verify rolloff above cutoff
        # Should be approximately -12dB/octave for 2nd order filter
        octave_above_idx = np.argmin(np.abs(freqs - cutoff_freq * 2))
        response_octave_above = transfer_db[octave_above_idx] - response_at_ref
        expected_rolloff = -12.0  # dB/octave for 2nd order
        
        if response_octave_above < normalized_response + expected_rolloff + 3:
            print(f"  ✅ Rolloff check: {response_octave_above:.1f}dB at {freqs[octave_above_idx]:.0f}Hz")
        else:
            print(f"  ⚠️  Weak rolloff: {response_octave_above:.1f}dB at {freqs[octave_above_idx]:.0f}Hz")
    
    print("\n" + "=" * 40)
    if all_passed:
        print("✅ MUS-03 PASSED: Filter cutoff accuracy within spec")
    else:
        print("❌ MUS-03 FAILED: Some cutoff frequencies out of spec")
    
    return all_passed


def test_filter_stability():
    """Test filter stability at extreme settings"""
    print("\nFilter Stability Test")
    print("=" * 40)
    
    sample_rate = 44100
    buffer_size = 256
    
    filter_module = BiquadFilter(sample_rate, buffer_size)
    
    # Test extreme Q values
    extreme_tests = [
        {"cutoff": 100, "q": 0.1, "name": "Very low Q"},
        {"cutoff": 1000, "q": 20.0, "name": "Very high Q"},
        {"cutoff": 20, "q": 0.707, "name": "Subsonic cutoff"},
        {"cutoff": 20000, "q": 0.707, "name": "Near Nyquist"},
    ]
    
    all_stable = True
    
    for test in extreme_tests:
        print(f"\nTesting: {test['name']}")
        print(f"  Cutoff: {test['cutoff']}Hz, Q: {test['q']}")
        
        filter_module.set_param("mode", 0, immediate=True)
        filter_module.set_param("cutoff", test['cutoff'], immediate=True)
        filter_module.set_param("q", test['q'], immediate=True)
        
        # Process impulse
        impulse = np.zeros(buffer_size * 10, dtype=np.float32)
        impulse[0] = 1.0
        
        output = np.zeros_like(impulse)
        
        for i in range(10):
            start = i * buffer_size
            end = start + buffer_size
            out_buf = filter_module.process(impulse[start:end])
            output[start:end] = out_buf
        
        # Check for NaN or Inf
        if np.any(np.isnan(output)) or np.any(np.isinf(output)):
            print(f"  ❌ UNSTABLE: NaN or Inf in output")
            all_stable = False
        elif np.max(np.abs(output)) > 10.0:
            print(f"  ❌ UNSTABLE: Output exceeds reasonable bounds")
            all_stable = False
        else:
            print(f"  ✅ STABLE: Max output = {np.max(np.abs(output)):.3f}")
    
    return all_stable


if __name__ == "__main__":
    import sys
    
    # Run tests
    cutoff_passed = test_filter_cutoff_accuracy()
    stability_passed = test_filter_stability()
    
    print("\n" + "=" * 40)
    print("FINAL RESULTS")
    print("=" * 40)
    
    if cutoff_passed and stability_passed:
        print("✅ ALL FILTER TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ SOME FILTER TESTS FAILED")
        sys.exit(1)