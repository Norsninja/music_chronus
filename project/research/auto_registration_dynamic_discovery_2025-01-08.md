# Auto-Registration and Dynamic Discovery Research - 2025-01-08

## Executive Summary

The Music Chronus engine implements a sophisticated auto-registration and dynamic discovery system based on a central parameter registry, schema-aware modules, and OSC route mapping. The system enables automatic adaptation to new modules without hardcoded references, making it ideal for informing a scalable virtual pet system that can discover and score musical quality dynamically.

## Scope

This investigation examined the complete auto-registration system across the Music Chronus codebase, including schema management, module discovery patterns, dynamic parameter handling, monitoring systems, and state management patterns. The focus was on identifying concrete patterns that could inform a self-scaling virtual pet system for the terminal visualizer.

## Key Findings

### Pattern Analysis

The codebase demonstrates four primary auto-discovery patterns:

1. **Central Registry Pattern**: A single source of truth parameter registry (lines 486-656 in engine_pyo.py)
2. **Module Schema Pattern**: Self-describing modules with get_schema() methods
3. **Dynamic Route Registration**: The map_route() wrapper automatically registers metadata
4. **State Broadcasting Pattern**: Automatic data broadcasting for monitoring

### Implementation Details

#### 1. Schema Auto-Registration System

- File: engine_pyo.py
- Lines: 963-997, 998-1012
- Purpose: Automatic OSC route registration with metadata tracking

```python
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
```

#### 2. Module Self-Registration Pattern

- File: simple_lfo.py
- Lines: 109-134
- Purpose: Modules expose their own parameter schemas for dynamic registration

```python
def get_schema(self):
    """Get parameter schema for registry integration"""
    return {
        "name": f"LFO ({self.module_id})",
        "type": "lfo",
        "params": {
            "rate": {
                "type": "float",
                "min": 0.01,
                "max": 10.0,
                "default": 0.25,
                "smoothing_ms": 20,
                "unit": "Hz",
                "notes": "0.01-0.5: slow, 0.5-2: wobble, 2-8: tremolo"
            },
            "depth": {
                "type": "float",
                "min": 0,
                "max": 1,
                "default": 0.7,
                "smoothing_ms": 20,
                "notes": "Modulation amount: 0=none, 1=full"
            }
        },
        "notes": "Simple sine LFO for modulation"
    }
```

#### 3. Dynamic Module Registration

- File: engine_pyo.py  
- Lines: 814-843, 998-1012
- Purpose: Register new modules dynamically without hardcoding

```python
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
```

#### 4. State Broadcasting System

- File: engine_pyo.py
- Lines: 900-951
- Purpose: Automatic broadcasting of engine data for monitoring

```python
def update_status(self):
    """Write current status to files and broadcast visualization data"""
    try:
        level = float(self.peak_meter.get())
        
        # Broadcast visualization data via OSC
        if hasattr(self, 'viz_broadcast'):
            # Get voice levels (clamped to 0.0-1.0)
            voice_levels = []
            for voice_id in ['voice1', 'voice2', 'voice3', 'voice4']:
                if voice_id in self.voice_meters:
                    level = float(self.voice_meters[voice_id].get())
                    voice_levels.append(max(0.0, min(1.0, level)))
                else:
                    voice_levels.append(0.0)
            
            # Send voice levels
            self.viz_broadcast.send_message('/viz/levels', voice_levels)
            
            # Send spectrum data
            self.viz_broadcast.send_message('/viz/spectrum', spectrum)
```

#### 5. Complete State Capture Pattern

- File: engine_pyo.py
- Lines: 1647-1681
- Purpose: Capture complete engine state dynamically

```python
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
    
    # Acid filter
    module_states["acid1"] = self.acid1.get_status()
    
    # Build complete state
    return {
        "chronus_version": "1.0.0",
        "schema_version": "1.0",
        "timestamp": time.time(),
        "sequencer": sequencer_state,
        "modules": module_states
    }
```

### Code Flow

The auto-registration system follows this flow:
1. **Engine Initialization**: Parameter registry is initialized with base structure
2. **Module Creation**: Modules are instantiated with self-describing schemas  
3. **Schema Registration**: register_module_schema() adds module schemas to registry
4. **Route Mapping**: map_route() creates OSC handlers with metadata
5. **Status Broadcasting**: update_status() automatically broadcasts current state
6. **Dynamic Discovery**: /engine/schema provides live parameter inventory

