#!/usr/bin/env python3
"""Simple test to see if workers stay alive."""

import os
import time

# Set up environment
os.environ['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'
os.environ['CHRONUS_VERBOSE'] = '1'

# Import after environment setup
from src.music_chronus.supervisor_v2_fixed import AudioSupervisor

print("=" * 60)
print("SIMPLE WORKER TEST")
print("=" * 60)

# Create and start supervisor normally
supervisor = AudioSupervisor()
print("\nStarting supervisor...")
supervisor.start()

# Check workers immediately
print("\nWorker status immediately after start:")
print(f"  Primary: {supervisor.primary_worker}")
print(f"  Primary alive: {supervisor.primary_worker.process.is_alive() if supervisor.primary_worker else 'None'}")
print(f"  Standby: {supervisor.standby_worker}")
print(f"  Standby alive: {supervisor.standby_worker.process.is_alive() if supervisor.standby_worker else 'None'}")

# Wait and check again
time.sleep(2)
print("\nWorker status after 2 seconds:")
print(f"  Primary: {supervisor.primary_worker}")
print(f"  Primary alive: {supervisor.primary_worker.process.is_alive() if supervisor.primary_worker else 'None'}")
print(f"  Standby: {supervisor.standby_worker}")
print(f"  Standby alive: {supervisor.standby_worker.process.is_alive() if supervisor.standby_worker else 'None'}")

# Get status
status = supervisor.get_status()
print("\nSupervisor status:")
print(f"  Running: {status['running']}")
print(f"  Metrics: {status['metrics']}")

# Stop
supervisor.stop()
print("\nTest complete")