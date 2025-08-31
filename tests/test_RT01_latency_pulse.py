#!/usr/bin/env python3
"""
RT-01: Audio Server Latency Test Harness (PulseAudio Fallback)
Tests round-trip latency using direct PulseAudio output
This is a fallback test when rtmixer is not available
"""

import time
import numpy as np
import subprocess
import os
import tempfile
from dataclasses import dataclass
from typing import List
import statistics
from scipy.io import wavfile

# Test configuration
SAMPLE_RATE = 44100
BUFFER_SIZE = 256  # ~5.8ms at 44100Hz
TEST_ITERATIONS = 20  # Reduced for quicker testing
LATENCY_TARGET = 0.050  # 50ms for PulseAudio (more realistic)
LATENCY_IDEAL = 0.030  # 30ms ideal for PulseAudio

@dataclass
class LatencyMeasurement:
    """Single latency measurement result"""
    trigger_time: float
    audio_time: float
    latency_ms: float
    passed: bool

class PulseAudioTestServer:
    """Minimal audio server using PulseAudio directly"""
    
    def __init__(self):
        self.measurements = []
        os.environ['PULSE_SERVER'] = 'tcp:172.21.240.1:4713'
        
    def trigger_beep(self, freq=1000, duration=0.05):
        """Generate and play a beep, measuring latency"""
        trigger_time = time.perf_counter()
        
        # Generate beep
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
        beep = 0.5 * np.sin(2 * np.pi * freq * t)
        
        # Window the beep for click-free playback
        window = np.hanning(len(beep))
        beep = beep * window
        
        # Convert to int16
        beep_int = (beep * 32767).astype(np.int16)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            wavfile.write(f.name, SAMPLE_RATE, beep_int)
            temp_file = f.name
        
        # Play with paplay (this blocks until playback starts)
        try:
            subprocess.run(
                ['paplay', temp_file],
                env={'PULSE_SERVER': 'tcp:172.21.240.1:4713'},
                capture_output=True,
                timeout=1
            )
        except subprocess.TimeoutExpired:
            pass
        finally:
            os.unlink(temp_file)
        
        audio_time = time.perf_counter()
        latency_ms = (audio_time - trigger_time) * 1000
        
        measurement = LatencyMeasurement(
            trigger_time=trigger_time,
            audio_time=audio_time,
            latency_ms=latency_ms,
            passed=(latency_ms <= LATENCY_TARGET * 1000)
        )
        
        self.measurements.append(measurement)
        return measurement
    
    def run_test(self, iterations=TEST_ITERATIONS):
        """Run multiple latency measurements"""
        print(f"\nRunning {iterations} latency measurements...")
        print("-" * 40)
        
        for i in range(iterations):
            measurement = self.trigger_beep(freq=1000 + i*50)  # Vary frequency
            status = "✓" if measurement.passed else "✗"
            print(f"[{i+1:2}/{iterations}] Latency: {measurement.latency_ms:6.2f}ms {status}")
            time.sleep(0.1)  # Small delay between tests
        
        return self.get_statistics()
    
    def get_statistics(self):
        """Calculate statistics from measurements"""
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
            'total': len(self.measurements)
        }
    
    def print_report(self):
        """Print test results"""
        stats = self.get_statistics()
        if not stats:
            print("No measurements collected!")
            return False
        
        print("\n" + "="*60)
        print("RT-01 LATENCY TEST RESULTS (PulseAudio Mode)")
        print("="*60)
        print(f"Total Measurements: {stats['total']}")
        print(f"Success Rate: {stats['success_rate']:.1f}%")
        print("-"*60)
        print(f"Mean Latency:   {stats['mean_ms']:6.2f}ms")
        print(f"Median Latency: {stats['median_ms']:6.2f}ms")
        print(f"Std Deviation:  {stats['stdev_ms']:6.2f}ms")
        print(f"Min Latency:    {stats['min_ms']:6.2f}ms")
        print(f"Max Latency:    {stats['max_ms']:6.2f}ms")
        print("-"*60)
        
        # Pass/Fail determination
        overall_pass = False
        if stats['max_ms'] <= LATENCY_TARGET * 1000:
            if stats['mean_ms'] <= LATENCY_IDEAL * 1000:
                print("✓ PASS - GOOD: Achieved ideal PulseAudio latency!")
                overall_pass = True
            else:
                print("✓ PASS: Within acceptable PulseAudio limits")
                overall_pass = True
        else:
            print("✗ FAIL: Latency requirements not met")
            print(f"  Max latency {stats['max_ms']:.2f}ms exceeds {LATENCY_TARGET*1000}ms limit")
        
        print("="*60)
        print("\nNOTE: This is using PulseAudio directly, not rtmixer.")
        print("Real-time performance will be better with rtmixer installed.")
        
        return overall_pass

def test_pulseaudio_connection():
    """Verify PulseAudio connection"""
    print("\n1. Testing PulseAudio connection...")
    env = {'PULSE_SERVER': 'tcp:172.21.240.1:4713'}
    try:
        result = subprocess.run(
            ['pactl', 'info'], 
            env=env, 
            capture_output=True, 
            text=True, 
            timeout=2
        )
        if result.returncode == 0:
            print("✓ PulseAudio connection established")
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

def main():
    """Run the latency test"""
    print("="*60)
    print("RT-01: AUDIO SERVER LATENCY TEST (PulseAudio Fallback)")
    print("="*60)
    print(f"Target Latency: <{LATENCY_TARGET*1000:.0f}ms (PulseAudio)")
    print(f"Ideal Latency: <{LATENCY_IDEAL*1000:.0f}ms")
    print("="*60)
    
    # Test PulseAudio connection
    if not test_pulseaudio_connection():
        print("\n✗ Cannot proceed without PulseAudio connection")
        return False
    
    # Create test server
    print("\n2. Creating PulseAudio test server...")
    server = PulseAudioTestServer()
    print("✓ Test server created")
    
    # Run latency tests
    print("\n3. Starting latency measurements...")
    server.run_test()
    
    # Print results
    return server.print_report()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)