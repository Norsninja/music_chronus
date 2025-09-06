#!/usr/bin/env python3
"""
Test with CORRECT OSC patterns that supervisor actually handles
"""

import time
from pythonosc import udp_client

print("Testing with CORRECT OSC patterns")
print("=" * 50)

client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

print("\n1. Setting frequency with /mod/ pattern...")
client.send_message("/mod/sine/freq", 440.0)

print("2. Simple gate test...")
client.send_message("/mod/adsr/gate", 1.0)
time.sleep(1.0)
client.send_message("/mod/adsr/gate", 0.0)
time.sleep(0.5)

print("\n3. Rapid gates...")
for i in range(4):
    client.send_message("/mod/adsr/gate", 1.0)
    time.sleep(0.2)
    client.send_message("/mod/adsr/gate", 0.0)
    time.sleep(0.2)

print("\nDone! Did you hear sound this time?")