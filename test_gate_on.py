#!/usr/bin/env python3
"""Simple test to check if gating ADSR produces sound."""

import os
import time
import sys

os.environ['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'

from src.music_chronus.supervisor_v2_fixed import AudioSupervisor
from src.music_chronus.module_host import pack_command_v2, CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL

print("Starting supervisor...")
supervisor = AudioSupervisor()
if not supervisor.start():
    print("Failed to start")
    sys.exit(1)

print("Supervisor running, waiting 2 seconds...")
time.sleep(2)

print("\nSending commands:")
# Critical: Set parameters BEFORE gating
commands = [
    ("sine gain 0.5", pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'gain', 0.5)),
    ("filter cutoff high", pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'filter', 'cutoff', 10000.0)),
    ("sine freq 440", pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'freq', 440.0)),
    ("GATE ON", pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, 'adsr', 'gate', 1.0)),
]

for desc, cmd in commands:
    print(f"  {desc} - {len(cmd)} bytes")
    # Show first few bytes
    print(f"    First 8 bytes: {cmd[:8].hex()}")
    supervisor.broadcast_command_raw(cmd)
    time.sleep(0.1)

print("\nLISTENING FOR SOUND (5 seconds)...")
print("You should hear a 440Hz tone if it works!")
time.sleep(5)

print("\nGating OFF...")
supervisor.broadcast_command_raw(pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, 'adsr', 'gate', 0.0))
time.sleep(1)

supervisor.stop()
print("Done")