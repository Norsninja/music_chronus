#!/usr/bin/env python3
"""
PROC-02: Worker Pool Task Assignment Test
Testing pre-warmed worker pool for <10ms task assignment

Based on research showing:
- Shared memory must be created BEFORE pool initialization
- maxtasksperchild trade-offs between memory and performance
- forkserver provides best balance for audio applications
"""

import multiprocessing as mp
import concurrent.futures
import ctypes
import numpy as np
import time
import psutil
import os
import signal
from statistics import mean, stdev, median
import traceback
import gc

# Audio configuration matching our synthesizer needs
SAMPLE_RATE = 44100
BUFFER_SIZE = 256
NUM_BUFFERS = 32  # Pre-allocated buffer pool
WORKER_COUNT = min(8, mp.cpu_count() * 2)  # 2x CPU count, max 8

# Test parameters
WARMUP_TASKS = 10
STRESS_TEST_TASKS = 400
MEMORY_TEST_TASKS = 1000

def init_worker(shared_buffers, buffer_shapes, worker_id_val):
    """
    Worker initialization - pre-import all heavy libraries.
    This runs once when each worker process starts.
    """
    # Store worker ID based on PID
    global worker_id
    worker_id = os.getpid() % 100  # Use PID modulo for unique IDs
    
    # Pre-import heavy libraries (this is the 600ms+ we're avoiding)
    global np, scipy_signal, osc_client
    import numpy as np
    import scipy.signal as scipy_signal
    from pythonosc import udp_client as osc_client
    
    # Store shared memory references as numpy arrays
    global audio_buffers
    audio_buffers = []
    
    for shared_buf, shape in zip(shared_buffers, buffer_shapes):
        # Create numpy view of shared memory (zero-copy)
        np_array = np.frombuffer(shared_buf, dtype=np.float32).reshape(shape)
        audio_buffers.append(np_array)
    
    # Log initialization
    print(f"   Worker initialized (PID: {os.getpid()})")
    
    # Warm up numpy/scipy
    _ = np.zeros(100)
    _ = scipy_signal.butter(4, 0.1)

def process_audio_task(task_id, buffer_index, frequency):
    """
    Simulated audio processing task - generate a sine wave.
    This represents a VCO or other audio module processing.
    """
    try:
        # Access pre-allocated shared buffer
        buffer = audio_buffers[buffer_index % len(audio_buffers)]
        
        # Generate audio (sine wave at specified frequency)
        t = np.linspace(0, BUFFER_SIZE / SAMPLE_RATE, BUFFER_SIZE, endpoint=False)
        samples = 0.5 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
        
        # Apply a simple filter (to exercise scipy)
        b, a = scipy_signal.butter(2, 0.5)
        filtered = scipy_signal.lfilter(b, a, samples)
        
        # Write to shared buffer
        buffer[:] = filtered
        
        return {
            'task_id': task_id,
            'worker_id': worker_id,
            'pid': os.getpid(),
            'success': True
        }
    except Exception as e:
        return {
            'task_id': task_id,
            'worker_id': worker_id,
            'error': str(e),
            'success': False
        }

def dummy_warmup_task():
    """Module-level function for pickling."""
    return None

def create_worker_pool(shared_buffers, buffer_shapes):
    """Create and warm up a worker pool."""
    
    print("\n1. Creating worker pool...")
    start_time = time.perf_counter()
    
    # Set start method
    ctx = mp.get_context('forkserver')
    
    # Create pool with pre-warmed workers
    pool = ctx.Pool(
        processes=WORKER_COUNT,
        initializer=init_worker,
        initargs=(shared_buffers, buffer_shapes, 0),  # Will be overridden
        maxtasksperchild=500  # Balance memory vs respawn overhead
    )
    
    creation_time = time.perf_counter() - start_time
    print(f"   Pool created in {creation_time:.2f}s")
    
    # Warm up the pool with dummy tasks
    print("   Warming up workers...")
    warmup_start = time.perf_counter()
    futures = []
    
    for i in range(WORKER_COUNT):
        # Override worker_id for each worker
        future = pool.apply_async(dummy_warmup_task)
        futures.append(future)
    
    # Wait for warmup
    for future in futures:
        future.get()
    
    warmup_time = time.perf_counter() - warmup_start
    print(f"   Warmup completed in {warmup_time:.3f}s")
    
    return pool, creation_time

def test_task_assignment(pool, num_tasks=10):
    """Test task assignment timing."""
    
    print(f"\n2. Testing task assignment ({num_tasks} tasks)...")
    
    assignment_times = []
    execution_times = []
    
    for i in range(num_tasks):
        # Measure assignment time
        assign_start = time.perf_counter()
        future = pool.apply_async(
            process_audio_task,
            args=(i, i % NUM_BUFFERS, 440 + i * 10)
        )
        assign_time = time.perf_counter() - assign_start
        assignment_times.append(assign_time * 1000)  # Convert to ms
        
        # Measure execution time
        exec_start = time.perf_counter()
        result = future.get(timeout=0.1)
        exec_time = time.perf_counter() - exec_start
        execution_times.append(exec_time * 1000)
        
        if not result['success']:
            print(f"   Task {i} failed: {result.get('error')}")
    
    return assignment_times, execution_times

