#!/usr/bin/env python3
"""
Test OSC commands for Windows supervisor
Send commands to generate a test tone
"""

import time
from pythonosc import udp_client

# Create OSC client
client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

print("Sending OSC commands to Windows supervisor...")

# Set frequency to 440 Hz (A4)
print("Setting frequency to 440 Hz")
client.send_message("/frequency", 440.0)
time.sleep(0.1)

# Set amplitude
print("Setting amplitude to 0.3")
client.send_message("/amplitude", 0.3)
time.sleep(0.1)

# Gate on (start sound)
print("Gate ON - should hear sound")
client.send_message("/gate", 1)
time.sleep(2)

# Change frequency
print("Changing frequency to 880 Hz")
client.send_message("/frequency", 880.0)
time.sleep(2)

# Change frequency again
print("Changing frequency to 220 Hz")
client.send_message("/frequency", 220.0)
time.sleep(2)

# Gate off
print("Gate OFF - sound should stop")
client.send_message("/gate", 0)
time.sleep(1)

# Quick melody
print("\nPlaying quick melody...")
notes = [440, 494, 523, 587, 659, 698, 784, 880]  # A major scale
for freq in notes:
    client.send_message("/frequency", float(freq))
    client.send_message("/gate", 1)
    time.sleep(0.2)
    client.send_message("/gate", 0)
    time.sleep(0.05)

print("\nTest complete!")
print("\nIf you heard sound, the Windows supervisor is working!")
print("If not, check:")
print("1. Audio device is connected")
print("2. Volume is up")
print("3. Device 17 (AB13X) is the correct output")