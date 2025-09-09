#!/usr/bin/env python3
"""
Direct schema checker for Music Chronus
Checks if noise types are properly registered
"""

import sys
sys.path.append('.')

from pyo_modules.voice import Voice
from pyo_modules.limiter import LimiterModule
import json

# Create a voice instance to get its schema
voice = Voice(voice_id="test_voice")
voice_schema = voice.get_schema()

# Check osc/type parameter
osc_type = voice_schema['params'].get('osc/type', {})
print("="*60)
print("VOICE OSC/TYPE SCHEMA:")
print(f"  Range: {osc_type.get('min', 'N/A')} to {osc_type.get('max', 'N/A')}")
print(f"  Notes: {osc_type.get('notes', 'N/A')}")
print("="*60)

# Check if noise types are included
if osc_type.get('max') == 5:
    print("✓ Noise generators properly registered (0-5 range)")
    print("  0 = sine")
    print("  1 = saw") 
    print("  2 = square")
    print("  3 = white noise")
    print("  4 = pink noise")
    print("  5 = brown noise")
else:
    print("✗ Noise generators NOT registered!")
    print(f"  Current max: {osc_type.get('max')}")

# Create a test limiter to check its schema
test_signal = voice.output  # Just for testing
limiter = LimiterModule(test_signal)
limiter_schema = limiter.get_schema()

print("\n" + "="*60)
print("LIMITER MODULE SCHEMA:")
print(json.dumps(limiter_schema, indent=2))
print("="*60)