def long_audio_task(task_id, duration_ms=50):
    """A longer-running task to verify parallelism."""
    import time
    start = time.perf_counter()
    
    # Simulate audio processing
    freq = 440 + task_id * 10
    t = np.linspace(0, 1, SAMPLE_RATE)
    samples = np.sin(2 * np.pi * freq * t)
    
    # Apply multiple filters to take more time
    for _ in range(10):
        b, a = scipy_signal.butter(4, 0.1)
        samples = scipy_signal.lfilter(b, a, samples)
    
    # Sleep to ensure minimum duration
    elapsed = (time.perf_counter() - start) * 1000
    if elapsed < duration_ms:
        time.sleep((duration_ms - elapsed) / 1000)
    
    return {
        'task_id': task_id,
        'worker_id': worker_id,
        'pid': os.getpid(),
        'success': True
    }

def test_concurrent_assignment(pool):
    """Test concurrent task assignment to all workers."""
    
    print(f"\n3. Testing concurrent assignment ({WORKER_COUNT} parallel tasks)...")
    
    start_time = time.perf_counter()
    
    # Submit longer tasks to all workers simultaneously
    futures = []
    for i in range(WORKER_COUNT):
        future = pool.apply_async(
            long_audio_task,
            args=(i, 50)  # 50ms minimum per task
        )
        futures.append(future)
    
    assignment_time = time.perf_counter() - start_time
    
    # Wait for all to complete
    results = [f.get(timeout=1.0) for f in futures]
    total_time = time.perf_counter() - start_time
    
    # Verify all ran in parallel (different PIDs)
    pids = set(r['pid'] for r in results if r['success'])
    
    print(f"   Total assignment time: {assignment_time*1000:.2f}ms")
    print(f"   Total execution time: {total_time*1000:.2f}ms")
    print(f"   Unique PIDs used: {len(pids)}")
    
    # If truly parallel, 8 tasks of 50ms each should complete in ~50ms, not 400ms
    parallelism_ratio = (len(results) * 50) / (total_time * 1000)
    print(f"   Parallelism efficiency: {parallelism_ratio:.1f}x")
    
    return assignment_time * 1000, len(pids)

def test_memory_growth(pool, num_tasks=100):
    """Test memory growth over many tasks."""
    
    print(f"\n4. Testing memory growth ({num_tasks} tasks)...")
    
    # Get initial memory usage
    process = psutil.Process()
    children = process.children(recursive=True)
    initial_memory = sum(p.memory_info().rss for p in children) / 1024 / 1024  # MB
    
    # Process many tasks
    for i in range(num_tasks):
        future = pool.apply_async(
            process_audio_task,
            args=(i, i % NUM_BUFFERS, 440)
        )
        _ = future.get(timeout=0.1)
        
        # Periodic memory check
        if i % 100 == 99:
            gc.collect()  # Force garbage collection
            current_memory = sum(p.memory_info().rss for p in process.children(recursive=True)) / 1024 / 1024
            growth = current_memory - initial_memory
            print(f"   After {i+1} tasks: {growth:.1f}MB growth")
    
    # Final memory check
    final_memory = sum(p.memory_info().rss for p in process.children(recursive=True)) / 1024 / 1024
    total_growth = final_memory - initial_memory
    growth_per_task = total_growth / num_tasks * 100  # Per 100 tasks
    
    print(f"   Total memory growth: {total_growth:.1f}MB")
    print(f"   Growth rate: {growth_per_task:.2f}MB per 100 tasks")
    
    return total_growth, growth_per_task

def crash_worker_task():
    """Module-level function that crashes the worker."""
    os.kill(os.getpid(), signal.SIGKILL)

def test_worker_crash_recovery():
    """Test pool recovery from worker crash."""
    
    print("\n5. Testing worker crash recovery...")
    
    # Create a pool using ProcessPoolExecutor for better error handling
    shared_buffers, buffer_shapes = create_shared_buffers()
    
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=4,
        initializer=init_worker,
        initargs=(shared_buffers, buffer_shapes, 0)
    ) as executor:
        
        # Submit a normal task
        future1 = executor.submit(process_audio_task, 1, 0, 440)
        result1 = future1.result(timeout=1)
        print(f"   Normal task completed: {result1['success']}")
        
        # Submit a task that will crash
        try:
            future2 = executor.submit(crash_worker_task)
            future2.result(timeout=1)
        except concurrent.futures.process.BrokenProcessPool:
            print("   Worker crash detected (BrokenProcessPool raised)")
            return True
        except Exception as e:
            print(f"   Unexpected error: {e}")
            return False
    
    return False

def create_shared_buffers():
    """Create pre-allocated shared memory buffers."""
    
    shared_buffers = []
    buffer_shapes = []
    
    for i in range(NUM_BUFFERS):
        # Create shared memory array
        shared_array = mp.Array(ctypes.c_float, BUFFER_SIZE, lock=False)
        shared_buffers.append(shared_array)
        buffer_shapes.append((BUFFER_SIZE,))
    
    return shared_buffers, buffer_shapes

