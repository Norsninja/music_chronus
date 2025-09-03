#!/usr/bin/env python3
"""Test the complete fix with spawn/forkserver and command application."""

import os
import sys
import time
import multiprocessing

# Set environment
os.environ['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'
os.environ['CHRONUS_VERBOSE'] = '1'

# Set start method BEFORE any imports
multiprocessing.set_start_method('forkserver', force=True)

# Now import supervisor
from src.music_chronus.supervisor_v2_fixed import AudioSupervisor
from src.music_chronus.module_host import pack_command_v2, CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL

print("=" * 60)
print("FINAL FIX TEST - Forkserver + Command Application")
print("=" * 60)

# Create and start supervisor
supervisor = AudioSupervisor()
print("\n1. Starting supervisor...")
if not supervisor.start():
    print("Failed to start supervisor")
    sys.exit(1)

# Wait for warmup
time.sleep(2)

print("\n2. Checking worker status...")
status = supervisor.get_status()
print(f"   Running: {status['running']}")
print(f"   Buffers processed: {status['metrics']['buffers_processed']}")
print(f"   Commands sent: {status['metrics']['commands_sent']}")

print("\n3. Sending commands to enable audio...")

# Set parameters in order
commands = [
    ("Setting sine gain", pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'gain', 0.5)),
    ("Setting filter cutoff", pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'filter', 'cutoff', 10000.0)),
    ("Setting filter Q", pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'filter', 'q', 0.707)),
    ("Setting sine frequency", pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'freq', 440.0)),
    ("Enabling ADSR gate", pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, 'adsr', 'gate', 1.0)),
]

for desc, cmd in commands:
    print(f"   {desc}...")
    old_count = supervisor.metrics.commands_sent
    supervisor.broadcast_command_raw(cmd)
    new_count = supervisor.metrics.commands_sent
    print(f"      Commands sent: {old_count} -> {new_count}")
    time.sleep(0.1)

print("\n4. Waiting for audio (3 seconds)...")
print("   You should hear a 440Hz tone if everything works!")
time.sleep(3)

print("\n5. Final status...")
status = supervisor.get_status()
print(f"   Buffers processed: {status['metrics']['buffers_processed']}")
print(f"   Underruns: {status['metrics']['underruns']}")
print(f"   Commands sent: {status['metrics']['commands_sent']}")
print(f"   Active worker: {status['metrics']['active_worker']}")

print("\n6. Stopping...")
supervisor.stop()

print("\nTest complete!")