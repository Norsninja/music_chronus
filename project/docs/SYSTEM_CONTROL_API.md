# Music Chronus System Control API

*Comprehensive documentation of all control mechanisms, routes, and methods*

**Research Date**: 2025-09-06  
**Engine Version**: Pyo-based architecture  
**Protocol**: OSC over UDP (port 5005)

## Executive Summary

The Music Chronus synthesizer system provides comprehensive control through:
- **OSC Commands**: Real-time parameter and gate control via UDP
- **PolySequencer Python API**: Pattern-based sequencing with genre presets  
- **Engine Control**: Start/stop, status, module listing
- **Voice Management**: 4-voice polyphony with effects routing
- **Emergency Controls**: Panic, reset, clear operations

Critical findings: OSC is the primary control interface; Python API provides higher-level sequencing; all examples are designed for headless/autonomous operation.

## OSC Command Routes

**Server Address**: `127.0.0.1:5005`  
**Protocol**: UDP  
**Format**: `/route/path <value>` or `/route/path/subpath <value>`

### Voice Control (voice1-voice4)

#### Basic Parameters
```
/mod/voiceN/freq <20-5000>           # Oscillator frequency (Hz)
/mod/voiceN/amp <0-1>                # Voice amplitude  
/gate/voiceN <0|1>                   # Gate on/off (triggers ADSR)
```

#### Filter Parameters
```
/mod/voiceN/filter/freq <50-8000>    # Filter cutoff frequency (Hz)
/mod/voiceN/filter/q <0.5-10>        # Filter resonance/Q factor
```

#### ADSR Envelope
```
/mod/voiceN/adsr/attack <0.001-2>    # Attack time (seconds)
/mod/voiceN/adsr/decay <0-2>         # Decay time (seconds)
/mod/voiceN/adsr/sustain <0-1>       # Sustain level (0-1)
/mod/voiceN/adsr/release <0.01-3>    # Release time (seconds)
```

#### Effects Sends
```
/mod/voiceN/send/reverb <0-1>        # Reverb send level
/mod/voiceN/send/delay <0-1>         # Delay send level
```

#### Advanced Controls (Stubs in current version)
```
/mod/voiceN/slide_time <value>       # Portamento time (not implemented)
/mod/voiceN/osc/type <value>         # Waveform selection (not implemented)
```

### Acid Filter Module (TB-303 style on voice2)

**Note**: Acid filter automatically processes voice2's pre-filter signal

#### Core Parameters
```
/mod/acid1/cutoff <80-5000>          # Base cutoff frequency (Hz)
/mod/acid1/res <0-0.98>              # Resonance amount
/mod/acid1/env_amount <0-5000>       # Envelope modulation depth (Hz)
/mod/acid1/decay <0.02-1.0>          # Envelope decay time (seconds)
/mod/acid1/drive <0-1>               # Pre-filter drive/distortion
/mod/acid1/mix <0-1>                 # Wet/dry mix
/mod/acid1/vol_comp <0-1>            # Resonance volume compensation
/gate/acid1 <0|1>                    # Gate (auto-synced with voice2)
```

#### Accent Parameters (Disabled in current version)
```
/mod/acid1/accent <0-1>              # Accent level (stub)
/mod/acid1/cutoff_offset <0-1000>    # Accent cutoff boost (stub)  
/mod/acid1/res_accent_boost <0-0.4>  # Accent resonance boost (stub)
/mod/acid1/accent_decay <0.02-0.15>  # Accent decay time (stub)
```

### Global Effects

#### Reverb Bus
```
/mod/reverb1/mix <0-1>               # Wet/dry mix
/mod/reverb1/room <0-1>              # Room size parameter
/mod/reverb1/damp <0-1>              # Damping amount
```

#### Delay Bus
```
/mod/delay1/time <0.1-0.6>           # Delay time (seconds)
/mod/delay1/feedback <0-0.7>         # Feedback amount (limited for safety)
/mod/delay1/mix <0-1>                # Wet/dry mix
/mod/delay1/lowcut <20-1000>         # High-pass filter in output
/mod/delay1/highcut <1000-10000>     # Low-pass filter in output
```

