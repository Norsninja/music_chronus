# Pyo Distortion Capabilities Research: Master Insert Implementation

**Executive Summary**: Pyo's Disto object provides a 4x faster waveshaper algorithm than traditional tanh/atan2 methods, making it ideal for master insert use. The existing custom distortion module lacks the efficient pyo implementation and proper signal chain integration. Critical findings include specific parameter ranges for techno/acid contexts, optimal placement between voice mixer and reverb/delay sends, and concrete techniques for transparent mix control using SigTo objects.

## Concrete Performance Data

### Pyo Disto Object Specifications
- **Algorithm**: Efficient waveshaper formula `y[n] = (1 + k) * x[n] / (1 + k * abs(x[n]))` where `k = (2 * drive) / (1 - drive)`
- **Performance**: 4x faster than tanh or atan2 functions (measured by pyo developers)
- **Parameters**: 
  - `drive`: 0.0-1.0 (distortion amount)
  - `slope`: 0.0-1.0 (post-distortion lowpass filter)
- **CPU Impact**: Listed as non-CPU-intensive object in pyo documentation

### Pyo Degrade Object for Bitcrushing
- **bitdepth**: 1-32 bits (16 default)
- **srscale**: 0.0009765625-1.0 (sampling rate multiplier)
- **Real-time modulation**: Both parameters accept PyoObjects for dynamic control
- **Performance**: Efficient sample-and-hold implementation

### Current Implementation Analysis
The existing `distortion.py` module uses:
- Custom numpy-based processing (slower than C-based pyo)
- Manual bitcrush loop (inefficient compared to pyo's Degrade)
- Fixed tone control range (200Hz-10.2kHz)
- Basic parameter smoothing (2-5ms)

## Critical Gotchas

### Signal Chain Placement Issues
1. **Wrong Position**: Distortion after effects destroys "fine nuances in sound spectrum" (techno production best practice)
2. **Master Bus Overload**: No soft limiter/clipper to prevent master bus clipping from drive boost
3. **Frequency Balance**: Current normalization `0.7 / max(drive, 1.0)` doesn't account for frequency-dependent gain changes

### Mix Control Problems
1. **Zipper Noise**: Current smoothing (5ms) insufficient for real-time control changes
2. **Loudness Jumps**: Linear mix control causes perceived volume changes due to harmonic generation
3. **No Equal-Loudness Compensation**: Mix changes affect perceived level due to harmonic content

### CPU Performance Traps
- Multi-channel expansion can easily saturate CPU with distortion
- Custom numpy loops less efficient than pyo's C implementations
- Lack of denormalization protection for tone filter state variable

## Battle-Tested Patterns

### Pyo Implementation Pattern
```python
# Efficient distortion with pyo objects
input_signal = Mix(voice_signals, voices=1)
drive_control = SigTo(0.75, time=0.02)  # Smooth parameter control
slope_control = SigTo(0.5, time=0.02)
disto = Disto(input_signal, drive=drive_control, slope=slope_control)

# Bitcrush with Degrade
bitdepth_control = SigTo(16, time=0.05)
srscale_control = SigTo(1.0, time=0.05)  
degrade = Degrade(input_signal, bitdepth=bitdepth_control, srscale=srscale_control)
```

### Signal Chain Integration
**Optimal placement** (based on techno production research):
```
Voice Mixer → Master Distortion → Tone Control → Reverb/Delay Sends → Master Limiter
```

### Transparent Mix Control
```python
# Equal-loudness mix control
dry_gain = Sqrt(1 - mix)  # -3dB at 50% mix
wet_gain = Sqrt(mix)      # Maintains perceived loudness
mix_smooth = SigTo(mix_target, time=0.02)  # Prevent zipper noise
```

## Trade-off Analysis

### Pyo Disto vs Custom Implementation
**Pyo Disto Advantages**:
- 4x faster processing (measured)
- Built-in post-distortion lowpass
- Proven stability in production use
- Automatic denormalization handling

**Current Custom Advantages**:
- Multiple distortion types in one module
- Flexible tone control range
- Direct numpy array processing
- Custom parameter mapping

### Master Insert vs Send Effect
**Master Insert** (Recommended):
- Affects entire mix consistently
- Prevents frequency masking issues
- Better for "glue" effect on full mix
- Easier gain staging control

**Send Effect**:
- Selective processing per voice
- Parallel processing preserves dynamics
- More complex routing required
- Harder to prevent overloads

## Red Flags

### Performance Warnings
1. **CPU Saturation**: Multi-channel expansion with distortion easily overloads CPU
2. **Denormal Numbers**: Tone filter state can cause performance drops without noise injection
3. **Real-time Safety**: No bounds checking on drive parameter changes

### Audio Quality Issues
1. **Master Clipping**: No protection against output overload from high drive settings
2. **Frequency Imbalance**: Heavy distortion destroys low-end content
3. **Zipper Artifacts**: Insufficient parameter smoothing for live control

### Integration Problems
1. **Signal Chain Position**: Current implementation after effects chain (suboptimal)
2. **No Sidechain**: Cannot bypass distortion for specific voices (e.g., kick drum)
3. **Parameter Drift**: No parameter validation or automatic recovery

## Key Recommendations

### 1. Implement Pyo-Based Master Distortion Insert
```python
class PyoMasterDistortion:
    def __init__(self, input_signal, server):
        # Core distortion
        self.drive_sig = Sig(0.0)
        self.drive = SigTo(self.drive_sig, time=0.02)
        self.slope_sig = Sig(0.5) 
        self.slope = SigTo(self.slope_sig, time=0.02)
        
        # Pyo Disto object
        self.disto = Disto(input_signal, drive=self.drive, slope=self.slope)
        
        # Mix control with equal-loudness
        self.mix_sig = Sig(0.0)
        self.mix = SigTo(self.mix_sig, time=0.02)
        self.dry_gain = Sqrt(1 - self.mix)
        self.wet_gain = Sqrt(self.mix)
        
        # Output mix
        self.output = (input_signal * self.dry_gain) + (self.disto * self.wet_gain)
        
        # Soft limiter for master bus protection
        self.limiter = Compress(self.output, thresh=-1, ratio=20, 
                               risetime=0.001, falltime=0.1, knee=0.5)
```

### 2. Optimal Parameter Ranges for Electronic Music
- **Techno/Acid Drive**: 0.1-0.6 (subtle saturation to aggressive)
- **Industrial**: 0.6-0.9 (heavy distortion)
- **Mix Control**: Equal-loudness curve (sqrt)
- **Tone Range**: 200Hz-8kHz (matches research findings)

### 3. Signal Chain Integration
Place distortion module between `dry_mix` and effects buses in `engine_pyo.py`:
```python
# Current: dry_mix → reverb/delay sends
# Improved: dry_mix → master_distortion → reverb/delay sends
self.master_distortion = PyoMasterDistortion(self.dry_mix, self.server)
self.distorted_signal = self.master_distortion.get_output()
# Update effects inputs to use distorted_signal
```

### 4. CPU Optimization
- Use pyo objects instead of numpy loops
- Add Denorm wrapper for tone filter
- Implement proper multi-channel handling
- Pre-allocate all buffers during initialization

### 5. Master Bus Protection
- Soft limiter with 20:1 ratio above -1dBFS
- High-frequency rolloff to prevent aliasing
- DC blocking filter in signal chain
- Peak monitoring with automatic gain reduction

---

*Research conducted 2025-01-07 by Chronus Nexus*
*Sources: Pyo 1.0.6 documentation, electronic music production best practices, real-world GitHub implementations*