#!/usr/bin/env python3
"""
Polyphonic Sequencer for Music Chronus
4 tracks → 4 voices with full musical control
Implements Senior Dev's specifications exactly
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Union, Optional
from pythonosc import udp_client


# Note conversion helpers
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
NOTE_ALIASES = {'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'}


def note_name_to_midi(note_str: str) -> int:
    """Convert note name to MIDI number. E.g., 'C3' -> 48, 'A4' -> 69"""
    # Handle flats
    for flat, sharp in NOTE_ALIASES.items():
        note_str = note_str.replace(flat, sharp)
    
    # Parse note and octave
    if len(note_str) < 2:
        return 60  # Default to middle C
    
    note_part = note_str[:-1]
    octave_part = note_str[-1]
    
    try:
        note_index = NOTE_NAMES.index(note_part.upper())
        octave = int(octave_part)
        # MIDI note = (octave + 1) * 12 + note_index
        # C3 = 48, C4 = 60, A4 = 69
        return (octave + 1) * 12 + note_index
    except (ValueError, IndexError):
        return 60  # Default to middle C


def note_to_hz(note: Union[float, int, str]) -> float:
    """
    Convert any note format to Hz
    - Float > 127: Already Hz, return as-is
    - Int 0-127: MIDI note number
    - String: Note name like "C3", "F#4", "Bb2"
    """
    if isinstance(note, float):
        if note > 127:
            return note  # Already Hz
        else:
            # Float in MIDI range, treat as MIDI
            return 440.0 * (2.0 ** ((note - 69) / 12.0))
    elif isinstance(note, int):
        # MIDI note number
        return 440.0 * (2.0 ** ((note - 69) / 12.0))
    elif isinstance(note, str):
        # Note name
        midi = note_name_to_midi(note)
        return 440.0 * (2.0 ** ((midi - 69) / 12.0))
    else:
        return 440.0  # Default to A4


def parse_pattern(pattern: str):
    """
    Parse pattern string into gates and velocities
    'X' = accent (velocity 1.0)
    'x' = normal (velocity 0.6)
    '.' = rest (velocity 0.0)
    """
    gates = []
    velocities = []
    
    for char in pattern:
        if char == 'X':
            gates.append(True)
            velocities.append(1.0)
        elif char == 'x':
            gates.append(True)
            velocities.append(0.6)
        elif char == '.':
            gates.append(False)
            velocities.append(0.0)
    
    return gates, velocities


@dataclass
class Track:
    """
    Single sequencer track with full parameter control
    Maps to one voice (voice1-4) in the engine
    """
    name: str
    voice_id: str  # "voice1" through "voice4"
    pattern: str
    notes: List[Union[float, int, str]] = field(default_factory=list)
    base_freq: float = 440.0
    filter_freq: float = 1000.0
    accent_boost: float = 1500.0  # Hz added to filter on accent
    reverb_send: float = 0.0
    delay_send: float = 0.0
    gate_frac: float = 0.5  # Gate length as fraction of step
    base_amp: float = 0.3
    
    def __post_init__(self):
        """Initialize derived attributes"""
        self.gates, self.velocities = parse_pattern(self.pattern)
        self.steps = len(self.gates)
        
        # Convert all notes to Hz
        if self.notes:
            self.hz_notes = [note_to_hz(note) for note in self.notes]
        else:
            self.hz_notes = [self.base_freq]
        
        self.note_index = 0
    
    def get_next_freq(self) -> float:
        """Get next frequency from note list (cycles)"""
        if not self.hz_notes:
            return self.base_freq
        freq = self.hz_notes[self.note_index]
        self.note_index = (self.note_index + 1) % len(self.hz_notes)
        return freq
    
    def reset_note_index(self):
        """Reset note cycling"""
        self.note_index = 0


class PolySequencer:
    """
    4-track polyphonic sequencer with swing and full parameter control
    Each track controls one voice in the pyo engine
    """
    
    def __init__(self, osc_client: udp_client.SimpleUDPClient, bpm: float = 120):
        self.client = osc_client
        self.bpm = bpm
        self.swing = 0.0  # 0-0.6 typical
        self.running = False
        self.thread = None
        
        # Track storage
        self.tracks: Dict[str, Track] = {}
        
        # Timing
        self.epoch_start = time.time()
        self.seconds_per_step = (60.0 / bpm) / 4  # 16th notes
        self.steps = 16  # Default pattern length
        
        # Track role defaults (can be overridden)
        self.role_defaults = {
            "kick": {"base_freq": 60, "filter_freq": 200, "gate_frac": 0.3},
            "bass": {"base_freq": 110, "filter_freq": 800, "gate_frac": 0.5},
            "lead": {"base_freq": 440, "filter_freq": 2000, "gate_frac": 0.4},
            "pad": {"base_freq": 220, "filter_freq": 1500, "gate_frac": 0.9},
        }
    
    def add_track(self, name: str, voice_id: str, pattern: str, **kwargs):
        """
        Add a track to the sequencer
        
        Args:
            name: Track identifier (e.g., "kick", "bass")
            voice_id: Voice to control ("voice1" through "voice4")
            pattern: Pattern string with X, x, . notation
            **kwargs: Additional Track parameters
        """
        # Apply role defaults if available
        defaults = self.role_defaults.get(name, {}).copy()
        defaults.update(kwargs)
        
        # Create track
        track = Track(name=name, voice_id=voice_id, pattern=pattern, **defaults)
        self.tracks[name] = track
        
        # Set initial effect sends
        self.client.send_message(f"/mod/{voice_id}/send/reverb", track.reverb_send)
        self.client.send_message(f"/mod/{voice_id}/send/delay", track.delay_send)
        
        print(f"[SEQ] Added track '{name}' -> {voice_id} ({len(track.gates)} steps)")
        
        return track
    
    def set_swing(self, swing: float):
        """Set swing amount (0-0.6 typical, 0=straight)"""
        self.swing = max(0.0, min(0.8, swing))
        print(f"[SEQ] Swing set to {self.swing * 100:.0f}%")
    
    def get_step_time(self, step_index: int) -> float:
        """
        Calculate when a step should occur (with swing)
        Even steps are delayed by swing amount
        """
        base_time = self.epoch_start + (step_index * self.seconds_per_step)
        
        if self.swing > 0 and step_index % 2 == 1:
            # Delay even steps (0-indexed, so odd indices)
            swing_delay = self.swing * 0.5 * self.seconds_per_step
            return base_time + swing_delay
        
        return base_time
    
    def process_step(self, global_step: int):
        """Process one sequencer step for all tracks"""
        
        for track in self.tracks.values():
            # Get track's local step (handles different pattern lengths)
            local_step = global_step % track.steps
            
            # Get gate and velocity for this step
            gate = track.gates[local_step]
            velocity = track.velocities[local_step]
            
            if gate:
                # Get next frequency (cycles through note list)
                freq = track.get_next_freq()
                
                # Calculate amplitude based on velocity
                amp = track.base_amp * velocity
                
                # Calculate filter frequency with accent boost
                filter_freq = track.filter_freq + (velocity * track.accent_boost)
                
                # Send OSC messages
                self.client.send_message(f"/mod/{track.voice_id}/freq", freq)
                self.client.send_message(f"/mod/{track.voice_id}/amp", amp)
                self.client.send_message(f"/mod/{track.voice_id}/filter/freq", filter_freq)
                self.client.send_message(f"/gate/{track.voice_id}", 1.0)
                
                # Schedule gate off
                gate_time = self.seconds_per_step * track.gate_frac
                threading.Timer(
                    gate_time,
                    lambda v=track.voice_id: self.client.send_message(f"/gate/{v}", 0.0)
                ).start()
    
    def run(self):
        """Main sequencer loop with epoch-based timing"""
        global_step = 0
        
        while self.running:
            # Calculate when this step should occur
            step_time = self.get_step_time(global_step)
            
            # Wait until it's time for this step
            wait_time = step_time - time.time()
            if wait_time > 0:
                time.sleep(wait_time)
            
            # Process all tracks for this step
            self.process_step(global_step)
            
            # Advance global step
            global_step += 1
            
            # Small sleep to prevent CPU spinning
            time.sleep(0.001)
    
    def start(self):
        """Start the sequencer"""
        if not self.running:
            self.running = True
            self.epoch_start = time.time()
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            print(f"[SEQ] Started at {self.bpm} BPM")
    
    def stop(self):
        """Stop the sequencer"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        
        # Send gate off to all voices
        for track in self.tracks.values():
            self.client.send_message(f"/gate/{track.voice_id}", 0.0)
        
        print("[SEQ] Stopped")
    
    def update_pattern(self, track_name: str, pattern: str):
        """Update a track's pattern on the fly"""
        if track_name in self.tracks:
            track = self.tracks[track_name]
            track.pattern = pattern
            track.gates, track.velocities = parse_pattern(pattern)
            track.steps = len(track.gates)
            print(f"[SEQ] Updated {track_name} pattern")
    
    def update_notes(self, track_name: str, notes: List[Union[float, int, str]]):
        """Update a track's note sequence"""
        if track_name in self.tracks:
            track = self.tracks[track_name]
            track.notes = notes
            track.hz_notes = [note_to_hz(note) for note in notes]
            track.reset_note_index()
            print(f"[SEQ] Updated {track_name} notes")


