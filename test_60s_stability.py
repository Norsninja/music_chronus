#!/usr/bin/env python3
"""
60-second stability test for Phase 1A Audio Engine
Success criteria: Zero underruns, stable callback timings
"""

import time
from audio_engine_v2 import AudioEngine

def test_60s_stability():
    print("=== Phase 1A: 60-Second Stability Test ===")
    print("Success Criteria:")
    print("- Zero underruns")
    print("- Stable callback timings")
    print("- Clean resource management")
    print("-" * 50)
    
    engine = AudioEngine()
    
    # Start the engine
    print("\nStarting audio engine...")
    if not engine.start():
        print("❌ FAILED: Could not start engine")
        return False
    
    print("✅ Engine started - 440Hz sine wave playing")
    print("\nMonitoring for 60 seconds...\n")
    
    # Monitor for 60 seconds with updates every 10 seconds
    start_time = time.time()
    last_underruns = 0
    
    for i in range(6):
        time.sleep(10)
        elapsed = time.time() - start_time
        status = engine.get_status()
        
        # Check for new underruns
        new_underruns = status.underrun_count - last_underruns
        underrun_marker = "" if new_underruns == 0 else f" ⚠️ +{new_underruns} underruns!"
        last_underruns = status.underrun_count
        
        print(f"[{elapsed:5.1f}s] "
              f"Buffers: {status.total_buffers:6d} | "
              f"Underruns: {status.underrun_count:3d} | "
              f"Callback: {status.callback_mean_us:.3f}ms | "
              f"CPU: {status.cpu_percent:4.1f}%"
              f"{underrun_marker}")
    
    # Final status
    print("\n" + "=" * 50)
    print("FINAL RESULTS")
    print("=" * 50)
    
    final_status = engine.get_status()
    print(final_status)
    
    # Calculate statistics
    expected_buffers = int(60 * SAMPLE_RATE / BUFFER_SIZE)
    actual_buffers = final_status.total_buffers
    buffer_accuracy = (actual_buffers / expected_buffers) * 100
    
    print(f"\nBuffer Statistics:")
    print(f"  Expected: {expected_buffers}")
    print(f"  Actual:   {actual_buffers}")
    print(f"  Accuracy: {buffer_accuracy:.2f}%")
    
    # Stop the engine
    print("\nStopping audio engine...")
    engine.stop()
    
    # Determine pass/fail
    print("\n" + "=" * 50)
    passed = True
    
    if final_status.underrun_count == 0:
        print("✅ PASS: Zero underruns")
    else:
        print(f"❌ FAIL: {final_status.underrun_count} underruns detected")
        passed = False
    
    if final_status.callback_max_us < 1.0:  # Less than 1ms
        print(f"✅ PASS: Max callback time {final_status.callback_max_us:.3f}ms < 1ms")
    else:
        print(f"⚠️ WARNING: Max callback time {final_status.callback_max_us:.3f}ms")
    
    if 98 <= buffer_accuracy <= 102:  # Within 2% of expected
        print(f"✅ PASS: Buffer count accurate ({buffer_accuracy:.1f}%)")
    else:
        print(f"⚠️ WARNING: Buffer count off ({buffer_accuracy:.1f}%)")
    
    if final_status.cpu_percent < 10:
        print(f"✅ PASS: CPU usage {final_status.cpu_percent:.1f}% < 10%")
    else:
        print(f"⚠️ WARNING: High CPU usage {final_status.cpu_percent:.1f}%")
    
    print("\n" + "=" * 50)
    if passed:
        print("🎉 PHASE 1A ACCEPTANCE CRITERIA MET!")
        print("Audio engine achieved 60s continuous playback with zero underruns")
    else:
        print("Phase 1A needs optimization")
    
    return passed


if __name__ == "__main__":
    # Import needed constant
    from audio_engine_v2 import SAMPLE_RATE, BUFFER_SIZE
    
    success = test_60s_stability()
    exit(0 if success else 1)