#!/usr/bin/env python3
"""
Quick failover test - focused on measuring detection and switch times
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import signal
from music_chronus import AudioSupervisor

def test_failover():
    print("Phase 1C Quick Failover Test")
    print("=" * 40)
    
    supervisor = AudioSupervisor()
    
    # Start supervisor
    print("Starting supervisor...")
    if not supervisor.start():
        print("Failed to start")
        return False
    
    # Let it stabilize
    time.sleep(1)
    
    # Get initial state
    status = supervisor.get_status()
    print(f"Initial: Primary PID={status['primary_pid']}, Standby PID={status['standby_pid']}")
    print(f"Heartbeats: Primary={status['primary_heartbeat']}, Standby={status['standby_heartbeat']}")
    
    # Test 1: SIGKILL primary
    print("\nTest 1: SIGKILL Primary Worker")
    primary_pid = status['primary_pid']
    
    detection_start = time.monotonic_ns()
    os.kill(primary_pid, signal.SIGKILL)
    
    # Poll for failover (max 20ms)
    for _ in range(20):
        time.sleep(0.001)  # 1ms polls
        new_status = supervisor.get_status()
        if new_status['primary_pid'] != primary_pid:
            detection_time = (time.monotonic_ns() - detection_start) / 1_000_000
            print(f"✅ Failover detected in {detection_time:.2f}ms")
            break
    else:
        print("❌ Failover not detected within 20ms")
    
    # Wait for standby respawn
    time.sleep(0.5)
    
    # Test 2: Clean termination
    print("\nTest 2: Clean Termination (SIGTERM)")
    status = supervisor.get_status()
    primary_pid = status['primary_pid']
    
    detection_start = time.monotonic_ns()
    os.kill(primary_pid, signal.SIGTERM)
    
    # Poll for failover (give slightly more time for clean exit)
    for _ in range(30):
        time.sleep(0.001)
        new_status = supervisor.get_status()
        if new_status['primary_pid'] != primary_pid:
            detection_time = (time.monotonic_ns() - detection_start) / 1_000_000
            print(f"✅ Failover detected in {detection_time:.2f}ms")
            break
    else:
        print("❌ Failover not detected within 30ms")
    
    # Check metrics
    print("\nMetrics Summary:")
    print(f"Total failovers: {supervisor.metrics.failovers}")
    print(f"Crashes: {supervisor.metrics.crash_count}")
    
    if supervisor.metrics.failover_times_ns:
        p50 = supervisor.metrics.get_percentile(supervisor.metrics.failover_times_ns, 50)
        p95 = supervisor.metrics.get_percentile(supervisor.metrics.failover_times_ns, 95)
        print(f"Switch times: p50={p50:.3f}ms, p95={p95:.3f}ms")
    
    # Check for underruns
    final_status = supervisor.get_status()
    print(f"Underruns: Primary={final_status['primary_ring_underruns']}, Standby={final_status['standby_ring_underruns']}")
    
    # Cleanup
    supervisor.stop()
    
    # Success if we had failovers and low switch time
    success = supervisor.metrics.failovers >= 2 and p95 < 10
    print(f"\n{'✅ PASS' if success else '❌ FAIL'}: Phase 1C failover <10ms target")
    return success

if __name__ == "__main__":
    import sys
    success = test_failover()
    sys.exit(0 if success else 1)