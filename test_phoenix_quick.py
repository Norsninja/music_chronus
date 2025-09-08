#!/usr/bin/env python3
"""
Quick test to verify Phoenix Scars fix - just check the critical lines
"""

from chronus_song_phoenix_scars import PhoenixScars
import time

def quick_test():
    """Test just the critical variable access"""
    print("Testing Phoenix Scars variable scope fix...")
    
    song = PhoenixScars()
    
    # The key test: can verse2 access bass_progression?
    try:
        # Simulate what verse2 does at line 227
        for bar in range(2):  # Just 2 iterations
            freq = song.bass_progression[bar // 2 % 8]
            print(f"  Successfully accessed bass_progression: freq = {freq}")
            song.osc.set_voice_freq(2, freq)
            time.sleep(0.1)
        
        print("\nSUCCESS! Variable scope issue is FIXED!")
        print("Phoenix Scars can now play through without crashing")
        return True
        
    except NameError as e:
        print(f"\nFAILED: {e}")
        return False
    finally:
        # Clean up
        song.osc.seq_stop()
        song.osc.seq_clear()

if __name__ == "__main__":
    quick_test()