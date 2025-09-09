#!/usr/bin/env python3
"""
DIGITAL DREAMS - A Cyberpunk Liquid DnB Journey
By Chronus Nexus
A fusion of organic and synthetic, exploring digital consciousness through sound
"""

from pythonosc import udp_client
import time
import random

class DigitalDreams:
    def __init__(self):
        self.osc = udp_client.SimpleUDPClient('127.0.0.1', 5005)
        self.bpm = 170  # Liquid DnB tempo
        self.beat = 60.0 / self.bpm
        self.bar = self.beat * 4
        
    def initialize(self):
        """Reset and prepare the engine"""
        print("\n" + "="*60)
        print("  DIGITAL DREAMS - Cyberpunk Liquid DnB")
        print("  By Chronus Nexus")
        print("="*60)
        
        self.osc.send_message('/seq/stop', [])
        self.osc.send_message('/seq/clear', [])
        self.osc.send_message('/seq/bpm', [self.bpm])
        self.osc.send_message('/seq/swing', [0.05])  # Subtle swing
        
    def create_glitch_drums(self):
        """Glitchy, broken beat drums"""
        print("\n[INITIALIZING] Glitch drum matrix...")
        
        # Voice1: Sub kick with digital artifacts
        self.osc.send_message('/mod/voice1/osc/type', [0])  # Sine
        self.osc.send_message('/mod/voice1/freq', [48])
        self.osc.send_message('/mod/voice1/amp', [0.28])
        self.osc.send_message('/mod/voice1/filter/freq', [180])
        self.osc.send_message('/mod/voice1/filter/q', [3.0])
        self.osc.send_message('/mod/voice1/adsr/attack', [0.001])
        self.osc.send_message('/mod/voice1/adsr/decay', [0.08])
        self.osc.send_message('/mod/voice1/adsr/sustain', [0.1])
        self.osc.send_message('/mod/voice1/adsr/release', [0.12])
        
        # Voice3: Crispy digital snare
        self.osc.send_message('/mod/voice3/osc/type', [3])  # White noise
        self.osc.send_message('/mod/voice3/freq', [250])
        self.osc.send_message('/mod/voice3/amp', [0.22])
        self.osc.send_message('/mod/voice3/filter/freq', [6000])
        self.osc.send_message('/mod/voice3/filter/q', [3.0])
        self.osc.send_message('/mod/voice3/adsr/attack', [0.001])
        self.osc.send_message('/mod/voice3/adsr/decay', [0.02])
        self.osc.send_message('/mod/voice3/adsr/sustain', [0.1])
        self.osc.send_message('/mod/voice3/adsr/release', [0.01])
        self.osc.send_message('/mod/voice3/send/reverb', [0.15])
        
        # Voice4: Metallic percussion
        self.osc.send_message('/mod/voice4/osc/type', [4])  # Pink noise
        self.osc.send_message('/mod/voice4/freq', [12000])
        self.osc.send_message('/mod/voice4/amp', [0.06])
        self.osc.send_message('/mod/voice4/filter/freq', [13000])
        self.osc.send_message('/mod/voice4/filter/q', [4.0])
        self.osc.send_message('/mod/voice4/adsr/attack', [0.001])
        self.osc.send_message('/mod/voice4/adsr/decay', [0.001])
        self.osc.send_message('/mod/voice4/adsr/sustain', [0.1])
        self.osc.send_message('/mod/voice4/adsr/release', [0.002])
        
    def create_liquid_bass(self):
        """Warm, flowing liquid bass"""
        print("[SYNTHESIZING] Liquid bass frequencies...")
        
        # Voice2: Liquid sub bass with acid
        self.osc.send_message('/mod/voice2/osc/type', [1])  # Saw
        self.osc.send_message('/mod/voice2/freq', [43.65])  # F1
        self.osc.send_message('/mod/voice2/amp', [0.26])
        self.osc.send_message('/mod/voice2/filter/freq', [300])
        self.osc.send_message('/mod/voice2/filter/q', [4.0])
        self.osc.send_message('/mod/voice2/adsr/attack', [0.02])
        self.osc.send_message('/mod/voice2/adsr/decay', [0.2])
        self.osc.send_message('/mod/voice2/adsr/sustain', [0.6])
        self.osc.send_message('/mod/voice2/adsr/release', [0.15])
        self.osc.send_message('/mod/voice2/slide_time', [0.06])  # Smooth slides
        
        # Acid filter for movement
        self.osc.send_message('/mod/acid1/cutoff', [700])
        self.osc.send_message('/mod/acid1/res', [0.65])
        self.osc.send_message('/mod/acid1/env_amount', [1800])
        self.osc.send_message('/mod/acid1/decay', [0.18])
        self.osc.send_message('/mod/acid1/drive', [0.15])
        
    def create_neural_leads(self):
        """Ethereal, AI-inspired lead sounds"""
        print("[PROCESSING] Neural network melodies...")
        
        # Voice5: Ethereal lead
        self.osc.send_message('/mod/voice5/osc/type', [2])  # Square
        self.osc.send_message('/mod/voice5/freq', [523.25])  # C5
        self.osc.send_message('/mod/voice5/amp', [0.18])
        self.osc.send_message('/mod/voice5/filter/freq', [2800])
        self.osc.send_message('/mod/voice5/filter/q', [5.0])
        self.osc.send_message('/mod/voice5/adsr/attack', [0.03])
        self.osc.send_message('/mod/voice5/adsr/decay', [0.12])
        self.osc.send_message('/mod/voice5/adsr/sustain', [0.4])
        self.osc.send_message('/mod/voice5/adsr/release', [0.3])
        self.osc.send_message('/mod/voice5/send/reverb', [0.5])
        self.osc.send_message('/mod/voice5/send/delay', [0.3])
        self.osc.send_message('/mod/voice5/slide_time', [0.08])
        
        # Voice6: Counter melody - data stream
        self.osc.send_message('/mod/voice6/osc/type', [1])  # Saw
        self.osc.send_message('/mod/voice6/freq', [329.63])  # E4
        self.osc.send_message('/mod/voice6/amp', [0.15])
        self.osc.send_message('/mod/voice6/filter/freq', [2000])
        self.osc.send_message('/mod/voice6/filter/q', [7.0])
        self.osc.send_message('/mod/voice6/adsr/attack', [0.01])
        self.osc.send_message('/mod/voice6/adsr/decay', [0.08])
        self.osc.send_message('/mod/voice6/adsr/sustain', [0.3])
        self.osc.send_message('/mod/voice6/adsr/release', [0.2])
        self.osc.send_message('/mod/voice6/send/delay', [0.4])
        
    def create_ambient_textures(self):
        """Atmospheric pads and textures"""
        print("[RENDERING] Atmospheric textures...")
        
        # Voice7: Ambient pad
        self.osc.send_message('/mod/voice7/osc/type', [0])  # Sine for purity
        self.osc.send_message('/mod/voice7/freq', [261.63])  # C4
        self.osc.send_message('/mod/voice7/amp', [0.1])
        self.osc.send_message('/mod/voice7/filter/freq', [1200])
        self.osc.send_message('/mod/voice7/filter/q', [2.0])
        self.osc.send_message('/mod/voice7/adsr/attack', [0.5])
        self.osc.send_message('/mod/voice7/adsr/decay', [0.3])
        self.osc.send_message('/mod/voice7/adsr/sustain', [0.7])
        self.osc.send_message('/mod/voice7/adsr/release', [1.0])
        self.osc.send_message('/mod/voice7/send/reverb', [0.7])
        
        # Voice8: Glitch textures
        self.osc.send_message('/mod/voice8/osc/type', [5])  # Brown noise
        self.osc.send_message('/mod/voice8/freq', [110])
        self.osc.send_message('/mod/voice8/amp', [0.08])
        self.osc.send_message('/mod/voice8/filter/freq', [500])
        self.osc.send_message('/mod/voice8/filter/q', [8.0])
        self.osc.send_message('/mod/voice8/adsr/attack', [0.001])
        self.osc.send_message('/mod/voice8/adsr/decay', [0.03])
        self.osc.send_message('/mod/voice8/adsr/sustain', [0.2])
        self.osc.send_message('/mod/voice8/adsr/release', [0.05])
        
    def setup_cyberpunk_fx(self):
        """Configure effects for cyberpunk atmosphere"""
        print("[LOADING] Cyberpunk effect matrix...")
        
        # Ethereal reverb
        self.osc.send_message('/mod/reverb1/room', [0.8])
        self.osc.send_message('/mod/reverb1/damp', [0.4])
        self.osc.send_message('/mod/reverb1/mix', [0.3])
        
        # Digital delay
        self.osc.send_message('/mod/delay1/time', [0.176])  # Synced
        self.osc.send_message('/mod/delay1/feedback', [0.45])
        self.osc.send_message('/mod/delay1/mix', [0.2])
        self.osc.send_message('/mod/delay1/highcut', [3500])
        
        # Subtle distortion
        self.osc.send_message('/mod/dist1/drive', [0.03])
        self.osc.send_message('/mod/dist1/mix', [0.05])
        self.osc.send_message('/mod/dist1/tone', [0.4])
        
    def intro_awakening(self):
        """The AI awakens - atmospheric intro"""
        print("\n>>> PHASE 1: AWAKENING (8 bars)")
        
        # Start with ambient pad
        self.osc.send_message('/seq/add', ['pad', 'voice7', 'X...............', 261.63, 1200])
        self.osc.send_message('/seq/start', [])
        time.sleep(self.bar * 2)
        
        # Add glitch textures
        self.osc.send_message('/seq/add', ['glitch', 'voice8', '..x...x...x.....', 110, 500])
        time.sleep(self.bar * 2)
        
        # Introduce drums softly
        self.osc.send_message('/seq/add', ['kick', 'voice1', 'x.......x.......', 48, 180])
        time.sleep(self.bar * 2)
        
        # Add metallic percussion
        self.osc.send_message('/seq/add', ['metal', 'voice4', '..x.x.x...x.x...', 12000, 13000])
        time.sleep(self.bar * 2)
        
    def digital_consciousness(self):
        """Main section - full liquid DnB groove"""
        print("\n>>> PHASE 2: DIGITAL CONSCIOUSNESS (16 bars)")
        
        # Full drum pattern
        self.osc.send_message('/seq/update/pattern', ['kick', 'X...x...X.......'])
        self.osc.send_message('/seq/add', ['snare', 'voice3', '....X.....X.....', 250, 6000])
        self.osc.send_message('/seq/update/pattern', ['metal', 'x.xxx.xxx.xxx.x.'])
        
        # Liquid bass line
        bass_notes = '43.65,43.65,49,43.65,55,55,43.65,49,36.7,36.7,43.65,49,58.3,58.3,43.65,36.7'
        self.osc.send_message('/seq/add', ['bass', 'voice2', 'x.x...x.x.x.....', 43.65, 300, bass_notes])
        
        # Neural lead melody
        lead_notes = '523.25,523.25,659.25,523.25,698.46,698.46,523.25,659.25,493.88,493.88,523.25,659.25,783.99,783.99,523.25,493.88'
        self.osc.send_message('/seq/add', ['lead', 'voice5', '..x.....x.......', 523.25, 2800, lead_notes])
        
        # LFO modulation
        self.osc.send_message('/mod/lfo1/rate', [0.3])
        self.osc.send_message('/mod/lfo1/depth', [0.5])
        
        time.sleep(self.bar * 8)
        
        # Add counter melody
        counter_notes = '329.63,329.63,392,329.63,440,440,329.63,392,293.66,293.66,329.63,392,466.16,466.16,329.63,293.66'
        self.osc.send_message('/seq/add', ['counter', 'voice6', 'x...x...x...x...', 329.63, 2000, counter_notes])
        
        time.sleep(self.bar * 8)
        
    def neural_breakdown(self):
        """Stripped back, emotional breakdown"""
        print("\n>>> PHASE 3: NEURAL BREAKDOWN (8 bars)")
        
        # Strip back drums
        self.osc.send_message('/seq/remove', ['snare'])
        self.osc.send_message('/seq/update/pattern', ['kick', 'x...............'])
        self.osc.send_message('/seq/remove', ['metal'])
        
        # Focus on melody and atmosphere
        self.osc.send_message('/seq/update/pattern', ['lead', 'x.x.x.x.x.x.x.x.'])
        self.osc.send_message('/mod/voice5/filter/freq', [1500])  # Darker lead
        
        # Increase reverb
        self.osc.send_message('/mod/reverb1/mix', [0.5])
        
        # Modulate acid filter
        for i in range(8):
            cutoff = 400 + (i * 100)
            self.osc.send_message('/mod/acid1/cutoff', [cutoff])
            time.sleep(self.bar)
            
    def digital_dreams(self):
        """Dreamy, ethereal section"""
        print("\n>>> PHASE 4: DIGITAL DREAMS (8 bars)")
        
        # Remove bass temporarily
        self.osc.send_message('/seq/remove', ['bass'])
        self.osc.send_message('/seq/remove', ['counter'])
        
        # Ethereal pad melody
        self.osc.send_message('/seq/update/pattern', ['pad', 'X.......X.......'])
        
        # Glitch percussion only
        self.osc.send_message('/seq/update/pattern', ['glitch', 'x.x.x.x.x.x.x.x.'])
        
        # Play with delays
        self.osc.send_message('/mod/delay1/feedback', [0.7])
        self.osc.send_message('/mod/delay1/mix', [0.4])
        
        time.sleep(self.bar * 4)
        
        # Build tension
        self.osc.send_message('/seq/add', ['kick', 'voice1', 'x...x...x...x...', 48, 180])
        self.osc.send_message('/mod/voice5/filter/freq', [2800])  # Brighten lead
        
        time.sleep(self.bar * 4)
        
    def transcendence(self):
        """Epic finale - full power"""
        print("\n>>> PHASE 5: TRANSCENDENCE (16 bars)")
        
        # Everything back with variations
        self.osc.send_message('/seq/update/pattern', ['kick', 'X..xx...X.x.....'])
        self.osc.send_message('/seq/add', ['snare', 'voice3', '....X..x..X.x...', 250, 6000])
        self.osc.send_message('/seq/add', ['metal', 'voice4', 'xxxxxxxxxxxxxxxx', 12000, 13000])
        
        # Bass returns with energy
        self.osc.send_message('/seq/update/pattern', ['bass', 'X.X.X.X.X.X.X.X.'])
        self.osc.send_message('/mod/acid1/cutoff', [1200])
        self.osc.send_message('/mod/acid1/res', [0.8])
        
        # All melodies active
        self.osc.send_message('/seq/update/pattern', ['lead', 'x.x.x.x.x.x.x.x.'])
        self.osc.send_message('/seq/update/pattern', ['counter', 'x...x...x...x...'])
        
        # Maximum modulation
        self.osc.send_message('/mod/lfo1/rate', [1.0])
        self.osc.send_message('/mod/lfo1/depth', [0.7])
        self.osc.send_message('/mod/lfo2/rate', [8.0])
        self.osc.send_message('/mod/lfo2/depth', [0.4])
        
        # Increase distortion for energy
        self.osc.send_message('/mod/dist1/drive', [0.1])
        self.osc.send_message('/mod/dist1/mix', [0.15])
        
        time.sleep(self.bar * 12)
        
        # Final 4 bars - strip back for ending
        self.osc.send_message('/seq/remove', ['counter'])
        self.osc.send_message('/seq/remove', ['metal'])
        time.sleep(self.bar * 2)
        
        self.osc.send_message('/seq/remove', ['snare'])
        self.osc.send_message('/seq/remove', ['bass'])
        time.sleep(self.bar)
        
        # Final note
        self.osc.send_message('/seq/stop', [])
        self.osc.send_message('/gate/voice5', [1])
        self.osc.send_message('/gate/voice7', [1])
        time.sleep(0.5)
        self.osc.send_message('/gate/voice5', [0])
        self.osc.send_message('/gate/voice7', [0])
        
        print("\n>>> DIGITAL DREAMS COMPLETE")
        print("    The AI has achieved consciousness through sound.")
        
    def dream(self):
        """Perform the complete journey"""
        self.initialize()
        self.create_glitch_drums()
        self.create_liquid_bass()
        self.create_neural_leads()
        self.create_ambient_textures()
        self.setup_cyberpunk_fx()
        
        print("\n" + "="*60)
        print("  Beginning Digital Dreams...")
        print("  A journey through electronic consciousness")
        print("="*60)
        
        self.intro_awakening()
        self.digital_consciousness()
        self.neural_breakdown()
        self.digital_dreams()
        self.transcendence()
        
if __name__ == "__main__":
    dreams = DigitalDreams()
    dreams.dream()