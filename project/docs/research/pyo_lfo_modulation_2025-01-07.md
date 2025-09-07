# Pyo LFO Implementation Research
## Technical Research Scout Report - January 7, 2025

**Executive Summary**: Pyo provides two primary LFO options: the dedicated `LFO` class with 8 waveforms and band-limiting, and the `Sine` class optimized for low frequencies. Both support efficient parameter scaling via `mul`/`add` or the `range()` method. Performance is excellent when properly routed, but multiple LFOs require careful mixing to avoid CPU overhead. Anti-aliasing is built-in, and zipper noise prevention uses crossfading techniques.

---

## 1. LFO vs Sine at Low Frequencies

### LFO Class (Dedicated)
- **Frequency Range**: Internally clamped between 0.00001 and sr/4 Hz
- **Waveforms**: 8 available types including saw up/down, square, triangle, pulse, sample & hold
- **Band-Limited**: True band-limited implementation prevents aliasing
- **Optimal Use**: Below 0.2 Hz for true LFO behavior; above generates broad spectrum noise

### Sine Class (General Purpose)
- **Frequency Range**: No specific low-frequency optimization
- **Performance**: FastSine variant with quality=0 provides very fast algorithm suitable for LFOs
- **Accuracy**: Less accurate than standard sine but much faster for modulation use
- **Optimal Use**: When pure sine wave modulation is needed

### Recommendation
**Use LFO class** for wobble bass and complex modulation shapes. **Use Sine class** for tremolo and vibrato where pure sinusoidal modulation is preferred.

---

## 2. Scaling LFO Output to Target Parameter Ranges

### Core Scaling Parameters
```python
# Basic scaling: output = (input * mul) + add
lfo = Sine(freq=0.1, mul=500, add=1000)  # ±500 around 1000Hz

# Range method (preferred): automatically computes mul/add
lfo = Sine(freq=0.4).range(2, 8)  # Output between 2 and 8
```

### Efficient Scaling Techniques
1. **Unipolar Modulation**: `lfo.range(min, max)` for parameters requiring positive values
2. **Bipolar Modulation**: Use `mul` for depth, `add` for center point
3. **Parameter Types**:
   - Filter cutoff: `Sine(0.1).range(200, 2000)` (Hz)
   - Filter Q: `Sine(0.4).range(0.5, 8)` (ratio)
   - Amplitude: `Sine(2).range(0, 1)` (0-1 scale)

---

## 3. Routing LFOs to Multiple Destinations

### Fixed Routing Implementation
```python
# LFO1 → Voice2 Filter Cutoff
lfo1 = Sine(freq=0.1).range(200, 2000)
filter_voice2 = MoogLP(audio_voice2, freq=lfo1, res=0.7)

# LFO2 → Voice3 Amplitude  
lfo2 = Sine(freq=0.3).range(0, 1)
amp_voice3 = audio_voice3 * lfo2
```

### Performance Optimization
- **Critical**: Use `mix()` before applying effects to multiple channels
- **Example**: 50 oscillators + Phaser = 47% CPU vs 7% CPU when mixed first
- **Rule**: Mix signals down to fewer channels before expensive processing

### Routing Best Practices
1. Stop unused LFOs with `stop()` method (not volume=0)
2. Use native C implementations over Python constructs
3. Avoid trigonometric functions at audio rate
4. Route LFOs at control rate when possible

---

## 4. Preventing Zipper Noise in Filter Modulation

### Built-in Crossfading
- Pyo filters include crossfade time parameters (default ~0.05s)
- Smooth transitions between parameter changes automatically handled

### Manual Smoothing Techniques
```python
# Using Interp for smooth parameter transitions
smooth_cutoff = Interp(old_freq, new_freq, interp_time=0.05)
filter = MoogLP(audio, freq=smooth_cutoff)

# Using SmoothDelay for artifact-free modulated delays
delay = SmoothDelay(audio, delay=lfo_modulated_time, feedback=0.3)
```

