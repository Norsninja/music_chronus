#!/usr/bin/env python3
"""
Test ring buffer health - monitor if worker keeps up with audio callback
This will help us understand why buffers are being missed
"""

import time
from pythonosc import udp_client
import subprocess
import sys

print("RING BUFFER HEALTH TEST")
print("=" * 50)
print("This test monitors buffer production vs consumption")
print("Healthy system: Buffers Processed ≈ Callbacks")
print("Current problem: Buffers << Callbacks (causing clicks)")
print()

client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

print("Setting up steady tone (no parameter changes)...")
client.send_message("/frequency", 440.0)
client.send_message("/amplitude", 0.3)

print("\nPhase 1: Gate OFF (silent) - Baseline measurement")
print("-" * 50)
client.send_message("/gate", 0.0)
print("Monitoring for 5 seconds...")
time.sleep(5)

print("\nPhase 2: Gate ON (playing) - Active measurement")  
print("-" * 50)
client.send_message("/gate", 1.0)
print("Monitoring for 10 seconds...")
print("Watch the supervisor metrics...")
print("- Callbacks should increase steadily")
print("- Buffers Processed should match Callbacks")
print("- Deficit = Callbacks - Buffers")
print()

for i in range(10):
    print(f"  Second {i+1}/10...")
    time.sleep(1)

client.send_message("/gate", 0.0)

print("\n" + "=" * 50)
print("ANALYSIS:")
print("-" * 50)
print("Check supervisor output for final metrics.")
print()
print("Calculate deficit percentage:")
print("  Deficit % = (Callbacks - Buffers) / Callbacks × 100")
print()
print("EXPECTED:")
print("  < 1% deficit = Good (occasional miss OK)")
print("  1-5% deficit = Marginal (some clicks)")
print("  > 5% deficit = Bad (constant clicks)")
print()
print("ACTUAL: ~32% deficit = Severe problem")
print()
print("NEXT STEPS:")
print("1. If deficit persists, worker is too slow")
print("2. Need to profile what's blocking the worker")
print("3. May need to remove processing from worker loop")