#!/usr/bin/env python3
"""
Test audio capabilities on Windows
"""

import sounddevice as sd
import numpy as np
import time

def list_audio_devices():
    """List all available audio devices and their capabilities"""
    print("=" * 60)
    print("AUDIO DEVICES AND CAPABILITIES")
    print("=" * 60)
    
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        print(f"\n[{i}] {device['name']}")
        print(f"    Host API: {sd.query_hostapis(device['hostapi'])['name']}")
        print(f"    Channels: {device['max_input_channels']} in, {device['max_output_channels']} out")
        print(f"    Default Sample Rate: {device['default_samplerate']} Hz")
        print(f"    Low/High Latency: {device['default_low_output_latency']*1000:.1f}ms / {device['default_high_output_latency']*1000:.1f}ms")
    
    print(f"\nDefault Input Device: {sd.default.device[0]}")
    print(f"Default Output Device: {sd.default.device[1]}")
    
    # Show available host APIs
    print("\n" + "=" * 60)
    print("HOST APIs AVAILABLE")
    print("=" * 60)
    for api in sd.query_hostapis():
        print(f"- {api['name']}: {api['device_count']} devices")

def test_simple_sine(duration=2.0, frequency=440.0, use_wasapi=False):
    """Test simple sine wave playback"""
    sample_rate = 44100
    samples = int(duration * sample_rate)
    
    # Generate sine wave
    t = np.arange(samples) / sample_rate
    audio = 0.5 * np.sin(2 * np.pi * frequency * t)
    
    print(f"\nPlaying {frequency}Hz sine wave for {duration}s...")
    
    if use_wasapi:
        # Try to find WASAPI device
        wasapi_device = None
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if 'WASAPI' in sd.query_hostapis(device['hostapi'])['name']:
                if device['max_output_channels'] > 0:
                    wasapi_device = i
                    print(f"Using WASAPI device: {device['name']}")
                    break
        
        if wasapi_device:
            sd.play(audio, sample_rate, device=wasapi_device)
        else:
            print("WASAPI device not found, using default")
            sd.play(audio, sample_rate)
    else:
        sd.play(audio, sample_rate)
    
    sd.wait()
    print("Playback complete")

def test_callback_latency(duration=5.0):
    """Test callback-based playback with latency measurement"""
    sample_rate = 44100
    buffer_size = 256
    frequency = 440.0
    
    # State for callback
    phase = 0.0
    callback_times = []
    
    def audio_callback(outdata, frames, time_info, status):
        nonlocal phase, callback_times
        
        if status:
            print(f"Callback status: {status}")
        
        # Record callback timing
        callback_times.append(time_info.currentTime)
        
        # Generate sine wave
        t = np.arange(frames) / sample_rate
        audio = 0.5 * np.sin(2 * np.pi * frequency * t + phase)
        phase += 2 * np.pi * frequency * frames / sample_rate
        
        # Wrap phase to prevent overflow
        if phase > 2 * np.pi:
            phase -= 2 * np.pi
        
        outdata[:] = audio.reshape(-1, 1)
    
    print(f"\nTesting callback-based playback for {duration}s...")
    print(f"Buffer size: {buffer_size} samples ({buffer_size/sample_rate*1000:.1f}ms)")
    
    with sd.OutputStream(
        samplerate=sample_rate,
        blocksize=buffer_size,
        channels=1,
        callback=audio_callback
    ) as stream:
        time.sleep(duration)
    
    if len(callback_times) > 1:
        intervals = np.diff(callback_times) * 1000  # Convert to ms
        print(f"Callback interval stats:")
        print(f"  Mean: {np.mean(intervals):.2f}ms")
        print(f"  Std:  {np.std(intervals):.2f}ms")
        print(f"  Min:  {np.min(intervals):.2f}ms")
        print(f"  Max:  {np.max(intervals):.2f}ms")

if __name__ == "__main__":
    print("Windows Audio Test for Music Chronus")
    print("=" * 60)
    
    # List devices
    list_audio_devices()
    
    # Test basic playback
    print("\n" + "=" * 60)
    print("TEST 1: Basic Playback (Default API)")
    print("=" * 60)
    test_simple_sine(duration=1.0)
    
    # Test WASAPI if available
    print("\n" + "=" * 60)
    print("TEST 2: WASAPI Playback")
    print("=" * 60)
    test_simple_sine(duration=1.0, use_wasapi=True)
    
    # Test callback mode
    print("\n" + "=" * 60)
    print("TEST 3: Callback Mode (for low latency)")
    print("=" * 60)
    test_callback_latency(duration=3.0)
    
    print("\n" + "=" * 60)
    print("Tests complete!")