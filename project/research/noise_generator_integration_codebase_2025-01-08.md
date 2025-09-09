# Noise Generator Integration Research - 2025-01-08

## Executive Summary

This research analyzes the Music Chronus voice architecture for integrating noise generators alongside the existing waveform oscillators. The system uses a Selector-based approach with pre-built oscillator tables that would cleanly accommodate noise sources. The integration requires updates to schema registration, OSC routing, and Voice class modifications.

## Scope

Investigation covers:
- Voice class architecture in pyo_modules/voice.py
- Waveform selection via Selector object
- OSC parameter routing system
- Schema registration patterns
- Signal flow from oscillator through ADSR to filter
- Integration patterns from other modules (DistortionModule, SimpleLFOModule)

## Key Findings

### Pattern Analysis

#### Current Waveform Architecture
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\voice.py
- Lines: 70-103
- Purpose: Multi-oscillator setup with Selector crossfading

```python
# Create waveform tables
self.sine_table = HarmTable([1], size=8192)  # Pure sine
self.saw_table = SawTable(order=12, size=8192).normalize()  # Band-limited saw
self.square_table = SquareTable(order=10, size=8192).normalize()  # Band-limited square

# Create oscillators for each waveform (all running simultaneously)
self.osc_sine = Osc(table=self.sine_table, freq=self.ported_freq, mul=self.adsr)
self.osc_saw = Osc(table=self.saw_table, freq=self.ported_freq, mul=self.adsr)
self.osc_square = Osc(table=self.square_table, freq=self.ported_freq, mul=self.adsr)

# Waveform selector control (0=sine, 1=saw, 2=square)
self.waveform_select = Sig(0)

# Selector with equal-power crossfade for click-free switching
self.osc = Selector([self.osc_sine, self.osc_saw, self.osc_square], voice=self.waveform_select)
self.osc.setMode(1)  # Mode 1 = equal-power crossfade
```

#### OSC Routing Pattern
- File: E:\TidalCyclesChronus\music_chronus\engine_pyo.py
- Lines: 1175-1176
- Purpose: Map osc/type parameter to waveform selection

```python
elif param == 'osc/type':
    voice.set_waveform(value)
```

#### Route Registration System
- File: E:\TidalCyclesChronus\music_chronus\engine_pyo.py
- Lines: 968-987
- Purpose: Atomic route registration with metadata

```python
def map_route(self, path, handler, meta=None):
    # Register the route
    self.registered_routes[path] = {
        "handler": handler,
        "meta": meta or {}
    }
    # Map to dispatcher
    self.dispatcher.map(path, handler)
```

### Implementation Details

#### Available Noise Objects in Pyo
Discovered via runtime inspection: `['BrownNoise', 'EventNoise', 'Noise', 'PinkNoise', 'TrigXnoise', 'Xnoise']`

Key noise types for integration:
- `Noise`: White noise generator
- `PinkNoise`: 1/f noise (pink noise) 
- `BrownNoise`: Brown/red noise (1/f² slope)

#### Module Schema Pattern
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\voice.py
- Lines: 281-302
- Purpose: Parameter schema with validation ranges

```python
def get_schema(self):
    return {
        "name": f"Voice ({self.voice_id})",
        "type": "voice",
        "params": {
            "osc/type": {"type": "int", "min": 0, "max": 2, "default": 0, 
                        "notes": "0=sine, 1=saw, 2=square"}
        }
    }
```

#### Parameter Validation Pattern
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\voice.py
- Lines: 249-260
- Purpose: Input validation with fallback to safe defaults

```python
def set_waveform(self, waveform):
    waveform = int(waveform)
    if waveform < 0 or waveform > 2:
        print(f"[VOICE] Warning: Invalid waveform {waveform}, using 0 (sine)")
        waveform = 0
    self.waveform_select.value = waveform
```

### Code Flow

#### Signal Chain Architecture
1. **Oscillator Layer**: Multiple oscillators running simultaneously
   - Table-based: Osc(table, freq, mul=adsr)
   - Would add: Noise generators (no freq dependency)
2. **Selection Layer**: Selector object with equal-power crossfade
3. **Envelope Layer**: ADSR applied via mul parameter
4. **Filter Layer**: Biquad lowpass with smoothed parameters
5. **Mix Layer**: Individual voice signals mixed via Mix object

#### Parameter Flow
1. OSC message: `/mod/voice1/osc/type <value>`
2. Route handler: `handle_mod_param()` in engine_pyo.py
3. Parameter dispatch: `elif param == 'osc/type': voice.set_waveform(value)`
4. Voice method: `set_waveform()` validates and sets `waveform_select.value`
5. Selector updates: Real-time crossfade between oscillator outputs

#### Initialization Flow
- File: E:\TidalCyclesChronus\music_chronus\engine_pyo.py
- Lines: 726-731
- Purpose: Voice creation during engine startup

```python
# Create 4 voices
self.voices = {}
for i in range(1, 5):
    voice_id = f"voice{i}"
    self.voices[voice_id] = Voice(voice_id, self.server)
```

