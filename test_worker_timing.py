#!/usr/bin/env python3
"""
Measure worker timing to find the bottleneck
"""

import time
import numpy as np

print("WORKER TIMING ANALYSIS")
print("=" * 50)

# Simulate the worker operations
BUFFER_SIZE = 512
SAMPLE_RATE = 48000
buffer_period = BUFFER_SIZE / SAMPLE_RATE  # 10.67ms

print(f"Buffer period: {buffer_period*1000:.2f}ms")
print(f"Required rate: {1/buffer_period:.1f} buffers/sec")
print()

# Test 1: How long does a simple sine generation take?
print("Test 1: Simple sine generation timing")
print("-" * 40)
phase = 0.0
freq = 440.0
phase_inc = 2 * np.pi * freq / SAMPLE_RATE
buffer = np.zeros(BUFFER_SIZE, dtype=np.float32)

times = []
for _ in range(100):
    start = time.perf_counter()
    
    # Simulate SimpleSine
    for i in range(BUFFER_SIZE):
        buffer[i] = np.sin(phase)
        phase += phase_inc
        if phase > 2 * np.pi:
            phase -= 2 * np.pi
    
    elapsed = time.perf_counter() - start
    times.append(elapsed * 1000)

avg_time = np.mean(times)
print(f"Average sine generation: {avg_time:.3f}ms")
print(f"As % of buffer period: {100*avg_time/(buffer_period*1000):.1f}%")
print()

# Test 2: NumPy vectorized version
print("Test 2: NumPy vectorized sine")
print("-" * 40)
phase_array = np.arange(BUFFER_SIZE, dtype=np.float32)

times = []
for _ in range(100):
    start = time.perf_counter()
    
    # Vectorized
    phases = phase_array * phase_inc + phase
    np.sin(phases, out=buffer)
    phase = phases[-1] + phase_inc
    if phase > 2 * np.pi:
        phase -= 2 * np.pi
    
    elapsed = time.perf_counter() - start
    times.append(elapsed * 1000)

avg_time = np.mean(times)
print(f"Average vectorized sine: {avg_time:.3f}ms")
print(f"As % of buffer period: {100*avg_time/(buffer_period*1000):.1f}%")
print()

# Test 3: Full chain simulation (3 modules)
print("Test 3: Three-module chain timing")
print("-" * 40)

times = []
for _ in range(100):
    start = time.perf_counter()
    
    # Module 1: Sine
    for i in range(BUFFER_SIZE):
        buffer[i] = np.sin(phase)
        phase += phase_inc
    
    # Module 2: ADSR (simplified)
    level = 0.7
    for i in range(BUFFER_SIZE):
        buffer[i] *= level
    
    # Module 3: Filter (simplified)
    for i in range(1, BUFFER_SIZE):
        buffer[i] = buffer[i] * 0.8 + buffer[i-1] * 0.2
    
    elapsed = time.perf_counter() - start
    times.append(elapsed * 1000)

avg_time = np.mean(times)
print(f"Average 3-module chain: {avg_time:.3f}ms")
print(f"As % of buffer period: {100*avg_time/(buffer_period*1000):.1f}%")
print()

# Analysis
print("=" * 50)
print("ANALYSIS:")
print("-" * 50)
print(f"Buffer period: {buffer_period*1000:.2f}ms")
print(f"Worker needs to produce a buffer faster than this")
print()
print("If chain processing takes >10ms, worker can't keep up.")
print("If it takes 15ms, worker only produces 67% of needed buffers.")
print()
print("The 31% deficit suggests processing takes ~15ms per buffer.")