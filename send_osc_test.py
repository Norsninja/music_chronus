#!/usr/bin/env python3
"""
Send test OSC commands to the Windows Audio Engine
"""

from pythonosc import udp_client
import time

# Create OSC client
client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

print("Sending OSC test commands...")

# Turn on the gate and set initial frequency
print("\n1. Starting tone at 440Hz...")
client.send_message("/amplitude", 0.3)
client.send_message("/frequency", 440.0)
client.send_message("/gate", 1)
time.sleep(2)

# Sweep through some frequencies
print("2. Frequency sweep...")
for freq in [220, 330, 440, 550, 660, 880, 440]:
    print(f"   {freq}Hz")
    client.send_message("/frequency", freq)
    time.sleep(0.5)

# Play a simple melody (C major scale)
print("\n3. Playing C major scale...")
notes = [
    261.63,  # C4
    293.66,  # D4
    329.63,  # E4
    349.23,  # F4
    392.00,  # G4
    440.00,  # A4
    493.88,  # B4
    523.25,  # C5
]

for note in notes:
    print(f"   {note:.1f}Hz")
    client.send_message("/frequency", note)
    time.sleep(0.3)

# Amplitude modulation
print("\n4. Amplitude fade in/out...")
client.send_message("/frequency", 440.0)
for i in range(10):
    amp = i / 10.0
    client.send_message("/amplitude", amp)
    time.sleep(0.1)
for i in range(10, -1, -1):
    amp = i / 10.0
    client.send_message("/amplitude", amp)
    time.sleep(0.1)

# Gate on/off pattern (rhythm)
print("\n5. Rhythmic pattern...")
client.send_message("/frequency", 330.0)
client.send_message("/amplitude", 0.4)
for _ in range(8):
    client.send_message("/gate", 1)
    time.sleep(0.2)
    client.send_message("/gate", 0)
    time.sleep(0.1)

# Final chord-like effect (rapid alternation)
print("\n6. Chord simulation (rapid notes)...")
client.send_message("/amplitude", 0.2)
chord = [261.63, 329.63, 392.00]  # C, E, G (C major)
for _ in range(30):
    for note in chord:
        client.send_message("/frequency", note)
        client.send_message("/gate", 1)
        time.sleep(0.03)

# Turn off
print("\n7. Turning off...")
client.send_message("/gate", 0)

print("\nTest complete! The engine should still be running.")
print("You can send more commands or press Ctrl+C in the engine window to stop.")