#!/usr/bin/env python3
"""
More obvious wobble test - slower rate, bigger range
"""

import time
from pyo import *

def test_obvious_wobble():
    """Test with very obvious wobble parameters"""
    
    print("[TEST] Starting OBVIOUS wobble test...")
    print("[TEST] 0.1Hz LFO (10-second cycle) with extreme range")
    print("[TEST] Press Ctrl+C to stop")
    
    # Initialize audio server
    s = Server(duplex=0, audio="portaudio")
    s.boot()
    s.start()
    
    # Richer source for more obvious filtering - use multiple harmonics
    src1 = Sine(110, mul=0.1)
    src2 = Sine(220, mul=0.05) 
    src3 = Sine(330, mul=0.03)
    src = src1 + src2 + src3  # Rich harmonic content to filter
    
    # Much slower LFO with extreme range
    lfo = Sine(freq=0.1, mul=1)  # 0.1Hz = 10 second cycle
    unipolar = (lfo + 1) * 0.5
    mod_hz = Scale(unipolar, inmin=0, inmax=1, outmin=-1500, outmax=1500)  # ±1500Hz
    
    # Filter with extreme modulation
    base = Sig(800)  # Lower base for more dramatic effect
    freq_total = Clip(base + mod_hz, 100, 3000)  # 100-3000Hz sweep
    filt = Biquad(src, freq=freq_total, q=4, type=0)  # Higher Q for more obvious effect
    
    print(f"[TEST] Filter will sweep from ~100Hz to ~3000Hz over 10 seconds")
    print(f"[TEST] Should sound like: dull → bright → dull → bright...")
    
    # Output
    filt.out()
    
    try:
        # Run for 15 seconds (1.5 cycles)
        print("[TEST] Running for 15 seconds...")
        time.sleep(15)
        
        print("[TEST] Test complete")
        s.stop()
        s.shutdown()
        
    except KeyboardInterrupt:
        print("\n[TEST] Interrupted by user")
        s.stop()
        s.shutdown()

if __name__ == "__main__":
    test_obvious_wobble()