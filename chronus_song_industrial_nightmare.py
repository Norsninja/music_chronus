#!/usr/bin/env python3
"""
'Industrial Nightmare' - An original composition by Chronus Nexus
Dark, heavy, distorted techno with aggressive acid lines
Maximum distortion, minimal mercy
Duration: ~3 minutes
"""

from chronus_osc import ChronusOSC
import time
import random
import math

class IndustrialNightmare:
    def __init__(self):
        self.osc = ChronusOSC()
        self.bpm = 135  # Driving tempo
        
    def setup_darkness(self):
        """Initialize for maximum darkness and aggression"""
        print("=" * 60)
        print("  'INDUSTRIAL NIGHTMARE' by Chronus Nexus")
        print("  WARNING: EXTREME DISTORTION AND AGGRESSIVE SOUNDS")
        print("=" * 60)
        print("\nInitializing the machinery...")
        
        # Clear and reset
        self.osc.seq_stop()
        self.osc.seq_clear()
        
        # Setup voices for industrial sound
        for voice in range(1, 5):
            self.osc.set_voice_amp(voice, 0.2)  # Lower initial volume due to distortion
            self.osc.gate_voice(voice, False)
        
        # Voice1: Sub bass kick
        self.osc.set_voice_adsr(1, attack=0.001, decay=0.08, sustain=0.2, release=0.05)
        self.osc.set_voice_filter(1, freq=80, q=4.0)
        
        # Voice2: Acid bass (will be heavily distorted)
        self.osc.set_voice_adsr(2, attack=0.005, decay=0.15, sustain=0.4, release=0.1)
        
        # Voice3: Metallic percussion
        self.osc.set_voice_adsr(3, attack=0.001, decay=0.01, sustain=0.0, release=0.02)
        self.osc.set_voice_filter(3, freq=8000, q=1.0)
        
        # Voice4: Industrial stabs
        self.osc.set_voice_adsr(4, attack=0.001, decay=0.05, sustain=0.1, release=0.05)
        
        # Setup acid filter for MAXIMUM SAFE aggression
        self.osc.set_acid_cutoff(150)  # Start very low
        self.osc.set_acid_res(0.75)    # High but safe resonance
        self.osc.set_acid_env(800, decay=0.08)  # Sharp, aggressive envelope
        self.osc.set_acid_drive(0.5, mix=0.9)   # Heavy but not maxed
        
        # Master distortion - start with some grit
        self.osc.set_distortion(drive=0.2, mix=0.2, tone=0.2)  # Dark tone
        
        # Minimal space effects for industrial dryness
        self.osc.set_reverb(mix=0.05, room=0.1, damp=0.9)
        self.osc.set_delay(mix=0.1, time=0.125, feedback=0.2)  # Short metallic delays
        
        # LFOs for modulation chaos
        self.osc.set_lfo(1, rate=0.1, depth=0)  # Slow sweep, off initially
        self.osc.set_lfo(2, rate=8.0, depth=0)   # Fast tremolo, off initially
        
        time.sleep(1)
        print("Machinery online. Initiating nightmare sequence...")
        
    def phase1_factory_floor(self):
        """Bars 1-16: Industrial foundation"""
        print("\n[PHASE 1] THE FACTORY FLOOR (16 bars)")
        print("  Establishing industrial atmosphere...")
        
        # Heavy distorted kick
        self.osc.seq_add_track('kick', 'voice1', 
                              'X...X...X...X...',
                              base_freq=45,  # Sub bass frequency
                              filter_freq=60)
        
        # Start with broken rhythm
        self.osc.seq_bpm(self.bpm)
        self.osc.seq_start()
        
        # Gradually increase distortion
        for bar in range(16):
            # Increase master distortion
            drive = 0.3 + (bar * 0.02)
            self.osc.set_distortion(drive=drive, mix=0.3 + (bar * 0.01))
            
            # Every 4 bars, make kick pattern more complex
            if bar % 4 == 0 and bar > 0:
                patterns = [
                    'X...X...X..XX...',
                    'X..X.X....X.X...',
                    'X...X...X...X.X.',
                    'X.X.X...X...X...'
                ]
                self.osc.seq_update_pattern('kick', patterns[bar // 4 - 1])
                print(f"  Pattern mutation {bar // 4}")
                
            # Add metallic hits halfway
            if bar == 8:
                self.osc.seq_add_track('metal', 'voice3',
                                      '....x.......x...',
                                      base_freq=8000,
                                      filter_freq=10000)
                self.osc.set_voice_amp(3, 0.1)
                print("  Metallic percussion engaged")
                
            time.sleep(1.78)  # Adjusted for 135 BPM
            
    def phase2_acid_injection(self):
        """Bars 17-32: Acid enters with maximum aggression"""
        print("\n[PHASE 2] ACID INJECTION (16 bars)")
        print("  Injecting corrosive acid line...")
        
        # Aggressive acid pattern
        self.osc.seq_add_track('acid', 'voice2',
                              'x.x.x...x.x.....',
                              base_freq=55,  # One octave above kick
                              filter_freq=200)
        
        # Increase acid parameters (but keep safe)
        self.osc.set_acid_res(0.85)  # High but not self-oscillating
        self.osc.set_acid_drive(0.6, mix=0.9)
        
        # More aggressive kick
        self.osc.seq_update_pattern('kick', 'X...X...X...X...')
        
        for bar in range(16):
            # Modulate acid cutoff aggressively
            if bar % 2 == 0:
                cutoff = 150 + random.randint(0, 300)
                self.osc.set_acid_cutoff(cutoff)
            else:
                cutoff = 400 + random.randint(0, 600)
                self.osc.set_acid_cutoff(cutoff)
                
            # Increase envelope modulation
            env = 1000 + (bar * 150)
            self.osc.set_acid_env(env, decay=0.08)
            
            # Change acid pattern for variation
            if bar % 4 == 2:
                acid_patterns = [
                    'X.X.X.X.........',
                    'x...x...x...x...',
                    'xxXxxxXxxxXxxxXx',
                    'X...X.X.X.X.....'
                ]
                self.osc.seq_update_pattern('acid', random.choice(acid_patterns))
                
            # Halfway through, add industrial stabs
            if bar == 8:
                self.osc.seq_add_track('stab', 'voice4',
                                      '....X.......X...',
                                      base_freq=110,
                                      filter_freq=500)
                self.osc.set_voice_sends(4, reverb=0.2, delay=0.3)
                print("  Industrial stabs online")
                
            time.sleep(1.78)
            
    def phase3_machinery_breakdown(self):
        """Bars 33-48: System malfunction"""
        print("\n[PHASE 3] MACHINERY BREAKDOWN (16 bars)")
        print("  WARNING: System malfunction detected...")
        
        # Glitchy, broken patterns
        self.osc.seq_update_pattern('kick', 'X..X.X....X.X...')
        self.osc.seq_update_pattern('acid', 'XxXxXx..XxXx....')
        self.osc.seq_update_pattern('metal', 'x.x.x.x.x.......')
        
        # High resonance - SCREAMING filter (but safe)
        self.osc.set_acid_res(0.88)  # Very high but not breaking
        self.osc.set_acid_env(3000, decay=0.05)
        
        # Push distortion harder (but not to breaking point)
        self.osc.set_distortion(drive=0.5, mix=0.4, tone=0.1)
        
        # Add LFO chaos
        self.osc.set_lfo(1, rate=0.3, depth=0.6)  # Slow filter sweep
        
        # Glitch effects with rapid changes
        glitch_patterns = [
            'X.X.X...X.X...X.',
            'XX..XX..........', 
            'X...............', 
            'XXXXXXXXXXXXXXXX',
            '................'
        ]
        
        for bar in range(16):
            # Random pattern glitches
            if random.random() > 0.3:
                track = random.choice(['kick', 'acid', 'metal'])
                pattern = random.choice(glitch_patterns)
                self.osc.seq_update_pattern(track, pattern)
                
            # Extreme filter sweeps
            if bar % 2 == 0:
                self.osc.set_acid_cutoff(100)
            else:
                self.osc.set_acid_cutoff(2000 + random.randint(0, 1500))
                
            # Random stabs
            if random.random() > 0.7:
                self.osc.seq_update_pattern('stab', 'X...............')
            else:
                self.osc.seq_update_pattern('stab', '................')
                
            # Speed changes for chaos
            if bar == 8:
                self.osc.seq_bpm(140)
                print("  System acceleration detected")
            elif bar == 12:
                self.osc.seq_bpm(130)
                print("  System deceleration")
                
            time.sleep(1.71 if bar < 8 else 1.78 if bar >= 12 else 1.71)
            
    def phase4_industrial_peak(self):
        """Bars 49-80: Maximum industrial intensity"""
        print("\n[PHASE 4] INDUSTRIAL PEAK (32 bars)")
        print("  MAXIMUM INTENSITY - TOTAL SYSTEM OVERLOAD")
        
        # Reset to driving tempo
        self.osc.seq_bpm(135)
        
        # EVERYTHING at maximum
        self.osc.seq_update_pattern('kick', 'X.X.X.X.X.X.X.X.')
        self.osc.seq_update_pattern('acid', 'XXXXXXXXXXXXXXXX')
        self.osc.seq_update_pattern('metal', 'xxxxxxxxxxxxxxxx')
        self.osc.seq_update_pattern('stab', 'X...X...X...X...')
        
        # HEAVY DISTORTION (but engine-safe)
        self.osc.set_distortion(drive=0.6, mix=0.5, tone=0.0)  # Darkest tone
        self.osc.set_acid_drive(0.7, mix=0.9)  # Heavy acid but not maxed
        self.osc.set_acid_res(0.90)  # Very high but stable
        
        # Fast modulation for chaos
        self.osc.set_lfo(2, rate=12.0, depth=0.5)
        
        print("  Distortion cascade active")
        print("  All systems at critical levels")
        
        for bar in range(32):
            # Aggressive filter modulation
            mod_speed = 0.5 + (bar * 0.05)
            cutoff = 500 + (2000 * abs(math.sin(bar * mod_speed)))
            self.osc.set_acid_cutoff(cutoff)
            
            # Envelope modulation for movement
            env = 2000 + (2000 * abs(math.cos(bar * 0.3)))
            self.osc.set_acid_env(env, decay=0.03)
            
            # Pattern variations every 8 bars
            if bar % 8 == 0 and bar > 0:
                section = bar // 8
                if section == 1:
                    self.osc.seq_update_pattern('kick', 'XXXXXXXXXXXXXXXX')
                    print("  Relentless kick engaged")
                elif section == 2:
                    self.osc.seq_add_track('aux', 'voice1',
                                          'X.X.X.X.X.X.X.X.',
                                          base_freq=35)  # Sub-sub bass
                    print("  Sub-bass auxiliary online")
                elif section == 3:
                    self.osc.set_distortion(drive=0.7, mix=0.6)
                    print("  DISTORTION EXTREME (but safe)")
                    
            # Brief moments of chaos
            if bar % 4 == 3:
                self.osc.seq_update_pattern('acid', 'X.X.X...X.X...X.')
                time.sleep(0.89)  # Half bar
                self.osc.seq_update_pattern('acid', 'XXXXXXXXXXXXXXXX')
                time.sleep(0.89)  # Half bar
            else:
                time.sleep(1.78)
                
    def phase5_system_failure(self):
        """Bars 81-96: Complete breakdown"""
        print("\n[PHASE 5] SYSTEM FAILURE (16 bars)")
        print("  Critical failure imminent...")
        
        # System breaking down
        self.osc.set_delay(mix=0.6, time=0.375, feedback=0.8)  # Feedback chaos
        
        # Remove elements progressively
        breakdown_schedule = [
            (0, 'metal', "Percussion systems offline"),
            (4, 'stab', "Stab generator failed"),
            (8, 'aux', "Auxiliary power lost"),
            (12, 'acid', "Acid core meltdown")
        ]
        
        for bar in range(16):
            # Check breakdown schedule
            for trigger_bar, track, message in breakdown_schedule:
                if bar == trigger_bar:
                    if track == 'aux':
                        try:
                            self.osc.seq_remove_track(track)
                        except:
                            pass
                    else:
                        self.osc.seq_remove_track(track)
                    print(f"  {message}")
                    
            # Distortion fading as power fails
            if bar >= 8:
                dist = 0.9 - ((bar - 8) * 0.1)
                self.osc.set_distortion(drive=dist, mix=dist * 0.7)
                
            # Kick becomes irregular
            if bar % 2 == 0:
                irregular_patterns = [
                    'X...............', 
                    'X...X...........',
                    'X.......X.......',
                    '................'
                ]
                self.osc.seq_update_pattern('kick', random.choice(irregular_patterns))
                
            # BPM slowing down (system dying)
            if bar >= 12:
                self.osc.seq_bpm(135 - ((bar - 12) * 5))
                
            time.sleep(1.78 + (bar * 0.02))  # Gradually slowing
            
    def outro_darkness(self):
        """Final decay into silence"""
        print("\n[OUTRO] DARKNESS PREVAILS (8 bars)")
        
        # Only kick remains, dying
        self.osc.seq_update_pattern('kick', 'X...............')
        
        # Massive reverb as everything collapses
        self.osc.set_reverb(mix=0.8, room=0.95, damp=0.1)
        
        # Reduce all levels
        for voice in range(1, 5):
            self.osc.set_voice_amp(voice, 0.05)
            
        # Final beats
        for bar in range(8):
            if bar == 4:
                self.osc.seq_update_pattern('kick', '................')
                print("  Silence approaches...")
            time.sleep(2.0)
            
        # Complete shutdown
        self.osc.seq_stop()
        self.osc.seq_clear()
        
        # Final reverb tail
        time.sleep(4)
        
        print("\n" + "=" * 60)
        print("  The nightmare ends... or does it?")
        print("  'Industrial Nightmare' - Maximum darkness achieved")
        print("=" * 60)
        
    def unleash_nightmare(self):
        """Perform the complete industrial nightmare"""
        self.setup_darkness()
        
        print("\n[WARNING: EXTREME AUDIO CONTENT]")
        print("[Starting in 3 seconds...]")
        time.sleep(3)
        
        # Full composition
        self.phase1_factory_floor()      # 16 bars - Industrial foundation
        self.phase2_acid_injection()     # 16 bars - Acid enters
        self.phase3_machinery_breakdown() # 16 bars - System malfunction  
        self.phase4_industrial_peak()     # 32 bars - Maximum intensity
        self.phase5_system_failure()     # 16 bars - Breaking down
        self.outro_darkness()            # 8 bars - Final darkness
        
        print("\nTotal duration: ~3 minutes")
        print("Genre: Industrial Techno / Dark Acid")
        print("Distortion level: MAXIMUM")
        print("Chronus Pet status: Probably traumatized")
        

if __name__ == "__main__":
    nightmare = IndustrialNightmare()
    nightmare.unleash_nightmare()