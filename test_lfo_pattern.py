#!/usr/bin/env python3
"""
Isolated LFO test case from Senior Dev
Tests the exact pattern we need to implement in Voice.apply_filter_lfo()
"""

import time
from pyo import *

def test_lfo_filter_pattern():
    """Test isolated LFO → filter modulation pattern"""
    
    print("[TEST] Starting isolated LFO filter test...")
    print("[TEST] You should hear a wobbling filter sweep")
    print("[TEST] Press Ctrl+C to stop")
    
    # Initialize audio server
    s = Server(duplex=0, audio="portaudio")
    s.boot()
    s.start()
    
    # Source oscillator
    src = Sine(110, mul=0.2)
    
    # LFO chain - exactly as Senior Dev specified
    lfo = Sine(freq=0.25, mul=1)  # 0.25Hz LFO
    unipolar = (lfo + 1) * 0.5    # Convert bipolar to unipolar (0-1)
    mod_hz = Scale(unipolar, inmin=0, inmax=1, outmin=-800, outmax=800)  # ±800Hz
    
    # Filter with LFO modulation
    base = Sig(1000)  # 1kHz base frequency
    freq_total = Clip(base + mod_hz, 50, 8000)  # Sum base + LFO, clamp to safe range
    filt = Biquad(src, freq=freq_total, q=2, type=0)  # Lowpass filter
    
    # Output
    filt.out()
    
    try:
        # Run for 10 seconds
        print("[TEST] Running for 10 seconds...")
        time.sleep(10)
        
        print("[TEST] Test complete - stopping audio")
        s.stop()
        s.shutdown()
        
        print("\n[TEST] Analysis:")
        print("- Did you hear wobbling filter sweep? (Should be obvious)")
        print("- Base frequency: 1000Hz")
        print("- LFO modulation: ±800Hz (200-1800Hz sweep)")
        print("- LFO rate: 0.25Hz (4-second cycle)")
        print("\nThis is EXACTLY what Voice.apply_filter_lfo() needs to do.")
        
    except KeyboardInterrupt:
        print("\n[TEST] Interrupted by user - stopping audio")
        s.stop()
        s.shutdown()

if __name__ == "__main__":
    test_lfo_filter_pattern()