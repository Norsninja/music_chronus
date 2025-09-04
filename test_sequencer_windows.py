#!/usr/bin/env python3
"""
Test sequencer on Windows with proper timing
Simplified version that avoids the emergency fill issues
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import threading
import numpy as np
import sounddevice as sd
from music_chronus.modules.simple_sine import SimpleSine
from music_chronus.modules.adsr import ADSR
from pythonosc import udp_client

# Configuration
SAMPLE_RATE = 48000  # WASAPI standard
BUFFER_SIZE = 256
BPM = 120
PATTERN = "X...x...X...x..."  # 16-step pattern

class SimpleSequencer:
    """
    Simplified sequencer that directly controls modules
    Uses sample-accurate timing in the audio callback
    """
    
    def __init__(self, sample_rate=48000, buffer_size=256, bpm=120):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.bpm = bpm
        
        # Create modules
        self.osc = SimpleSine(sample_rate, buffer_size)
        self.env = ADSR(sample_rate, buffer_size)
        
        # Configure modules
        self.osc.set_param('freq', 220.0)
        self.osc.set_param('gain', 0.5)
        
        self.env.set_param('attack', 5.0)     # 5ms
        self.env.set_param('decay', 50.0)     # 50ms
        self.env.set_param('sustain', 0.7)
        self.env.set_param('release', 100.0)  # 100ms
        
        # Pattern parsing
        self.pattern = PATTERN
        self.steps = len(self.pattern)
        self.current_step = 0
        
        # Timing calculation
        self.samples_per_beat = int((60.0 / bpm) * sample_rate)
        self.samples_per_step = self.samples_per_beat // 4  # 16th notes
        self.sample_counter = 0
        
        # Gate state
        self.gate_on = False
        self.gate_duration_samples = self.samples_per_step // 2  # 50% gate length
        self.gate_off_counter = 0
        
        # Statistics
        self.total_buffers = 0
        self.underruns = 0
        self.step_times = []
        self.last_step_time = time.perf_counter()
    
    def audio_callback(self, outdata, frames, time_info, status):
        """Audio callback with sample-accurate sequencing"""
        
        if status:
            self.underruns += 1
        
        self.total_buffers += 1
        
        # Allocate buffers
        in_buf = np.zeros(frames, dtype=np.float32)
        out_buf = np.zeros(frames, dtype=np.float32)
        
        # Process sample-by-sample for accurate timing
        for i in range(frames):
            # Check for step trigger
            if self.sample_counter >= self.samples_per_step:
                self.sample_counter = 0
                self.advance_step()
            
            # Check for gate off
            if self.gate_on and self.gate_off_counter > 0:
                self.gate_off_counter -= 1
                if self.gate_off_counter == 0:
                    self.env.set_gate(False)
                    self.gate_on = False
            
            self.sample_counter += 1
        
        # Process audio through modules
        self.osc.process_buffer(in_buf, out_buf)
        
        # Apply envelope
        np.copyto(in_buf, out_buf)
        self.env.process_buffer(in_buf, out_buf)
        
        # Output
        outdata[:, 0] = out_buf
    
    def advance_step(self):
        """Advance to next step in pattern"""
        
        # Record timing
        now = time.perf_counter()
        if self.step_times:
            interval = now - self.last_step_time
            self.step_times.append(interval)
        self.last_step_time = now
        
        # Get current step
        char = self.pattern[self.current_step]
        
        # Process step
        if char == 'X':  # Accent
            self.osc.set_param('freq', 220.0)
            self.osc.set_param('gain', 0.7)
            self.env.set_gate(True)
            self.gate_on = True
            self.gate_off_counter = self.gate_duration_samples
            
        elif char == 'x':  # Normal hit
            self.osc.set_param('freq', 165.0)
            self.osc.set_param('gain', 0.5)
            self.env.set_gate(True)
            self.gate_on = True
            self.gate_off_counter = self.gate_duration_samples
        
        # Advance step counter
        self.current_step = (self.current_step + 1) % self.steps
        
        # Visual feedback (Windows-safe characters)
        pattern_display = list(self.pattern)
        pattern_display[self.current_step] = '>'
        print(f"\rStep {self.current_step:2d}: {''.join(pattern_display)}", end='', flush=True)


def test_sequencer(duration=10.0):
    """Test the sequencer"""
    
    print("=" * 60)
    print("Windows Sequencer Test")
    print("=" * 60)
    print(f"BPM: {BPM}")
    print(f"Pattern: {PATTERN}")
    print(f"Buffer size: {BUFFER_SIZE} samples ({BUFFER_SIZE/SAMPLE_RATE*1000:.1f}ms)")
    print("=" * 60)
    
    # Create sequencer
    seq = SimpleSequencer(SAMPLE_RATE, BUFFER_SIZE, BPM)
    
    # Find WASAPI device
    wasapi_device = None
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
            if device['max_output_channels'] > 0 and ('USB' in device['name'] or 'AB13X' in device['name']):
                wasapi_device = i
                print(f"Using WASAPI device: {device['name']}\n")
                break
    
    if not wasapi_device:
        for i, device in enumerate(devices):
            if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
                if device['max_output_channels'] > 0:
                    wasapi_device = i
                    print(f"Using WASAPI device: {device['name']}\n")
                    break
    
    # Create audio stream
    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        device=wasapi_device,
        channels=1,
        callback=seq.audio_callback,
        latency='low'
    )
    
    # Run sequencer
    print("Starting sequencer...\n")
    with stream:
        time.sleep(duration)
    
    print("\n\n" + "=" * 60)
    print("Statistics:")
    print(f"Total buffers: {seq.total_buffers}")
    print(f"Underruns: {seq.underruns}")
    
    if seq.step_times:
        intervals = np.array(seq.step_times) * 1000  # Convert to ms
        expected = (60.0 / BPM / 4) * 1000  # Expected interval in ms
        
        print(f"\nTiming accuracy:")
        print(f"  Expected step interval: {expected:.1f}ms")
        print(f"  Actual mean: {np.mean(intervals):.1f}ms")
        print(f"  Std deviation: {np.std(intervals):.2f}ms")
        print(f"  Min/Max: {np.min(intervals):.1f}ms / {np.max(intervals):.1f}ms")
        print(f"  Timing drift: {(np.mean(intervals) - expected)/expected*100:.1f}%")


def test_osc_sequencer():
    """Test controlling the Windows engine via OSC with sequenced patterns"""
    
    print("=" * 60)
    print("OSC Sequencer Test")
    print("=" * 60)
    print("Make sure engine_windows.py is running!")
    print("=" * 60)
    
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    # Setup
    client.send_message("/amplitude", 0.4)
    client.send_message("/gate", 1)
    
    # Pattern
    pattern = "X...x...X...x..."
    notes = [220, 0, 0, 0, 165, 0, 0, 0, 220, 0, 0, 0, 165, 0, 0, 0]
    
    bpm = 120
    step_duration = 60.0 / bpm / 4  # 16th notes
    
    print(f"Playing pattern: {pattern}")
    print(f"BPM: {bpm}")
    print("Press Ctrl+C to stop\n")
    
    try:
        step = 0
        while True:
            char = pattern[step]
            
            if char == 'X' or char == 'x':
                # Note on
                freq = notes[step]
                if freq > 0:
                    client.send_message("/frequency", freq)
                    client.send_message("/gate", 1)
                    client.send_message("/amplitude", 0.6 if char == 'X' else 0.4)
            else:
                # Note off
                client.send_message("/gate", 0)
            
            # Visual feedback (Windows-safe)
            pattern_display = list(pattern)
            pattern_display[step] = '>'
            print(f"\rStep {step:2d}: {''.join(pattern_display)}", end='', flush=True)
            
            # Wait for next step
            time.sleep(step_duration)
            
            # Advance
            step = (step + 1) % len(pattern)
            
    except KeyboardInterrupt:
        print("\n\nStopping...")
        client.send_message("/gate", 0)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "osc":
        test_osc_sequencer()
    else:
        test_sequencer(duration=15.0)