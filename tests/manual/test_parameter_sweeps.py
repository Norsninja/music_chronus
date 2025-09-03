#!/usr/bin/env python3
"""
Test live parameter sweeps for zippering artifacts
"""

import time
import numpy as np
from pythonosc import udp_client

def test_parameter_sweeps():
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("=" * 60)
    print("PARAMETER SWEEP TEST - Checking for Zippering")
    print("=" * 60)
    
    # Build basic patch
    print("\n[1] Building test patch...")
    client.send_message("/patch/create", ["osc1", "simple_sine"])
    client.send_message("/patch/create", ["filt1", "biquad_filter"])
    client.send_message("/patch/connect", ["osc1", "filt1"])
    client.send_message("/patch/commit", [])
    time.sleep(1)
    
    # Set initial parameters
    client.send_message("/mod/osc1/freq", [440.0])
    client.send_message("/mod/osc1/gain", [0.3])
    client.send_message("/mod/filt1/cutoff", [8000.0])
    client.send_message("/mod/filt1/q", [1.0])
    time.sleep(0.5)
    
    print("\n[2] Testing filter cutoff sweep (slow)")
    print("    Listen for: smooth frequency change without clicks/zips")
    # Slow sweep - 3 seconds from 8kHz to 500Hz
    cutoff_values = np.linspace(8000, 500, 100)
    for cutoff in cutoff_values:
        client.send_message("/mod/filt1/cutoff", [float(cutoff)])
        time.sleep(0.03)  # 30ms per step
    
    time.sleep(1)
    
    print("\n[3] Testing filter cutoff sweep (fast)")
    print("    Listen for: potential zippering due to fast changes")
    # Fast sweep - 0.5 seconds
    cutoff_values = np.linspace(500, 8000, 50)
    for cutoff in cutoff_values:
        client.send_message("/mod/filt1/cutoff", [float(cutoff)])
        time.sleep(0.01)  # 10ms per step
    
    time.sleep(1)
    
    print("\n[4] Testing filter Q sweep")
    print("    Listen for: resonance changes without instability")
    # Q sweep from 0.7 to 10 (high resonance)
    q_values = np.linspace(0.7, 10.0, 60)
    for q in q_values:
        client.send_message("/mod/filt1/q", [float(q)])
        time.sleep(0.025)  # 25ms per step
    
    # Return to safe Q
    client.send_message("/mod/filt1/q", [1.0])
    time.sleep(1)
    
    print("\n[5] Testing gain sweep")
    print("    Listen for: smooth volume changes")
    # Gain sweep
    gain_values = np.concatenate([
        np.linspace(0.3, 0.01, 30),  # Fade out
        np.linspace(0.01, 0.3, 30)    # Fade in
    ])
    for gain in gain_values:
        client.send_message("/mod/osc1/gain", [float(gain)])
        time.sleep(0.02)  # 20ms per step
    
    time.sleep(1)
    
    print("\n[6] Testing frequency sweep")
    print("    Listen for: smooth pitch glide without artifacts")
    # Frequency sweep (one octave)
    freq_values = np.linspace(440, 880, 50)
    for freq in freq_values:
        client.send_message("/mod/osc1/freq", [float(freq)])
        time.sleep(0.02)
    
    # Glide back down
    freq_values = np.linspace(880, 440, 50)
    for freq in freq_values:
        client.send_message("/mod/osc1/freq", [float(freq)])
        time.sleep(0.02)
    
    time.sleep(1)
    
    print("\n[7] Testing simultaneous sweeps")
    print("    Listen for: multiple parameters changing together")
    # Simultaneous cutoff and gain
    cutoff_values = np.linspace(8000, 1000, 40)
    gain_values = np.linspace(0.3, 0.1, 40)
    for cutoff, gain in zip(cutoff_values, gain_values):
        client.send_message("/mod/filt1/cutoff", [float(cutoff)])
        client.send_message("/mod/osc1/gain", [float(gain)])
        time.sleep(0.025)
    
    print("\n" + "=" * 60)
    print("RESULTS:")
    print("- If sweeps sound smooth: immediate=True working well")
    print("- If clicking/zipping heard: need parameter smoothing")
    print("- Note which parameters need smoothing for Track B")
    print("=" * 60)

if __name__ == "__main__":
    test_parameter_sweeps()