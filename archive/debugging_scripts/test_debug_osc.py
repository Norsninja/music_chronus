#!/usr/bin/env python3
"""Debug why commands aren't being sent to workers."""

import os
os.environ['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'

from src.music_chronus.supervisor_v2_fixed import AudioSupervisor
import time

# Start supervisor
supervisor = AudioSupervisor()

print("Before start:")
print(f"  primary_worker: {supervisor.primary_worker}")
print(f"  standby_worker: {supervisor.standby_worker}")

supervisor.start()
time.sleep(1)

print("\nAfter start:")
print(f"  primary_worker: {supervisor.primary_worker}")
print(f"  standby_worker: {supervisor.standby_worker}")
print(f"  running: {supervisor.running}")

# Try broadcasting directly
from src.music_chronus.module_host import pack_command_v2, CMD_OP_SET, CMD_TYPE_FLOAT

print("\nTrying direct broadcast...")
cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'freq', 440.0)
print(f"  Command packed: {len(cmd)} bytes")

old_count = supervisor.metrics.commands_sent
supervisor.broadcast_command_raw(cmd)
new_count = supervisor.metrics.commands_sent

print(f"  Commands sent before: {old_count}")
print(f"  Commands sent after: {new_count}")
print(f"  Difference: {new_count - old_count}")

supervisor.stop()