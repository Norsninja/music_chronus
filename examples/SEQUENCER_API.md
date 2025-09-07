# PolySequencer API Documentation

## Executive Summary

The **PolySequencer** class is a 4-voice polyphonic sequencer that controls the pyo engine via OSC. It uses pattern notation (`X.x.`) for rhythm programming and supports per-track parameter control including notes, velocities, effects sends, and gate lengths. Each track maps to one voice (voice1-4) in the engine.

## Critical Performance Data

- **Timing System**: Epoch-based timing prevents drift
- **Pattern Length**: Variable per track (8, 16, 32 steps supported)
- **Voice Mapping**: 4 tracks → 4 voices maximum
- **OSC Latency**: ~5.3ms (pyo engine performance)
- **Threading**: Uses daemon threads for non-blocking operation

## API Reference

### Class: PolySequencer

#### Constructor
```python
PolySequencer(osc_client: udp_client.SimpleUDPClient, bpm: float = 120)
```

**Parameters:**
- `osc_client`: SimpleUDPClient instance connected to engine (port 5005)
- `bpm`: Tempo in beats per minute (default: 120)

**Example:**
```python
from pythonosc import udp_client
from examples.poly_sequencer import PolySequencer

client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
seq = PolySequencer(client, bpm=140)
```

#### Core Methods

##### add_track()
```python
add_track(name: str, voice_id: str, pattern: str, **kwargs) -> Track
```

**Critical Requirements:**
- `voice_id` MUST be one of: "voice1", "voice2", "voice3", "voice4"
- `pattern` uses notation: 'X' (accent), 'x' (normal), '.' (rest)
- Track names are stored in `self.tracks` dictionary
- Returns Track object for further manipulation

**Parameters:**
- `name`: Track identifier (string, used as dictionary key)
- `voice_id`: Target voice ("voice1" through "voice4")
- `pattern`: Rhythm pattern string
- `**kwargs`: Additional Track parameters (see Track class below)

**Working Example:**
```python
# Add kick drum on voice1
track = seq.add_track(
    name="kick",
    voice_id="voice1", 
    pattern="X.x.X.x.X.x.X.x.",
    base_freq=60,
    filter_freq=150,
    gate_frac=0.2,
    reverb_send=0.1
)
```

##### start()
```python
start() -> None
```

Starts the sequencer in a daemon thread. Sets `self.running = True` and begins epoch-based timing.

**Thread Safety:** Uses daemon thread, automatically stops when main program exits.

##### stop()
```python
stop() -> None
```

Stops sequencer and sends gate-off to all voices. Joins thread with 1-second timeout.

**Critical Cleanup:** Always call to prevent hanging notes and clean thread termination.

##### set_swing()
```python
set_swing(swing: float) -> None
```

**Parameters:**
- `swing`: 0.0-0.8 (clamped), where 0.0 = straight timing, 0.6 = heavy swing

**Timing Implementation:** Delays odd-indexed steps (2nd, 4th, 6th...) by `swing * 0.5 * seconds_per_step`

##### update_pattern()
```python
update_pattern(track_name: str, pattern: str) -> None
```

**Real-time Safe:** Can be called while sequencer is running. Pattern change takes effect on next loop iteration.

##### update_notes()
```python
update_notes(track_name: str, notes: List[Union[float, int, str]]) -> None
```

Updates note sequence and resets note cycling to beginning.

**Note Formats Supported:**
- Float > 127: Frequency in Hz
- Int 0-127: MIDI note number  
- String: Note name ("C3", "F#4", "Bb2")

### Class: Track

#### Constructor Parameters
```python
@dataclass
class Track:
    name: str                    # Track identifier
    voice_id: str               # "voice1" through "voice4"
    pattern: str                # Pattern string (X.x. notation)
    notes: List[Union[float, int, str]] = []  # Note sequence (cycles)
    base_freq: float = 440.0    # Fallback frequency
    filter_freq: float = 1000.0 # Base filter cutoff
    accent_boost: float = 1500.0 # Hz added on 'X' steps  
    reverb_send: float = 0.0    # 0.0-1.0 reverb send level
    delay_send: float = 0.0     # 0.0-1.0 delay send level
    gate_frac: float = 0.5      # Gate length (0.1-0.95)
    base_amp: float = 0.3       # Base amplitude
```

#### Track Methods

##### get_next_freq()
```python
get_next_freq() -> float
```

Returns next frequency from notes list and advances internal counter. Cycles through notes infinitely.

##### reset_note_index()
```python
reset_note_index() -> None
```

