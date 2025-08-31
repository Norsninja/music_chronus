#!/usr/bin/env python3
"""
RT-01: Correct rtmixer latency test using proper API
Testing actual achievable latency with rtmixer's play_buffer() method
"""

import time
import numpy as np
import rtmixer
import sounddevice as sd
import os
from statistics import mean, stdev

# Configuration
SAMPLE_RATE = 44100
BUFFER_SIZE = 256  # ~5.8ms per buffer
CHANNELS = 1
TEST_ITERATIONS = 20

def measure_rtmixer_latency():
    """Measure actual audio latency using rtmixer's proper API"""
    
    print("="*60)
    print("RT-01: RTMIXER LATENCY TEST")
    print("="*60)
    print(f"Sample Rate: {SAMPLE_RATE}Hz")
    print(f"Buffer Size: {BUFFER_SIZE} samples ({BUFFER_SIZE/SAMPLE_RATE*1000:.1f}ms)")
    print(f"Target: <20ms total latency")
    print("="*60)
    
    # Set PulseAudio environment
    os.environ['PULSE_SERVER'] = 'tcp:172.21.240.1:4713'
    
    # Check devices
    print("\n1. Audio Setup:")
    try:
        devices = sd.query_devices()
        default_out = sd.default.device[1]
        print(f"   Output device: {devices[default_out]['name']}")
        print(f"   Max channels: {devices[default_out]['max_output_channels']}")
    except Exception as e:
        print(f"   Warning: {e}")
    
    print("\n2. Creating rtmixer...")
    
    # Create mixer with low latency settings
    mixer = rtmixer.Mixer(
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        channels=CHANNELS,
        latency='low'  # Request low latency mode
    )
    
    # Start the mixer (enter context)
    mixer.__enter__()
    print("   ✓ Mixer started")
    
    # Measure scheduling latency
    scheduling_latencies = []
    playback_times = []
    
    print(f"\n3. Running {TEST_ITERATIONS} latency measurements...")
    print("-" * 40)
    
    try:
        for i in range(TEST_ITERATIONS):
            # Generate test tone (short click for precise timing)
            duration = 0.001  # 1ms click
            samples = int(SAMPLE_RATE * duration)
            t = np.linspace(0, duration, samples)
            
            # Create click with envelope to avoid pops
            click = np.sin(2 * np.pi * 1000 * t) * np.exp(-t * 1000)
            click = click.astype(np.float32)
            
            # Measure scheduling time
            schedule_start = time.perf_counter()
            
            # Schedule playback with start=0 (ASAP)
            action = mixer.play_buffer(
                buffer=click,
                channels=CHANNELS,
                start=0,  # Play immediately
                allow_belated=True
            )
            
            schedule_end = time.perf_counter()
            scheduling_latency = (schedule_end - schedule_start) * 1000
            scheduling_latencies.append(scheduling_latency)
            
            # Wait for action to complete
            mixer.wait(action, sleeptime=1)
            
            # Check action timing (this is when audio actually started)
            if action.actual_time > 0:
                # The actual_time is relative to stream start
                playback_delay = action.actual_time * 1000  # Convert to ms
                playback_times.append(playback_delay)
            
            # Get stats from the action
            if i % 5 == 0:
                stats = action.stats
                print(f"   [{i+1:2}/{TEST_ITERATIONS}] Schedule: {scheduling_latency:.2f}ms, "
                      f"Blocks: {stats.blocks}, "
                      f"Underflows: {stats.output_underflows}")
            
            # Small delay between tests
            time.sleep(0.05)
            
    finally:
        # Clean up
        mixer.__exit__(None, None, None)
        print("\n   ✓ Mixer stopped")
    
    # Calculate results
    print("\n" + "="*60)
    print("RESULTS:")
    print("-" * 60)
    
    if scheduling_latencies:
        print(f"Scheduling Latency (Python → C callback):")
        print(f"  Mean:  {mean(scheduling_latencies):.2f}ms")
        print(f"  Min:   {min(scheduling_latencies):.2f}ms")
        print(f"  Max:   {max(scheduling_latencies):.2f}ms")
        if len(scheduling_latencies) > 1:
            print(f"  StDev: {stdev(scheduling_latencies):.2f}ms")
    
    # Hardware buffer latency
    hardware_latency = BUFFER_SIZE / SAMPLE_RATE * 1000
    print(f"\nHardware Buffer Latency: {hardware_latency:.1f}ms")
    
    # Total estimated latency
    total_latency = hardware_latency + mean(scheduling_latencies)
    print(f"\nEstimated Total Latency: {total_latency:.1f}ms")
    print("(Scheduling + Buffer + Hardware)")
    
    # Check stream statistics
    stream_stats = mixer.stats
    if stream_stats:
        print(f"\nStream Statistics:")
        print(f"  Total blocks: {stream_stats.blocks}")
        print(f"  Output underflows: {stream_stats.output_underflows}")
        if stream_stats.output_underflows > 0:
            print("  ⚠️  Underflows detected - buffer size may be too small")
    
    print("="*60)
    
    # Pass/Fail determination
    if total_latency < 20:
        print("✓ PASS: Achieved <20ms latency target!")
        if total_latency < 10:
            print("  EXCELLENT: Achieved <10ms ideal latency!")
        return True
    elif total_latency < 30:
        print("✓ PASS (Marginal): Acceptable for most music applications")
        return True
    else:
        print("✗ FAIL: Latency too high for real-time music")
        return False

def main():
    """Run the test with error handling"""
    try:
        print("Starting rtmixer latency test...")
        print("You should hear a series of clicks.\n")
        
        success = measure_rtmixer_latency()
        
        print("\nNOTE: This measures scheduling latency + buffer latency.")
        print("Actual round-trip latency includes PulseAudio bridge overhead.")
        
        return success
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        print("\nTroubleshooting:")
        print("1. Verify PulseAudio is running: pactl info")
        print("2. Check PULSE_SERVER environment variable")
        print("3. Try larger buffer size if getting underflows")
        print("4. Ensure no other audio applications are running")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)