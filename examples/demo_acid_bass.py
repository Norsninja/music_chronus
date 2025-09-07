#!/usr/bin/env python3
"""
Acid Bass Demo - TB-303 Style
Showcases the acid filter module with classic 303 patterns
Completely headless/autonomous - no user interaction
"""

import time
import random
from pythonosc import udp_client

class AcidBassDemo:
    """
    Autonomous acid bass demonstration
    Classic 303-style patterns at 125 BPM
    """
    
    def __init__(self, host="127.0.0.1", port=5005):
        """Initialize OSC client"""
        self.client = udp_client.SimpleUDPClient(host, port)
        self.bpm = 125
        self.step_time = 60.0 / self.bpm / 4  # 16th notes
        
        print("\n" + "="*60)
        print("ACID BASS DEMO - TB-303 STYLE")
        print("="*60)
        print(f"BPM: {self.bpm}")
        print("Duration: 90 seconds")
        print("Watch the filter sweep and accent patterns!")
        print("-"*60)
    
    def setup_voice(self):
        """Configure voice2 for bass frequencies"""
        # Use sawtooth-like settings on voice2
        self.client.send_message("/mod/voice2/amp", 0.5)
        self.client.send_message("/mod/voice2/filter/freq", 800)  # Let acid handle filtering
        self.client.send_message("/mod/voice2/filter/q", 1.0)
        
        # Fast envelope for punchy bass
        self.client.send_message("/mod/voice2/adsr/attack", 0.001)
        self.client.send_message("/mod/voice2/adsr/decay", 0.05)
        self.client.send_message("/mod/voice2/adsr/sustain", 0.3)
        self.client.send_message("/mod/voice2/adsr/release", 0.1)
        
        # Add some reverb and delay
        self.client.send_message("/mod/voice2/send/reverb", 0.1)
        self.client.send_message("/mod/voice2/send/delay", 0.15)
    
    def setup_acid(self):
        """Configure acid filter for classic 303 sound"""
        self.client.send_message("/mod/acid1/cutoff", 300)  # Low starting cutoff
        self.client.send_message("/mod/acid1/res", 0.65)  # Good resonance
        self.client.send_message("/mod/acid1/env_amount", 2500)  # Strong envelope
        self.client.send_message("/mod/acid1/decay", 0.25)  # Classic decay
        self.client.send_message("/mod/acid1/cutoff_offset", 600)  # Accent boost
        self.client.send_message("/mod/acid1/res_accent_boost", 0.25)  # More squelch on accent
        self.client.send_message("/mod/acid1/accent_decay", 0.08)  # Snappy accent
        self.client.send_message("/mod/acid1/drive", 0.3)  # Some grit
        self.client.send_message("/mod/acid1/mix", 1.0)  # Full wet
        self.client.send_message("/mod/acid1/vol_comp", 0.5)  # Resonance compensation
    
    def setup_effects(self):
        """Configure global effects for acid house vibe"""
        # Reverb - spacious warehouse feel
        self.client.send_message("/mod/reverb1/mix", 0.25)
        self.client.send_message("/mod/reverb1/room", 0.7)
        self.client.send_message("/mod/reverb1/damp", 0.3)
        
        # Delay - rhythmic echoes
        self.client.send_message("/mod/delay1/time", 0.375)  # Dotted 8th at 125 BPM
        self.client.send_message("/mod/delay1/feedback", 0.4)
        self.client.send_message("/mod/delay1/mix", 0.3)
    
    def play_pattern(self, notes, accents, repeats=4):
        """
        Play a 16-step pattern with accents
        
        Args:
            notes: List of 16 note values (MIDI notes or None for rest)
            accents: List of 16 boolean values for accent steps
            repeats: Number of times to repeat the pattern
        """
        for _ in range(repeats):
            for step in range(16):
                note = notes[step]
                accent = accents[step]
                
                if note is not None:
                    # Convert MIDI to frequency
                    freq = 440.0 * (2.0 ** ((note - 69) / 12.0))
                    
                    # Set accent before gate
                    if accent:
                        self.client.send_message("/mod/acid1/accent", 1.0)
                    else:
                        self.client.send_message("/mod/acid1/accent", 0.0)
                    
                    # Set frequency and trigger
                    self.client.send_message("/mod/voice2/freq", freq)
                    self.client.send_message("/gate/voice2", 1)
                    
                    # Short gate for 303 style
                    time.sleep(self.step_time * 0.5)
                    self.client.send_message("/gate/voice2", 0)
                    time.sleep(self.step_time * 0.5)
                else:
                    # Rest
                    time.sleep(self.step_time)
    
    def pattern_variations(self):
        """Play different acid patterns with parameter tweaks"""
        
        # Pattern 1: Classic acid riff (8 bars)
        print("\nPattern 1: Classic Acid Riff")
        notes1 = [
            36, None, 36, 36,  48, None, 36, None,
            36, None, 43, None, 48, 48, None, 36
        ]
        accents1 = [
            True, False, False, False, True, False, False, False,
            False, False, True, False, False, True, False, False
        ]
        self.play_pattern(notes1, accents1, repeats=8)
        
        # Pattern 2: Walking bassline with filter sweep (8 bars)
        print("Pattern 2: Walking Bass + Filter Sweep")
        notes2 = [
            36, 36, 39, 41,  43, 43, 41, 39,
            36, 36, 39, 41,  43, 48, 46, 43
        ]
        accents2 = [
            True, False, False, True, False, False, True, False,
            True, False, False, True, False, True, True, False
        ]
        
        # Gradually open filter
        for i in range(8):
            cutoff = 300 + (i * 200)  # 300 -> 1900
            self.client.send_message("/mod/acid1/cutoff", cutoff)
            self.play_pattern(notes2, accents2, repeats=1)
        
        # Pattern 3: Staccato acid stabs (8 bars)
        print("Pattern 3: Acid Stabs")
        self.client.send_message("/mod/acid1/decay", 0.12)  # Shorter decay
        self.client.send_message("/mod/acid1/res", 0.8)  # More resonance
        
        notes3 = [
            48, None, None, 48,  None, 48, None, None,
            43, None, 43, None,  48, None, 46, None
        ]
        accents3 = [
            True, False, False, True,  False, True, False, False,
            True, False, True, False,  True, False, True, False
        ]
        self.play_pattern(notes3, accents3, repeats=8)
        
        # Pattern 4: Slide-style pattern (8 bars)
        print("Pattern 4: Slide Pattern")
        self.client.send_message("/mod/acid1/decay", 0.35)  # Longer decay
        self.client.send_message("/mod/acid1/env_amount", 3500)  # More sweep
        
        notes4 = [
            36, 36, 38, 39,  41, 43, 41, 39,
            36, 38, 39, 41,  43, 46, 48, 46
        ]
        # Every other note accented for groove
        accents4 = [i % 2 == 0 for i in range(16)]
        self.play_pattern(notes4, accents4, repeats=8)
        
        # Pattern 5: Climax with resonance sweep (8 bars)
        print("Pattern 5: Climax!")
        self.client.send_message("/mod/acid1/drive", 0.5)  # More drive
        
        notes5 = notes1  # Back to pattern 1
        accents5 = [True if i % 3 == 0 else False for i in range(16)]  # Syncopated accents
        
        # Sweep resonance up
        for i in range(8):
            res = 0.65 + (i * 0.04)  # 0.65 -> 0.93
            self.client.send_message("/mod/acid1/res", res)
            self.play_pattern(notes5, accents5, repeats=1)
        
        # Cool down
        print("Cooling down...")
        self.client.send_message("/mod/acid1/res", 0.5)
        self.client.send_message("/mod/acid1/cutoff", 200)
        self.client.send_message("/mod/acid1/drive", 0.2)
        self.play_pattern(notes1, accents1, repeats=4)
    
    def run(self):
        """Run the complete acid bass demonstration"""
        try:
            print("\nInitializing...")
            time.sleep(1)
            
            # Setup everything
            self.setup_voice()
            self.setup_acid()
            self.setup_effects()
            
            print("Starting acid bass demo...\n")
            time.sleep(1)
            
            # Play the patterns
            self.pattern_variations()
            
            # Final notes
            print("\nEnding with filter close...")
            for i in range(4):
                cutoff = 500 - (i * 100)
                self.client.send_message("/mod/acid1/cutoff", cutoff)
                self.client.send_message("/mod/voice2/freq", 110)  # A2
                self.client.send_message("/gate/voice2", 1)
                time.sleep(0.25)
                self.client.send_message("/gate/voice2", 0)
                time.sleep(0.25)
            
            print("\nDemo complete!")
            print("="*60)
            
        except KeyboardInterrupt:
            print("\n\nDemo interrupted by user")
        except Exception as e:
            print(f"\nError during demo: {e}")


if __name__ == "__main__":
    # Create and run demo
    demo = AcidBassDemo()
    
    print("\nMake sure engine_pyo.py is running first!")
    print("Press Ctrl+C to stop the demo\n")
    
    # Wait a moment for user to read
    time.sleep(3)
    
    # Run the demo
    demo.run()