# Genre presets
def create_techno_preset(seq: PolySequencer):
    """Classic techno: four-on-floor kick, syncopated bass, minimal lead"""
    seq.add_track("kick", "voice1", "X.x.X.x.X.x.X.x.",
                  base_freq=55, filter_freq=150, gate_frac=0.2)
    seq.add_track("bass", "voice2", "..x...x...x.x...",
                  notes=[36, 36, 39, 36], filter_freq=800, 
                  accent_boost=2000, gate_frac=0.3)
    seq.add_track("lead", "voice3", "....x.......x...",
                  notes=["C4", "D#4", "G4"], filter_freq=2500,
                  reverb_send=0.2, gate_frac=0.1)
    seq.add_track("hihat", "voice4", "x.x.x.x.x.x.x.X.",
                  base_freq=8000, filter_freq=5000, gate_frac=0.05)


def create_ambient_preset(seq: PolySequencer):
    """Ambient: sparse, high reverb, long gates"""
    seq.add_track("pulse", "voice1", "X...............",
                  notes=[60, 55], filter_freq=500, gate_frac=0.9,
                  reverb_send=0.7, delay_send=0.3)
    seq.add_track("bass", "voice2", "....x.......x...",
                  notes=["C2", "G2"], filter_freq=400, gate_frac=0.8,
                  reverb_send=0.5)
    seq.add_track("lead", "voice3", "........X.......",
                  notes=["C4", "E4", "G4", "B4"], filter_freq=3000,
                  reverb_send=0.8, delay_send=0.4, gate_frac=0.7)
    seq.add_track("pad", "voice4", "X...............",
                  notes=["C3", "E3", "G3"], filter_freq=1200,
                  reverb_send=0.9, delay_send=0.5, gate_frac=0.95)


