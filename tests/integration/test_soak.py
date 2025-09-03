#!/usr/bin/env python3
"""
10-15 minute soak test with periodic stats reporting
"""

import time
import sys
from pythonosc import udp_client

def run_soak_test(duration_minutes=10):
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("=" * 60)
    print(f"SOAK TEST - {duration_minutes} minute run")
    print("=" * 60)
    
    # Build a moderate complexity patch
    print("\n[Setup] Building test patch...")
    client.send_message("/patch/create", ["osc1", "simple_sine"])
    client.send_message("/patch/create", ["env1", "adsr"])
    client.send_message("/patch/create", ["filt1", "biquad_filter"])
    client.send_message("/patch/connect", ["osc1", "env1"])
    client.send_message("/patch/connect", ["env1", "filt1"])
    client.send_message("/patch/commit", [])
    time.sleep(1)
    
    # Set parameters
    client.send_message("/mod/osc1/freq", [440.0])
    client.send_message("/mod/osc1/gain", [0.2])
    client.send_message("/mod/env1/attack", [10.0])
    client.send_message("/mod/env1/decay", [100.0])
    client.send_message("/mod/env1/sustain", [0.7])
    client.send_message("/mod/env1/release", [200.0])
    client.send_message("/mod/filt1/cutoff", [4000.0])
    client.send_message("/mod/filt1/q", [2.0])
    
    print(f"\n[Running] Starting {duration_minutes} minute soak test...")
    print("Monitor for:")
    print("  - None-reads staying ≤1%")
    print("  - Ring occupancy stability")
    print("  - No audio dropouts")
    print("  - Worker late cycles")
    print("\nProgress:")
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    last_activity = time.time()
    minute_counter = 0
    
    # Main soak loop
    while time.time() < end_time:
        current_minute = int((time.time() - start_time) / 60)
        
        # Print progress every minute
        if current_minute > minute_counter:
            minute_counter = current_minute
            elapsed = time.time() - start_time
            print(f"  [{current_minute:2d}/{duration_minutes}] "
                  f"Elapsed: {elapsed:.1f}s - "
                  f"Check supervisor for stats")
        
        # Periodic activity to keep audio active
        if time.time() - last_activity > 10:  # Every 10 seconds
            # Trigger a note
            client.send_message("/gate/env1", [1])
            time.sleep(0.5)
            client.send_message("/gate/env1", [0])
            
            # Small parameter change
            import random
            freq = 440 + random.uniform(-50, 50)
            client.send_message("/mod/osc1/freq", [freq])
            
            last_activity = time.time()
        
        time.sleep(1)  # Check every second
    
    # Test complete
    elapsed_total = time.time() - start_time
    print(f"\n[Complete] Soak test ran for {elapsed_total:.1f} seconds")
    print("\nCheck supervisor output for:")
    print("  - Final none-reads % (should be ≤1%)")
    print("  - Ring occupancy patterns")
    print("  - Worker late cycles")
    print("  - Any error messages")
    
    # Final sustained tone to verify audio still working
    print("\n[Verify] Playing sustained tone for 5 seconds...")
    client.send_message("/gate/env1", [1])
    time.sleep(5)
    client.send_message("/gate/env1", [0])
    
    print("\nSOAK TEST COMPLETE")

if __name__ == "__main__":
    # Check for custom duration
    duration = 10  # default
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
            duration = max(1, min(duration, 30))  # Clamp 1-30 minutes
        except ValueError:
            pass
    
    run_soak_test(duration)