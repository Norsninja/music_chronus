#!/usr/bin/env python3
"""Test DSP modules in isolation to find the issue."""

import numpy as np
import sys
import os
sys.path.insert(0, '/home/norsninja/music_chronus/src')

from music_chronus.modules.simple_sine import SimpleSine
from music_chronus.modules.adsr import ADSR
from music_chronus.modules.biquad_filter import BiquadFilter

SAMPLE_RATE = 44100
BUFFER_SIZE = 256

print("Testing DSP modules in isolation...")
print("=" * 50)

# Test 1: Just the sine oscillator
print("\n1. Testing SimpleSine alone:")
sine = SimpleSine(SAMPLE_RATE, BUFFER_SIZE)
sine.set_param("freq", 440.0, immediate=True)
sine.set_param("gain", 0.5, immediate=True)

# Generate a few buffers
for i in range(3):
    buffer = sine.process(None)
    rms = np.sqrt(np.mean(buffer**2))
    print(f"   Buffer {i}: RMS = {rms:.4f}, Min = {np.min(buffer):.4f}, Max = {np.max(buffer):.4f}")

# Test 2: Sine + ADSR
print("\n2. Testing SimpleSine + ADSR:")
sine.reset()
adsr = ADSR(SAMPLE_RATE, BUFFER_SIZE)
adsr.set_param("attack", 10.0, immediate=True)
adsr.set_param("decay", 100.0, immediate=True)
adsr.set_param("sustain", 0.7, immediate=True)
adsr.set_param("release", 200.0, immediate=True)

# Gate on
adsr.set_param("gate", True, immediate=True)
for i in range(3):
    sine_out = sine.process(None)
    adsr_out = adsr.process(sine_out)
    rms = np.sqrt(np.mean(adsr_out**2))
    print(f"   Buffer {i}: RMS = {rms:.4f}, Min = {np.min(adsr_out):.4f}, Max = {np.max(adsr_out):.4f}")

# Test 3: Full chain
print("\n3. Testing full chain (Sine + ADSR + Filter):")
sine.reset()
adsr.reset()
biquad = BiquadFilter(SAMPLE_RATE, BUFFER_SIZE)
biquad.set_param("mode", 0, immediate=True)  # Lowpass
biquad.set_param("cutoff", 2000.0, immediate=True)
biquad.set_param("q", 0.707, immediate=True)

for i in range(3):
    sine_out = sine.process(None)
    adsr_out = adsr.process(sine_out)
    filter_out = biquad.process(adsr_out)
    rms = np.sqrt(np.mean(filter_out**2))
    print(f"   Buffer {i}: RMS = {rms:.4f}, Min = {np.min(filter_out):.4f}, Max = {np.max(filter_out):.4f}")

# Check for NaN or Inf
print("\n4. Checking for NaN/Inf in output:")
sine_out = sine.process(None)
adsr_out = adsr.process(sine_out)
filter_out = biquad.process(adsr_out)

print(f"   Sine has NaN: {np.any(np.isnan(sine_out))}")
print(f"   Sine has Inf: {np.any(np.isinf(sine_out))}")
print(f"   ADSR has NaN: {np.any(np.isnan(adsr_out))}")
print(f"   ADSR has Inf: {np.any(np.isinf(adsr_out))}")
print(f"   Filter has NaN: {np.any(np.isnan(filter_out))}")
print(f"   Filter has Inf: {np.any(np.isinf(filter_out))}")

print("\n" + "=" * 50)
print("If RMS values are reasonable (0.0 to 1.0) and no NaN/Inf,")
print("then the DSP modules are working correctly in isolation.")