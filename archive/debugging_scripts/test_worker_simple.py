#!/usr/bin/env python3
"""Simple test to understand worker behavior."""

import os
import sys

# Suppress duplicate output by redirecting stderr
original_stderr = sys.stderr
sys.stderr = open('/tmp/worker_stderr.log', 'w')

os.environ['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'

from src.music_chronus.supervisor_v2_fixed import AudioWorker
from src.music_chronus.supervisor import CommandRing, AudioRing
import multiprocessing as mp
import time

print("Creating single worker...")

# Create necessary structures
cmd_ring = CommandRing(64)
audio_ring = AudioRing()
heartbeat_array = mp.Array('L', 2, lock=False)
initial_state = {'frequency': 440.0, 'amplitude': 0.5}

# Create a single worker with ID 0 (valid)
worker = AudioWorker(
    worker_id=0,
    cmd_ring=cmd_ring,
    audio_ring=audio_ring,
    heartbeat_array=heartbeat_array,
    initial_state=initial_state
)

print("Starting worker...")
worker.start()
print(f"Worker started. PID: {worker.pid}")

# Check if it's alive
for i in range(5):
    time.sleep(1)
    alive = worker.process.is_alive()
    hb = heartbeat_array[0]
    print(f"After {i+1}s: alive={alive}, heartbeat={hb}")
    if not alive:
        print("Worker died!")
        break

# Clean up
if worker.process.is_alive():
    print("Terminating worker...")
    worker.terminate()

# Restore stderr and show what was logged
sys.stderr.close()
sys.stderr = original_stderr

print("\nStderr output:")
with open('/tmp/worker_stderr.log', 'r') as f:
    print(f.read())