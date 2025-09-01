#!/usr/bin/env python3
"""Debug command packing and unpacking."""

from src.music_chronus.module_host import pack_command_v2, unpack_command_v2
from src.music_chronus.module_host import CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL

print("Testing command packing/unpacking:\n")

# Test the commands we're sending
commands = [
    ("sine gain", CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'gain', 0.5),
    ("filter cutoff", CMD_OP_SET, CMD_TYPE_FLOAT, 'filter', 'cutoff', 10000.0),
    ("sine freq", CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'freq', 440.0),
    ("GATE ON", CMD_OP_GATE, CMD_TYPE_BOOL, 'adsr', 'gate', 1.0),
]

for desc, op, dtype, module_id, param, value in commands:
    print(f"{desc}:")
    print(f"  Input: op={op}, dtype={dtype}, module={module_id}, param={param}, value={value}")
    
    # Pack
    packed = pack_command_v2(op, dtype, module_id, param, value)
    print(f"  Packed: {len(packed)} bytes")
    
    # Unpack
    try:
        unpacked = unpack_command_v2(packed)
        op2, dtype2, mod2, param2, val2 = unpacked
        print(f"  Unpacked: op={op2}, dtype={dtype2}, module={mod2}, param={param2}, value={val2}")
        if mod2 == module_id and param2 == param and val2 == value:
            print(f"  ✓ Correct!")
        else:
            print(f"  ✗ MISMATCH!")
    except Exception as e:
        print(f"  ✗ Unpack failed: {e}")
    print()

# Test what happens with corrupted data
print("\nTesting with zeros:")
zeros = b'\x00' * 64
try:
    unpacked = unpack_command_v2(zeros)
    op, dtype, mod, param, val = unpacked
    print(f"  Unpacked zeros: module='{mod}', param='{param}', value={val}")
except Exception as e:
    print(f"  Failed to unpack zeros: {e}")