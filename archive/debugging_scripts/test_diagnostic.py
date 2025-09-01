#!/usr/bin/env python3
"""Diagnostic test to see what's happening in the audio pipeline."""

import os
import time
from pythonosc import udp_client

# Set environment BEFORE importing the supervisor
os.environ['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'
os.environ['CHRONUS_VERBOSE'] = '1'

# Now import
from src.music_chronus.supervisor_v2_fixed import AudioSupervisor

print("Starting diagnostic test...")
print(f"PULSE_SERVER: {os.environ.get('PULSE_SERVER')}")

# Start supervisor
supervisor = AudioSupervisor()
supervisor.start()

print("\nWaiting for startup...")
time.sleep(2)

# Send test commands
print("\nSending OSC commands...")
client = udp_client.SimpleUDPClient('127.0.0.1', 5005)

client.send_message('/mod/sine/gain', 0.9)
client.send_message('/mod/filter/cutoff', 10000.0)
client.send_message('/mod/filter/q', 0.7)
client.send_message('/mod/sine/freq', 440.0)
print("Parameters set, triggering gate...")
client.send_message('/gate/adsr', 'on')

print("\nPlaying for 3 seconds...")
time.sleep(3)

# Check metrics
print("\nMetrics:")
print(f"  Buffers processed: {supervisor.metrics.buffers_processed}")
print(f"  Commands sent: {supervisor.metrics.commands_sent}")
print(f"  Underruns: {supervisor.metrics.underruns}")

# Check if audio ring has data
print(f"\nChecking audio rings:")
print(f"  Active ring is primary: {supervisor.active_ring == supervisor.primary_audio_ring}")

# Get a buffer to see if it's silent
buffer = supervisor.active_ring.read_latest()
if buffer is not None:
    import numpy as np
    print(f"  Buffer stats: min={np.min(buffer):.4f}, max={np.max(buffer):.4f}, mean={np.mean(buffer):.4f}")
    if np.max(np.abs(buffer)) < 0.0001:
        print("  ⚠️ BUFFER IS SILENT!")
else:
    print("  ⚠️ NO BUFFER AVAILABLE!")

client.send_message('/gate/adsr', 'off')
supervisor.stop()
print("\nDiagnostic complete.")