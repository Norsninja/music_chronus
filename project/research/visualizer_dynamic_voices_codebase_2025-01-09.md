# Dynamic Voice Configuration Research - 2025-01-09

## Executive Summary

The Music Chronus codebase handles dynamic voice configuration through environment variables, registry-based auto-discovery, and adaptive OSC routing. The engine supports 1-16 configurable voices via `CHRONUS_NUM_VOICES`, with the visualizer designed to display exactly 4 voices in a fixed layout. This research identifies patterns for scaling the visualizer to support dynamic voice counts while maintaining consistency with the existing architecture.

## Scope

This investigation examined dynamic configuration patterns across the Music Chronus codebase, focusing on:
- Engine voice configuration and OSC broadcast adaptation
- Visualizer architecture and display panel generation
- Configuration patterns and environment variable usage
- OSC communication protocols and data formatting
- Rich UI layout structures and scaling strategies

## Key Findings

### Pattern Analysis

#### Engine Voice Configuration
- **File**: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- **Lines**: 495-499, 734-743
- **Purpose**: Dynamic voice creation based on environment variable
```python
num_voices = int(os.environ.get('CHRONUS_NUM_VOICES', '4'))
num_voices = max(1, min(16, num_voices))  # Clamp between 1-16

# Create N voices
self.voices = {}
for i in range(1, num_voices + 1):
    voice_id = f"voice{i}"
    self.voices[voice_id] = Voice(voice_id, self.server)
```

#### Registry Schema Generation
- **File**: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- **Lines**: 498-524
- **Purpose**: Dynamic schema generation for OSC parameter registry
```python
# Generate voice instances dynamically
voice_instances = [f"voice{i}" for i in range(1, num_voices + 1)]

self.registry = {
    "modules": {
        "voice": {
            "instances": voice_instances,
            "params": { /* voice parameters */ }
        }
    }
}
```

#### OSC Broadcast Adaptation
- **File**: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- **Lines**: 950-961
- **Purpose**: Voice level monitoring scales with voice count
```python
voice_levels = []
for voice_id in sorted(self.voices.keys()):
    if voice_id in self.voice_meters:
        level = float(self.voice_meters[voice_id].get())
        voice_levels.append(max(0.0, min(1.0, level)))
    else:
        voice_levels.append(0.0)

self.viz_broadcast.send_message('/viz/levels', voice_levels)
```

### Implementation Details

#### Environment Variable Configuration Pattern
- **File**: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- **Lines**: 671-674
- **Purpose**: Centralized configuration through environment variables
```python
sample_rate = sample_rate or int(os.environ.get('CHRONUS_SAMPLE_RATE', 48000))
buffer_size = buffer_size or int(os.environ.get('CHRONUS_BUFFER_SIZE', 256))
device_id = device_id if device_id is not None else int(os.environ.get('CHRONUS_DEVICE_ID', -1))
self.verbose = os.environ.get('CHRONUS_VERBOSE', '').lower() in ('1', 'true', 'yes')
```

#### Voice Routing and Effects Integration
- **File**: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- **Lines**: 776-785
- **Purpose**: Dynamic signal routing adapts to voice count
```python
dry_signals = []
for i in range(1, num_voices + 1):
    voice_id = f"voice{i}"
    if voice_id == 'voice2' and acid_output is not None:
        dry_signals.append(acid_output)
    else:
        dry_signals.append(self.voices[voice_id].get_dry_signal())

self.dry_mix = Mix(dry_signals, voices=1)
```

### Code Flow

#### Engine Initialization Flow
1. **Environment Detection**: Read `CHRONUS_NUM_VOICES` with 4-voice default
2. **Registry Generation**: Create dynamic parameter schema with voice instances
3. **Voice Creation**: Instantiate N voices with consistent naming (voice1-voiceN)
4. **Signal Routing**: Build audio routing with dynamic voice count awareness
5. **OSC Registration**: Map routes for all created voices using dynamic patterns
6. **Monitoring Setup**: Create per-voice meters and broadcast arrays