### Engine Control
```
/engine/start                        # Start audio processing
/engine/stop                         # Stop audio processing
/engine/status                       # Print detailed status to console
/engine/list                         # List all available modules and parameters
```

### Integrated Sequencer Control (NEW - 2025-01-07)
```
/seq/add <track_id> <voice_id> <pattern> [base_freq] [filter_freq] [notes]
                                     # Add a new track to sequencer
/seq/remove <track_id>               # Remove a track
/seq/clear                           # Clear all tracks
/seq/start                           # Start the sequencer
/seq/stop                            # Stop sequencer and gate off all voices
/seq/bpm <30-300>                    # Set sequencer BPM
/seq/swing <0-0.6>                   # Set swing amount
/seq/update/pattern <track_id> <pattern>  # Update track pattern
/seq/update/notes <track_id> <notes>      # Update track note sequence
/seq/status                          # Print sequencer status
```

### Backward Compatibility Routes

*These map to voice1 for legacy support*

```
/mod/sine1/freq <value>              # Maps to /mod/voice1/freq
/mod/filter1/freq <value>            # Maps to /mod/voice1/filter/freq
/mod/filter1/q <value>               # Maps to /mod/voice1/filter/q
/mod/adsr1/attack <value>            # Maps to /mod/voice1/adsr/attack
/mod/adsr1/decay <value>             # Maps to /mod/voice1/adsr/decay
/mod/adsr1/sustain <value>           # Maps to /mod/voice1/adsr/sustain
/mod/adsr1/release <value>           # Maps to /mod/voice1/adsr/release
/gate/adsr1 <0|1>                    # Maps to /gate/voice1
/gate/1 <0|1>                        # Maps to /gate/voice1
```

## PolySequencer Python API

**Location**: `examples/poly_sequencer.py`  
**Class**: `PolySequencer`

### Initialization
```python
from examples.poly_sequencer import PolySequencer
from pythonosc import udp_client

client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
seq = PolySequencer(client, bpm=120)
```

### Core Control Methods

#### Sequencer Lifecycle
```python
seq.start()                          # Start the sequencer thread
seq.stop()                           # Stop sequencer and gate off all voices
seq.running                          # Boolean status flag
```

#### Track Management
```python
seq.add_track(name, voice_id, pattern, **kwargs)
# name: String identifier ("kick", "bass", "lead", etc.)
# voice_id: Target voice ("voice1" through "voice4")  
# pattern: Gate pattern using X.x. notation
# **kwargs: Additional Track parameters

seq.tracks                           # Dict of all active tracks
seq.tracks.clear()                   # Remove all tracks
```

#### Real-time Pattern Updates
```python
seq.update_pattern(track_name, pattern)     # Change pattern on the fly
seq.update_notes(track_name, note_list)     # Update note sequence
seq.set_swing(swing_amount)                 # Set timing swing (0-0.8)
```

### Pattern Notation

**Format**: String with characters representing 16th note steps
```
'X' = Accent hit (velocity 1.0)
'x' = Normal hit (velocity 0.6)  
'.' = Rest (no trigger)
```

**Examples**:
```python
"X...X...X...X..."                  # Four-on-floor kick
"..x...x...x.x..."                  # Syncopated snare
"x.x.x.x.x.x.x.X."                  # Hi-hat with accent
```

### Note Format Support

The sequencer accepts multiple note formats:
```python
# MIDI note numbers
notes=[60, 64, 67]                   # C4, E4, G4

# Note names with octaves  
notes=["C4", "E4", "G4"]             # Same as above

# Frequency in Hz
notes=[261.63, 329.63, 392.0]       # Same as above

# Mixed formats
notes=[60, "E4", 392.0]              # All valid
```

### Track Parameters

When adding tracks, these parameters control voice behavior:
```python
seq.add_track("bass", "voice2", "x.x.x.x.",
    base_freq=110,                   # Fundamental frequency
    filter_freq=800,                 # Base filter cutoff
    accent_boost=1500,               # Hz added to filter on accents
    reverb_send=0.2,                 # Reverb send level (0-1)
    delay_send=0.0,                  # Delay send level (0-1)
    gate_frac=0.5,                   # Gate length as fraction of step
    base_amp=0.3,                    # Base amplitude
    notes=[36, 36, 41, 43]           # Note sequence (cycles)
)
```