### Related Components

#### Module Integration Examples

**DistortionModule Pattern**:
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\distortion.py
- Schema method: Returns complete parameter definitions
- OSC routing: Handled via wildcard `/mod/*/*` pattern
- Safety: Emergency clipping and DC blocking

**SimpleLFOModule Pattern**:
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\simple_lfo.py
- Smoothed parameters: SigTo objects for zipper-free control
- Output scaling: Multiple scaled outputs for different uses

#### Dependency Chain
- Voice class imports: `from pyo import *`
- Engine registration: `self.register_module_schema()` 
- Schema validation: Individual module `get_schema()` methods
- Route mapping: Centralized `map_route()` wrapper

## File Inventory

### Core Architecture Files
- **E:\TidalCyclesChronus\music_chronus\pyo_modules\voice.py** - Primary voice implementation, waveform selection
- **E:\TidalCyclesChronus\music_chronus\engine_pyo.py** - OSC routing, schema registration, voice initialization

### Integration Pattern Examples
- **E:\TidalCyclesChronus\music_chronus\pyo_modules\distortion.py** - Module schema and safety patterns
- **E:\TidalCyclesChronus\music_chronus\pyo_modules\simple_lfo.py** - Parameter smoothing patterns

### Test Reference Files
- **E:\TidalCyclesChronus\music_chronus\test_waveforms_complete.py** - OSC control examples for waveform switching
- **E:\TidalCyclesChronus\music_chronus\test_saw_oscillator.py** - Demonstrates /mod/voice1/osc/type usage

## Technical Notes

### Integration Requirements

#### 1. Voice Class Modifications Required
- Add noise generator objects (Noise, PinkNoise, BrownNoise)
- Extend Selector input list to include noise sources
- Update `set_waveform()` validation range (0-5 instead of 0-2)
- Update `get_schema()` parameter definitions

#### 2. Schema Registry Updates
- File: E:\TidalCyclesChronus\music_chronus\engine_pyo.py
- Lines: 500-516 (voice module schema)
- Update: `"osc/type": {"max": 5, "notes": "0=sine, 1=saw, 2=square, 3=noise, 4=pink, 5=brown"}`

#### 3. Noise Generator Characteristics
- **No frequency dependency**: Noise generators don't use freq parameter
- **Amplitude scaling**: Use mul=self.adsr like other oscillators
- **Thread safety**: Pyo noise generators are C-based, thread-safe

#### 4. Safety Considerations
- **Volume matching**: Noise can be louder than tonal oscillators
- **DC blocking**: Already implemented in distortion module pattern
- **Filter interaction**: Noise provides full-spectrum input to filter

#### 5. Backward Compatibility
- **Existing presets**: Waveform indices 0-2 remain unchanged
- **OSC routes**: No changes to existing `/mod/voice*/osc/type` routing
- **Schema validation**: Expanded range maintains existing validation pattern

### Recommended Implementation Approach

#### Phase 1: Core Integration
1. **Extend Voice.__init__()**:
   - Add `self.osc_noise = Noise(mul=self.adsr)`
   - Add `self.osc_pink = PinkNoise(mul=self.adsr)`  
   - Add `self.osc_brown = BrownNoise(mul=self.adsr)`

2. **Update Selector**:
   - Extend input list: `[sine, saw, square, noise, pink, brown]`
   - Test crossfading behavior with noise sources

3. **Update Validation**:
   - Change `set_waveform()` max value from 2 to 5
   - Update schema `"max": 5` and notes

#### Phase 2: Testing and Optimization  
1. **Volume calibration**: Compare noise levels to tonal oscillators
2. **Filter response**: Test noise through existing Biquad filter
3. **Integration testing**: Verify ADSR envelope response with noise

#### Phase 3: Documentation and Examples
1. **Update schema documentation**
2. **Create noise-specific test scripts**
3. **Update existing test files with noise examples**

### Potential Compatibility Issues

#### 1. Volume Level Differences
- **Issue**: Noise generators may have different output levels than tonal oscillators
- **Solution**: Apply gain compensation in oscillator creation
- **Pattern**: Similar to distortion module `comp_gain` scaling

#### 2. Filter Frequency Response
- **Issue**: Full-spectrum noise may behave differently than tonal input
- **Solution**: Existing Biquad filter should handle this naturally
- **Testing**: Verify filter sweep behavior with noise input

#### 3. ADSR Envelope Interaction
- **Issue**: Noise attack/decay characteristics differ from tonal
- **Solution**: No code changes needed, envelope applied via mul parameter
- **Verification**: Test envelope shapes with different noise types

#### 4. LFO Modulation Compatibility
- **Issue**: Frequency modulation doesn't apply to noise generators
- **Solution**: Amplitude LFO still works, filter LFO provides spectral movement
- **Documentation**: Update LFO usage notes for noise sources

The architecture is well-designed for this integration with minimal breaking changes required.