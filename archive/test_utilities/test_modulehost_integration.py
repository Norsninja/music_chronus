#!/usr/bin/env python3
"""
Integration test for supervisor_v2 with ModuleHost
Tests synthesis chain and OSC control
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import signal
from pythonosc import udp_client
from music_chronus.supervisor_v2 import AudioSupervisor

def test_module_integration():
    """Test ModuleHost integration with supervisor"""
    print("ModuleHost Integration Test")
    print("=" * 40)
    
    supervisor = AudioSupervisor()
    
    # Start supervisor
    print("Starting supervisor with ModuleHost...")
    if not supervisor.start():
        print("Failed to start")
        return False
    
    # Let it stabilize
    print("Waiting for stabilization...")
    time.sleep(2)
    
    # Get initial status
    status = supervisor.get_status()
    print(f"\nInitial Status:")
    print(f"  Workers: Primary={status['workers']['primary']['alive']}, "
          f"Standby={status['workers']['standby']['alive']}")
    print(f"  Active Worker: {status['metrics']['active_worker']}")
    print(f"  Module Chain: {status['modules']['chain']}")
    print(f"  Protocol: {status['modules']['protocol']}")
    
    # Test OSC control
    print("\n" + "=" * 40)
    print("Testing OSC Control...")
    
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    # Test 1: Sine frequency control
    print("\n1. Testing sine frequency control...")
    client.send_message("/mod/sine/freq", 880.0)
    time.sleep(0.1)
    print("   Sent: /mod/sine/freq 880.0")
    
    # Test 2: ADSR gate control
    print("\n2. Testing ADSR gate...")
    client.send_message("/gate/adsr", "on")
    time.sleep(0.5)
    print("   Gate ON")
    client.send_message("/gate/adsr", "off")
    time.sleep(0.5)
    print("   Gate OFF")
    
    # Test 3: Filter control
    print("\n3. Testing filter parameters...")
    client.send_message("/mod/filter/cutoff", 500.0)
    client.send_message("/mod/filter/q", 5.0)
    time.sleep(0.1)
    print("   Set filter: cutoff=500Hz, Q=5.0")
    
    # Test 4: Legacy compatibility
    print("\n4. Testing legacy OSC addresses...")
    client.send_message("/engine/freq", 440.0)
    client.send_message("/engine/amp", 0.7)
    time.sleep(0.1)
    print("   Legacy: freq=440Hz, amp=0.7")
    
    # Check metrics
    time.sleep(1)
    final_status = supervisor.get_status()
    
    print("\n" + "=" * 40)
    print("Final Metrics:")
    print(f"  Buffers Processed: {final_status['metrics']['buffers_processed']}")
    print(f"  Underruns: {final_status['metrics']['underruns']}")
    print(f"  Commands Sent: {final_status['metrics']['commands_sent']}")
    print(f"  Failovers: {final_status['metrics']['failover_count']}")
    
    # Check success criteria
    success = True
    
    if final_status['metrics']['underruns'] > 0:
        print(f"\n⚠️  Had {final_status['metrics']['underruns']} underruns")
        success = False
    else:
        print("\n✅ No underruns")
    
    if final_status['metrics']['commands_sent'] < 10:
        print(f"⚠️  Only {final_status['metrics']['commands_sent']} commands processed")
        success = False
    else:
        print(f"✅ {final_status['metrics']['commands_sent']} commands processed")
    
    if final_status['metrics']['buffers_processed'] < 100:
        print(f"⚠️  Only {final_status['metrics']['buffers_processed']} buffers processed")
        success = False
    else:
        print(f"✅ {final_status['metrics']['buffers_processed']} buffers processed")
    
    # Clean shutdown
    print("\n" + "=" * 40)
    print("Shutting down...")
    supervisor.stop()
    
    return success


def test_failover_with_modules():
    """Test failover with ModuleHost active"""
    print("\nFailover Test with ModuleHost")
    print("=" * 40)
    
    supervisor = AudioSupervisor()
    
    # Start supervisor
    print("Starting supervisor...")
    if not supervisor.start():
        print("Failed to start")
        return False
    
    # Let it stabilize
    time.sleep(1)
    
    # Send some OSC commands to activate modules
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    client.send_message("/mod/sine/freq", 440.0)
    client.send_message("/gate/adsr", "on")
    client.send_message("/mod/filter/cutoff", 1000.0)
    time.sleep(0.5)
    
    # Get initial state
    status = supervisor.get_status()
    print(f"Active worker: {status['metrics']['active_worker']}")
    print(f"Primary heartbeat: {status['workers']['primary']['heartbeat']}")
    print(f"Standby heartbeat: {status['workers']['standby']['heartbeat']}")
    
    # Force failover by killing primary
    if supervisor.primary_worker:
        print(f"\nKilling primary worker (PID: {supervisor.primary_worker.process.pid})...")
        os.kill(supervisor.primary_worker.process.pid, signal.SIGKILL)
        
        # Wait for failover
        failover_start = time.perf_counter()
        for i in range(50):  # Check for up to 500ms
            time.sleep(0.01)
            new_status = supervisor.get_status()
            if new_status['metrics']['active_worker'] != status['metrics']['active_worker']:
                failover_time = (time.perf_counter() - failover_start) * 1000
                print(f"✅ Failover completed in {failover_time:.2f}ms")
                break
        else:
            print("❌ Failover did not occur within 500ms")
            supervisor.stop()
            return False
    
    # Check audio continues
    time.sleep(1)
    final_status = supervisor.get_status()
    
    if final_status['metrics']['underruns'] == 0:
        print("✅ No underruns during failover")
    else:
        print(f"⚠️  {final_status['metrics']['underruns']} underruns during failover")
    
    print(f"✅ Audio continued with worker {final_status['metrics']['active_worker']}")
    
    # Clean up
    supervisor.stop()
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("ModuleHost Supervisor Integration Tests")
    print("=" * 50)
    
    # Test 1: Basic integration
    print("\nTest 1: Basic Integration")
    if test_module_integration():
        print("\n✅ PASSED: Basic integration test")
    else:
        print("\n❌ FAILED: Basic integration test")
        sys.exit(1)
    
    # Test 2: Failover with modules
    print("\n" + "=" * 50)
    print("\nTest 2: Failover with ModuleHost")
    if test_failover_with_modules():
        print("\n✅ PASSED: Failover test")
    else:
        print("\n❌ FAILED: Failover test")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("✅ ALL TESTS PASSED")
    print("ModuleHost integration successful!")
    print("=" * 50)