#!/usr/bin/env python3
"""Test all visualizer fixes"""

from pythonosc import udp_client
import time

def test_fixes():
    c = udp_client.SimpleUDPClient('127.0.0.1', 5005)
    
    print("Testing all visualizer fixes...")
    print("-" * 40)
    
    # Test 1: Voice meter clamping (was showing >1.0)
    print("1. Testing voice meter clamping")
    print("   Setting voice2 amp to 2.0 (should clamp to 1.0)")
    c.send_message('/mod/voice2/amp', 2.0)  # Excessive gain
    c.send_message('/mod/voice2/freq', 440.0)
    c.send_message('/gate/voice2', 1)
    time.sleep(2)
    c.send_message('/gate/voice2', 0)
    print("   ✓ Voice2 meter should show max 1.0, not 1.2+")
    
    # Test 2: OSC message display
    print("\n2. Testing OSC message display")
    print("   Generating traffic...")
    for i in range(3):
        c.send_message('/gate/voice1', 1)
        time.sleep(0.5)
        c.send_message('/gate/voice1', 0)
        time.sleep(0.5)
    print("   ✓ /viz/spectrum and /viz/levels should appear in OSC panel")
    
    # Test 3: Spectrum analyzer
    print("\n3. Testing spectrum analyzer")
    print("   Playing frequency sweep...")
    
    # Bass frequencies
    print("   - Bass (100Hz)")
    c.send_message('/mod/voice1/freq', 100.0)
    c.send_message('/gate/voice1', 1)
    time.sleep(1)
    
    # Mid frequencies  
    print("   - Mid (1000Hz)")
    c.send_message('/mod/voice2/freq', 1000.0)
    c.send_message('/gate/voice2', 1)
    time.sleep(1)
    
    # High frequencies
    print("   - High (4000Hz)")
    c.send_message('/mod/voice3/freq', 4000.0)
    c.send_message('/gate/voice3', 1)
    time.sleep(2)
    
    # Cleanup
    for i in range(1, 4):
        c.send_message(f'/gate/voice{i}', 0)
    
    print("   ✓ Spectrum bars should show activity")
    
    print("\n" + "=" * 40)
    print("All tests complete! Check visualizer for:")
    print("1. Voice meters clamped to 1.0")
    print("2. /viz messages in OSC panel")
    print("3. Spectrum analyzer showing bars")

if __name__ == "__main__":
    test_fixes()