### Anti-Zipper Guidelines
1. **Interpolation Time**: 70ms is good compromise between latency and artifacts
2. **Smooth Sources**: Keep LFO signals low-frequency and narrow-band
3. **Parameter Smoothing**: Apply smoothing to incoming control signals, not filter coefficients

---

## 5. CPU Impact of Multiple LFOs

### Concrete Performance Data
- **Measurement Context**: Multiple oscillator scenario with effects processing
- **Critical Finding**: Multi-channel expansion creates duplicate objects per channel
- **Performance Cliff**: 50 LFOs + effects can jump from 7% to 47% CPU without proper routing

### Optimization Strategies
1. **Mix Before Processing**: `mixed_signal = signals.mix(2)` before effects
2. **Stop Unused Objects**: `lfo.stop()` removes from computation loop
3. **Efficient Object Use**: Native PyoObjects (C implementations) over Python constructs
4. **Threading**: Set `sys.setcheckinterval()` to larger values for better performance

### CPU-Efficient LFO Patterns
```python
# Efficient: One LFO driving multiple parameters via scaling
master_lfo = Sine(freq=0.1)
cutoff_mod = master_lfo.range(200, 2000)
amp_mod = master_lfo.range(0.2, 0.8)
```

---

## 6. Waveform Options and Applications

### LFO Waveform Types (8 available)
1. **Saw Up**: Rising modulation, good for filter sweeps
2. **Saw Down**: Falling modulation, reverse filter sweeps  
3. **Square**: On/off modulation, tremolo gates
4. **Triangle**: Smooth bi-directional modulation
5. **Pulse**: Variable duty cycle square waves
6. **Bipolar Pulse**: Positive/negative pulse trains
7. **Sample & Hold**: Random stepped values
8. **Modulated Sine**: Sine with harmonic content control

### Electronic Music Applications
```python
# Wobble Bass (Dubstep/DnB)
wobble_lfo = LFO(freq=0.25, type=2, sharp=0.8).range(100, 800)  # Square wave
bass_filter = MoogLP(bass_osc, freq=wobble_lfo, res=0.9)

# Tremolo Effect  
tremolo_lfo = Sine(freq=4).range(0.1, 1.0)
tremolo_out = audio * tremolo_lfo

# Vibrato Effect
vibrato_lfo = Sine(freq=5, mul=10)  # ±10 Hz modulation
vibrato_osc = Sine(freq=440 + vibrato_lfo)
```

---

## 7. Real-World Implementation Examples

### Wobble Bass (from pyo-tools/fatbass.py)
```python
# PWM Oscillator with LFO modulation
mod_freq = carrier_freq * 0.25  # 1-2 octaves below carrier
modulator = Phasor(mod_freq)
square_mod = (modulator < 0.5) * 2 - 1
filter = MoogLP(pwm_osc * square_mod, cutoff=lfo_cutoff, res=0.8)
```

### Multi-LFO Routing Pattern
```python
# Phase-offset LFOs for complex modulation
lfo1 = Sine(freq=0.1, phase=0).range(200, 2000)      # Filter
lfo2 = Sine(freq=0.1, phase=0.25).range(0.2, 0.8)   # Amplitude  
lfo3 = Sine(freq=0.1, phase=0.5).range(0.1, 0.9)    # Resonance
```

---

## 8. Common Rate/Depth Ranges for Electronic Music

### Typical LFO Rates
- **Sub-Bass Wobble**: 0.1-0.5 Hz (dubstep/trap)
- **Filter Sweeps**: 0.25-2 Hz (house/techno)
- **Tremolo**: 2-8 Hz (traditional tremolo effect)
- **Vibrato**: 4-7 Hz (musical vibrato)
- **Tempo-Sync**: BPM/16 to BPM/2 (synchronized effects)

### Modulation Depth Guidelines
- **Filter Cutoff**: 200-2000 Hz range for most electronic music
- **Amplitude**: 0.1-1.0 range (never completely off unless intended)
- **Pitch**: ±10-50 cents for subtle vibrato, ±100-200 for dramatic effects
- **Resonance**: 0.5-0.9 (avoid >1.0 unless self-oscillation desired)

