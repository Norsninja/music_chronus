#!/usr/bin/env python3
"""Debug monitor thread behavior."""

import os
import time
import threading

os.environ['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'
os.environ['CHRONUS_VERBOSE'] = '1'

from src.music_chronus.supervisor_v2_fixed import AudioSupervisor

print("=" * 60)
print("MONITOR THREAD DEBUG TEST")
print("=" * 60)

# Create supervisor
supervisor = AudioSupervisor()

# Manually start workers WITHOUT monitor thread
print("\n1. Starting workers manually (no monitor)...")
from src.music_chronus.supervisor_v2_fixed import AudioWorker

supervisor.primary_worker = AudioWorker(
    worker_id=0,
    cmd_ring=supervisor.primary_cmd_ring,
    audio_ring=supervisor.primary_audio_ring,
    heartbeat_array=supervisor.heartbeat_array,
    initial_state=supervisor.initial_state.copy()
)
supervisor.primary_worker.start()
print(f"   Primary started: PID {supervisor.primary_worker.pid}")

supervisor.standby_worker = AudioWorker(
    worker_id=1,
    cmd_ring=supervisor.standby_cmd_ring,
    audio_ring=supervisor.standby_audio_ring,
    heartbeat_array=supervisor.heartbeat_array,
    initial_state=supervisor.initial_state.copy()
)
supervisor.standby_worker.start()
print(f"   Standby started: PID {supervisor.standby_worker.pid}")

# Wait a moment WITHOUT monitor
print("\n2. Waiting 3 seconds WITHOUT monitor thread...")
time.sleep(3)

print("\n3. Check worker status (no monitor running):")
print(f"   Primary alive? {supervisor.primary_worker.process.is_alive()}")
print(f"   Standby alive? {supervisor.standby_worker.process.is_alive()}")

# Check heartbeats
print(f"   Primary heartbeat: {supervisor.heartbeat_array[0]}")
print(f"   Standby heartbeat: {supervisor.heartbeat_array[1]}")

# Now start the monitor
print("\n4. Starting monitor thread NOW...")
supervisor.monitor_stop = threading.Event()
supervisor.respawn_lock = threading.Lock()
from src.music_chronus.supervisor_v2_fixed import AudioMetrics
supervisor.metrics = AudioMetrics()
supervisor.active_idx = 0
supervisor.monitor_thread = threading.Thread(target=supervisor.monitor_workers, daemon=True)
supervisor.monitor_thread.start()

# Watch what happens
print("\n5. Monitoring for 3 seconds...")
for i in range(3):
    time.sleep(1)
    print(f"   After {i+1}s: Primary={supervisor.primary_worker.process.is_alive() if supervisor.primary_worker else 'None'}, "
          f"Standby={supervisor.standby_worker.process.is_alive() if supervisor.standby_worker else 'None'}")

# Stop monitor
print("\n6. Stopping monitor...")
supervisor.monitor_stop.set()
supervisor.monitor_thread.join(timeout=1.0)

# Clean up
print("\n7. Cleaning up...")
if supervisor.primary_worker and supervisor.primary_worker.process.is_alive():
    supervisor.primary_worker.terminate()
if supervisor.standby_worker and supervisor.standby_worker.process.is_alive():
    supervisor.standby_worker.terminate()

print("\nTest complete")