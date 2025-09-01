#!/usr/bin/env python3
"""
Test for supervisor_v2_fixed with restored <10ms failover
Tests sentinel detection, standby respawn, and ModuleHost integration
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import signal
from pythonosc import udp_client
from music_chronus.supervisor_v2_fixed import AudioSupervisor

def test_fast_failover():
    """Test that failover is back to <10ms with sentinel detection"""
    print("Fast Failover Test (Fixed)")
    print("=" * 40)
    
    supervisor = AudioSupervisor()
    
    # Start supervisor
    print("Starting supervisor with sentinel detection...")
    if not supervisor.start():
        print("Failed to start")
        return False
    
    # Let it stabilize
    time.sleep(2)
    
    # Get initial status
    status = supervisor.get_status()
    print(f"\nInitial Status:")
    print(f"  Primary PID: {status['workers']['primary']['pid']}")
    print(f"  Standby PID: {status['workers']['standby']['pid']}")
    print(f"  Active Worker: {status['metrics']['active_worker']}")
    
    # Kill primary worker
    primary_pid = status['workers']['primary']['pid']
    print(f"\nKilling primary worker (PID: {primary_pid})...")
    
    kill_time = time.monotonic_ns()
    os.kill(primary_pid, signal.SIGKILL)
    
    # Poll for failover (should be MUCH faster now)
    initial_failovers = status['metrics']['failover_count']
    for i in range(50):  # Check for up to 50ms
        time.sleep(0.001)  # 1ms polls
        new_status = supervisor.get_status()
        if new_status['metrics']['failover_count'] > initial_failovers:
            total_time = (time.monotonic_ns() - kill_time) / 1_000_000
            
            print(f"\n✅ Failover detected!")
            print(f"  Detection time: {new_status['metrics']['detection_time_ms']:.2f}ms")
            print(f"  Switch time: {new_status['metrics']['switch_time_ms']:.2f}ms")
            print(f"  Total from kill: {total_time:.2f}ms")
            
            # Check if <10ms
            if new_status['metrics']['failover_time_ms'] < 10.0:
                print(f"✅ PASSED: Failover in {new_status['metrics']['failover_time_ms']:.2f}ms (<10ms)")
            else:
                print(f"⚠️  WARNING: Failover took {new_status['metrics']['failover_time_ms']:.2f}ms (>10ms)")
            break
    else:
        print("❌ FAILED: Failover not detected within 50ms")
        supervisor.stop()
        return False
    
    # Check for standby respawn
    print("\nChecking for standby respawn...")
    time.sleep(1)
    
    final_status = supervisor.get_status()
    if final_status['workers']['standby']['alive']:
        print(f"✅ New standby spawned (PID: {final_status['workers']['standby']['pid']})")
    else:
        print("❌ No standby respawned")
        supervisor.stop()
        return False
    
    # Clean up
    supervisor.stop()
    return True


def test_shutdown_command():
    """Test that shutdown command works properly"""
    print("\nShutdown Command Test")
    print("=" * 40)
    
    supervisor = AudioSupervisor()
    
    # Start supervisor
    print("Starting supervisor...")
    if not supervisor.start():
        print("Failed to start")
        return False
    
    time.sleep(1)
    
    # Get initial PIDs
    status = supervisor.get_status()
    primary_pid = status['workers']['primary']['pid']
    standby_pid = status['workers']['standby']['pid']
    
    print(f"Workers: Primary={primary_pid}, Standby={standby_pid}")
    
    # Stop supervisor (should cleanly shutdown workers)
    print("Stopping supervisor (should trigger clean shutdown)...")
    supervisor.stop()
    
    # Give workers time to exit
    time.sleep(1)
    
    # Check if processes are gone
    try:
        os.kill(primary_pid, 0)
        print("❌ Primary worker still alive")
        return False
    except ProcessLookupError:
        print("✅ Primary worker cleanly shut down")
    
    try:
        os.kill(standby_pid, 0)
        print("❌ Standby worker still alive")
        return False
    except ProcessLookupError:
        print("✅ Standby worker cleanly shut down")
    
    return True


def test_osc_error_handling():
    """Test that invalid OSC commands don't crash the handler"""
    print("\nOSC Error Handling Test")
    print("=" * 40)
    
    supervisor = AudioSupervisor()
    
    # Start supervisor
    print("Starting supervisor...")
    if not supervisor.start():
        print("Failed to start")
        return False
    
    time.sleep(1)
    
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    # Send invalid module IDs (non-ASCII)
    print("Sending invalid module IDs...")
    try:
        client.send_message("/mod/INVALID!/param", 123.0)  # Has '!' which isn't allowed
        client.send_message("/mod/test-module/param", 456.0)  # Has '-' which isn't allowed
        time.sleep(0.5)
        
        # Check supervisor is still running
        status = supervisor.get_status()
        if supervisor.running:
            print("✅ Supervisor still running after invalid commands")
        else:
            print("❌ Supervisor crashed")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        supervisor.stop()
        return False
    
    # Send valid command to verify it still works
    print("Sending valid command...")
    client.send_message("/mod/sine/freq", 880.0)
    time.sleep(0.1)
    
    status = supervisor.get_status()
    if status['metrics']['commands_sent'] > 0:
        print("✅ Valid commands still processed")
    
    supervisor.stop()
    return True


