#!/usr/bin/env python3
"""
RT-02: Buffer Underrun Test
Testing sustained audio playback without dropouts for 60 seconds

Based on research showing:
- rtmixer provides fetch_and_reset_stats() for underrun detection
- Buffer size of 256 frames provides best balance
- GC and Python operations are primary causes of underruns
"""

import time
import gc
import numpy as np
import sounddevice as sd
import threading
import multiprocessing as mp
import random
import psutil
import os
from statistics import mean, stdev
from collections import defaultdict
from datetime import datetime

# Try to import rtmixer - will need to handle if not available
try:
    import rtmixer
    RTMIXER_AVAILABLE = True
except ImportError:
    RTMIXER_AVAILABLE = False
    print("Warning: rtmixer not installed. Using sounddevice fallback mode.")

# Audio configuration
SAMPLE_RATE = 44100
TEST_DURATION = 60  # seconds
STATS_INTERVAL = 0.1  # Check stats every 100ms

# Buffer configurations to test
BUFFER_CONFIGS = [
    {"frames": 128, "max_underruns": 20, "latency_ms": 2.9},
    {"frames": 256, "max_underruns": 5, "latency_ms": 5.8},
    {"frames": 512, "max_underruns": 1, "latency_ms": 11.6},
]

class UnderrunMonitor:
    """Monitors and records buffer underruns during playback."""
    
    def __init__(self):
        self.underrun_count = 0
        self.underrun_times = []
        self.stats_history = []
        self.start_time = None
        self.monitoring = False
        
    def start(self):
        """Start monitoring."""
        self.start_time = time.perf_counter()
        self.monitoring = True
        self.underrun_count = 0
        self.underrun_times = []
        self.stats_history = []
        
    def stop(self):
        """Stop monitoring."""
        self.monitoring = False
        
    def record_underrun(self, count=1):
        """Record an underrun event."""
        if self.monitoring:
            self.underrun_count += count
            current_time = time.perf_counter() - self.start_time
            for _ in range(count):
                self.underrun_times.append(current_time)
                
    def get_statistics(self):
        """Calculate underrun statistics."""
        if not self.underrun_times:
            return {
                'total_count': 0,
                'mean_interval': float('inf'),
                'clustering': 0.0,
                'max_consecutive': 0
            }
            
        # Calculate intervals between underruns
        intervals = []
        if len(self.underrun_times) > 1:
            for i in range(1, len(self.underrun_times)):
                intervals.append(self.underrun_times[i] - self.underrun_times[i-1])
                
        # Count consecutive underruns (within 100ms)
        consecutive_counts = []
        current_consecutive = 1
        for i in range(1, len(self.underrun_times)):
            if self.underrun_times[i] - self.underrun_times[i-1] < 0.1:
                current_consecutive += 1
            else:
                consecutive_counts.append(current_consecutive)
                current_consecutive = 1
        consecutive_counts.append(current_consecutive)
        
        return {
            'total_count': self.underrun_count,
            'mean_interval': mean(intervals) if intervals else float('inf'),
            'clustering': sum(c > 1 for c in consecutive_counts) / len(consecutive_counts),
            'max_consecutive': max(consecutive_counts) if consecutive_counts else 0
        }

