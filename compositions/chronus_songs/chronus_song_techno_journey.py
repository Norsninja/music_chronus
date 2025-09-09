#!/usr/bin/env python3
"""
'Techno Journey' - An original composition by Chronus Nexus
A progressive techno track that builds from minimal to epic
Duration: ~2 minutes
"""

from pythonosc import udp_client
import time
import random

class TechnoJourney:
    def __init__(self):
        self.osc = udp_client.SimpleUDPClient('127.0.0.1', 5005)
        self.bpm = 128
        
    def setup_initial_parameters(self):
        """Initialize all parameters to known state"""
        print("== 'Techno Journey' by Chronus Nexus ==")
        print("Initializing synthesizer...")
        
        # Reset everything
        self.osc.send_message('/seq/stop', [])
        self.osc.send_message('/seq/clear', [])
        
        # Set initial voice parameters
        for i in range(1, 5):
            self.osc.send_message(f'/gate/voice{i}', 0)
            self.osc.send_message(f'/mod/voice{i}/amp', 0.3)
            self.osc.send_message(f'/mod/voice{i}/adsr/attack', 0.01)
            self.osc.send_message(f'/mod/voice{i}/adsr/decay', 0.1)
            self.osc.send_message(f'/mod/voice{i}/adsr/sustain', 0.7)
            self.osc.send_message(f'/mod/voice{i}/adsr/release', 0.2)
            
        # Start with clean effects
        self.osc.send_message('/mod/reverb1/mix', 0.1)
        self.osc.send_message('/mod/reverb1/room', 0.3)
        self.osc.send_message('/mod/delay1/time', 0.375)  # Dotted eighth
        self.osc.send_message('/mod/delay1/feedback', 0.3)
        self.osc.send_message('/mod/delay1/mix', 0)
        self.osc.send_message('/mod/dist1/drive', 0)
        self.osc.send_message('/mod/dist1/mix', 0)
        
        # Setup acid filter for voice2
        self.osc.send_message('/mod/acid1/cutoff', 200)
        self.osc.send_message('/mod/acid1/res', 0.3)
        self.osc.send_message('/mod/acid1/env_amount', 1000)
        self.osc.send_message('/mod/acid1/decay', 0.2)
        
        # LFOs off initially
        self.osc.send_message('/mod/lfo1/depth', 0)
        self.osc.send_message('/mod/lfo2/depth', 0)
        
        print("Ready to begin journey...")
        time.sleep(1)
        
    def intro_minimal(self):
        """Bars 1-8: Minimal kick pattern"""
        print("\n[INTRO] Bars 1-8: The journey begins...")
        
        # Just kick drum
        self.osc.send_message('/seq/add', ['kick', 'voice1', 'X...X...X...X...', 50, 100])
        self.osc.send_message('/mod/voice1/adsr/attack', 0.001)
        self.osc.send_message('/mod/voice1/adsr/decay', 0.05)
        self.osc.send_message('/mod/voice1/adsr/release', 0.1)
        
        self.osc.send_message('/seq/bpm', self.bpm)
        self.osc.send_message('/seq/start', [])
        
        # Gradually open filter
        for i in range(8):
            self.osc.send_message('/mod/voice1/filter/freq', 100 + (i * 50))
            time.sleep(2)  # 2 seconds per bar at 128 BPM
            
    def add_bass(self):
        """Bars 9-16: Add rolling bassline"""
        print("\n[BUILD] Bars 9-16: Bass enters...")
        
        # Add acid bassline
        self.osc.send_message('/seq/add', ['bass', 'voice2', 'x.x.x.x.X.x.x.X.', 110, 800])
        self.osc.send_message('/mod/voice2/amp', 0.35)
        
        # Gradually increase acid resonance
        for i in range(8):
            res = 0.3 + (i * 0.05)
            self.osc.send_message('/mod/acid1/res', min(0.8, res))
            self.osc.send_message('/mod/acid1/cutoff', 200 + (i * 100))
            
            # Add subtle LFO wobble halfway through
            if i == 4:
                self.osc.send_message('/mod/lfo1/rate', 0.25)
                self.osc.send_message('/mod/lfo1/depth', 0.3)
                
            time.sleep(2)
            
    def add_percussion(self):
        """Bars 17-24: Hi-hats and percussion"""
        print("\n[PERCUSSION] Bars 17-24: Rhythm intensifies...")
        
        # Add hi-hats
        self.osc.send_message('/seq/add', ['hats', 'voice3', '..x...x...x...x.', 4000, 8000])
        self.osc.send_message('/mod/voice3/amp', 0.15)
        self.osc.send_message('/mod/voice3/adsr/attack', 0.001)
        self.osc.send_message('/mod/voice3/adsr/decay', 0.02)
        self.osc.send_message('/mod/voice3/adsr/release', 0.05)
        
        # Open hats pattern
        self.osc.send_message('/seq/add', ['open', 'voice4', '....X.......X...', 6000, 10000])
        self.osc.send_message('/mod/voice4/amp', 0.1)
        self.osc.send_message('/mod/voice4/adsr/decay', 0.3)
        self.osc.send_message('/mod/voice4/adsr/release', 0.4)
        
        # Add reverb to percussion
        self.osc.send_message('/mod/voice3/send/reverb', 0.2)
        self.osc.send_message('/mod/voice4/send/reverb', 0.4)
        
        # Gradually add delay
        for i in range(8):
            self.osc.send_message('/mod/delay1/mix', i * 0.02)
            self.osc.send_message('/mod/voice3/send/delay', i * 0.03)
            
            # Speed up hi-hats midway
            if i == 4:
                self.osc.send_message('/seq/update/pattern', ['hats', 'x.x.x.x.x.x.x.x.'])
                
            time.sleep(2)
            
    def main_drop(self):
        """Bars 25-40: Main drop with all elements"""
        print("\n[DROP] Bars 25-40: Peak energy!")
        
        # Update patterns for drop
        self.osc.send_message('/seq/update/pattern', ['kick', 'X...X...X..XX...'])
        self.osc.send_message('/seq/update/pattern', ['bass', 'XxXxXxXxXxXxXxXx'])
        self.osc.send_message('/seq/update/pattern', ['hats', 'xxxxxxxxxxxxxxxx'])
        
        # Increase energy
        self.osc.send_message('/mod/acid1/res', 0.85)
        self.osc.send_message('/mod/acid1/env_amount', 3000)
        self.osc.send_message('/mod/dist1/drive', 0.3)
        self.osc.send_message('/mod/dist1/mix', 0.3)
        
        # Add lead melody
        lead_notes = [220, 277, 330, 277, 220, 185, 220, 277]
        
        for bar in range(16):
            # Modulate lead frequency
            if bar % 2 == 0:
                note = lead_notes[bar // 2]
                self.osc.send_message('/mod/voice4/freq', note * 2)
                self.osc.send_message('/seq/update/pattern', ['open', 'X...............'])
            else:
                self.osc.send_message('/seq/update/pattern', ['open', '....X.......X...'])
                
            # Filter sweep on bass
            if bar % 4 == 0:
                self.osc.send_message('/mod/acid1/cutoff', 300)
            else:
                cutoff = 300 + (bar % 4) * 400
                self.osc.send_message('/mod/acid1/cutoff', cutoff)
                
            # Add tremolo on lead
            if bar >= 8:
                self.osc.send_message('/mod/lfo2/rate', 6.0)
                self.osc.send_message('/mod/lfo2/depth', 0.4)
                
            time.sleep(2)
            
    def breakdown(self):
        """Bars 41-48: Breakdown section"""
        print("\n[BREAKDOWN] Bars 41-48: Atmospheric break...")
        
        # Remove kick and reduce patterns
        self.osc.send_message('/seq/remove', ['kick'])
        self.osc.send_message('/seq/update/pattern', ['bass', '....X.......X...'])
        self.osc.send_message('/seq/update/pattern', ['hats', '..x...x...x...x.'])
        
        # Increase reverb and delay
        self.osc.send_message('/mod/reverb1/mix', 0.5)
        self.osc.send_message('/mod/reverb1/room', 0.8)
        self.osc.send_message('/mod/delay1/feedback', 0.6)
        self.osc.send_message('/mod/delay1/mix', 0.4)
        
        # Reduce distortion
        self.osc.send_message('/mod/dist1/mix', 0)
        
        # Slow filter sweeps
        for i in range(8):
            cutoff = 2000 - (i * 200)
            self.osc.send_message('/mod/acid1/cutoff', cutoff)
            self.osc.send_message('/mod/acid1/res', 0.4)
            time.sleep(2)
            
    def final_drop(self):
        """Bars 49-56: Final drop"""
        print("\n[FINAL DROP] Bars 49-56: Maximum energy!")
        
        # Bring everything back
        self.osc.send_message('/seq/add', ['kick', 'voice1', 'X.X.X.X.X.X.X.X.', 50, 100])
        self.osc.send_message('/seq/update/pattern', ['bass', 'XXXXXXXXXXXXXXXX'])
        self.osc.send_message('/seq/update/pattern', ['hats', 'XxXxXxXxXxXxXxXx'])
        self.osc.send_message('/seq/update/pattern', ['open', 'X.X.X.X.X.X.X.X.'])
        
        # Maximum energy
        self.osc.send_message('/mod/dist1/drive', 0.5)
        self.osc.send_message('/mod/dist1/mix', 0.5)
        self.osc.send_message('/mod/acid1/res', 0.95)
        self.osc.send_message('/mod/acid1/cutoff', 1500)
        self.osc.send_message('/mod/acid1/env_amount', 4000)
        
        # Wild filter modulation
        for i in range(8):
            self.osc.send_message('/mod/acid1/cutoff', 500 + (i % 2) * 2000)
            self.osc.send_message('/mod/lfo1/depth', 0.8)
            time.sleep(2)
            
    def outro(self):
        """Bars 57-64: Fade out"""
        print("\n[OUTRO] Bars 57-64: Journey ends...")
        
        # Gradually remove elements
        elements = ['open', 'hats', 'bass', 'kick']
        
        for i, element in enumerate(elements):
            print(f"  Removing {element}...")
            self.osc.send_message('/seq/remove', [element])
            
            # Reduce effects
            self.osc.send_message('/mod/dist1/mix', 0.5 - (i * 0.125))
            self.osc.send_message('/mod/reverb1/mix', 0.5 + (i * 0.1))
            self.osc.send_message('/mod/delay1/feedback', 0.6 + (i * 0.05))
            
            time.sleep(4)
            
        # Final fade
        print("  Final fade...")
        self.osc.send_message('/seq/stop', [])
        
        # Long reverb tail
        self.osc.send_message('/mod/reverb1/room', 0.95)
        self.osc.send_message('/mod/delay1/feedback', 0.8)
        
        time.sleep(4)
        
        # Clean up
        self.osc.send_message('/seq/clear', [])
        print("\n== Thank you for listening to 'Techno Journey' ==")
        
    def perform(self):
        """Perform the complete song"""
        self.setup_initial_parameters()
        
        # Song structure
        self.intro_minimal()      # Bars 1-8
        self.add_bass()          # Bars 9-16
        self.add_percussion()    # Bars 17-24
        self.main_drop()         # Bars 25-40
        self.breakdown()         # Bars 41-48
        self.final_drop()        # Bars 49-56
        self.outro()            # Bars 57-64
        
        print("\nTotal duration: ~2 minutes")
        print("Watch the Chronus Pet dance through the journey!")


if __name__ == "__main__":
    song = TechnoJourney()
    song.perform()