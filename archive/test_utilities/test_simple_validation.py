#!/usr/bin/env python3
"""
Simple validation test for supervisor_v2_fixed
Focus on core functionality without complex timing tests
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import time
from music_chronus import AudioSupervisor

def test_basic_startup():
    """Test that supervisor starts without errors"""
    print("Testing basic startup...")
    
    supervisor = AudioSupervisor()
    
    # Start supervisor
    if not supervisor.start():
        print("❌ Failed to start supervisor")
        return False
    
    # Let it run briefly
    time.sleep(2)
    
    # Check status
    status = supervisor.get_status()
    
    # Verify both workers are alive
    if status['workers']['primary']['alive'] and status['workers']['standby']['alive']:
        print(f"✅ Both workers running: Primary={status['workers']['primary']['pid']}, Standby={status['workers']['standby']['pid']}")
    else:
        print("❌ Workers not running properly")
        supervisor.stop()
        return False
    
    # Check no underruns
    if status['metrics']['underruns'] == 0:
        print(f"✅ No underruns after {status['metrics']['buffers_processed']} buffers")
    else:
        print(f"⚠️  {status['metrics']['underruns']} underruns detected")
    
    # Clean shutdown
    supervisor.stop()
    time.sleep(1)
    
    print("✅ Clean startup and shutdown successful")
    return True


def test_osc_commands():
    """Test that OSC commands are processed"""
    print("\nTesting OSC command processing...")
    
    supervisor = AudioSupervisor()
    supervisor.start()
    time.sleep(1)
    
    from pythonosc import udp_client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    # Send some commands
    client.send_message("/mod/sine/freq", 880.0)
    client.send_message("/gate/adsr", "on")
    client.send_message("/mod/filter/cutoff", 1000.0)
    
    time.sleep(0.5)
    
    # Check commands were sent
    status = supervisor.get_status()
    if status['metrics']['commands_sent'] >= 6:  # 3 commands × 2 workers
        print(f"✅ Commands processed: {status['metrics']['commands_sent']}")
    else:
        print(f"❌ Only {status['metrics']['commands_sent']} commands sent")
        supervisor.stop()
        return False
    
    supervisor.stop()
    print("✅ OSC command processing works")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("Simple Validation Test")
    print("=" * 50)
    
    all_passed = True
    
    # Test 1: Basic startup
    if not test_basic_startup():
        all_passed = False
    
    # Test 2: OSC commands
    if not test_osc_commands():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ VALIDATION PASSED")
        print("Core functionality working!")
    else:
        print("❌ VALIDATION FAILED")
        print("Check errors above")
    print("=" * 50)