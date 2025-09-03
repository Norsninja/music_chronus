#!/usr/bin/env python3
"""
Static Parameter Test - Hold all params steady for 2-3 minutes
If grit vanishes, it confirms parameter motion is the cause
"""

import time
from pythonosc import udp_client

def test_static_params(duration_seconds=180):
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("=" * 60)
    print("STATIC PARAMETER TEST")
    print("Duration: {} seconds ({:.1f} minutes)".format(duration_seconds, duration_seconds/60))
    print("=" * 60)
    
    # Build patch
    print("\n[Setup] Building patch with filter...")
    client.send_message("/patch/create", ["osc1", "simple_sine"])
    client.send_message("/patch/create", ["filt1", "biquad_filter"])
    client.send_message("/patch/connect", ["osc1", "filt1"])
    client.send_message("/patch/commit", [])
    time.sleep(1)
    
    # Set parameters ONCE
    print("\n[Setup] Setting parameters (will not change)...")
    client.send_message("/mod/osc1/freq", [440.0])
    client.send_message("/mod/osc1/gain", [0.2])
    client.send_message("/mod/filt1/cutoff", [4000.0])
    client.send_message("/mod/filt1/q", [1.5])
    time.sleep(0.5)
    
    print("\n[Running] Holding all parameters steady...")
    print("Listen for grit/artifacts with NO parameter changes")
    print("\nIf grit vanishes → parameter stepping is the cause")
    print("If grit remains → boundary/phase issues\n")
    
    start_time = time.time()
    last_update = start_time
    
    while (time.time() - start_time) < duration_seconds:
        elapsed = time.time() - start_time
        
        # Print progress every 10 seconds
        if (time.time() - last_update) >= 10:
            remaining = duration_seconds - elapsed
            print(f"  [{elapsed:3.0f}s] Still running... {remaining:.0f}s remaining")
            last_update = time.time()
        
        time.sleep(1)
    
    print(f"\n[Complete] Ran for {duration_seconds} seconds")
    print("\nRESULT:")
    print("- If audio was CLEAN → grit is from parameter motion")
    print("- If grit REMAINED → issue is boundary/phase related")
    print("Check supervisor stats for none-reads %")

if __name__ == "__main__":
    test_static_params(180)  # 3 minutes