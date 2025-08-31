#!/usr/bin/env python3
"""
RT-03: Final Verdict on Threading vs Multiprocessing

Testing with realistic audio buffer sizes and operations.
"""

import time
import threading
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import numpy as np
import scipy.signal
import psutil

# Realistic audio parameters
SAMPLE_RATE = 44100
BUFFER_SIZE = 256  # 5.8ms buffer
NUM_BUFFERS = 1000  # Process 1000 buffers to simulate sustained load

def realistic_dsp_module(module_type="vco", buffer_size=None):
    """Simulate a real DSP module processing audio buffers."""
    
    if buffer_size is None:
        buffer_size = BUFFER_SIZE
    
    # Pre-allocate buffers
    audio_buffer = np.zeros(buffer_size, dtype=np.float32)
    output_buffer = np.zeros(buffer_size, dtype=np.float32)
    
    if module_type == "vco":
        # Oscillator - generate waveform
        phase = 0.0
        freq = 440.0
        phase_inc = 2 * np.pi * freq / SAMPLE_RATE
        
        for _ in range(NUM_BUFFERS):
            # Generate sine wave
            phases = np.arange(buffer_size) * phase_inc + phase
            output_buffer[:] = np.sin(phases)
            phase = (phase + buffer_size * phase_inc) % (2 * np.pi)
            
    elif module_type == "filter":
        # Filter - process audio
        sos = scipy.signal.butter(4, 1000/SAMPLE_RATE*2, output='sos')
        
        for _ in range(NUM_BUFFERS):
            # Random input to simulate
            audio_buffer[:] = np.random.randn(buffer_size) * 0.1
            output_buffer[:] = scipy.signal.sosfilt(sos, audio_buffer)
            
    elif module_type == "reverb":
        # Reverb - convolution
        ir_size = 512  # Small impulse response
        impulse_response = np.random.randn(ir_size) * 0.01
        
        for _ in range(NUM_BUFFERS):
            audio_buffer[:] = np.random.randn(buffer_size) * 0.1
            # This is memory intensive
            convolved = np.convolve(audio_buffer, impulse_response, mode='same')
            output_buffer[:] = convolved[:buffer_size]
    
    return module_type

