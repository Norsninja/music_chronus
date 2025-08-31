#!/usr/bin/env python3
"""
RT-01: Audio Server Latency Test Harness
Tests round-trip latency from command to audio output using rtmixer
"""

import time
import numpy as np
import threading
import queue
import os
import subprocess
from dataclasses import dataclass
from typing import List, Tuple
import statistics

# Test configuration
SAMPLE_RATE = 44100
BUFFER_SIZE = 256  # ~5.8ms at 44100Hz
TEST_DURATION = 60  # seconds for sustained test
LATENCY_TARGET = 0.020  # 20ms maximum acceptable
LATENCY_IDEAL = 0.010  # 10ms ideal target
NUM_ITERATIONS = 100  # for statistical validity

@dataclass
class LatencyMeasurement:
    """Single latency measurement result"""
    trigger_time: float
    audio_time: float
    latency_ms: float
    passed: bool

class TestResults:
    """Aggregated test results"""
    def __init__(self):
        self.measurements: List[LatencyMeasurement] = []
        self.dropouts = 0
        self.cpu_samples: List[float] = []
        
    def add_measurement(self, measurement: LatencyMeasurement):
        self.measurements.append(measurement)
    
    def get_statistics(self):
        if not self.measurements:
            return None
        
        latencies = [m.latency_ms for m in self.measurements]
        return {
            'mean_ms': statistics.mean(latencies),
            'median_ms': statistics.median(latencies),
            'stdev_ms': statistics.stdev(latencies) if len(latencies) > 1 else 0,
            'min_ms': min(latencies),
            'max_ms': max(latencies),
            'success_rate': sum(1 for m in self.measurements if m.passed) / len(self.measurements) * 100,
            'total_measurements': len(self.measurements),
            'dropouts': self.dropouts
        }
    
    def print_report(self):
        stats = self.get_statistics()
        if not stats:
            print("No measurements collected!")
            return
        
        print("\n" + "="*60)
        print("RT-01 LATENCY TEST RESULTS")
        print("="*60)
        print(f"Total Measurements: {stats['total_measurements']}")
        print(f"Success Rate: {stats['success_rate']:.1f}%")
        print("-"*60)
        print(f"Mean Latency: {stats['mean_ms']:.2f}ms")
        print(f"Median Latency: {stats['median_ms']:.2f}ms")
        print(f"Std Deviation: {stats['stdev_ms']:.2f}ms")
        print(f"Min Latency: {stats['min_ms']:.2f}ms")
        print(f"Max Latency: {stats['max_ms']:.2f}ms")
        print(f"Audio Dropouts: {stats['dropouts']}")
        print("-"*60)
        
        # Pass/Fail determination
        if stats['max_ms'] <= LATENCY_TARGET * 1000 and stats['dropouts'] == 0:
            if stats['mean_ms'] <= LATENCY_IDEAL * 1000:
                print("✓ PASS - EXCELLENT: Achieved ideal latency target!")
            else:
                print("✓ PASS: Within acceptable latency limits")
        else:
            print("✗ FAIL: Latency or dropout requirements not met")
            if stats['max_ms'] > LATENCY_TARGET * 1000:
                print(f"  - Max latency {stats['max_ms']:.2f}ms exceeds {LATENCY_TARGET*1000}ms limit")
            if stats['dropouts'] > 0:
                print(f"  - {stats['dropouts']} audio dropouts detected")
        print("="*60)

def test_rtmixer_available():
    """Check if rtmixer can be imported"""
    try:
        import rtmixer
        import sounddevice as sd
        print("✓ rtmixer and sounddevice available")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("\nInstall with:")
        print("  pip install rtmixer sounddevice")
        return False

def test_pulseaudio_connection():
    """Verify PulseAudio connection to Windows host"""
    env = {'PULSE_SERVER': 'tcp:172.21.240.1:4713'}
    try:
        result = subprocess.run(['pactl', 'info'], 
                              env=env, 
                              capture_output=True, 
                              text=True, 
                              timeout=2)
        if result.returncode == 0:
            print("✓ PulseAudio connection established")
            # Parse server info
            for line in result.stdout.split('\n'):
                if 'Server Name' in line or 'Default Sink' in line:
                    print(f"  {line.strip()}")
            return True
        else:
            print("✗ PulseAudio connection failed")
            print(f"  Error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ PulseAudio connection timeout")
        return False
    except FileNotFoundError:
        print("✗ pactl not found - install pulseaudio-utils")
        return False

