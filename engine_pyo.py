#!/usr/bin/env python3
"""
Music Chronus - Pyo Audio Engine
Polyphonic synthesizer with configurable voice count and global effects
Maintains backward compatibility with existing OSC control schema
"""

import os
import sys
import time
import threading
import json
import math
import shutil
import tempfile
from pathlib import Path
from collections import deque
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Union
from pyo import *
from pythonosc import dispatcher, osc_server, udp_client

# Import our pyo modules
from pyo_modules import Voice, ReverbBus, DelayBus
from pyo_modules.acid_working import AcidFilter  # WORKING: Final version without accent
from pyo_modules.distortion import DistortionModule  # Master insert distortion
from pyo_modules.simple_lfo import SimpleLFOModule  # Pattern-compliant LFO module
from pyo_modules.limiter import LimiterModule  # Master limiter for protection


@dataclass
class Track:
    """Represents a sequencer track"""
    name: str
    voice_id: str
    pattern: str
    notes: List[float] = None
    base_freq: float = 440.0
    base_amp: float = 0.3
    filter_freq: float = 1000.0
    accent_boost: float = 1500.0
    reverb_send: float = 0.0
    delay_send: float = 0.0
    gate_frac: float = 0.5
    note_index: int = 0
    
    def __post_init__(self):
        if self.notes is None:
            self.notes = []
    
    def get_next_freq(self) -> float:
        """Get next frequency from note list, cycling through"""
        if not self.notes:
            return self.base_freq
        freq = self.notes[self.note_index]
        self.note_index = (self.note_index + 1) % len(self.notes)
        return freq
    
    def reset_note_index(self):
        """Reset note cycling to beginning"""
        self.note_index = 0


