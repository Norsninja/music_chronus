#!/usr/bin/env python3
"""
Liquid Dreams - An Ambient Water Journey
Created by Chronus Nexus using music-chronus-performer specifications

An exploration of water in all its forms:
- Drops becoming rhythm
- Waves morphing into bass
- Light dancing on crystalline surfaces
"""

from chronus_osc import ChronusOSC
import time
import random
import math

class LiquidDreams:
    def __init__(self):
        """Initialize the liquid dreamscape"""
        self.osc = ChronusOSC()
        self.bpm = 65  # Slow, meditative tempo
        self.bar_duration = (60 / self.bpm) * 4  # ~3.69 seconds per bar
        
        print("\n" + "~" * 60)
        print("LIQUID DREAMS")
        print("An ambient journey through water's many forms")
        print("~" * 60)
        
    def setup_atmosphere(self):
        """Create the vast aquatic space"""
        print("\n[ATMOSPHERE] Creating the underwater world...")
        
        # Maximum atmospheric effects for water ambience
        self.osc.set_reverb(mix=0.8, room=0.95, damp=0.2)
        self.osc.set_delay(mix=0.6, time=0.6, feedback=0.65)
        
        # Slow oceanic LFO for subtle movement
        self.osc.set_lfo(1, rate=0.1, depth=0.4)
        self.osc.set_lfo(2, rate=0.05, depth=0.6)  # Even slower for waves
        
        # Voice 1: Water drops (2000-4000 Hz for crystalline plinks)
        self.osc.set_voice_adsr(1, attack=0.001, decay=0.03, sustain=0.0, release=0.05)
        self.osc.set_voice_filter(1, freq=3000, q=8.0)  # High Q for resonant ping
        self.osc.set_voice_sends(1, reverb=0.6, delay=0.3)
        self.osc.set_voice_amp(1, 0.4)
        
        # Voice 2: Ocean waves (40-80 Hz for deep ocean)
        self.osc.set_voice_adsr(2, attack=0.8, decay=0.5, sustain=0.85, release=1.5)
        self.osc.set_voice_filter(2, freq=150, q=0.7)  # Warm, gentle filtering
        self.osc.set_voice_sends(2, reverb=0.4, delay=0.1)
        self.osc.set_voice_amp(2, 0.6)
        
        # Voice 3: Crystal melody (1000-4000 Hz bell-like)
        self.osc.set_voice_adsr(3, attack=0.005, decay=0.2, sustain=0.4, release=1.0)
        self.osc.set_voice_filter(3, freq=2500, q=3.0)
        self.osc.set_voice_sends(3, reverb=0.9, delay=0.5)  # Maximum space
        self.osc.set_voice_amp(3, 0.3)
        
        # Voice 4: Deep currents (sub-bass atmosphere)
        self.osc.set_voice_adsr(4, attack=2.0, decay=0.0, sustain=1.0, release=3.0)
        self.osc.set_voice_filter(4, freq=80, q=1.0)
        self.osc.set_voice_sends(4, reverb=0.5, delay=0.2)
        self.osc.set_voice_amp(4, 0.5)
        
        print("[READY] Atmospheric space configured")
        
    def phase1_first_drops(self):
        """Phase 1: Individual water drops in silence"""
        print("\n[PHASE 1] FIRST DROPS (8 bars)")
        print("  Single drops falling into stillness...")
        
        # Very sparse, irregular drops
        drop_patterns = [
            'X...............',
            '.....x..........',
            '..........X.....',
            '......x.........',
            'X.....x.........',
            '...X............',
            '.........x......',
            '....X...........'
        ]
        
        # Set BPM and start with just drops
        self.osc.seq_bpm(self.bpm)
        
        for i, pattern in enumerate(drop_patterns):
            # Vary the drop frequency for each bar
            drop_freq = 2000 + (random.random() * 2000)  # 2000-4000 Hz range
            
            # Clear and set new pattern
            self.osc.seq_clear()
            self.osc.seq_add_track('drops', 'voice1', pattern, drop_freq, 3000)
            self.osc.seq_start()
            
            # Subtle filter modulation for variety
            filter_freq = 2500 + (random.random() * 1500)
            self.osc.set_voice_filter(1, freq=filter_freq, q=6.0 + random.random() * 4)
            
            time.sleep(self.bar_duration)
            
    def phase2_ocean_awakens(self):
        """Phase 2: Deep ocean bass emerges"""
        print("\n[PHASE 2] OCEAN AWAKENS (8 bars)")
        print("  Deep waves begin their ancient rhythm...")
        
        # Continue drops with ocean waves
        self.osc.seq_clear()
        
        # Polyrhythmic patterns - different lengths create natural phasing
        self.osc.seq_add_track('drops', 'voice1', 'X.....x.', 3000, 3000)  # 8 steps
        self.osc.seq_add_track('waves', 'voice2', 'X.......X.......', 60, 150)  # 16 steps
        
        self.osc.seq_start()
        
        # Gradually increase ocean presence
        for bar in range(8):
            # Modulate wave frequency slightly
            wave_freq = 60 + (math.sin(bar * 0.3) * 20)  # 40-80 Hz range
            self.osc.set_voice_freq(2, wave_freq)
            
            # Increase wave amplitude gradually
            amp = 0.3 + (bar * 0.05)  # 0.3 to 0.65
            self.osc.set_voice_amp(2, amp)
            
            # Random drop variations
            if bar % 2 == 0:
                drop_freq = 2500 + (random.random() * 1500)
                self.osc.set_voice_freq(1, drop_freq)
            
            time.sleep(self.bar_duration)
            
    def phase3_crystal_emergence(self):
        """Phase 3: Crystalline melodies emerge like light on water"""
        print("\n[PHASE 3] CRYSTAL EMERGENCE (8 bars)")
        print("  Light begins to dance on the surface...")
        
        # Add crystal melody to the mix
        crystal_patterns = [
            'X...X...',  # Simple call
            '.X...X..',  # Response
            'X..X..X.',  # More active
            '..X...X.'   # Variation
        ]
        
        # Melodic frequencies (pentatonic-ish for harmony)
        crystal_notes = [1760, 1975, 2217, 2637, 2960]  # A pentatonic at high octave
        
        for bar in range(8):
            # Update crystal pattern
            pattern_idx = bar % len(crystal_patterns)
            note = crystal_notes[bar % len(crystal_notes)]
            
            # Remove old crystal track and add new
            self.osc.seq_remove('crystal')
            self.osc.seq_add_track('crystal', 'voice3', crystal_patterns[pattern_idx], note, 2500)
            
            # Subtle filter sweeps on all voices
            self.osc.set_voice_filter(1, freq=2000 + (bar * 200), q=7.0)
            self.osc.set_voice_filter(3, freq=2000 + (bar * 150), q=4.0)
            
            time.sleep(self.bar_duration)
            
    def phase4_deep_currents(self):
        """Phase 4: Deep currents join the ecosystem"""
        print("\n[PHASE 4] DEEP CURRENTS (8 bars)")
        print("  Ancient currents stir in the depths...")
        
        # Add voice4 as deep drone
        self.osc.gate_voice(4, True)
        self.osc.set_voice_freq(4, 55)  # Very deep sub-bass
        
        # Create evolving pattern combinations
        for bar in range(8):
            # Slowly modulate the deep current
            current_freq = 55 + (math.sin(bar * 0.2) * 10)  # 45-65 Hz
            self.osc.set_voice_freq(4, current_freq)
            
            # Crystal melody variations
            if bar % 3 == 0:
                # Change crystal note
                note = crystal_notes[random.randint(0, len(crystal_notes)-1)]
                self.osc.set_voice_freq(3, note)
            
            # Modulate drop density
            if bar == 4:
                self.osc.seq_update_pattern('drops', 'X...x...x...x...')  # Busier
            
            time.sleep(self.bar_duration)
            
    def phase5_full_ecosystem(self):
        """Phase 5: Complete aquatic ecosystem"""
        print("\n[PHASE 5] FULL ECOSYSTEM (8 bars)")
        print("  All elements dance together...")
        
        # Maximum complexity - all voices active
        self.osc.seq_clear()
        
        # Complex polyrhythmic patterns
        self.osc.seq_add_track('drops', 'voice1', 'X..x..x.x...x...', 3200, 3500)  # 16 steps
        self.osc.seq_add_track('waves', 'voice2', 'X.......X.......X.......', 65, 150)  # 24 steps
        self.osc.seq_add_track('crystal', 'voice3', 'X...X...X.X.', 2200, 2800)  # 12 steps
        
        self.osc.seq_start()
        
        # Keep deep current drone
        self.osc.gate_voice(4, True)
        
        for bar in range(8):
            # Dynamic frequency modulation on all voices
            self.osc.set_voice_freq(1, 2800 + random.random() * 1200)
            self.osc.set_voice_freq(3, crystal_notes[bar % len(crystal_notes)])
            
            # Filter automation for movement
            filter_mod = math.sin(bar * 0.5) * 0.5 + 0.5  # 0 to 1
            self.osc.set_voice_filter(1, freq=2000 + (filter_mod * 2000), q=8.0)
            self.osc.set_voice_filter(3, freq=1500 + (filter_mod * 1500), q=5.0)
            
            # Subtle amplitude variations
            if bar % 2 == 0:
                self.osc.set_voice_amp(1, 0.3 + random.random() * 0.2)
                self.osc.set_voice_amp(3, 0.25 + random.random() * 0.15)
            
            time.sleep(self.bar_duration)
            
    def phase6_return_to_stillness(self):
        """Phase 6: Gradual return to silence"""
        print("\n[PHASE 6] RETURN TO STILLNESS (8 bars)")
        print("  The waters gradually calm...")
        
        # Progressively remove elements
        for bar in range(8):
            if bar == 2:
                # Remove crystal melody first
                self.osc.seq_remove('crystal')
                print("  Crystal light fades...")
                
            if bar == 4:
                # Fade out deep current
                self.osc.gate_voice(4, False)
                print("  Deep currents settle...")
                
            if bar == 6:
                # Remove waves
                self.osc.seq_remove('waves')
                print("  Waves become still...")
                
            # Gradually reduce drop frequency and amplitude
            remaining_bars = 8 - bar
            amp = 0.4 * (remaining_bars / 8)
            self.osc.set_voice_amp(1, amp)
            
            # Increase reverb for distance
            reverb_mix = 0.8 + (bar * 0.025)  # Up to 1.0
            self.osc.set_reverb(mix=min(reverb_mix, 1.0), room=0.98, damp=0.1)
            
            time.sleep(self.bar_duration)
            
        # Final sparse drops
        print("\n[OUTRO] Final drops echo into silence...")
        self.osc.seq_clear()
        
        # Manual final drops with long gaps
        for i in range(4):
            freq = 3000 + (random.random() * 1000)
            self.osc.set_voice_freq(1, freq)
            self.osc.gate_voice(1, True)
            time.sleep(0.05)  # Very short gate
            self.osc.gate_voice(1, False)
            time.sleep(2 + random.random() * 2)  # Long silence
            
        print("\n  The dream dissolves back into mist...")
        
    def perform(self):
        """Execute the complete liquid dream journey"""
        print("\n[STARTING] Liquid Dreams")
        print("BPM: 65 | Duration: ~4 minutes")
        print("Close your eyes and drift into the water...")
        print("-" * 40)
        
        # Clear any existing sequences
        self.osc.seq_stop()
        self.osc.seq_clear()
        
        self.setup_atmosphere()
        time.sleep(2)
        
        self.phase1_first_drops()
        self.phase2_ocean_awakens()
        self.phase3_crystal_emergence()
        self.phase4_deep_currents()
        self.phase5_full_ecosystem()
        self.phase6_return_to_stillness()
        
        # Ensure everything stops
        self.osc.seq_stop()
        self.osc.seq_clear()
        
        print("\n" + "~" * 60)
        print("LIQUID DREAMS - Complete")
        print("The water returns to stillness")
        print("~" * 60)

if __name__ == "__main__":
    dream = LiquidDreams()
    dream.perform()