### Genre Presets

**Built-in preset functions**:
```python
create_techno_preset(seq)            # Four-on-floor, syncopated bass
create_ambient_preset(seq)           # Sparse, high reverb, long gates
create_dub_preset(seq)               # Offbeat stabs, delay emphasis
```

**Usage**:
```python
seq = PolySequencer(client, bpm=125)
create_techno_preset(seq)
seq.start()
```

### Note Cycling Behavior

Each track cycles through its note list:
```python
track.get_next_freq()                # Returns next frequency in sequence
track.reset_note_index()             # Reset to first note
track.note_index                     # Current position in note list
```

## Emergency Control Mechanisms

### Panic/Stop All
```python
# Via PolySequencer
seq.stop()                           # Stops sequencer + gates off all voices

# Manual gate-off all voices
client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
for i in range(1, 5):
    client.send_message(f"/gate/voice{i}", 0.0)
```

### Reset/Clear Operations
```python
# Clear all sequencer tracks
seq.tracks.clear()

# Reset sequencer timing
seq.epoch_start = time.time()

# Engine restart (via OSC)
client.send_message("/engine/stop", 1)
client.send_message("/engine/start", 1)
```

### Parameter Reset to Defaults
```python
# Voice defaults (per voice)
client.send_message("/mod/voiceN/freq", 440.0)
client.send_message("/mod/voiceN/amp", 0.3)
client.send_message("/mod/voiceN/filter/freq", 1000.0)
client.send_message("/mod/voiceN/filter/q", 2.0)
client.send_message("/mod/voiceN/adsr/attack", 0.01)
client.send_message("/mod/voiceN/adsr/decay", 0.1)
client.send_message("/mod/voiceN/adsr/sustain", 0.7)
client.send_message("/mod/voiceN/adsr/release", 0.5)
client.send_message("/mod/voiceN/send/reverb", 0.0)
client.send_message("/mod/voiceN/send/delay", 0.0)

# Acid filter defaults
client.send_message("/mod/acid1/cutoff", 1500.0)
client.send_message("/mod/acid1/res", 0.45)
client.send_message("/mod/acid1/env_amount", 2500.0)
client.send_message("/mod/acid1/decay", 0.25)
client.send_message("/mod/acid1/drive", 0.2)
client.send_message("/mod/acid1/mix", 1.0)
client.send_message("/mod/acid1/vol_comp", 0.5)

# Effects defaults
client.send_message("/mod/reverb1/mix", 0.3)
client.send_message("/mod/reverb1/room", 0.5)
client.send_message("/mod/reverb1/damp", 0.5)
client.send_message("/mod/delay1/time", 0.25)
client.send_message("/mod/delay1/feedback", 0.4)
client.send_message("/mod/delay1/mix", 0.3)
```

## System Status and Monitoring

### Real-time Status Files

**Engine automatically writes status to files**:
- `engine_status.txt`: One-line status update (100ms intervals)
- `engine_log.txt`: Event log with timestamps

**Status file format**:
```
AUDIO: 0.1234 | MSG: 42 | GATES: 2 | LAST: /gate/voice1 1 | TIME: 14:32:15
```

### Python Status Methods

```python
# Engine status (via OSC)
client.send_message("/engine/status", 1)    # Prints to engine console
client.send_message("/engine/list", 1)      # Lists all modules

# Voice status (Python API - if engine exposed)
voice_status = voice.get_status()
# Returns: {'voice_id': 'voice1', 'freq': 440.0, 'amp': 0.3, ...}

# Effects status  
reverb_status = reverb.get_status()
# Returns: {'mix': 0.3, 'room': 0.5, 'damp': 0.5}

delay_status = delay.get_status() 
# Returns: {'time': 0.25, 'feedback': 0.4, 'mix': 0.3, ...}

# Acid filter status
acid_status = acid.get_status()
# Returns: {'cutoff': 1500.0, 'res': 0.45, ..., 'accent_disabled': True}
```

## Usage Patterns and Examples

