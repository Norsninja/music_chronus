# Pyo Port Object Research for Frequency Slide Implementation
**Research Date:** 2025-09-07  
**Researcher:** Chronus Nexus  
**Target:** Implementation of pitch slide/glide in synthesizer voices using pyo's Port object

## Executive Summary

Pyo's Port object provides exponential portamento through lowpass filtering with separate rise/fall times - ideal for 303-style acid bass slides. Key finding: Port creates exponential curves while SigTo creates linear ramps. TB-303 uses constant 60ms slide time with 6dB/octave filtering. Current voice.py architecture supports easy Port integration by replacing SigTo for frequency control.

## Concrete Performance Data

### CPU Usage Benchmarks
- **Pyo Processing**: Most computations occur at C level after Python script execution, providing significant performance benefits
- **Multi-oscillator Overhead**: 50 oscillators with phasing effect = 47% CPU on i5 3320M @ 2.6GHz (Thinkpad T430)
- **Buffer Size Impact**: Default 256 samples = ~5ms latency; increase to 512 to prevent clicks
- **Native Objects**: Always more efficient than equivalent constructs built from scratch

### Port vs SigTo Performance
- Both implemented in C, minimal CPU difference
- Port: Exponential curves via lowpass filtering
- SigTo: Linear ramps with single time parameter
- VarPort: Similar to SigTo but with callback support

## Critical Gotchas

### Click Prevention
1. **Buffer Size**: Increase from default 256 to 512 samples to prevent clicks when changing parameters
2. **Denormal Prevention**: Add low-level noise (1e-24) to prevent CPU spikes from denormal numbers
3. **Parameter Smoothing**: Always use portamento when switching between immediate/slide modes
4. **GUI Overhead**: Disable Server GUI if not needed to reduce CPU usage

### Port Object Limitations
1. **Numeric vs Signal Input**: Port accepts both numeric values and PyoObject signals - ensure type consistency
2. **Initialization**: No explicit init parameter - Port starts from current input value
3. **Multi-channel**: Using mul parameter as list creates multiple streams - mix down if fewer output channels needed

## Battle-Tested Patterns

### TB-303 Slide Implementation
```python
# TB-303 accurate slide timing (60ms constant time)
freq_target = Choice([200, 250, 300, 350, 400], freq=4)
freq_slide = Port(freq_target, risetime=0.001, falltime=0.06)  # Sharp attack, 60ms fall
osc = Sine(freq=freq_slide)
```

### Switchable Slide Mode
```python
class Voice:
    def __init__(self):
        self.slide_enabled = False
        self.slide_time = 0.06  # TB-303 standard
        
        # Dual frequency paths
        self.freq_target = Sig(440.0)
        self.freq_immediate = SigTo(self.freq_target, time=0.001)  # Immediate (1ms)
        self.freq_slide = Port(self.freq_target, risetime=0.001, falltime=self.slide_time)
        
        # Selector between immediate and slide
        self.freq_selector = Selector([self.freq_immediate, self.freq_slide])
        
    def set_slide_mode(self, enabled):
        self.slide_enabled = enabled
        self.freq_selector.voice = 1 if enabled else 0
```

### Per-Note Slide Control
```python
# Dynamic slide time adjustment
def set_slide_time(self, time):
    """Set slide time with click-free transition"""
    if hasattr(self, 'freq_slide'):
        # Smooth transition to new slide time
        self.freq_slide.setFalltime(max(0.001, min(1.0, time)))
```

## Trade-off Analysis

### Port vs SigTo Comparison
| Feature | Port | SigTo | VarPort |
|---------|------|-------|---------|
| Curve Type | Exponential | Linear | Linear |
| Rise/Fall Control | Separate | Combined | Combined |
| TB-303 Accuracy | Excellent | Poor | Poor |
| CPU Usage | Low | Low | Low |
| Callback Support | No | No | Yes |

### Integration with Existing Voice.py
**Current Implementation:**
```python
self.freq_sig = Sig(440.0)
self.freq = SigTo(self.freq_sig, time=self.smooth_time)  # 20ms linear
```

**Slide-Enabled Implementation:**
```python
self.freq_sig = Sig(440.0)
self.freq_immediate = SigTo(self.freq_sig, time=0.001)
self.freq_slide = Port(self.freq_sig, risetime=0.001, falltime=0.06)
self.freq = Selector([self.freq_immediate, self.freq_slide])
```

## Red Flags

### Common Misconceptions
1. **Port = Portamento**: Port is exponential lowpass filtering, not traditional portamento
2. **Linear Slides**: Using SigTo for 303-style slides sounds wrong - exponential curves are essential
3. **Single Time Parameter**: Port requires separate rise/fall times - can't use one value for both

### Implementation Risks
1. **Click Sources**: 
   - Switching between immediate/slide modes without smoothing
   - Setting Port parameters while audio is running
   - Using numeric values instead of signals for dynamic control

2. **Performance Pitfalls**:
   - Creating multiple Port objects instead of using multi-channel expansion
   - Not mixing down multi-channel signals before effects
   - Using trigonometric functions at audio rate

### Missing Features
- No built-in legato detection (must implement externally)
- No automatic per-note slide time scaling
- No sync to musical time divisions

## Key Implementation Points for voice.py

### Current Integration Points
- Line 31-32: `self.freq_sig` and `self.freq` - Replace SigTo with Port/Selector pattern
- Line 157-159: `set_slide_time()` stub method - Implement with Port parameter control
- Line 28: `self.smooth_time = 0.02` - Keep for non-slide parameters, separate slide timing

### Recommended Implementation
1. **Dual Path Architecture**: Keep both immediate (SigTo) and slide (Port) frequency paths
2. **Selector Switch**: Use Selector object to choose between immediate/slide modes
3. **Click Prevention**: Always transition selector voice parameter with short fade
4. **Parameter Validation**: Slide time range 0.001s to 1.0s (TB-303 uses 0.06s)

### Musical Style Slide Times
- **Acid/TB-303**: 60ms (0.06s) constant time
- **Trance Leads**: 100-200ms
- **Ambient Pads**: 500ms-1s
- **Rapid Acid**: 20-40ms
- **Smooth Jazz**: 150-300ms

## Conclusion

Port object provides authentic 303-style exponential slides with minimal CPU overhead. Integration requires dual-path frequency architecture with Selector switching to prevent clicks. Implementation complexity is low, but attention to buffer sizing and parameter smoothing is critical for professional results.