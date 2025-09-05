#!/usr/bin/env python3
"""
Simplified sequencer timing test for Windows
Focus on measuring timing accuracy without the complex display
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import numpy as np
import sounddevice as sd
from music_chronus.modules.simple_sine import SimpleSine
from music_chronus.modules.adsr import ADSR

# Configuration
SAMPLE_RATE = 48000
BUFFER_SIZE = 256
BPM = 120
PATTERN = "X...x...X...x..."

class TimingTestSequencer:
    """Sequencer focused on timing measurement"""
    
    def __init__(self, sample_rate, buffer_size, bpm):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.bpm = bpm
        
        # Modules
        self.osc = SimpleSine(sample_rate, buffer_size)
        self.env = ADSR(sample_rate, buffer_size)
        
        self.osc.set_param('gain', 0.3)
        self.env.set_param('attack', 5.0)
        self.env.set_param('decay', 50.0)
        self.env.set_param('sustain', 0.5)
        self.env.set_param('release', 100.0)
        
        # Pattern
        self.pattern = PATTERN
        self.steps = len(self.pattern)
        self.current_step = 0
        
        # Timing
        self.samples_per_beat = int((60.0 / bpm) * sample_rate)
        self.samples_per_step = self.samples_per_beat // 4
        self.sample_counter = 0
        self.gate_duration_samples = self.samples_per_step // 2
        self.gate_off_counter = 0
        
        # Metrics
        self.step_count = 0
        self.step_times = []
        self.last_step_time = None
        self.start_time = None
    
    def audio_callback(self, outdata, frames, time_info, status):
        in_buf = np.zeros(frames, dtype=np.float32)
        out_buf = np.zeros(frames, dtype=np.float32)
        
        # Check for step boundaries
        samples_to_process = frames
        while samples_to_process > 0:
            samples_until_step = self.samples_per_step - self.sample_counter
            chunk = min(samples_to_process, samples_until_step)
            
            if samples_until_step <= chunk:
                # Step boundary reached
                self.trigger_step()
            
            self.sample_counter = (self.sample_counter + chunk) % self.samples_per_step
            samples_to_process -= chunk
            
            # Handle gate off
            if self.gate_off_counter > 0:
                self.gate_off_counter -= chunk
                if self.gate_off_counter <= 0:
                    self.env.set_gate(False)
        
        # Process audio
        self.osc.process_buffer(in_buf, out_buf)
        np.copyto(in_buf, out_buf)
        self.env.process_buffer(in_buf, out_buf)
        outdata[:, 0] = out_buf
    
    def trigger_step(self):
        # Record timing
        now = time.perf_counter()
        if self.last_step_time is not None:
            interval = now - self.last_step_time
            self.step_times.append(interval)
        else:
            self.start_time = now
        self.last_step_time = now
        
        # Process pattern
        char = self.pattern[self.current_step]
        if char == 'X':
            self.osc.set_param('freq', 220.0)
            self.env.set_gate(True)
            self.gate_off_counter = self.gate_duration_samples
        elif char == 'x':
            self.osc.set_param('freq', 165.0)
            self.env.set_gate(True)
            self.gate_off_counter = self.gate_duration_samples
        
        self.step_count += 1
        self.current_step = (self.current_step + 1) % self.steps


def run_timing_test(duration=10.0):
    print("Windows Sequencer Timing Test")
    print("=" * 50)
    print(f"BPM: {BPM}")
    print(f"Expected step interval: {60.0/BPM/4*1000:.1f}ms")
    print(f"Buffer: {BUFFER_SIZE} samples ({BUFFER_SIZE/SAMPLE_RATE*1000:.1f}ms)")
    print()
    
    # Find WASAPI device
    wasapi_device = None
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
            if device['max_output_channels'] > 0:
                wasapi_device = i
                break
    
    # Create and run sequencer
    seq = TimingTestSequencer(SAMPLE_RATE, BUFFER_SIZE, BPM)
    
    with sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        device=wasapi_device,
        channels=1,
        callback=seq.audio_callback,
        latency='low'
    ) as stream:
        print(f"Running for {duration} seconds...")
        time.sleep(duration)
    
    # Analyze results
    print("\nResults:")
    print("-" * 50)
    
    if seq.step_times:
        intervals = np.array(seq.step_times) * 1000
        expected = 60.0 / BPM / 4 * 1000
        
        print(f"Steps triggered: {seq.step_count}")
        print(f"Expected interval: {expected:.1f}ms")
        print(f"Actual mean: {np.mean(intervals):.2f}ms")
        print(f"Std deviation: {np.std(intervals):.2f}ms")
        print(f"Min/Max: {np.min(intervals):.2f}ms / {np.max(intervals):.2f}ms")
        
        drift = (np.mean(intervals) - expected) / expected * 100
        print(f"\nTiming accuracy: {100 - abs(drift):.1f}%")
        
        if abs(drift) < 1.0:
            print("✓ EXCELLENT - Less than 1% drift")
        elif abs(drift) < 5.0:
            print("✓ GOOD - Less than 5% drift")
        else:
            print(f"✗ POOR - {abs(drift):.1f}% drift")
        
        # Check jitter
        if np.std(intervals) < 1.0:
            print("✓ EXCELLENT - Jitter < 1ms")
        elif np.std(intervals) < 5.0:
            print("✓ GOOD - Jitter < 5ms")
        else:
            print(f"✗ POOR - Jitter {np.std(intervals):.1f}ms")


if __name__ == "__main__":
    run_timing_test(10.0)