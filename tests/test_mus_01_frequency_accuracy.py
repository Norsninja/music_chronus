"""
MUS-01: Frequency Accuracy Test
Test oscillator frequency accuracy within ±1 cent tolerance.

A cent is 1/100th of a semitone. At 440Hz:
- 1 cent = 440 * (2^(1/1200) - 1) ≈ 0.254 Hz
- Tolerance: 439.746 Hz to 440.254 Hz
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from music_chronus.modules.simple_sine import SimpleSine


def measure_frequency(samples: np.ndarray, sample_rate: int) -> float:
    """
    Measure frequency using FFT with quadratic interpolation.
    
    Args:
        samples: Audio samples
        sample_rate: Sample rate
        
    Returns:
        Measured frequency in Hz
    """
    # Apply Hann window to reduce spectral leakage
    window = np.hanning(len(samples))
    windowed = samples * window
    
    # FFT
    fft = np.fft.rfft(windowed)
    freqs = np.fft.rfftfreq(len(windowed), 1/sample_rate)
    
    # Find peak magnitude
    magnitudes = np.abs(fft)
    peak_idx = np.argmax(magnitudes)
    
    # Quadratic interpolation for sub-bin accuracy
    if 1 < peak_idx < len(magnitudes) - 1:
        y1 = magnitudes[peak_idx - 1]
        y2 = magnitudes[peak_idx]
        y3 = magnitudes[peak_idx + 1]
        
        # Parabolic interpolation
        x0 = (y3 - y1) / (2 * (2 * y2 - y1 - y3))
        peak_freq = freqs[peak_idx] + x0 * (freqs[1] - freqs[0])
    else:
        peak_freq = freqs[peak_idx]
    
    return peak_freq


def cents_difference(freq1: float, freq2: float) -> float:
    """
    Calculate the difference in cents between two frequencies.
    
    Args:
        freq1: First frequency
        freq2: Second frequency
        
    Returns:
        Difference in cents
    """
    return 1200 * np.log2(freq1 / freq2)


class TestFrequencyAccuracy:
    """Test SimpleSine frequency accuracy to ±1 cent."""
    
    def test_mus_01_440hz_accuracy(self):
        """Test 440Hz sine wave accuracy."""
        sample_rate = 44100
        buffer_size = 256
        target_freq = 440.0
        
        # Create oscillator
        osc = SimpleSine(sample_rate, buffer_size)
        osc.set_param("freq", target_freq, immediate=True)
        osc.set_param("gain", 1.0, immediate=True)
        
        # Generate 1 second of audio
        num_buffers = (sample_rate // buffer_size) + 1
        samples = []
        
        for _ in range(num_buffers):
            out_buf = np.zeros(buffer_size, dtype=np.float32)
            osc.process_buffer(None, out_buf)
            samples.extend(out_buf)
        
        # Trim to exactly 1 second
        samples = np.array(samples[:sample_rate])
        
        # Measure frequency
        measured_freq = measure_frequency(samples, sample_rate)
        
        # Calculate cents difference
        cents_diff = abs(cents_difference(measured_freq, target_freq))
        
        # Assert within ±1 cent
        assert cents_diff <= 1.0, (
            f"Frequency error too large: {measured_freq:.3f}Hz "
            f"(target: {target_freq}Hz, {cents_diff:.3f} cents)"
        )
        
        # Also check absolute Hz tolerance (0.254 Hz at 440Hz)
        hz_tolerance = target_freq * (2**(1/1200) - 1)
        hz_diff = abs(measured_freq - target_freq)
        assert hz_diff <= hz_tolerance, (
            f"Frequency error: {hz_diff:.3f}Hz exceeds tolerance {hz_tolerance:.3f}Hz"
        )
        
        print(f"✓ 440Hz accuracy: {measured_freq:.3f}Hz ({cents_diff:.3f} cents)")
    
    def test_mus_01_multiple_frequencies(self):
        """Test accuracy across multiple frequencies."""
        sample_rate = 44100
        buffer_size = 256
        
        # Test frequencies spanning musical range
        test_frequencies = [
            110.0,   # A2
            220.0,   # A3
            440.0,   # A4
            880.0,   # A5
            1760.0,  # A6
            261.63,  # Middle C
            523.25,  # C5
            1046.50, # C6
        ]
        
        for target_freq in test_frequencies:
            # Create fresh oscillator for each test
            osc = SimpleSine(sample_rate, buffer_size)
            osc.set_param("freq", target_freq, immediate=True)
            osc.set_param("gain", 1.0, immediate=True)
            
            # Generate samples (at least 0.5 seconds for low frequencies)
            min_samples = max(sample_rate // 2, int(10 * sample_rate / target_freq))
            num_buffers = (min_samples // buffer_size) + 1
            samples = []
            
            for _ in range(num_buffers):
                out_buf = np.zeros(buffer_size, dtype=np.float32)
                osc.process_buffer(None, out_buf)
                samples.extend(out_buf)
            
            # Measure frequency
            samples = np.array(samples[:min_samples])
            measured_freq = measure_frequency(samples, sample_rate)
            
            # Calculate cents difference
            cents_diff = abs(cents_difference(measured_freq, target_freq))
            
            # Assert within ±1 cent
            assert cents_diff <= 1.0, (
                f"Frequency {target_freq}Hz: measured {measured_freq:.3f}Hz "
                f"({cents_diff:.3f} cents error)"
            )
            
            print(f"✓ {target_freq:7.2f}Hz accuracy: {measured_freq:7.3f}Hz "
                  f"({cents_diff:.3f} cents)")
    
    def test_mus_01_phase_continuity(self):
        """Test phase continuity across buffer boundaries."""
        sample_rate = 44100
        buffer_size = 256
        target_freq = 1000.0  # Use higher frequency to see more cycles
        
        osc = SimpleSine(sample_rate, buffer_size)
        osc.set_param("freq", target_freq, immediate=True)
        osc.set_param("gain", 1.0, immediate=True)
        
        # Generate multiple buffers
        buffers = []
        for _ in range(10):
            out_buf = np.zeros(buffer_size, dtype=np.float32)
            osc.process_buffer(None, out_buf)
            buffers.append(out_buf.copy())
        
        # Check continuity at buffer boundaries
        for i in range(len(buffers) - 1):
            # Last sample of current buffer
            last_sample = buffers[i][-1]
            # First sample of next buffer
            first_sample = buffers[i + 1][0]
            
            # Calculate expected phase increment
            phase_inc = 2 * np.pi * target_freq / sample_rate
            
            # The phase should continue smoothly
            # We can't check exact values due to sine nonlinearity,
            # but we can check that there's no sudden jump
            # by verifying the derivative is reasonable
            sample_diff = abs(first_sample - last_sample)
            
            # Maximum expected change (sine derivative max is 2*pi*freq/sr)
            max_expected_diff = 2 * abs(np.sin(phase_inc))
            
            assert sample_diff <= max_expected_diff * 1.1, (
                f"Discontinuity at buffer boundary {i}: "
                f"jump of {sample_diff:.4f} exceeds expected {max_expected_diff:.4f}"
            )
        
        print(f"✓ Phase continuity verified across 10 buffer boundaries")


if __name__ == "__main__":
    # Run with verbose output
    pytest.main([__file__, "-v", "-s"])