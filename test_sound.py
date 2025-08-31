#!/usr/bin/env python3
"""
Simple sound test - Can I make and play a beep?
"""

import numpy as np
from scipy.io import wavfile
import subprocess
import sys

def make_beep(freq=440, duration=0.5, sample_rate=44100):
    """Generate a simple beep"""
    t = np.linspace(0, duration, int(sample_rate * duration))
    wave = 0.3 * np.sin(2 * np.pi * freq * t)
    
    # Convert to 16-bit
    wave_int = (wave * 32767).astype(np.int16)
    
    # Save to temp file
    filename = '/tmp/test_beep.wav'
    wavfile.write(filename, sample_rate, wave_int)
    
    return filename

def play_sound(filename):
    """Play through PulseAudio"""
    try:
        subprocess.run(['paplay', filename], 
                      env={'PULSE_SERVER': 'tcp:172.21.240.1:4713'},
                      check=True)
        return True
    except subprocess.CalledProcessError:
        return False

if __name__ == "__main__":
    # Allow command line control
    if len(sys.argv) > 1:
        freq = float(sys.argv[1])
    else:
        freq = 440
    
    print(f"Generating {freq}Hz beep...")
    wav_file = make_beep(freq=freq, duration=0.5)
    
    print("Playing...")
    if play_sound(wav_file):
        print("Success!")
    else:
        print("Failed to play")