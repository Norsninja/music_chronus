#!/usr/bin/env python3
"""
Test script to verify OSC type error fix
Should run without any 'bool' object has no attribute 'encode' errors
"""

from pythonosc import udp_client
import time

def test_osc_commands():
    """Test the problematic OSC commands that were causing type errors"""
    
    client = udp_client.SimpleUDPClient('127.0.0.1', 5005)
    
    print("Testing OSC command fixes...")
    print("-" * 40)
    
    # Test 1: Add a sequencer track (this was working)
    print("\n1. Adding sequencer track...")
    client.send_message('/seq/add', ['test', 'voice1', 'X...X...X...X...', 110, 500])
    time.sleep(0.5)
    
    # Test 2: Update pattern (this was causing errors)
    print("\n2. Updating pattern (previously caused type error)...")
    client.send_message('/seq/update/pattern', ['test', 'x.x.x.x.x.x.x.x.'])
    time.sleep(0.5)
    
    # Test 3: Update notes (this was causing errors)
    print("\n3. Updating notes (previously caused type error)...")
    client.send_message('/seq/update/notes', ['test', 'C4 D4 E4 F4'])
    time.sleep(0.5)
    
    # Test 4: Multiple rapid updates (stress test)
    print("\n4. Rapid pattern updates (stress test)...")
    patterns = ['X...X...', 'XX..XX..', 'XXXXXXXX', '....X...']
    for i, pattern in enumerate(patterns):
        print(f"   Pattern {i+1}: {pattern}")
        client.send_message('/seq/update/pattern', ['test', pattern])
        time.sleep(0.2)
    
    # Test 5: Start and stop sequencer
    print("\n5. Starting sequencer...")
    client.send_message('/seq/start', [])
    time.sleep(2)
    
    print("\n6. Stopping sequencer...")
    client.send_message('/seq/stop', [])
    
    # Clean up
    print("\n7. Cleaning up...")
    client.send_message('/seq/clear', [])
    
    print("\n" + "-" * 40)
    print("Test complete! Check engine output for any type errors.")
    print("If no 'bool' object errors appeared, the fix is working!")

if __name__ == "__main__":
    test_osc_commands()