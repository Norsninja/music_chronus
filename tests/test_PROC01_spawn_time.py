#!/usr/bin/env python3
"""
PROC-01: Module Process Spawn Time Test
Testing how fast we can create synthesizer module processes

Based on research:
- Fork: ~2ms but unsafe with threads
- Spawn: ~42ms but safe
- Forkserver: ~10-20ms, good compromise
- Process pools: <10ms for warm assignment
"""

import multiprocessing as mp
import time
import numpy as np
import sys
from statistics import mean, stdev
import platform

# Test configuration
NUM_SPAWN_TESTS = 5
NUM_POOL_TESTS = 10
SPAWN_TARGET = 0.100  # 100ms target
POOL_TARGET = 0.010   # 10ms for pool assignment

def minimal_module_process():
    """Minimal module just to test spawn time"""
    pass

def realistic_module_process():
    """Realistic module with library imports"""
    import numpy as np
    import scipy.signal
    from pythonosc import udp_client
    
    # Simulate module initialization
    buffer = np.zeros(256, dtype=np.float32)
    return True

def module_worker_init():
    """Initialize worker with pre-imported libraries"""
    global np, scipy_signal, osc_client
    import numpy as np
    import scipy.signal as scipy_signal
    from pythonosc import udp_client
    
    # Pre-create commonly used objects
    osc_client = udp_client.SimpleUDPClient("127.0.0.1", 5000)
    
def module_worker_task(module_type):
    """Task executed by pool worker"""
    # Simulate module work using pre-imported libraries
    if module_type == "vco":
        # Generate sine wave
        t = np.linspace(0, 1, 256)
        signal = np.sin(2 * np.pi * 440 * t)
    elif module_type == "vcf":
        # Design filter using pre-imported scipy
        b, a = scipy_signal.butter(4, 0.1)
    
    return f"{module_type} initialized"

def test_spawn_methods():
    """Test different multiprocessing start methods"""
    
    print("\n1. Testing spawn methods...")
    print("-" * 40)
    
    results = {}
    
    # Test available methods based on platform
    if platform.system() == "Linux":
        methods = ["fork", "spawn", "forkserver"]
    elif platform.system() == "Darwin":  # macOS
        methods = ["spawn", "forkserver"]  # fork is problematic on macOS
    else:  # Windows
        methods = ["spawn"]
    
    for method in methods:
        try:
            mp.set_start_method(method, force=True)
            times = []
            
            for i in range(NUM_SPAWN_TESTS):
                start = time.perf_counter()
                
                # Spawn a minimal process
                p = mp.Process(target=minimal_module_process)
                p.start()
                p.join()
                
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            
            avg_time = mean(times) * 1000  # Convert to ms
            results[method] = {
                'mean': avg_time,
                'min': min(times) * 1000,
                'max': max(times) * 1000
            }
            
            print(f"   {method:10s}: {avg_time:6.2f}ms (min: {results[method]['min']:.2f}ms, max: {results[method]['max']:.2f}ms)")
            
        except Exception as e:
            print(f"   {method:10s}: Failed - {e}")
    
    return results

def test_cold_spawn():
    """Test spawning a realistic module from cold start"""
    
    print("\n2. Testing cold spawn with library imports...")
    print("-" * 40)
    
    # Use spawn for safety
    mp.set_start_method("spawn", force=True)
    
    times = []
    for i in range(3):  # Only 3 tests as this is slow
        start = time.perf_counter()
        
        # Spawn process with realistic initialization
        p = mp.Process(target=realistic_module_process)
        p.start()
        p.join()
        
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"   Run {i+1}: {elapsed*1000:.2f}ms")
    
    avg_time = mean(times) * 1000
    print(f"   Average: {avg_time:.2f}ms")
    
    return avg_time

