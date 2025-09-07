# Pyo Oscillator Waveform Switching Research
*Technical Research Report - January 7, 2025*

## Executive Summary

Pyo provides robust band-limited waveform generation through SawTable and SquareTable with configurable harmonic content (order parameter). Click-free waveform switching requires crossfading techniques using Selector or Interp objects. Critical performance issues exist on resource-constrained platforms (Raspberry Pi) with large table sizes causing event loop lockups. Order=12 provides good balance between harmonic richness and CPU efficiency for most use cases.

## Concrete Performance Data

### Table Size Performance
- **Default size**: 8192 samples for SawTable/SquareTable
- **Raspberry Pi issue**: Tables >4096 samples cause complete event loop lockup
- **Recommended sizes**: 
  - Desktop systems: 8192 (default)
  - Raspberry Pi: 4096 or lower
  - Multiple oscillators: 1024-2048 to prevent CPU saturation

### Order Parameter Benchmarks
- **Default order**: 10 harmonics for both SawTable and SquareTable
- **Recommended range**: 8-15 for most applications
- **Order=12**: Good balance between harmonic content and CPU usage
- **High values (30+)**: Can cause performance issues on limited hardware
- **Performance scaling**: Linear increase in CPU usage with higher order values

### Band-Limiting Effectiveness
- SawTable: Uses all harmonics up to specified order (1/i amplitude scaling)
- SquareTable: Uses only odd harmonics up to specified order (1/i amplitude scaling)  
- Both use additive synthesis via HarmTable internally
- Prevents aliasing by limiting harmonics below Nyquist frequency

## Critical Gotchas

### Platform-Specific Issues
1. **Raspberry Pi Event Loop Lockup**: Tables >4096 samples cause complete system freeze
   - Symptoms: No audio output, MIDI unresponsive, event loop locked
   - Solution: Reduce table size to 4096 or lower
   - Affected: Raspberry Pi 2 Model B confirmed, likely other ARM platforms

2. **Multi-Channel CPU Saturation**: 50+ oscillators can consume 47% CPU (i5 3320M @ 2.6GHz)
   - Problem: Each oscillator creates separate processing chains
   - Solution: Use mix() method before applying effects

3. **Denormalization Performance Hit**: Recursive delay objects suffer from denormal number computation
   - Affected: Filters, delays, reverbs, harmonizers
   - Solution: Wrap in Denorm object to add minimal noise above smallest normal number

### Table Switching Pitfalls
1. **Click Generation**: Direct table switching always causes audible clicks
   - Cause: Switching occurs at control block boundaries (64 samples default)
   - Cannot guarantee switching at zero-crossing points
   - Solution: Always use crossfading, never direct switching

2. **Phase Correlation Issues**: Out-of-phase waveforms cause amplitude drops during crossfade
   - Problem: Standard crossfade assumes in-phase signals
   - Solution: Use equal-power crossfade (mode=1 in Selector)

## Battle-Tested Patterns

### Basic Waveform Creation
```python
# Band-limited waveforms with recommended parameters
sine_table = HarmTable([1])  # Pure sine
saw_table = SawTable(order=12, size=8192)  # Good balance
square_table = SquareTable(order=10, size=8192)  # Default values work well

# Always normalize for consistent amplitude
saw_table.normalize()
square_table.normalize()
```

### Click-Free Table Switching with Selector
```python
# Create multiple oscillators
osc_sine = Osc(table=sine_table, freq=440, mul=0.3)
osc_saw = Osc(table=saw_table, freq=440, mul=0.3)  
osc_square = Osc(table=square_table, freq=440, mul=0.3)

# Smooth switching with Selector
selector = Selector(inputs=[osc_sine, osc_saw, osc_square], voice=control_sig)
selector.setMode(1)  # Equal-power crossfade for phase-uncorrelated signals
```

### Click-Free Interpolation with Interp
```python
# Two-way morphing between waveforms
interp = Interp(input=osc1, input2=osc2, interp=morph_control)
# morph_control: 0.0 = only osc1, 1.0 = only osc2, 0.5 = equal mix
```

