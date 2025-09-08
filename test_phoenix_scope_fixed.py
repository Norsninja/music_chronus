#!/usr/bin/env python3
"""
Test demonstrating the FIX for the variable scope issue
"""

from chronus_osc import ChronusOSC
import time

class TestPhoenixFixed:
    def __init__(self):
        self.osc = ChronusOSC()
        self.bar_duration = 2  # 2 seconds per bar at 120 BPM
        
        # FIX: Define bass_progression as INSTANCE variable
        self.bass_progression = [82.4, 82.4, 110.0, 110.0, 130.8, 130.8, 146.8, 146.8]
        
    def verse1_uses_instance(self):
        """Verse1 now uses self.bass_progression"""
        print("Verse 1: Using self.bass_progression")
        
        # Use INSTANCE variable
        for i in range(2):  # Just 2 iterations for test
            freq = self.bass_progression[i % 8]  # Using self.
            print(f"  Setting frequency in verse1: {freq}")
            self.osc.set_voice_freq(2, freq)
            time.sleep(0.5)
            
    def verse2_also_uses_instance(self):
        """Verse2 can now access self.bass_progression"""
        print("\nVerse 2: Also using self.bass_progression")
        
        # Now this works!
        for bar in range(2):
            freq = self.bass_progression[bar % 8]  # Using self.
            print(f"  Setting frequency in verse2: {freq}")
            self.osc.set_voice_freq(2, freq)
            time.sleep(0.5)
            
        print("\nSUCCESS! No crash - instance variable accessible across methods")
        return True
        
    def test_fixed_scope(self):
        """Run the test with the fix"""
        print("="*60)
        print("TESTING PHOENIX SCARS WITH FIX")
        print("="*60)
        
        # Setup
        self.osc.seq_stop()
        self.osc.seq_clear()
        self.osc.set_voice_amp(2, 0.2)
        
        # Run verse1 (works)
        self.verse1_uses_instance()
        
        # Run verse2 (now also works!)
        success = self.verse2_also_uses_instance()
        
        if success:
            print("\n" + "="*60)
            print("FIX VERIFIED: Using self.bass_progression works!")
            print("Solution: Define shared data as instance variables in __init__")
            print("="*60)
            
        # Cleanup
        self.osc.seq_stop()
        self.osc.seq_clear()

if __name__ == "__main__":
    test = TestPhoenixFixed()
    test.test_fixed_scope()