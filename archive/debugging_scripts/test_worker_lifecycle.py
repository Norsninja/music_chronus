#!/usr/bin/env python3
"""Test to diagnose why workers are being killed immediately."""

import os
import time
import multiprocessing as mp
from multiprocessing import connection

# Set up environment
os.environ['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'
os.environ['CHRONUS_VERBOSE'] = '1'

# Import after environment setup
from src.music_chronus.supervisor_v2_fixed import AudioSupervisor, AudioWorker
from src.music_chronus.supervisor import CommandRing, AudioRing

print("=" * 60)
print("WORKER LIFECYCLE DIAGNOSTIC TEST")
print("=" * 60)

# Test 1: Can we create a worker without supervisor?
print("\n[TEST 1] Creating standalone worker...")
cmd_ring = CommandRing(64)
audio_ring = AudioRing()
heartbeat_array = mp.Array('L', 2, lock=False)
initial_state = {'frequency': 440.0, 'amplitude': 0.5}

worker = AudioWorker(
    worker_id=99,  # Use different ID to avoid conflicts
    cmd_ring=cmd_ring,
    audio_ring=audio_ring,
    heartbeat_array=heartbeat_array,
    initial_state=initial_state
)

print("  Worker created, starting...")
worker.start()
print(f"  Worker started. PID: {worker.pid}")
print(f"  Worker alive? {worker.process.is_alive()}")

# Wait a moment
time.sleep(0.5)
print(f"  After 0.5s - Worker alive? {worker.process.is_alive()}")

# Check sentinel
sentinels = [worker.sentinel]
print("\n  Checking sentinel with connection.wait()...")
ready = connection.wait(sentinels, timeout=0.001)
if ready:
    print(f"  ⚠️ Sentinel triggered! Worker died!")
else:
    print(f"  ✓ Sentinel OK - worker still alive")

# Clean up test worker
if worker.process.is_alive():
    print("  Terminating test worker...")
    worker.terminate()
    print("  Test worker terminated")
else:
    print("  Worker already dead!")

print("\n" + "=" * 60)
print("[TEST 2] Testing supervisor start sequence...")
print("=" * 60)

# Create supervisor but don't start yet
supervisor = AudioSupervisor()
print("Supervisor created")

# Hook into the start process step by step
print("\n1. Creating primary worker...")
supervisor.primary_worker = AudioWorker(
    worker_id=0,
    cmd_ring=supervisor.primary_cmd_ring,
    audio_ring=supervisor.primary_audio_ring,
    heartbeat_array=supervisor.heartbeat_array,
    initial_state=supervisor.initial_state.copy()
)
supervisor.primary_worker.start()
print(f"   Primary started. PID: {supervisor.primary_worker.pid}")
print(f"   Primary alive? {supervisor.primary_worker.process.is_alive()}")

time.sleep(0.1)
print(f"   After 0.1s - Primary alive? {supervisor.primary_worker.process.is_alive()}")

print("\n2. Creating standby worker...")
supervisor.standby_worker = AudioWorker(
    worker_id=1,
    cmd_ring=supervisor.standby_cmd_ring,
    audio_ring=supervisor.standby_audio_ring,
    heartbeat_array=supervisor.heartbeat_array,
    initial_state=supervisor.initial_state.copy()
)
supervisor.standby_worker.start()
print(f"   Standby started. PID: {supervisor.standby_worker.pid}")
print(f"   Standby alive? {supervisor.standby_worker.process.is_alive()}")

time.sleep(0.1)
print(f"   After 0.1s - Standby alive? {supervisor.standby_worker.process.is_alive()}")

print("\n3. Checking sentinels before monitor thread...")
workers = [supervisor.primary_worker, supervisor.standby_worker]
sentinels = []
for w in workers:
    if w and w.sentinel:
        sentinels.append(w.sentinel)
        
if sentinels:
    ready = connection.wait(sentinels, timeout=0.001)
    if ready:
        print("   ⚠️ Workers died before monitor thread even started!")
        for i, worker in enumerate(workers):
            if worker and worker.sentinel in ready:
                print(f"   Worker {i} is dead!")
    else:
        print("   ✓ Workers still alive before monitor thread")

print("\n4. Starting monitor thread...")
import threading
supervisor.monitor_stop = threading.Event()
supervisor.monitor_thread = threading.Thread(target=supervisor.monitor_workers, daemon=True)
supervisor.monitor_thread.start()
print("   Monitor thread started")

time.sleep(0.1)
print(f"\n5. After monitor thread started (0.1s):")
print(f"   Primary alive? {supervisor.primary_worker.process.is_alive() if supervisor.primary_worker else 'None'}")
print(f"   Standby alive? {supervisor.standby_worker.process.is_alive() if supervisor.standby_worker else 'None'}")

# Clean up
print("\n6. Cleaning up...")
supervisor.monitor_stop.set()
if supervisor.primary_worker and supervisor.primary_worker.process.is_alive():
    supervisor.primary_worker.terminate()
if supervisor.standby_worker and supervisor.standby_worker.process.is_alive():
    supervisor.standby_worker.terminate()

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)