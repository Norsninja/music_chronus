#!/usr/bin/env python3
"""
Test ADSR v2 - Make it work first approach
No unit tests, just real audio
"""

import time
import numpy as np
from pythonosc import udp_client
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_adsr_v2():
    """Test the new ADSR with real musical patterns"""
    
    print("Starting ADSR v2 test - LISTEN for clicks!")
    print("=" * 50)
    
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    # Start the engine (supervisor should be running)
    print("\n1. Testing simple gate on/off...")
    print("   Should hear: Clean envelope, no clicks")
    
    # Simple sine at 220Hz
    client.send_message("/module/sine/freq", 220.0)
    
    # Single gate on/off
    client.send_message("/module/adsr/gate", 1.0)
    time.sleep(0.5)
    client.send_message("/module/adsr/gate", 0.0)
    time.sleep(0.5)
    
    print("\n2. Testing rapid retriggers (bassline pattern)...")
    print("   Should hear: Punchy attacks, no clicks")
    
    # Bassline pattern - rapid triggers
    for _ in range(8):
        client.send_message("/module/adsr/gate", 1.0)
        time.sleep(0.1)  # 100ms notes
        client.send_message("/module/adsr/gate", 0.0)
        time.sleep(0.1)
    
    print("\n3. Testing overlapping gates (legato)...")
    print("   Should hear: Smooth transitions, no clicks")
    
    # Overlapping gates - release interrupted by new attack
    for _ in range(4):
        client.send_message("/module/adsr/gate", 1.0)
        time.sleep(0.15)
        client.send_message("/module/adsr/gate", 0.0)
        time.sleep(0.05)  # Very short release before retriggering
    
    print("\n4. Testing instant retrigger (stress test)...")
    print("   Should hear: This might click - that's OK, we'll fix it")
    
    # Instant retrigger - worst case
    for _ in range(8):
        client.send_message("/module/adsr/gate", 1.0)
        client.send_message("/module/adsr/gate", 0.0)
        client.send_message("/module/adsr/gate", 1.0)
        time.sleep(0.2)
        client.send_message("/module/adsr/gate", 0.0)
        time.sleep(0.1)
    
    print("\n5. Testing slow envelope (pad)...")
    print("   Should hear: Smooth fade in/out")
    
    # Set slower times for pad
    client.send_message("/module/adsr/attack", 0.5)   # 500ms attack
    client.send_message("/module/adsr/release", 1.0)  # 1s release
    
    client.send_message("/module/adsr/gate", 1.0)
    time.sleep(2.0)
    client.send_message("/module/adsr/gate", 0.0)
    time.sleep(2.0)
    
    print("\n" + "=" * 50)
    print("Test complete!")
    print("\nDid you hear clicks? Note where they happened.")
    print("We'll only fix the ones that actually occurred.\n")

if __name__ == "__main__":
    print("ADSR v2 Minimal Test")
    print("Make sure supervisor_windows.py is running first!")
    print("This will play actual sounds - listen carefully\n")
    
    print("Starting test in 2 seconds...")
    time.sleep(2)
    
    test_adsr_v2()