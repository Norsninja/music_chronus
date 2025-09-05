#!/usr/bin/env python3
"""
Send test OSC commands to supervisor_windows
"""

from pythonosc import udp_client
import time

# Create OSC client
client = udp_client.SimpleUDPClient('127.0.0.1', 5005)

print("Sending OSC test commands...")

# Turn on the synthesizer
print("Setting frequency to 440Hz")
client.send_message('/frequency', 440.0)
time.sleep(0.1)

print("Setting amplitude to 0.5")
client.send_message('/amplitude', 0.5)
time.sleep(0.1)

print("Turning gate ON")
client.send_message('/gate', 1.0)
time.sleep(2)

# Change frequency
print("Changing frequency to 880Hz")
client.send_message('/frequency', 880.0)
time.sleep(2)

print("Changing frequency to 220Hz")
client.send_message('/frequency', 220.0)
time.sleep(2)

# Turn off
print("Turning gate OFF")
client.send_message('/gate', 0.0)

print("\nTest complete! Check supervisor output for metrics.")