def main():
    """Run complete worker pool test suite."""
    
    print("\n" + "="*60)
    print("PROC-02: WORKER POOL TASK ASSIGNMENT TEST")
    print("="*60)
    print(f"Workers: {WORKER_COUNT}")
    print(f"Buffer pool: {NUM_BUFFERS} x {BUFFER_SIZE} samples")
    print(f"Target: <10ms task assignment")
    print("="*60)
    
    # Create shared memory BEFORE pool (critical!)
    print("\nPre-allocating shared memory buffers...")
    shared_buffers, buffer_shapes = create_shared_buffers()
    print(f"Created {NUM_BUFFERS} shared buffers")
    
    # Test 1: Pool creation
    pool, creation_time = create_worker_pool(shared_buffers, buffer_shapes)
    
    # Test 2: Cold assignment (first task)
    print("\n" + "-"*40)
    print("COLD ASSIGNMENT TEST:")
    cold_times, _ = test_task_assignment(pool, num_tasks=1)
    print(f"First task assignment: {cold_times[0]:.2f}ms")
    
    # Test 3: Warm assignment
    print("\n" + "-"*40)
    print("WARM ASSIGNMENT TEST:")
    warm_times, exec_times = test_task_assignment(pool, num_tasks=WARMUP_TASKS)
    
    # Test 4: Concurrent assignment
    print("\n" + "-"*40)
    print("CONCURRENT ASSIGNMENT TEST:")
    concurrent_time, parallel_count = test_concurrent_assignment(pool)
    
    # Test 5: Memory growth
    print("\n" + "-"*40)
    print("MEMORY GROWTH TEST:")
    memory_growth, growth_rate = test_memory_growth(pool, STRESS_TEST_TASKS)
    
    # Test 6: Crash recovery (separate pool)
    print("\n" + "-"*40)
    print("CRASH RECOVERY TEST:")
    recovery_works = test_worker_crash_recovery()
    
    # Clean up
    pool.terminate()
    pool.join()
    
    # Results summary
    print("\n" + "="*60)
    print("RESULTS SUMMARY:")
    print("-"*60)
    
    # Timing results
    print(f"Pool creation time: {creation_time:.2f}s")
    print(f"Cold assignment: {cold_times[0]:.2f}ms")
    print(f"Warm assignment (avg): {mean(warm_times):.2f}ms")
    print(f"Warm assignment (median): {median(warm_times):.2f}ms")
    print(f"Concurrent assignment: {concurrent_time:.2f}ms for {WORKER_COUNT} tasks")
    
    # Memory results
    print(f"Memory growth: {memory_growth:.1f}MB over {STRESS_TEST_TASKS} tasks")
    print(f"Growth rate: {growth_rate:.2f}MB per 100 tasks")
    
    # Crash recovery
    print(f"Crash recovery: {'✓ Working' if recovery_works else '✗ Failed'}")
    
    print("-"*60)
    
    # Pass/Fail determination
    success = True
    
    if creation_time > 3.0:
        print(f"⚠️  Pool creation {creation_time:.2f}s exceeds 3s target")
        success = False
    else:
        print(f"✓ Pool creation {creation_time:.2f}s within 3s target")
    
    if cold_times[0] > 10.0:
        print(f"⚠️  Cold assignment {cold_times[0]:.2f}ms exceeds 10ms target")
        success = False
    else:
        print(f"✓ Cold assignment {cold_times[0]:.2f}ms meets 10ms target")
    
    if mean(warm_times) > 2.0:
        print(f"⚠️  Warm assignment {mean(warm_times):.2f}ms exceeds 2ms target")
        success = False
    else:
        print(f"✓ Warm assignment {mean(warm_times):.2f}ms meets 2ms target")
    
    if concurrent_time > 10.0:
        print(f"⚠️  Concurrent assignment {concurrent_time:.2f}ms exceeds 10ms target")
        success = False
    else:
        print(f"✓ Concurrent assignment {concurrent_time:.2f}ms meets 10ms target")
    
    if growth_rate > 1.0:
        print(f"⚠️  Memory growth rate {growth_rate:.2f}MB/100 tasks is concerning")
    else:
        print(f"✓ Memory growth rate {growth_rate:.2f}MB/100 tasks is acceptable")
    
    if parallel_count < WORKER_COUNT:
        print(f"⚠️  Only {parallel_count}/{WORKER_COUNT} workers ran in parallel")
        success = False
    else:
        print(f"✓ All {parallel_count} workers ran in parallel")
    
    print("="*60)
    
    if success:
        print("\n✓ PROC-02 PASSED: Worker pool meets real-time requirements!")
        print("\nWhat this means:")
        print("• We can assign modules to workers in <10ms")
        print("• No 600ms library import delay")
        print("• Multiple modules can process in parallel")
        print("• Memory growth is manageable with maxtasksperchild")
    else:
        print("\n✗ PROC-02 FAILED: Worker pool needs optimization")
    
    return success

if __name__ == "__main__":
    # Set start method before any multiprocessing
    mp.set_start_method('forkserver', force=True)
    
    success = main()
    exit(0 if success else 1)