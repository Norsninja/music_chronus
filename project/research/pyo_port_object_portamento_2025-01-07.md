# Pyo Port Object for Synthesizer Portamento - Technical Research

**Research Date**: 2025-01-07  
**Scope**: Port object vs SigTo for portamento/glide implementation in pyo synthesizers

## Executive Summary

The pyo Port object provides exponential smoothing with independent rise/fall times, making it superior to SigTo for musical portamento. Critical findings: Port uses seconds (not milliseconds) for timing, should be applied after signal generation but before audio synthesis, and offers better performance for audio parameter smoothing than linear alternatives. Key gotcha: risetime/falltime values below 0.001s may cause artifacts.

## Concrete Performance Data

### Timing Specifications
- **Port parameters**: risetime/falltime in **seconds** (e.g., 0.001 = 1ms, 0.25 = 250ms)
- **Default values**: risetime=0.01s, falltime=0.1s
- **Typical musical values**: risetime=0.001s (1ms), falltime=0.25s (250ms) for sharp attack/long release
- **Sub-millisecond precision**: Possible (e.g., 0.0001 = 100μs) but may introduce artifacts

### Performance Characteristics
- **Port**: Exponential smoothing via lowpass filtering - "good and efficient way" per documentation
- **SigTo**: Linear ramps - simpler computation but less natural for audio
- **CPU Impact**: No specific benchmarks found, but Port described as efficient for its exponential approach

### Real-World Measurements
From GitHub examples:
```python
# Typical synthesizer portamento
ch_port = Port(choice, risetime=.001, falltime=.001)

# MIDI velocity smoothing
Port(notes["velocity"], risetime=0.005, falltime=0.5, mul=0.1)

# Amplitude envelope smoothing
Port(rec['/pos'], risetime=.05, falltime=.05, mul=table.getDur()*44100.)
```

## Critical Gotchas

### 1. Server Boot Issues (Most Common)
- **Problem**: "PyoServerStateException: The Server must be booted before creating any audio object"
- **Cause**: Other applications using audio (YouTube, VLC, etc.) or improper server initialization
- **Solution**: Close all audio applications, use `Server(..., winhost="wasapi")` on Windows

### 2. Windows-Specific Audio Problems
- **Issue**: Default DirectSound host fails on Vista+
- **Required**: WASAPI host: `Server(..., winhost="wasapi")`
- **Constraint**: Sample rates must match (default 44100 Hz)

### 3. Signal Chain Order Critical
- **Correct**: Signal Source → Port → Audio Objects
- **Incorrect**: Applying Port after audio generation
- **Example**: 
```python
# RIGHT
fr = Sig(value=400)
p = Port(fr, risetime=0.001, falltime=0.001)
a = SineLoop(freq=p)

# WRONG  
a = SineLoop(freq=400)
p = Port(a, ...)  # Port on audio signal, not control
```

### 4. Timing Parameter Confusion
- **Critical**: Parameters are in SECONDS, not milliseconds
- **Common Error**: Using millisecond values directly (e.g., `risetime=1` = 1 second, not 1ms)
- **Correct**: Divide by 1000 for millisecond timing (e.g., `risetime=0.001` for 1ms)

### 5. None-Type Errors with Random Values
- **Symptom**: Code works line-by-line in interpreter but fails in scripts
- **Cause**: Timing issues with random value generation and Port initialization
- **Solution**: Ensure proper initialization order and value validation

## Battle-Tested Patterns

### 1. Musical Frequency Portamento
```python
# Proven pattern from tiagovaz/pyo-collection
from pyo import *
s = Server().boot()

# Generate pitch choices
pitches = [midiToHz(m) for m in [36,43,48,55,60,62,64,65,67,69,71,72]]
choice = Choice(choice=pitches, freq=1)

# Apply exponential portamento
ch_port = Port(choice, risetime=.001, falltime=.001)

# Use in synthesis
instrument = SuperSaw(freq=ch_port, detune=0.07, mul=.1)
```

### 2. MIDI Velocity Smoothing
```python
# From official documentation
velocity_smooth = Port(notes["velocity"], risetime=0.005, falltime=0.5, mul=0.1)
```

### 3. Parameter Automation via set() Method
```python
# Alternative to direct Port usage
osc = Sine(freq=440)
osc.set(attr="freq", value=600, port=5)  # 5-second portamento
```

### 4. Combined with SigTo for Complex Envelopes
```python
# Linear ramp + exponential portamento
amp = SigTo(value=0.3, time=2.0, init=0.0)  # Linear amplitude ramp
freq_pick = Choice([200, 250, 300, 350, 400], freq=4)
freq_smooth = Port(freq_pick, risetime=0.001, falltime=0.25)  # Exponential freq portamento
```

