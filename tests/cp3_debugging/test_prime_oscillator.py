#!/usr/bin/env python3
"""Test prime mechanism with oscillator only"""

import time
import os
from pythonosc import udp_client

# Enable router mode
os.environ['CHRONUS_ROUTER'] = '1'
os.environ['CHRONUS_VERBOSE'] = '1'

def test_oscillator_prime():
    """Test oscillator with direct priming"""
    print("\n=== Test 1: Oscillator-Only Prime Test ===")
    
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    # Create oscillator
    print("\n1. Creating oscillator...")
    client.send_message("/patch/create", ["osc1", "simple_sine"])
    time.sleep(0.1)
    
    # Commit patch
    print("\n2. Committing patch (triggers prime)...")
    client.send_message("/patch/commit", [])
    
    # Wait for prime and switch
    print("\n3. Waiting for prime and switch...")
    time.sleep(1.0)
    
    # Let it run
    print("\n4. Playing for 3 seconds...")
    time.sleep(3.0)
    
    print("\n✅ Test 1 complete - check supervisor output for:")
    print("   - Prime complete message")
    print("   - Non-silent warmup RMS")
    print("   - Successful switch")
    print("   - Low none-reads %")

if __name__ == "__main__":
    test_oscillator_prime()