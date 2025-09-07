#!/usr/bin/env python3
"""
Quick test of the acid filter module
Tests basic functionality and parameter sweeps
"""

import time
from pythonosc import udp_client

def test_acid():
    """Test acid filter with simple patterns"""
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("\n" + "="*50)
    print("ACID FILTER TEST")
    print("="*50)
    
    # Setup voice2 for bass
    print("\n1. Setting up voice2...")
    client.send_message("/mod/voice2/freq", 110)  # A2
    client.send_message("/mod/voice2/amp", 0.5)
    client.send_message("/mod/voice2/filter/freq", 1000)
    client.send_message("/mod/voice2/adsr/attack", 0.001)
    client.send_message("/mod/voice2/adsr/decay", 0.1)
    client.send_message("/mod/voice2/adsr/sustain", 0.3)
    client.send_message("/mod/voice2/adsr/release", 0.1)
    
    # Setup acid filter
    print("2. Configuring acid filter...")
    client.send_message("/mod/acid1/cutoff", 300)
    client.send_message("/mod/acid1/res", 0.7)
    client.send_message("/mod/acid1/env_amount", 2000)
    client.send_message("/mod/acid1/decay", 0.3)
    client.send_message("/mod/acid1/drive", 0.3)
    client.send_message("/mod/acid1/mix", 1.0)
    
    # Test 1: Basic gate without accent
    print("\n3. Testing basic gate (no accent)...")
    for i in range(4):
        client.send_message("/gate/voice2", 1)
        time.sleep(0.1)
        client.send_message("/gate/voice2", 0)
        time.sleep(0.2)
    
    time.sleep(0.5)
    
    # Test 2: With accent
    print("4. Testing with accent...")
    for i in range(4):
        if i % 2 == 0:
            client.send_message("/mod/acid1/accent", 1.0)
            print("  - Accent ON")
        else:
            client.send_message("/mod/acid1/accent", 0.0)
            print("  - Accent OFF")
        
        client.send_message("/gate/voice2", 1)
        time.sleep(0.1)
        client.send_message("/gate/voice2", 0)
        time.sleep(0.3)
    
    time.sleep(0.5)
    
    # Test 3: Cutoff sweep
    print("\n5. Testing cutoff sweep...")
    client.send_message("/mod/acid1/accent", 0.0)
    
    for cutoff in [200, 400, 800, 1600, 800, 400, 200]:
        print(f"  - Cutoff: {cutoff}Hz")
        client.send_message("/mod/acid1/cutoff", cutoff)
        client.send_message("/gate/voice2", 1)
        time.sleep(0.15)
        client.send_message("/gate/voice2", 0)
        time.sleep(0.15)
    
    time.sleep(0.5)
    
    # Test 4: Resonance sweep
    print("\n6. Testing resonance sweep...")
    client.send_message("/mod/acid1/cutoff", 400)
    
    for res in [0.3, 0.5, 0.7, 0.85, 0.95, 0.85, 0.7, 0.5]:
        print(f"  - Resonance: {res}")
        client.send_message("/mod/acid1/res", res)
        client.send_message("/gate/voice2", 1)
        time.sleep(0.15)
        client.send_message("/gate/voice2", 0)
        time.sleep(0.15)
    
    time.sleep(0.5)
    
    # Test 5: Classic 303 pattern with accents
    print("\n7. Testing 303 pattern...")
    client.send_message("/mod/acid1/cutoff", 350)
    client.send_message("/mod/acid1/res", 0.75)
    client.send_message("/mod/acid1/env_amount", 2500)
    
    notes = [110, 110, 138, 165, 110, None, 138, 110]
    accents = [True, False, False, True, False, False, True, False]
    
    for _ in range(4):  # Repeat pattern 4 times
        for note, accent in zip(notes, accents):
            if note:
                client.send_message("/mod/acid1/accent", 1.0 if accent else 0.0)
                client.send_message("/mod/voice2/freq", note)
                client.send_message("/gate/voice2", 1)
                time.sleep(0.12)
                client.send_message("/gate/voice2", 0)
                time.sleep(0.08)
            else:
                time.sleep(0.2)
    
    print("\nTest complete!")
    print("="*50)

if __name__ == "__main__":
    print("Make sure engine_pyo.py is running!")
    print("Starting test in 2 seconds...")
    time.sleep(2)
    
    try:
        test_acid()
    except KeyboardInterrupt:
        print("\nTest interrupted")