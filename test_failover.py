#!/usr/bin/env python3
"""
Test failover mechanism - verify audio continues cleanly when primary worker fails
"""

import time
import os
import signal
import subprocess
from pythonosc import udp_client

def test_failover():
    """Test that audio continues without glitches during failover"""
    
    client = udp_client.SimpleUDPClient('127.0.0.1', 5005)
    
    print("Starting failover test...")
    print("1. Playing 440Hz tone...")
    
    # Start a continuous tone
    client.send_message('/mod/sine/freq', [440.0])
    client.send_message('/mod/sine/gain', [0.3])
    client.send_message('/mod/adsr/attack', [1.0])
    client.send_message('/mod/adsr/release', [10.0])
    client.send_message('/gate/adsr', [1])
    
    print("   Audio should be playing now")
    time.sleep(2)
    
    print("2. Getting primary worker PID...")
    # Get the supervisor PID first - try both versions
    result = subprocess.run(['pgrep', '-f', 'supervisor_v2_slots_fixed'], 
                          capture_output=True, text=True)
    
    if not result.stdout:
        # Try the other version
        result = subprocess.run(['pgrep', '-f', 'supervisor_v2_graceful'], 
                              capture_output=True, text=True)
    
    if not result.stdout:
        print("ERROR: Could not find supervisor process")
        return False
    
    supervisor_pid = int(result.stdout.strip().split('\n')[0])
    print(f"   Supervisor PID: {supervisor_pid}")
    
    # Get worker processes (children of supervisor)
    result = subprocess.run(['pgrep', '-P', str(supervisor_pid)], 
                          capture_output=True, text=True)
    
    if not result.stdout:
        print("ERROR: Could not find worker processes")
        return False
    
    worker_pids = [int(pid) for pid in result.stdout.strip().split('\n')]
    print(f"   Worker PIDs: {worker_pids}")
    
    if len(worker_pids) < 2:
        print("ERROR: Need at least 2 workers for failover test")
        return False
    
    primary_pid = worker_pids[0]  # Assume first is primary
    
    print(f"3. Killing primary worker (PID {primary_pid})...")
    print("   LISTEN FOR AUDIO GLITCH!")
    
    # Kill the primary worker
    os.kill(primary_pid, signal.SIGKILL)
    
    print("   Primary killed - failover should occur within 50ms")
    print("   Audio should continue with minimal interruption")
    
    # Let it play for a bit to verify continuity
    time.sleep(3)
    
    print("4. Changing frequency to verify standby is now active...")
    client.send_message('/mod/sine/freq', [880.0])
    time.sleep(2)
    
    print("5. Stopping audio...")
    client.send_message('/gate/adsr', [0])
    time.sleep(1)
    
    print("\nFailover test complete!")
    print("Did you hear:")
    print("  - Continuous 440Hz tone at start?")
    print("  - Brief glitch (<50ms) when primary was killed?")
    print("  - Tone continue after failover?")
    print("  - Frequency change to 880Hz?")
    
    return True

if __name__ == "__main__":
    try:
        success = test_failover()
        if not success:
            print("\nTest failed - see errors above")
    except Exception as e:
        print(f"\nTest error: {e}")
        import traceback
        traceback.print_exc()