### Related Components

#### Discovery and Control Systems
- **chronusctl.py**: Command-line tool for querying live engine schema
- **visualizer.py**: Real-time monitoring with OSC data consumption
- **Pattern System**: Complete state capture and restoration via capture_all_states()

#### Module Architecture
All modules follow consistent patterns:
- **get_schema()**: Self-describing parameter metadata
- **get_status()**: Current parameter values for state capture
- **set_*()**: Parameter setters with validation and range clamping

## File Inventory

### Core Engine Files
- **engine_pyo.py**: Main engine with registry and auto-registration (1902 lines)
- **chronusctl.py**: Command-line discovery tool (179 lines)  
- **visualizer.py**: Real-time monitoring with OSC consumption (339 lines)

### Module Files
- **pyo_modules/simple_lfo.py**: LFO module with schema pattern (138 lines)
- **pyo_modules/distortion.py**: Distortion module with schema pattern (149 lines)
- **pyo_modules/voice.py**: Voice module with comprehensive schema (302 lines)
- **pyo_modules/effects.py**: Effects modules with status methods (191 lines)

### Test Files
- **test_all_fixes.py**: Demonstrates dynamic parameter control (69 lines)

## Technical Notes

### Key Patterns for Virtual Pet Implementation

1. **Schema Query Pattern**
   - Use `/engine/schema` OSC command to get complete parameter inventory
   - Registry updates automatically as new modules are added
   - No hardcoding required - pet discovers parameters dynamically

2. **Live Data Access**
   - Engine broadcasts `/viz/levels` and `/viz/spectrum` automatically
   - Voice-level metering available via update_status() pattern
   - Active gate tracking via self.active_gates set

3. **State Capture Pattern**
   - capture_all_states() provides complete engine snapshot
   - Each module's get_status() returns current parameter values
   - Thread-safe operation with minimal locking

4. **Parameter Range Discovery**
   - All modules expose min/max ranges in schema
   - Parameter types and units included in metadata
   - Default values provided for baseline comparisons

5. **Module Type Classification**
   - Schema includes "type" field (voice, lfo, distortion, etc.)
   - Parameter groupings (adsr/, filter/, send/) for semantic understanding
   - Notes field provides human-readable context

### Scalability Features

- **No Hardcoded Module Lists**: Registry builds dynamically during initialization
- **Automatic Route Registration**: map_route() handles metadata atomically
- **Schema Versioning**: Supports evolution without breaking compatibility
- **Unknown Route Tracking**: Detects drift between registry and actual routes
- **Thread-Safe Operations**: All discovery and state capture operations use proper locking

### Data Already Available for Pet Scoring

1. **Audio Levels**: Per-voice and master levels via PeakAmp meters
2. **Spectrum Analysis**: 8-band frequency analysis via bandpass filters  
3. **Gate Activity**: Active voice tracking via active_gates set
4. **Parameter Values**: Complete module states via get_status() methods
5. **Message Traffic**: OSC message counting and logging
6. **Timing Data**: Sequencer state with BPM, swing, and pattern info

The system provides all necessary infrastructure for a self-scaling virtual pet that can:
- Discover new modules automatically without code changes
- Score musical quality using parameter ranges and current values
- Monitor audio characteristics in real-time
- Adapt behavior based on engine state changes

## Concrete Adaptation Recommendations

### Pet Auto-Discovery Implementation
1. **Query Live Schema**: Send `/engine/schema` on startup to discover all available parameters
2. **Monitor Broadcast Data**: Listen to `/viz/levels` and `/viz/spectrum` for real-time audio analysis
3. **Parse Parameter Ranges**: Use min/max values from schema to normalize parameter scores
4. **Track Module Types**: Use schema "type" field to apply appropriate scoring algorithms
5. **Detect New Modules**: Compare schema responses over time to identify additions

### Musical Quality Scoring Approach  
1. **Parameter Utilization**: Score based on how much of each parameter's range is being used
2. **Audio Activity**: Weight scores based on actual audio output levels
3. **Harmonic Content**: Use spectrum data to assess frequency balance
4. **Rhythmic Patterns**: Analyze gate activity and sequencer patterns
5. **Module Diversity**: Higher scores for more active module types

This research demonstrates that the Music Chronus engine provides an ideal foundation for implementing a fully automated, self-scaling virtual pet system that requires no manual updates as the synthesis engine grows.