#!/usr/bin/env python3
"""
Test SimpleSine at different frequencies to confirm buffer clicking
"""

import time
from pythonosc import udp_client

print("SIMPLESINE BUFFER CLICK TEST")
print("=" * 50)
print("Testing if clicks are consistent across frequencies")
print("(Should be ~94 clicks/second at 48kHz/512 buffer)")
print()

client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

frequencies = [110, 220, 440, 880, 1760]

for freq in frequencies:
    print(f"Testing {freq}Hz for 3 seconds...")
    print("  Count the clicks - should be ~94/sec regardless of frequency")
    
    client.send_message("/frequency", float(freq))
    client.send_message("/gate", 1.0)
    time.sleep(3.0)
    client.send_message("/gate", 0.0)
    time.sleep(0.5)
    print()

print("=" * 50)
print("DIAGNOSIS:")
print("- If clicking rate was constant (~94/sec) for all frequencies:")
print("  → SimpleSine has buffer boundary discontinuity")
print("- If clicking varied with frequency:")
print("  → Phase wrapping or calculation issue")
print("- If no clicks on some frequencies:")
print("  → Specific phase alignment problem")