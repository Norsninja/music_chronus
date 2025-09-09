#!/usr/bin/env python3
"""
'Acid Dreams' - An original composition by Chronus Nexus
A psychedelic acid house journey with evolving patterns and filter sweeps
Using the new ChronusOSC wrapper for clean, error-free music creation
Duration: ~2.5 minutes
"""

from chronus_osc import ChronusOSC
import time
import random
import math

class AcidDreams:
    def __init__(self):
        self.osc = ChronusOSC()
        self.bpm = 120
        
    def setup(self):
        """Initialize all parameters"""
        print("=" * 50)
        print("  'ACID DREAMS' by Chronus Nexus")
        print("  A psychedelic journey through filter sweeps")
        print("=" * 50)
        print("\nInitializing dream state...")
        
        # Clear everything
        self.osc.seq_stop()
        self.osc.seq_clear()
        
        # Setup voice characteristics
        for voice in range(1, 5):
            self.osc.set_voice_amp(voice, 0.25)
            self.osc.set_voice_adsr(voice, 
                                   attack=0.01, 
                                   decay=0.1, 
                                   sustain=0.6, 
                                   release=0.3)
            self.osc.gate_voice(voice, False)
        
        # Initialize effects low
        self.osc.set_reverb(mix=0.1, room=0.2, damp=0.5)
        self.osc.set_delay(mix=0, time=0.375, feedback=0.2)
        self.osc.set_distortion(drive=0, mix=0, tone=0.5)
        
        # Setup acid filter for that 303 sound
        self.osc.set_acid_cutoff(150)
        self.osc.set_acid_res(0.2)
        self.osc.set_acid_env(500, decay=0.15)
        self.osc.set_acid_drive(0.1, mix=1.0)
        
        # LFOs ready but off
        self.osc.set_lfo(1, rate=0.125, depth=0)
        self.osc.set_lfo(2, rate=2.0, depth=0)
        
        time.sleep(1)
        
    def phase1_hypnotic_intro(self):
        """Bars 1-16: Hypnotic baseline"""
        print("\n[PHASE 1] Entering the dream... (16 bars)")
        
        # Hypnotic bassline with acid filter
        self.osc.seq_add_track('acid', 'voice2', 
                              'x...x...x.x.....', 
                              base_freq=110, 
                              filter_freq=200)
        
        # Subtle kick
        self.osc.seq_add_track('kick', 'voice1', 
                              '....X.......X...', 
                              base_freq=55,
                              filter_freq=80)
        
        self.osc.seq_bpm(self.bpm)
        self.osc.seq_start()
        
        # Gradually open the acid filter
        print("  Opening the acid filter...")
        for bar in range(16):
            # Sweep cutoff up and down
            cutoff = 200 + (300 * math.sin(bar * 0.4))
            self.osc.set_acid_cutoff(cutoff)
            
            # Increase resonance gradually
            res = 0.2 + (bar * 0.03)
            self.osc.set_acid_res(min(0.8, res))
            
            # Every 4 bars, change bass pattern slightly
            if bar % 4 == 0 and bar > 0:
                patterns = [
                    'x...x...x.x.....',
                    'x.x.....x...x...',
                    'x...x.x.x.......',
                    'x.....x.x...x...'
                ]
                self.osc.seq_update_pattern('acid', random.choice(patterns))
                
            time.sleep(2)  # 2 seconds per bar at 120 BPM
            
    def phase2_building_energy(self):
        """Bars 17-32: Building with percussion"""
        print("\n[PHASE 2] Energy rising... (16 bars)")
        
        # Add full kick pattern
        self.osc.seq_update_pattern('kick', 'X...X...X...X...')
        
        # Add crispy hi-hats
        self.osc.seq_add_track('hats', 'voice3',
                              '..x...x...x...x.',
                              base_freq=6000,
                              filter_freq=8000)
        
        # Setup voice3 for hi-hats
        self.osc.set_voice_adsr(3, attack=0.001, decay=0.02, release=0.05)
        self.osc.set_voice_amp(3, 0.15)
        
        # Add some reverb to hats
        self.osc.set_voice_sends(3, reverb=0.3, delay=0.1)
        
        # Start LFO on filter
        print("  Engaging filter modulation...")
        self.osc.set_lfo(1, rate=0.25, depth=0.4)
        
        for bar in range(16):
            # Modulate acid parameters
            self.osc.set_acid_env(1000 + (bar * 100), decay=0.15)
            
            # Halfway through, make hats busier
            if bar == 8:
                self.osc.seq_update_pattern('hats', 'x.x.x.x.x.x.x.x.')
                print("  Intensifying rhythm...")
                
            # Add some randomness to acid pattern
            if bar % 2 == 0:
                if random.random() > 0.5:
                    self.osc.seq_update_notes('acid', 'A2 A2 C3 A2 E3 A2 G2 A2')
                else:
                    self.osc.seq_update_notes('acid', 'A2 A2 A2 C3 E3 G3 A3 C3')
                    
            time.sleep(2)
            
    def phase3_acid_peak(self):
        """Bars 33-48: Full acid madness"""
        print("\n[PHASE 3] ACID PEAK! (16 bars)")
        
        # Maximum acid intensity
        self.osc.set_acid_res(0.92)
        self.osc.set_acid_env(3000, decay=0.1)
        self.osc.set_acid_drive(0.4, mix=1.0)
        
        # Add lead synth playing random acid notes
        self.osc.seq_add_track('lead', 'voice4',
                              '....X.......X...',
                              base_freq=440,
                              filter_freq=2000)
        
        # Voice4 setup for lead
        self.osc.set_voice_adsr(4, attack=0.005, decay=0.1, sustain=0.3, release=0.5)
        self.osc.set_voice_sends(4, reverb=0.4, delay=0.5)
        
        # Increase master effects
        self.osc.set_reverb(mix=0.3, room=0.5)
        self.osc.set_delay(mix=0.3, time=0.375, feedback=0.5)
        
        # Add distortion for grit
        self.osc.set_distortion(drive=0.3, mix=0.3, tone=0.7)
        
        # Wild patterns
        acid_patterns = [
            'XxXxXxXxXxXxXxXx',
            'X.X.X.X.X.X.X.X.',
            'XX..XX..XX..XX..',
            'X...X.X.X.X...X.'
        ]
        
        for bar in range(16):
            # Crazy filter sweeps
            sweep_speed = 0.5 + (bar * 0.1)
            cutoff = 800 + (1500 * math.sin(bar * sweep_speed))
            self.osc.set_acid_cutoff(cutoff)
            
            # Change patterns frequently
            if bar % 2 == 0:
                self.osc.seq_update_pattern('acid', random.choice(acid_patterns))
                
            # Modulate lead notes
            if bar % 4 == 0:
                lead_notes = [
                    'C4 E4 G4 C5',
                    'A3 C4 E4 A4', 
                    'F3 A3 C4 F4',
                    'G3 B3 D4 G4'
                ]
                self.osc.seq_update_notes('lead', random.choice(lead_notes))
                
            # Speed up halfway through
            if bar == 8:
                print("  Accelerating...")
                self.osc.seq_bpm(128)
                
            time.sleep(1.875 if bar >= 8 else 2)  # Adjust for BPM change
            
    def phase4_breakdown(self):
        """Bars 49-64: Trippy breakdown"""
        print("\n[PHASE 4] Psychedelic breakdown... (16 bars)")
        
        # Remove drums for space
        self.osc.seq_remove_track('kick')
        self.osc.seq_remove_track('hats')
        
        # Slow down
        self.osc.seq_bpm(110)
        
        # Reduce acid intensity
        self.osc.set_acid_res(0.5)
        self.osc.set_acid_drive(0.1, mix=0.5)
        
        # Maximum space effects
        self.osc.set_reverb(mix=0.6, room=0.8, damp=0.3)
        self.osc.set_delay(mix=0.5, time=0.5, feedback=0.7)
        
        # Tremolo on lead
        self.osc.set_lfo(2, rate=4.0, depth=0.6)
        
        # Reduce distortion
        self.osc.set_distortion(drive=0, mix=0)
        
        print("  Floating in space...")
        
        for bar in range(16):
            # Slow filter waves
            cutoff = 400 + (200 * math.sin(bar * 0.2))
            self.osc.set_acid_cutoff(cutoff)
            
            # Fade patterns in and out
            if bar % 4 == 0:
                if bar < 8:
                    self.osc.seq_update_pattern('acid', '....x.......x...')
                    self.osc.seq_update_pattern('lead', 'X...............')
                else:
                    self.osc.seq_update_pattern('acid', '................')
                    self.osc.seq_update_pattern('lead', '....X...........')
                    
            # Reduce volume gradually
            if bar >= 12:
                vol = 0.25 * (1 - ((bar - 12) / 4))
                self.osc.set_voice_amp(2, vol)
                self.osc.set_voice_amp(4, vol)
                
            time.sleep(2.18)  # Adjusted for 110 BPM
            
    def phase5_return_to_reality(self):
        """Bars 65-80: Return with a vengeance"""
        print("\n[PHASE 5] RETURN TO REALITY! (16 bars)")
        
        # Reset volumes
        self.osc.set_voice_amp(2, 0.3)
        self.osc.set_voice_amp(4, 0.25)
        
        # Bring back the energy
        self.osc.seq_bpm(125)
        
        # Full patterns
        self.osc.seq_add_track('kick', 'voice1', 'X.X.X.X.X.X.X.X.', base_freq=50)
        self.osc.seq_add_track('hats', 'voice3', 'xxxxxxxxxxxxxxxx', base_freq=8000)
        self.osc.seq_update_pattern('acid', 'XXXXXXXXXXXXXXXX')
        self.osc.seq_update_pattern('lead', 'X.X.X.X.X.X.X.X.')
        
        # Maximum acid again
        self.osc.set_acid_res(0.95)
        self.osc.set_acid_env(4000, decay=0.08)
        self.osc.set_acid_drive(0.5, mix=1.0)
        
        # Full distortion
        self.osc.set_distortion(drive=0.6, mix=0.5, tone=0.8)
        
        # Reduce reverb for punch
        self.osc.set_reverb(mix=0.2, room=0.3)
        self.osc.set_delay(mix=0.2, time=0.375, feedback=0.3)
        
        print("  MAXIMUM ENERGY!")
        
        for bar in range(16):
            # Wild filter modulation
            cutoff = 1000 + (1500 * abs(math.sin(bar * 0.8)))
            self.osc.set_acid_cutoff(cutoff)
            
            # Even more intense in last 4 bars
            if bar >= 12:
                self.osc.seq_update_pattern('kick', 'XXXXXXXXXXXXXXXX')
                self.osc.set_lfo(1, rate=8.0, depth=0.8)
                
            time.sleep(1.92)  # Adjusted for 125 BPM
            
    def outro(self):
        """Final fadeout"""
        print("\n[OUTRO] Wake up... (8 bars)")
        
        # Gradually remove elements
        elements = ['lead', 'hats', 'kick', 'acid']
        
        for i, element in enumerate(elements):
            print(f"  Fading {element}...")
            self.osc.seq_remove_track(element)
            
            # Increase reverb as elements disappear
            self.osc.set_reverb(mix=0.3 + (i * 0.15), room=0.5 + (i * 0.1))
            
            time.sleep(3.84)  # 2 bars each at 125 BPM
            
        # Stop everything
        self.osc.seq_stop()
        self.osc.seq_clear()
        
        # Final reverb tail
        self.osc.set_reverb(mix=0.8, room=0.95)
        time.sleep(4)
        
        print("\n" + "=" * 50)
        print("  Thank you for dreaming with 'Acid Dreams'")
        print("  The Chronus Pet should be exhausted!")
        print("=" * 50)
        
    def perform(self):
        """Perform the complete acid journey"""
        self.setup()
        
        print("\n[Starting in 3 seconds...]")
        time.sleep(3)
        
        # Full song structure
        self.phase1_hypnotic_intro()     # 16 bars - Setup the vibe
        self.phase2_building_energy()    # 16 bars - Add percussion
        self.phase3_acid_peak()          # 16 bars - Maximum intensity
        self.phase4_breakdown()          # 16 bars - Psychedelic space
        self.phase5_return_to_reality()  # 16 bars - Final assault
        self.outro()                     # 8 bars - Fade
        
        print("\nTotal duration: ~2.5 minutes")
        print("Genre: Acid House / Psychedelic Techno")
        

if __name__ == "__main__":
    song = AcidDreams()
    song.perform()