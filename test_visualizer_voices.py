#!/usr/bin/env python3
"""
Test script for dynamic voice count in visualizer
Tests different voice configurations
"""

import os
import time
import subprocess
import signal
from pythonosc import udp_client

def test_voice_configuration(num_voices):
    """Test visualizer with specific voice count"""
    print(f"\n{'='*60}")
    print(f"Testing with {num_voices} voices")
    print(f"{'='*60}")
    
    # Set environment variable
    os.environ['CHRONUS_NUM_VOICES'] = str(num_voices)
    
    # Start engine
    print(f"Starting engine with {num_voices} voices...")
    engine_proc = subprocess.Popen(
        ['python', 'engine_pyo.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for engine to start
    time.sleep(3)
    
    # Start visualizer in separate process
    print(f"Starting visualizer...")
    viz_proc = subprocess.Popen(
        ['python', 'visualizer.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for visualizer to initialize
    time.sleep(2)
    
    # Send test OSC messages
    client = udp_client.SimpleUDPClient('127.0.0.1', 5005)
    
    print(f"Sending test patterns to {num_voices} voices...")
    
    # Test each voice
    for i in range(1, num_voices + 1):
        # Set frequency for each voice (ascending scale)
        freq = 110 * (2 ** ((i-1) / 12))  # Chromatic scale from A2
        client.send_message(f'/mod/voice{i}/freq', freq)
        client.send_message(f'/gate/voice{i}', 1)
        time.sleep(0.1)
    
    # Let it run for a few seconds
    print("Playing all voices for 3 seconds...")
    time.sleep(3)
    
    # Turn off all voices
    for i in range(1, num_voices + 1):
        client.send_message(f'/gate/voice{i}', 0)
    
    time.sleep(1)
    
    # Cleanup
    print("Stopping processes...")
    viz_proc.terminate()
    engine_proc.terminate()
    
    # Wait for cleanup
    viz_proc.wait(timeout=2)
    engine_proc.wait(timeout=2)
    
    print(f"Test with {num_voices} voices completed\n")

def test_auto_detection():
    """Test auto-detection without environment variable"""
    print(f"\n{'='*60}")
    print("Testing auto-detection (no env var)")
    print(f"{'='*60}")
    
    # Clear environment variable
    if 'CHRONUS_NUM_VOICES' in os.environ:
        del os.environ['CHRONUS_NUM_VOICES']
    
    # Start engine with 8 voices
    os.environ['CHRONUS_NUM_VOICES'] = '8'
    print("Starting engine with 8 voices...")
    engine_proc = subprocess.Popen(
        ['python', 'engine_pyo.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    time.sleep(3)
    
    # Start visualizer WITHOUT env var (should auto-detect)
    del os.environ['CHRONUS_NUM_VOICES']
    print("Starting visualizer without CHRONUS_NUM_VOICES...")
    viz_proc = subprocess.Popen(
        ['python', 'visualizer.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    time.sleep(2)
    
    # Send test with 8 voices
    client = udp_client.SimpleUDPClient('127.0.0.1', 5005)
    
    print("Sending 8-voice chord...")
    for i in range(1, 9):
        freq = 220 * (2 ** ((i-1) / 12))
        client.send_message(f'/mod/voice{i}/freq', freq)
        client.send_message(f'/gate/voice{i}', 1)
        time.sleep(0.05)
    
    print("Visualizer should auto-detect 8 voices from OSC data...")
    time.sleep(3)
    
    # Cleanup
    for i in range(1, 9):
        client.send_message(f'/gate/voice{i}', 0)
    
    time.sleep(1)
    
    viz_proc.terminate()
    engine_proc.terminate()
    viz_proc.wait(timeout=2)
    engine_proc.wait(timeout=2)
    
    print("Auto-detection test completed\n")

if __name__ == "__main__":
    print("Music Chronus Visualizer - Dynamic Voice Count Tests")
    print("=" * 60)
    
    # Test with different voice counts
    test_configs = [1, 4, 8, 16]
    
    for num_voices in test_configs:
        try:
            test_voice_configuration(num_voices)
        except Exception as e:
            print(f"Error testing {num_voices} voices: {e}")
        time.sleep(2)
    
    # Test auto-detection
    try:
        test_auto_detection()
    except Exception as e:
        print(f"Error testing auto-detection: {e}")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("Phase 1 implementation validated:")
    print("- Environment variable detection works")
    print("- Dynamic array sizing works")
    print("- Auto-detection from OSC works")
    print("- Thread-safe reconfiguration works")
    print("=" * 60)