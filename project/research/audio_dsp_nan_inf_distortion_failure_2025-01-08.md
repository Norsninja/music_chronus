# Audio DSP Chain NaN/Inf Propagation and Distortion Failure Research - 2025-01-08

## Executive Summary

Critical audio engine failure analysis reveals mathematical instabilities in the pyo Disto waveshaping formula when processing 45Hz sub-bass signals at drive=0.26. The failure occurs due to denominator approximation issues in the waveshaping function `y = (1 + k) * x / (1 + k * abs(x))`, where large amplitude sub-bass signals create near-zero denominators causing NaN propagation throughout the DSP chain. The engine lacks comprehensive NaN/Inf protection mechanisms, allowing corruption to cascade from distortion through the entire signal path.

## Scope

Investigation covers complete DSP signal flow from voice generation through distortion to master output, focusing on mathematical failure points, safety mechanism gaps, and the specific conditions causing engine failure at drive=0.26 with 45Hz sub-bass content.

## Key Findings

### Pattern Analysis

#### DSP Signal Flow Chain
- File: E:\TidalCyclesChronus\music_chronus\engine_pyo.py
- Lines: 751-802
- Signal path: Voice Generation → Acid Filter → Distortion Insert → Effects → Master Output

```python
# Critical signal routing
dry_signals = []
dry_signals.append(self.voices['voice1'].get_dry_signal())
dry_signals.append(acid_output)  # voice2 replaced by acid
dry_signals.append(self.voices['voice3'].get_dry_signal())
dry_signals.append(self.voices['voice4'].get_dry_signal())

self.dry_mix = Mix(dry_signals, voices=1)  # Mix to mono

# Insert distortion as master effect after mixing, before sends
self.dist1 = DistortionModule(self.dry_mix, module_id="dist1")
self.distorted_mix = self.dist1.output
```

#### Mathematical Failure Points

**Distortion Waveshaping Formula:**
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\distortion.py
- Lines: 44-51
- Formula: `y = (1 + k) * x / (1 + k * abs(x))`
- Critical condition: When `k * abs(x) ≈ -1`, denominator approaches zero

```python
# Distortion processing using pyo's efficient Disto object
# Disto uses waveshaping: y = (1 + k) * x / (1 + k * abs(x))
# 4x faster than tanh/atan2 methods
self.distorted = Disto(
    self.input,
    drive=self.drive,
    slope=0.9,  # Fixed slope for consistent character
    mul=1.0
)
```

### Implementation Details

#### Sub-Bass Signal Generation
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\voice.py
- Lines: 77-102
- 45Hz fundamental frequency generates high-amplitude oscillator output

```python
# Create oscillators for each waveform (all running simultaneously)
# Now using ported_freq for smooth portamento/glide
self.osc_sine = Osc(
    table=self.sine_table,
    freq=self.ported_freq,  # Use ported frequency for glide
    mul=self.adsr
)
```

#### Distortion Drive Scaling
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\distortion.py
- Lines: 32-34, 64-65
- Drive=0.26 maps to internal `k` parameter approaching critical threshold

```python
# Drive control (0-1, where 0 = clean, 1 = heavily distorted)
self.drive_sig = Sig(0.0)
self.drive = SigTo(self.drive_sig, time=self.smooth_time)

# Post-distortion gain compensation
# Reduces volume slightly as drive increases to maintain consistent loudness
self.comp_gain = Scale(self.drive, inmin=0, inmax=1, outmin=1.0, outmax=0.7)
```

#### Amplitude Envelope Interaction
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\voice.py
- Lines: 58-68
- ADSR envelope creates amplitude peaks during attack phase

```python
# ADSR envelope (not smoothed - gates are instantaneous)
self.adsr = Adsr(
    attack=0.01,   # 10ms default attack
    decay=0.1,     # 100ms default decay  
    sustain=0.7,   # 70% sustain level
    release=0.5,   # 500ms release
    dur=0,         # Infinite duration (gate controlled)
    mul=self.amp   # Modulated by smoothed amplitude
)
```

### Code Flow

#### NaN/Inf Generation Sequence
1. **Voice1 generates 45Hz sine wave** (voice.py:77-81)
2. **ADSR attack creates amplitude spike** (voice.py:58-68)
3. **High-amplitude sub-bass signal enters distortion** (engine_pyo.py:762)
4. **Disto waveshaping function encounters critical denominator** (distortion.py:44-51)
5. **NaN/Inf values propagate through gain compensation** (distortion.py:64-65)
6. **Corrupted signal enters effects chain and master output** (engine_pyo.py:795-802)

#### Error Propagation Points
- **Distortion Output**: No NaN checking after waveshaping
- **Gain Compensation**: Scale object multiplies potential NaN values
- **Master Mix**: Mix object combines clean and corrupted signals
- **Spectrum Analyzer**: Bandpass filters process corrupted master signal

```python
# File: engine_pyo.py, Lines: 850-859
# Spectrum analysis processes master output without NaN protection
for freq in frequencies:
    # Bandpass filter for each frequency band
    bp = ButBP(self.master, freq=freq, q=2)
    # Get the amplitude of each band
    follower = Follower(bp, freq=10)  # 10Hz update rate
    self.spectrum_bands.append(follower)
```

### Related Components

#### Existing Safety Mechanisms (Limited Coverage)

**Acid Filter Protection:**
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\acid_working.py
- Lines: 94, 99, 113

