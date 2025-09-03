#!/usr/bin/env python
"""Test script for CP3 router audio generation"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.music_chronus.module_host import ModuleHost
from src.music_chronus.patch_router import PatchRouter
from src.music_chronus.modules.simple_sine import SimpleSine
import numpy as np

SAMPLE_RATE = 48000
BUFFER_SIZE = 256

# Create a module host with router
module_host = ModuleHost(SAMPLE_RATE, BUFFER_SIZE, use_router=True)
router = PatchRouter(BUFFER_SIZE)
module_host.enable_router(router)

# Create a simple sine oscillator
osc1 = SimpleSine(SAMPLE_RATE, BUFFER_SIZE)

# Add module using the new helper method
module_host.router_add_module('osc1', osc1)

# Set parameters
osc1.params['freq'] = 440.0
osc1.params['gain'] = 0.5

# Mark module as active
osc1.active = True

print(f"Module created: osc1")
print(f"Parameters: freq={osc1.params['freq']}, gain={osc1.params['gain']}")
print(f"Active: {osc1.active}")

# Process some buffers
for i in range(10):
    # Process the chain
    output = module_host.process_chain()
    
    # Calculate RMS
    rms = np.sqrt(np.mean(output**2))
    
    print(f"Buffer {i}: RMS = {rms:.6f}")
    
    # Check the first few samples
    if i == 0:
        print(f"  First 10 samples: {output[:10]}")

print("\nTest complete!")