def test_realistic_scenario():
    """Test a realistic synthesizer patch with multiple modules."""
    print("=" * 60)
    print("RT-03: FINAL VERDICT - Realistic Audio Processing")
    print("=" * 60)
    
    print(f"\nTest Parameters:")
    print(f"  Buffer size: {BUFFER_SIZE} samples ({BUFFER_SIZE/SAMPLE_RATE*1000:.1f}ms)")
    print(f"  Buffers to process: {NUM_BUFFERS}")
    print(f"  Total audio time: {NUM_BUFFERS * BUFFER_SIZE / SAMPLE_RATE:.1f}s")
    
    modules = ["vco", "filter", "reverb", "vco", "filter", "reverb"]
    
    # Test 1: Sequential baseline
    print(f"\n1. Sequential Processing ({len(modules)} modules):")
    start = time.perf_counter()
    for module in modules:
        realistic_dsp_module(module)
    seq_time = time.perf_counter() - start
    print(f"   Time: {seq_time:.3f}s")
    print(f"   Real-time ratio: {(NUM_BUFFERS * BUFFER_SIZE / SAMPLE_RATE) / seq_time:.2f}x")
    
    # Test 2: Threading
    print(f"\n2. Threading ({len(modules)} threads):")
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(modules)) as executor:
        futures = [executor.submit(realistic_dsp_module, module) for module in modules]
        [f.result() for f in futures]
    thread_time = time.perf_counter() - start
    print(f"   Time: {thread_time:.3f}s")
    print(f"   Speedup vs sequential: {seq_time/thread_time:.2f}x")
    print(f"   Real-time ratio: {(NUM_BUFFERS * BUFFER_SIZE / SAMPLE_RATE) / thread_time:.2f}x")
    
    # Test 3: Multiprocessing
    print(f"\n3. Multiprocessing ({len(modules)} processes):")
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=len(modules)) as executor:
        futures = [executor.submit(realistic_dsp_module, module) for module in modules]
        [f.result() for f in futures]
    process_time = time.perf_counter() - start
    print(f"   Time: {process_time:.3f}s")
    print(f"   Speedup vs sequential: {seq_time/process_time:.2f}x")
    print(f"   Real-time ratio: {(NUM_BUFFERS * BUFFER_SIZE / SAMPLE_RATE) / process_time:.2f}x")
    
    # Test 4: Measure with larger buffers
    print(f"\n4. Testing Larger Buffers (1024 samples):")
    
    print("   Threading with 1024 sample buffer:")
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(realistic_dsp_module, "filter", 1024) for _ in range(4)]
        [f.result() for f in futures]
    large_thread = time.perf_counter() - start
    
    print("   Multiprocessing with 1024 sample buffer:")
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(realistic_dsp_module, "filter", 1024) for _ in range(4)]
        [f.result() for f in futures]
    large_process = time.perf_counter() - start
    
    print(f"   Threading: {large_thread:.3f}s")
    print(f"   Multiprocessing: {large_process:.3f}s")
    
    # Analysis
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    
    if thread_time < seq_time * 0.6:
        print("✅ Threading achieves good parallelism")
    else:
        print("⚠️ Threading parallelism limited")
    
    if thread_time < process_time * 1.1:
        print("✅ Threading competitive with multiprocessing")
    else:
        print("❌ Multiprocessing significantly faster")
    
    thread_efficiency = seq_time / (thread_time * len(modules))
    process_efficiency = seq_time / (process_time * len(modules))
    
    print(f"\nParallel Efficiency:")
    print(f"  Threading: {thread_efficiency*100:.1f}%")
    print(f"  Multiprocessing: {process_efficiency*100:.1f}%")
    
    # Memory test
    print("\nMemory Usage Test:")
    process = psutil.Process()
    
    # Threading memory
    mem_before = process.memory_info().rss / 1024 / 1024
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(lambda: np.zeros(1024*1024)) for _ in range(8)]
        [f.result() for f in futures]
    thread_mem = process.memory_info().rss / 1024 / 1024 - mem_before
    
    # Process memory
    mem_before = process.memory_info().rss / 1024 / 1024
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(lambda: np.zeros(1024*1024)) for _ in range(8)]
        [f.result() for f in futures]
    process_mem = process.memory_info().rss / 1024 / 1024 - mem_before
    
    print(f"  Threading overhead: {thread_mem:.1f} MB")
    print(f"  Multiprocessing overhead: {process_mem:.1f} MB")
    
    # Final verdict
    print("\n" + "=" * 60)
    print("FINAL VERDICT")
    print("=" * 60)
    
    thread_score = 0
    process_score = 0
    
    if thread_time < process_time:
        thread_score += 2
        print("✅ Threading faster for our workload")
    else:
        process_score += 2
        print("✅ Multiprocessing faster for our workload")
    
    if thread_mem < process_mem:
        thread_score += 1
        print("✅ Threading uses less memory")
    else:
        process_score += 1
        print("✅ Multiprocessing uses less memory")
    
    if thread_efficiency > 0.3:
        thread_score += 1
        print("✅ Threading achieves decent parallelism")
    
    if process_efficiency > 0.3:
        process_score += 1
        print("✅ Multiprocessing achieves decent parallelism")
    
    print(f"\nScores: Threading={thread_score}, Multiprocessing={process_score}")
    
    if thread_score > process_score:
        print("\n🎯 RECOMMENDATION: Use THREADING")
        print("   Lower overhead and memory usage outweigh modest parallelism")
    elif process_score > thread_score:
        print("\n🎯 RECOMMENDATION: Use MULTIPROCESSING")
        print("   Better parallelism justifies the overhead")
    else:
        print("\n🎯 RECOMMENDATION: Use HYBRID ARCHITECTURE")
        print("   Processes for isolation, threads within each for efficiency")
    
    # Real-time capability check
    min_time = min(thread_time, process_time)
    audio_duration = NUM_BUFFERS * BUFFER_SIZE / SAMPLE_RATE
    if min_time < audio_duration:
        print(f"\n✅ REAL-TIME CAPABLE: Processing {audio_duration/min_time:.1f}x faster than real-time")
    else:
        print(f"\n❌ NOT REAL-TIME: Only {audio_duration/min_time:.1f}x real-time speed")

if __name__ == "__main__":
    test_realistic_scenario()