### Performance-Optimized Voice Implementation
```python
class OptimizedVoice:
    def __init__(self, voice_id):
        # Use smaller tables on resource-constrained platforms
        table_size = 4096 if platform.machine().startswith('arm') else 8192
        
        # Conservative order values for stability
        self.sine_table = HarmTable([1], size=table_size)
        self.saw_table = SawTable(order=10, size=table_size).normalize()
        self.square_table = SquareTable(order=8, size=table_size).normalize()
        
        # Create oscillators
        osc_sine = Osc(table=self.sine_table, freq=self.freq, mul=self.env)
        osc_saw = Osc(table=self.saw_table, freq=self.freq, mul=self.env)
        osc_square = Osc(table=self.square_table, freq=self.freq, mul=self.env)
        
        # Selector with crossfading
        self.oscillator = Selector([osc_sine, osc_saw, osc_square], voice=self.waveform_control)
        self.oscillator.setMode(1)  # Equal-power crossfade
```

## Trade-off Analysis

### Order Parameter Trade-offs
| Order | Pros | Cons | Use Case |
|-------|------|------|-----------|
| 5-8 | Low CPU, stable | Limited harmonics, soft sound | Background pads, ambient |
| 10-12 | Balanced, good quality | Moderate CPU | General purpose, leads |
| 15-20 | Rich harmonics, bright | Higher CPU | Aggressive leads, bass |
| 25+ | Very rich, complex | High CPU, potential instability | Special effects only |

### Table Size Trade-offs
| Size | Pros | Cons | Best For |
|------|------|------|-----------|
| 1024 | Low memory, ARM-safe | Limited resolution | Multiple oscillators, embedded |
| 4096 | Good balance, Pi-safe | Moderate resolution | Raspberry Pi, mobile |
| 8192 | High resolution, default | Higher memory | Desktop, single voices |
| 16384+ | Maximum resolution | High memory, potential issues | Offline rendering only |

### Switching Method Comparison
| Method | Pros | Cons | CPU Impact |
|--------|------|------|------------|
| Direct switching | Zero CPU overhead | Always clicks | None |
| Selector | Smooth, flexible | Moderate CPU | Low-Medium |
| Interp | Perfect for 2-way morph | Limited to 2 inputs | Low |
| BLOsc-style | Professional quality | Complex implementation | Medium-High |

## Red Flags

### Avoid These Patterns
1. **Never use direct table switching**: `osc.table = new_table` always clicks
2. **Don't exceed safe table sizes**: >8192 on desktop, >4096 on Pi
3. **Avoid high order values without testing**: Order >20 often causes instability
4. **Don't ignore CPU monitoring**: Multiple high-order oscillators saturate CPU quickly
5. **Never use default crossfade mode with uncorrelated signals**: Causes amplitude drops

### Warning Signs
- **Audio dropouts**: Usually indicates CPU saturation from too many oscillators
- **MIDI unresponsiveness**: Classic sign of event loop lockup from oversized tables
- **Amplitude drops during morphing**: Indicates need for equal-power crossfade mode
- **Aliasing artifacts**: Order parameter too low for frequency range being used

### Architecture Limitations
- **Control rate limitations**: Parameter changes limited to control block boundaries (64 samples)
- **Memory pressure**: Each table occupies size * sizeof(float) bytes
- **Single-threaded processing**: No automatic parallelization of oscillator banks
- **Platform dependencies**: ARM platforms have significantly lower limits than x86

## Key Implementation Principles

1. **Always crossfade, never switch**: Direct table switching is fundamentally broken
2. **Test on target platform**: Raspberry Pi limits are much lower than desktop
3. **Monitor CPU usage**: Oscillator banks scale linearly with voice count
4. **Use conservative defaults**: Order=10-12, size=4096-8192 work reliably
5. **Normalize all tables**: Prevents unexpected amplitude variations
6. **Profile before optimizing**: Measure actual CPU usage before adding complexity
7. **Plan for scaling**: Design voice allocation system from the start

This research provides the foundation for implementing robust, click-free waveform switching in the Music Chronus voice.py module while avoiding the critical pitfalls that cause system instability and poor audio quality.