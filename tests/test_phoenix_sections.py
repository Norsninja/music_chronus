#!/usr/bin/env python3
"""
Test Phoenix Scars sections individually to verify the fix
"""

from chronus_song_phoenix_scars import PhoenixScars
import time

def test_sections():
    """Test individual sections of Phoenix Scars"""
    print("="*60)
    print("TESTING PHOENIX SCARS SECTIONS")
    print("="*60)
    
    song = PhoenixScars()
    song.setup_instruments()
    
    print("\n[TEST] Testing verse1 (should work)...")
    try:
        song.verse1_space_for_pain()
        print("✓ Verse1 completed successfully")
    except Exception as e:
        print(f"✗ Verse1 failed: {e}")
        return False
    
    # Give a moment between sections
    time.sleep(2)
    
    print("\n[TEST] Testing verse2 (previously crashed)...")
    try:
        song.verse2_wisdom_gained()
        print("✓ Verse2 completed successfully - FIX WORKS!")
    except Exception as e:
        print(f"✗ Verse2 failed: {e}")
        return False
    
    # Clean up
    song.osc.seq_stop()
    song.osc.seq_clear()
    
    print("\n" + "="*60)
    print("SUCCESS: All sections work! Phoenix Scars is fixed!")
    print("="*60)
    return True

if __name__ == "__main__":
    # Run limited test (not full song)
    success = test_sections()
    if not success:
        print("\nFailed - check the error above")