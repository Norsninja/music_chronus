#!/usr/bin/env python3
"""Sustained tone test for gathering statistics"""

import time
from pythonosc import udp_client

def test_sustained():
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("=== Sustained Tone Test (2-5 minutes) ===")
    
    # Create minimal patch
    print("Creating oscillator...")
    client.send_message("/patch/create", ["osc1", "simple_sine"])
    time.sleep(0.1)
    client.send_message("/patch/commit", [])
    time.sleep(0.5)
    
    # Set parameters
    client.send_message("/mod/osc1/freq", [440.0])
    client.send_message("/mod/osc1/gain", [0.3])
    
    print("\nGenerating sustained 440Hz tone...")
    print("Watch terminal for stats:")
    print("  - [WORKER] prod/late/drop/period_us")
    print("  - [STATS] None reads %")
    print("\nListen for artifacts while stats accumulate...")
    
    # Run for 2 minutes
    duration = 120
    start = time.time()
    while time.time() - start < duration:
        remaining = duration - (time.time() - start)
        print(f"\rTime remaining: {remaining:.0f}s  ", end="", flush=True)
        time.sleep(1)
    
    print("\n\nSilencing...")
    client.send_message("/mod/osc1/gain", [0.0])
    
    print("Test complete! Check stats in terminal.")

if __name__ == "__main__":
    test_sustained()