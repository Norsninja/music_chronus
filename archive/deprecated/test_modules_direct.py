#!/usr/bin/env python3
"""
Direct test of the module chain to isolate the issue
Tests SimpleSine -> ADSR -> BiquadFilter without multiprocessing
"""

import numpy as np
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.music_chronus.module_host import ModuleHost, pack_command_v2, CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL
from src.music_chronus.modules.simple_sine import SimpleSine
from src.music_chronus.modules.adsr import ADSR
from src.music_chronus.modules.biquad_filter import BiquadFilter

# Constants
SAMPLE_RATE = 44100
BUFFER_SIZE = 256

def test_module_chain():
    """Test the module chain directly"""
    print("Testing module chain directly...")
    
    # Create host
    host = ModuleHost(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    
    # Create modules
    sine = SimpleSine(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    adsr = ADSR(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    filt = BiquadFilter(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    
    # Register modules
    host.add_module('sine', sine)
    host.add_module('adsr', adsr)
    host.add_module('filter', filt)
    
    print("Modules registered")
    
    # Set parameters
    commands = [
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'freq', 440.0),
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'adsr', 'gain', 0.5),
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'filter', 'cutoff', 10000.0),
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'filter', 'q', 0.707),
    ]
    
    for cmd in commands:
        host.queue_command(cmd)
    
    print("Commands queued")
    
    # Process commands
    host.process_commands()
    
    # Test 1: Without gate (should be silent)
    print("\nTest 1: Gate OFF")
    for i in range(3):
        audio = host.process_chain()
        rms = np.sqrt(np.mean(audio**2))
        print(f"  Buffer {i}: RMS = {rms:.6f}")
    
    # Test 2: With gate ON
    print("\nTest 2: Gate ON")
    gate_cmd = pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, 'adsr', '', True)
    host.queue_command(gate_cmd)
    host.process_commands()
    
    for i in range(3):
        audio = host.process_chain()
        rms = np.sqrt(np.mean(audio**2))
        print(f"  Buffer {i}: RMS = {rms:.6f}")
    
    # Test 3: Check each module individually
    print("\nTest 3: Individual module outputs")
    
    # Test sine directly
    sine.set_parameter('freq', 440.0)
    sine_out = np.zeros(BUFFER_SIZE, dtype=np.float32)
    sine.process_buffer(sine_out, sine_out)
    print(f"  Sine only: RMS = {np.sqrt(np.mean(sine_out**2)):.6f}")
    
    # Test ADSR with gate on
    adsr.set_parameter('gain', 0.5)
    adsr.set_parameter('gate', True)
    adsr_in = np.ones(BUFFER_SIZE, dtype=np.float32) * 0.5
    adsr_out = np.zeros(BUFFER_SIZE, dtype=np.float32)
    adsr.process_buffer(adsr_in, adsr_out)
    print(f"  ADSR (gate on): RMS = {np.sqrt(np.mean(adsr_out**2)):.6f}")
    
    # Test filter
    filt.set_parameter('cutoff', 10000.0)
    filt.set_parameter('q', 0.707)
    filt_in = np.ones(BUFFER_SIZE, dtype=np.float32) * 0.5
    filt_out = np.zeros(BUFFER_SIZE, dtype=np.float32)
    filt.process_buffer(filt_in, filt_out)
    print(f"  Filter: RMS = {np.sqrt(np.mean(filt_out**2)):.6f}")
    
    # Test 4: Manual chain processing
    print("\nTest 4: Manual chain (gate on)")
    
    # Reset and manually process
    sine.set_parameter('freq', 440.0)
    adsr.set_parameter('gate', True)
    adsr.set_parameter('gain', 0.5)
    
    buf1 = np.zeros(BUFFER_SIZE, dtype=np.float32)
    buf2 = np.zeros(BUFFER_SIZE, dtype=np.float32)
    
    # Sine -> buf1
    sine.process_buffer(buf1, buf1)
    print(f"  After sine: RMS = {np.sqrt(np.mean(buf1**2)):.6f}")
    
    # ADSR: buf1 -> buf2
    adsr.process_buffer(buf1, buf2)
    print(f"  After ADSR: RMS = {np.sqrt(np.mean(buf2**2)):.6f}")
    
    # Filter: buf2 -> buf1
    filt.process_buffer(buf2, buf1)
    print(f"  After filter: RMS = {np.sqrt(np.mean(buf1**2)):.6f}")

if __name__ == '__main__':
    test_module_chain()