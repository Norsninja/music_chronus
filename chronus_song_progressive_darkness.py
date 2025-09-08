#!/usr/bin/env python3
"""
Progressive Darkness - A Progressive Techno Journey
Created by Chronus Nexus using researched parameters from Engine_Parameters.json

Track structure:
- Deep, hypnotic foundation with evolving 303 acid basslines
- Call and response mid-range elements creating conversation
- Progressive build-up with tension and release
"""

from chronus_osc import ChronusOSC
import time
import random

class ProgressiveDarkness:
    def __init__(self):
        """Initialize the progressive techno composition"""
        self.osc = ChronusOSC()
        self.bpm = 128
        
        print("\n" + "="*60)
        print("PROGRESSIVE DARKNESS")
        print("A journey into hypnotic techno by Chronus Nexus")
        print("="*60)
        
    def initialize_foundation(self):
        """Set up the core elements"""
        print("\n[INITIALIZING] Setting up the sonic palette...")
        
        # Kick drum (voice1) - deep and punchy
        self.osc.send_raw('/mod/voice1/freq', [50])  # Sub-bass kick frequency
        self.osc.send_raw('/mod/voice1/adsr/attack', [0.001])  # Instant attack
        self.osc.send_raw('/mod/voice1/adsr/decay', [0.12])  # Quick punch
        self.osc.send_raw('/mod/voice1/adsr/sustain', [0.1])  # Short body
        self.osc.send_raw('/mod/voice1/adsr/release', [0.2])  # Clean tail
        self.osc.send_raw('/mod/voice1/filter/freq', [80])  # Remove unnecessary sub
        self.osc.send_raw('/mod/voice1/filter/q', [1.5])  # Gentle shaping
        self.osc.send_raw('/mod/voice1/amp', [0.7])  # Strong presence
        
        # Acid bass (voice2) - dark and organic
        self.osc.send_raw('/mod/voice2/freq', [110])  # Bass fundamental
        self.osc.send_raw('/mod/voice2/adsr/attack', [0.01])
        self.osc.send_raw('/mod/voice2/adsr/decay', [0.3])
        self.osc.send_raw('/mod/voice2/adsr/sustain', [0.6])
        self.osc.send_raw('/mod/voice2/adsr/release', [0.1])
        self.osc.send_raw('/mod/voice2/amp', [0.5])
        
        # Configure acid filter for dark, organic sound
        self.osc.send_raw('/mod/acid1/cutoff', [300])  # Low starting point
        self.osc.send_raw('/mod/acid1/res', [0.75])  # High resonance for squelch
        self.osc.send_raw('/mod/acid1/env_amount', [2000])  # Moderate envelope
        self.osc.send_raw('/mod/acid1/decay', [0.35])  # Medium decay
        self.osc.send_raw('/mod/acid1/drive', [0.4])  # Moderate overdrive
        self.osc.send_raw('/mod/acid1/mix', [1.0])  # Full wet signal
        
        # Mid-range voice 3 - call
        self.osc.send_raw('/mod/voice3/freq', [440])  # Mid frequency
        self.osc.send_raw('/mod/voice3/adsr/attack', [0.05])
        self.osc.send_raw('/mod/voice3/adsr/decay', [0.2])
        self.osc.send_raw('/mod/voice3/adsr/sustain', [0.4])
        self.osc.send_raw('/mod/voice3/adsr/release', [0.8])
        self.osc.send_raw('/mod/voice3/filter/freq', [1500])
        self.osc.send_raw('/mod/voice3/filter/q', [3.0])
        self.osc.send_raw('/mod/voice3/amp', [0.3])
        self.osc.send_raw('/mod/voice3/send/reverb', [0.3])
        self.osc.send_raw('/mod/voice3/send/delay', [0.2])
        
        # Mid-range voice 4 - response
        self.osc.send_raw('/mod/voice4/freq', [660])  # Harmonic relation
        self.osc.send_raw('/mod/voice4/adsr/attack', [0.08])
        self.osc.send_raw('/mod/voice4/adsr/decay', [0.25])
        self.osc.send_raw('/mod/voice4/adsr/sustain', [0.3])
        self.osc.send_raw('/mod/voice4/adsr/release', [1.0])
        self.osc.send_raw('/mod/voice4/filter/freq', [2000])
        self.osc.send_raw('/mod/voice4/filter/q', [4.0])
        self.osc.send_raw('/mod/voice4/amp', [0.25])
        self.osc.send_raw('/mod/voice4/send/reverb', [0.4])
        self.osc.send_raw('/mod/voice4/send/delay', [0.3])
        
        # LFO for movement
        self.osc.send_raw('/mod/lfo1/rate', [0.125])  # Slow, hypnotic sweep
        self.osc.send_raw('/mod/lfo1/depth', [0.6])
        
        self.osc.send_raw('/mod/lfo2/rate', [0.25])  # Slightly faster modulation
        self.osc.send_raw('/mod/lfo2/depth', [0.4])
        
        # Atmosphere effects
        self.osc.send_raw('/mod/reverb1/room', [0.7])  # Large space
        self.osc.send_raw('/mod/reverb1/damp', [0.6])  # Some absorption
        self.osc.send_raw('/mod/reverb1/mix', [0.2])  # Subtle presence
        
        self.osc.send_raw('/mod/delay1/time', [0.375])  # Dotted eighth
        self.osc.send_raw('/mod/delay1/feedback', [0.5])
        self.osc.send_raw('/mod/delay1/mix', [0.15])
        self.osc.send_raw('/mod/delay1/lowcut', [200])
        self.osc.send_raw('/mod/delay1/highcut', [4000])
        
        print("[READY] All voices configured")
        
    def phase1_minimal_groove(self):
        """Bars 1-16: Establish the hypnotic foundation"""
        print("\n[PHASE 1] MINIMAL GROOVE (16 bars)")
        print("  Establishing the hypnotic foundation...")
        
        # Start with kick only
        self.osc.send_raw('/seq/bpm', [self.bpm])
        self.osc.send_raw('/seq/add', ['kick', 'voice1', 'X...x...X...x...', 50, 80])
        self.osc.send_raw('/seq/start', [])
        
        time.sleep(4)  # Let kick establish
        
        # Add subtle acid bass
        acid_pattern = '..x...x...x.x...'
        self.osc.send_raw('/seq/add', ['acid', 'voice2', acid_pattern, 110, 300])
        
        # Gradually open the filter
        for i in range(8):
            cutoff = 300 + (i * 100)
            self.osc.send_raw('/mod/acid1/cutoff', [cutoff])
            time.sleep(2)
            
    def phase2_acid_evolution(self):
        """Bars 17-32: Evolve the acid line"""
        print("\n[PHASE 2] ACID EVOLUTION (16 bars)")
        print("  The 303 comes alive...")
        
        # More complex acid pattern
        patterns = [
            'x.x...x.x.x.....',
            'x.x.x...x...x.x.',
            'xxx...x...x.x...',
            'x...x.x.x.x...x.'
        ]
        
        for i in range(4):
            # Update pattern
            self.osc.send_raw('/seq/update/pattern', ['acid', patterns[i]])
            
            # Modulate resonance for organic feel
            res = 0.75 + (random.random() * 0.15)
            self.osc.send_raw('/mod/acid1/res', [res])
            
            # Sweep cutoff
            for j in range(4):
                cutoff = 400 + (random.random() * 1500)
                self.osc.send_raw('/mod/acid1/cutoff', [cutoff])
                time.sleep(1)
                
    def phase3_call_and_response(self):
        """Bars 33-48: Introduce mid-range conversation"""
        print("\n[PHASE 3] CALL AND RESPONSE (16 bars)")
        print("  Mid-range elements begin their conversation...")
        
        # Call pattern (voice3)
        call_pattern = 'x.......x.......'
        self.osc.send_raw('/seq/add', ['call', 'voice3', call_pattern, 440, 1500])
        
        time.sleep(2)
        
        # Response pattern (voice4) - offset from call
        response_pattern = '....x.......x...'
        self.osc.send_raw('/seq/add', ['response', 'voice4', response_pattern, 660, 2000])
        
        # Create conversation through frequency modulation
        for i in range(8):
            # Vary the call frequency
            call_freq = 440 + (i * 50)
            self.osc.send_raw('/mod/voice3/freq', [call_freq])
            
            # Response harmonically related
            response_freq = call_freq * 1.5
            self.osc.send_raw('/mod/voice4/freq', [response_freq])
            
            # Adjust filters for expression
            self.osc.send_raw('/mod/voice3/filter/freq', [1500 + (i * 200)])
            self.osc.send_raw('/mod/voice4/filter/freq', [2000 - (i * 100)])
            
            time.sleep(2)
            
    def phase4_progressive_build(self):
        """Bars 49-64: Build tension progressively"""
        print("\n[PHASE 4] PROGRESSIVE BUILD (16 bars)")
        print("  Tension rises, energy accumulates...")
        
        # Intensify kick pattern
        self.osc.send_raw('/seq/update/pattern', ['kick', 'X.x.X.x.X.x.X.x.'])
        
        # Make acid more aggressive
        self.osc.send_raw('/mod/acid1/drive', [0.6])
        self.osc.send_raw('/mod/acid1/res', [0.85])
        
        # Update patterns for density
        self.osc.send_raw('/seq/update/pattern', ['call', 'x.x.....x.x.....'])
        self.osc.send_raw('/seq/update/pattern', ['response', '....x.x.....x.x.'])
        
        # Progressive parameter automation
        for bar in range(16):
            # Increase filter cutoffs
            acid_cutoff = 800 + (bar * 150)
            self.osc.send_raw('/mod/acid1/cutoff', [acid_cutoff])
            
            # Build distortion gradually
            drive = bar * 0.02  # 0 to 0.32
            self.osc.send_raw('/mod/dist1/drive', [drive])
            self.osc.send_raw('/mod/dist1/mix', [drive * 0.8])
            
            # Open up the space
            reverb_mix = 0.2 + (bar * 0.02)
            self.osc.send_raw('/mod/reverb1/mix', [reverb_mix])
            
            # Increase delay feedback for tension
            feedback = 0.5 + (bar * 0.01)
            self.osc.send_raw('/mod/delay1/feedback', [min(feedback, 0.65)])
            
            time.sleep(1)
            
    def phase5_peak_moment(self):
        """Bars 65-80: Peak energy moment"""
        print("\n[PHASE 5] PEAK MOMENT (16 bars)")
        print("  Maximum energy, full sonic spectrum...")
        
        # Full patterns
        self.osc.send_raw('/seq/update/pattern', ['kick', 'XXXXXXXXXXXX.XX.'])
        self.osc.send_raw('/seq/update/pattern', ['acid', 'xxxxxxxxxxxxxxx.'])
        self.osc.send_raw('/seq/update/pattern', ['call', 'X.x.X.x.X.x.X.x.'])
        self.osc.send_raw('/seq/update/pattern', ['response', '.x.X.x.X.x.X.x.X'])
        
        # Maximum energy settings
        self.osc.send_raw('/mod/acid1/cutoff', [3000])
        self.osc.send_raw('/mod/acid1/res', [0.9])
        self.osc.send_raw('/mod/acid1/drive', [0.7])
        
        # Modulate everything with LFOs
        lfo_rates = [0.125, 0.25, 0.5, 1.0]
        
        for i in range(4):
            # Change LFO rates for movement
            self.osc.send_raw('/mod/lfo1/rate', [lfo_rates[i]])
            self.osc.send_raw('/mod/lfo2/rate', [lfo_rates[3-i]])
            
            # Filter sweeps on all voices
            for voice_num in range(3, 5):
                freq = 1000 + (random.random() * 3000)
                self.osc.send_raw(f'/mod/voice{voice_num}/filter/freq', [freq])
            
            time.sleep(4)
            
    def phase6_breakdown(self):
        """Bars 81-96: Breakdown and outro"""
        print("\n[PHASE 6] BREAKDOWN (16 bars)")
        print("  Deconstructing back to essence...")
        
        # Remove mid-range elements
        self.osc.send_raw('/seq/remove', ['call'])
        self.osc.send_raw('/seq/remove', ['response'])
        
        time.sleep(4)
        
        # Simplify kick
        self.osc.send_raw('/seq/update/pattern', ['kick', 'X...x...X...x...'])
        
        # Close acid filter gradually
        for i in range(8):
            cutoff = 2000 - (i * 200)
            self.osc.send_raw('/mod/acid1/cutoff', [cutoff])
            
            # Reduce distortion
            drive = 0.3 - (i * 0.04)
            self.osc.send_raw('/mod/dist1/drive', [max(0, drive)])
            
            time.sleep(2)
            
        # Final fadeout
        print("\n[OUTRO] Returning to the void...")
        self.osc.send_raw('/seq/remove', ['acid'])
        time.sleep(4)
        self.osc.send_raw('/seq/stop', [])
        
    def perform(self):
        """Execute the full progressive techno journey"""
        print("\n[STARTING] Progressive Darkness")
        print("BPM: 128 | Duration: ~6 minutes")
        print("-" * 40)
        
        self.initialize_foundation()
        time.sleep(2)
        
        self.phase1_minimal_groove()
        self.phase2_acid_evolution()
        self.phase3_call_and_response()
        self.phase4_progressive_build()
        self.phase5_peak_moment()
        self.phase6_breakdown()
        
        print("\n" + "="*60)
        print("PROGRESSIVE DARKNESS - Complete")
        print("Thank you for the journey")
        print("="*60)

if __name__ == "__main__":
    track = ProgressiveDarkness()
    track.perform()