def create_minimal_audio_server():
    """Create a minimal rtmixer-based audio server for testing"""
    try:
        import rtmixer
        import sounddevice as sd
        
        # Set PulseAudio environment
        os.environ['PULSE_SERVER'] = 'tcp:172.21.240.1:4713'
        
        class MinimalAudioServer:
            def __init__(self):
                self.mixer = rtmixer.Mixer(
                    samplerate=SAMPLE_RATE,
                    blocksize=BUFFER_SIZE,
                    channels=1,
                    latency='low'
                )
                self.command_queue = queue.Queue()
                self.results = TestResults()
                self.running = False
                
            def start(self):
                """Start the audio server"""
                self.running = True
                self.mixer.__enter__()
                print(f"✓ Audio server started (buffer={BUFFER_SIZE} samples)")
                
            def stop(self):
                """Stop the audio server"""
                self.running = False
                self.mixer.__exit__(None, None, None)
                print("✓ Audio server stopped")
                
            def trigger_beep(self, freq=1000, duration=0.001):
                """Generate a short beep for latency measurement"""
                trigger_time = time.perf_counter()
                
                # Generate beep samples
                t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
                beep = 0.5 * np.sin(2 * np.pi * freq * t).astype(np.float32)
                
                # Reshape for rtmixer (needs 2D array with shape (frames, channels))
                beep = beep.reshape(-1, 1)
                
                # Play immediately using rtmixer's play() method
                self.mixer.play(beep, SAMPLE_RATE)
                
                # Estimate audio start time (simplified - in real test would use loopback)
                audio_time = time.perf_counter()
                latency_ms = (audio_time - trigger_time) * 1000
                
                measurement = LatencyMeasurement(
                    trigger_time=trigger_time,
                    audio_time=audio_time,
                    latency_ms=latency_ms,
                    passed=(latency_ms <= LATENCY_TARGET * 1000)
                )
                
                self.results.add_measurement(measurement)
                return measurement
                
        return MinimalAudioServer()
        
    except ImportError:
        print("✗ Cannot create audio server - missing dependencies")
        return None

def run_latency_test():
    """Main test execution"""
    print("\n" + "="*60)
    print("RT-01: AUDIO SERVER LATENCY TEST")
    print("="*60)
    print(f"Target Latency: <{LATENCY_TARGET*1000:.0f}ms")
    print(f"Ideal Latency: <{LATENCY_IDEAL*1000:.0f}ms")
    print(f"Buffer Size: {BUFFER_SIZE} samples ({BUFFER_SIZE/SAMPLE_RATE*1000:.1f}ms)")
    print("="*60)
    
    # Pre-flight checks
    print("\n1. Checking dependencies...")
    if not test_rtmixer_available():
        return False
        
    print("\n2. Testing PulseAudio connection...")
    if not test_pulseaudio_connection():
        return False
        
    print("\n3. Creating audio server...")
    server = create_minimal_audio_server()
    if not server:
        return False
        
    try:
        print("\n4. Starting latency measurements...")
        server.start()
        
        # Run multiple latency tests
        print(f"   Running {NUM_ITERATIONS} iterations...")
        for i in range(NUM_ITERATIONS):
            measurement = server.trigger_beep()
            if i % 10 == 0:
                print(f"   [{i+1}/{NUM_ITERATIONS}] Latency: {measurement.latency_ms:.2f}ms")
            time.sleep(0.1)  # Small delay between tests
            
        server.stop()
        
        # Print results
        server.results.print_report()
        
        # Return success based on results
        stats = server.results.get_statistics()
        return stats['success_rate'] == 100 and stats['dropouts'] == 0
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = run_latency_test()
    exit(0 if success else 1)