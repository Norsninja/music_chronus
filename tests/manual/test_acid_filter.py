#!/usr/bin/env python3
"""
Test the TB-303 style Acid Filter
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import numpy as np
import sounddevice as sd
from music_chronus.modules.simple_sine import SimpleSine
from music_chronus.modules.acid_filter import AcidFilter
from music_chronus.modules.distortion import Distortion
from music_chronus.modules.adsr import ADSR

# Configuration
SAMPLE_RATE = 48000
BUFFER_SIZE = 256

class AcidBassTest:
    """Test the acid filter with classic 303 patterns"""
    
    def __init__(self, sample_rate=48000, buffer_size=256):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        
        # Create modules for acid bass chain
        self.osc = SimpleSine(sample_rate, buffer_size)
        self.filter = AcidFilter(sample_rate, buffer_size)
        self.dist = Distortion(sample_rate, buffer_size)
        
        # Configure for acid bass
        self.osc.set_param('gain', 0.8)
        
        # Start with classic 303 filter settings
        self.filter.set_param('cutoff', 200.0)
        self.filter.set_param('resonance', 0.7)
        self.filter.set_param('env_amount', 0.8)
        self.filter.set_param('decay', 150.0)
        self.filter.set_param('drive', 2.0)
        
        # Mild distortion for extra grit
        self.dist.set_param('mode', 0)  # Soft clip
        self.dist.set_param('drive', 3.0)
        self.dist.set_param('mix', 0.5)
        self.dist.set_param('tone', 0.6)
        
        # State
        self.total_buffers = 0
    
    def audio_callback(self, outdata, frames, time_info, status):
        """Process audio through acid chain"""
        
        if status:
            print(f"Callback status: {status}")
        
        self.total_buffers += 1
        
        # Allocate buffers
        buffer1 = np.zeros(frames, dtype=np.float32)
        buffer2 = np.zeros(frames, dtype=np.float32)
        
        # Process: Osc -> Acid Filter -> Distortion
        self.osc.process_buffer(buffer1, buffer2)
        np.copyto(buffer1, buffer2)
        
        self.filter.process_buffer(buffer1, buffer2)
        np.copyto(buffer1, buffer2)
        
        self.dist.process_buffer(buffer1, buffer2)
        
        # Output
        outdata[:, 0] = buffer2


def test_acid_sweeps():
    """Test classic acid filter sweeps"""
    
    print("=" * 60)
    print("ACID FILTER TEST - Classic 303 Sweeps")
    print("=" * 60)
    
    # Find WASAPI device
    wasapi_device = None
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
            if device['max_output_channels'] > 0:
                wasapi_device = i
                break
    
    test = AcidBassTest(SAMPLE_RATE, BUFFER_SIZE)
    
    with sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        device=wasapi_device,
        channels=1,
        callback=test.audio_callback,
        latency='low'
    ) as stream:
        
        # Test 1: Resonance sweep
        print("\n1. Resonance Sweep (filter self-oscillation)")
        print("-" * 40)
        test.osc.set_param('freq', 110.0)  # A2 bass
        
        for res in np.linspace(0.0, 0.9, 20):
            print(f"  Resonance: {res:.2f}", end='\r')
            test.filter.set_param('resonance', res)
            test.filter.set_gate(True)
            time.sleep(0.1)
        print("\n  Self-oscillation reached!")
        time.sleep(0.5)
        
        # Test 2: Classic acid pattern with filter envelope
        print("\n2. Classic Acid Pattern (with envelope)")
        print("-" * 40)
        
        # Reset to moderate resonance
        test.filter.set_param('resonance', 0.75)
        test.filter.set_param('env_amount', 1.0)
        
        # Classic acid pattern
        notes = [55, 0, 55, 55, 0, 82.5, 0, 55,  # A1 pattern
                 55, 0, 110, 0, 55, 0, 82.5, 0]
        pattern = "X.xxX.x.X.X.x.x."
        
        print(f"  Pattern: {pattern}")
        
        for _ in range(4):  # Play 4 times
            for note, trigger in zip(notes, pattern):
                if trigger == 'X':  # Accent
                    if note > 0:
                        test.osc.set_param('freq', note)
                        test.filter.set_accent(True)
                        test.filter.set_gate(True)
                elif trigger == 'x':  # Normal
                    if note > 0:
                        test.osc.set_param('freq', note)
                        test.filter.set_accent(False)
                        test.filter.set_gate(True)
                
                time.sleep(0.125)  # 16th notes
        
        # Test 3: Cutoff modulation
        print("\n3. Manual Cutoff Sweep (filter opening)")
        print("-" * 40)
        
        test.osc.set_param('freq', 55.0)  # Low A
        test.filter.set_param('resonance', 0.8)
        test.filter.set_param('env_amount', 0.0)  # No envelope
        
        # Sweep cutoff from dark to bright
        print("  Dark -> Bright")
        for cutoff in np.logspace(np.log10(100), np.log10(5000), 30):
            test.filter.set_param('cutoff', cutoff)
            test.filter.set_gate(True)
            time.sleep(0.05)
        
        # Test 4: Accent demonstration
        print("\n4. Accent Demonstration")
        print("-" * 40)
        
        test.filter.set_param('cutoff', 300.0)
        test.filter.set_param('resonance', 0.6)
        test.filter.set_param('env_amount', 0.8)
        
        for i in range(8):
            if i % 2 == 0:
                print("  Normal", end='\r')
                test.filter.set_accent(False)
            else:
                print("  ACCENT", end='\r')
                test.filter.set_accent(True)
            
            test.osc.set_param('freq', 110.0)
            test.filter.set_gate(True)
            time.sleep(0.25)
        
        print("\n\nTest complete!")


def acid_bassline_demo():
    """Play a full acid bassline with filter automation"""
    
    print("=" * 60)
    print("ACID BASSLINE DEMO")
    print("=" * 60)
    print("Full 303-style acid line with filter sweeps")
    
    # Find WASAPI device
    wasapi_device = None
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
            if device['max_output_channels'] > 0:
                wasapi_device = i
                break
    
    test = AcidBassTest(SAMPLE_RATE, BUFFER_SIZE)
    
    # Configure for proper acid
    test.filter.set_param('cutoff', 150.0)
    test.filter.set_param('resonance', 0.82)
    test.filter.set_param('env_amount', 0.9)
    test.filter.set_param('decay', 180.0)
    test.filter.set_param('drive', 2.5)
    
    # More distortion for acid
    test.dist.set_param('drive', 5.0)
    test.dist.set_param('mix', 0.7)
    
    with sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        device=wasapi_device,
        channels=1,
        callback=test.audio_callback,
        latency='low'
    ) as stream:
        
        # Acid bassline (A minor)
        bassline = [
            (55, 'X'), (0, '.'), (55, 'x'), (55, 'x'),
            (0, '.'), (82.5, 'x'), (0, '.'), (55, 'x'),
            (110, 'X'), (0, '.'), (55, 'x'), (0, '.'),
            (65.4, 'x'), (0, '.'), (82.5, 'x'), (55, 'X')
        ]
        
        print("\nPlaying acid bassline...")
        print("Listen for the filter sweeps and resonance!")
        
        # Play for several bars with variations
        for bar in range(8):
            # Modulate parameters over time
            if bar == 2:
                print("  Increasing resonance...")
                test.filter.set_param('resonance', 0.88)
            elif bar == 4:
                print("  Opening filter...")
                test.filter.set_param('cutoff', 400.0)
            elif bar == 6:
                print("  Maximum acid!")
                test.filter.set_param('resonance', 0.92)
                test.filter.set_param('env_amount', 1.0)
                test.dist.set_param('drive', 8.0)
            
            # Play the bassline
            for note, trigger in bassline:
                if trigger == 'X':  # Accent
                    if note > 0:
                        test.osc.set_param('freq', note)
                        test.filter.set_accent(True)
                        test.filter.set_gate(True)
                elif trigger == 'x':  # Normal
                    if note > 0:
                        test.osc.set_param('freq', note)
                        test.filter.set_accent(False)
                        test.filter.set_gate(True)
                
                time.sleep(0.125)  # 16th notes at 120 BPM
        
        print("\nAcid bassline complete!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        acid_bassline_demo()
    else:
        test_acid_sweeps()