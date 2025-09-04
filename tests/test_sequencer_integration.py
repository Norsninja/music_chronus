#!/usr/bin/env python3
"""
Integration test for sequencer with live audio.
Tests a kick pattern with recording to verify timing.
"""

import time
import os
import sys
from pythonosc import udp_client

# Configuration
OSC_HOST = '127.0.0.1'
OSC_PORT = 5005


def test_sequencer_kick_pattern():
    """Test basic kick pattern at 120 BPM."""
    print("=== Sequencer Integration Test ===")
    print("Make sure supervisor_v3_router.py is running with CHRONUS_ROUTER=1")
    
    client = udp_client.SimpleUDPClient(OSC_HOST, OSC_PORT)
    
    try:
        # 1. Create patch (sine -> adsr -> output)
        print("\n1. Creating patch...")
        client.send_message('/patch/create', ['sine', 'simple_sine'])
        time.sleep(0.1)
        client.send_message('/patch/create', ['adsr', 'adsr'])
        time.sleep(0.1)
        client.send_message('/patch/create', ['filter', 'biquad_filter'])
        time.sleep(0.1)
        
        # Connect modules
        client.send_message('/patch/connect', ['sine', 'adsr'])
        time.sleep(0.1)
        client.send_message('/patch/connect', ['adsr', 'filter'])
        time.sleep(0.1)
        client.send_message('/patch/connect', ['filter', 'output'])
        time.sleep(0.1)
        
        # Commit patch
        client.send_message('/patch/commit', [])
        time.sleep(0.5)
        print("   Patch created and committed")
        
        # 2. Configure modules for kick sound
        print("\n2. Configuring kick sound...")
        client.send_message('/mod/sine/freq', 60.0)  # Low frequency for kick
        client.send_message('/mod/sine/gain', 0.7)
        client.send_message('/mod/adsr/attack', 1.0)    # Fast attack
        client.send_message('/mod/adsr/decay', 100.0)   # Quick decay
        client.send_message('/mod/adsr/sustain', 0.3)
        client.send_message('/mod/adsr/release', 200.0)
        client.send_message('/mod/filter/cutoff', 1000.0)
        client.send_message('/mod/filter/q', 2.0)
        time.sleep(0.2)
        print("   Kick sound configured")
        
        # 3. Create and configure sequencer
        print("\n3. Setting up sequencer...")
        client.send_message('/seq/create', 'kick')
        time.sleep(0.1)
        client.send_message('/seq/config', ['kick', 120, 16, 4])  # 120 BPM, 16 steps, quarter notes
        time.sleep(0.1)
        client.send_message('/seq/pattern', ['kick', 'x...x...x...x...'])
        time.sleep(0.1)
        client.send_message('/seq/assign', ['kick', 'gate', 'adsr'])
        time.sleep(0.1)
        client.send_message('/seq/gate_len', ['kick', 0.5])  # 50% gate length
        time.sleep(0.2)
        print("   Sequencer configured")
        
        # 4. Start recording
        print("\n4. Starting recording...")
        client.send_message('/record/start', 'test_sequencer_kick.wav')
        time.sleep(0.5)
        
        # 5. Start sequencer
        print("\n5. Starting sequencer...")
        client.send_message('/seq/start', 'kick')
        
        # Let it run for 8 seconds (4 bars at 120 BPM)
        print("   Running for 8 seconds...")
        time.sleep(8)
        
        # 6. Test tempo change
        print("\n6. Changing tempo to 140 BPM...")
        client.send_message('/seq/bpm', ['kick', 140])
        time.sleep(4)
        
        # 7. Test pattern change
        print("\n7. Changing pattern to busier rhythm...")
        client.send_message('/seq/pattern', ['kick', 'x.x.x.x.x.x.x.x.'])
        time.sleep(4)
        
        # 8. Stop sequencer
        print("\n8. Stopping sequencer...")
        client.send_message('/seq/stop', 'kick')
        time.sleep(1)
        
        # 9. Stop recording
        print("\n9. Stopping recording...")
        client.send_message('/record/stop', [])
        time.sleep(0.5)
        
        print("\n=== Test Complete ===")
        print("Check test_sequencer_kick.wav for results")
        print("Expected: Clean kick pattern with no pops")
        print("         Tempo change at 8s mark")
        print("         Pattern change at 12s mark")
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True


def test_multi_sequencer():
    """Test multiple sequencers running simultaneously."""
    print("\n=== Multi-Sequencer Test ===")
    
    client = udp_client.SimpleUDPClient(OSC_HOST, OSC_PORT)
    
    try:
        # Assume patch is already created from previous test
        
        # 1. Create hihat sequencer
        print("\n1. Creating hihat sequencer...")
        client.send_message('/seq/create', 'hihat')
        client.send_message('/seq/config', ['hihat', 120, 16, 16])  # 16th notes
        client.send_message('/seq/pattern', ['hihat', '..x...x...x...x.'])
        
        # For hihat, use higher frequency and shorter envelope
        client.send_message('/mod/sine/freq', 800.0)
        client.send_message('/mod/adsr/attack', 0.5)
        client.send_message('/mod/adsr/decay', 20.0)
        client.send_message('/mod/adsr/release', 50.0)
        client.send_message('/mod/filter/cutoff', 4000.0)
        
        client.send_message('/seq/assign', ['hihat', 'gate', 'adsr'])
        client.send_message('/seq/gate_len', ['hihat', 0.1])  # Very short gates
        time.sleep(0.2)
        
        # 2. Start recording
        print("\n2. Starting recording...")
        client.send_message('/record/start', 'test_multi_sequencer.wav')
        time.sleep(0.5)
        
        # 3. Start both sequencers
        print("\n3. Starting kick and hihat...")
        client.send_message('/seq/reset_all', [])  # Sync to downbeat
        client.send_message('/seq/start', 'kick')
        client.send_message('/seq/start', 'hihat')
        
        # Run for 8 seconds
        print("   Running for 8 seconds...")
        time.sleep(8)
        
        # 4. Stop and save
        print("\n4. Stopping...")
        client.send_message('/seq/stop', 'kick')
        client.send_message('/seq/stop', 'hihat')
        time.sleep(1)
        
        client.send_message('/record/stop', [])
        time.sleep(0.5)
        
        print("\n=== Multi-Sequencer Test Complete ===")
        print("Check test_multi_sequencer.wav")
        print("Expected: Kick and hihat playing in sync")
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True


if __name__ == '__main__':
    # Run tests
    print("Starting sequencer integration tests...")
    print("Prerequisites:")
    print("1. Run: export CHRONUS_ROUTER=1")
    print("2. Run: python src/music_chronus/supervisor_v3_router.py")
    print("3. Then run this test script")
    print("\nPress Enter when ready...")
    input()
    
    success = test_sequencer_kick_pattern()
    if success:
        print("\nPress Enter to run multi-sequencer test...")
        input()
        test_multi_sequencer()
    
    print("\n=== All Tests Complete ===")