#### Visualizer Architecture Flow
1. **Fixed Layout**: Hard-coded 4-voice display structure
2. **OSC Reception**: Listen for `/viz/levels` with variable-length arrays
3. **Data Processing**: Handle arrays with safety checks for NaN/invalid values
4. **Display Generation**: Create fixed 4-row voice level display
5. **Rich UI Update**: Refresh panels with static layout structure

### Related Components

#### Voice Module Integration
- **File**: `E:\TidalCyclesChronus\music_chronus\pyo_modules\voice.py`
- **Lines**: 268-309
- **Purpose**: Consistent parameter schema across all voice instances
```python
def get_schema(self):
    return {
        "name": f"Voice ({self.voice_id})",
        "type": "voice",
        "params": { /* standardized voice parameters */ }
    }
```

#### OSC Parameter Routing
- **File**: `E:\TidalCyclesChronus\music_chronus\engine_pyo.py`
- **Lines**: 1190-1214
- **Purpose**: Dynamic voice parameter routing by voice ID
```python
if module_id.startswith('voice'):
    if module_id in self.voices:
        voice = self.voices[module_id]
        # Route parameters to specific voice instance
```

#### Rich UI Layout Structure
- **File**: `E:\TidalCyclesChronus\music_chronus\visualizer.py`
- **Lines**: 70-86, 203-250
- **Purpose**: Fixed layout with hard-coded voice display count
```python
for i in range(4):  # Hard-coded 4 voices
    level = self.audio_levels[i]
    # Fixed voice display logic
```

## File Inventory

### Core Configuration Files
- `engine_pyo.py` - Primary dynamic voice configuration and OSC broadcasting
- `visualizer.py` - Static 4-voice display layout and OSC message handling
- `pyo_modules/voice.py` - Voice module with consistent parameter schema

### Environment Variable References
- `engine_pyo.py:495` - `CHRONUS_NUM_VOICES` primary usage in registry
- `engine_pyo.py:734` - `CHRONUS_NUM_VOICES` usage in voice creation
- `engine_pyo.py:671-674` - Audio system configuration variables
- Multiple handoff documents - Historical usage patterns

### OSC Communication Files
- `check_spectrum_broadcast.py` - OSC broadcast testing utility
- `test_spectrum_debug.py` - Visualization data flow debugging
- Engine status monitoring files - Real-time data sources

### Pattern Save/Load System
- Pattern serialization handles dynamic voice counts in module state capture
- Voice restoration iterates over existing voices dynamically
- No hardcoded voice assumptions in persistence layer

## Technical Notes

### Configuration Consistency Patterns
1. **Environment Variable Pattern**: `CHRONUS_*` prefix with sensible defaults
2. **Registry Auto-Update**: Schema reflects actual engine configuration
3. **Clamp and Validate**: All numeric inputs clamped to safe ranges (1-16 voices)
4. **Graceful Fallbacks**: Missing voices ignored, extra data discarded safely

### OSC Message Format Standards
- **Voice Levels**: `/viz/levels` with variable-length float array
- **Spectrum Data**: `/viz/spectrum` with fixed 8-band frequency analysis
- **Parameter Control**: `/mod/voiceN/param` with consistent routing patterns
- **Gate Control**: `/gate/voiceN` with unified voice triggering

### Display Scaling Requirements
1. **Dynamic Voice Count Detection**: Query engine for actual voice count
2. **Layout Adaptation**: Rich layout must accommodate 1-16 voice displays
3. **Data Array Handling**: Voice level arrays may contain 1-16 elements
4. **Error Boundaries**: Handle mismatched data gracefully with defaults

### Thread Safety Considerations
- Engine voice creation is single-threaded during initialization
- OSC broadcast uses thread-safe data collection with locks
- Visualizer data processing must handle concurrent OSC updates
- Registry updates are atomic and don't require locking

### Memory and Performance Patterns
- Voice instances are created once and reused throughout session
- OSC broadcast arrays are recreated on each update cycle
- Rich UI updates are rate-limited to target FPS (20Hz default)
- Pattern save/load captures complete state without deepcopy

---

*Generated for AI consumption - contains precise file references and implementation patterns for dynamic voice configuration scaling*