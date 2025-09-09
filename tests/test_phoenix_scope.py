#!/usr/bin/env python3
"""
Test to verify the variable scope issue in Phoenix Scars
"""

from chronus_osc import ChronusOSC
import time
import traceback

class TestPhoenixScope:
    def __init__(self):
        self.osc = ChronusOSC()
        self.bar_duration = 2  # 2 seconds per bar at 120 BPM
        
    def verse1_defines_local(self):
        """This simulates verse1 with LOCAL variable"""
        print("Verse 1: Defining bass_progression locally")
        
        # Define bass_progression as LOCAL variable (the bug)
        bass_progression = [82.4, 82.4, 110.0, 110.0, 130.8, 130.8, 146.8, 146.8]
        
        # Use it successfully in this method
        for i in range(2):  # Just 2 iterations for test
            freq = bass_progression[i % 8]
            print(f"  Setting frequency in verse1: {freq}")
            self.osc.set_voice_freq(2, freq)
            time.sleep(0.5)
            
    def verse2_references_undefined(self):
        """This simulates verse2 trying to access undefined variable"""
        print("\nVerse 2: Trying to access bass_progression")
        
        try:
            # This should crash with NameError
            for bar in range(2):
                freq = bass_progression[bar % 8]  # Line 225 equivalent
                print(f"  Setting frequency in verse2: {freq}")
                self.osc.set_voice_freq(2, freq)
                time.sleep(0.5)
        except NameError as e:
            print(f"\n❌ CRASH! NameError: {e}")
            print("  This is exactly what happens in Phoenix Scars at line 225!")
            traceback.print_exc()
            return False
        return True
        
    def test_scope_issue(self):
        """Run the test to demonstrate the scope problem"""
        print("="*60)
        print("TESTING PHOENIX SCARS VARIABLE SCOPE ISSUE")
        print("="*60)
        
        # Setup
        self.osc.seq_stop()
        self.osc.seq_clear()
        self.osc.set_voice_amp(2, 0.2)
        
        # Run verse1 (works fine)
        self.verse1_defines_local()
        
        # Try to run verse2 (should crash)
        success = self.verse2_references_undefined()
        
        if not success:
            print("\n" + "="*60)
            print("CONFIRMED: Variable scope issue reproduced!")
            print("Solution: Define bass_progression as self.bass_progression")
            print("="*60)
            
        # Cleanup
        self.osc.seq_stop()
        self.osc.seq_clear()

if __name__ == "__main__":
    test = TestPhoenixScope()
    test.test_scope_issue()