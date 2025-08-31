#!/usr/bin/env python3
"""
Live Music Interface - Controllable through tmux
"""

import numpy as np
from scipy.io import wavfile
import subprocess
import time
import sys
import os

class LiveComposer:
    def __init__(self):
        self.sr = 44100
        self.notes = {
            'C': 261.63, 'C#': 277.18, 'D': 293.66, 'D#': 311.13,
            'E': 329.63, 'F': 349.23, 'F#': 369.99, 'G': 392.00,
            'G#': 415.30, 'A': 440.00, 'A#': 466.16, 'B': 493.88
        }
        
    def sine(self, freq, duration, amp=0.3):
        t = np.linspace(0, duration, int(self.sr * duration))
        return amp * np.sin(2 * np.pi * freq * t)
    
    def play(self, sound):
        # Normalize and convert
        sound = np.clip(sound, -1, 1)
        sound_int = (sound * 32767).astype(np.int16)
        
        # Save and play
        temp = '/tmp/live_sound.wav'
        wavfile.write(temp, self.sr, sound_int)
        subprocess.run(['paplay', temp], 
                      env={'PULSE_SERVER': 'tcp:172.21.240.1:4713'})
    
    def parse_command(self, cmd):
        """Parse simple music commands
        note C 0.5  - play C for 0.5 seconds
        chord C E G - play chord
        seq C D E F - play sequence
        """
        parts = cmd.strip().split()
        if not parts:
            return
        
        action = parts[0].lower()
        
        if action == 'note' and len(parts) >= 2:
            note = parts[1].upper()
            duration = float(parts[2]) if len(parts) > 2 else 0.5
            if note in self.notes:
                freq = self.notes[note]
                sound = self.sine(freq, duration)
                self.play(sound)
                print(f"♪ {note} ({freq:.1f}Hz)")
                
        elif action == 'chord' and len(parts) >= 2:
            chord_notes = [n.upper() for n in parts[1:]]
            sounds = []
            freqs = []
            for note in chord_notes:
                if note in self.notes:
                    freq = self.notes[note]
                    freqs.append(freq)
                    sounds.append(self.sine(freq, 1.0, amp=0.2))
            
            if sounds:
                chord = np.sum(sounds, axis=0) / len(sounds)
                self.play(chord)
                print(f"♫ Chord: {' '.join(chord_notes)}")
                
        elif action == 'seq' and len(parts) >= 2:
            sequence = []
            for note in parts[1:]:
                if note.upper() in self.notes:
                    freq = self.notes[note.upper()]
                    sequence.append(self.sine(freq, 0.3))
                    
            if sequence:
                full_seq = np.concatenate(sequence)
                self.play(full_seq)
                print(f"♩♪♫ Sequence: {' '.join(parts[1:])}")
                
        elif action == 'help':
            print("Commands:")
            print("  note C [duration] - Play a single note")
            print("  chord C E G      - Play a chord")
            print("  seq C D E F      - Play a sequence")
            print("  quit             - Exit")
        
        elif action == 'quit':
            return False
            
        return True

def main():
    print("="*50)
    print("LIVE MUSIC INTERFACE")
    print("="*50)
    print("Commands: note, chord, seq, help, quit")
    print("-"*50)
    
    composer = LiveComposer()
    
    # Check for command line args
    if len(sys.argv) > 1:
        # Single command mode
        cmd = ' '.join(sys.argv[1:])
        composer.parse_command(cmd)
    else:
        # Interactive mode
        print("Ready for music commands...")
        while True:
            try:
                cmd = input("♪ > ")
                if not composer.parse_command(cmd):
                    break
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
    
    print("\nGoodbye!")

if __name__ == "__main__":
    main()