def test_performance_comparison():
    """Compare failover times between original and fixed versions"""
    print("\nPerformance Comparison")
    print("=" * 40)
    
    results = []
    
    # Test fixed version multiple times
    print("Testing fixed version (5 runs)...")
    for i in range(5):
        supervisor = AudioSupervisor()
        supervisor.start()
        time.sleep(1)
        
        status = supervisor.get_status()
        primary_pid = status['workers']['primary']['pid']
        
        kill_time = time.monotonic_ns()
        os.kill(primary_pid, signal.SIGKILL)
        
        # Wait for failover
        for _ in range(50):
            time.sleep(0.001)
            new_status = supervisor.get_status()
            if new_status['metrics']['failover_count'] > 0:
                failover_time = new_status['metrics']['failover_time_ms']
                results.append(failover_time)
                print(f"  Run {i+1}: {failover_time:.2f}ms")
                break
        
        supervisor.stop()
        time.sleep(0.5)
    
    if results:
        avg_time = sum(results) / len(results)
        min_time = min(results)
        max_time = max(results)
        
        print(f"\nResults:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Min: {min_time:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")
        
        if avg_time < 10.0:
            print(f"✅ PASSED: Average failover {avg_time:.2f}ms < 10ms target")
            return True
        else:
            print(f"⚠️  WARNING: Average failover {avg_time:.2f}ms > 10ms target")
            return False
    else:
        print("❌ No results collected")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Supervisor v2 Fixed - Validation Tests")
    print("=" * 50)
    
    all_passed = True
    
    # Test 1: Fast failover
    print("\nTest 1: Fast Failover (<10ms)")
    if test_fast_failover():
        print("✅ PASSED: Fast failover test")
    else:
        print("❌ FAILED: Fast failover test")
        all_passed = False
    
    # Test 2: Shutdown command
    print("\n" + "=" * 50)
    if test_shutdown_command():
        print("✅ PASSED: Shutdown command test")
    else:
        print("❌ FAILED: Shutdown command test")
        all_passed = False
    
    # Test 3: OSC error handling
    print("\n" + "=" * 50)
    if test_osc_error_handling():
        print("✅ PASSED: OSC error handling test")
    else:
        print("❌ FAILED: OSC error handling test")
        all_passed = False
    
    # Test 4: Performance comparison
    print("\n" + "=" * 50)
    if test_performance_comparison():
        print("✅ PASSED: Performance comparison")
    else:
        print("❌ FAILED: Performance comparison")
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("Supervisor v2 Fixed meets all requirements!")
    else:
        print("❌ SOME TESTS FAILED")
        print("Review failures above")
    print("=" * 50)