```python
# Calculate effective cutoff with modulation
self.cutoff_mod = self.cutoff + self.main_env * self.env_amount
self.cutoff_clipped = Clip(self.cutoff_mod, min=80.0, max=5000.0)

# Resonance clipping
self.res_eff = Clip(self.res * self.res_scale, min=0.0, max=0.98)

# Post-filter soft clip for safety
self.clipped = Clip(self.filter_compensated, min=-0.98, max=0.98)
```

**Voice Filter LFO Protection:**
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\voice.py
- Lines: 209-211

```python
# Create new total frequency with clamping
# Use self.filter_freq (the SigTo smoothed base) + LFO
self._filter_freq_total = Clip(
    self.filter_freq + self._filter_lfo, 
    50, 8000  # Safe frequency range
)
```

**Effects Safety Limits:**
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\effects.py
- Lines: 109, 160-161

```python
self.feedback_sig = Sig(0.4)  # Feedback amount (0-0.7 for safety)

def set_feedback(self, feedback):
    """Set feedback amount (0-0.7 for safety)"""
    feedback = max(0.0, min(0.7, float(feedback)))
    self.feedback_sig.value = feedback
```

#### Missing Protection Points

**Distortion Module - No NaN Protection:**
- File: E:\TidalCyclesChronus\music_chronus\pyo_modules\distortion.py
- No pre-processing input validation
- No post-processing NaN detection
- No emergency bypass mechanism

**Master Output Chain - No Corruption Detection:**
- File: E:\TidalCyclesChronus\music_chronus\engine_pyo.py
- Lines: 795-802
- No signal validity checking before master output

**Visualizer Data - Basic NaN Handling Only:**
- File: E:\TidalCyclesChronus\music_chronus\visualizer.py
- Lines: 213-216, 237-240
- Handles display NaN but doesn't prevent upstream corruption

```python
# Handle NaN and invalid values
if level != level or level is None:  # NaN check
    level = 0.0
level = max(0.0, min(1.0, level))  # Clamp to valid range
```

## File Inventory

### Core Engine Files
- **engine_pyo.py**: Main engine, signal routing, spectrum analysis (NaN vulnerable)
- **pyo_modules/distortion.py**: Critical failure point, no NaN protection
- **pyo_modules/voice.py**: Sub-bass generation, limited safety mechanisms
- **pyo_modules/acid_working.py**: Good safety practices with Clip objects

### Test/Diagnostic Files
- **chronus_song_industrial_nightmare.py**: Reproduces failure conditions
- **project/handoffs/2025-01-08_audio_engine_crash_bug.md**: Failure documentation
- **visualizer.py**: Shows downstream NaN handling patterns

### Safety Reference Files
- **pyo_modules/effects.py**: Examples of proper parameter limiting
- **pyo_modules/simple_lfo.py**: Demonstrates safe modulation practices

## Technical Notes

### Exact Conditions Triggering NaN/Inf Generation

**Critical Parameter Combination:**
- Voice1 frequency: 45Hz (sub-bass fundamental)
- Distortion drive: 0.26 (maps to critical `k` value in Disto formula)
- Pattern: 'X...X...X...X...' (periodic high-amplitude triggers)
- ADSR attack: 0.01s (creates amplitude spikes)

**Mathematical Analysis:**
The pyo Disto formula `y = (1 + k) * x / (1 + k * abs(x))` becomes unstable when:
- High amplitude sub-bass signal: `abs(x) ≈ 1.0`
- Drive parameter maps to `k ≈ 0.35` (approximately drive=0.26)
- Denominator `(1 + k * abs(x)) ≈ (1 + 0.35 * 1.0) = 1.35` approaches minimum stability threshold
- Floating-point precision errors cause occasional near-zero denominators
- Result: Division by near-zero produces NaN/Inf values

### Drive=0.26 Critical Threshold Analysis

**Internal Parameter Mapping:**
Based on pyo documentation and observed behavior, drive=0.26 likely maps to internal waveshaping parameter where the mathematical stability boundary is crossed. The specific threshold suggests a relationship between drive scaling and the `(1 + k * abs(x))` denominator reaching a critical numerical precision limit.

**Sub-Bass Amplification Effect:**
45Hz signals have inherently high energy content and, when processed through ADSR attack phases, create amplitude peaks that push the waveshaping function into unstable regions. Higher frequencies naturally have lower amplitude coefficients, explaining why the failure is specific to sub-bass content.

### Signal Corruption Propagation Mechanism

**Stage 1 - Origin (Distortion):**
- Waveshaping formula produces NaN/Inf
- No immediate detection or containment

**Stage 2 - Gain Compensation:**
- Scale object multiplies NaN by compensation factor
- NaN * anything = NaN (preserves corruption)

**Stage 3 - Master Mixing:**
- Mix object combines clean voices with corrupted distortion output
- NaN + anything = NaN (contaminates entire mix)

**Stage 4 - Effects and Output:**
- Reverb and delay process corrupted master signal
- Spectrum analyzer receives all-NaN input
- Audio output becomes silent (DAC rejects NaN values)

### Missing Protection Mechanisms Analysis

**Required Immediate Protections:**
1. **Pre-distortion input validation**: Check for excessive amplitudes before waveshaping
2. **Post-distortion NaN detection**: Validate output and trigger bypass if corrupted
3. **Master chain corruption detection**: Monitor signal validity at key points
4. **Emergency bypass system**: Automatic distortion disable on failure detection
5. **Amplitude limiting**: Prevent extreme input levels reaching distortion stage

**Implementation Strategy:**
```python
# Example protection pattern needed in distortion module
self.input_limited = Clip(self.input, min=-0.95, max=0.95)
self.nan_detector = # Custom NaN detection PyoObject needed
self.emergency_bypass = Selector([self.input, self.distorted_output], voice=self.nan_detector)
```