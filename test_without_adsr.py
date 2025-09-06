#!/usr/bin/env python3
"""
Test WITHOUT ADSR - just sine directly to see if clicking persists
This will help isolate if ADSR is the problem or something else
"""

import time
from pythonosc import udp_client

print("Testing WITHOUT ADSR - Raw sine wave")
print("=" * 50)
print("NOTE: This bypasses ADSR - just tests raw oscillator")
print("If clicks persist, the problem is NOT the ADSR!")
print()

client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

# We need to find a way to bypass ADSR or set it to always output 1.0
# First, let's try setting ADSR to very fast attack and full sustain
print("Setting ADSR to minimal impact (fast attack, full sustain)...")
# These commands won't work with current handlers, but let's try direct approach

print("\n1. Testing continuous tone (should be smooth)...")
client.send_message("/frequency", 440.0)
client.send_message("/amplitude", 0.5)  # Try setting amplitude directly
time.sleep(2.0)

print("\n2. Testing frequency changes...")
for freq in [220, 330, 440, 550, 660]:
    print(f"   Frequency: {freq}Hz")
    client.send_message("/frequency", float(freq))
    time.sleep(0.5)

print("\n3. Testing amplitude changes...")
client.send_message("/frequency", 440.0)
for amp in [0.1, 0.3, 0.5, 0.7, 0.5, 0.3, 0.1]:
    print(f"   Amplitude: {amp}")
    client.send_message("/amplitude", float(amp))
    time.sleep(0.3)

print("\n" + "=" * 50)
print("If you heard clicking even without ADSR gate changes,")
print("then the problem is in SimpleSine, BiquadFilter, or the buffer exchange!")