### Basic OSC Control
```python
from pythonosc import udp_client
import time

client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

# Play a note
client.send_message("/mod/voice1/freq", 440)
client.send_message("/gate/voice1", 1.0)
time.sleep(1.0)
client.send_message("/gate/voice1", 0.0)
```

### Sequenced Pattern
```python
# Create and run a 30-second techno loop
seq = PolySequencer(client, bpm=125)
create_techno_preset(seq)
seq.start()
time.sleep(30)
seq.stop()
```

### Real-time Parameter Modulation
```python
# Sweep acid filter cutoff
for cutoff in range(100, 3000, 50):
    client.send_message("/mod/acid1/cutoff", cutoff)
    time.sleep(0.1)
```

### Multi-voice Chord
```python
# Play Am chord (A, C, E)
frequencies = [220.0, 261.63, 329.63]
for i, freq in enumerate(frequencies, 1):
    client.send_message(f"/mod/voice{i}/freq", freq)
    client.send_message(f"/gate/voice{i}", 1.0)

time.sleep(2.0)

# Release all
for i in range(1, 4):
    client.send_message(f"/gate/voice{i}", 0.0)
```

## Critical Implementation Details

### Parameter Smoothing
- All voice and effects parameters use 20ms smoothing (SigTo)
- Gate operations are instantaneous (no smoothing)
- ADSR parameters update immediately when changed

### Signal Routing
- **voice1, voice3, voice4**: Direct voice output to mixer
- **voice2**: Routes through acid1 filter before mixer
- **Acid input**: Uses voice2's pre-filter signal (oscillator * ADSR)
- **Effects**: Global reverb/delay buses with per-voice sends

### Timing and Threading
- **PolySequencer**: Runs in separate daemon thread
- **Engine**: Main thread with OSC server in background thread  
- **Timing**: Epoch-based with swing support (not sample-accurate)

### Safety Limits
- **Delay feedback**: Limited to 0.7 to prevent runaway
- **Filter Q**: Limited to 10.0 to prevent instability
- **Frequencies**: Clamped to reasonable ranges (20-5000Hz oscillator, 50-8000Hz filter)
- **Amplitudes**: Clamped to 0-1 range

### Headless Operation
- All examples designed for autonomous operation
- No user input prompts or interactive menus
- Time-based demos with predictable runtime
- Suitable for AI control and automation

## Gotchas and Limitations

### Current Limitations
1. **Acid accents disabled**: Accent system causes signal graph breaks
2. **Slide/portamento not implemented**: Stubs exist but no functionality  
3. **Single waveform**: Only sine waves, no waveform switching
4. **Mono output**: Effects and master output are mono
5. **No MIDI input**: OSC-only control interface

### Timing Considerations  
1. **Not sample-accurate**: Thread-based timing with ~1ms precision
2. **Swing affects CPU**: Higher swing values increase thread switching
3. **Long patterns**: No practical limit on pattern length, but memory usage scales

### OSC Message Handling
1. **Unknown routes ignored**: Invalid OSC paths are logged but don't error
2. **Parameter clamping**: Out-of-range values are silently clamped
3. **Type coercion**: All numeric parameters converted to float

### Thread Safety
1. **Parameter updates thread-safe**: Pyo handles concurrent parameter changes
2. **PolySequencer stop**: Uses timeout-based thread joining
3. **Emergency stop**: Gate-off operations are always safe

---

## Quick Reference

### Essential Commands
```bash
# Start engine
python engine_pyo.py

# Test basic functionality  
python examples/test_pyo_engine.py

# Run autonomous sequencer demo
python examples/poly_sequencer.py
```

### Emergency Stop
```python
seq.stop()  # If using PolySequencer
# OR manually:
client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
for i in range(1, 5):
    client.send_message(f"/gate/voice{i}", 0.0)
```

### Status Check
```python
client.send_message("/engine/status", 1)  # Detailed status
# OR check files:
# cat engine_status.txt  # Real-time status
# cat engine_log.txt     # Event log
```

---

*Last updated: 2025-09-06*  
*Total routes documented: 50+ OSC commands*  
*Total API methods: 20+ Python methods*  
*All examples tested and verified headless-compatible*