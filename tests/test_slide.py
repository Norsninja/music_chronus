#!/usr/bin/env python3
"""
Test Voice slide/portamento implementation
Tests frequency gliding with 110->220->330 Hz transitions
"""

import time
from pythonosc import udp_client

def test_slide():
    """Test slide/portamento with different slide times"""
    
    print("[TEST] Voice Slide/Portamento Test")
    print("[TEST] Testing frequency glides: 110Hz -> 220Hz -> 330Hz")
    print("="*50)
    
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    # Test 1: No slide (instant changes)
    print("\n1. Testing NO SLIDE (slide_time=0)")
    print("   Should hear instant frequency jumps")
    
    client.send_message("/mod/voice1/slide_time", 0)
    client.send_message("/mod/voice1/amp", 0.3)
    client.send_message("/gate/voice1", 1)
    
    frequencies = [110, 220, 330, 220, 110]
    for freq in frequencies:
        print(f"   Setting frequency: {freq}Hz")
        client.send_message("/mod/voice1/freq", freq)
        time.sleep(1)
    
    client.send_message("/gate/voice1", 0)
    time.sleep(0.5)
    
    # Test 2: Fast slide (0.1s)
    print("\n2. Testing FAST SLIDE (slide_time=0.1s)")
    print("   Should hear quick smooth glides")
    
    client.send_message("/mod/voice1/slide_time", 0.1)
    client.send_message("/gate/voice1", 1)
    
    for freq in frequencies:
        print(f"   Gliding to: {freq}Hz")
        client.send_message("/mod/voice1/freq", freq)
        time.sleep(1.5)
    
    client.send_message("/gate/voice1", 0)
    time.sleep(0.5)
    
    # Test 3: Medium slide (0.3s) - Classic synth portamento
    print("\n3. Testing MEDIUM SLIDE (slide_time=0.3s)")
    print("   Should hear classic synth portamento")
    
    client.send_message("/mod/voice1/slide_time", 0.3)
    client.send_message("/gate/voice1", 1)
    
    for freq in frequencies:
        print(f"   Gliding to: {freq}Hz")
        client.send_message("/mod/voice1/freq", freq)
        time.sleep(2)
    
    client.send_message("/gate/voice1", 0)
    time.sleep(0.5)
    
    # Test 4: Slow slide (0.8s) - Dramatic sweeps
    print("\n4. Testing SLOW SLIDE (slide_time=0.8s)")
    print("   Should hear dramatic pitch sweeps")
    
    client.send_message("/mod/voice1/slide_time", 0.8)
    client.send_message("/gate/voice1", 1)
    
    for freq in frequencies:
        print(f"   Gliding to: {freq}Hz")
        client.send_message("/mod/voice1/freq", freq)
        time.sleep(3)
    
    client.send_message("/gate/voice1", 0)
    time.sleep(0.5)
    
    # Test 5: Slide with different waveforms
    print("\n5. Testing slide with different waveforms")
    
    waveforms = [
        (0, "Sine"),
        (1, "Saw"),
        (2, "Square")
    ]
    
    client.send_message("/mod/voice1/slide_time", 0.25)
    
    for waveform_id, waveform_name in waveforms:
        print(f"\n   Testing {waveform_name} wave:")
        client.send_message("/mod/voice1/osc/type", waveform_id)
        client.send_message("/gate/voice1", 1)
        
        for freq in [110, 220, 330]:
            print(f"     -> {freq}Hz")
            client.send_message("/mod/voice1/freq", freq)
            time.sleep(1.5)
        
        client.send_message("/gate/voice1", 0)
        time.sleep(0.5)
    
    # Test 6: Acid-style slide on voice2
    print("\n6. Testing TB-303 style slide on voice2 with acid filter")
    
    # Setup voice2 with acid filter
    client.send_message("/mod/voice2/osc/type", 1)  # Saw wave
    client.send_message("/mod/voice2/filter/freq", 300)
    client.send_message("/mod/voice2/filter/q", 8)
    client.send_message("/mod/voice2/slide_time", 0.15)  # 303-style slide
    client.send_message("/mod/voice2/amp", 0.4)
    
    print("   Playing acid pattern with slides...")
    client.send_message("/gate/voice2", 1)
    
    # Acid-style pattern with octave jumps
    acid_pattern = [110, 110, 220, 110, 330, 220, 110, 220]
    for freq in acid_pattern:
        print(f"     -> {freq}Hz")
        client.send_message("/mod/voice2/freq", freq)
        time.sleep(0.3)
    
    client.send_message("/gate/voice2", 0)
    
    print("\n" + "="*50)
    print("[TEST] Slide test complete!")
    print("[TEST] All portamento modes tested successfully")

if __name__ == "__main__":
    print("Make sure engine_pyo.py is running before starting this test")
    print("Press Ctrl+C to abort test")
    print()
    
    try:
        test_slide()
    except KeyboardInterrupt:
        print("\n[TEST] Aborted by user")
    except Exception as e:
        print(f"[TEST] Error: {e}")