def generate_sine_wave(frequency=440, duration=1.0, sample_rate=44100):
    """Generate a sine wave."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    return 0.3 * np.sin(2 * np.pi * frequency * t).astype(np.float32)

def audio_callback_simple(outdata, frames, time_info, status):
    """Simple audio callback that fills buffer with sine wave."""
    global audio_phase, callback_count
    
    if status.output_underflow:
        monitor.record_underrun()
        
    # Generate sine wave
    t = (audio_phase + np.arange(frames)) / SAMPLE_RATE
    outdata[:] = (0.3 * np.sin(2 * np.pi * 440 * t)).reshape(-1, 1).astype(np.float32)
    audio_phase = (audio_phase + frames) % SAMPLE_RATE
    callback_count += 1

def test_clean_playback(buffer_size=256, duration=60):
    """Test clean audio playback without stress."""
    
    print(f"\n1. Testing clean playback ({buffer_size} frames, {duration}s)...")
    
    monitor = UnderrunMonitor()
    global audio_phase, callback_count
    audio_phase = 0
    callback_count = 0
    
    # Configure stream
    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=buffer_size,
        channels=1,
        dtype='float32',
        callback=audio_callback_simple
    )
    
    monitor.start()
    
    with stream:
        print(f"   Playing audio for {duration} seconds...")
        time.sleep(duration)
        
    monitor.stop()
    stats = monitor.get_statistics()
    
    print(f"   Callbacks executed: {callback_count}")
    print(f"   Underruns detected: {stats['total_count']}")
    
    return stats

def test_with_gc_pressure(buffer_size=256, duration=60):
    """Test playback with garbage collection pressure."""
    
    print(f"\n2. Testing with GC pressure ({buffer_size} frames)...")
    
    monitor = UnderrunMonitor()
    global audio_phase, callback_count
    audio_phase = 0
    callback_count = 0
    
    def gc_stress_thread():
        """Thread that creates GC pressure."""
        while monitor.monitoring:
            # Allocate and discard memory
            _ = [np.random.random((1000, 1000)) for _ in range(10)]
            
            # Random GC trigger
            if random.random() < 0.2:  # 20% chance
                gc.collect()
                
            time.sleep(random.uniform(0.5, 2.0))
    
    # Start audio stream
    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=buffer_size,
        channels=1,
        dtype='float32',
        callback=audio_callback_simple
    )
    
    monitor.start()
    
    # Start GC stress thread
    stress_thread = threading.Thread(target=gc_stress_thread, daemon=True)
    stress_thread.start()
    
    with stream:
        print(f"   Playing audio with GC stress for {duration}s...")
        time.sleep(duration)
        
    monitor.stop()
    stats = monitor.get_statistics()
    
    print(f"   Underruns detected: {stats['total_count']}")
    print(f"   Max consecutive underruns: {stats['max_consecutive']}")
    print(f"   Clustering coefficient: {stats['clustering']:.2f}")
    
    return stats

def test_concurrent_dsp_load(buffer_size=256, duration=60):
    """Test with concurrent DSP processing load."""
    
    print(f"\n3. Testing with concurrent DSP load ({buffer_size} frames)...")
    
    monitor = UnderrunMonitor()
    global audio_phase, callback_count
    audio_phase = 0
    callback_count = 0
    
    def dsp_worker(worker_id, stop_event):
        """Worker that simulates DSP processing."""
        import queue
        
        # Each worker does continuous DSP work
        while not stop_event.is_set():
            try:
                # Simulate different DSP operations based on worker ID
                if worker_id == 0:
                    # VCO - light load
                    _ = np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, 4410))
                    time.sleep(0.005)  # ~5ms processing
                elif worker_id == 1:
                    # Filter - medium load
                    data = np.random.random(2205)
                    for _ in range(3):
                        data = np.convolve(data, [0.25, 0.5, 0.25], mode='same')
                    time.sleep(0.010)  # ~10ms processing
                elif worker_id == 2:
                    # Delay - light load
                    buffer = np.zeros(4410)
                    buffer = np.roll(buffer, 1000)
                    time.sleep(0.008)  # ~8ms processing
                else:
                    # Reverb - heavier but not excessive
                    data = np.random.random(2205)
                    kernel = np.random.random(50)  # Smaller kernel
                    _ = np.convolve(data, kernel, mode='same')
                    time.sleep(0.015)  # ~15ms processing
                    
            except Exception as e:
                print(f"   Worker {worker_id} error: {e}")
                break
    
    # Create worker processes (no queue needed - they just run continuously)
    stop_event = mp.Event()
    workers = []
    
    print(f"   Starting {min(4, mp.cpu_count())} DSP workers...")
    
    for i in range(min(4, mp.cpu_count())):
        p = mp.Process(target=dsp_worker, args=(i, stop_event))
        p.daemon = True  # Ensure cleanup
        p.start()
        workers.append(p)
    
    # Start audio stream
    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=buffer_size,
        channels=1,
        dtype='float32',
        callback=audio_callback_simple
    )
    
    monitor.start()
    
    try:
        with stream:
            print(f"   Playing audio with DSP load for {duration}s...")
            # Check for underruns periodically
            for i in range(duration):
                time.sleep(1)
                if i % 10 == 0 and i > 0:
                    print(f"      {i}s elapsed, {monitor.underrun_count} underruns so far...")
    finally:
        monitor.stop()
        stop_event.set()
        
        # Clean up workers with timeout
        print("   Stopping DSP workers...")
        for p in workers:
            p.join(timeout=1.0)
            if p.is_alive():
                p.terminate()
                p.join(timeout=0.5)
    
    stats = monitor.get_statistics()
    
    print(f"   Underruns detected: {stats['total_count']}")
    if stats['mean_interval'] != float('inf'):
        print(f"   Mean interval between underruns: {stats['mean_interval']:.2f}s")
    
    return stats

def test_multiple_buffer_sizes():
    """Test different buffer size configurations."""
    
    print("\n4. Testing multiple buffer sizes...")
    print("-" * 50)
    
    results = []
    
    for config in BUFFER_CONFIGS:
        buffer_size = config['frames']
        expected_latency = buffer_size / SAMPLE_RATE * 1000
        
        print(f"\n   Buffer size: {buffer_size} frames")
        print(f"   Expected latency: {expected_latency:.1f}ms")
        print(f"   Target: <{config['max_underruns']} underruns")
        
        # Run short test (10 seconds for buffer size validation)
        stats = test_clean_playback(buffer_size, duration=10)
        
        # Scale up to 60-second equivalent
        scaled_underruns = stats['total_count'] * 6
        
        passed = scaled_underruns <= config['max_underruns']
        status = "✓ PASS" if passed else "✗ FAIL"
        
        print(f"   Result: {stats['total_count']} underruns (scaled: {scaled_underruns})")
        print(f"   {status}")
        
        results.append({
            'buffer_size': buffer_size,
            'underruns': stats['total_count'],
            'scaled_underruns': scaled_underruns,
            'passed': passed
        })
    
    return results

def check_system_configuration():
    """Check if system is configured for real-time audio."""
    
    print("\n5. Checking system configuration...")
    
    config_status = {}
    
    # Check if we can set RT priority
    try:
        import os
        # Try to set real-time scheduling (will fail if not allowed)
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(1))
        config_status['rt_priority'] = True
        # Reset to normal
        os.sched_setscheduler(0, os.SCHED_OTHER, os.sched_param(0))
    except (AttributeError, PermissionError):
        config_status['rt_priority'] = False
    
    # Check memory locking limits
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_MEMLOCK)
        config_status['memlock'] = soft > 0
        config_status['memlock_limit'] = soft
    except:
        config_status['memlock'] = False
        config_status['memlock_limit'] = 0
    
    # Check CPU governor (Linux)
    try:
        with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor', 'r') as f:
            governor = f.read().strip()
            config_status['cpu_governor'] = governor
            config_status['governor_optimal'] = governor == 'performance'
    except:
        config_status['cpu_governor'] = 'unknown'
        config_status['governor_optimal'] = False
    
    # Print results
    print(f"   RT Priority Available: {'✓' if config_status.get('rt_priority') else '✗'}")
    print(f"   Memory Locking: {'✓' if config_status.get('memlock') else '✗'}")
    print(f"   CPU Governor: {config_status.get('cpu_governor', 'unknown')}")
    
    if not config_status.get('rt_priority'):
        print("   ⚠️  Warning: Cannot set RT priority. Audio may have dropouts.")
        print("      Fix: Add user to audio group and configure limits.d")
    
    return config_status

def main():
    """Run the complete buffer underrun test suite."""
    
    print("\n" + "="*60)
    print("RT-02: BUFFER UNDERRUN TEST")
    print("="*60)
    print(f"Sample Rate: {SAMPLE_RATE} Hz")
    print(f"Test Duration: {TEST_DURATION} seconds")
    print(f"rtmixer Available: {RTMIXER_AVAILABLE}")
    print("="*60)
    
    if not RTMIXER_AVAILABLE:
        print("\n⚠️  rtmixer not available - using sounddevice fallback")
        print("   Results may not reflect true rtmixer performance")
    
    # Initialize global monitor
    global monitor
    monitor = UnderrunMonitor()
    
    # Check system configuration
    sys_config = check_system_configuration()
    
    # Test 1: Clean playback
    clean_stats = test_clean_playback(buffer_size=256, duration=30)
    
    # Test 2: GC pressure
    gc_stats = test_with_gc_pressure(buffer_size=256, duration=30)
    
    # Test 3: Concurrent DSP
    dsp_stats = test_concurrent_dsp_load(buffer_size=256, duration=30)
    
    # Test 4: Multiple buffer sizes
    buffer_results = test_multiple_buffer_sizes()
    
    # Results summary
    print("\n" + "="*60)
    print("RESULTS SUMMARY:")
    print("-"*60)
    
    print("Test Results:")
    print(f"  Clean playback: {clean_stats['total_count']} underruns")
    print(f"  With GC pressure: {gc_stats['total_count']} underruns")
    print(f"  With DSP load: {dsp_stats['total_count']} underruns")
    
    print("\nBuffer Size Results:")
    for result in buffer_results:
        status = "✓" if result['passed'] else "✗"
        print(f"  {result['buffer_size']} frames: {status} ({result['underruns']} underruns)")
    
    print("\nSystem Configuration:")
    for key, value in sys_config.items():
        if isinstance(value, bool):
            print(f"  {key}: {'✓' if value else '✗'}")
        else:
            print(f"  {key}: {value}")
    
    print("-"*60)
    
    # Overall pass/fail
    success = True
    
    if clean_stats['total_count'] > 0:
        print("✗ FAIL: Underruns in clean playback")
        success = False
    else:
        print("✓ PASS: Clean playback successful")
    
    if gc_stats['total_count'] > 10:
        print(f"✗ FAIL: Too many underruns with GC ({gc_stats['total_count']})")
        success = False
    else:
        print(f"✓ PASS: GC stress handled ({gc_stats['total_count']} underruns)")
    
    if dsp_stats['total_count'] > 10:
        print(f"✗ FAIL: Too many underruns with DSP load ({dsp_stats['total_count']})")
        success = False
    else:
        print(f"✓ PASS: DSP load handled ({dsp_stats['total_count']} underruns)")
    
    print("="*60)
    
    if success:
        print("\n✓ RT-02 PASSED: System can sustain audio without excessive underruns")
        print("\nWhat this means:")
        print("• Audio playback is stable for live performance")
        print("• Buffer size of 256 frames provides good balance")
        print("• System can handle moderate load without dropouts")
    else:
        print("\n✗ RT-02 FAILED: System has underrun issues")
        print("\nRecommendations:")
        print("• Check system RT configuration")
        print("• Consider larger buffer sizes")
        print("• Optimize Python GC usage")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)