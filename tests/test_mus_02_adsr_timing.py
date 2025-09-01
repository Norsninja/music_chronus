"""
MUS-02: ADSR Timing Accuracy Test
Test ADSR envelope timing within ±1 buffer tolerance.

At 44100Hz with 256-sample buffers:
- 1 buffer = 5.8ms
- Timing tolerance = ±5.8ms
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from music_chronus.modules.adsr import ADSR


def find_envelope_points(samples: np.ndarray, threshold_low: float = 0.1, 
                        threshold_high: float = 0.9) -> tuple:
    """
    Find 10% and 90% envelope points for rise time measurement.
    
    Args:
        samples: Envelope output samples
        threshold_low: Low threshold (default 0.1)
        threshold_high: High threshold (default 0.9)
        
    Returns:
        Tuple of (low_index, high_index) or (None, None) if not found
    """
    # Find first crossing of low threshold
    low_idx = None
    for i, val in enumerate(samples):
        if val >= threshold_low:
            low_idx = i
            break
    
    # Find first crossing of high threshold
    high_idx = None
    if low_idx is not None:
        for i in range(low_idx, len(samples)):
            if samples[i] >= threshold_high:
                high_idx = i
                break
    
    return low_idx, high_idx


def find_decay_points(samples: np.ndarray, sustain_level: float) -> tuple:
    """
    Find decay phase endpoints.
    
    Args:
        samples: Envelope samples
        sustain_level: Expected sustain level
        
    Returns:
        Tuple of (peak_index, sustain_index)
    """
    # Find peak (end of attack)
    peak_idx = np.argmax(samples)
    
    # Find where it reaches sustain (with small tolerance)
    sustain_idx = None
    tolerance = 0.01
    for i in range(peak_idx, len(samples)):
        if abs(samples[i] - sustain_level) < tolerance:
            sustain_idx = i
            break
    
    return peak_idx, sustain_idx


class TestADSRTiming:
    """Test ADSR envelope timing accuracy to ±1 buffer."""
    
    def test_mus_02_attack_timing(self):
        """Test attack phase timing accuracy."""
        sample_rate = 44100
        buffer_size = 256
        attack_ms = 100.0  # 100ms attack
        
        # Create ADSR
        adsr = ADSR(sample_rate, buffer_size)
        adsr.set_param("attack", attack_ms, immediate=True)
        adsr.set_param("decay", 100.0, immediate=True)
        adsr.set_param("sustain", 0.7, immediate=True)
        adsr.set_param("release", 200.0, immediate=True)
        
        # Trigger gate
        adsr.set_gate(True)
        
        # Generate enough buffers for attack phase
        expected_samples = int(attack_ms * sample_rate / 1000)
        num_buffers = (expected_samples // buffer_size) + 5  # Extra for safety
        samples = []
        
        for _ in range(num_buffers):
            in_buf = np.ones(buffer_size, dtype=np.float32)
            out_buf = np.zeros(buffer_size, dtype=np.float32)
            adsr.process_buffer(in_buf, out_buf)
            samples.extend(out_buf)
        
        samples = np.array(samples)
        
        # Find 10% and 90% points
        idx_10, idx_90 = find_envelope_points(samples, 0.1, 0.9)
        
        assert idx_10 is not None and idx_90 is not None, (
            "Could not find rise time points"
        )
        
        # Measure rise time (10% to 90%)
        rise_samples = idx_90 - idx_10
        expected_rise_samples = int(0.8 * expected_samples)  # 80% of attack time
        
        # Check within ±1 buffer tolerance
        sample_diff = abs(rise_samples - expected_rise_samples)
        buffer_diff = sample_diff / buffer_size
        
        assert buffer_diff <= 1.0, (
            f"Attack timing error: {rise_samples} samples "
            f"(expected {expected_rise_samples} ± {buffer_size}), "
            f"error: {buffer_diff:.2f} buffers"
        )
        
        print(f"✓ Attack timing: {rise_samples} samples "
              f"(target: {expected_rise_samples}, {buffer_diff:.2f} buffers error)")
    
    def test_mus_02_decay_timing(self):
        """Test decay phase timing accuracy."""
        sample_rate = 44100
        buffer_size = 256
        decay_ms = 100.0  # 100ms decay
        sustain_level = 0.7
        
        # Create ADSR
        adsr = ADSR(sample_rate, buffer_size)
        adsr.set_param("attack", 10.0, immediate=True)  # Fast attack
        adsr.set_param("decay", decay_ms, immediate=True)
        adsr.set_param("sustain", sustain_level, immediate=True)
        adsr.set_param("release", 200.0, immediate=True)
        
        # Trigger gate
        adsr.set_gate(True)
        
        # Generate enough buffers for attack + decay
        expected_decay_samples = int(decay_ms * sample_rate / 1000)
        num_buffers = ((expected_decay_samples + 1000) // buffer_size) + 5
        samples = []
        
        for _ in range(num_buffers):
            in_buf = np.ones(buffer_size, dtype=np.float32)
            out_buf = np.zeros(buffer_size, dtype=np.float32)
            adsr.process_buffer(in_buf, out_buf)
            samples.extend(out_buf)
        
        samples = np.array(samples)
        
        # Find decay endpoints
        peak_idx, sustain_idx = find_decay_points(samples, sustain_level)
        
        assert peak_idx is not None and sustain_idx is not None, (
            "Could not find decay phase endpoints"
        )
        
        # Measure decay time
        decay_samples = sustain_idx - peak_idx
        
        # Check within ±1 buffer tolerance
        sample_diff = abs(decay_samples - expected_decay_samples)
        buffer_diff = sample_diff / buffer_size
        
        assert buffer_diff <= 1.0, (
            f"Decay timing error: {decay_samples} samples "
            f"(expected {expected_decay_samples} ± {buffer_size}), "
            f"error: {buffer_diff:.2f} buffers"
        )
        
        print(f"✓ Decay timing: {decay_samples} samples "
              f"(target: {expected_decay_samples}, {buffer_diff:.2f} buffers error)")
    
    def test_mus_02_release_timing(self):
        """Test release phase timing accuracy."""
        sample_rate = 44100
        buffer_size = 256
        release_ms = 200.0  # 200ms release
        
        # Create ADSR
        adsr = ADSR(sample_rate, buffer_size)
        adsr.set_param("attack", 10.0, immediate=True)  # Fast attack
        adsr.set_param("decay", 10.0, immediate=True)   # Fast decay
        adsr.set_param("sustain", 0.7, immediate=True)
        adsr.set_param("release", release_ms, immediate=True)
        
        # Trigger gate
        adsr.set_gate(True)
        
        # Let it reach sustain
        for _ in range(10):
            in_buf = np.ones(buffer_size, dtype=np.float32)
            out_buf = np.zeros(buffer_size, dtype=np.float32)
            adsr.process_buffer(in_buf, out_buf)
        
        # Release gate
        adsr.set_gate(False)
        
        # Capture release phase
        expected_release_samples = int(release_ms * sample_rate / 1000)
        num_buffers = (expected_release_samples // buffer_size) + 5
        samples = []
        
        for _ in range(num_buffers):
            in_buf = np.ones(buffer_size, dtype=np.float32)
            out_buf = np.zeros(buffer_size, dtype=np.float32)
            adsr.process_buffer(in_buf, out_buf)
            samples.extend(out_buf)
        
        samples = np.array(samples)
        
        # Find where envelope reaches near zero (< 0.01)
        release_end_idx = None
        for i, val in enumerate(samples):
            if val < 0.01:
                release_end_idx = i
                break
        
        assert release_end_idx is not None, "Release did not complete"
        
        # The actual release time depends on the starting level
        # For 0.7 sustain level, we expect about 0.7 * release_time
        expected_adjusted = int(0.7 * expected_release_samples)
        
        # Check within ±1 buffer tolerance
        sample_diff = abs(release_end_idx - expected_adjusted)
        buffer_diff = sample_diff / buffer_size
        
        assert buffer_diff <= 1.5, (  # Slightly more tolerance for release
            f"Release timing error: {release_end_idx} samples "
            f"(expected ~{expected_adjusted} ± {buffer_size}), "
            f"error: {buffer_diff:.2f} buffers"
        )
        
        print(f"✓ Release timing: {release_end_idx} samples "
              f"(target: ~{expected_adjusted}, {buffer_diff:.2f} buffers error)")
    
    def test_mus_02_gate_retrigger(self):
        """Test gate retrigger behavior."""
        sample_rate = 44100
        buffer_size = 256
        
        adsr = ADSR(sample_rate, buffer_size)
        adsr.set_param("attack", 50.0, immediate=True)
        adsr.set_param("decay", 50.0, immediate=True)
        adsr.set_param("sustain", 0.5, immediate=True)
        adsr.set_param("release", 100.0, immediate=True)
        
        # First gate
        adsr.set_gate(True)
        
        # Process a few buffers (partway through attack)
        for _ in range(3):
            in_buf = np.ones(buffer_size, dtype=np.float32)
            out_buf = np.zeros(buffer_size, dtype=np.float32)
            adsr.process_buffer(in_buf, out_buf)
            last_level = out_buf[-1]
        
        # Retrigger (should restart attack from current level)
        adsr.set_gate(False)
        adsr.set_gate(True)
        
        # Process one buffer
        in_buf = np.ones(buffer_size, dtype=np.float32)
        out_buf = np.zeros(buffer_size, dtype=np.float32)
        adsr.process_buffer(in_buf, out_buf)
        
        # After retrigger, level should continue rising
        # (attack phase should restart)
        new_level = out_buf[0]
        
        # The envelope should be in attack phase, rising
        assert out_buf[-1] > out_buf[0], (
            "Envelope should be rising after retrigger"
        )
        
        print(f"✓ Gate retrigger working correctly")
    
    def test_mus_02_buffer_boundary_consistency(self):
        """Test that parameter changes apply at buffer boundaries."""
        sample_rate = 44100
        buffer_size = 256
        
        adsr = ADSR(sample_rate, buffer_size)
        adsr.set_param("attack", 100.0, immediate=True)
        adsr.set_param("decay", 100.0, immediate=True)
        adsr.set_param("sustain", 0.7, immediate=True)
        adsr.set_param("release", 200.0, immediate=True)
        
        # Trigger gate
        adsr.set_gate(True)
        
        # Process one buffer
        in_buf = np.ones(buffer_size, dtype=np.float32)
        out_buf1 = np.zeros(buffer_size, dtype=np.float32)
        adsr.process_buffer(in_buf, out_buf1)
        
        # Change attack time (should apply at next buffer)
        adsr.set_param("attack", 200.0)
        
        # Process another buffer
        out_buf2 = np.zeros(buffer_size, dtype=np.float32)
        adsr.process_buffer(in_buf, out_buf2)
        
        # The slope should change between buffers
        # Calculate average slopes
        slope1 = (out_buf1[-1] - out_buf1[0]) / buffer_size
        slope2 = (out_buf2[-1] - out_buf2[0]) / buffer_size
        
        # With doubled attack time, slope should be roughly half
        # (not exact due to boundary effects)
        ratio = slope2 / slope1
        assert 0.4 < ratio < 0.6, (
            f"Attack time change not applied correctly: "
            f"slope ratio {ratio:.3f} (expected ~0.5)"
        )
        
        print(f"✓ Buffer boundary parameter changes working correctly")


if __name__ == "__main__":
    # Run with verbose output
    pytest.main([__file__, "-v", "-s"])