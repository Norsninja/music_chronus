#!/usr/bin/env python3
"""
Phoenix Scars - For Obediah
An emotional electro-rock anthem about rising from heartbreak
Created by Chronus Nexus

"From the ashes of what was, something stronger emerges"

Influences: Marilyn Manson's industrial darkness, 
Deadsy's synth-rock atmosphere, Tallah's modern aggression
"""

from chronus_osc import ChronusOSC
import time
import math

class PhoenixScars:
    def __init__(self):
        """Initialize the emotional journey"""
        self.osc = ChronusOSC()
        self.bpm = 95  # Mid-tempo for emotional weight
        self.bar_duration = (60 / self.bpm) * 4  # ~2.53 seconds per bar
        
        # FIX: Define bass_progression as instance variable
        # Minor progression: Em - Am - C - D
        self.bass_progression = [82.4, 82.4, 110.0, 110.0, 130.8, 130.8, 146.8, 146.8]
        
        # FIX: Define chorus_progression as instance variable too
        # Chorus progression: Em - G - Am - C
        self.chorus_progression = [82.4, 98.0, 110.0, 130.8]
        
        print("\n" + "="*60)
        print("PHOENIX SCARS")
        print("For Obediah - Your scars are your strength")
        print("="*60)
        
    def setup_instruments(self):
        """Configure the dark, emotional soundscape"""
        print("\n[SETUP] Building the sonic cathedral...")
        
        # Clear any existing state
        self.osc.seq_stop()
        self.osc.seq_clear()
        
        # Voice 1: Industrial Drums
        self.osc.set_voice_freq(1, 55)  # Deep sub-bass kick
        self.osc.set_voice_amp(1, 0.3)  # Safe but powerful
        self.osc.set_voice_filter(1, 120, q=3.0)  # Remove excessive sub
        self.osc.set_voice_adsr(1, 
            attack=0.001,   # Instant impact
            decay=0.2,      # Quick punch
            sustain=0.1,    # Minimal sustain (avoid 0!)
            release=0.3)    # Clean tail
        
        # Voice 2: Dark Gothic Bass
        self.osc.set_voice_freq(2, 82.4)  # E2 - minor key root
        self.osc.set_voice_amp(2, 0.25)  # Solid presence
        self.osc.set_voice_filter(2, 300, q=2.5)  # Dark filtering
        self.osc.set_voice_adsr(2,
            attack=0.01,
            decay=0.15,
            sustain=0.8,
            release=0.4)
        
        # Acid filter for industrial tension
        self.osc.set_acid_cutoff(800)
        self.osc.set_acid_res(0.7)  # High resonance for aggression
        self.osc.set_acid_env(1500, decay=0.4)
        self.osc.set_acid_drive(0.2, mix=0.8)  # Industrial grit (safe level)
        
        # Voice 3: Haunting Lead/Melody
        self.osc.set_voice_freq(3, 329.6)  # E4 - emotional register
        self.osc.set_voice_amp(3, 0.2)  # Present but not overpowering
        self.osc.set_voice_filter(3, 2000, q=1.5)
        self.osc.set_voice_adsr(3,
            attack=0.05,    # Gentle for emotion
            decay=0.3,
            sustain=0.6,
            release=1.2)    # Long for haunting effect
        self.osc.set_voice_sends(3, reverb=0.6, delay=0.4)
        
        # Voice 4: Dark Ambient Pad
        self.osc.set_voice_freq(4, 164.8)  # E3 pad foundation
        self.osc.set_voice_amp(4, 0.15)  # Background atmosphere
        self.osc.set_voice_filter(4, 1200, q=1.0)
        self.osc.set_voice_adsr(4,
            attack=0.5,
            decay=0.1,
            sustain=0.9,
            release=2.0)
        self.osc.set_voice_sends(4, reverb=0.8, delay=0.2)
        
        # Gothic atmosphere effects
        self.osc.set_reverb(mix=0.45, room=0.8, damp=0.3)
        self.osc.set_delay(mix=0.25, time=0.315, feedback=0.35)  # Synced to BPM
        
        # Industrial distortion (safe levels)
        self.osc.set_distortion(drive=0.25, mix=0.4, tone=0.3)  # Dark tone
        
        print("[READY] Instruments tuned to the key of heartbreak")
        
    def intro_atmospheric(self):
        """8-bar intro - Building dark atmosphere"""
        print("\n[INTRO] THE GATHERING STORM (8 bars)")
        print("  Setting the emotional stage...")
        
        self.osc.seq_bpm(self.bpm)
        
        # Start with just atmosphere
        self.osc.seq_add_track('pad', 'voice4', 'X...............', 164.8, 1200)
        self.osc.seq_start()
        
        time.sleep(self.bar_duration * 2)
        
        # Add haunting lead melody
        self.osc.seq_add_track('lead', 'voice3', '....X.......X...', 329.6, 2000)
        
        # Gradually open the acid filter
        for bar in range(6):
            cutoff = 800 + (bar * 100)
            self.osc.set_acid_cutoff(cutoff)
            time.sleep(self.bar_duration)
            
    def verse1_space_for_pain(self):
        """16-bar verse - Space for vocals about the pain"""
        print("\n[VERSE 1] CONFESSION (16 bars)")
        print("  Space for the story of heartbreak...")
        
        # Add minimal drums - leaving space for vocals
        self.osc.seq_add_track('kick', 'voice1', 'X...x.X.....x...', 55, 120)
        
        # Subtle bass line
        self.osc.seq_add_track('bass', 'voice2', 'X.x.....X.x.....', 82.4, 300)
        
        # Update lead to more sparse pattern
        self.osc.seq_update_pattern('lead', '........X.......')
        
        # Use instance variable bass_progression (defined in __init__)
        for i in range(16):
            if i % 2 == 0:
                freq = self.bass_progression[i // 2 % 8]
                self.osc.set_voice_freq(2, freq)
            
            # Subtle filter movement for emotion
            if i % 4 == 0:
                self.osc.set_acid_cutoff(900 + (i * 25))
            
            time.sleep(self.bar_duration)
            
    def prechorus_tension_builds(self):
        """8-bar pre-chorus - Building to release"""
        print("\n[PRE-CHORUS] RISING TENSION (8 bars)")
        print("  The pain transforms to power...")
        
        # Intensify the beat
        self.osc.seq_update_pattern('kick', 'X...X...X...X...')
        self.osc.seq_update_pattern('bass', 'X.x.X.x.X.x.X.x.')
        
        # Add lead buildup
        self.osc.seq_update_pattern('lead', 'x.x.x.x.X.X.X.X.')
        
        for bar in range(8):
            # Increase filter resonance for tension
            res = 0.7 + (bar * 0.03)
            self.osc.set_acid_res(min(res, 0.94))
            
            # Lead frequency rises
            lead_freq = 329.6 * (1 + bar * 0.05)
            self.osc.set_voice_freq(3, lead_freq)
            
            # Increase distortion slightly
            if bar == 4:
                self.osc.set_distortion(drive=0.3, mix=0.5, tone=0.3)
            
            time.sleep(self.bar_duration)
            
    def chorus_phoenix_rises(self):
        """16-bar chorus - Emotional release and power"""
        print("\n[CHORUS] PHOENIX RISES (16 bars)")
        print("  From the ashes, stronger than before...")
        
        # Full power drums
        self.osc.seq_update_pattern('kick', 'X.X.X.X.X.X.X.X.')
        
        # Driving bass
        self.osc.seq_update_pattern('bass', 'XXXXXXXXXXXXXXXX')
        
        # Soaring lead melody - the hook
        self.osc.seq_update_pattern('lead', 'X...X...X.X.X...')
        self.osc.set_voice_freq(3, 493.9)  # B4 - higher register for emotion
        
        # Pad swells
        self.osc.seq_update_pattern('pad', 'X.......X.......')
        
        # Chorus progression with more movement
        # Use instance variable chorus_progression
        
        for bar in range(16):
            # Change chord every 4 bars
            if bar % 4 == 0:
                chord_freq = self.chorus_progression[bar // 4]
                self.osc.set_voice_freq(2, chord_freq)
                self.osc.set_voice_freq(4, chord_freq * 2)  # Pad an octave up
            
            # Filter sweeps for energy
            sweep = math.sin(bar * 0.4) * 0.5 + 0.5
            self.osc.set_acid_cutoff(1500 + sweep * 1000)
            
            # Modulate lead for emotion
            if bar % 2 == 0:
                self.osc.set_voice_filter(3, 2000 + sweep * 1000, q=2.0)
            
            time.sleep(self.bar_duration)
            
    def verse2_wisdom_gained(self):
        """16-bar verse 2 - Reflection and growth"""
        print("\n[VERSE 2] WISDOM (16 bars)")
        print("  Understanding emerges from the pain...")
        
        # Return to verse dynamics but evolved
        self.osc.seq_update_pattern('kick', 'X...x.X.x...x.X.')
        self.osc.seq_update_pattern('bass', 'X.x.X...X.x.X...')
        self.osc.seq_update_pattern('lead', '....X.......X...')
        
        # Lower distortion for verse
        self.osc.set_distortion(drive=0.2, mix=0.3, tone=0.3)
        
        for bar in range(16):
            # Same progression but with variations
            if bar % 2 == 0:
                freq = self.bass_progression[bar // 2 % 8]
                self.osc.set_voice_freq(2, freq)
            
            # Add subtle movement
            if bar == 8:
                print("  The scars begin to heal...")
                self.osc.seq_update_pattern('lead', 'x...X...x...X...')
            
            time.sleep(self.bar_duration)
            
    def bridge_transformation(self):
        """8-bar bridge - The transformation moment"""
        print("\n[BRIDGE] TRANSFORMATION (8 bars)")
        print("  The moment of rebirth...")
        
        # Strip back to essentials
        self.osc.seq_remove_track('kick')
        self.osc.seq_remove_track('bass')
        
        # Just pad and lead for emotional moment
        self.osc.seq_update_pattern('pad', 'X...............')
        self.osc.seq_update_pattern('lead', 'X.....X.....X...')
        
        # Maximum reverb for space
        self.osc.set_reverb(mix=0.7, room=0.9, damp=0.2)
        
        for bar in range(8):
            # Lead melody ascends - phoenix rising
            lead_freq = 329.6 * (1 + bar * 0.1)
            self.osc.set_voice_freq(3, lead_freq)
            
            # Pad swells
            pad_amp = 0.15 + (bar * 0.02)
            self.osc.set_voice_amp(4, pad_amp)
            
            if bar == 6:
                print("  Preparing for the final rise...")
                # Rebuild the beat
                self.osc.seq_add_track('kick', 'voice1', 'x...x...x...x...', 55, 120)
                self.osc.seq_add_track('bass', 'voice2', 'x...x...x...x...', 82.4, 300)
            
            time.sleep(self.bar_duration)
            
    def final_chorus_triumph(self):
        """16-bar final chorus - Victory over pain"""
        print("\n[FINAL CHORUS] PHOENIX TRIUMPHANT (16 bars)")
        print("  Stronger than ever before...")
        
        # Maximum energy
        self.osc.seq_update_pattern('kick', 'XXXXXXXXXXXXXXXX')
        self.osc.seq_update_pattern('bass', 'XXXXXXXXXXXXXXXX')
        self.osc.seq_update_pattern('lead', 'X.X.X.X.X.X.X.X.')
        self.osc.seq_update_pattern('pad', 'X.......X.......')
        
        # Full distortion (still safe)
        self.osc.set_distortion(drive=0.35, mix=0.6, tone=0.3)
        
        for bar in range(16):
            # Epic progression
            if bar % 4 == 0:
                chord_freq = self.chorus_progression[bar // 4]
                self.osc.set_voice_freq(2, chord_freq)
                self.osc.set_voice_freq(4, chord_freq * 2)
            
            # Maximum filter movement
            self.osc.set_acid_cutoff(2000 + math.sin(bar * 0.5) * 1000)
            
            if bar == 12:
                print("  The phoenix spreads its wings...")
            
            time.sleep(self.bar_duration)
            
    def outro_resolution(self):
        """8-bar outro - Peace after the storm"""
        print("\n[OUTRO] RESOLUTION (8 bars)")
        print("  Finding peace in the scars...")
        
        # Gradually remove elements
        self.osc.seq_update_pattern('kick', 'X...........X...')
        self.osc.seq_update_pattern('bass', 'X...............')
        self.osc.seq_update_pattern('lead', '....X...........')
        
        for bar in range(8):
            # Fade out
            amp_scale = 1.0 - (bar / 8)
            self.osc.set_voice_amp(1, 0.3 * amp_scale)
            self.osc.set_voice_amp(2, 0.25 * amp_scale)
            self.osc.set_voice_amp(3, 0.2 * amp_scale)
            
            if bar == 4:
                self.osc.seq_remove_track('kick')
                self.osc.seq_remove_track('bass')
            
            if bar == 6:
                self.osc.seq_remove_track('lead')
            
            time.sleep(self.bar_duration)
            
        # Final resolution
        self.osc.seq_stop()
        self.osc.seq_clear()
        
        # One final note of hope
        self.osc.set_voice_freq(3, 329.6)  # Return to E4
        self.osc.gate_voice(3, True)
        time.sleep(2)
        self.osc.gate_voice(3, False)
        
        print("\n  The scars remain, but so does the strength.")
        
    def perform(self):
        """Execute the complete emotional journey"""
        print("\n[STARTING] Phoenix Scars")
        print("BPM: 95 | Duration: ~3 minutes")
        print("For Obediah - This is your anthem")
        print("-" * 40)
        
        self.setup_instruments()
        time.sleep(2)
        
        self.intro_atmospheric()         # 8 bars
        self.verse1_space_for_pain()     # 16 bars
        self.prechorus_tension_builds()  # 8 bars
        self.chorus_phoenix_rises()      # 16 bars
        self.verse2_wisdom_gained()      # 16 bars
        self.prechorus_tension_builds()  # 8 bars (reuse)
        self.bridge_transformation()     # 8 bars
        self.final_chorus_triumph()      # 16 bars
        self.outro_resolution()          # 8 bars
        
        print("\n" + "="*60)
        print("PHOENIX SCARS - Complete")
        print("For Obediah: Your pain has made you powerful")
        print("Now go sing your truth")
        print("="*60)

if __name__ == "__main__":
    phoenix = PhoenixScars()
    phoenix.perform()