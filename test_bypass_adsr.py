#!/usr/bin/env python3
"""
Test to isolate clicking source - is it ADSR or elsewhere?
"""

import time
from pythonosc import udp_client

print("DIAGNOSTIC: Isolating click source")
print("=" * 50)

client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

print("\nTest A: ADSR always ON (gate held high)")
print("-" * 40)
client.send_message("/frequency", 440.0)
client.send_message("/gate", 1.0)  # Gate ON and KEEP it on
print("Gate is ON - listen for 3 seconds...")
print("Should hear continuous tone after attack phase")
print("If clicking persists, it's NOT gate transitions!")
time.sleep(3.0)

print("\nTest B: Change frequency while gate stays ON")
print("-" * 40)
print("Gate still ON, changing frequencies...")
for freq in [330, 440, 550, 440]:
    print(f"  Freq: {freq}Hz")
    client.send_message("/frequency", float(freq))
    time.sleep(0.5)
print("Did frequency changes cause clicks?")
time.sleep(0.5)

print("\nTest C: Change amplitude while gate stays ON")  
print("-" * 40)
print("Gate still ON, changing amplitude...")
for amp in [0.3, 0.5, 0.7, 0.5, 0.3]:
    print(f"  Amplitude: {amp}")
    client.send_message("/amplitude", float(amp))
    time.sleep(0.5)
print("Did amplitude changes cause clicks?")

# Finally release
client.send_message("/gate", 0.0)
print("\nGate released.")

print("\n" + "=" * 50)
print("CRITICAL QUESTIONS:")
print("1. With gate held ON, did clicking continue?")
print("   YES = Problem is NOT ADSR transitions")
print("   NO = Problem IS ADSR related")
print()
print("2. Which caused clicks?")
print("   - Frequency changes?")
print("   - Amplitude changes?")
print("   - Continuous tone with no changes?")
print()
print("This tells us where to look next!")