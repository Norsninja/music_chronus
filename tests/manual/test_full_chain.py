#!/usr/bin/env python3
"""Test full synthesis chain with envelope and filter"""

import time
from pythonosc import udp_client

def test_full_chain():
    """Test complete chain: oscillator -> envelope -> filter"""
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("=== Testing Full Chain (Post-Deadline Fix) ===\n")
    
    # 1. Build complete patch
    print("1. Building full synthesizer patch...")
    client.send_message("/patch/create", ["osc1", "simple_sine"])
    time.sleep(0.1)
    client.send_message("/patch/create", ["env1", "adsr"])
    time.sleep(0.1)
    client.send_message("/patch/create", ["filt1", "biquad_filter"])
    time.sleep(0.1)
    
    # 2. Connect modules
    print("2. Connecting modules: osc1 -> env1 -> filt1...")
    client.send_message("/patch/connect", ["osc1", "env1"])
    time.sleep(0.1)
    client.send_message("/patch/connect", ["env1", "filt1"])
    time.sleep(0.1)
    
    # 3. Commit patch
    print("3. Committing patch to active slot...")
    client.send_message("/patch/commit", [])
    time.sleep(0.5)
    
    # 4. Configure parameters
    print("4. Setting parameters...")
    # Oscillator
    client.send_message("/mod/osc1/freq", [440.0])
    client.send_message("/mod/osc1/gain", [0.3])
    
    # ADSR - short attack, medium decay, high sustain, medium release
    client.send_message("/mod/env1/attack", [5.0])
    client.send_message("/mod/env1/decay", [50.0])
    client.send_message("/mod/env1/sustain", [0.8])
    client.send_message("/mod/env1/release", [100.0])
    
    # Filter - fairly open (high cutoff, low resonance)
    client.send_message("/mod/filt1/cutoff", [12000.0])
    client.send_message("/mod/filt1/q", [0.7])
    time.sleep(0.1)
    
    # 5. Test sustained note
    print("\n5. Testing sustained note (gate on)...")
    print("   Listen for: Clean attack, smooth sustain, no warble")
    client.send_message("/gate/env1", [1])
    time.sleep(2)
    
    print("   Gate off (testing release)...")
    client.send_message("/gate/env1", [0])
    time.sleep(0.5)
    
    # 6. Test multiple notes
    print("\n6. Testing multiple note triggers...")
    for i in range(3):
        print(f"   Note {i+1}")
        client.send_message("/gate/env1", [1])
        time.sleep(0.3)
        client.send_message("/gate/env1", [0])
        time.sleep(0.2)
    
    # 7. Test filter sweep while sustaining
    print("\n7. Testing filter sweep during sustain...")
    client.send_message("/gate/env1", [1])
    time.sleep(0.2)  # Let attack complete
    
    cutoffs = [12000, 8000, 4000, 2000, 1000, 2000, 4000, 8000, 12000]
    for cutoff in cutoffs:
        print(f"   Cutoff: {cutoff}Hz")
        client.send_message("/mod/filt1/cutoff", [float(cutoff)])
        time.sleep(0.3)
    
    client.send_message("/gate/env1", [0])
    
    print("\n8. Test complete!")
    print("\nExpected results:")
    print("- Clean envelope articulation (no clicks)")
    print("- Smooth sustain phase (no warble)")
    print("- Filter sweeps without zipper noise")
    print("\nIf artifacts only during parameter changes, need smoothing.")

if __name__ == "__main__":
    test_full_chain()