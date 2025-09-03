#!/usr/bin/env python3
"""Test deadline scheduling fix - oscillator only patch for clean tone"""

import time
from pythonosc import udp_client

def test_oscillator_only():
    """Test pure sine wave generation with no envelope or filter"""
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("=== Testing Oscillator-Only Patch (Post-Deadline Fix) ===\n")
    
    # 1. Create minimal patch - just oscillator
    print("1. Creating sine oscillator...")
    client.send_message("/patch/create", ["osc1", "simple_sine"])
    time.sleep(0.1)
    
    # 2. Commit the patch
    print("2. Committing patch to active slot...")
    client.send_message("/patch/commit", [])
    time.sleep(0.5)  # Give time for slot switch
    
    # 3. Set oscillator parameters
    print("3. Setting oscillator parameters...")
    client.send_message("/mod/osc1/freq", [440.0])
    client.send_message("/mod/osc1/gain", [0.2])
    time.sleep(0.1)
    
    # 4. Listen for clean tone
    print("\n4. Generating 440Hz sine wave...")
    print("   Listen for: CLEAN tone, no grain/warble/artifacts")
    print("   Expected: Pure sine wave")
    time.sleep(3)
    
    # 5. Test frequency sweep to check smoothness
    print("\n5. Testing frequency sweep (should be smooth)...")
    freqs = [440, 550, 660, 550, 440]
    for freq in freqs:
        print(f"   {freq}Hz")
        client.send_message("/mod/osc1/freq", [float(freq)])
        time.sleep(0.5)
    
    print("\n6. Test complete!")
    print("\nExpected result: Clean, pure sine tones with no artifacts")
    print("If still gritty, parameter smoothing is the likely cause.")

if __name__ == "__main__":
    test_oscillator_only()