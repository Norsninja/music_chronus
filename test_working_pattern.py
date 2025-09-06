#!/usr/bin/env python3
"""
Test using ONLY the patterns that actually work
Based on what produced audio in test_simple_osc_debug.py
"""

import time
from pythonosc import udp_client

print("Testing with WORKING OSC patterns")
print("=" * 50)

client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

print("\n1. Simple note test...")
client.send_message("/frequency", 440.0)
client.send_message("/gate", 1.0)
time.sleep(0.5)
client.send_message("/gate", 0.0)
time.sleep(0.5)

print("\n2. Testing different frequencies...")
for freq in [220, 330, 440, 550]:
    print(f"   Playing {freq}Hz...")
    client.send_message("/frequency", float(freq))
    client.send_message("/gate", 1.0)
    time.sleep(0.3)
    client.send_message("/gate", 0.0)
    time.sleep(0.2)

print("\n3. Testing rapid retriggers (bassline)...")
client.send_message("/frequency", 110.0)  # Low bass note
for _ in range(8):
    client.send_message("/gate", 1.0)
    time.sleep(0.1)
    client.send_message("/gate", 0.0)
    time.sleep(0.1)

print("\n4. Testing legato (overlapping gates)...")
client.send_message("/frequency", 440.0)
for _ in range(4):
    client.send_message("/gate", 1.0)
    time.sleep(0.15)
    client.send_message("/gate", 0.0)
    time.sleep(0.05)  # Very short gap

print("\n5. Testing slow envelope...")
client.send_message("/frequency", 330.0)
client.send_message("/gate", 1.0)
time.sleep(2.0)
client.send_message("/gate", 0.0)
time.sleep(2.0)

print("\n" + "=" * 50)
print("COMPLETE! Please report:")
print("1. Did you hear all 5 tests?")
print("2. Were there clicks/pops?")
print("3. How did the rapid retriggers sound?")