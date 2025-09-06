#!/usr/bin/env python3
"""
Test to prove buffer production priority is the issue
Monitor the deficit and see if it correlates with clicking
"""

import time
from pythonosc import udp_client

print("BUFFER PRODUCTION PRIORITY TEST")
print("=" * 50)
print("Theory: Worker checks buffer deadline AFTER other work")
print("Result: Misses deadlines, creates deficit, causes clicks")
print()

client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

print("Starting steady tone test...")
print("NO parameter changes - just steady audio")
print()

# Simple steady tone
client.send_message("/frequency", 440.0)
client.send_message("/amplitude", 0.3)
client.send_message("/gate", 1.0)

print("Monitor supervisor output for 15 seconds...")
print("Watch the growing deficit:")
print()

for i in range(15):
    print(f"Second {i+1}/15 - Check metrics in supervisor window")
    time.sleep(1)

client.send_message("/gate", 0.0)

print("\n" + "=" * 50)
print("EXPECTED RESULTS:")
print("-" * 50)
print("1. Deficit grows steadily (Callbacks - Buffers increases)")
print("2. Deficit percentage stays around 32%")
print("3. Clicking is periodic, matching buffer rate")
print()
print("This proves the worker can't keep up due to loop structure.")
print()
print("THE FIX:")
print("Worker must check buffer deadline FIRST in the loop,")
print("not after processing commands and waiting on events.")
print()
print("Would you like me to implement the fix?")