#!/usr/bin/env python3
"""Debug OSC connectivity and audio generation."""

import time
import sys
from pythonosc import udp_client

print("OSC Debug Test")
print("=" * 50)

# Create client
client = udp_client.SimpleUDPClient('127.0.0.1', 5005)
print(f"✓ OSC client created targeting 127.0.0.1:5005")

# Test sequence with explicit steps
print("\n1. Setting oscillator frequency...")
client.send_message('/mod/sine/freq', 440.0)
time.sleep(0.1)

print("2. Setting oscillator gain to maximum...")
client.send_message('/mod/sine/gain', 1.0)
time.sleep(0.1)

print("3. Opening filter completely...")
client.send_message('/mod/filter/cutoff', 20000.0)
time.sleep(0.1)

print("4. Setting filter Q to minimum...")
client.send_message('/mod/filter/q', 0.7)
time.sleep(0.1)

print("5. Setting ADSR for instant attack...")
client.send_message('/mod/adsr/attack', 0.1)
client.send_message('/mod/adsr/decay', 100.0)
client.send_message('/mod/adsr/sustain', 1.0)
client.send_message('/mod/adsr/release', 100.0)
time.sleep(0.1)

print("\n6. TRIGGERING GATE ON...")
client.send_message('/gate/adsr', 'on')
print("   *** YOU SHOULD HEAR SOUND NOW ***")
time.sleep(2)

print("\n7. Gate OFF...")
client.send_message('/gate/adsr', 'off')

print("\n8. Testing legacy endpoints...")
client.send_message('/engine/freq', 880.0)
client.send_message('/engine/amp', 1.0)
time.sleep(0.1)

print("9. Gate ON with legacy frequency...")
client.send_message('/gate/adsr', 'on')
print("   *** Should hear 880Hz now ***")
time.sleep(2)

print("10. Gate OFF...")
client.send_message('/gate/adsr', 'off')

print("\n" + "=" * 50)
print("Test complete.")
print("\nIf you heard nothing, check:")
print("1. Is 'Audio stream started' shown in Pane 1?")
print("2. Run: pactl list sinks short")
print("3. Run: pactl get-sink-volume @DEFAULT_SINK@")