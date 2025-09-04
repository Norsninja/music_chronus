#!/usr/bin/env python3
"""
Test Music Chronus DSP modules on Windows
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import numpy as np
import sounddevice as sd
from music_chronus.modules.simple_sine import SimpleSine
from music_chronus.modules.adsr import ADSR
from music_chronus.modules.biquad_filter import BiquadFilter

# Configuration
SAMPLE_RATE = 48000  # WASAPI standard
BUFFER_SIZE = 256
CHANNELS = 1

def test_module_chain():
    """Test a chain of DSP modules"""
    
    # Create modules
    print("Creating DSP modules...")
    oscillator = SimpleSine(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    envelope = ADSR(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    filter_module = BiquadFilter(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    
    # Configure modules
    oscillator.set_param('freq', 440.0)
    oscillator.set_param('gain', 0.7)
    
    envelope.set_param('attack', 10.0)    # 10ms attack
    envelope.set_param('decay', 100.0)    # 100ms decay
    envelope.set_param('sustain', 0.7)    # 70% sustain level
    envelope.set_param('release', 500.0)  # 500ms release
    
    filter_module.set_param('cutoff', 2000.0)
    filter_module.set_param('q', 2.0)
    filter_module.set_param('mode', 0)  # Lowpass
    
    # Audio state
    phase = 0.0
    total_buffers = 0
    underruns = 0
    
    def audio_callback(outdata, frames, time_info, status):
        nonlocal total_buffers, underruns
        
        if status:
            underruns += 1
            print(f"Callback status: {status}")
        
        total_buffers += 1
        
        # Allocate buffers (modules use in_buf and out_buf pattern)
        in_buf = np.zeros(frames, dtype=np.float32)
        out_buf = np.zeros(frames, dtype=np.float32)
        
        # Process through module chain
        # SimpleSine is a generator, ignores in_buf
        oscillator.process_buffer(in_buf, out_buf)
        
        # ADSR and filter are processors, modify in place
        np.copyto(in_buf, out_buf)  # Copy oscillator output to envelope input
        envelope.process_buffer(in_buf, out_buf)
        
        np.copyto(in_buf, out_buf)  # Copy envelope output to filter input
        filter_module.process_buffer(in_buf, out_buf)
        
        # Output
        outdata[:, 0] = out_buf
    
    # Find WASAPI device
    wasapi_device = None
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
            if device['max_output_channels'] > 0 and ('USB' in device['name'] or 'AB13X' in device['name']):
                wasapi_device = i
                print(f"Using WASAPI device: {device['name']}")
                break
    
    if not wasapi_device:
        for i, device in enumerate(devices):
            if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
                if device['max_output_channels'] > 0:
                    wasapi_device = i
                    print(f"Using WASAPI device: {device['name']}")
                    break
    
    # Create stream
    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        device=wasapi_device,
        channels=CHANNELS,
        callback=audio_callback,
        latency='low'
    )
    
    print("\nTesting DSP module chain...")
    print("Playing notes with ADSR envelope and filter\n")
    
    with stream:
        # Play several notes
        for note_freq in [261.63, 329.63, 392.00, 523.25]:  # C, E, G, C
            print(f"Playing {note_freq:.1f}Hz...")
            
            # Set frequency
            oscillator.set_param('freq', note_freq)
            
            # Trigger envelope
            envelope.set_param('gate', 1.0)
            time.sleep(0.3)  # Hold note
            
            # Release
            envelope.set_param('gate', 0.0)
            time.sleep(0.7)  # Wait for release
    
    print(f"\nTest complete!")
    print(f"Total buffers: {total_buffers}")
    print(f"Underruns: {underruns}")
    print(f"Success rate: {(1 - underruns/total_buffers)*100:.1f}%")


def test_sine_sweep():
    """Test frequency sweep with SimpleSine module"""
    
    print("Testing SimpleSine frequency sweep...")
    
    # Create oscillator
    osc = SimpleSine(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    osc.set_param('gain', 0.3)
    
    # Audio callback
    def audio_callback(outdata, frames, time_info, status):
        in_buf = np.zeros(frames, dtype=np.float32)
        out_buf = np.zeros(frames, dtype=np.float32)
        osc.process_buffer(in_buf, out_buf)
        outdata[:, 0] = out_buf
    
    # Find WASAPI device
    wasapi_device = None
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
            if device['max_output_channels'] > 0:
                wasapi_device = i
                break
    
    # Create stream
    with sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        device=wasapi_device,
        channels=CHANNELS,
        callback=audio_callback,
        latency='low'
    ) as stream:
        print("Sweeping from 100Hz to 2000Hz...")
        
        # Frequency sweep
        start_freq = 100
        end_freq = 2000
        duration = 3.0
        steps = 100
        
        for i in range(steps):
            freq = start_freq + (end_freq - start_freq) * (i / steps)
            osc.set_param('freq', freq)
            time.sleep(duration / steps)
    
    print("Sweep complete!")


if __name__ == "__main__":
    print("=" * 60)
    print("Music Chronus Module Test - Windows")
    print("=" * 60)
    
    # Test 1: Simple sine sweep
    print("\nTest 1: Sine frequency sweep")
    print("-" * 40)
    test_sine_sweep()
    
    time.sleep(1)
    
    # Test 2: Full module chain
    print("\n" + "=" * 60)
    print("Test 2: Module chain (Oscillator -> ADSR -> Filter)")
    print("-" * 40)
    test_module_chain()
    
    print("\n" + "=" * 60)
    print("All tests complete!")