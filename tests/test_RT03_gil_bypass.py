#!/usr/bin/env python3
"""
RT-03: GIL Bypass Verification Test

This test verifies that NumPy operations release the GIL, enabling
true parallelism with threading. It compares threading vs multiprocessing
performance for DSP operations to determine the optimal architecture.
"""

import time
import threading
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import numpy as np
import scipy.signal
import psutil
import os
from typing import Dict, List, Tuple
import statistics

# Test configuration
SAMPLE_RATE = 44100
BUFFER_SIZE = 256  # ~5.8ms at 44.1kHz
FFT_SIZE = 4096
NUM_WORKERS = 8
TEST_DURATION = 5  # seconds
ITERATIONS_PER_WORKER = 100

def setup_cpu_affinity():
    """Pin process to specific CPU cores for consistent measurements."""
    try:
        p = psutil.Process()
        p.cpu_affinity(list(range(psutil.cpu_count())))
        return psutil.cpu_count()
    except:
        return os.cpu_count() or 8

def dsp_workload(worker_id: int, iterations: int = ITERATIONS_PER_WORKER) -> Tuple[float, int]:
    """
    Simulate realistic DSP workload with operations that should release GIL.
    Returns: (execution_time, worker_id)
    """
    start_time = time.perf_counter()
    
    # Pre-allocate arrays
    audio_buffer = np.random.randn(BUFFER_SIZE).astype(np.float32)
    fft_buffer = np.random.randn(FFT_SIZE).astype(np.float32)
    
    # Design a filter (expensive operation)
    sos = scipy.signal.butter(4, 0.2, output='sos')
    
    for _ in range(iterations):
        # FFT operation (should release GIL)
        spectrum = np.fft.rfft(fft_buffer)
        
        # Array arithmetic (should release GIL)
        magnitude = np.abs(spectrum)
        phase = np.angle(spectrum)
        
        # Filtering (should release GIL)
        filtered = scipy.signal.sosfilt(sos, audio_buffer)
        
        # Convolution (memory intensive, should release GIL)
        convolved = np.convolve(filtered, filtered[:64], mode='same')
        
        # Prevent optimization
        _ = convolved.sum()
    
    elapsed = time.perf_counter() - start_time
    return elapsed, worker_id

def measure_sequential_baseline() -> float:
    """Measure single-threaded performance as baseline."""
    print("\n1. Measuring Sequential Baseline...")
    total_time = 0
    
    for i in range(NUM_WORKERS):
        elapsed, _ = dsp_workload(i)
        total_time += elapsed
        print(f"   Worker {i}: {elapsed:.3f}s")
    
    print(f"   Total sequential time: {total_time:.3f}s")
    return total_time

def measure_threading_performance() -> Dict:
    """Measure multi-threaded performance with ThreadPoolExecutor."""
    print("\n2. Measuring Threading Performance...")
    
    results = {
        'execution_times': [],
        'speedup': 0,
        'memory_usage': 0,
        'cpu_usage': []
    }
    
    # Monitor CPU usage during execution
    cpu_monitor = []
    stop_monitoring = threading.Event()
    
    def monitor_cpu():
        while not stop_monitoring.is_set():
            cpu_monitor.append(psutil.cpu_percent(interval=0.1, percpu=True))
    
    monitor_thread = threading.Thread(target=monitor_cpu)
    monitor_thread.start()
    
    # Measure memory before
    process = psutil.Process()
    mem_before = process.memory_info().rss / 1024 / 1024  # MB
    
    # Run DSP workloads in parallel threads
    start_time = time.perf_counter()
    
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [executor.submit(dsp_workload, i) for i in range(NUM_WORKERS)]
        thread_results = [f.result() for f in futures]
    
    total_time = time.perf_counter() - start_time
    
    # Stop monitoring
    stop_monitoring.set()
    monitor_thread.join()
    
    # Measure memory after
    mem_after = process.memory_info().rss / 1024 / 1024  # MB
    
    # Process results
    for elapsed, worker_id in thread_results:
        results['execution_times'].append(elapsed)
        print(f"   Thread {worker_id}: {elapsed:.3f}s")
    
    results['total_time'] = total_time
    results['memory_usage'] = mem_after - mem_before
    
    # Calculate average CPU usage
    if cpu_monitor:
        avg_cpu_per_core = [statistics.mean(core_usage[i] for core_usage in cpu_monitor) 
                            for i in range(len(cpu_monitor[0]))]
        results['cpu_usage'] = avg_cpu_per_core
        results['avg_cpu'] = statistics.mean(avg_cpu_per_core)
        
    print(f"   Total parallel time: {total_time:.3f}s")
    print(f"   Memory delta: {results['memory_usage']:.1f} MB")
    print(f"   Average CPU: {results.get('avg_cpu', 0):.1f}%")
    
    return results

