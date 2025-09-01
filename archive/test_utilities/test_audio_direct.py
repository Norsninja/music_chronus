#!/usr/bin/env python3
"""Direct test of audio output with the same environment."""

import os
import sounddevice as sd
import numpy as np
import time

# Use same environment as Pane 1
os.environ['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'

print("Direct Audio Test")
print(f"PULSE_SERVER: {os.environ.get('PULSE_SERVER')}")
print(f"Devices: {sd.query_devices()}")

# Generate test tone
sample_rate = 44100
freq = 440.0
duration = 2.0

t = np.linspace(0, duration, int(sample_rate * duration))
wave = 0.5 * np.sin(2 * np.pi * freq * t)

print(f"\nPlaying {freq}Hz for {duration} seconds...")
sd.play(wave, sample_rate)
sd.wait()
print("Done. Did you hear it?")