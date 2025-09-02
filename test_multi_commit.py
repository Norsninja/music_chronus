#!/usr/bin/env python3
"""Test multi-commit cycle - validates router fix"""

import time
from pythonosc import udp_client

def test_multi_commit():
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("=== Multi-Commit Cycle Test ===")
    print("Testing repeated patch builds and commits\n")
    
    # Cycle A: First patch
    print("CYCLE A: Building first patch (440Hz)")
    print("  1. Creating osc1 -> env1 -> filt1")
    client.send_message("/patch/create", ["osc1", "simple_sine"])
    time.sleep(0.1)
    client.send_message("/patch/create", ["env1", "adsr"]) 
    time.sleep(0.1)
    client.send_message("/patch/create", ["filt1", "biquad_filter"])
    time.sleep(0.1)
    
    print("  2. Connecting modules")
    client.send_message("/patch/connect", ["osc1", "env1"])
    time.sleep(0.1)
    client.send_message("/patch/connect", ["env1", "filt1"])
    time.sleep(0.1)
    
    print("  3. Committing patch")
    client.send_message("/patch/commit", [])
    time.sleep(0.5)
    
    print("  4. Setting parameters and playing")
    client.send_message("/mod/osc1/freq", [440.0])
    client.send_message("/mod/osc1/gain", [0.3])
    client.send_message("/gate/env1", [1])
    time.sleep(2)
    client.send_message("/gate/env1", [0])
    time.sleep(0.5)
    
    print("  ✓ Cycle A complete - should hear 440Hz tone\n")
    
    # Cycle B: Different patch
    print("CYCLE B: Building different patch (660Hz, no filter)")
    print("  1. Creating osc2 -> env2")
    client.send_message("/patch/create", ["osc2", "simple_sine"])
    time.sleep(0.1)
    client.send_message("/patch/create", ["env2", "adsr"])
    time.sleep(0.1)
    
    print("  2. Connecting modules")
    client.send_message("/patch/connect", ["osc2", "env2"])
    time.sleep(0.1)
    
    print("  3. Committing patch")
    client.send_message("/patch/commit", [])
    time.sleep(0.5)
    
    print("  4. Setting parameters and playing")
    client.send_message("/mod/osc2/freq", [660.0])
    client.send_message("/mod/osc2/gain", [0.3])
    client.send_message("/gate/env2", [1])
    time.sleep(2)
    client.send_message("/gate/env2", [0])
    time.sleep(0.5)
    
    print("  ✓ Cycle B complete - should hear 660Hz tone\n")
    
    # Cycle C: Simple patch
    print("CYCLE C: Building simple patch (880Hz, osc only)")
    print("  1. Creating osc3")
    client.send_message("/patch/create", ["osc3", "simple_sine"])
    time.sleep(0.1)
    
    print("  2. Committing patch")
    client.send_message("/patch/commit", [])
    time.sleep(0.5)
    
    print("  3. Setting parameters and playing")
    client.send_message("/mod/osc3/freq", [880.0])
    client.send_message("/mod/osc3/gain", [0.3])
    time.sleep(2)
    
    print("  ✓ Cycle C complete - should hear 880Hz tone\n")
    
    # Silence
    client.send_message("/mod/osc3/gain", [0.0])
    
    print("=== TEST COMPLETE ===")
    print("\nExpected results:")
    print("- Three different patches played successfully")
    print("- Smooth transitions between patches")
    print("- Worker logs show router enabled on new standby after each swap")
    print("- '[CALLBACK] Switched to slot X' alternates (0,1,0)")
    print("\nCheck terminal for confirmation")

if __name__ == "__main__":
    test_multi_commit()