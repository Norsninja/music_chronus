# Music Chronus Visualizer Diagnostic Research - 2025-01-08

## Executive Summary
Investigation of three critical visualizer issues revealed fundamental problems in audio level normalization, OSC message routing, and port configuration. Voice meters exceed 1.0 due to unclamped PeakAmp values, /viz messages bypass the display system due to specific dispatcher routing, and there are port conflicts preventing proper data flow.

## Scope
Analysis focused on data flow from engine_pyo.py through OSC broadcast to visualizer.py display, examining voice level collection, spectrum analysis, and message routing mechanisms.

## Key Findings

### Issue 1: Voice Meters Exceeding 1.0

#### Pattern Analysis
PeakAmp values are collected directly without normalization or clamping in the broadcast loop.

#### Implementation Details
- File: E:\TidalCyclesChronus\music_chronus\engine_pyo.py
- Lines: 904-912
- Purpose: Voice level collection for visualization broadcast
```python
# Get voice levels
voice_levels = []
for voice_id in ['voice1', 'voice2', 'voice3', 'voice4']:
    if voice_id in self.voice_meters:
        voice_levels.append(float(self.voice_meters[voice_id].get()))
    else:
        voice_levels.append(0.0)
```

#### Root Cause Analysis
The signal chain produces amplified output through multiple stages:
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\voice.py
- Lines: 77-93, 118
- Signal flow: Oscillator (amplitude 1.0) → ADSR envelope (mul=self.amp) → Biquad filter → output

The Voice construction shows potential amplification:
```python
self.osc_sine = Osc(
    table=self.sine_table,
    freq=self.ported_freq,
    mul=self.adsr  # ADSR envelope with amp multiplier
)
# ...
self.output = self.filter  # Direct filter output, no clamping
```

PeakAmp meters are created on line 859:
```python
self.voice_meters[voice_id] = PeakAmp(self.voices[voice_id].get_dry_signal())
```

**Problem**: No clamping or normalization applied to PeakAmp.get() values before broadcast.

### Issue 2: OSC Messages Not Displaying

#### Pattern Analysis  
The visualizer uses dual OSC message routing - specific handlers for /viz/ messages and a default handler for general OSC monitoring.

#### Implementation Details
- File: E:\TidalCyclesChronus\music_chronus\visualizer.py
- Lines: 104-108, 127-149
- Purpose: OSC message routing and display management

```python
# Dispatcher setup
self.dispatcher.set_default_handler(self.handle_osc_message)
self.dispatcher.map("/viz/spectrum", self.handle_spectrum_data)
self.dispatcher.map("/viz/levels", self.handle_level_data)
```

The handle_osc_message method (lines 127-149) adds messages to the display deque:
```python
def handle_osc_message(self, addr: str, *args):
    with self.data_lock:
        self.osc_messages.append({
            'time': timestamp,
            'addr': addr,
            'args': args[:3] if args else []
        })
```

#### Root Cause Analysis
**Problem**: /viz/spectrum and /viz/levels messages are routed to specific handlers that DO NOT add messages to the osc_messages deque for display. The specific handlers (handle_spectrum_data, handle_level_data) only update internal data structures but bypass the display system.

### Issue 3: Spectrum Analyzer Not Working

#### Pattern Analysis
Spectrum analysis uses pyo.Spectrum object with proper error handling and band grouping.

#### Implementation Details
- File: E:\TidalCyclesChronus\music_chronus\engine_pyo.py
- Lines: 851, 915-951
- Purpose: Real-time spectrum analysis and broadcast

Spectrum analyzer initialization:
```python
self.spectrum_analyzer = Spectrum(self.master, size=2048)
```

Spectrum data processing (lines 918-948):
```python
spectrum_data = self.spectrum_analyzer.get()
if spectrum_data and len(spectrum_data) > 0:
    # Group into 8 frequency bands
    # ... band processing logic ...
    self.viz_broadcast.send_message('/viz/spectrum', spectrum[:8])
```

#### Root Cause Analysis
**Problem**: Port configuration mismatch discovered during testing.
- Engine broadcasts to port 5006 (line 854): `udp_client.SimpleUDPClient('127.0.0.1', 5006)`
- Visualizer configured for port 5006 (line 41): `self.osc_monitor_port = 5006`
- But visualizer console output shows: "OSC listener started on port 5007"

This indicates either a port conflict causing automatic port reassignment or a configuration override.

### Code Flow

1. **Engine Data Collection**
   - Voice meters: PeakAmp objects collect levels from voice dry signals
   - Spectrum: Spectrum object analyzes master output
   - Broadcast: UDP client sends to port 5006

2. **OSC Message Routing**
   - Default handler: Catches all messages for display
   - Specific handlers: Process /viz/ messages for data updates
   - **Conflict**: /viz/ messages bypass display system

3. **Visualizer Reception**
   - Attempts to listen on port 5006
   - May be forced to use alternative port (5007 observed)
   - Specific /viz/ handlers update internal state but not display

### Related Components

#### Affected Files
- E:\TidalCyclesChronus\music_chronus\engine_pyo.py: Voice level collection, spectrum analysis
- E:\TidalCyclesChronus\music_chronus\pyo_modules\voice.py: Signal generation and routing  
- E:\TidalCyclesChronus\music_chronus\visualizer.py: OSC message handling and display

#### Dependencies
- pyo.PeakAmp: Audio level measurement (no built-in clamping)
- pyo.Spectrum: Frequency analysis
- pythonosc: OSC communication layer

## File Inventory

### Examined Files
- E:\TidalCyclesChronus\music_chronus\engine_pyo.py - Main engine with monitoring setup
- E:\TidalCyclesChronus\music_chronus\pyo_modules\voice.py - Voice signal generation
- E:\TidalCyclesChronus\music_chronus\visualizer.py - Visualization display and OSC handling

### Relevance Notes
- engine_pyo.py: Contains all three issue sources
- voice.py: Signal amplification source causing >1.0 levels
- visualizer.py: Message routing and port configuration issues

## Technical Notes

### Critical Fixes Needed

1. **Voice Level Clamping**
   - Add clamping in engine_pyo.py line 907: `voice_levels.append(min(1.0, float(self.voice_meters[voice_id].get())))`

2. **OSC Message Display Fix**
   - Modify handle_spectrum_data and handle_level_data to also call handle_osc_message for display
   - Or route /viz/ messages through default handler first

3. **Port Configuration Resolution**
   - Investigate why visualizer reports port 5007 when configured for 5006
   - Ensure engine broadcast and visualizer listener use same port
   - Add port conflict detection and reporting

### Performance Considerations
- PeakAmp.get() calls occur in broadcast loop (every engine cycle)
- Spectrum analysis with 2048-point FFT may be computationally intensive
- OSC message history deque should have size limits to prevent memory growth

### Pattern Violations
- No input validation on audio levels before broadcast
- Inconsistent error handling between spectrum and level data
- Port configuration not validated at startup