Resets note cycling to beginning of notes list.

## Pattern Notation

### Rhythm Notation
- `X`: Accent hit (velocity 1.0, full accent_boost applied)
- `x`: Normal hit (velocity 0.6, partial accent_boost)  
- `.`: Rest (velocity 0.0, no trigger)

### Pattern Examples
```python
"X.x.X.x.X.x.X.x."  # Four-on-floor kick
"....X.......X..."  # Snare on 2 and 4
"x.x.x.x.x.x.x.X."  # Hi-hat pattern with accent
"X..............."  # Sparse ambient pulse
```

## Battle-Tested Patterns

### Techno Pattern (125 BPM)
```python
seq = PolySequencer(client, bpm=125)

# Four-on-floor kick
seq.add_track("kick", "voice1", "X.x.X.x.X.x.X.x.",
              base_freq=55, filter_freq=150, gate_frac=0.2)

# Syncopated bass  
seq.add_track("bass", "voice2", "..x...x...x.x...",
              notes=[36, 36, 39, 36], filter_freq=800, 
              accent_boost=2000, gate_frac=0.3)

# Minimal lead
seq.add_track("lead", "voice3", "....x.......x...",
              notes=["C4", "D#4", "G4"], filter_freq=2500,
              reverb_send=0.2, gate_frac=0.1)

# Hi-hat
seq.add_track("hihat", "voice4", "x.x.x.x.x.x.x.X.",
              base_freq=8000, filter_freq=5000, gate_frac=0.05)
```

### D&B Pattern (175 BPM)
```python
seq = PolySequencer(client, bpm=175)

# Sparse kick pattern
seq.add_track("kick", "voice1", "X.......X.......",
              base_freq=50, filter_freq=120, gate_frac=0.15)

# Complex snare with ghost notes
seq.add_track("snare", "voice2", "....X.x.....X.x.",
              base_freq=200, filter_freq=3000, gate_frac=0.08,
              reverb_send=0.3)

# Rolling bass
seq.add_track("bass", "voice3", "x.x.x..xx.x.x.x.",
              notes=[30, 33, 30, 30, 35, 30, 33, 30],
              filter_freq=600, accent_boost=1200)

# Breakbeat hi-hat
seq.add_track("hihat", "voice4", "x.x.x.xxx.x.x.x.",
              base_freq=9000, filter_freq=6000, gate_frac=0.03)
```

### Ambient Pattern (80 BPM)
```python
seq = PolySequencer(client, bpm=80)

# Long pulse
seq.add_track("pulse", "voice1", "X...............",
              notes=[60, 55], filter_freq=500, gate_frac=0.9,
              reverb_send=0.7, delay_send=0.3)

# Sparse bass
seq.add_track("bass", "voice2", "....x.......x...",
              notes=["C2", "G2"], filter_freq=400, gate_frac=0.8,
              reverb_send=0.5)

# Ethereal lead
seq.add_track("lead", "voice3", "........X.......",
              notes=["C4", "E4", "G4", "B4"], filter_freq=3000,
              reverb_send=0.8, delay_send=0.4, gate_frac=0.7)

# Pad layer
seq.add_track("pad", "voice4", "X...............",
              notes=["C3", "E3", "G3"], filter_freq=1200,
              reverb_send=0.9, delay_send=0.5, gate_frac=0.95)
```

### Dub Pattern (90 BPM)  
```python
seq = PolySequencer(client, bpm=90)

# Sparse kick
seq.add_track("kick", "voice1", "X.......X.......",
              base_freq=60, filter_freq=200, gate_frac=0.3)

# Walking bass
seq.add_track("bass", "voice2", "x.x.x.x.x.x.x.x.",
              notes=[41, 41, 36, 41, 43, 41, 36, 36],
              filter_freq=600, accent_boost=1000, gate_frac=0.4)

# Offbeat stabs with heavy delay
seq.add_track("stab", "voice3", "..X...X...X...X.",
              notes=["D4", "F4", "A4"], filter_freq=2000,
              reverb_send=0.3, delay_send=0.6, gate_frac=0.1)

# Subtle hi-hat
seq.add_track("hihat", "voice4", "....x.......x...",
              base_freq=7000, filter_freq=4000,
              reverb_send=0.1, gate_frac=0.05)
```

## Complete Working Example

