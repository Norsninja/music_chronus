#!/usr/bin/env python3
"""
RT-03: Simplified GIL Release Verification

Direct test to verify if NumPy actually releases the GIL
"""

import time
import threading
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import numpy as np
import scipy.signal

def numpy_intensive_task(duration=1.0):
    """Pure NumPy operations that should release GIL."""
    start = time.perf_counter()
    data = np.random.randn(1024, 1024).astype(np.float32)
    
    while time.perf_counter() - start < duration:
        # These operations should release GIL
        result = np.fft.fft2(data)
        result = np.abs(result)
        result = np.sqrt(result)
        _ = result.mean()
    
    return time.perf_counter() - start

def python_intensive_task(duration=1.0):
    """Pure Python operations that hold GIL."""
    start = time.perf_counter()
    
    while time.perf_counter() - start < duration:
        # Pure Python - holds GIL
        result = sum(i**2 for i in range(1000))
        _ = [x**2 for x in range(1000)]
    
    return time.perf_counter() - start

def test_gil_release():
    """Test if NumPy actually releases the GIL."""
    print("Testing GIL Release with NumPy Operations")
    print("=" * 50)
    
    # Test 1: Sequential NumPy
    print("\n1. Sequential NumPy (2 tasks, 1 second each):")
    start = time.perf_counter()
    numpy_intensive_task(1.0)
    numpy_intensive_task(1.0)
    sequential_time = time.perf_counter() - start
    print(f"   Sequential time: {sequential_time:.2f}s")
    
    # Test 2: Threaded NumPy
    print("\n2. Threaded NumPy (2 threads, 1 second each):")
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(numpy_intensive_task, 1.0) for _ in range(2)]
        [f.result() for f in futures]
    threaded_time = time.perf_counter() - start
    print(f"   Threaded time: {threaded_time:.2f}s")
    print(f"   Speedup: {sequential_time/threaded_time:.2f}x")
    
    if threaded_time < sequential_time * 0.7:
        print("   ✅ GIL RELEASED - NumPy runs in parallel!")
    else:
        print("   ❌ GIL NOT RELEASED - No parallelism")
    
    # Test 3: Compare with Pure Python (should NOT parallelize)
    print("\n3. Pure Python (2 threads, 1 second each):")
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(python_intensive_task, 1.0) for _ in range(2)]
        [f.result() for f in futures]
    python_threaded_time = time.perf_counter() - start
    print(f"   Threaded time: {python_threaded_time:.2f}s")
    print(f"   Speedup: {sequential_time/python_threaded_time:.2f}x")
    
    if python_threaded_time > sequential_time * 0.9:
        print("   ✅ Expected - Pure Python holds GIL")
    
    # Test 4: Test with varying number of threads
    print("\n4. NumPy Scaling Test:")
    for n_threads in [1, 2, 3, 4]:
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=n_threads) as executor:
            futures = [executor.submit(numpy_intensive_task, 0.5) for _ in range(n_threads)]
            [f.result() for f in futures]
        elapsed = time.perf_counter() - start
        expected_sequential = n_threads * 0.5
        speedup = expected_sequential / elapsed
        print(f"   {n_threads} threads: {elapsed:.2f}s, speedup: {speedup:.2f}x")
    
    # Test 5: Direct comparison - Threading vs Multiprocessing
    print("\n5. Direct Comparison (4 workers, 0.5s tasks):")
    
    # Threading
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(numpy_intensive_task, 0.5) for _ in range(4)]
        [f.result() for f in futures]
    thread_time = time.perf_counter() - start
    
    # Multiprocessing
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(numpy_intensive_task, 0.5) for _ in range(4)]
        [f.result() for f in futures]
    process_time = time.perf_counter() - start
    
    print(f"   Threading:        {thread_time:.2f}s")
    print(f"   Multiprocessing:  {process_time:.2f}s")
    print(f"   Difference:       {abs(thread_time - process_time):.2f}s")
    
    if thread_time < process_time:
        print(f"   ✅ Threading {process_time/thread_time:.1f}x faster")
    else:
        print(f"   ⚠️ Multiprocessing {thread_time/process_time:.1f}x faster")

def dsp_task():
    """Realistic DSP workload."""
    buffer_size = 256
    fft_size = 4096
    
    audio = np.random.randn(buffer_size).astype(np.float32)
    fft_buffer = np.random.randn(fft_size).astype(np.float32)
    
    # Design filter once
    sos = scipy.signal.butter(4, 0.2, output='sos')
    
    for _ in range(1000):
        # FFT
        spectrum = np.fft.rfft(fft_buffer)
        # Filter
        filtered = scipy.signal.sosfilt(sos, audio)
        # Convolution
        conv = np.convolve(filtered, filtered[:64], mode='same')
        _ = conv.sum()

def test_dsp_operations():
    """Test specific DSP operations we'll use."""
    print("\n" + "=" * 50)
    print("Testing DSP Operations")
    print("=" * 50)
    
    print("\n1. Sequential DSP (4 tasks):")
    start = time.perf_counter()
    for _ in range(4):
        dsp_task()
    seq_time = time.perf_counter() - start
    print(f"   Time: {seq_time:.3f}s")
    
    print("\n2. Threaded DSP (4 threads):")
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(dsp_task) for _ in range(4)]
        [f.result() for f in futures]
    thread_time = time.perf_counter() - start
    print(f"   Time: {thread_time:.3f}s")
    print(f"   Speedup: {seq_time/thread_time:.2f}x")
    
    print("\n3. Multiprocess DSP (4 processes):")
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(dsp_task) for _ in range(4)]
        [f.result() for f in futures]
    process_time = time.perf_counter() - start
    print(f"   Time: {process_time:.3f}s")
    print(f"   Speedup: {seq_time/process_time:.2f}x")
    
    print("\n" + "=" * 50)
    print("CONCLUSION")
    print("=" * 50)
    
    if thread_time < seq_time * 0.5:
        print("✅ NumPy/SciPy operations DO release the GIL")
        print("   Threading achieves good parallelism")
    else:
        print("❌ Limited GIL release detected")
        print("   Threading not achieving expected parallelism")
    
    if thread_time < process_time * 1.2:
        print("✅ Threading competitive with multiprocessing")
        print("   Lower overhead makes threading attractive")
    else:
        print("⚠️ Multiprocessing significantly faster")
        print("   Process isolation may be worth the overhead")

if __name__ == "__main__":
    test_gil_release()
    test_dsp_operations()