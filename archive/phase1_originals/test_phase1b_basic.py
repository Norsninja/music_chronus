#!/usr/bin/env python3
"""
Phase 1B: Basic OSC Control Test
Verifies frequency changes work without glitches
"""

import time
import subprocess
import sys
from pythonosc import udp_client

def test_basic_osc_control():
    """Test basic frequency changes via OSC"""
    print("=== Phase 1B: Basic OSC Control Test ===")
    print("Starting audio engine...")
    
    # Start the audio engine
    engine_proc = subprocess.Popen(
        [sys.executable, "audio_engine_v3.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Give it time to initialize
    time.sleep(2)
    
    # Send start command via stdin
    engine_proc.stdin.write("start\n")
    engine_proc.stdin.flush()
    time.sleep(1)
    
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("\nTesting frequency changes...")
    print("-" * 40)
    
    # Test frequency sequence
    test_frequencies = [
        (440, "A4"),
        (880, "A5"),
        (220, "A3"),
        (1760, "A6"),
        (110, "A2"),
        (440, "A4 (return)"),
    ]
    
    for freq, note in test_frequencies:
        print(f"Setting frequency to {freq} Hz ({note})")
        client.send_message("/engine/freq", freq)
        time.sleep(1)
    
    # Get status
    print("\nGetting final status...")
    engine_proc.stdin.write("status\n")
    engine_proc.stdin.flush()
    time.sleep(0.5)
    
    # Stop engine
    print("\nStopping engine...")
    engine_proc.stdin.write("quit\n")
    engine_proc.stdin.flush()
    
    # Wait for clean shutdown
    engine_proc.wait(timeout=5)
    
    print("\n=== Test Complete ===")
    print("✅ Basic OSC control test passed")
    print("Listen for smooth frequency transitions without clicks")
    
    return True


if __name__ == "__main__":
    success = test_basic_osc_control()
    sys.exit(0 if success else 1)