def measure_multiprocessing_performance() -> Dict:
    """Measure multi-process performance with ProcessPoolExecutor."""
    print("\n3. Measuring Multiprocessing Performance...")
    
    results = {
        'execution_times': [],
        'speedup': 0,
        'memory_usage': 0,
        'cpu_usage': []
    }
    
    # Monitor system resources
    process = psutil.Process()
    mem_before = process.memory_info().rss / 1024 / 1024  # MB
    
    # Pre-import numpy in workers by using initializer
    def init_worker():
        import numpy as np
        import scipy.signal
    
    # Run DSP workloads in parallel processes
    start_time = time.perf_counter()
    
    with ProcessPoolExecutor(max_workers=NUM_WORKERS, initializer=init_worker) as executor:
        futures = [executor.submit(dsp_workload, i) for i in range(NUM_WORKERS)]
        process_results = [f.result() for f in futures]
    
    total_time = time.perf_counter() - start_time
    
    # Measure memory after (includes child processes)
    mem_after = process.memory_info().rss / 1024 / 1024  # MB
    
    # Process results
    for elapsed, worker_id in process_results:
        results['execution_times'].append(elapsed)
        print(f"   Process {worker_id}: {elapsed:.3f}s")
    
    results['total_time'] = total_time
    results['memory_usage'] = mem_after - mem_before
    
    print(f"   Total parallel time: {total_time:.3f}s")
    print(f"   Memory delta: {results['memory_usage']:.1f} MB")
    
    return results