```python
#!/usr/bin/env python3
"""
Complete PolySequencer Example
Autonomous demo with genre switching
"""

import time
from pythonosc import udp_client
from examples.poly_sequencer import PolySequencer, create_techno_preset

def main():
    # Connect to engine
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    # Create sequencer
    seq = PolySequencer(client, bpm=130)
    
    try:
        # Load techno preset
        create_techno_preset(seq)
        
        print("Starting techno sequence...")
        seq.start()
        
        # Play for 16 bars
        time.sleep(16 * (60.0/130) * 4)  # 16 bars at 130 BPM
        
        # Add swing
        print("Adding 40% swing...")  
        seq.set_swing(0.4)
        time.sleep(8 * (60.0/130) * 4)   # 8 more bars
        
        # Update bass pattern on the fly
        print("Updating bass pattern...")
        seq.update_notes("bass", [32, 36, 39, 43])
        time.sleep(8 * (60.0/130) * 4)
        
    finally:
        seq.stop()
        print("Demo complete")

if __name__ == "__main__":
    main()
```

## Critical Gotchas

### Voice Mapping Issues
- **Problem**: Only 4 voices available (voice1-4)
- **Solution**: Plan track assignments carefully, max 4 simultaneous tracks

### Pattern Length Mismatches  
- **Problem**: Different pattern lengths can cause phasing
- **Solution**: Use compatible lengths (8, 16, 32) or embrace polyrhythms

### Thread Safety
- **Problem**: Calling start() twice creates multiple threads
- **Solution**: Always check `self.running` before starting

### Gate Hanging
- **Problem**: Stopping without cleanup leaves gates open
- **Solution**: Always call `stop()`, it sends gate-off to all voices

### Performance Cliffs
- **Problem**: Very fast BPM (>200) can cause timing issues
- **Solution**: Test timing accuracy above 180 BPM, consider larger gate_frac

## Timing System Details

### Epoch-Based Timing
The sequencer uses absolute time references to prevent drift:

```python
step_time = self.epoch_start + (step_index * self.seconds_per_step)
```

This ensures perfect timing over long periods, unlike relative sleep() timing.

### Swing Implementation
Swing is applied to odd-indexed steps (2nd, 4th, 6th...):

```python
if self.swing > 0 and step_index % 2 == 1:
    swing_delay = self.swing * 0.5 * self.seconds_per_step
    return base_time + swing_delay
```

### Gate Timing
Gates are scheduled off using threading.Timer:

```python
gate_time = self.seconds_per_step * track.gate_frac
threading.Timer(gate_time, lambda: send_gate_off()).start()
```

## Red Flags

### Signs of Problems
- Audio dropouts → Engine overload, reduce complexity
- Timing drift → Check BPM too high or system load
- Silent voices → Check voice_id spelling, engine connectivity
- Hanging notes → Missing stop() call or exception during playback

### Common Mistakes
```python
# ❌ WRONG: Invalid voice ID
seq.add_track("kick", "voice5", "X...")  # Only voice1-4 exist

# ❌ WRONG: Forgot to start
seq.add_track("kick", "voice1", "X...")
# seq.start()  # Missing!

# ❌ WRONG: Pattern too complex for BPM
seq = PolySequencer(client, bpm=200)  # Very fast
seq.add_track("complex", "voice1", "XxXxXxXxXxXxXxXx")  # Too dense

# ✅ CORRECT: Proper usage
seq = PolySequencer(client, bpm=140)
seq.add_track("kick", "voice1", "X.x.X.x.", base_freq=60)
seq.start()
time.sleep(10)
seq.stop()
```

## Migration from Legacy APIs

### Deprecated Methods (from old dnb_collab.py)
These methods do NOT exist in current PolySequencer:
- `set_track_pattern()` → Use `update_pattern()`
- `set_track_notes()` → Use `update_notes()`  
- `set_track_velocities()` → Not available, velocities derived from pattern

### Current Approach
```python
# OLD (doesn't work):
seq.set_track_pattern(0, "X...")
seq.set_track_notes(0, [60])

# NEW (correct):
seq.add_track("kick", "voice1", "X...", notes=[60])
# or
seq.update_pattern("kick", "X...")
seq.update_notes("kick", [60])
```

---

## Summary

The PolySequencer provides a robust, low-latency sequencing solution with:
- **4-voice polyphony** with individual parameter control
- **Real-time pattern updates** while running
- **Flexible note formats** (Hz, MIDI, note names)
- **Built-in swing** and precise timing
- **Per-voice effects sends** for spatial mixing

The API is designed for both autonomous AI control and real-time manipulation, making it suitable for live performance and generative music applications.

**Key Success Factor**: Always ensure engine_pyo.py is running before creating sequences, and always call `stop()` for clean shutdown.