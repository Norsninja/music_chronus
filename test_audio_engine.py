#!/usr/bin/env python3
"""
Test script for audio engine - runs for 5 seconds then reports metrics
"""

import time
from audio_engine import AudioEngine

def test_audio_engine():
    print("=== Audio Engine 5-Second Test ===\n")
    
    engine = AudioEngine()
    
    # Start the engine
    print("Starting audio engine...")
    if not engine.start():
        print("Failed to start engine!")
        return
    
    print("You should hear a 440Hz tone now.\n")
    
    # Run for 5 seconds, checking status periodically
    for i in range(5):
        time.sleep(1)
        status = engine.get_status()
        print(f"[{i+1}s] Buffers: {status.total_buffers}, "
              f"Underruns: {status.underrun_count}, "
              f"Callback: {status.callback_mean_us:.3f}ms")
    
    # Final status
    print("\n=== Final Status ===")
    print(engine.get_status())
    
    # Stop the engine
    print("\nStopping audio engine...")
    engine.stop()
    
    print("\nTest complete!")


if __name__ == "__main__":
    test_audio_engine()