class SequencerManager:
    """Internal sequencer driven by pyo Pattern"""
    
    def __init__(self, engine):
        self.engine = engine
        self.server = engine.server
        
        # Sequencer state
        self.tracks: Dict[str, Track] = {}
        self.bpm = 120.0
        self.swing = 0.0
        self.running = False
        self.global_step = 0
        self.epoch_start = 0.0
        
        # Timing
        self.seconds_per_step = (60.0 / self.bpm) / 4.0
        
        # Gate-off queue: List of (voice_id, due_time) tuples
        self.gate_off_queue: List[tuple] = []
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Pyo Pattern for scheduling (will be created on start)
        self.pattern = None
        
        # Pattern save/load support - bar-aligned loading
        self.pending_snapshots = []  # List of (snapshot, target_bar, timeout)
        self.pending_timeout = 10.0  # Max seconds to wait for bar alignment
        
        print("[SEQ] SequencerManager initialized")
    
    def _tick(self):
        """Main sequencer tick - called by Pattern"""
        now = time.time()
        
        # Check for pending pattern loads (bar-aligned)
        self._check_pending_snapshots()
        
        # Process gate-offs first
        with self.lock:
            while self.gate_off_queue and self.gate_off_queue[0][1] <= now:
                voice_id, _ = self.gate_off_queue.pop(0)
                if voice_id in self.engine.voices:
                    self.engine.voices[voice_id].gate(0)
                    self.engine.active_gates.discard(voice_id)
                    if self.engine.verbose:
                        print(f"[SEQ] Gate off: {voice_id}")
        
        # Get current tracks snapshot
        with self.lock:
            if not self.running:
                return
            tracks_snapshot = list(self.tracks.values())
            current_step = self.global_step
            self.global_step += 1
        
        # Process each track
        for track in tracks_snapshot:
            # Get pattern position
            pattern_index = current_step % len(track.pattern)
            char = track.pattern[pattern_index]
            
            if char in ('X', 'x'):
                # Calculate velocity
                velocity = 1.0 if char == 'X' else 0.6
                
                # Get voice
                if track.voice_id in self.engine.voices:
                    voice = self.engine.voices[track.voice_id]
                    
                    # Get frequency
                    freq = track.get_next_freq()
                    
                    # Apply parameters with velocity modulation
                    voice.set_freq(freq)
                    voice.set_amp(track.base_amp * velocity)
                    
                    # Filter modulation
                    filter_cutoff = track.filter_freq + (track.accent_boost * (velocity - 0.5))
                    voice.set_filter_freq(filter_cutoff)
                    
                    # Effects sends
                    voice.set_reverb_send(track.reverb_send)
                    voice.set_delay_send(track.delay_send)
                    
                    # Special handling for voice2/acid
                    if track.voice_id == 'voice2' and char == 'X':
                        # Set accent before gate (even though it's disabled, for future)
                        if hasattr(self.engine, 'acid1'):
                            self.engine.acid1.set_accent(1.0)
                    
                    # Trigger gate
                    voice.gate(1)
                    self.engine.active_gates.add(track.voice_id)
                    
                    # Schedule gate-off
                    gate_time = self.seconds_per_step * track.gate_frac
                    due_time = now + gate_time
                    with self.lock:
                        self.gate_off_queue.append((track.voice_id, due_time))
                        self.gate_off_queue.sort(key=lambda x: x[1])
                    
                    # Log event
                    self.engine.log_event(f"GATE_ON: {track.voice_id}")
                    
                    if self.engine.verbose:
                        print(f"[SEQ] Step {current_step}: {track.name} -> {track.voice_id} ({freq:.0f}Hz, vel={velocity:.1f})")
        
        # Calculate next tick time with swing
        step_in_bar = current_step % 16
        if self.swing > 0 and step_in_bar % 2 == 1:
            # Delay odd steps for swing
            next_time = self.seconds_per_step + (self.swing * 0.5 * self.seconds_per_step)
        else:
            next_time = self.seconds_per_step
        
        # Update Pattern time for next tick
        if self.pattern:
            self.pattern.time = next_time
    
    def add_track(self, track_id: str, voice_id: str, pattern: str, **kwargs) -> bool:
        """Add a new track"""
        with self.lock:
            # Parse any notes if provided
            notes = kwargs.pop('notes', [])
            if isinstance(notes, str):
                notes = self._parse_notes(notes)
            
            track = Track(
                name=track_id,
                voice_id=voice_id,
                pattern=pattern,
                notes=notes,
                **kwargs
            )
            self.tracks[track_id] = track
            print(f"[SEQ] Added track '{track_id}' -> {voice_id} ({len(pattern)} steps)")
            return True
    
    def remove_track(self, track_id: str) -> bool:
        """Remove a track"""
        with self.lock:
            if track_id in self.tracks:
                del self.tracks[track_id]
                print(f"[SEQ] Removed track '{track_id}'")
                return True
            return False
    
    def clear(self):
        """Clear all tracks"""
        with self.lock:
            self.tracks.clear()
            self.gate_off_queue.clear()
            print("[SEQ] Cleared all tracks")
    
    def start(self):
        """Start the sequencer"""
        with self.lock:
            if self.running:
                return
            
            self.running = True
            self.global_step = 0
            self.epoch_start = time.time()
            
            # Create Pattern with initial timing
            self.pattern = Pattern(self._tick, time=self.seconds_per_step)
            self.pattern.play()
            
            print(f"[SEQ] Started at {self.bpm} BPM")
    
    def stop(self):
        """Stop the sequencer and clear all gates"""
        with self.lock:
            if not self.running:
                return
            
            self.running = False
            
            # Stop pattern
            if self.pattern:
                self.pattern.stop()
                self.pattern = None
            
            # Clear gate-off queue
            self.gate_off_queue.clear()
        
        # Gate off all voices (outside lock to avoid deadlock)
        for voice_id in self.engine.voices:
            self.engine.voices[voice_id].gate(0)
            self.engine.active_gates.discard(voice_id)
        
        print("[SEQ] Stopped")
    
    def set_bpm(self, bpm: float):
        """Update BPM"""
        with self.lock:
            self.bpm = max(30, min(300, bpm))
            self.seconds_per_step = (60.0 / self.bpm) / 4.0
            print(f"[SEQ] BPM set to {self.bpm}")
    
    def set_swing(self, swing: float):
        """Update swing amount (0-0.6)"""
        with self.lock:
            self.swing = max(0, min(0.6, swing))
            print(f"[SEQ] Swing set to {self.swing:.1%}")
    
    def update_pattern(self, track_id: str, pattern: str):
        """Update a track's pattern"""
        with self.lock:
            if track_id in self.tracks:
                self.tracks[track_id].pattern = pattern
                print(f"[SEQ] Updated pattern for '{track_id}'")
    
    def update_notes(self, track_id: str, notes: Union[str, List]):
        """Update a track's note sequence"""
        with self.lock:
            if track_id in self.tracks:
                if isinstance(notes, str):
                    notes = self._parse_notes(notes)
                self.tracks[track_id].notes = notes
                self.tracks[track_id].reset_note_index()
                print(f"[SEQ] Updated notes for '{track_id}'")
    
    def get_status(self) -> str:
        """Get current sequencer status"""
        with self.lock:
            status = f"BPM: {self.bpm}, Swing: {self.swing:.1%}, "
            status += f"Running: {self.running}, Step: {self.global_step}, "
            status += f"Tracks: {list(self.tracks.keys())}"
            return status
    
    def _parse_notes(self, notes_str: str) -> List[float]:
        """Parse comma-separated notes (Hz, MIDI, or note names)"""
        notes = []
        for note in notes_str.split(','):
            note = note.strip()
            try:
                # Try as float (Hz)
                if '.' in note:
                    notes.append(float(note))
                # Try as MIDI note number
                elif note.isdigit():
                    midi = int(note)
                    notes.append(440.0 * (2.0 ** ((midi - 69) / 12.0)))
                # Try as note name
                else:
                    notes.append(self._note_to_freq(note))
            except:
                print(f"[SEQ] Warning: Could not parse note '{note}'")
        return notes
    
    def _note_to_freq(self, note: str) -> float:
        """Convert note name to frequency"""
        # Simple note name parser (C4 = middle C = 261.63Hz)
        note_map = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        
        # Parse note name
        base_note = note[0].upper()
        if base_note not in note_map:
            return 440.0
        
        # Parse accidentals and octave
        offset = 0
        octave = 4
        pos = 1
        
        if pos < len(note) and note[pos] in '#b':
            offset = 1 if note[pos] == '#' else -1
            pos += 1
        
        if pos < len(note):
            try:
                octave = int(note[pos:])
            except:
                pass
        
        # Calculate MIDI note number
        midi = (octave + 1) * 12 + note_map[base_note] + offset
        
        # Convert to frequency
        return 440.0 * (2.0 ** ((midi - 69) / 12.0))
    
    def snapshot(self) -> dict:
        """
        Capture complete sequencer state atomically.
        No deepcopy - manually build dict with only needed fields.
        Thread-safe with minimal lock time.
        """
        with self.lock:
            # Build tracks dict without deepcopy
            tracks_dict = {}
            for track_id, track in self.tracks.items():
                # Manual shallow copy of Track fields
                tracks_dict[track_id] = {
                    "name": track.name,
                    "voice_id": track.voice_id,
                    "pattern": track.pattern,
                    "notes": list(track.notes) if track.notes else [],  # Shallow copy of list
                    "base_freq": track.base_freq,
                    "base_amp": track.base_amp,
                    "filter_freq": track.filter_freq,
                    "accent_boost": track.accent_boost,
                    "reverb_send": track.reverb_send,
                    "delay_send": track.delay_send,
                    "gate_frac": track.gate_frac,
                    "note_index": track.note_index
                }
            
            # Return complete state
            return {
                "bpm": self.bpm,
                "swing": self.swing,
                "running": self.running,
                "global_step": self.global_step,
                "tracks": tracks_dict
            }
    
    def apply_snapshot(self, snapshot: dict, immediate: bool = False):
        """
        Restore sequencer state from snapshot.
        immediate=False: Queue for bar-aligned loading (default)
        immediate=True: Apply immediately (for testing)
        """
        if immediate:
            self._apply_snapshot_immediate(snapshot)
        else:
            with self.lock:
                # Calculate target bar (next bar boundary)
                target_bar = ((self.global_step // 16) + 1) * 16
                timeout = time.time() + self.pending_timeout
                
                # Add to pending queue (overwrites any existing pending)
                # Could check and warn if already pending
                if self.pending_snapshots:
                    print(f"[SEQ] Warning: Overwriting {len(self.pending_snapshots)} pending pattern(s)")
                
                self.pending_snapshots.append((snapshot, target_bar, timeout))
                print(f"[SEQ] Pattern queued for bar {target_bar // 16} (step {target_bar})")
    
    def _apply_snapshot_immediate(self, snapshot: dict):
        """
        Internal method to apply snapshot immediately.
        Gates off all voices first to prevent stuck notes.
        """
        # Gate off all voices first (prevent stuck notes)
        for voice_id in self.engine.voices:
            self.engine.voices[voice_id].gate(0)
        self.engine.active_gates.clear()
        
        with self.lock:
            # Clear existing tracks
            self.tracks.clear()
            self.gate_off_queue.clear()
            
            # Apply sequencer parameters
            self.bpm = snapshot.get("bpm", 120.0)
            self.swing = snapshot.get("swing", 0.0)
            self.global_step = snapshot.get("global_step", 0)
            self.running = snapshot.get("running", False)
            
            # Recalculate timing
            self.seconds_per_step = (60.0 / self.bpm) / 4.0
            
            # Recreate tracks with type coercion
            tracks_data = snapshot.get("tracks", {})
            for track_id, track_dict in tracks_data.items():
                # Type-safe Track reconstruction
                track = Track(
                    name=str(track_dict.get("name", track_id)),
                    voice_id=str(track_dict.get("voice_id", "voice1")),
                    pattern=str(track_dict.get("pattern", "." * 16)),
                    notes=[float(n) for n in track_dict.get("notes", [])],
                    base_freq=float(track_dict.get("base_freq", 440.0)),
                    base_amp=float(track_dict.get("base_amp", 0.3)),
                    filter_freq=float(track_dict.get("filter_freq", 1000.0)),
                    accent_boost=float(track_dict.get("accent_boost", 1500.0)),
                    reverb_send=float(track_dict.get("reverb_send", 0.0)),
                    delay_send=float(track_dict.get("delay_send", 0.0)),
                    gate_frac=float(track_dict.get("gate_frac", 0.5)),
                    note_index=int(track_dict.get("note_index", 0))
                )
                self.tracks[track_id] = track
            
            print(f"[SEQ] Snapshot applied: {len(self.tracks)} tracks, BPM={self.bpm}")
    
    def _check_pending_snapshots(self):
        """
        Check for pending snapshots ready to apply.
        Called from _tick() to ensure bar-aligned loading.
        """
        snapshots_to_apply = []
        current_time = time.time()
        
        with self.lock:
            remaining = []
            
            for snapshot, target_bar, timeout in self.pending_snapshots:
                if self.global_step >= target_bar:
                    # Ready to apply at bar boundary
                    snapshots_to_apply.append(snapshot)
                    print(f"[SEQ] Applying pattern at bar {self.global_step // 16}")
                elif current_time > timeout:
                    # Timeout - apply anyway
                    snapshots_to_apply.append(snapshot)
                    print(f"[SEQ] Pattern load timeout - applying immediately")
                else:
                    # Keep waiting
                    remaining.append((snapshot, target_bar, timeout))
            
            self.pending_snapshots = remaining
        
        # Apply snapshots outside lock
        for snapshot in snapshots_to_apply:
            self._apply_snapshot_immediate(snapshot)

class PyoEngine:
    """
    Headless modular synthesizer using pyo's C backend
    Compatible with existing OSC control patterns
    """
    
    def init_parameter_registry(self):
        """Initialize the parameter registry - single source of truth for all params"""
        # Track unknown routes for drift detection
        self.unknown_routes = set()
        self.registered_routes = {}
        
        # Get configurable voice count
        num_voices = int(os.environ.get('CHRONUS_NUM_VOICES', '4'))
        num_voices = max(1, min(16, num_voices))
        
        # Generate voice instances dynamically
        voice_instances = [f"voice{i}" for i in range(1, num_voices + 1)]
        
        # Base registry structure
        self.registry = {
            "version": "1.0.0",
            "engine": "pyo",
            "schema_version": "1.0",
            "modules": {
                # Voice modules (dynamic count)
                "voice": {
                    "instances": voice_instances,
                    "params": {
                        "freq": {"type": "float", "min": 20, "max": 5000, "default": 440.0, "smoothing_ms": 20, "unit": "Hz"},
                        "amp": {"type": "float", "min": 0, "max": 1, "default": 0.3, "smoothing_ms": 20},
                        "filter/freq": {"type": "float", "min": 50, "max": 8000, "default": 1000.0, "smoothing_ms": 20, "unit": "Hz"},
                        "filter/q": {"type": "float", "min": 0.5, "max": 10, "default": 2.0, "smoothing_ms": 20},
                        "adsr/attack": {"type": "float", "min": 0.001, "max": 2, "default": 0.01, "unit": "seconds"},
                        "adsr/decay": {"type": "float", "min": 0, "max": 2, "default": 0.1, "unit": "seconds"},
                        "adsr/sustain": {"type": "float", "min": 0, "max": 1, "default": 0.7},
                        "adsr/release": {"type": "float", "min": 0.01, "max": 3, "default": 0.5, "unit": "seconds"},
                        "send/reverb": {"type": "float", "min": 0, "max": 1, "default": 0.0},
                        "send/delay": {"type": "float", "min": 0, "max": 1, "default": 0.0}
                    },
                    "gates": ["gate"],
                    "notes": "4-voice polyphonic synthesis with individual ADSR and filter"
                },
                
                # Acid filter module
                "acid1": {
                    "params": {
                        "cutoff": {"type": "float", "min": 80, "max": 5000, "default": 1500.0, "unit": "Hz"},
                        "res": {"type": "float", "min": 0, "max": 0.98, "default": 0.45},
                        "env_amount": {"type": "float", "min": 0, "max": 5000, "default": 2500.0, "unit": "Hz"},
                        "decay": {"type": "float", "min": 0.02, "max": 1.0, "default": 0.25, "unit": "seconds"},
                        "accent": {"type": "float", "min": 0, "max": 1, "default": 0, "notes": "Currently disabled"},
                        "cutoff_offset": {"type": "float", "min": 0, "max": 1000, "default": 300, "unit": "Hz", "notes": "Accent boost (disabled)"},
                        "res_accent_boost": {"type": "float", "min": 0, "max": 0.4, "default": 0.2, "notes": "Accent resonance (disabled)"},
                        "accent_decay": {"type": "float", "min": 0.02, "max": 0.15, "default": 0.05, "unit": "seconds", "notes": "Accent decay (disabled)"},
                        "drive": {"type": "float", "min": 0, "max": 1, "default": 0.2},
                        "mix": {"type": "float", "min": 0, "max": 1, "default": 1.0},
                        "vol_comp": {"type": "float", "min": 0, "max": 1, "default": 0.5}
                    },
                    "gates": ["gate"],
                    "notes": "TB-303 style acid filter, processes voice2 pre-filter signal"
                },
                
                # Distortion module (master insert)
                "dist1": {
                    "params": {
                        "drive": {"type": "float", "min": 0, "max": 1, "default": 0.0, "smoothing_ms": 20, "notes": "0-0.2: warmth, 0.2-0.5: crunch, 0.5-1.0: heavy"},
                        "mix": {"type": "float", "min": 0, "max": 1, "default": 0.0, "smoothing_ms": 20, "notes": "Dry/wet with equal-loudness compensation"},
                        "tone": {"type": "float", "min": 0, "max": 1, "default": 0.5, "smoothing_ms": 20, "notes": "0=dark, 0.5=neutral, 1=bright"}
                    },
                    "notes": "Master insert distortion using pyo Disto (4x faster than tanh)"
                },
                
                # Reverb effect
                "reverb1": {
                    "params": {
                        "mix": {"type": "float", "min": 0, "max": 1, "default": 0.3},
                        "room": {"type": "float", "min": 0, "max": 1, "default": 0.5},
                        "damp": {"type": "float", "min": 0, "max": 1, "default": 0.5}
                    },
                    "notes": "Global reverb bus with per-voice sends"
                },
                
                # Delay effect
                "delay1": {
                    "params": {
                        "time": {"type": "float", "min": 0.1, "max": 0.6, "default": 0.25, "unit": "seconds"},
                        "feedback": {"type": "float", "min": 0, "max": 0.7, "default": 0.4, "notes": "Limited to prevent runaway"},
                        "mix": {"type": "float", "min": 0, "max": 1, "default": 0.3},
                        "lowcut": {"type": "float", "min": 20, "max": 1000, "default": 100, "unit": "Hz"},
                        "highcut": {"type": "float", "min": 1000, "max": 10000, "default": 5000, "unit": "Hz"}
                    },
                    "notes": "Global delay bus with filtering"
                },
                
                # LFO modules (research-optimized modulation sources)
                "lfo1": {
                    "params": {
                        "rate": {"type": "float", "min": 0.01, "max": 10.0, "default": 0.25, "smoothing_ms": 20, "unit": "Hz", "notes": "0.1-0.5: wobble, 2-8: tremolo, 4-7: vibrato"},
                        "depth": {"type": "float", "min": 0, "max": 1, "default": 0.7, "smoothing_ms": 20, "notes": "Modulation amount: 0=none, 1=full"},
                        "shape": {"type": "int", "min": 0, "max": 7, "default": 2, "notes": "0=saw↑, 1=saw↓, 2=square, 3=triangle, 4=pulse, 5=bipolar, 6=S&H, 7=mod_sine"},
                        "offset": {"type": "float", "min": -1, "max": 1, "default": 0.0, "smoothing_ms": 20, "notes": "DC offset for centering modulation"}
                    },
                    "routing": "voice2 filter cutoff (wobble bass)",
                    "notes": "Complex waveform LFO for wobble bass effects"
                },
                
                "lfo2": {
                    "params": {
                        "rate": {"type": "float", "min": 0.01, "max": 10.0, "default": 4.0, "smoothing_ms": 20, "unit": "Hz", "notes": "0.1-0.5: wobble, 2-8: tremolo, 4-7: vibrato"},
                        "depth": {"type": "float", "min": 0, "max": 1, "default": 0.3, "smoothing_ms": 20, "notes": "Modulation amount: 0=none, 1=full"},
                        "offset": {"type": "float", "min": -1, "max": 1, "default": 0.0, "smoothing_ms": 20, "notes": "DC offset for centering modulation"}
                    },
                    "routing": "voice3 amplitude (tremolo)",
                    "notes": "Sine wave LFO for smooth tremolo effects"
                }
            },
            
            "sequencer": {
                "commands": {
                    "/seq/add": {
                        "args": ["track_id", "voice_id", "pattern", "[base_freq]", "[filter_freq]", "[notes]"],
                        "description": "Add a new track to the sequencer",
                        "example": "/seq/add kick voice1 X...X...X...X... 60 200"
                    },
                    "/seq/remove": {
                        "args": ["track_id"],
                        "description": "Remove a track from the sequencer"
                    },
                    "/seq/clear": {
                        "args": [],
                        "description": "Clear all tracks"
                    },
                    "/seq/start": {
                        "args": [],
                        "description": "Start the sequencer"
                    },
                    "/seq/stop": {
                        "args": [],
                        "description": "Stop the sequencer and gate off all voices"
                    },
                    "/seq/bpm": {
                        "args": ["bpm_value"],
                        "range": [30, 300],
                        "default": 120,
                        "description": "Set sequencer BPM"
                    },
                    "/seq/swing": {
                        "args": ["swing_amount"],
                        "range": [0, 0.6],
                        "default": 0,
                        "description": "Set swing amount"
                    },
                    "/seq/update/pattern": {
                        "args": ["track_id", "new_pattern"],
                        "description": "Update a track's pattern"
                    },
                    "/seq/update/notes": {
                        "args": ["track_id", "notes_string"],
                        "description": "Update a track's note sequence"
                    },
                    "/seq/status": {
                        "args": [],
                        "description": "Get sequencer status"
                    }
                },
                "pattern_notation": {
                    "X": "Accent hit (velocity 1.0)",
                    "x": "Normal hit (velocity 0.6)",
                    ".": "Rest (no trigger)"
                }
            },
            
            "engine_commands": {
                "/engine/start": {"args": [], "description": "Start audio processing"},
                "/engine/stop": {"args": [], "description": "Stop audio processing"},
                "/engine/status": {"args": [], "description": "Print detailed status"},
                "/engine/list": {"args": [], "description": "List all modules (human-readable)"},
                "/engine/schema": {"args": ["[format]"], "description": "Get full parameter schema", "formats": ["json", "stdout", "file"]},
                "/engine/record/start": {"args": ["[filename]"], "description": "Start recording to WAV file"},
                "/engine/record/stop": {"args": [], "description": "Stop current recording"},
                "/engine/record/status": {"args": [], "description": "Get recording status"}
            }
        }
    
    def __init__(self, sample_rate=None, buffer_size=None, device_id=None):
        """Initialize pyo server with environment-aware configuration"""
        
        # Get configuration from environment or use defaults
        sample_rate = sample_rate or int(os.environ.get('CHRONUS_SAMPLE_RATE', 48000))
        buffer_size = buffer_size or int(os.environ.get('CHRONUS_BUFFER_SIZE', 256))
        device_id = device_id if device_id is not None else int(os.environ.get('CHRONUS_DEVICE_ID', -1))
        self.verbose = os.environ.get('CHRONUS_VERBOSE', '').lower() in ('1', 'true', 'yes')
        
        # Initialize parameter registry (single source of truth)
        self.init_parameter_registry()
        
        # Create pattern directory structure (Windows-safe paths)
        try:
            pattern_dirs = [
                Path("patterns") / "slots",
                Path("patterns") / "backups", 
                Path("patterns") / "library",
                Path("patterns") / "temp"
            ]
            for dir_path in pattern_dirs:
                dir_path.mkdir(parents=True, exist_ok=True)
            if self.verbose:
                print("[PATTERN] Directory structure verified")
        except OSError as e:
            print(f"[PATTERN] Warning: Could not create pattern directories: {e}")
            # Continue anyway - will fail gracefully on first save
        
        # Initialize pattern I/O lock for thread safety
        self.pattern_io_lock = threading.Lock()
        
        # Configure pyo server for Windows
        self.server = Server(
            sr=sample_rate,
            nchnls=1,  # Mono for now
            buffersize=buffer_size,
            duplex=0,  # Output only
            audio='portaudio',  # Use PortAudio backend
            winhost='wasapi'  # Windows WASAPI
        )
        
        # Set output device (AB13X USB Audio)
        if device_id >= 0:
            self.server.setOutputDevice(device_id)
        
        # Boot server but don't start yet
        self.server.boot()
        
        if self.verbose:
            print("[PYO] Available audio devices:")
            pa_list_devices()
        
        # Create voices and effects
        self.setup_voices_and_effects()
        
        # OSC server setup
        self.setup_osc_server()
        
        print(f"[PYO] Engine initialized")
        print(f"[PYO] Sample rate: {sample_rate}Hz")
        print(f"[PYO] Buffer size: {buffer_size} samples")
        print(f"[PYO] Latency: {buffer_size/sample_rate*1000:.1f}ms")
    
    def setup_voices_and_effects(self):
        """Create 4 voices, acid filter, and global effects buses"""
        
        # Get configurable voice count from environment
        num_voices = int(os.environ.get('CHRONUS_NUM_VOICES', '4'))
        num_voices = max(1, min(16, num_voices))  # Clamp between 1-16
        print(f"[PYO] Configuring {num_voices} voices")
        
        # Create N voices
        self.voices = {}
        for i in range(1, num_voices + 1):
            voice_id = f"voice{i}"
            self.voices[voice_id] = Voice(voice_id, self.server)
            print(f"[PYO] Created {voice_id}")
        
        # Create acid filter on voice2 (if it exists)
        self.acid1 = None
        if 'voice2' in self.voices:
            # Use pre-filter signal (oscillator * ADSR) as per Senior Dev's guidance
            self.acid1 = AcidFilter(
                self.voices['voice2'].get_prefilter_signal(),  # Pre-filter tap for authentic 303
                voice_id="acid1",
                server=self.server
            )
            print("[PYO] Created acid1 filter on voice2")
        else:
            print(f"[PYO] Skipping acid filter (requires voice2, have {num_voices} voices)")
        
        # Create routing and effects with proper audio signal passing
        self.setup_routing()
        
        modules_str = f"{num_voices} voices"
        if self.acid1:
            modules_str += " + acid1"
        modules_str += " + dist1 + reverb + delay"
        print(f"[PYO] Created {modules_str}")
    
    def setup_routing(self):
        """Setup signal routing: voices -> acid (voice2) -> distortion -> effects -> output"""
        # Get voice count for this session
        num_voices = len(self.voices)
        
        # Get acid output once and store it (if acid exists)
        acid_output = self.acid1.get_output() if self.acid1 else None
        
        # Build dry signals list, replacing voice2 with acid1 output if it exists
        # Dynamically handle N voices
        dry_signals = []
        for i in range(1, num_voices + 1):
            voice_id = f"voice{i}"
            if voice_id == 'voice2' and acid_output is not None:
                # voice2 replaced by acid output
                dry_signals.append(acid_output)
            else:
                dry_signals.append(self.voices[voice_id].get_dry_signal())
        
        self.dry_mix = Mix(dry_signals, voices=1)  # Mix to mono
        
        # Insert distortion as master effect after mixing, before sends
        self.dist1 = DistortionModule(self.dry_mix, module_id="dist1")
        self.distorted_mix = self.dist1.output
        print("[PYO] Created dist1 distortion module (master insert)")
        
        # Register distortion module schema
        self.register_module_schema("dist1", self.dist1.get_schema())
        
        # Build reverb sends from individual voices (pre-distortion)
        # This allows clean reverb tails even with heavy distortion
        reverb_sends = []
        for i in range(1, num_voices + 1):
            voice_id = f"voice{i}"
            if voice_id == 'voice2' and acid_output is not None:
                # acid with voice2's send level
                reverb_sends.append(acid_output * self.voices['voice2'].reverb_send)
            else:
                reverb_sends.append(self.voices[voice_id].get_reverb_send())
        
        self.reverb_input = Mix(reverb_sends, voices=1)
        
        # Build delay sends from individual voices (pre-distortion)
        delay_sends = []
        for i in range(1, num_voices + 1):
            voice_id = f"voice{i}"
            if voice_id == 'voice2' and acid_output is not None:
                # acid with voice2's send level
                delay_sends.append(acid_output * self.voices['voice2'].delay_send)
            else:
                delay_sends.append(self.voices[voice_id].get_delay_send())
        
        self.delay_input = Mix(delay_sends, voices=1)
        
        # Create effects with proper audio signal inputs (not Sig(0)!)
        self.reverb = ReverbBus(self.reverb_input, self.server)
        self.delay = DelayBus(self.delay_input, self.server)
        
        # Setup LFO modulation after all voices are created
        self.setup_lfos()
        
        # Master output: distorted dry + reverb + delay
        self.master_mix = Mix([
            self.distorted_mix,  # Now includes distortion
            self.reverb.get_output(),
            self.delay.get_output()
        ], voices=1)
        
        # Add master limiter for protection (-3dB threshold, 20:1 ratio)
        self.limiter = LimiterModule(self.master_mix, thresh=-3, ratio=20)
        self.master = self.limiter.output
        print("[PYO] Master limiter added for protection")
        
        # Send to output
        self.master.out()
        
        # Setup monitoring after master is created
        self.setup_monitoring()
        
        # Setup recording capability
        self.setup_recording()
        
        # Create integrated sequencer
        self.sequencer = SequencerManager(self)
        print("[PYO] Integrated sequencer ready")
    
    def setup_lfos(self):
        """Setup LFO modulation using proper module pattern"""
        print("[PYO] Setting up LFO modulation...")
        
        # Create LFO modules following established patterns
        self.lfo1 = SimpleLFOModule(module_id="lfo1")
        self.lfo1.set_rate(0.25)  # Default wobble rate
        self.lfo1.set_depth(0.7)  # Default 70% depth
        
        self.lfo2 = SimpleLFOModule(module_id="lfo2")
        self.lfo2.set_rate(4.0)   # Default tremolo rate
        self.lfo2.set_depth(0.3)  # Default 30% depth
        
        # Apply LFO1 to Voice2 filter (wobble bass)
        if "voice2" in self.voices:
            lfo1_scaled = self.lfo1.get_scaled_for_filter(hz_range=800)
            self.voices["voice2"].apply_filter_lfo(lfo1_scaled)
            print("[PYO] LFO1 → Voice2 filter cutoff (wobble bass)")
        
        # Apply LFO2 to Voice3 amplitude (tremolo)
        if "voice3" in self.voices:
            lfo2_scaled = self.lfo2.get_scaled_for_amp(min_amp=0.2)
            self.voices["voice3"].apply_amp_lfo(lfo2_scaled)
            print("[PYO] LFO2 → Voice3 amplitude (tremolo)")
        
        # Register LFO modules in the schema registry
        self.register_module_schema("lfo1", self.lfo1.get_schema())
        self.register_module_schema("lfo2", self.lfo2.get_schema())
        
        print("[PYO] LFO setup complete")
    
    def setup_monitoring(self):
        """Setup real-time audio and message monitoring"""
        # Audio level monitoring
        self.peak_meter = PeakAmp(self.master)
        
        # Use multiple band-pass filters for spectrum analysis (FFT alternative)
        # This approach doesn't require WxPython and gives us direct frequency band levels
        self.spectrum_bands = []
        frequencies = [63, 125, 250, 500, 1000, 2000, 4000, 8000]
        for freq in frequencies:
            # Bandpass filter for each frequency band
            bp = ButBP(self.master, freq=freq, q=2)
            # Get the amplitude of each band
            follower = Follower(bp, freq=10)  # 10Hz update rate
            self.spectrum_bands.append(follower)
        
        # OSC broadcast client for visualization data
        self.viz_broadcast = udp_client.SimpleUDPClient('127.0.0.1', 5006)
        
        # Per-voice level monitoring
        self.voice_meters = {}
        for voice_id in self.voices:
            self.voice_meters[voice_id] = PeakAmp(self.voices[voice_id].get_dry_signal())
        
        # Statistics
        self.msg_count = 0
        self.last_msg = "none"
        self.last_level = 0.0
        self.active_gates = set()
        
        # Log buffer (last 100 events)
        self.log_buffer = deque(maxlen=100)
        
        # Update status every 100ms
        self.status_pattern = Pattern(self.update_status, time=0.1)
        self.status_pattern.play()
        
        print("[MONITOR] Status monitoring enabled")
        print("[MONITOR] Writing to engine_status.txt and engine_log.txt")
        print("[MONITOR] Broadcasting visualization data on port 5006")
    
    def setup_recording(self):
        """Initialize recording capability"""
        # Create recordings directory if it doesn't exist
        self.recordings_dir = Path("recordings")
        self.recordings_dir.mkdir(exist_ok=True)
        
        # Recording state management
        self.recording_active = False
        self.recording_lock = threading.Lock()
        self.current_recording = None
        
        print("[RECORDING] Recording system initialized")
        print(f"[RECORDING] Output directory: {self.recordings_dir.absolute()}")
    
    def update_status(self):
        """Write current status to files and broadcast visualization data"""
        try:
            level = float(self.peak_meter.get())
            
            # One-line status
            with open('engine_status.txt', 'w') as f:
                f.write(f"AUDIO: {level:.4f} | MSG: {self.msg_count} | GATES: {len(self.active_gates)} | LAST: {self.last_msg} | TIME: {time.strftime('%H:%M:%S')}\n")
            
            # Broadcast visualization data via OSC
            if hasattr(self, 'viz_broadcast'):
                # Get voice levels (clamped to 0.0-1.0)
                voice_levels = []
                for voice_id in sorted(self.voices.keys()):
                    if voice_id in self.voice_meters:
                        level = float(self.voice_meters[voice_id].get())
                        # Clamp to prevent display overflow
                        voice_levels.append(max(0.0, min(1.0, level)))
                    else:
                        voice_levels.append(0.0)
                
                # Send voice levels
                self.viz_broadcast.send_message('/viz/levels', voice_levels)
                
                # Get spectrum data from bandpass filters (8 bands)
                if hasattr(self, 'spectrum_bands'):
                    try:
                        # Get the level from each frequency band
                        spectrum = []
                        for band_follower in self.spectrum_bands:
                            # Get current amplitude of this frequency band
                            level = float(band_follower.get())
                            # Check for NaN/Inf and replace with 0
                            if math.isnan(level) or math.isinf(level):
                                level = 0.0
                            # Scale for display (adjust multiplier as needed)
                            spectrum.append(min(level * 50, 1.0))
                        
                        # Send spectrum data
                        self.viz_broadcast.send_message('/viz/spectrum', spectrum)
                    except Exception as e:
                        # If spectrum extraction fails, send zeros
                        print(f"[DEBUG] Spectrum error: {e}")
                        self.viz_broadcast.send_message('/viz/spectrum', [0.0] * 8)
            
            # Log significant events
            if level < 0.001 and self.last_level > 0.01:
                self.log_event(f"SILENCE_DETECTED (was {self.last_level:.4f})")
            elif level > 0.01 and self.last_level < 0.001:
                self.log_event(f"AUDIO_STARTED ({level:.4f})")
            
            self.last_level = level
        except:
            pass  # Don't crash audio thread
    
    def log_event(self, event):
        """Log event to buffer and file"""
        entry = f"{time.strftime('%H:%M:%S')} | LEVEL: {self.last_level:.4f} | {event}"
        self.log_buffer.append(entry)
        
        try:
            with open('engine_log.txt', 'w') as f:
                f.write('\n'.join(self.log_buffer))
        except:
            pass
    
    def map_route(self, path, handler, meta=None):
        """
        Route wrapper that registers metadata and maps handler atomically.
        This ensures registry stays in sync with actual routes.
        """
        # Register the route
        self.registered_routes[path] = {
            "handler": handler,
            "meta": meta or {}
        }
        
        # Log in verbose mode
        if self.verbose:
            if meta:
                print(f"[REGISTRY] Registered route {path} with metadata: {meta}")
            else:
                print(f"[REGISTRY] WARNING: Route {path} registered without metadata")
        
        # Map to dispatcher
        self.dispatcher.map(path, handler)
        
        # Update registry if this is a parameter route
        if path.startswith("/mod/") and meta:
            parts = path.split("/")
            if len(parts) >= 4:
                module_id = parts[2]
                param = "/".join(parts[3:])
                
                # Ensure module exists in registry
                if module_id not in self.registry["modules"]:
                    self.registry["modules"][module_id] = {"params": {}}
                
                # Update parameter metadata
                self.registry["modules"][module_id]["params"][param] = meta
    
    def register_module_schema(self, module_id, schema):
        """Register a module's schema in the registry dynamically
        
        Args:
            module_id: Module identifier (e.g., "lfo1", "dist1")
            schema: Schema dict from module's get_schema() method
        """
        if module_id not in self.registry["modules"]:
            self.registry["modules"][module_id] = {}
        
        # Update with the module's schema
        self.registry["modules"][module_id] = schema
        
        if self.verbose:
            print(f"[REGISTRY] Registered module schema: {module_id}")
    
    def track_unknown_route(self, addr):
        """Track routes that were called but not registered"""
        if addr not in self.registered_routes and addr not in self.unknown_routes:
            self.unknown_routes.add(addr)
            print(f"[REGISTRY] WARNING: Unknown route accessed: {addr}")
    
    def setup_osc_server(self):
        """Setup OSC server for control messages"""
        
        # Create dispatcher for OSC routing
        self.dispatcher = dispatcher.Dispatcher()
        
        # Register all routes with metadata using the wrapper
        
        # Module parameter control - wildcard pattern (handled specially)
        self.map_route("/mod/*/*", self.handle_mod_param, 
                      meta={"type": "wildcard", "description": "Module parameter control"})
        
        # Gate control - wildcard pattern
        self.map_route("/gate/*", self.handle_gate,
                      meta={"type": "wildcard", "description": "Gate control for modules"})
        
        # Engine control routes
        self.map_route("/engine/start", lambda addr, *args: self.start(),
                      meta={"args": [], "description": "Start audio processing"})
        
        self.map_route("/engine/stop", lambda addr, *args: self.stop(),
                      meta={"args": [], "description": "Stop audio processing"})
        
        self.map_route("/engine/status", lambda addr, *args: self.print_status(),
                      meta={"args": [], "description": "Print detailed status"})
        
        self.map_route("/engine/list", lambda addr, *args: self.list_modules(),
                      meta={"args": [], "description": "List all modules (human-readable)"})
        
        self.map_route("/engine/schema", self.handle_schema,
                      meta={"args": ["[format]"], "description": "Get full parameter schema", 
                            "formats": ["json", "stdout", "file"]})
        
        # Recording control routes
        self.map_route("/engine/record/start", self.handle_record_start,
                      meta={"args": ["[filename]"], "description": "Start recording to WAV file"})
        
        self.map_route("/engine/record/stop", self.handle_record_stop,
                      meta={"args": [], "description": "Stop current recording"})
        
        self.map_route("/engine/record/status", self.handle_record_status,
                      meta={"args": [], "description": "Get recording status"})
        
        # Sequencer control routes with full metadata
        self.map_route("/seq/add", self.handle_seq_add,
                      meta={"args": ["track_id", "voice_id", "pattern", "[base_freq]", "[filter_freq]", "[notes]"],
                            "description": "Add a new track to the sequencer",
                            "example": "/seq/add kick voice1 X...X...X...X... 60 200"})
        
        self.map_route("/seq/remove", self.handle_seq_remove,
                      meta={"args": ["track_id"], "description": "Remove a track from the sequencer"})
        
        self.map_route("/seq/clear", self.handle_seq_clear,
                      meta={"args": [], "description": "Clear all tracks"})
        
        self.map_route("/seq/start", self.handle_seq_start,
                      meta={"args": [], "description": "Start the sequencer"})
        
        self.map_route("/seq/stop", self.handle_seq_stop,
                      meta={"args": [], "description": "Stop the sequencer and gate off all voices"})
        
        self.map_route("/seq/bpm", self.handle_seq_bpm,
                      meta={"args": ["bpm_value"], "type": "float", "min": 30, "max": 300, 
                            "default": 120, "description": "Set sequencer BPM"})
        
        self.map_route("/seq/swing", self.handle_seq_swing,
                      meta={"args": ["swing_amount"], "type": "float", "min": 0, "max": 0.6,
                            "default": 0, "description": "Set swing amount"})
        
        self.map_route("/seq/update/pattern", 
                      self.handle_update_pattern,
                      meta={"args": ["track_id", "new_pattern"], "description": "Update a track's pattern"})
        
        self.map_route("/seq/update/notes",
                      self.handle_update_notes,
                      meta={"args": ["track_id", "notes_string"], "description": "Update a track's note sequence"})
        
        self.map_route("/seq/status", lambda addr, *args: print(f"[SEQ] {self.sequencer.get_status()}"),
                      meta={"args": [], "description": "Get sequencer status"})
        
        # Pattern save/load routes
        self.map_route("/pattern/save", self.handle_pattern_save,
                      meta={"args": ["slot_number"], "type": "int", "min": 1, "max": 128,
                            "description": "Save current pattern to slot 1-128"})
        
        self.map_route("/pattern/load", self.handle_pattern_load,
                      meta={"args": ["slot_number", "[immediate]"], "type": "int", "min": 1, "max": 128,
                            "description": "Load pattern from slot 1-128 (optional immediate flag)"})
        
        self.map_route("/pattern/list", self.handle_pattern_list,
                      meta={"args": [], "description": "List all saved patterns"})
        
        # Catch-all for debugging - tracks unknown routes
        self.dispatcher.set_default_handler(self.handle_unknown)
        
        # Create OSC server on port 5005
        self.osc_server = osc_server.ThreadingOSCUDPServer(
            ("127.0.0.1", 5005),
            self.dispatcher
        )
        
        # Start OSC server in background thread
        self.osc_thread = threading.Thread(
            target=self.osc_server.serve_forever,
            daemon=True
        )
        self.osc_thread.start()
        
        print("[OSC] Server listening on 127.0.0.1:5005")
    
    def handle_mod_param(self, addr, *args):
        """Handle /mod/<module_id>/<param> value"""
        
        parts = addr.split('/')
        if len(parts) < 4 or len(args) < 1:
            return
        
        module_id = parts[2]
        param = parts[3]
        value = args[0]
        
        # Handle sub-parameters like /mod/voice1/adsr/attack
        if len(parts) > 4:
            param = '/'.join(parts[3:])
        
        if self.verbose:
            print(f"[OSC] Set {module_id}.{param} = {value}")
        
        # Route voice parameters
        if module_id.startswith('voice'):
            if module_id in self.voices:
                voice = self.voices[module_id]
                
                if param == 'freq':
                    voice.set_freq(value)
                elif param == 'amp':
                    voice.set_amp(value)
                elif param == 'filter/freq':
                    voice.set_filter_freq(value)
                elif param == 'filter/q':
                    voice.set_filter_q(value)
                elif param.startswith('adsr/'):
                    adsr_param = param.split('/')[1]
                    voice.set_adsr(adsr_param, value)
                elif param == 'send/reverb':
                    voice.set_reverb_send(value)
                elif param == 'send/delay':
                    voice.set_delay_send(value)
                elif param == 'slide_time':
                    voice.set_slide_time(value)
                elif param == 'osc/type':
                    voice.set_waveform(value)
        
        # Backward compatibility: map old names to voice1
        elif module_id == 'sine1' and param == 'freq':
            self.voices['voice1'].set_freq(value)
        elif module_id == 'filter1':
            if param == 'freq':
                self.voices['voice1'].set_filter_freq(value)
            elif param == 'q':
                self.voices['voice1'].set_filter_q(value)
        elif module_id == 'adsr1':
            if param in ['attack', 'decay', 'sustain', 'release']:
                self.voices['voice1'].set_adsr(param, value)
        
        # Route effect parameters
        elif module_id == 'reverb1':
            if param == 'mix':
                self.reverb.set_mix(value)
            elif param == 'room':
                self.reverb.set_room(value)
            elif param == 'damp':
                self.reverb.set_damp(value)
        
        elif module_id == 'delay1':
            if param == 'time':
                self.delay.set_time(value)
            elif param == 'feedback':
                self.delay.set_feedback(value)
            elif param == 'mix':
                self.delay.set_mix(value)
            elif param == 'lowcut':
                self.delay.set_lowcut(value)
            elif param == 'highcut':
                self.delay.set_highcut(value)
        
        # Route distortion parameters
        elif module_id == 'dist1':
            if param == 'drive':
                self.dist1.set_drive(value)
            elif param == 'mix':
                self.dist1.set_mix(value)
            elif param == 'tone':
                self.dist1.set_tone(value)
        
        # Route LFO parameters using proper module methods
        elif module_id == 'lfo1':
            if param == 'rate':
                self.lfo1.set_rate(value)
                if self.verbose:
                    print(f"[OSC] LFO1 rate: {value}Hz")
            elif param == 'depth':
                self.lfo1.set_depth(value)
                if self.verbose:
                    print(f"[OSC] LFO1 depth: {value}")
        
        elif module_id == 'lfo2':
            if param == 'rate':
                self.lfo2.set_rate(value)
                if self.verbose:
                    print(f"[OSC] LFO2 rate: {value}Hz")
            elif param == 'depth':
                self.lfo2.set_depth(value)
                if self.verbose:
                    print(f"[OSC] LFO2 depth: {value}")
        
        # Route acid filter parameters
        elif module_id == 'acid1' and self.acid1:
            if param == 'cutoff':
                self.acid1.set_cutoff(value)
            elif param == 'res':
                self.acid1.set_res(value)
            elif param == 'env_amount':
                self.acid1.set_env_amount(value)
            elif param == 'decay':
                self.acid1.set_decay(value)
            elif param == 'accent':
                self.acid1.set_accent(value)
            elif param == 'cutoff_offset':
                self.acid1.set_cutoff_offset(value)
            elif param == 'res_accent_boost':
                self.acid1.set_res_accent_boost(value)
            elif param == 'accent_decay':
                self.acid1.set_accent_decay(value)
            elif param == 'drive':
                self.acid1.set_drive(value)
            elif param == 'mix':
                self.acid1.set_mix(value)
            elif param == 'vol_comp':
                self.acid1.set_vol_comp(value)
    
    def handle_gate(self, addr, *args):
        """Handle /gate/<module_id> value"""
        
        # Track messages
        self.msg_count += 1
        self.last_msg = f"{addr} {args[0] if args else ''}"[:40]
        
        parts = addr.split('/')
        if len(parts) < 3 or len(args) < 1:
            return
        
        module_id = parts[2]
        gate = args[0]
        
        # Track active gates
        if float(gate) > 0:
            self.active_gates.add(module_id)
            self.log_event(f"GATE_ON: {module_id}")
        else:
            self.active_gates.discard(module_id)
        
        if self.verbose:
            print(f"[OSC] Gate {module_id} = {gate}")
        
        # Route to voices
        if module_id.startswith('voice'):
            if module_id in self.voices:
                self.voices[module_id].gate(gate)
                
                # If voice2, also trigger acid1
                if module_id == 'voice2':
                    self.acid1.gate(gate)
        
        # Direct acid gate (optional, aliased to voice2)
        elif module_id == 'acid1':
            self.acid1.gate(gate)
            # Also gate voice2 to keep them in sync
            self.voices['voice2'].gate(gate)
        
        # Backward compatibility: map old names to voice1
        elif module_id == 'adsr1' or module_id == '1':
            self.voices['voice1'].gate(gate)
    
    def handle_seq_add(self, addr, *args):
        """Handle /seq/add track_id voice_id pattern [base_freq] [filter_freq] [notes] ..."""
        if len(args) < 3:
            print(f"[OSC] /seq/add requires at least 3 args: track_id voice_id pattern")
            return
        
        track_id = str(args[0])
        voice_id = str(args[1])
        pattern = str(args[2])
        
        # Parse optional kwargs from remaining args
        kwargs = {}
        if len(args) > 3:
            # Try to parse pairs of key=value or positional common params
            for i in range(3, len(args)):
                arg = str(args[i])
                if '=' in arg:
                    # Key=value format
                    key, value = arg.split('=', 1)
                    try:
                        # Try to convert to float if possible
                        kwargs[key] = float(value)
                    except:
                        kwargs[key] = value
                else:
                    # Positional args mapping (for common params)
                    if i == 3:
                        try:
                            kwargs['base_freq'] = float(arg)
                        except:
                            pass
                    elif i == 4:
                        try:
                            kwargs['filter_freq'] = float(arg)
                        except:
                            pass
                    elif i == 5:
                        kwargs['notes'] = arg  # Will be parsed by add_track
        
        # Add the track
        success = self.sequencer.add_track(track_id, voice_id, pattern, **kwargs)
        if success and self.verbose:
            print(f"[OSC] Added track '{track_id}' with pattern length {len(pattern)}")
    
    def handle_schema(self, addr, *args):
        """Handle /engine/schema - return full parameter schema"""
        format_type = str(args[0]) if args else "stdout"
        
        # Build complete schema including registered and unknown routes
        complete_schema = dict(self.registry)
        
        # Add registered routes info
        complete_schema["registered_routes"] = list(self.registered_routes.keys())
        
        # Add unknown routes if any were tracked
        if self.unknown_routes:
            complete_schema["unknown_routes"] = list(self.unknown_routes)
            complete_schema["warning"] = "Unknown routes detected - these may indicate drift!"
        
        # Convert to JSON
        schema_json = json.dumps(complete_schema, indent=2)
        
        if format_type == "json" or format_type == "stdout":
            # Print to stdout
            print("\n" + "="*50)
            print("ENGINE PARAMETER SCHEMA")
            print("="*50)
            print(schema_json)
            print("="*50 + "\n")
        
        elif format_type == "file":
            # Write to file if environment variable is set
            if True:  # Temporarily always allow export
                filename = f"chronus_schema_{time.strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w') as f:
                    f.write(schema_json)
                print(f"[SCHEMA] Exported to {filename}")
            else:
                print("[SCHEMA] Set CHRONUS_EXPORT_SCHEMA=1 to enable file export")
        
        # TODO: Add OSC reply-to functionality when needed
        # This would require tracking the sender address and using send_message back
    
    def handle_record_start(self, addr, *args):
        """Handle /engine/record/start [filename]"""
        filename = args[0] if args else None
        success = self.start_recording(filename)
        if not success:
            print("[OSC] Recording already in progress")
    
    def handle_record_stop(self, addr, *args):
        """Handle /engine/record/stop"""
        recorded_file = self.stop_recording()
        if recorded_file:
            print(f"[OSC] Recording saved to: {recorded_file}")
    
    def handle_record_status(self, addr, *args):
        """Handle /engine/record/status"""
        status = self.get_recording_status()
        print("\n" + "="*50)
        print("RECORDING STATUS")
        print("="*50)
        print(f"Active: {status['active']}")
        if status['current_file']:
            print(f"Current file: {status['current_file']}")
        print(f"Output directory: {status['recordings_dir']}")
        print("="*50 + "\n")
    
    def handle_pattern_save(self, addr, *args):
        """Handle pattern save with feedback"""
        if not args:
            print("[PATTERN] Error: No slot number provided")
            return
        
        try:
            # Robust conversion handling both int and float strings
            slot = int(float(args[0]))
            if self.save_pattern(slot):
                # Success message printed by save_pattern
                pass
            else:
                # Error message printed by save_pattern
                pass
        except (ValueError, TypeError) as e:
            print(f"[PATTERN] Error: Invalid slot number: {args[0]}")
    
    def handle_pattern_load(self, addr, *args):
        """Handle pattern load with optional immediate flag"""
        if not args:
            print("[PATTERN] Error: No slot number provided")
            return
        
        try:
            # Parse slot number
            slot = int(float(args[0]))
            
            # Parse optional immediate flag
            immediate = False
            if len(args) > 1:
                immediate_arg = str(args[1]).lower()
                immediate = immediate_arg in ('1', 'true', 'immediate', 'now')
            
            if self.load_pattern(slot, immediate=immediate):
                # Success message printed by load_pattern
                pass
            else:
                # Error message printed by load_pattern
                pass
        except (ValueError, TypeError) as e:
            print(f"[PATTERN] Error: Invalid arguments: {args}")
    
    def handle_pattern_list(self, addr, *args):
        """Handle pattern list - returns nothing to avoid OSC errors"""
        self.list_patterns()
        # Don't return anything - OSC handlers should return None
    
    def handle_update_pattern(self, addr, *args):
        """Handle sequencer pattern update - no return value to avoid OSC errors"""
        if len(args) >= 2:
            self.sequencer.update_pattern(str(args[0]), str(args[1]))
        else:
            print(f"[SEQ] Error: update_pattern requires track_id and pattern")
    
    def handle_update_notes(self, addr, *args):
        """Handle sequencer notes update - no return value to avoid OSC errors"""
        if len(args) >= 2:
            self.sequencer.update_notes(str(args[0]), str(args[1]))
        else:
            print(f"[SEQ] Error: update_notes requires track_id and notes")
    
    def handle_seq_remove(self, addr, *args):
        """Handle sequencer track removal - no return value to avoid OSC errors"""
        if len(args) >= 1:
            self.sequencer.remove_track(str(args[0]))  # Don't return the boolean result
        else:
            print(f"[SEQ] Error: remove requires track_id")
    
    def handle_seq_clear(self, addr, *args):
        """Handle sequencer clear - no return value to avoid OSC errors"""
        self.sequencer.clear()  # Don't return anything
    
    def handle_seq_start(self, addr, *args):
        """Handle sequencer start - no return value to avoid OSC errors"""
        self.sequencer.start()  # Don't return anything
    
    def handle_seq_stop(self, addr, *args):
        """Handle sequencer stop - no return value to avoid OSC errors"""
        self.sequencer.stop()  # Don't return anything
    
    def handle_seq_bpm(self, addr, *args):
        """Handle sequencer BPM change - no return value to avoid OSC errors"""
        if len(args) >= 1:
            self.sequencer.set_bpm(float(args[0]))
        else:
            print(f"[SEQ] Error: bpm requires a value")
    
    def handle_seq_swing(self, addr, *args):
        """Handle sequencer swing change - no return value to avoid OSC errors"""
        if len(args) >= 1:
            self.sequencer.set_swing(float(args[0]))
        else:
            print(f"[SEQ] Error: swing requires a value")
    
    def handle_unknown(self, addr, *args):
        """Debug handler for unmatched OSC messages - tracks drift"""
        self.track_unknown_route(addr)
        print(f"[OSC] Unknown: {addr} {args}")
    
    def start(self):
        """Start audio processing"""
        self.server.start()
        print("[PYO] Audio started")
    
    def stop(self):
        """Stop audio processing and sequencer"""
        # Stop any active recording
        if hasattr(self, 'recording_active') and self.recording_active:
            self.stop_recording()
        # Stop sequencer first
        self.sequencer.stop()
        # Then stop audio
        self.server.stop()
        print("[PYO] Audio stopped")
    
    def start_recording(self, filename=None):
        """Start recording master output to file
        
        Args:
            filename: Optional custom filename. If None, uses timestamp.
        
        Returns:
            bool: True if recording started, False if already recording
        """
        with self.recording_lock:
            if self.recording_active:
                print("[RECORDING] Already recording!")
                return False
            
            # Generate filename if not provided
            if filename is None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = self.recordings_dir / f"chronus_{timestamp}.wav"
            else:
                # Ensure it's in the recordings directory
                filename = self.recordings_dir / Path(filename).name
            
            # Configure server recording options
            self.server.recordOptions(
                dur=-1,  # Record until stopped
                filename=str(filename),
                fileformat=0,  # WAV format
                sampletype=0   # 16-bit integer
            )
            
            # Start recording
            self.server.recstart()
            self.recording_active = True
            self.current_recording = filename
            
            print(f"[RECORDING] Started recording to: {filename}")
            self.log_event(f"RECORDING_START: {filename.name}")
            return True
    
    def stop_recording(self):
        """Stop current recording
        
        Returns:
            str: Path to recorded file, or None if not recording
        """
        with self.recording_lock:
            if not self.recording_active:
                print("[RECORDING] Not currently recording")
                return None
            
            # Stop recording
            self.server.recstop()
            self.recording_active = False
            
            recorded_file = self.current_recording
            self.current_recording = None
            
            print(f"[RECORDING] Stopped recording: {recorded_file}")
            self.log_event(f"RECORDING_STOP: {recorded_file.name}")
            
            return str(recorded_file)
    
    def get_recording_status(self):
        """Get current recording status
        
        Returns:
            dict: Recording status information
        """
        with self.recording_lock:
            return {
                "active": self.recording_active,
                "current_file": str(self.current_recording) if self.current_recording else None,
                "recordings_dir": str(self.recordings_dir.absolute())
            }
    
    def print_status(self):
        """Print current engine status"""
        print("\n" + "="*50)
        print("PYO ENGINE STATUS")
        print("="*50)
        print(f"Server running: {self.server.getIsStarted()}")
        print(f"Sample rate: {self.server.getSamplingRate()}Hz")
        print(f"Buffer size: {self.server.getBufferSize()}")
        print(f"Output latency: {self.server.getBufferSize()/self.server.getSamplingRate()*1000:.1f}ms")
        print("\nVoices (4):")
        for voice_id in self.voices:
            print(f"  {voice_id}: ready")
        print("\nDSP Modules:")
        acid_status = self.acid1.get_status()
        print(f"  acid1: cutoff={acid_status['cutoff']:.0f}Hz res={acid_status['res']:.2f} (on voice2)")
        print("\nEffects:")
        print(f"  reverb1: mix={self.reverb.get_status()['mix']:.2f}")
        print(f"  delay1: time={self.delay.get_status()['time']:.2f}s")
        print("="*50 + "\n")
    
    def list_modules(self):
        """List available modules and parameters"""
        print("\n" + "="*50)
        print("AVAILABLE MODULES")
        print("="*50)
        
        num_voices = len(self.voices)
        print(f"\nVoices (voice1-voice{num_voices}):") 
        print("  /mod/voiceN/freq <20-5000>")
        print("  /mod/voiceN/amp <0-1>")
        print("  /mod/voiceN/filter/freq <50-8000>")
        print("  /mod/voiceN/filter/q <0.5-10>")
        print("  /mod/voiceN/adsr/attack <0.001-2>")
        print("  /mod/voiceN/adsr/decay <0-2>")
        print("  /mod/voiceN/adsr/sustain <0-1>")
        print("  /mod/voiceN/adsr/release <0.01-3>")
        print("  /mod/voiceN/send/reverb <0-1>")
        print("  /mod/voiceN/send/delay <0-1>")
        print("  /gate/voiceN <0|1>")
        
        print("\nDSP Modules:")
        print("  acid1 (TB-303 filter on voice2):")
        print("    /mod/acid1/cutoff <80-5000> - Base cutoff Hz")
        print("    /mod/acid1/res <0-0.98> - Resonance")
        print("    /mod/acid1/env_amount <0-5000> - Envelope depth Hz")
        print("    /mod/acid1/decay <0.02-1.0> - Envelope decay s")
        print("    /mod/acid1/accent <0-1> - Accent level")
        print("    /mod/acid1/cutoff_offset <0-1000> - Accent cutoff boost")
        print("    /mod/acid1/res_accent_boost <0-0.4> - Accent resonance")
        print("    /mod/acid1/accent_decay <0.02-0.15> - Accent env decay")
        print("    /mod/acid1/drive <0-1> - Pre-filter drive")
        print("    /mod/acid1/mix <0-1> - Wet/dry mix")
        print("    /mod/acid1/vol_comp <0-1> - Resonance compensation")
        print("    /gate/acid1 - Optional (auto-triggers with voice2)")
        
        print("\nEffects:")
        print("  /mod/reverb1/mix <0-1>")
        print("  /mod/reverb1/room <0-1>")
        print("  /mod/reverb1/damp <0-1>")
        print("  /mod/delay1/time <0.1-0.6>")
        print("  /mod/delay1/feedback <0-0.7>")
        print("  /mod/delay1/mix <0-1>")
        
        print("\nBackward Compatibility (mapped to voice1):")
        print("  /mod/sine1/freq")
        print("  /mod/filter1/freq|q")
        print("  /mod/adsr1/*")
        print("  /gate/adsr1")
        
        print("="*50 + "\n")
    
    def run_forever(self):
        """Keep engine running (for headless operation)"""
        print("\n[PYO] Engine ready for OSC control")
        print("Commands:")
        print("  /mod/<module>/<param> value - Set parameter")
        print("  /gate/<module> 0/1 - Gate control")
        print("  /engine/start - Start audio")
        print("  /engine/stop - Stop audio")
        print("  /engine/status - Show status")
        print("  /engine/list - List all modules")
        print("\nPress Ctrl+C to exit\n")
        
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[PYO] Shutting down...")
            self.stop()
            self.server.shutdown()
            self.osc_server.shutdown()
    
    def capture_all_states(self) -> dict:
        """
        Capture complete engine state: sequencer + all modules.
        Thread-safe, no deepcopy, combines all subsystem states.
        """
        # Get sequencer state
        sequencer_state = self.sequencer.snapshot()
        
        # Capture module states
        module_states = {}
        
        # Voices
        for voice_id, voice in self.voices.items():
            module_states[voice_id] = voice.get_status()
        
        # Effects
        module_states["dist1"] = self.dist1.get_status()
        module_states["reverb1"] = self.reverb.get_status()
        module_states["delay1"] = self.delay.get_status()
        
        # LFO modules using proper get_status() method
        module_states["lfo1"] = self.lfo1.get_status()
        module_states["lfo2"] = self.lfo2.get_status()
        
        # Acid filter (if it exists)
        if self.acid1:
            module_states["acid1"] = self.acid1.get_status()
        
        # Build complete state
        return {
            "chronus_version": "1.0.0",
            "schema_version": "1.0",
            "timestamp": time.time(),
            "sequencer": sequencer_state,
            "modules": module_states
        }
    
    def restore_all_states(self, data: dict, immediate: bool = False):
        """
        Restore complete engine state from saved data.
        Applies in correct order: sequencer -> voices -> effects -> acid.
        """
        # Validate schema version
        schema_version = data.get("schema_version", "1.0")
        if schema_version != "1.0":
            print(f"[PATTERN] Warning: Schema version mismatch ({schema_version} != 1.0)")
        
        # Restore sequencer state
        sequencer_data = data.get("sequencer", {})
        if sequencer_data:
            self.sequencer.apply_snapshot(sequencer_data, immediate=immediate)
        
        # Restore module states in dependency order
        module_data = data.get("modules", {})
        
        # Phase 1: Voice parameters (no dependencies)
        # Dynamically iterate over existing voices
        for voice_id in self.voices.keys():
            if voice_id in module_data:
                voice_state = module_data[voice_id]
                voice = self.voices[voice_id]
                
                # Apply voice parameters
                voice.set_freq(voice_state.get("freq", 440.0))
                voice.set_amp(voice_state.get("amp", 0.3))
                voice.set_filter_freq(voice_state.get("filter_freq", 1000.0))
                voice.set_filter_q(voice_state.get("filter_q", 2.0))
                voice.set_reverb_send(voice_state.get("reverb_send", 0.0))
                voice.set_delay_send(voice_state.get("delay_send", 0.0))
                
                # ADSR parameters
                adsr = voice_state.get("adsr", {})
                voice.set_adsr("attack", adsr.get("attack", 0.01))
                voice.set_adsr("decay", adsr.get("decay", 0.1))
                voice.set_adsr("sustain", adsr.get("sustain", 0.7))
                voice.set_adsr("release", adsr.get("release", 0.5))
        
        # Phase 2: Effects (depend on voice sends)
        if "dist1" in module_data:
            dist_state = module_data["dist1"]
            self.dist1.set_drive(dist_state.get("drive", 0.0))
            self.dist1.set_mix(dist_state.get("mix", 0.0))
            self.dist1.set_tone(dist_state.get("tone", 0.5))
        
        # Restore LFO states using proper module methods
        if "lfo1" in module_data:
            lfo1_state = module_data["lfo1"]
            self.lfo1.set_rate(lfo1_state.get("rate", 0.25))
            self.lfo1.set_depth(lfo1_state.get("depth", 0.7))
        
        if "lfo2" in module_data:
            lfo2_state = module_data["lfo2"]
            self.lfo2.set_rate(lfo2_state.get("rate", 4.0))
            self.lfo2.set_depth(lfo2_state.get("depth", 0.3))
        
        if "reverb1" in module_data:
            reverb_state = module_data["reverb1"]
            self.reverb.set_mix(reverb_state.get("mix", 0.3))
            self.reverb.set_room(reverb_state.get("room", 0.5))
            self.reverb.set_damp(reverb_state.get("damp", 0.5))
        
        if "delay1" in module_data:
            delay_state = module_data["delay1"]
            self.delay.set_time(delay_state.get("time", 0.25))
            self.delay.set_feedback(delay_state.get("feedback", 0.4))
            self.delay.set_mix(delay_state.get("mix", 0.3))
            self.delay.set_lowcut(delay_state.get("lowcut", 100.0))
            self.delay.set_highcut(delay_state.get("highcut", 5000.0))
        
        # Phase 3: Acid filter (depends on voice2)
        if "acid1" in module_data and self.acid1:
            acid_state = module_data["acid1"]
            self.acid1.set_cutoff(acid_state.get("cutoff", 1500.0))
            self.acid1.set_res(acid_state.get("res", 0.45))
            self.acid1.set_env_amount(acid_state.get("env_amount", 2500.0))
            self.acid1.set_decay(acid_state.get("decay", 0.25))
            self.acid1.set_drive(acid_state.get("drive", 0.2))
            self.acid1.set_mix(acid_state.get("mix", 1.0))
            self.acid1.set_vol_comp(acid_state.get("vol_comp", 0.5))
        
        if self.verbose:
            print(f"[PATTERN] State restored: {len(module_data)} modules")
    
    def save_pattern(self, slot: int) -> bool:
        """
        Save current pattern to numbered slot (1-128).
        Uses atomic file operations to prevent corruption.
        """
        # Validate slot number
        if not 1 <= slot <= 128:
            print(f"[PATTERN] Error: Slot {slot} out of range (1-128)")
            return False
        
        # Capture complete state with lock
        with self.pattern_io_lock:
            pattern_data = self.capture_all_states()
        
        # Prepare file paths using Path objects
        slot_dir = Path("patterns") / "slots"
        slot_path = slot_dir / f"slot_{slot:03d}.json"
        
        # Atomic write using tempfile
        try:
            # Create temp file in same directory for atomic rename
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=slot_dir,
                suffix='.tmp',
                delete=False
            ) as tmp:
                json.dump(pattern_data, tmp, indent=2)
                tmp_path = Path(tmp.name)
            
            # Backup existing if present
            if slot_path.exists():
                backup_dir = Path("patterns") / "backups"
                backup_path = backup_dir / f"slot_{slot:03d}_{int(time.time())}.backup"
                shutil.copy2(slot_path, backup_path)
                if self.verbose:
                    print(f"[PATTERN] Backed up existing slot {slot}")
            
            # Atomic replace (Windows-safe using pathlib)
            tmp_path.replace(slot_path)
            print(f"[PATTERN] Saved to slot {slot}")
            return True
            
        except Exception as e:
            print(f"[PATTERN] Save failed: {e}")
            # Clean up temp file if it exists
            if 'tmp_path' in locals():
                tmp_path.unlink(missing_ok=True)
            return False
    
    def load_pattern(self, slot: int, immediate: bool = False) -> bool:
        """
        Load pattern from numbered slot (1-128).
        immediate=False: Bar-aligned loading (default)
        immediate=True: Load immediately
        """
        # Validate slot number
        if not 1 <= slot <= 128:
            print(f"[PATTERN] Error: Slot {slot} out of range (1-128)")
            return False
        
        # Prepare file paths
        slot_path = Path("patterns") / "slots" / f"slot_{slot:03d}.json"
        backup_path = Path("patterns") / "backups" / f"slot_{slot:03d}.backup"
        
        # Try to load pattern file
        pattern_data = None
        try:
            with open(slot_path, 'r') as f:
                pattern_data = json.load(f)
                if self.verbose:
                    print(f"[PATTERN] Loaded slot {slot}")
        except (json.JSONDecodeError, IOError) as e:
            # Try backup if main file fails
            if backup_path.exists():
                print(f"[PATTERN] Slot {slot} corrupted, trying backup")
                try:
                    with open(backup_path, 'r') as f:
                        pattern_data = json.load(f)
                        print(f"[PATTERN] Backup loaded successfully")
                except:
                    pass
        
        if pattern_data is None:
            print(f"[PATTERN] Error: No valid pattern in slot {slot}")
            return False
        
        # Apply the loaded pattern
        try:
            self.restore_all_states(pattern_data, immediate=immediate)
            print(f"[PATTERN] Loaded slot {slot} {'immediately' if immediate else 'queued for bar boundary'}")
            return True
        except Exception as e:
            print(f"[PATTERN] Error applying pattern: {e}")
            return False
    
    def list_patterns(self) -> list:
        """
        List all saved pattern slots.
        Returns list of used slot numbers for programmatic use.
        """
        slots_dir = Path("patterns") / "slots"
        used_slots = []
        
        print("[PATTERN] Saved patterns:")
        for slot in range(1, 129):
            slot_path = slots_dir / f"slot_{slot:03d}.json"
            if slot_path.exists():
                used_slots.append(slot)
                # Get file modification time
                mtime = slot_path.stat().st_mtime
                time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
                print(f"  Slot {slot:3d}: {time_str}")
        
        if not used_slots:
            print("  (no saved patterns)")
        
        return used_slots


def main():
    """Main entry point"""
    
    # Create engine with environment-aware config
    engine = PyoEngine()
    
    # Auto-start audio
    engine.start()
    
    # Run forever (headless mode)
    engine.run_forever()


if __name__ == "__main__":
    main()