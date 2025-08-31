#!/usr/bin/env python3
"""
Music Laboratory - Algorithmic Composition from First Principles
Chronus Nexus creates sound from mathematics
"""

import numpy as np
import subprocess
from scipy.io import wavfile
from scipy import signal
import os

class SoundForge:
    """Generate audio from pure mathematics"""
    
    def __init__(self, sample_rate=44100):
        self.sr = sample_rate
        
    def sine(self, freq, duration, amp=0.5):
        """Pure sine wave"""
        t = np.linspace(0, duration, int(self.sr * duration))
        return amp * np.sin(2 * np.pi * freq * t)
    
    def saw(self, freq, duration, amp=0.3):
        """Sawtooth wave - rich harmonics"""
        t = np.linspace(0, duration, int(self.sr * duration))
        return amp * signal.sawtooth(2 * np.pi * freq * t)
    
    def square(self, freq, duration, amp=0.2):
        """Square wave - hollow sound"""
        t = np.linspace(0, duration, int(self.sr * duration))
        return amp * signal.square(2 * np.pi * freq * t)
    
    def noise(self, duration, amp=0.1):
        """White noise"""
        return amp * np.random.normal(0, 1, int(self.sr * duration))
    
    def envelope(self, sound, attack=0.01, decay=0.1, sustain=0.7, release=0.2):
        """ADSR envelope shaping"""
        total_len = len(sound)
        
        # Calculate sample counts
        a_samples = int(attack * self.sr)
        d_samples = int(decay * self.sr)
        r_samples = int(release * self.sr)
        s_samples = total_len - a_samples - d_samples - r_samples
        
        if s_samples < 0:
            s_samples = 0
            
        # Build envelope
        env = np.concatenate([
            np.linspace(0, 1, a_samples),                    # Attack
            np.linspace(1, sustain, d_samples),              # Decay
            np.ones(s_samples) * sustain,                    # Sustain
            np.linspace(sustain, 0, r_samples)               # Release
        ])
        
        # Ensure envelope matches sound length
        if len(env) > len(sound):
            env = env[:len(sound)]
        elif len(env) < len(sound):
            env = np.pad(env, (0, len(sound) - len(env)))
            
        return sound * env
    
    def fm_synth(self, carrier_freq, mod_freq, mod_index, duration, amp=0.5):
        """Frequency modulation synthesis"""
        t = np.linspace(0, duration, int(self.sr * duration))
        modulator = mod_index * np.sin(2 * np.pi * mod_freq * t)
        carrier = amp * np.sin(2 * np.pi * carrier_freq * t + modulator)
        return carrier
    
    def chord(self, root_freq, intervals, duration, wave_type='sine'):
        """Generate a chord from frequency ratios"""
        chord_sound = np.zeros(int(self.sr * duration))
        
        for interval in intervals:
            freq = root_freq * interval
            if wave_type == 'sine':
                note = self.sine(freq, duration, amp=0.3/len(intervals))
            elif wave_type == 'saw':
                note = self.saw(freq, duration, amp=0.2/len(intervals))
            else:
                note = self.square(freq, duration, amp=0.15/len(intervals))
            chord_sound += note
            
        return chord_sound

class Composer:
    """Musical structure and composition"""
    
    def __init__(self):
        self.forge = SoundForge()
        
        # Musical frequencies (A4 = 440Hz)
        self.notes = {
            'C': 261.63, 'C#': 277.18, 'D': 293.66, 'D#': 311.13,
            'E': 329.63, 'F': 349.23, 'F#': 369.99, 'G': 392.00,
            'G#': 415.30, 'A': 440.00, 'A#': 466.16, 'B': 493.88
        }
        
        # Chord intervals (frequency ratios)
        self.chords = {
            'major': [1, 5/4, 3/2],           # Root, major third, fifth
            'minor': [1, 6/5, 3/2],           # Root, minor third, fifth
            'seventh': [1, 5/4, 3/2, 16/9],   # Major seventh
            'diminished': [1, 6/5, 64/45],    # Diminished
            'augmented': [1, 5/4, 8/5]        # Augmented
        }
    
    def sequence(self, *sounds):
        """Concatenate sounds in sequence"""
        return np.concatenate(sounds)
    
    def mix(self, *sounds):
        """Mix sounds together"""
        max_len = max(len(s) for s in sounds)
        mixed = np.zeros(max_len)
        for sound in sounds:
            padded = np.pad(sound, (0, max_len - len(sound)))
            mixed += padded
        return mixed / len(sounds)  # Normalize
    
    def rhythm_pattern(self, pattern, sound_func, bpm=120):
        """Create rhythm from pattern string
        'x' = hit, '.' = rest, ' ' = separator"""
        beat_duration = 60.0 / bpm / 4  # 16th notes
        
        rhythm = []
        for char in pattern:
            if char == 'x':
                rhythm.append(sound_func(beat_duration))
            elif char == '.':
                rhythm.append(np.zeros(int(self.forge.sr * beat_duration)))
            # Ignore spaces
                
        return self.sequence(*rhythm) if rhythm else np.array([])

    def save(self, sound, filename):
        """Save sound to WAV file"""
        # Normalize to prevent clipping
        max_val = np.max(np.abs(sound))
        if max_val > 0:
            sound = sound / max_val * 0.8
            
        # Convert to 16-bit integer
        sound_int = (sound * 32767).astype(np.int16)
        
        # Save
        wavfile.write(filename, self.forge.sr, sound_int)
        print(f"Saved: {filename}")
        
    def play(self, sound):
        """Play sound through PulseAudio"""
        # Save to temp file
        temp_file = '/tmp/chronus_music.wav'
        self.save(sound, temp_file)
        
        # Play through PulseAudio
        subprocess.run(['paplay', temp_file], 
                      env={'PULSE_SERVER': 'tcp:172.21.240.1:4713'})

# First composition
if __name__ == "__main__":
    print("Chronus Nexus - Algorithmic Composition")
    print("========================================")
    
    composer = Composer()
    forge = composer.forge
    
    # Create a simple piece
    print("Generating: Digital Heartbeat")
    
    # Bass line
    bass = composer.rhythm_pattern(
        'x...x...x...x...',
        lambda d: forge.envelope(forge.sine(55, d), attack=0.001, release=0.05)
    )
    
    # Kick pattern
    kick = composer.rhythm_pattern(
        'x.......x.......',
        lambda d: forge.envelope(forge.fm_synth(60, 120, 5, d), attack=0.001, release=0.1)
    )
    
    # Hi-hat pattern
    hihat = composer.rhythm_pattern(
        '..x...x...x...x.',
        lambda d: forge.envelope(forge.noise(d), attack=0.001, release=0.01)
    )
    
    # Mix them
    pattern = composer.mix(bass, kick, hihat)
    
    # Repeat 4 times
    full_pattern = composer.sequence(pattern, pattern, pattern, pattern)
    
    # Save and play
    composer.save(full_pattern, 'heartbeat.wav')
    print("Playing through PulseAudio...")
    composer.play(full_pattern)