#!/usr/bin/env python3
"""
Component isolation test - find which module causes clicks
Strategy: We'll try to bypass components to isolate the culprit
"""

import time
from pythonosc import udp_client

print("COMPONENT ISOLATION TEST")
print("=" * 50)

client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

print("\nPREP: Setting up baseline...")
client.send_message("/frequency", 440.0)
client.send_message("/amplitude", 0.5)

print("\n" + "="*50)
print("TEST 1: Steady tone, no changes")
print("-" * 50)
print("Gate ON, holding for 5 seconds...")
print("Listen for periodic clicks (every ~10ms)")
client.send_message("/gate", 1.0)
time.sleep(5.0)
client.send_message("/gate", 0.0)
time.sleep(1.0)

print("\n" + "="*50)
print("TEST 2: Filter cutoff sweep (if filter is the issue)")
print("-" * 50)
print("Gate ON, sweeping filter cutoff...")
client.send_message("/gate", 1.0)

# Try to control filter (these OSC addresses might not work, but let's try)
print("Attempting filter control (may not be implemented)...")
for cutoff in [500, 1000, 2000, 4000, 2000, 1000, 500]:
    print(f"  Cutoff: {cutoff}Hz")
    # These won't work with current handlers, but document the attempt
    client.send_message("/filter/cutoff", float(cutoff))
    client.send_message("/mod/filter/cutoff", float(cutoff))
    time.sleep(0.5)

client.send_message("/gate", 0.0)
time.sleep(1.0)

print("\n" + "="*50)
print("TEST 3: Very slow frequency change (phase continuity test)")
print("-" * 50)
print("Gate ON, very gradual frequency change...")
client.send_message("/gate", 1.0)

# Change frequency very slowly to test phase continuity
base_freq = 440.0
for i in range(20):
    freq = base_freq + (i * 5)  # 440 -> 535 Hz over 20 steps
    client.send_message("/frequency", freq)
    time.sleep(0.1)  # Quick changes

client.send_message("/gate", 0.0)
time.sleep(1.0)

print("\n" + "="*50)
print("TEST 4: Single frequency, different amplitudes")
print("-" * 50)
print("Testing if gain changes cause clicks...")
client.send_message("/frequency", 440.0)
client.send_message("/gate", 1.0)

for amp in [0.1, 0.2, 0.3, 0.4, 0.5, 0.4, 0.3, 0.2, 0.1]:
    print(f"  Amplitude: {amp}")
    client.send_message("/amplitude", amp)
    time.sleep(0.3)

client.send_message("/gate", 0.0)

print("\n" + "="*50)
print("RESULTS TO REPORT:")
print("-" * 50)
print("1. TEST 1 (steady tone): Clicks? YES/NO")
print("   - If YES: Problem is in buffer exchange or synthesis")
print("   - If NO: Problem is in parameter changes")
print()
print("2. TEST 2 (filter sweep): Different clicks? Worse?")
print("   - May not work if filter control not implemented")
print()
print("3. TEST 3 (frequency sweep): More clicks during changes?")
print("   - If YES: SimpleSine phase discontinuity")
print()
print("4. TEST 4 (amplitude changes): Clicks at change points?")
print("   - If YES: Gain parameter smoothing issue")
print()
print("Key question: Is clicking PERIODIC (every buffer) or EVENT-BASED (on changes)?")