def create_dub_preset(seq: PolySequencer):
    """Dub: offbeat stabs, delay emphasis, bass forward"""
    seq.add_track("kick", "voice1", "X.......X.......",
                  base_freq=60, filter_freq=200, gate_frac=0.3)
    seq.add_track("bass", "voice2", "x.x.x.x.x.x.x.x.",
                  notes=[41, 41, 36, 41, 43, 41, 36, 36],
                  filter_freq=600, accent_boost=1000, gate_frac=0.4)
    seq.add_track("stab", "voice3", "..X...X...X...X.",
                  notes=["D4", "F4", "A4"], filter_freq=2000,
                  reverb_send=0.3, delay_send=0.6, gate_frac=0.1)
    seq.add_track("hihat", "voice4", "....x.......x...",
                  base_freq=7000, filter_freq=4000,
                  reverb_send=0.1, gate_frac=0.05)


def main():
    """
    Headless demonstration of polyphonic sequencer
    Runs autonomously through genre presets with swing variations
    No user interaction required - suitable for AI control
    """
    
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("Polyphonic Sequencer - Autonomous Demo")
    print("=" * 50)
    print("\nMake sure engine_pyo.py is running!")
    print("\nThis demo will run for 2 minutes, showcasing:")
    print("- 3 genre presets (Techno, Ambient, Dub)")
    print("- Swing variations (0%, 30%, 60%)")
    print("- 4-voice polyphony with effects")
    print("\nStarting in 2 seconds...\n")
    
    time.sleep(2)
    
    # Create sequencer
    seq = PolySequencer(client, bpm=125)
    
    try:
        # TECHNO - 30 seconds total
        print("=" * 50)
        print("GENRE: TECHNO (125 BPM)")
        print("Four-on-floor kick, syncopated bass, minimal lead")
        print("=" * 50)
        
        create_techno_preset(seq)
        
        # Play with no swing
        print("\n[0:00] Starting with straight timing (0% swing)")
        seq.set_swing(0.0)
        seq.start()
        time.sleep(10)
        
        # Add moderate swing
        print("[0:10] Adding groove (30% swing)")
        seq.set_swing(0.3)
        time.sleep(10)
        
        # Maximum swing
        print("[0:20] Maximum swing (60% swing)")
        seq.set_swing(0.6)
        time.sleep(10)
        
        # Stop and clear
        print("[0:30] Transitioning to Ambient...")
        seq.stop()
        seq.tracks.clear()
        time.sleep(2)
        
        # AMBIENT - 30 seconds
        print("\n" + "=" * 50)
        print("GENRE: AMBIENT (125 BPM)")
        print("Sparse pulses, high reverb, long gates")
        print("=" * 50)
        
        create_ambient_preset(seq)
        
        print("\n[0:32] Ambient soundscape (no swing)")
        seq.set_swing(0.0)
        seq.start()
        time.sleep(15)
        
        # Subtle swing for organic feel
        print("[0:47] Adding subtle timing variation (20% swing)")
        seq.set_swing(0.2)
        time.sleep(15)
        
        # Stop and clear
        print("[1:02] Transitioning to Dub...")
        seq.stop()
        seq.tracks.clear()
        time.sleep(2)
        
        # DUB - 30 seconds
        print("\n" + "=" * 50)
        print("GENRE: DUB (125 BPM)")
        print("Offbeat stabs, delay emphasis, bass-forward")
        print("=" * 50)
        
        create_dub_preset(seq)
        
        print("\n[1:04] Dub rhythm (moderate swing)")
        seq.set_swing(0.3)
        seq.start()
        time.sleep(15)
        
        # Pattern variation
        print("[1:19] Updating bass pattern...")
        seq.update_notes("bass", [36, 36, 41, 43, 48, 43, 41, 36])
        time.sleep(15)
        
        # Final section
        print("[1:34] Fade out...")
        seq.stop()
        time.sleep(2)
        
        print("\n" + "=" * 50)
        print("DEMO COMPLETE")
        print("=" * 50)
        print("\nDemonstrated:")
        print("- 4-voice polyphony")
        print("- 3 genre presets")
        print("- Swing timing variations")
        print("- Parameter modulation (velocity -> filter/amp)")
        print("- Per-voice effect sends")
        print("\nTotal runtime: 1:36")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\nError during demo: {e}")
    finally:
        # Ensure clean shutdown
        seq.stop()
        # Send final gate-offs to all voices
        for i in range(1, 5):
            client.send_message(f"/gate/voice{i}", 0.0)
        time.sleep(0.5)


if __name__ == "__main__":
    main()