## Trade-off Analysis

### Port vs SigTo Comparison

| Aspect | Port | SigTo |
|--------|------|-------|
| **Smoothing Type** | Exponential (musical) | Linear (mathematical) |
| **Rise/Fall Control** | Independent (risetime/falltime) | Single time parameter |
| **CPU Usage** | Lowpass filter (moderate) | Linear interpolation (minimal) |
| **Audio Quality** | Natural, musical transitions | Mechanical, uniform ramps |
| **Use Cases** | Frequency/pitch portamento, MIDI smoothing | Amplitude envelopes, linear automation |
| **Artifacts** | Smooth, no clicks | May introduce artifacts on abrupt changes |

### When to Use Each

**Use Port for**:
- Frequency/pitch portamento (exponential feels musical)
- MIDI parameter smoothing (velocity, mod wheel)
- Audio parameter automation requiring different attack/release
- Avoiding clicks on abrupt value changes

**Use SigTo for**:
- Amplitude envelopes (linear often preferred)
- Simple automation with uniform timing
- CPU-constrained applications
- Mathematical/measurement applications

### Performance Implications
- **Port**: More CPU due to lowpass filtering, but "efficient" according to docs
- **SigTo**: Minimal CPU overhead for linear interpolation
- **Recommendation**: Port's musical benefits typically outweigh CPU cost for synthesis

## Red Flags

### 1. Signal Chain Violations
- **Warning**: Applying Port to audio signals instead of control signals
- **Impact**: Unnecessary processing, potential audio quality degradation
- **Detection**: If Port is applied after `.out()` calls or to audio-rate signals

### 2. Extreme Timing Values
- **Danger**: risetime/falltime < 0.0001s may cause instability
- **Danger**: risetime/falltime > 10s creates sluggish response
- **Safe Range**: 0.001s to 2.0s for most musical applications

### 3. Windows Audio Configuration
- **Red Flag**: Using default audio host on Windows Vista+
- **Consequence**: Complete audio system failure
- **Required**: Explicit WASAPI configuration

### 4. Server State Management
- **Critical**: Creating Port objects before server boot
- **Symptom**: PyoServerStateException on object creation
- **Prevention**: Always call `s.boot()` before creating any pyo objects

### 5. Missing Initialization Values
- **Problem**: Using Port without proper input signal initialization
- **Result**: None-type errors or unpredictable behavior
- **Solution**: Ensure input signals have valid initial values

## Key Technical Specifications

### Port Object Constructor
```python
Port(input, risetime=0.01, falltime=0.1, init=0.0, mul=1, add=0)
```

### Parameter Ranges
- **risetime/falltime**: 0.0001s to practical maximum (~10s)
- **Musical range**: 0.001s (1ms) to 2.0s (2000ms)
- **Resolution**: Supports sub-millisecond precision

### Alternative Methods
- **set() method**: `object.set(attr="param", value=new_val, port=time_sec)`
- **VarPort**: Similar to Port but for converting numeric values directly

## Concrete Code Examples

### Complete Synthesizer with Portamento
```python
from pyo import *
import random

# Initialize server (CRITICAL: Windows needs WASAPI)
s = Server(winhost="wasapi").boot()
s.start()

# Create frequency source
fr = Sig(value=440)

# Apply exponential portamento 
p = Port(fr, risetime=0.001, falltime=0.001)

# Synthesizer with slight detune for richness
a = SineLoop(freq=p, feedback=0.08, mul=.3).out()
b = SineLoop(freq=p*1.005, feedback=0.08, mul=.3).out(1)

# Function to change frequency with portamento
def pick_new_freq():
    fr.value = random.randrange(300, 601, 50)

# Trigger frequency changes
pat = Pattern(function=pick_new_freq, time=0.5).play()

s.gui(locals())
```

### MIDI-Style Portamento
```python
# MIDI note input with portamento
midi_notes = Notein()
frequency = Port(
    MToF(midi_notes['pitch']), 
    risetime=0.002,  # Sharp attack
    falltime=0.1     # Smooth release
)
velocity = Port(
    midi_notes['velocity'], 
    risetime=0.005, 
    falltime=0.5, 
    mul=0.1
)

synth = FM(
    carrier=frequency,
    ratio=1.5,
    index=3,
    mul=velocity
).out()
```

This research provides the technical foundation for implementing professional-quality portamento in pyo synthesizers, avoiding common pitfalls while leveraging the Port object's exponential smoothing capabilities for musical expression.