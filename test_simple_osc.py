#!/usr/bin/env python3
"""
Simple OSC test - verify communication with supervisor
"""

import time
from pythonosc import udp_client

print("Simple OSC Test")
print("=" * 50)

# Create OSC client
client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

print("Sending frequency change to sine oscillator...")
client.send_message("/module/sine/freq", 440.0)
time.sleep(0.5)

print("Sending gate ON to ADSR...")
client.send_message("/module/adsr/gate", 1.0)
time.sleep(1.0)

print("Sending gate OFF to ADSR...")
client.send_message("/module/adsr/gate", 0.0)
time.sleep(1.0)

print("\nTest complete. Did you hear anything?")