#!/usr/bin/env python3
"""
Test script to verify Senior Dev's prime fix
Tests that patch commands are routed to the correct standby worker
"""

import time
from pythonosc import udp_client

def main():
    print("=" * 60)
    print("Prime Fix Verification Test")
    print("=" * 60)
    
    c = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("\n1. Creating initial patch...")
    c.send_message("/patch/create", ["osc1", "simple_sine"])
    c.send_message("/patch/commit", [])
    
    time.sleep(1)
    
    print("\n2. Setting parameters...")
    c.send_message("/mod/osc1/freq", [440.0])
    c.send_message("/mod/osc1/gain", [0.3])
    
    time.sleep(2)
    
    print("\n3. Creating second patch (should go to standby)...")
    c.send_message("/patch/create", ["osc2", "simple_sine"])
    c.send_message("/patch/commit", [])
    
    time.sleep(1)
    
    print("\n4. Setting new parameters...")
    c.send_message("/mod/osc2/freq", [660.0])
    c.send_message("/mod/osc2/gain", [0.3])
    
    time.sleep(2)
    
    print("\n5. Creating third patch (tests alternation)...")
    c.send_message("/patch/create", ["osc3", "simple_sine"])
    c.send_message("/patch/commit", [])
    
    time.sleep(1)
    
    c.send_message("/mod/osc3/freq", [880.0])
    c.send_message("/mod/osc3/gain", [0.3])
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print("\nExpected behavior:")
    print("1. Logs show '[OSC] Routing patch ... to standby slot X'")
    print("2. '[WORKER X] Applying ...' matches standby slot")
    print("3. '[WORKER X] prime_ready set' appears")
    print("4. '[OSC] Standby primed in Xms' (not timeout)")
    print("5. '[CALLBACK] Switched to slot X' shows alternation")
    print("6. Audio changes frequency: 440Hz → 660Hz → 880Hz")
    print("7. No popping or artifacts")
    print("\nIf all checks pass, the fix is working!")

if __name__ == "__main__":
    main()