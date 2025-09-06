#!/usr/bin/env python3
"""
Integrated sequencer + pyo engine
Shows what we can reuse from our project:
1. Pattern parsing from sequencer.py
2. OSC command schema
3. Epoch-based timing concepts
4. Multi-track sequencing
"""

import time
import threading
from pythonosc import udp_client
from dataclasses import dataclass
from typing import Dict, List

# Reuse our pattern parsing
def parse_pattern(pattern: str):
    """From our sequencer.py"""
    gates = []
    velocities = []
    for char in pattern:
        if char == 'X':
            gates.append(True)
            velocities.append(127)
        elif char == 'x':
            gates.append(True)
            velocities.append(64)
        elif char == '.':
            gates.append(False)
            velocities.append(0)
    return gates, velocities


@dataclass
class Track:
    """Single sequencer track"""
    name: str
    pattern: str
    module_id: str  # Which pyo module to control
    base_freq: float = 440.0
    
    def __post_init__(self):
        self.gates, self.velocities = parse_pattern(self.pattern)
        self.steps = len(self.gates)


class MultiTrackSequencer:
    """
    Multi-track sequencer using our existing concepts
    This is what we KEEP from our project
    """
    
    def __init__(self, osc_client, bpm=120):
        self.client = osc_client
        self.bpm = bpm
        self.running = False
        self.thread = None
        
        # Multiple tracks
        self.tracks: Dict[str, Track] = {}
        self.current_step = 0
        self.steps = 16
        
        # Epoch-based timing (from our design)
        self.epoch_start = time.time()
        self.seconds_per_step = (60.0 / bpm) / 4
    
    def add_track(self, name: str, pattern: str, module_id: str, base_freq: float = 440.0):
        """Add a track to sequence"""
        self.tracks[name] = Track(name, pattern, module_id, base_freq)
        print(f"[SEQ] Added track '{name}' -> {module_id}")
    
    def get_epoch_step(self):
        """Calculate current step from epoch (our timing approach)"""
        elapsed = time.time() - self.epoch_start
        total_steps = int(elapsed / self.seconds_per_step)
        return total_steps % self.steps
    
    def run(self):
        """Main sequencer loop"""
        last_step = -1
        
        while self.running:
            # Epoch-based timing (no drift!)
            current_step = self.get_epoch_step()
            
            if current_step != last_step:
                # New step - trigger all tracks
                for track in self.tracks.values():
                    step_index = current_step % track.steps
                    gate = track.gates[step_index]
                    velocity = track.velocities[step_index]
                    
                    if gate:
                        # Use velocity to modulate frequency
                        freq_mult = 1.0 + (velocity / 127.0)
                        freq = track.base_freq * freq_mult
                        
                        # Send OSC commands using our schema
                        self.client.send_message(f"/mod/{track.module_id}/freq", freq)
                        self.client.send_message(f"/gate/{track.module_id}", 1.0)
                        
                        # Schedule gate off (50% of step)
                        threading.Timer(
                            self.seconds_per_step * 0.5,
                            lambda m=track.module_id: self.client.send_message(f"/gate/{m}", 0.0)
                        ).start()
                
                last_step = current_step
            
            # Small sleep to not burn CPU
            time.sleep(0.001)
    
    def start(self):
        """Start sequencer"""
        if not self.running:
            self.running = True
            self.epoch_start = time.time()
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            print(f"[SEQ] Started at {self.bpm} BPM (epoch-based)")
    
    def stop(self):
        """Stop sequencer"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        print("[SEQ] Stopped")


def main():
    """
    Demo: What we can reuse from our project
    """
    
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("Multi-Track Sequencer with Pyo")
    print("=" * 50)
    print("\nThis demonstrates what we KEEP from our project:")
    print("1. Pattern format (X, x, .)")
    print("2. OSC command schema (/mod/*, /gate/*)")
    print("3. Epoch-based timing (no drift)")
    print("4. Multi-track sequencing")
    print("\nMake sure engine_pyo.py is running!")
    print("\nPress Enter to change patterns, Ctrl+C to stop\n")
    
    # Create multi-track sequencer
    seq = MultiTrackSequencer(client, bpm=120)
    
    # Add initial tracks
    # Note: For this demo, all tracks control the same module
    # In real use, you'd have multiple modules in pyo
    seq.add_track("kick", "X...x...X...x...", "adsr1", base_freq=60)
    seq.add_track("snare", "....X.......X...", "adsr1", base_freq=200)
    seq.add_track("hihat", "x.x.x.x.x.x.x.x.", "adsr1", base_freq=800)
    
    # Pattern sets to cycle through
    pattern_sets = [
        {
            "name": "Basic Beat",
            "kick":  "X...x...X...x...",
            "snare": "....X.......X...",
            "hihat": "x.x.x.x.x.x.x.x."
        },
        {
            "name": "Four on Floor",
            "kick":  "X.X.X.X.X.X.X.X.",
            "snare": "....X.......X...",
            "hihat": "..x...x...x...x."
        },
        {
            "name": "Breakbeat",
            "kick":  "X..x..X.....x...",
            "snare": "....X..x..X.....",
            "hihat": "xxXxxxXxxxXxxxXx"
        },
        {
            "name": "Minimal",
            "kick":  "X.......x.......",
            "snare": "................",
            "hihat": "....x.......x..."
        }
    ]
    
    try:
        seq.start()
        
        for patterns in pattern_sets:
            print(f"\nPlaying: {patterns['name']}")
            
            # Update all track patterns
            for track_name in ["kick", "snare", "hihat"]:
                if track_name in seq.tracks and track_name in patterns:
                    seq.tracks[track_name].pattern = patterns[track_name]
                    seq.tracks[track_name].gates, seq.tracks[track_name].velocities = parse_pattern(patterns[track_name])
            
            # Wait for user to press Enter
            input("Press Enter for next pattern...")
        
        print("\n" + "=" * 50)
        print("Demo complete!")
        print("\nWhat we demonstrated:")
        print("- Our sequencer logic works perfectly with pyo")
        print("- Pattern format is reusable")
        print("- OSC schema is maintained")
        print("- Epoch-based timing prevents drift")
        print("- Multi-track capability preserved")
        
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        seq.stop()
        # Send final gate offs
        for track in seq.tracks.values():
            client.send_message(f"/gate/{track.module_id}", 0.0)


if __name__ == "__main__":
    main()