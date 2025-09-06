#!/usr/bin/env python3
"""
Debug OSC test - Send messages with different patterns to diagnose
"""

import time
from pythonosc import udp_client

print("OSC Debug Test")
print("=" * 50)

# Create OSC client
client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

print("\n1. Testing direct frequency (old pattern)...")
client.send_message("/frequency", 440.0)
time.sleep(0.5)

print("2. Testing direct gate (old pattern)...")
client.send_message("/gate", 1.0)
time.sleep(1.0)
client.send_message("/gate", 0.0)
time.sleep(0.5)

print("\n3. Testing /module/ pattern (what test script uses)...")
client.send_message("/module/sine/freq", 440.0)
time.sleep(0.5)
client.send_message("/module/adsr/gate", 1.0)
time.sleep(1.0)
client.send_message("/module/adsr/gate", 0.0)
time.sleep(0.5)

print("\n4. Testing /mod/ pattern (mentioned by Senior Dev)...")
client.send_message("/mod/sine/freq", 440.0)
time.sleep(0.5)
client.send_message("/mod/adsr/gate", 1.0)
time.sleep(1.0)
client.send_message("/mod/adsr/gate", 0.0)
time.sleep(0.5)

print("\nTest complete. Check if any pattern produced sound.")