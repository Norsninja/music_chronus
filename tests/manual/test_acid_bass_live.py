#!/usr/bin/env python3
"""
Live Acid Bass Test - Hear the 303 filter in action!
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

# Configuration
SAMPLE_RATE = 48000
BUFFER_SIZE = 256

class LiveAcidBass:
    """Live acid bass demonstration"""
    
    def __init__(self):
        # Create modules
        self.osc = SimpleSine(SAMPLE_RATE, BUFFER_SIZE)
        self.filter = AcidFilter(SAMPLE_RATE, BUFFER_SIZE)
        self.dist = Distortion(SAMPLE_RATE, BUFFER_SIZE)
        
        # Configure for ACID!
        self.osc.set_param('gain', 0.9)
        
        # Classic 303 settings
        self.filter.set_param('cutoff', 200.0)     # Start low
        self.filter.set_param('resonance', 0.85)   # High resonance!
        self.filter.set_param('env_amount', 0.9)   # Strong envelope
        self.filter.set_param('decay', 200.0)      # Medium decay
        self.filter.set_param('drive', 3.0)        # Overdrive the filter
        
        # Add some dirt
        self.dist.set_param('mode', 2)  # Foldback distortion
        self.dist.set_param('drive', 4.0)
        self.dist.set_param('mix', 0.6)
        self.dist.set_param('tone', 0.4)  # Darker tone
        
        self.buffer_count = 0
    
    def audio_callback(self, outdata, frames, time_info, status):
        """Process audio"""
        if status:
            print(f"Audio status: {status}")
        
        self.buffer_count += 1
        
        # Create buffers
        buf1 = np.zeros(frames, dtype=np.float32)
        buf2 = np.zeros(frames, dtype=np.float32)
        
        # Process chain: Osc -> Filter -> Distortion
        self.osc.process_buffer(buf1, buf2)
        np.copyto(buf1, buf2)
        
        self.filter.process_buffer(buf1, buf2)
        np.copyto(buf1, buf2)
        
        self.dist.process_buffer(buf1, buf2)
        
        outdata[:, 0] = buf2


def run_live_acid_demo():
    """Run the live acid bass demonstration"""
    
    print("=" * 70)
    print("LIVE ACID BASS DEMONSTRATION - TB-303 Style Filter")
    print("=" * 70)
    print("\nThis will play a classic acid bassline with:")
    print("- Filter envelope sweeps (the signature 'wow' sound)")
    print("- High resonance (almost self-oscillating)")
    print("- Accent hits (louder with more envelope)")
    print("- Distortion for extra grit")
    print("\nStarting in 2 seconds...")
    time.sleep(2)
    
    # Find AB13X USB Audio device specifically
    wasapi_device = None
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
            if 'AB13X' in device['name'] and device['max_output_channels'] > 0:
                wasapi_device = i
                print(f"\nUsing audio device: {device['name']}")
                break
    
    # Fallback if AB13X not found
    if wasapi_device is None:
        for i, device in enumerate(devices):
            if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
                if device['max_output_channels'] > 0:
                    wasapi_device = i
                    print(f"\nFallback device: {device['name']}")
                    break
    
    # Create the acid bass
    acid = LiveAcidBass()
    
    # Create audio stream
    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        device=wasapi_device,
        channels=1,
        callback=acid.audio_callback,
        latency='low'
    )
    
    with stream:
        print("\n" + "=" * 70)
        print("PLAYING ACID BASSLINE")
        print("=" * 70)
        
        # Classic acid pattern (16 steps)
        # Using low frequencies for that deep bass
        notes = [
            (55, True),   # A1 with accent
            (0, False),   # rest
            (55, False),  # A1 no accent
            (55, False),  # A1 no accent
            (0, False),   # rest
            (82.5, False), # E2
            (0, False),   # rest
            (55, False),  # A1
            (110, True),  # A2 with accent
            (0, False),   # rest
            (55, False),  # A1
            (0, False),   # rest
            (65.4, False), # C2
            (0, False),   # rest
            (82.5, False), # E2
            (55, True),   # A1 with accent
        ]
        
        print("\nPart 1: Basic pattern with filter envelope")
        print("-" * 40)
        
        # Play basic pattern
        for _ in range(8):  # 8 repetitions
            for note, accent in notes:
                if note > 0:
                    acid.osc.set_param('freq', note)
                    acid.filter.set_accent(accent)
                    acid.filter.set_gate(True)
                time.sleep(0.125)  # 16th notes at 120 BPM
        
        print("\nPart 2: Increasing resonance (getting squelchy!)")
        print("-" * 40)
        
        # Increase resonance
        acid.filter.set_param('resonance', 0.92)
        
        for _ in range(8):
            for note, accent in notes:
                if note > 0:
                    acid.osc.set_param('freq', note)
                    acid.filter.set_accent(accent)
                    acid.filter.set_gate(True)
                time.sleep(0.125)
        
        print("\nPart 3: Opening the filter (brighter)")
        print("-" * 40)
        
        # Open up the filter
        acid.filter.set_param('cutoff', 800.0)
        acid.filter.set_param('env_amount', 0.6)
        
        for _ in range(8):
            for note, accent in notes:
                if note > 0:
                    acid.osc.set_param('freq', note)
                    acid.filter.set_accent(accent)
                    acid.filter.set_gate(True)
                time.sleep(0.125)
        
        print("\nPart 4: MAXIMUM ACID! (filter sweep madness)")
        print("-" * 40)
        
        # Go crazy with the filter
        acid.filter.set_param('resonance', 0.94)  # Almost self-oscillating
        acid.filter.set_param('env_amount', 1.0)  # Maximum envelope
        acid.filter.set_param('decay', 100.0)     # Faster decay for more punch
        acid.dist.set_param('drive', 8.0)         # More distortion!
        
        # Play with manual filter sweeps
        for rep in range(8):
            # Sweep the cutoff while playing
            cutoff = 200 + (rep * 100)  # Gradually open
            acid.filter.set_param('cutoff', cutoff)
            
            for note, accent in notes:
                if note > 0:
                    acid.osc.set_param('freq', note)
                    acid.filter.set_accent(accent)
                    acid.filter.set_gate(True)
                time.sleep(0.125)
        
        print("\n" + "=" * 70)
        print("ACID DEMONSTRATION COMPLETE!")
        print("=" * 70)
        print(f"\nTotal buffers processed: {acid.buffer_count}")
        print("\nDid you hear:")
        print("- The filter envelope 'wow' on each note?")
        print("- The resonance getting more aggressive?")
        print("- The filter opening up in part 3?")
        print("- The crazy acid sweeps in part 4?")


if __name__ == "__main__":
    run_live_acid_demo()