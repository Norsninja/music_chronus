#!/usr/bin/env python3
"""
Test master recording functionality
Tests recording during playback with all effects active
"""

import time
from pythonosc import udp_client

def test_recording():
    """Test recording with various audio configurations"""
    
    print("[TEST] Master Recording Test")
    print("="*50)
    
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    # Check recording status first
    print("\n1. Checking recording status...")
    client.send_message("/engine/record/status", None)
    time.sleep(0.5)
    
    # Test 1: Simple recording with single voice
    print("\n2. Testing simple recording (5 seconds)")
    print("   Starting recording...")
    client.send_message("/engine/record/start", None)  # Auto-timestamp filename
    time.sleep(0.5)
    
    # Play a simple melody
    print("   Playing melody on voice1...")
    client.send_message("/mod/voice1/amp", 0.3)
    notes = [220, 277, 330, 440, 330, 277, 220]
    
    for note in notes:
        client.send_message("/mod/voice1/freq", note)
        client.send_message("/gate/voice1", 1)
        time.sleep(0.5)
        client.send_message("/gate/voice1", 0)
        time.sleep(0.2)
    
    print("   Stopping recording...")
    client.send_message("/engine/record/stop", None)
    time.sleep(0.5)
    
    # Test 2: Recording with all effects and modulations
    print("\n3. Testing complex recording (10 seconds)")
    print("   Setting up effects and modulations...")
    
    # Setup voices
    client.send_message("/mod/voice1/osc/type", 0)  # Sine
    client.send_message("/mod/voice2/osc/type", 1)  # Saw
    client.send_message("/mod/voice3/osc/type", 2)  # Square
    client.send_message("/mod/voice4/osc/type", 0)  # Sine
    
    # Setup effects
    client.send_message("/mod/voice1/send/reverb", 0.3)
    client.send_message("/mod/voice2/send/delay", 0.4)
    client.send_message("/mod/voice3/send/reverb", 0.2)
    
    # Setup slide
    client.send_message("/mod/voice1/slide_time", 0.2)
    client.send_message("/mod/voice2/slide_time", 0.1)
    
    # Setup distortion
    client.send_message("/mod/dist1/drive", 0.3)
    client.send_message("/mod/dist1/mix", 0.5)
    
    # LFOs are already active on voice2 and voice3
    
    print("   Starting recording with custom name...")
    client.send_message("/engine/record/start", "test_complex_audio.wav")
    time.sleep(0.5)
    
    print("   Playing complex pattern...")
    # Voice 1: Bass line with slide
    client.send_message("/mod/voice1/amp", 0.3)
    client.send_message("/gate/voice1", 1)
    bass_notes = [110, 110, 165, 110, 220, 165, 110, 110]
    
    # Voice 2: Lead with filter wobble (LFO1)
    client.send_message("/mod/voice2/amp", 0.25)
    client.send_message("/mod/voice2/filter/freq", 800)
    client.send_message("/mod/voice2/filter/q", 4)
    client.send_message("/gate/voice2", 1)
    
    # Voice 3: Pad with tremolo (LFO2)
    client.send_message("/mod/voice3/amp", 0.2)
    client.send_message("/mod/voice3/freq", 440)
    client.send_message("/gate/voice3", 1)
    
    # Voice 4: High melody
    client.send_message("/mod/voice4/amp", 0.15)
    
    # Play pattern
    for i, bass in enumerate(bass_notes):
        # Bass movement
        client.send_message("/mod/voice1/freq", bass)
        
        # Lead movement
        client.send_message("/mod/voice2/freq", bass * 2)
        
        # Melody notes
        if i % 2 == 0:
            client.send_message("/mod/voice4/freq", 880)
            client.send_message("/gate/voice4", 1)
        else:
            client.send_message("/gate/voice4", 0)
        
        time.sleep(0.5)
    
    # Stop all voices
    for i in range(1, 5):
        client.send_message(f"/gate/voice{i}", 0)
    
    time.sleep(1)
    
    print("   Stopping recording...")
    client.send_message("/engine/record/stop", None)
    time.sleep(0.5)
    
    # Test 3: Verify no recording conflicts
    print("\n4. Testing recording conflict prevention")
    print("   Starting first recording...")
    client.send_message("/engine/record/start", "test_first.wav")
    time.sleep(0.5)
    
    print("   Attempting second recording (should fail)...")
    client.send_message("/engine/record/start", "test_second.wav")
    time.sleep(0.5)
    
    print("   Stopping recording...")
    client.send_message("/engine/record/stop", None)
    time.sleep(0.5)
    
    # Final status check
    print("\n5. Final recording status check...")
    client.send_message("/engine/record/status", None)
    
    print("\n" + "="*50)
    print("[TEST] Recording test complete!")
    print("[TEST] Check 'recordings' folder for output files")
    print("[TEST] Files should have no dropouts and clean audio")

if __name__ == "__main__":
    print("Make sure engine_pyo.py is running before starting this test")
    print("This test will create WAV files in the 'recordings' folder")
    print("Press Ctrl+C to abort test")
    print()
    
    try:
        test_recording()
    except KeyboardInterrupt:
        print("\n[TEST] Aborted by user")
    except Exception as e:
        print(f"[TEST] Error: {e}")