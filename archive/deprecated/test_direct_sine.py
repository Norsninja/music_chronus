#!/usr/bin/env python3
"""
Direct sine wave test - bypasses all ring buffers to isolate the issue
"""

import numpy as np
import sounddevice as sd
import time
import sys

# Constants
SAMPLE_RATE = 44100
BUFFER_SIZE = 256
FREQUENCY = 440.0
GAIN = 0.5

class DirectSineGenerator:
    def __init__(self):
        self.phase = 0.0
        self.phase_step = 2 * np.pi * FREQUENCY / SAMPLE_RATE
        self.callback_count = 0
        self.last_log_time = time.time()
        
    def audio_callback(self, outdata, frames, time_info, status):
        """Direct sine generation in callback - no ring buffer"""
        if status:
            print(f"Status: {status}")
        
        # Generate sine directly
        t = np.arange(frames) * self.phase_step + self.phase
        audio = (GAIN * np.sin(t)).astype(np.float32)
        
        # Update phase for next callback
        self.phase = (self.phase + frames * self.phase_step) % (2 * np.pi)
        
        # Copy to output
        outdata[:, 0] = audio
        
        # Log periodically
        self.callback_count += 1
        current_time = time.time()
        if current_time - self.last_log_time >= 1.0:
            rms = np.sqrt(np.mean(audio**2))
            print(f"Callbacks: {self.callback_count}, RMS: {rms:.6f}")
            self.last_log_time = current_time

def main():
    print("Direct Sine Test - No Ring Buffers")
    print("This should produce a clean 440Hz tone")
    print("-" * 40)
    
    generator = DirectSineGenerator()
    
    # Check actual sample rate
    device_info = sd.query_devices(sd.default.device, 'output')
    print(f"Output device: {device_info['name']}")
    print(f"Default sample rate: {device_info['default_samplerate']}")
    
    # Start stream
    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        channels=1,
        dtype='float32',
        callback=generator.audio_callback
    )
    
    stream.start()
    print(f"\nPlaying {FREQUENCY}Hz sine wave at {SAMPLE_RATE}Hz")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stream.stop()
        stream.close()

if __name__ == '__main__':
    main()