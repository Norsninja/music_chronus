#!/usr/bin/env python3
"""Simple audio test to verify sound output works outside tmux."""

import numpy as np
import sounddevice as sd
import time

print("Simple Audio Test")
print("-" * 40)

# Check devices
print("Available audio devices:")
print(sd.query_devices())
print()

# Generate a 440Hz sine wave
sample_rate = 44100
duration = 1.0
frequency = 440.0

print(f"Playing {frequency}Hz sine wave for {duration} second...")
t = np.linspace(0, duration, int(sample_rate * duration))
wave = 0.5 * np.sin(2 * np.pi * frequency * t)

try:
    sd.play(wave, sample_rate)
    sd.wait()
    print("Playback complete!")
except Exception as e:
    print(f"Error: {e}")

print("\nIf you heard the tone, audio is working.")
print("If not, check PulseAudio configuration.")