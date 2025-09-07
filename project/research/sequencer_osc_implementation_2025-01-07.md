# Sequencer OSC Implementation Research - 2025-01-07

## Executive Summary

The Music Chronus sequencer OSC commands are implemented through a robust multi-layer architecture with specific syntax requirements for multi-argument messages. The `/seq/add` command accepts both positional and key=value arguments, with built-in error handling to prevent server crashes.

## Scope

Investigated the complete OSC sequencer implementation in `engine_pyo.py`, focusing on:
- `handle_seq_add()` method argument processing
- `SequencerManager.add_track()` parameter handling
- pythonosc multi-argument syntax patterns
- Error handling and server stability measures
- Working examples from project documentation

## Key Findings

### Pattern Analysis

#### OSC Handler Implementation
- File: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- Lines: 1251-1293
- Purpose: Handle `/seq/add` OSC messages with flexible argument parsing

```python
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
                    kwargs[key] = float(value)
                except:
                    kwargs[key] = value
            else:
                # Positional args mapping
                if i == 3:
                    kwargs['base_freq'] = float(arg)
                elif i == 4:
                    kwargs['filter_freq'] = float(arg)
                elif i == 5:
                    kwargs['notes'] = arg
```

#### SequencerManager Track Creation
- File: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- Lines: 184-201
- Purpose: Create Track objects from parsed OSC arguments

```python
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
```

### Implementation Details

#### Track Data Structure
- File: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- Lines: 29-59
- Purpose: Define track parameters and defaults

```python
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
```

#### Parameter Registry Schema
- File: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- Lines: 593-597
- Purpose: Document expected `/seq/add` arguments

```python
"/seq/add": {
    "args": ["track_id", "voice_id", "pattern", "[base_freq]", "[filter_freq]", "[notes]"],
    "description": "Add a new track to the sequencer",
    "example": "/seq/add kick voice1 X...X...X...X... 60 200"
}
```

### Code Flow

1. **OSC Message Reception**: OSC server receives `/seq/add` message with arguments
2. **Handler Dispatch**: `handle_seq_add()` method processes arguments
3. **Argument Parsing**: Supports both positional and key=value formats
4. **Track Creation**: `SequencerManager.add_track()` creates Track object
5. **Note Parsing**: String notes converted to frequency list if provided
6. **Thread-Safe Storage**: Track added to sequencer with lock protection

### Related Components

#### OSC Server Setup
- File: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- Lines: 1010-1014
- Purpose: Register `/seq/add` route with metadata

```python
self.map_route("/seq/add", self.handle_seq_add,
              meta={"args": ["track_id", "voice_id", "pattern", "[base_freq]", "[filter_freq]", "[notes]"],
                    "description": "Add a new track to the sequencer",
                    "example": "/seq/add kick voice1 X...X...X...X... 60 200"})
```

#### Error Handling Strategy
- File: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- Lines: 1253-1255
- Purpose: Prevent server crashes from malformed messages

```python
if len(args) < 3:
    print(f"[OSC] /seq/add requires at least 3 args: track_id voice_id pattern")
    return
```

## File Inventory

### Core Implementation Files
- `E:\TidalCyclesChronus\music_chronus\engine_pyo.py` - Main sequencer and OSC handling
  - Lines 29-59: Track dataclass definition
  - Lines 184-201: SequencerManager.add_track() method
  - Lines 1251-1293: handle_seq_add() OSC handler
  - Lines 1010-1014: OSC route registration with metadata

### Working Examples Documentation
- `E:\TidalCyclesChronus\music_chronus\project\handoffs\2025-01-07_sequencer_osc_integration_complete.md` - Contains validated working examples
  - Line 121: Basic usage example
  - Lines 132-134: Multi-track examples with all argument types
- `E:\TidalCyclesChronus\music_chronus\project\research\music_chronus_complete_capabilities_2025-01-07.md` - Additional usage patterns
  - Lines 590-591: Simple pattern examples

### Test Files
- `E:\TidalCyclesChronus\music_chronus\test_recording.py` - Shows proper pythonosc syntax patterns
  - Lines 27,72: Single argument examples (`None` parameter)
  - Lines 32-67: Multi-argument examples with proper syntax

## Technical Notes

### pythonosc Multi-Argument Syntax Requirements

**Correct Syntax Patterns:**
```python
# Single argument (use None for empty)
client.send_message("/engine/record/start", None)

# Multiple arguments (use list)
client.send_message('/seq/add', ['kick', 'voice1', 'X...X...X...X...', 60.0, 200.0])

# Complex example with notes
client.send_message('/seq/add', ['bass', 'voice2', 'x.x.....x.x.....', 110.0, 800.0, '36,36,41,43'])
```

**Argument Processing Logic:**
1. **Required Arguments**: `track_id`, `voice_id`, `pattern` (minimum 3)
2. **Optional Positional**: Arguments 4-6 map to `base_freq`, `filter_freq`, `notes`
3. **Key=Value Format**: Arguments containing `=` are parsed as key-value pairs
4. **Type Conversion**: Float conversion attempted for numeric values

### Error Prevention Measures

**Server Stability:**
- Minimum argument validation prevents crashes
- Try-catch blocks around float conversions
- Thread-safe operations with locks
- Graceful degradation on parsing errors

**Common Failure Points:**
- Sending arguments without list wrapper causes crashes
- Missing required arguments triggers validation error
- Invalid numeric strings are caught and ignored
- Threading issues prevented by SequencerManager locks

### Pattern Notation Support

**Standard Patterns:**
- `X` = Accent hit (velocity 1.0)
- `x` = Normal hit (velocity 0.6)  
- `.` = Rest (no trigger)

**Note Format Support:**
- Frequency in Hz: `440.0, 880.0`
- MIDI numbers: `36, 41, 43`
- Note names: `C4, F#3` (parsed by `_note_to_freq`)

### Integration Points

**Voice System Integration:**
- Tracks target specific voice instances (`voice1`-`voice4`)
- Voice parameters controlled via `/mod/voiceN/*` routes
- Gate control through `/gate/voiceN` messages

**Effects Integration:**
- Reverb/delay sends per track
- Master distortion applied after track mixing
- LFO modulation on designated voices

**Pattern Management:**
- Save/load functionality through `/pattern/*` routes
- Bar-aligned loading for seamless transitions
- Atomic file operations prevent corruption