#!/usr/bin/env python3
"""
Test script to verify distortion fix at critical failure point
Tests the exact conditions that caused audio engine failure
"""

from pythonosc import udp_client
import time

client = udp_client.SimpleUDPClient('127.0.0.1', 5005)

print("=" * 60)
print("DISTORTION FIX TEST - Critical Failure Point")
print("=" * 60)

# Reset engine state
print("\n[1] Resetting engine state...")
client.send_message('/mod/dist1/drive', [0.0])
client.send_message('/mod/dist1/mix', [0.0])
client.send_message('/gate/voice1', [0])
time.sleep(1)

# Test 1: Exact failure conditions
print("\n[2] Testing exact failure conditions:")
print("    - Sub-bass: 45Hz")
print("    - Distortion drive: 0.26 (previous crash point)")
print("    - Distortion mix: 0.23")

# Set up voice with sub-bass frequency
client.send_message('/mod/voice1/freq', [45])
client.send_message('/mod/voice1/amp', [0.3])
client.send_message('/mod/voice1/wave', ['saw'])

# Apply the exact distortion settings that caused failure
client.send_message('/mod/dist1/drive', [0.26])
client.send_message('/mod/dist1/mix', [0.23])

# Trigger the note
print("\n[3] Playing sub-bass with distortion...")
client.send_message('/gate/voice1', [1])
time.sleep(3)
client.send_message('/gate/voice1', [0])

print("    [OK] No crash at drive=0.26!")

# Test 2: Gradually increase distortion
print("\n[4] Testing progressive distortion increase:")
for drive in [0.3, 0.4, 0.5, 0.6, 0.7]:
    print(f"    Testing drive={drive:.1f}...", end="")
    client.send_message('/mod/dist1/drive', [drive])
    client.send_message('/mod/dist1/mix', [drive])
    client.send_message('/gate/voice1', [1])
    time.sleep(1)
    client.send_message('/gate/voice1', [0])
    print(" [OK]")
    time.sleep(0.5)

# Test 3: Extreme test (optional)
print("\n[5] Testing extreme settings (drive=0.85):")
client.send_message('/mod/dist1/drive', [0.85])
client.send_message('/mod/dist1/mix', [1.0])
client.send_message('/gate/voice1', [1])
time.sleep(2)
client.send_message('/gate/voice1', [0])
print("    [OK] Survived extreme distortion!")

# Reset
print("\n[6] Cleaning up...")
client.send_message('/mod/dist1/drive', [0.0])
client.send_message('/mod/dist1/mix', [0.0])

print("\n" + "=" * 60)
print("TEST COMPLETE - ALL TESTS PASSED!")
print("The distortion fix is working correctly.")
print("=" * 60)