---

## 9. Anti-Aliasing and Band-Limiting

### Built-in Protection
- **LFO Class**: True band-limited implementation
- **Frequency Clamping**: Automatic limitation to sr/4 prevents aliasing
- **Quality Parameter**: FastSine quality=0 trades accuracy for speed

### Band-Limiting Benefits
- No spurious frequencies above Nyquist
- Clean modulation without digital artifacts
- Suitable for professional audio production

---

## 10. Trade-off Analysis

| Approach | Pros | Cons | Best Use |
|----------|------|------|----------|
| LFO Class | 8 waveforms, band-limited, optimized | Limited to low frequencies | Complex modulation shapes |
| Sine Class | Fast, simple, pure waveform | No built-in band-limiting | Smooth tremolo/vibrato |
| Multiple LFOs | Rich modulation possibilities | CPU intensive without optimization | Complex rhythmic patterns |
| Single LFO + Scaling | CPU efficient, coherent modulation | Less variety in modulation | Simple, efficient effects |

---

## 11. Critical Gotchas

### Performance Issues
- **Multi-channel Expansion**: Creates duplicate objects per channel - always mix first
- **Unused Objects**: Setting volume=0 doesn't save CPU - use `stop()` method
- **Parameter Updates**: Avoid updating filter coefficients at audio rate

### Modulation Artifacts
- **Zipper Noise**: Use crossfading or Interp objects for smooth parameter changes
- **Aliasing**: Stick to LFO class for guaranteed band-limited operation
- **Phase Issues**: Consider phase relationships when using multiple LFOs

### Routing Mistakes
- **Direct Mapping**: Never call dispatcher.map directly - use map_route()
- **Channel Mismatch**: Ensure LFO output channels match target parameter inputs
- **Range Errors**: Verify parameter ranges match target object expectations

---

## 12. Battle-Tested Implementation Patterns

### Fixed Routing System (Recommended Starting Point)
```python
class LFORouter:
    def __init__(self):
        # LFO1 → Voice2 Filter
        self.lfo1 = LFO(freq=0.1, type=1, sharp=0.5).range(200, 2000)
        
        # LFO2 → Voice3 Amplitude
        self.lfo2 = Sine(freq=0.3).range(0.2, 1.0)
        
        # LFO3 → Master Filter Resonance  
        self.lfo3 = Sine(freq=0.05).range(0.5, 0.8)
    
    def apply_modulation(self, voices):
        voices[1].set_filter_cutoff(self.lfo1)  
        voices[2].set_amplitude(self.lfo2)
        self.master_filter.set_resonance(self.lfo3)
```

### Expandable Architecture
```python
# Modulation matrix for future expansion
class ModMatrix:
    def __init__(self):
        self.lfos = [LFO(freq=f).range(0, 1) for f in [0.1, 0.2, 0.3, 0.4]]
        self.targets = {}  # destination: lfo_index mapping
    
    def route(self, target, lfo_index, scale_range):
        scaled_lfo = self.lfos[lfo_index].range(*scale_range)  
        self.targets[target] = scaled_lfo
```

---

## 13. Red Flags and Warning Signs

### Avoid These Patterns
- Creating LFOs inside audio processing loops
- Using trigonometric functions at audio rate for modulation
- Applying effects to multi-channel LFO signals without mixing
- Setting parameter ranges outside target object specifications
- Ignoring crossfade times in filter modulation

### Performance Warning Signs  
- CPU usage suddenly jumping when adding LFOs
- Audio dropouts during parameter changes
- Zipper noise in filter modulation
- LFO frequencies above 20 Hz without specific purpose

---

**Key Principle**: Pyo's LFO implementation is production-ready with proper routing and scaling. The dedicated LFO class provides professional band-limited modulation, while efficient routing patterns prevent CPU bottlenecks. Start with fixed routing (LFO1→Voice2 filter, LFO2→Voice3 amp) and expand systematically.