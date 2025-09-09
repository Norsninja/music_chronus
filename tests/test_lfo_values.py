#!/usr/bin/env python3
"""
Test if LFO is actually generating changing values
"""

import time
from pyo import *

# Start server
s = Server(duplex=0, audio="portaudio")
s.boot()
s.start()

# Create the exact same LFO setup as in engine
lfo1_rate = Sig(0.5)  # 0.5Hz
lfo1_depth = Sig(1.0)  # Full depth

# Same as engine
lfo1_osc = Sine(freq=lfo1_rate, mul=1)
lfo1_uni = (lfo1_osc + 1) * 0.5
lfo1_with_depth = lfo1_uni * lfo1_depth
lfo1_scaled = Scale(lfo1_with_depth, inmin=0, inmax=1, outmin=-800, outmax=800)

# Print values to see if they're changing
print("Monitoring LFO output for 5 seconds...")
print("Should see values oscillating between -800 and +800")

def print_value():
    val = lfo1_scaled.get()
    print(f"LFO output: {val:.1f} Hz offset")

# Monitor for 5 seconds
pat = Pattern(print_value, time=0.1).play()

time.sleep(5)

pat.stop()
s.stop()
s.shutdown()

print("\nIf values stayed at 0.0, the LFO isn't running.")
print("If values changed, the LFO works but isn't connected properly.")