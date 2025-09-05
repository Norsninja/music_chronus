#!/usr/bin/env python3
"""
Test the Distortion module - all 4 modes
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import numpy as np
import sounddevice as sd
from music_chronus.modules.simple_sine import SimpleSine
from music_chronus.modules.distortion import Distortion
from music_chronus.modules.adsr import ADSR

# Configuration
SAMPLE_RATE = 48000
BUFFER_SIZE = 256

class DistortionTest:
    """Test harness for distortion module"""
    
    def __init__(self, sample_rate=48000, buffer_size=256):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        
        # Create modules
        self.osc = SimpleSine(sample_rate, buffer_size)
        self.env = ADSR(sample_rate, buffer_size)
        self.dist = Distortion(sample_rate, buffer_size)
        
        # Configure oscillator (bass frequency)
        self.osc.set_param('freq', 110.0)  # A2 bass note
        self.osc.set_param('gain', 0.7)
        
        # Configure envelope
        self.env.set_param('attack', 10.0)
        self.env.set_param('decay', 100.0)
        self.env.set_param('sustain', 0.8)
        self.env.set_param('release', 200.0)
        
        # Start with mild distortion
        self.dist.set_param('drive', 2.0)
        self.dist.set_param('mix', 1.0)
        self.dist.set_param('mode', 0)  # Soft clip
        self.dist.set_param('tone', 0.5)
        
        # Tracking
        self.total_buffers = 0
        self.current_mode = 0
        self.mode_names = ["Soft Clip", "Hard Clip", "Foldback", "Bitcrush"]
    
    def audio_callback(self, outdata, frames, time_info, status):
        """Process audio through distortion chain"""
        
        if status:
            print(f"Callback status: {status}")
        
        self.total_buffers += 1
        
        # Allocate buffers
        buffer1 = np.zeros(frames, dtype=np.float32)
        buffer2 = np.zeros(frames, dtype=np.float32)
        
        # Process: Osc -> Envelope -> Distortion
        self.osc.process_buffer(buffer1, buffer2)
        np.copyto(buffer1, buffer2)
        
        self.env.process_buffer(buffer1, buffer2)
        np.copyto(buffer1, buffer2)
        
        self.dist.process_buffer(buffer1, buffer2)
        
        # Output
        outdata[:, 0] = buffer2
    
    def trigger_note(self):
        """Trigger a bass note"""
        self.env.set_gate(True)
        time.sleep(0.2)
        self.env.set_gate(False)
    
    def test_all_modes(self):
        """Test each distortion mode"""
        for mode in range(4):
            print(f"\nMode {mode}: {self.mode_names[mode]}")
            print("-" * 40)
            
            # Set mode
            self.dist.set_param('mode', mode)
            self.current_mode = mode
            
            # Test different drive levels
            drive_levels = [1.0, 5.0, 15.0, 30.0]
            drive_names = ["Clean", "Warm", "Hot", "Destroyed"]
            
            for drive, name in zip(drive_levels, drive_names):
                print(f"  Drive {drive:4.1f} ({name:10s})", end='')
                self.dist.set_param('drive', drive)
                
                # Play note
                self.trigger_note()
                time.sleep(0.3)
                print(" [OK]")
            
            # Special parameters for certain modes
            if mode == 3:  # Bitcrush
                print("  Testing sample rate reduction...")
                self.trigger_note()
                time.sleep(0.5)
    
    def test_tone_sweep(self):
        """Test tone control sweep"""
        print("\nTone Control Sweep")
        print("-" * 40)
        
        # Set moderate distortion
        self.dist.set_param('mode', 1)  # Hard clip
        self.dist.set_param('drive', 10.0)
        
        # Trigger note
        self.env.set_gate(True)
        
        # Sweep tone from dark to bright
        print("  Dark -> Bright")
        for tone in np.linspace(0.0, 1.0, 20):
            self.dist.set_param('tone', tone)
            time.sleep(0.1)
        
        self.env.set_gate(False)
        time.sleep(0.5)
    
    def test_mix_blend(self):
        """Test dry/wet mix"""
        print("\nDry/Wet Mix Test")
        print("-" * 40)
        
        # Heavy distortion
        self.dist.set_param('mode', 2)  # Foldback
        self.dist.set_param('drive', 20.0)
        
        # Play with different mix levels
        mix_levels = [0.0, 0.25, 0.5, 0.75, 1.0]
        mix_names = ["Dry", "25%", "50%", "75%", "Wet"]
        
        for mix, name in zip(mix_levels, mix_names):
            print(f"  Mix: {name}")
            self.dist.set_param('mix', mix)
            self.trigger_note()
            time.sleep(0.5)


def run_distortion_test():
    """Run the full distortion test suite"""
    
    print("=" * 60)
    print("DISTORTION MODULE TEST")
    print("=" * 60)
    print("Testing 4 distortion modes with bass frequency (110Hz)")
    print("Each mode tested with different drive levels")
    
    # Find WASAPI device
    wasapi_device = None
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
            if device['max_output_channels'] > 0:
                if 'USB' in device['name'] or 'AB13X' in device['name']:
                    wasapi_device = i
                    print(f"Using: {device['name']}")
                    break
    
    if not wasapi_device:
        for i, device in enumerate(devices):
            if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
                if device['max_output_channels'] > 0:
                    wasapi_device = i
                    print(f"Using: {device['name']}")
                    break
    
    # Create test harness
    test = DistortionTest(SAMPLE_RATE, BUFFER_SIZE)
    
    # Create audio stream
    with sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        device=wasapi_device,
        channels=1,
        callback=test.audio_callback,
        latency='low'
    ) as stream:
        
        # Run tests
        test.test_all_modes()
        test.test_tone_sweep()
        test.test_mix_blend()
        
        print("\n" + "=" * 60)
        print(f"Test complete! Total buffers: {test.total_buffers}")
        print("=" * 60)


def quick_dirty_bass_demo():
    """Quick demo of dirty bass sound"""
    
    print("=" * 60)
    print("DIRTY BASS DEMO")
    print("=" * 60)
    print("Playing a simple bass pattern with heavy distortion")
    
    # Find WASAPI device
    wasapi_device = None
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
            if device['max_output_channels'] > 0:
                wasapi_device = i
                break
    
    test = DistortionTest(SAMPLE_RATE, BUFFER_SIZE)
    
    # Configure for dirty bass
    test.osc.set_param('freq', 55.0)  # Low A
    test.dist.set_param('mode', 2)    # Foldback
    test.dist.set_param('drive', 25.0) # Heavy drive
    test.dist.set_param('tone', 0.3)   # Dark tone
    test.dist.set_param('mix', 0.8)    # 80% wet
    
    # Play pattern
    pattern = "X...x...X.x.x..."
    
    with sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        device=wasapi_device,
        channels=1,
        callback=test.audio_callback,
        latency='low'
    ) as stream:
        
        print("\nPattern: " + pattern)
        print("Playing...")
        
        for _ in range(2):  # Play pattern twice
            for step, char in enumerate(pattern):
                if char == 'X':
                    test.osc.set_param('freq', 55.0)  # Low A
                    test.env.set_gate(True)
                elif char == 'x':
                    test.osc.set_param('freq', 82.5)  # Low E
                    test.env.set_gate(True)
                
                time.sleep(0.125)  # 16th notes at 120 BPM
                
                if char in 'Xx':
                    test.env.set_gate(False)
        
        print("\nDone!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "dirty":
        quick_dirty_bass_demo()
    else:
        run_distortion_test()