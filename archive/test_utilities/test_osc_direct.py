#!/usr/bin/env python3
"""Direct OSC test to synthesizer."""

from pythonosc import udp_client
import time

print("Direct OSC Test")
print("-" * 40)

client = udp_client.SimpleUDPClient('127.0.0.1', 5005)

print("Setting up sound parameters...")
client.send_message('/mod/sine/freq', 440.0)
client.send_message('/mod/sine/gain', 0.9)
client.send_message('/mod/filter/cutoff', 10000.0)
client.send_message('/mod/filter/q', 0.7)

print("Playing note for 2 seconds...")
client.send_message('/gate/adsr', 'on')
time.sleep(2)
client.send_message('/gate/adsr', 'off')

print("Test complete. Did you hear the note?")