def test_process_pool():
    """Test using a pre-warmed process pool"""
    
    print("\n3. Testing pre-warmed process pool...")
    print("-" * 40)
    
    # Create pool with pre-imported libraries
    print("   Creating pool with 4 workers (includes library imports)...")
    pool_create_start = time.perf_counter()
    
    with mp.Pool(processes=4, initializer=module_worker_init) as pool:
        pool_create_time = time.perf_counter() - pool_create_start
        print(f"   Pool creation time: {pool_create_time*1000:.2f}ms (one-time cost)")
        
        # Test module assignment times
        assignment_times = []
        module_types = ["vco", "vcf", "vca", "lfo", "adsr"] * 2  # 10 modules
        
        print(f"   Testing {len(module_types)} module assignments...")
        
        for module_type in module_types:
            start = time.perf_counter()
            
            # Assign module to pool worker
            result = pool.apply(module_worker_task, (module_type,))
            
            elapsed = time.perf_counter() - start
            assignment_times.append(elapsed)
        
        avg_assignment = mean(assignment_times) * 1000
        max_assignment = max(assignment_times) * 1000
        
        print(f"   Average assignment: {avg_assignment:.2f}ms")
        print(f"   Max assignment: {max_assignment:.2f}ms")
        
        return avg_assignment, pool_create_time * 1000

def test_parallel_spawn():
    """Test spawning multiple modules in parallel"""
    
    print("\n4. Testing parallel module creation...")
    print("-" * 40)
    
    mp.set_start_method("spawn", force=True)
    
    # Spawn 5 modules as fast as possible
    module_names = ["VCO", "VCF", "VCA", "LFO", "ADSR"]
    
    start = time.perf_counter()
    
    processes = []
    for name in module_names:
        p = mp.Process(target=minimal_module_process, name=name)
        p.start()
        processes.append(p)
        print(f"   Started {name}")
    
    # Wait for all to complete
    for p in processes:
        p.join()
    
    total_time = time.perf_counter() - start
    print(f"   Total time for 5 modules: {total_time*1000:.2f}ms")
    print(f"   Average per module: {total_time*1000/5:.2f}ms")
    
    return total_time * 1000

def main():
    """Run all spawn time tests"""
    
    print("="*60)
    print("PROC-01: MODULE PROCESS SPAWN TIME TEST")
    print("="*60)
    print(f"Platform: {platform.system()}")
    print(f"Target: <{SPAWN_TARGET*1000}ms per module")
    print(f"Pool target: <{POOL_TARGET*1000}ms assignment")
    print("="*60)
    
    # Test different spawn methods
    spawn_results = test_spawn_methods()
    
    # Test cold spawn with imports
    cold_spawn_time = test_cold_spawn()
    
    # Test process pool
    pool_assignment_time, pool_create_time = test_process_pool()
    
    # Test parallel spawning
    parallel_time = test_parallel_spawn()
    
    # Results summary
    print("\n" + "="*60)
    print("RESULTS SUMMARY:")
    print("-"*60)
    
    # Find best spawn method
    if spawn_results:
        best_method = min(spawn_results.items(), key=lambda x: x[1]['mean'])
        print(f"Best spawn method: {best_method[0]} at {best_method[1]['mean']:.2f}ms")
    
    print(f"Cold spawn (with imports): {cold_spawn_time:.2f}ms")
    print(f"Pool creation: {pool_create_time:.2f}ms (one-time cost)")
    print(f"Pool assignment: {pool_assignment_time:.2f}ms per module")
    print(f"Parallel 5 modules: {parallel_time:.2f}ms total")
    
    print("-"*60)
    
    # Pass/Fail determination
    passed = True
    
    if cold_spawn_time > SPAWN_TARGET * 1000:
        print(f"⚠️  Cold spawn {cold_spawn_time:.2f}ms exceeds {SPAWN_TARGET*1000}ms target")
        print("   → Solution: Use process pools")
    
    if pool_assignment_time < POOL_TARGET * 1000:
        print(f"✓ PASS: Pool assignment {pool_assignment_time:.2f}ms meets {POOL_TARGET*1000}ms target!")
    else:
        print(f"✗ FAIL: Pool assignment {pool_assignment_time:.2f}ms exceeds target")
        passed = False
    
    print("\nRecommendations:")
    if platform.system() == "Linux" and "fork" in spawn_results:
        if spawn_results["fork"]["mean"] < 5:
            print("• Fork is fastest (~2ms) but use with caution (thread safety)")
    
    print("• Use process pools for production (pre-warmed workers)")
    print("• Pool size = CPU cores for optimal performance")
    print("• Pre-import all libraries in worker initializer")
    
    print("="*60)
    
    return passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)