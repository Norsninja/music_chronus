#!/usr/bin/env python3
"""
Test script for audio engine v2 - runs for 10 seconds with periodic status
"""

import time
from audio_engine_v2 import AudioEngine

def test_audio_engine():
    print("=== Audio Engine 10-Second Test ===\n")
    
    engine = AudioEngine()
    
    # Start the engine
    print("Starting audio engine...")
    if not engine.start():
        print("Failed to start engine!")
        return
    
    print("You should hear a 440Hz tone now.\n")
    
    # Run for 10 seconds, checking status every 2 seconds
    for i in range(5):
        time.sleep(2)
        status = engine.get_status()
        print(f"[{(i+1)*2}s] Buffers: {status.total_buffers:5d}, "
              f"Underruns: {status.underrun_count:2d}, "
              f"Callback: {status.callback_mean_us:.3f}ms, "
              f"CPU: {status.cpu_percent:.1f}%")
    
    # Final detailed status
    print("\n=== Final Status ===")
    final_status = engine.get_status()
    print(final_status)
    
    # Check for success
    if final_status.underrun_count == 0:
        print("\n✅ SUCCESS: No underruns detected!")
    else:
        print(f"\n⚠️ WARNING: {final_status.underrun_count} underruns detected")
    
    # Stop the engine
    print("\nStopping audio engine...")
    engine.stop()
    
    print("\nTest complete!")


if __name__ == "__main__":
    test_audio_engine()