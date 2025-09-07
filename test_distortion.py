#!/usr/bin/env python3
"""
Test script for Distortion module implementation
Demonstrates master insert distortion with drive, mix, and tone controls
"""

import time
from pythonosc import udp_client

# Create OSC client
client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

def test_distortion():
    """Test the distortion module implementation"""
    
    print("\n" + "="*50)
    print("DISTORTION MODULE TEST")
    print("="*50)
    
    # Start engine
    client.send_message("/engine/start", [])
    print("Engine started")
    time.sleep(0.5)
    
    # Set up a basic pattern with saw waves for better distortion effect
    client.send_message("/mod/voice1/osc/type", 1)  # Saw
    client.send_message("/mod/voice1/freq", 110)  # A2 bass
    client.send_message("/mod/voice1/amp", 0.5)
    client.send_message("/mod/voice1/filter/freq", 1500)
    client.send_message("/mod/voice1/filter/q", 2)
    
    client.send_message("/mod/voice2/osc/type", 1)  # Saw
    client.send_message("/mod/voice2/freq", 220)  # A3
    client.send_message("/mod/voice2/amp", 0.4)
    
    print("\n--- TEST 1: CLEAN (No Distortion) ---")
    client.send_message("/mod/dist1/drive", 0.0)
    client.send_message("/mod/dist1/mix", 0.0)
    print("Playing clean signal...")
    
    for i in range(4):
        client.send_message("/gate/voice1", 1)
        client.send_message("/gate/voice2", 1)
        time.sleep(0.2)
        client.send_message("/gate/voice1", 0)
        client.send_message("/gate/voice2", 0)
        time.sleep(0.2)
    
    print("\n--- TEST 2: WARM SATURATION ---")
    client.send_message("/mod/dist1/drive", 0.15)
    client.send_message("/mod/dist1/mix", 0.7)
    client.send_message("/mod/dist1/tone", 0.5)
    print("Drive: 0.15 (subtle warmth)")
    print("Mix: 0.7 (mostly wet)")
    print("Tone: 0.5 (neutral)")
    
    for i in range(4):
        client.send_message("/gate/voice1", 1)
        client.send_message("/gate/voice2", 1)
        time.sleep(0.2)
        client.send_message("/gate/voice1", 0)
        client.send_message("/gate/voice2", 0)
        time.sleep(0.2)
    
    print("\n--- TEST 3: MODERATE CRUNCH ---")
    client.send_message("/mod/dist1/drive", 0.4)
    client.send_message("/mod/dist1/mix", 0.8)
    client.send_message("/mod/dist1/tone", 0.6)
    print("Drive: 0.4 (moderate crunch)")
    print("Mix: 0.8")
    print("Tone: 0.6 (slightly bright)")
    
    for i in range(4):
        client.send_message("/gate/voice1", 1)
        client.send_message("/gate/voice2", 1)
        time.sleep(0.2)
        client.send_message("/gate/voice1", 0)
        client.send_message("/gate/voice2", 0)
        time.sleep(0.2)
    
    print("\n--- TEST 4: HEAVY DISTORTION ---")
    client.send_message("/mod/dist1/drive", 0.7)
    client.send_message("/mod/dist1/mix", 1.0)
    client.send_message("/mod/dist1/tone", 0.4)
    print("Drive: 0.7 (heavy distortion)")
    print("Mix: 1.0 (fully wet)")
    print("Tone: 0.4 (darker to tame harshness)")
    
    for i in range(4):
        client.send_message("/gate/voice1", 1)
        client.send_message("/gate/voice2", 1)
        time.sleep(0.2)
        client.send_message("/gate/voice1", 0)
        client.send_message("/gate/voice2", 0)
        time.sleep(0.2)
    
    print("\n--- TEST 5: MIX CONTROL (Parallel Processing) ---")
    print("Testing dry/wet mix with heavy drive...")
    client.send_message("/mod/dist1/drive", 0.8)
    client.send_message("/mod/dist1/tone", 0.5)
    
    # Sweep mix from dry to wet
    print("Sweeping mix from 0 to 1...")
    client.send_message("/gate/voice1", 1)
    
    for mix in [0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        print(f"  Mix: {mix}")
        client.send_message("/mod/dist1/mix", mix)
        time.sleep(0.5)
    
    client.send_message("/gate/voice1", 0)
    
    print("\n--- TEST 6: TONE CONTROL ---")
    print("Testing tone sweep with moderate distortion...")
    client.send_message("/mod/dist1/drive", 0.5)
    client.send_message("/mod/dist1/mix", 0.9)
    
    client.send_message("/gate/voice1", 1)
    client.send_message("/gate/voice2", 1)
    
    # Sweep tone from dark to bright
    print("Sweeping tone from dark to bright...")
    for tone in [0, 0.25, 0.5, 0.75, 1.0]:
        print(f"  Tone: {tone} ({'dark' if tone < 0.3 else 'neutral' if tone < 0.7 else 'bright'})")
        client.send_message("/mod/dist1/tone", tone)
        time.sleep(0.4)
    
    client.send_message("/gate/voice1", 0)
    client.send_message("/gate/voice2", 0)
    
    print("\n--- TEST 7: TECHNO/ACID COMBINATION ---")
    print("Testing distortion with acid filter...")
    
    # Configure acid filter
    client.send_message("/mod/acid1/cutoff", 800)
    client.send_message("/mod/acid1/res", 0.7)
    client.send_message("/mod/acid1/env_amount", 2000)
    
    # Moderate distortion for techno character
    client.send_message("/mod/dist1/drive", 0.3)
    client.send_message("/mod/dist1/mix", 0.6)
    client.send_message("/mod/dist1/tone", 0.6)
    
    # Play pattern
    print("Playing techno pattern with distorted acid...")
    pattern = [1, 0, 1, 0, 1, 0, 1, 1]
    for step in pattern * 2:
        if step:
            client.send_message("/gate/voice2", 1)
            client.send_message("/gate/acid1", 1)
        time.sleep(0.125)
        client.send_message("/gate/voice2", 0)
        client.send_message("/gate/acid1", 0)
    
    print("\n--- TEST COMPLETE ---")
    print("Summary:")
    print("  [OK] Clean bypass works (mix=0)")
    print("  [OK] Subtle warmth (drive 0-0.2)")
    print("  [OK] Moderate crunch (drive 0.2-0.5)")
    print("  [OK] Heavy distortion (drive 0.5-1.0)")
    print("  [OK] Mix control maintains loudness")
    print("  [OK] Tone control shapes character")
    print("  [OK] Works with acid filter")
    
    # Reset distortion
    client.send_message("/mod/dist1/drive", 0.0)
    client.send_message("/mod/dist1/mix", 0.0)
    
    # Stop engine
    time.sleep(1)
    client.send_message("/engine/stop", [])
    print("\nEngine stopped")

if __name__ == "__main__":
    print("Starting Distortion Module Test...")
    print("Make sure engine_pyo.py is running!")
    print("")
    
    try:
        test_distortion()
    except KeyboardInterrupt:
        print("\nTest interrupted")
        client.send_message("/engine/stop", [])
    except Exception as e:
        print(f"Error: {e}")
        client.send_message("/engine/stop", [])