#!/usr/bin/env python3
"""
PROC-04: Resource Cleanup Test
Testing reliable resource cleanup on teardown and abnormal exits

Focus Areas:
- Zero leaks after 50 teardown/re-init cycles
- SIGKILL cleanup via JSON registry
- File descriptor stability
- Memory growth prevention
"""

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import os
import sys
import time
import json
import psutil
import signal
import gc
from pathlib import Path
from multiprocessing import shared_memory
import socket
import tempfile
import subprocess
from statistics import mean, stdev

# Configuration
NUM_CYCLES = 50  # Number of teardown/re-init cycles
NUM_WORKERS = 4
NUM_SHM_SEGMENTS = 8
SHM_SIZE = 1024 * 1024  # 1MB per segment
SHM_PREFIX = "chronus_"
REGISTRY_PATH = "/tmp/chronus_shm_registry.json"

# Set environment for workers
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'


def warmup_task():
    """Simple task for warming up process pool"""
    return True


def double_value(x):
    """Simple task that doubles a value"""
    return x * 2


class ResourceMonitor:
    """Monitor system resources for leak detection"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.baseline_fds = None
        self.baseline_memory = None
        self.baseline_shm_count = None
    
    def capture_baseline(self):
        """Capture baseline resource usage"""
        self.baseline_fds = self.get_fd_count()
        self.baseline_memory = self.get_memory_usage()
        self.baseline_shm_count = self.get_shm_count()
        
        return {
            'fds': self.baseline_fds,
            'memory_mb': self.baseline_memory / 1024 / 1024,
            'shm_segments': self.baseline_shm_count
        }
    
    def get_fd_count(self):
        """Get current file descriptor count"""
        try:
            return self.process.num_fds()
        except:
            # Fallback for systems without num_fds
            fd_dir = f'/proc/{self.process.pid}/fd'
            if os.path.exists(fd_dir):
                return len(os.listdir(fd_dir))
            return 0
    
    def get_memory_usage(self):
        """Get current RSS memory usage"""
        return self.process.memory_info().rss
    
    def get_shm_count(self):
        """Count chronus_* segments in /dev/shm"""
        shm_dir = Path('/dev/shm')
        if not shm_dir.exists():
            return 0
        
        count = 0
        for item in shm_dir.iterdir():
            if item.name.startswith(SHM_PREFIX):
                count += 1
        return count
    
    def check_leaks(self):
        """Check for resource leaks against baseline"""
        current_fds = self.get_fd_count()
        current_memory = self.get_memory_usage()
        current_shm = self.get_shm_count()
        
        results = {
            'fd_delta': current_fds - self.baseline_fds if self.baseline_fds else 0,
            'memory_delta_mb': (current_memory - self.baseline_memory) / 1024 / 1024 if self.baseline_memory else 0,
            'shm_delta': current_shm - self.baseline_shm_count if self.baseline_shm_count is not None else 0,
            'current_fds': current_fds,
            'current_memory_mb': current_memory / 1024 / 1024,
            'current_shm': current_shm
        }
        
        # Check for leaks
        results['has_fd_leak'] = abs(results['fd_delta']) > 5
        results['has_memory_leak'] = results['memory_delta_mb'] > self.baseline_memory * 0.1 / 1024 / 1024
        results['has_shm_leak'] = results['shm_delta'] > 0
        
        return results


class SharedMemoryManager:
    """Manage shared memory with registry for cleanup"""
    
    def __init__(self):
        self.segments = {}
        self.registry_path = Path(REGISTRY_PATH)
        self.load_registry()
    
    def load_registry(self):
        """Load registry from disk"""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    data = json.load(f)
                    # Clean up any orphans
                    for name in list(data.keys()):
                        self.cleanup_segment(name)
            except:
                pass
    
    def create_segment(self, name, size):
        """Create a new shared memory segment"""
        full_name = f"{SHM_PREFIX}{name}"
        
        # Clean up if exists
        self.cleanup_segment(full_name)
        
        # Create new segment
        shm = shared_memory.SharedMemory(create=True, size=size, name=full_name)
        self.segments[full_name] = shm
        
        # Update registry
        self.update_registry(full_name, size, os.getpid())
        
        return shm
    
    def cleanup_segment(self, name):
        """Clean up a shared memory segment"""
        try:
            # Try to unlink existing segment
            shm = shared_memory.SharedMemory(name=name)
            shm.close()
            shm.unlink()
        except FileNotFoundError:
            pass  # Already cleaned
        except:
            pass  # Other error, ignore
        
        # Remove from local tracking
        if name in self.segments:
            try:
                self.segments[name].close()
                self.segments[name].unlink()
            except:
                pass
            del self.segments[name]
        
        # Remove from registry
        self.remove_from_registry(name)
    
    def update_registry(self, name, size, pid):
        """Update the JSON registry"""
        registry = {}
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    registry = json.load(f)
            except:
                pass
        
        registry[name] = {
            'size': size,
            'pid': pid,
            'created': time.time()
        }
        
        # Atomic write
        temp_path = self.registry_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(registry, f)
        temp_path.rename(self.registry_path)
    
    def remove_from_registry(self, name):
        """Remove entry from registry"""
        if not self.registry_path.exists():
            return
        
        try:
            with open(self.registry_path, 'r') as f:
                registry = json.load(f)
            
            if name in registry:
                del registry[name]
                
                # Atomic write
                temp_path = self.registry_path.with_suffix('.tmp')
                with open(temp_path, 'w') as f:
                    json.dump(registry, f)
                temp_path.rename(self.registry_path)
        except:
            pass
    
    def cleanup_all(self):
        """Clean up all managed segments"""
        for name in list(self.segments.keys()):
            self.cleanup_segment(name)
        
        # Clean up registry file
        if self.registry_path.exists():
            os.unlink(self.registry_path)


class AudioSystem:
    """Simulated audio system with full resource stack"""
    
    def __init__(self):
        self.executor = None
        self.shm_manager = SharedMemoryManager()
        self.osc_sockets = []
        self.init_time = None
    
    def initialize(self):
        """Initialize all components"""
        start = time.time()
        
        # Create process pool
        self.executor = ProcessPoolExecutor(max_workers=NUM_WORKERS)
        
        # Create shared memory segments
        for i in range(NUM_SHM_SEGMENTS):
            self.shm_manager.create_segment(f"audio_{i}", SHM_SIZE)
        
        # Create OSC sockets (simplified - just create, don't bind)
        for i in range(2):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.osc_sockets.append(sock)
        
        # Submit some work to warm up pool
        futures = [self.executor.submit(warmup_task) for _ in range(NUM_WORKERS)]
        for f in futures:
            f.result()
        
        self.init_time = time.time() - start
        return self.init_time
    
    def teardown(self):
        """Clean teardown of all resources"""
        start = time.time()
        
        # Shutdown executor
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None
        
        # Close sockets
        for sock in self.osc_sockets:
            try:
                sock.close()
            except:
                pass
        self.osc_sockets = []
        
        # Clean up shared memory
        self.shm_manager.cleanup_all()
        
        teardown_time = time.time() - start
        return teardown_time


def test_teardown_reinit_cycles():
    """Test 50 teardown/re-init cycles for leaks"""
    print("\n=== Testing Teardown/Re-init Cycles ===")
    
    monitor = ResourceMonitor()
    baseline = monitor.capture_baseline()
    print(f"Baseline: {json.dumps(baseline, indent=2)}")
    
    system = AudioSystem()
    init_times = []
    teardown_times = []
    
    print(f"\nRunning {NUM_CYCLES} cycles...")
    
    for i in range(NUM_CYCLES):
        # Initialize
        init_time = system.initialize()
        init_times.append(init_time)
        
        # Run briefly
        time.sleep(0.01)
        
        # Teardown
        teardown_time = system.teardown()
        teardown_times.append(teardown_time)
        
        # Check for leaks every 10 cycles
        if (i + 1) % 10 == 0:
            leaks = monitor.check_leaks()
            print(f"  Cycle {i+1}: FDs={leaks['current_fds']} "
                  f"(Δ{leaks['fd_delta']:+d}), "
                  f"Mem={leaks['current_memory_mb']:.1f}MB "
                  f"(Δ{leaks['memory_delta_mb']:+.1f}), "
                  f"SHM={leaks['current_shm']} "
                  f"(Δ{leaks['shm_delta']:+d})")
    
    # Final leak check
    final = monitor.check_leaks()
    
    print(f"\n### Results after {NUM_CYCLES} cycles ###")
    print(f"Init times: mean={mean(init_times)*1000:.1f}ms, "
          f"max={max(init_times)*1000:.1f}ms")
    print(f"Teardown times: mean={mean(teardown_times)*1000:.1f}ms, "
          f"max={max(teardown_times)*1000:.1f}ms")
    print(f"FD leak: {final['fd_delta']:+d} "
          f"({'LEAK' if final['has_fd_leak'] else 'OK'})")
    print(f"Memory delta: {final['memory_delta_mb']:+.1f}MB "
          f"({'LEAK' if final['has_memory_leak'] else 'OK'})")
    print(f"SHM leak: {final['shm_delta']:+d} "
          f"({'LEAK' if final['has_shm_leak'] else 'OK'})")
    
    # Assertions
    assert max(init_times) < 1.5, f"Init too slow: {max(init_times)}s"
    assert max(teardown_times) < 0.5, f"Teardown too slow: {max(teardown_times)}s"
    assert not final['has_fd_leak'], f"FD leak detected: {final['fd_delta']}"
    assert not final['has_shm_leak'], f"SHM leak detected: {final['shm_delta']}"
    
    print("✅ Teardown/Re-init test PASSED")
    return True


def test_sigkill_cleanup():
    """Test cleanup after SIGKILL with registry"""
    print("\n=== Testing SIGKILL Cleanup ===")
    
    monitor = ResourceMonitor()
    baseline_shm = monitor.get_shm_count()
    print(f"Baseline SHM count: {baseline_shm}")
    
    # Create a worker process with shared memory
    def worker_with_shm():
        """Worker that creates SHM and gets killed"""
        manager = SharedMemoryManager()
        
        # Create some segments
        for i in range(3):
            manager.create_segment(f"worker_{os.getpid()}_{i}", 1024)
        
        # Wait to be killed
        time.sleep(10)
    
    # Start worker
    proc = mp.Process(target=worker_with_shm)
    proc.start()
    
    # Let it create segments
    time.sleep(0.5)
    
    # Check segments were created
    during_shm = monitor.get_shm_count()
    print(f"SHM count with worker: {during_shm}")
    assert during_shm > baseline_shm, "Worker didn't create segments"
    
    # SIGKILL the worker
    os.kill(proc.pid, signal.SIGKILL)
    proc.join(timeout=1)
    
    print(f"Worker {proc.pid} killed with SIGKILL")
    
    # Load registry and clean up orphans
    manager = SharedMemoryManager()
    
    # Check all segments cleaned
    final_shm = monitor.get_shm_count()
    print(f"SHM count after cleanup: {final_shm}")
    
    leak_count = final_shm - baseline_shm
    
    if leak_count > 0:
        # List leaked segments for debugging
        shm_dir = Path('/dev/shm')
        for item in shm_dir.iterdir():
            if item.name.startswith(SHM_PREFIX):
                print(f"  Leaked: {item.name}")
    
    assert leak_count == 0, f"Found {leak_count} leaked segments after SIGKILL"
    
    print("✅ SIGKILL cleanup test PASSED")
    return True


def test_fd_stability():
    """Test file descriptor stability over many operations"""
    print("\n=== Testing File Descriptor Stability ===")
    
    monitor = ResourceMonitor()
    baseline_fds = monitor.get_fd_count()
    print(f"Baseline FD count: {baseline_fds}")
    
    fd_history = []
    
    print("Running 50 operation cycles...")
    
    for i in range(50):
        # Create and destroy various resources
        
        # Executor operations
        executor = ProcessPoolExecutor(max_workers=2)
        futures = [executor.submit(double_value, i) for i in range(10)]
        for f in futures:
            f.result()
        executor.shutdown(wait=True)
        
        # Shared memory operations
        segments = []
        for j in range(3):
            name = f"{SHM_PREFIX}test_{i}_{j}"
            try:
                shm = shared_memory.SharedMemory(create=True, size=1024, name=name)
                segments.append(shm)
            except:
                pass
        
        for shm in segments:
            try:
                shm.close()
                shm.unlink()
            except:
                pass
        
        # Socket operations
        sockets = []
        for j in range(2):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sockets.append(sock)
        
        for sock in sockets:
            sock.close()
        
        # Check FD count
        current_fds = monitor.get_fd_count()
        fd_history.append(current_fds)
        
        if (i + 1) % 10 == 0:
            delta = current_fds - baseline_fds
            print(f"  Cycle {i+1}: FDs={current_fds} (Δ{delta:+d})")
    
    # Final check
    final_fds = monitor.get_fd_count()
    final_delta = final_fds - baseline_fds
    
    print(f"\n### FD Stability Results ###")
    print(f"Baseline: {baseline_fds}")
    print(f"Final: {final_fds}")
    print(f"Delta: {final_delta:+d}")
    print(f"Max during test: {max(fd_history)}")
    print(f"FD variation: {stdev(fd_history):.2f}")
    
    # Check for zombie processes
    zombies = []
    for proc in psutil.process_iter(['pid', 'name', 'status']):
        try:
            if proc.info['status'] == psutil.STATUS_ZOMBIE:
                zombies.append(proc.info)
        except:
            pass
    
    if zombies:
        print(f"WARNING: Found {len(zombies)} zombie processes")
    
    assert abs(final_delta) <= 5, f"FD leak detected: {final_delta:+d}"
    assert len(zombies) == 0, f"Found {len(zombies)} zombie processes"
    
    print("✅ FD stability test PASSED")
    return True


def test_memory_stability():
    """Test memory stability over allocation cycles"""
    print("\n=== Testing Memory Stability ===")
    
    monitor = ResourceMonitor()
    initial_memory = monitor.get_memory_usage()
    print(f"Initial memory: {initial_memory/1024/1024:.1f}MB")
    
    # Force garbage collection for clean baseline
    gc.collect()
    
    memory_history = []
    
    print("Running 100 allocation cycles...")
    
    for i in range(100):
        # Create various objects
        executor = ProcessPoolExecutor(max_workers=2)
        
        # Allocate and process data
        data = [list(range(10000)) for _ in range(10)]
        futures = [executor.submit(sum, d) for d in data]
        results = [f.result() for f in futures]
        
        executor.shutdown(wait=True)
        
        # Force cleanup
        del executor
        del data
        del futures
        del results
        
        # Periodic GC
        if i % 10 == 0:
            gc.collect()
            current_memory = monitor.get_memory_usage()
            memory_history.append(current_memory)
            delta_mb = (current_memory - initial_memory) / 1024 / 1024
            print(f"  Cycle {i}: Memory={current_memory/1024/1024:.1f}MB "
                  f"(Δ{delta_mb:+.1f}MB)")
    
    # Final GC and check
    gc.collect()
    final_memory = monitor.get_memory_usage()
    memory_growth = (final_memory - initial_memory) / initial_memory
    
    print(f"\n### Memory Stability Results ###")
    print(f"Initial: {initial_memory/1024/1024:.1f}MB")
    print(f"Final: {final_memory/1024/1024:.1f}MB")
    print(f"Growth: {memory_growth*100:.1f}%")
    
    # Check for monotonic growth
    is_monotonic = all(memory_history[i] <= memory_history[i+1] 
                      for i in range(len(memory_history)-1))
    
    if is_monotonic:
        print("WARNING: Monotonic memory growth detected")
    
    assert memory_growth < 0.1, f"Memory leak detected: {memory_growth*100:.1f}% growth"
    
    print("✅ Memory stability test PASSED")
    return True


def main():
    """Run PROC-04 Resource Cleanup tests"""
    print("PROC-04: Resource Cleanup Test")
    print("=" * 50)
    
    # Clean up any previous test artifacts
    if Path(REGISTRY_PATH).exists():
        os.unlink(REGISTRY_PATH)
    
    # Clean up any leaked SHM segments
    shm_dir = Path('/dev/shm')
    if shm_dir.exists():
        for item in shm_dir.iterdir():
            if item.name.startswith(SHM_PREFIX):
                try:
                    os.unlink(item)
                except:
                    pass
    
    tests = [
        ("Teardown/Re-init Cycles", test_teardown_reinit_cycles),
        ("SIGKILL Cleanup", test_sigkill_cleanup),
        ("FD Stability", test_fd_stability),
        ("Memory Stability", test_memory_stability)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ PROC-04 TEST SUITE PASSED")
        print("\nKey Achievements:")
        print("- Zero leaks after 50 teardown/re-init cycles")
        print("- SIGKILL cleanup via registry works")
        print("- File descriptors remain stable")
        print("- Memory usage stays bounded")
        print("- Re-init time consistently <1.5s")
    else:
        print("❌ PROC-04 TEST SUITE FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()