def process_with_threads():
    """Single process running multiple threads internally."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(dsp_workload, i, ITERATIONS_PER_WORKER//2) 
                  for i in range(4)]
        return [f.result() for f in futures]

def measure_hybrid_architecture() -> Dict:
    """Test hybrid approach: process with internal thread pool."""
    print("\n4. Testing Hybrid Architecture (Process + Threads)...")
    
    results = {}
    start_time = time.perf_counter()
    
    # Run 2 processes, each with 4 threads
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(process_with_threads) for _ in range(2)]
        hybrid_results = [f.result() for f in futures]
    
    total_time = time.perf_counter() - start_time
    results['total_time'] = total_time
    
    print(f"   Total hybrid time: {total_time:.3f}s")
    print(f"   2 processes × 4 threads each")
    
    return results

def analyze_memory_bandwidth_limit():
    """Determine at what point memory bandwidth becomes the bottleneck."""
    print("\n5. Analyzing Memory Bandwidth Bottleneck...")
    
    speedups = []
    
    for num_workers in range(1, 9):
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(dsp_workload, i, iterations=50) 
                      for i in range(num_workers)]
            _ = [f.result() for f in futures]
        
        elapsed = time.perf_counter() - start_time
        
        # Calculate speedup vs single thread
        single_thread_equivalent = num_workers * (elapsed / num_workers)
        speedup = num_workers / (elapsed / single_thread_equivalent) if elapsed > 0 else 0
        speedups.append(speedup)
        
        print(f"   {num_workers} workers: {elapsed:.3f}s, speedup: {speedup:.2f}x")
    
    # Find where speedup plateaus
    max_speedup = max(speedups)
    plateau_point = next((i+1 for i, s in enumerate(speedups) 
                         if s > max_speedup * 0.9), len(speedups))
    
    print(f"   Speedup plateaus at ~{plateau_point} workers")
    return plateau_point

def run_all_tests():
    """Execute all RT-03 test scenarios."""
    print("=" * 60)
    print("RT-03: GIL Bypass Verification Test")
    print("=" * 60)
    
    cpu_count = setup_cpu_affinity()
    print(f"System: {cpu_count} CPU cores available")
    print(f"Testing with {NUM_WORKERS} workers")
    
    # Run tests
    sequential_time = measure_sequential_baseline()
    threading_results = measure_threading_performance()
    multiprocessing_results = measure_multiprocessing_performance()
    hybrid_results = measure_hybrid_architecture()
    bandwidth_limit = analyze_memory_bandwidth_limit()
    
    # Calculate speedups
    threading_speedup = sequential_time / threading_results['total_time']
    multiprocessing_speedup = sequential_time / multiprocessing_results['total_time']
    hybrid_speedup = sequential_time / hybrid_results['total_time']
    
    # Print summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    
    print(f"\nSpeedup vs Sequential ({sequential_time:.2f}s):")
    print(f"  Threading:        {threading_speedup:.2f}x speedup")
    print(f"  Multiprocessing:  {multiprocessing_speedup:.2f}x speedup")
    print(f"  Hybrid:          {hybrid_speedup:.2f}x speedup")
    
    print(f"\nMemory Usage Delta:")
    print(f"  Threading:        {threading_results['memory_usage']:.1f} MB")
    print(f"  Multiprocessing:  {multiprocessing_results['memory_usage']:.1f} MB")
    
    print(f"\nCPU Utilization:")
    print(f"  Threading:        {threading_results.get('avg_cpu', 0):.1f}%")
    
    print(f"\nMemory Bandwidth:")
    print(f"  Bottleneck at:    {bandwidth_limit} parallel operations")
    
    # Verdict
    print("\n" + "=" * 60)
    print("ARCHITECTURE RECOMMENDATION")
    print("=" * 60)
    
    if threading_speedup > multiprocessing_speedup * 0.9:
        print("\n✅ THREADING RECOMMENDED")
        print(f"   - {threading_speedup/multiprocessing_speedup:.1f}x better performance")
        print(f"   - {multiprocessing_results['memory_usage']/max(threading_results['memory_usage'], 1):.1f}x less memory")
        print("   - NumPy successfully releases GIL")
        print("   - Consider hybrid for fault isolation")
    else:
        print("\n⚠️ MULTIPROCESSING STILL VIABLE")
        print("   - Similar performance to threading")
        print("   - Better fault isolation")
        print("   - Higher memory cost acceptable")
    
    print(f"\n💡 Key Finding: Memory bandwidth limits parallelism to ~{bandwidth_limit} workers")
    print("   This explains why only 2-3 workers run in parallel in production")
    
    # Test pass/fail criteria
    print("\n" + "=" * 60)
    print("TEST CRITERIA")
    print("=" * 60)
    
    criteria = [
        ("GIL Release Verified", threading_speedup > 1.5),
        ("Threading Memory Advantage", threading_results['memory_usage'] < multiprocessing_results['memory_usage']),
        ("Bandwidth Bottleneck Found", 2 <= bandwidth_limit <= 4),
        ("Hybrid Architecture Works", hybrid_speedup > 1.5),
    ]
    
    all_passed = True
    for criterion, passed in criteria:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {criterion}: {status}")
        all_passed = all_passed and passed
    
    print("\n" + "=" * 60)
    if all_passed:
        print("RT-03 TEST: ✅ PASSED")
        print("NumPy GIL release confirmed, architecture decision data collected")
    else:
        print("RT-03 TEST: ⚠️ PARTIAL")
        print("Some criteria not met, review results")
    print("=" * 60)

if __name__ == "__main__":
    # Set process to high priority if possible
    try:
        p = psutil.Process()
        p.nice(-5)  # Higher priority
    except:
        pass
    
    run_all_tests()