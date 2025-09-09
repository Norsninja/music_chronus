#!/usr/bin/env python3
"""
ANTHEM BREAKBEAT 174 - Epic 8-Voice DnB Composition
Created by Chronus Nexus
Requires: CHRONUS_NUM_VOICES=8 environment variable set before starting engine
"""

from pythonosc import udp_client
import time

class AnthemBreakbeat:
    def __init__(self):
        self.osc = udp_client.SimpleUDPClient('127.0.0.1', 5005)
        self.bpm = 174
        self.beat = 60.0 / self.bpm
        self.bar = self.beat * 4
        
    def setup(self):
        """Initialize the anthem setup"""
        print(">>> ANTHEM BREAKBEAT 174 - Initializing...")
        self.osc.send_message('/seq/stop', [])
        self.osc.send_message('/seq/clear', [])
        self.osc.send_message('/seq/bpm', [self.bpm])
        self.osc.send_message('/seq/swing', [0.12])  # Human groove
        
        # Reset effects
        self.osc.send_message('/mod/dist1/drive', [0.0])
        self.osc.send_message('/mod/dist1/mix', [0.0])
        
    def configure_drums(self):
        """Setup drum voices 1, 3, 4"""
        print("  [DRUMS] Configuring drums...")
        
        # Voice1: Deep kick
        self.osc.send_message('/mod/voice1/osc/type', [0])  # Sine
        self.osc.send_message('/mod/voice1/freq', [45])
        self.osc.send_message('/mod/voice1/amp', [0.3])
        self.osc.send_message('/mod/voice1/filter/freq', [200])
        self.osc.send_message('/mod/voice1/filter/q', [2.5])
        self.osc.send_message('/mod/voice1/adsr/attack', [0.001])
        self.osc.send_message('/mod/voice1/adsr/decay', [0.11])
        self.osc.send_message('/mod/voice1/adsr/sustain', [0.1])
        self.osc.send_message('/mod/voice1/adsr/release', [0.18])
        
        # Voice3: Crispy snare
        self.osc.send_message('/mod/voice3/osc/type', [3])  # White noise
        self.osc.send_message('/mod/voice3/freq', [200])
        self.osc.send_message('/mod/voice3/amp', [0.26])
        self.osc.send_message('/mod/voice3/filter/freq', [5000])
        self.osc.send_message('/mod/voice3/filter/q', [2.0])
        self.osc.send_message('/mod/voice3/adsr/attack', [0.001])
        self.osc.send_message('/mod/voice3/adsr/decay', [0.025])
        self.osc.send_message('/mod/voice3/adsr/sustain', [0.1])
        self.osc.send_message('/mod/voice3/adsr/release', [0.015])
        self.osc.send_message('/mod/voice3/send/reverb', [0.2])
        
        # Voice4: Tight hi-hats
        self.osc.send_message('/mod/voice4/osc/type', [4])  # Pink noise
        self.osc.send_message('/mod/voice4/freq', [9000])
        self.osc.send_message('/mod/voice4/amp', [0.07])
        self.osc.send_message('/mod/voice4/filter/freq', [11000])
        self.osc.send_message('/mod/voice4/filter/q', [1.5])
        self.osc.send_message('/mod/voice4/adsr/attack', [0.001])
        self.osc.send_message('/mod/voice4/adsr/decay', [0.002])
        self.osc.send_message('/mod/voice4/adsr/sustain', [0.1])
        self.osc.send_message('/mod/voice4/adsr/release', [0.003])
        
    def configure_bass(self):
        """Setup bass with acid filter on voice2"""
        print("  [BASS] Configuring sub bass...")
        
        # Voice2: Sub bass with acid
        self.osc.send_message('/mod/voice2/osc/type', [1])  # Saw
        self.osc.send_message('/mod/voice2/freq', [41.2])  # E1
        self.osc.send_message('/mod/voice2/amp', [0.24])
        self.osc.send_message('/mod/voice2/filter/freq', [250])
        self.osc.send_message('/mod/voice2/filter/q', [3.5])
        self.osc.send_message('/mod/voice2/adsr/attack', [0.01])
        self.osc.send_message('/mod/voice2/adsr/decay', [0.15])
        self.osc.send_message('/mod/voice2/adsr/sustain', [0.5])
        self.osc.send_message('/mod/voice2/adsr/release', [0.12])
        self.osc.send_message('/mod/voice2/slide_time', [0.04])
        
        # Acid filter settings
        self.osc.send_message('/mod/acid1/cutoff', [600])
        self.osc.send_message('/mod/acid1/res', [0.75])
        self.osc.send_message('/mod/acid1/env_amount', [2000])
        self.osc.send_message('/mod/acid1/decay', [0.13])
        self.osc.send_message('/mod/acid1/drive', [0.2])
        
    def configure_vocals(self):
        """Setup vocal 'hey' calls on voices 5-6"""
        print("  [VOCALS] Configuring vocal elements...")
        
        # Voice5: High 'HEY' call
        self.osc.send_message('/mod/voice5/osc/type', [1])  # Saw
        self.osc.send_message('/mod/voice5/freq', [220])  # A3
        self.osc.send_message('/mod/voice5/amp', [0.22])
        self.osc.send_message('/mod/voice5/filter/freq', [2200])  # 'EH' formant
        self.osc.send_message('/mod/voice5/filter/q', [9.0])
        self.osc.send_message('/mod/voice5/adsr/attack', [0.02])
        self.osc.send_message('/mod/voice5/adsr/decay', [0.09])
        self.osc.send_message('/mod/voice5/adsr/sustain', [0.2])
        self.osc.send_message('/mod/voice5/adsr/release', [0.12])
        self.osc.send_message('/mod/voice5/send/reverb', [0.45])
        self.osc.send_message('/mod/voice5/send/delay', [0.2])
        
        # Voice6: Low 'HEY' response
        self.osc.send_message('/mod/voice6/osc/type', [2])  # Square
        self.osc.send_message('/mod/voice6/freq', [165])  # E3
        self.osc.send_message('/mod/voice6/amp', [0.2])
        self.osc.send_message('/mod/voice6/filter/freq', [1800])  # 'AH' formant
        self.osc.send_message('/mod/voice6/filter/q', [11.0])
        self.osc.send_message('/mod/voice6/adsr/attack', [0.01])
        self.osc.send_message('/mod/voice6/adsr/decay', [0.11])
        self.osc.send_message('/mod/voice6/adsr/sustain', [0.15])
        self.osc.send_message('/mod/voice6/adsr/release', [0.14])
        self.osc.send_message('/mod/voice6/send/reverb', [0.4])
        self.osc.send_message('/mod/voice6/send/delay', [0.25])
        
    def configure_atmosphere(self):
        """Setup atmospheric elements on voices 7-8"""
        print("  [ATMOSPHERE] Configuring atmosphere...")
        
        # Voice7: Crowd 'OH' chants
        self.osc.send_message('/mod/voice7/osc/type', [3])  # White noise
        self.osc.send_message('/mod/voice7/freq', [330])  # E4
        self.osc.send_message('/mod/voice7/amp', [0.13])
        self.osc.send_message('/mod/voice7/filter/freq', [800])  # 'OH' formant
        self.osc.send_message('/mod/voice7/filter/q', [7.0])
        self.osc.send_message('/mod/voice7/adsr/attack', [0.04])
        self.osc.send_message('/mod/voice7/adsr/decay', [0.18])
        self.osc.send_message('/mod/voice7/adsr/sustain', [0.35])
        self.osc.send_message('/mod/voice7/adsr/release', [0.25])
        self.osc.send_message('/mod/voice7/send/reverb', [0.55])
        
        # Voice8: Epic synth stabs
        self.osc.send_message('/mod/voice8/osc/type', [2])  # Square
        self.osc.send_message('/mod/voice8/freq', [440])  # A4
        self.osc.send_message('/mod/voice8/amp', [0.17])
        self.osc.send_message('/mod/voice8/filter/freq', [3500])
        self.osc.send_message('/mod/voice8/filter/q', [3.5])
        self.osc.send_message('/mod/voice8/adsr/attack', [0.001])
        self.osc.send_message('/mod/voice8/adsr/decay', [0.06])
        self.osc.send_message('/mod/voice8/adsr/sustain', [0.1])
        self.osc.send_message('/mod/voice8/adsr/release', [0.1])
        self.osc.send_message('/mod/voice8/send/delay', [0.35])
        
    def setup_effects(self, intensity='normal'):
        """Configure global effects"""
        if intensity == 'normal':
            self.osc.send_message('/mod/reverb1/room', [0.7])
            self.osc.send_message('/mod/reverb1/damp', [0.3])
            self.osc.send_message('/mod/reverb1/mix', [0.35])
            self.osc.send_message('/mod/delay1/time', [0.172])
            self.osc.send_message('/mod/delay1/feedback', [0.35])
            self.osc.send_message('/mod/delay1/mix', [0.25])
            self.osc.send_message('/mod/dist1/drive', [0.05])
            self.osc.send_message('/mod/dist1/mix', [0.1])
        elif intensity == 'stadium':
            self.osc.send_message('/mod/reverb1/room', [0.92])
            self.osc.send_message('/mod/reverb1/damp', [0.2])
            self.osc.send_message('/mod/reverb1/mix', [0.5])
            self.osc.send_message('/mod/delay1/time', [0.172])
            self.osc.send_message('/mod/delay1/feedback', [0.5])
            self.osc.send_message('/mod/delay1/mix', [0.35])
            self.osc.send_message('/mod/dist1/drive', [0.12])
            self.osc.send_message('/mod/dist1/mix', [0.2])
            
    def intro(self):
        """8 bar intro building up"""
        print("\n>>> INTRO (8 bars)")
        
        # Start with just kick
        self.osc.send_message('/seq/add', ['kick', 'voice1', 'X.......x.......', 45, 200])
        self.osc.send_message('/seq/start', [])
        time.sleep(self.bar * 2)
        
        # Add hi-hats
        self.osc.send_message('/seq/add', ['hats', 'voice4', 'xxxxxxxxxxxxxxxx', 9000, 11000])
        time.sleep(self.bar * 2)
        
        # Add bass
        bass_notes = '41.2,41.2,36.7,41.2,49,49,41.2,36.7,32.7,32.7,41.2,49,55,55,41.2,36.7'
        self.osc.send_message('/seq/add', ['bass', 'voice2', 'x.x.x...x.x.....', 41.2, 250, bass_notes])
        time.sleep(self.bar * 2)
        
        # Add snare
        self.osc.send_message('/seq/add', ['snare', 'voice3', '....X.....X.x...', 200, 5000])
        time.sleep(self.bar * 2)
        
    def drop(self):
        """16 bar main drop - full energy"""
        print("\n>>> DROP! (16 bars)")
        
        # Full drums pattern
        self.osc.send_message('/seq/update/pattern', ['kick', 'X...x...X.x.x...'])
        self.osc.send_message('/seq/update/pattern', ['snare', '....X..x..X.X.x.'])
        
        # Add vocal calls
        self.osc.send_message('/seq/add', ['hey1', 'voice5', '..X.............', 220, 2200])
        self.osc.send_message('/seq/add', ['hey2', 'voice6', '......X.X.......', 165, 1800])
        
        # Add crowd and stabs
        self.osc.send_message('/seq/add', ['crowd', 'voice7', '........X.X.X.X.', 330, 800])
        self.osc.send_message('/seq/add', ['stab', 'voice8', '....x.......x...', 440, 3500])
        
        # Increase effects
        self.setup_effects('stadium')
        
        # Let it ride
        time.sleep(self.bar * 8)
        
        # Second half with variation
        self.osc.send_message('/seq/update/pattern', ['bass', 'x.x.x.x.x.x.....'])
        self.osc.send_message('/mod/lfo1/rate', [0.5])
        self.osc.send_message('/mod/lfo1/depth', [0.6])
        
        time.sleep(self.bar * 8)
        
    def breakdown(self):
        """8 bar breakdown - atmospheric"""
        print("\n>>> BREAKDOWN (8 bars)")
        
        # Remove drums except minimal kick
        self.osc.send_message('/seq/remove', ['snare'])
        self.osc.send_message('/seq/update/pattern', ['kick', 'X...............'])
        self.osc.send_message('/seq/update/pattern', ['hats', '..x...x...x...x.'])
        
        # Keep atmosphere
        self.osc.send_message('/seq/remove', ['stab'])
        
        # Mellow the bass
        self.osc.send_message('/mod/acid1/cutoff', [400])
        self.osc.send_message('/mod/acid1/res', [0.5])
        
        time.sleep(self.bar * 4)
        
        # Build tension
        for i in range(4):
            cutoff = 400 + (i * 200)
            self.osc.send_message('/mod/acid1/cutoff', [cutoff])
            time.sleep(self.bar)
            
    def buildup(self):
        """8 bar build-up to second drop"""
        print("\n>>> BUILD-UP (8 bars)")
        
        # Gradually add elements back
        self.osc.send_message('/seq/add', ['snare', 'voice3', '....x...x...x.x.', 200, 5000])
        
        # Rising filter sweeps
        for i in range(8):
            freq = 600 + (i * 150)
            self.osc.send_message('/mod/acid1/cutoff', [freq])
            self.osc.send_message('/mod/voice8/filter/freq', [3500 + (i * 200)])
            
            if i == 4:
                self.osc.send_message('/seq/update/pattern', ['kick', 'X...x...X...x...'])
                self.osc.send_message('/seq/add', ['stab', 'voice8', 'x.x.x.x.x.x.x.x.', 440 + (i * 20), 3500])
                
            time.sleep(self.bar)
            
    def second_drop(self):
        """16 bar second drop - maximum energy"""
        print("\n>>> SECOND DROP! (16 bars)")
        
        # Full patterns
        self.osc.send_message('/seq/update/pattern', ['kick', 'X..xx...X.x.x...'])
        self.osc.send_message('/seq/update/pattern', ['snare', '....X..x..X.X..x'])
        self.osc.send_message('/seq/update/pattern', ['hats', 'XxXxXxXxXxXxXxXx'])
        self.osc.send_message('/seq/update/pattern', ['bass', 'X.X.X.X.X.X.X...'])
        
        # Maximum effects
        self.setup_effects('stadium')
        self.osc.send_message('/mod/dist1/drive', [0.15])
        self.osc.send_message('/mod/dist1/mix', [0.25])
        
        # All vocals active
        self.osc.send_message('/seq/update/pattern', ['hey1', 'X.X.............'])
        self.osc.send_message('/seq/update/pattern', ['hey2', '....X.X.X.......'])
        self.osc.send_message('/seq/update/pattern', ['crowd', 'X.X.X.X.X.X.X.X.'])
        
        # LFO modulation
        self.osc.send_message('/mod/lfo1/rate', [0.75])
        self.osc.send_message('/mod/lfo1/depth', [0.8])
        self.osc.send_message('/mod/lfo2/rate', [4.0])
        self.osc.send_message('/mod/lfo2/depth', [0.3])
        
        time.sleep(self.bar * 16)
        
    def outro(self):
        """Epic outro"""
        print("\n>>> OUTRO (4 bars)")
        
        # Remove elements one by one
        self.osc.send_message('/seq/remove', ['crowd'])
        time.sleep(self.bar)
        
        self.osc.send_message('/seq/remove', ['hey1'])
        self.osc.send_message('/seq/remove', ['hey2'])
        time.sleep(self.bar)
        
        self.osc.send_message('/seq/remove', ['bass'])
        self.osc.send_message('/seq/remove', ['hats'])
        time.sleep(self.bar)
        
        # Final hit
        self.osc.send_message('/seq/stop', [])
        self.osc.send_message('/gate/voice1', [1])
        self.osc.send_message('/gate/voice3', [1])
        self.osc.send_message('/gate/voice7', [1])
        time.sleep(0.1)
        self.osc.send_message('/gate/voice1', [0])
        self.osc.send_message('/gate/voice3', [0])
        self.osc.send_message('/gate/voice7', [0])
        
        print("\n>>> ANTHEM COMPLETE!")
        
    def perform(self):
        """Perform the complete anthem"""
        self.setup()
        self.configure_drums()
        self.configure_bass()
        self.configure_vocals()
        self.configure_atmosphere()
        self.setup_effects('normal')
        
        print("\n" + "="*50)
        print("  ANTHEM BREAKBEAT 174 - STARTING")
        print("="*50)
        
        self.intro()
        self.drop()
        self.breakdown()
        self.buildup()
        self.second_drop()
        self.outro()
        
if __name__ == "__main__":
    anthem = AnthemBreakbeat()
    anthem.perform()