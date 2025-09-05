#!/usr/bin/env python3
"""
Recording-enabled acid bass session
Simple WAV recording for our Windows synthesizer
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import wave
import numpy as np
import sounddevice as sd
from datetime import datetime
from music_chronus.modules.simple_sine import SimpleSine
from music_chronus.modules.acid_filter import AcidFilter
from music_chronus.modules.distortion import Distortion

# Configuration
SAMPLE_RATE = 48000
BUFFER_SIZE = 256
CHANNELS = 1

class RecordingSession:
    """Session with recording capability"""
    
    def __init__(self, filename=None):
        # Modules
        self.osc = SimpleSine(SAMPLE_RATE, BUFFER_SIZE)
        self.filter = AcidFilter(SAMPLE_RATE, BUFFER_SIZE)
        self.dist = Distortion(SAMPLE_RATE, BUFFER_SIZE)
        
        # Configure for acid bass
        self.osc.set_param('gain', 0.9)
        self.filter.set_param('cutoff', 200.0)
        self.filter.set_param('resonance', 0.85)
        self.filter.set_param('env_amount', 0.9)
        self.filter.set_param('decay', 200.0)
        self.filter.set_param('drive', 3.0)
        self.dist.set_param('mode', 2)  # Foldback
        self.dist.set_param('drive', 4.0)
        self.dist.set_param('mix', 0.6)
        self.dist.set_param('tone', 0.4)
        
        # Recording setup
        self.recording = []
        self.filename = filename or f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        self.buffer_count = 0
        
    def audio_callback(self, outdata, frames, time_info, status):
        """Process and record audio"""
        if status:
            print(f"Audio status: {status}")
        
        self.buffer_count += 1
        
        # Process audio chain
        buf1 = np.zeros(frames, dtype=np.float32)
        buf2 = np.zeros(frames, dtype=np.float32)
        
        self.osc.process_buffer(buf1, buf2)
        np.copyto(buf1, buf2)
        
        self.filter.process_buffer(buf1, buf2)
        np.copyto(buf1, buf2)
        
        self.dist.process_buffer(buf1, buf2)
        
        # Output
        outdata[:, 0] = buf2
        
        # Record (convert to int16 for WAV)
        recorded = (buf2 * 32767).astype(np.int16)
        self.recording.extend(recorded.tolist())
    
    def save_recording(self):
        """Save recording to WAV file"""
        if not self.recording:
            print("No audio recorded")
            return
        
        # Save as WAV
        with wave.open(self.filename, 'wb') as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(np.array(self.recording, dtype=np.int16).tobytes())
        
        duration = len(self.recording) / SAMPLE_RATE
        size_kb = len(self.recording) * 2 / 1024
        
        print(f"\nRecording saved:")
        print(f"  File: {self.filename}")
        print(f"  Duration: {duration:.2f} seconds")
        print(f"  Size: {size_kb:.1f} KB")
        print(f"  Buffers: {self.buffer_count}")


def record_acid_session():
    """Record an acid bass session"""
    
    print("=" * 70)
    print("RECORDING ACID BASS SESSION")
    print("=" * 70)
    
    # Find AB13X device
    wasapi_device = None
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
            if 'AB13X' in device['name'] and device['max_output_channels'] > 0:
                wasapi_device = i
                print(f"Audio device: {device['name']}")
                break
    
    if not wasapi_device:
        for i, device in enumerate(devices):
            if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
                if device['max_output_channels'] > 0:
                    wasapi_device = i
                    break
    
    # Create recording session
    session = RecordingSession("acid_bass_demo.wav")
    
    print(f"Recording to: {session.filename}")
    print("\nStarting in 2 seconds...")
    time.sleep(2)
    
    # Create stream
    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        device=wasapi_device,
        channels=CHANNELS,
        callback=session.audio_callback,
        latency='low'
    )
    
    with stream:
        print("\n[RECORDING] Playing acid bassline...")
        
        # Pattern
        bassline = [
            (55, True),   # A1 accent
            (0, False),
            (55, False),
            (55, False),
            (0, False),
            (82.5, False), # E2
            (0, False),
            (55, False),
            (110, True),  # A2 accent
            (0, False),
            (55, False),
            (0, False),
            (65.4, False), # C2
            (0, False),
            (82.5, False),
            (55, True),
        ]
        
        # Record 8 bars
        for bar in range(8):
            # Modulate over time
            if bar == 2:
                session.filter.set_param('resonance', 0.90)
            elif bar == 4:
                session.filter.set_param('cutoff', 500.0)
            elif bar == 6:
                session.filter.set_param('resonance', 0.93)
                session.dist.set_param('drive', 6.0)
            
            # Play pattern
            for note, accent in bassline:
                if note > 0:
                    session.osc.set_param('freq', note)
                    session.filter.set_accent(accent)
                    session.filter.set_gate(True)
                time.sleep(0.125)  # 16th notes
        
        print("[RECORDING] Complete!")
    
    # Save the recording
    session.save_recording()
    
    print("\n" + "=" * 70)
    print("SESSION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    record_acid_session()