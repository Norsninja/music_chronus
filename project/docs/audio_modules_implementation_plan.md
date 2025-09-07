# Audio Modules Implementation Plan
**Date**: 2025-01-07  
**Author**: Chronus Nexus & Mike  
**Status**: Research Complete, Implementation Starting

## Overview
Expanding Music Chronus with essential audio synthesis modules to transform it from a basic sine-wave system into a full modular synthesizer capable of rich, evolving sounds.

## Priority Order & Rationale

### Priority 1: Oscillator Types ⚡ CURRENT
**Impact**: Immediate sonic expansion  
**Risk**: Low (research shows clear path)  
**Implementation**: Replace Sine with selectable Saw/Square waveforms

### Priority 2: Distortion Module
**Impact**: Adds harmonic richness and aggression  
**Risk**: Low-Medium (CPU management needed)  
**Implementation**: Master insert with Disto object

### Priority 3: LFO Modules  
**Impact**: Brings movement and life to static sounds  
**Risk**: Medium (routing complexity)  
**Implementation**: Fixed destinations initially, expandable later

### Priority 4: Slide/Glide (Port)
**Impact**: Musical expression, 303-style bass  
**Risk**: Low (well-researched)  
**Implementation**: Dual-path frequency control

### Priority 5: Additional Envelopes
**Impact**: Complex modulation possibilities  
**Risk**: Low (builds on existing ADSR)  
**Implementation**: Per-voice filter envelope

## Module 1: Oscillator Types (Saw/Square)

### Research Findings
- **Click-free switching**: Use Selector with 3 oscillators, not table switching
- **Band-limiting**: Order=12 optimal, 8192 sample tables
- **CPU**: Linear scaling, ~47% for 50 oscillators on i5

### Implementation Details
```python
# voice.py modifications
class Voice:
    def __init__(self):
        # Create waveform tables
        self.sine_table = HarmTable([1], size=8192)
        self.saw_table = SawTable(order=12, size=8192).normalize()
        self.square_table = SquareTable(order=10, size=8192).normalize()
        
        # Create three oscillators
        self.osc_sine = Osc(self.sine_table, freq=self.freq_sig)
        self.osc_saw = Osc(self.saw_table, freq=self.freq_sig)
        self.osc_square = Osc(self.square_table, freq=self.freq_sig)
        
        # Selector for click-free switching
        self.waveform_select = Sig(0)  # 0=sine, 1=saw, 2=square
        self.osc = Selector([self.osc_sine, self.osc_saw, self.osc_square], 
                           voice=self.waveform_select)
        self.osc.setMode(1)  # Equal-power crossfade
        
    def set_waveform(self, waveform_type):
        """0=sine, 1=saw, 2=square"""
        self.waveform_select.value = waveform_type
```

### OSC Routes
- `/mod/voice1/osc/type <0|1|2>` - Select waveform
- `/mod/voice2/osc/type <0|1|2>`
- `/mod/voice3/osc/type <0|1|2>`
- `/mod/voice4/osc/type <0|1|2>`

### Demo Sequences
```python
# Bass comparison
/mod/voice2/osc/type 0  # Sine - warm, fundamental
/mod/voice2/osc/type 1  # Saw - rich, full
/mod/voice2/osc/type 2  # Square - hollow, sub

# Lead sound design
/mod/voice1/osc/type 1  # Saw for lead
/mod/voice1/filter/freq 2000
/mod/voice1/filter/q 4
```

## Module 2: Distortion (Master Insert)

### Research Findings
- **Pyo Disto**: 4x faster than custom waveshaping
- **Placement**: Before reverb/delay for clarity
- **Mix control**: Equal-loudness with Sqrt(1-mix)

### Implementation Details
```python
# engine_pyo.py - After voice mixing, before effects
class DistortionModule:
    def __init__(self, input_sig):
        self.input = input_sig
        
        # Parameters
        self.drive_sig = SigTo(0.0, time=0.02)  # 0-1
        self.mix_sig = SigTo(0.0, time=0.02)    # 0-1
        self.tone_sig = SigTo(0.5, time=0.02)   # 0-1 (LP/HP balance)
        
        # Distortion processing
        self.distorted = Disto(self.input, 
                               drive=self.drive_sig,
                               slope=0.9)  # Fixed slope for consistency
        
        # Tone control (post-distortion filtering)
        self.tone_lp = ButLP(self.distorted, freq=5000)
        self.tone_hp = ButHP(self.tone_lp, freq=200)
        
        # Equal-loudness mixing
        self.dry_gain = Sqrt(1 - self.mix_sig)
        self.wet_gain = Sqrt(self.mix_sig)
        
        self.output = (self.input * self.dry_gain) + (self.tone_hp * self.wet_gain)
```

### OSC Routes
- `/mod/dist1/drive <0-1>` - Distortion amount
- `/mod/dist1/mix <0-1>` - Wet/dry mix
- `/mod/dist1/tone <0-1>` - Brightness control

### Audio Chain
```
Voices → Mixer → DISTORTION → Reverb/Delay → Output
```

## Module 3: LFO Modules

### Research Findings
- **LFO class**: 8 waveforms, band-limited, for wobble
- **Sine class**: Efficient for simple tremolo
- **Critical**: Mix channels before effects (7x CPU savings)

### Implementation Details
```python
# engine_pyo.py - Global LFO modules
class LFOModule:
    def __init__(self, lfo_id="lfo1"):
        self.lfo_id = lfo_id
        
        # Parameters
        self.rate_sig = SigTo(0.25, time=0.02)   # Hz
        self.depth_sig = SigTo(0.5, time=0.02)   # 0-1
        self.shape_sig = SigTo(2, time=0.02)     # Waveform type
        
        # LFO oscillator (multiple waveforms)
        self.lfo = LFO(freq=self.rate_sig, 
                       type=self.shape_sig,  # 0-7 waveforms
                       sharp=0.5)
        
        # Output scaled to 0-1 range
        self.output = self.lfo * 0.5 + 0.5

# Fixed routing v1
self.lfo1 = LFOModule("lfo1")
self.lfo2 = LFOModule("lfo2")

# LFO1 → Voice2 filter cutoff (wobble bass)
lfo1_scaled = self.lfo1.output.range(200, 2000)
self.voices["voice2"].filter_freq_sig.value = lfo1_scaled

# LFO2 → Voice3 amplitude (tremolo)
lfo2_scaled = self.lfo2.output * self.lfo2.depth_sig
self.voices["voice3"].amp_sig.value = self.voices["voice3"].amp_sig * lfo2_scaled
```

### OSC Routes
- `/mod/lfo1/rate <0.01-10>` - LFO frequency Hz
- `/mod/lfo1/depth <0-1>` - Modulation depth
- `/mod/lfo1/shape <0-7>` - Waveform selection
- `/mod/lfo2/rate <0.01-10>`
- `/mod/lfo2/depth <0-1>`

### Waveform Types
- 0: Saw up
- 1: Saw down
- 2: Square
- 3: Triangle
- 4: Pulse
- 5: Bipolar pulse
- 6: Sample & Hold
- 7: Modulated sine

## Module 4: Slide/Glide (Port)

### Research Findings
- **Port**: Exponential curve matches TB-303
- **Timing**: 60ms fall time for authentic acid
- **Dual-path**: Need immediate + slide paths with Selector

### Implementation Details
```python
# voice.py modifications
class Voice:
    def __init__(self):
        # Existing frequency control
        self.freq_sig = SigTo(440, time=0.001)
        
        # Dual-path frequency routing
        self.freq_immediate = SigTo(self.freq_sig, time=0.001)
        self.freq_slide = Port(self.freq_sig, 
                              risetime=0.001,   # Fast attack
                              falltime=0.06)    # 303 slide time
        
        # Slide enable control
        self.slide_enable = Sig(0)  # 0=immediate, 1=slide
        self.freq_final = Selector([self.freq_immediate, self.freq_slide],
                                   voice=self.slide_enable)
        
        # Connect to oscillators
        self.osc.freq = self.freq_final
        
    def set_slide_time(self, time_sec):
        """Set slide time in seconds"""
        self.freq_slide.risetime = time_sec
        self.freq_slide.falltime = time_sec
        
    def set_slide_enable(self, enable):
        """Enable/disable slide mode"""
        self.slide_enable.value = 1 if enable else 0
```

### OSC Routes
- `/mod/voice1/slide/time <0.001-1.0>` - Slide time in seconds
- `/mod/voice1/slide/enable <0|1>` - Enable slide mode

### Sequencer Integration
```python
# In sequencer - detect legato notes
if pattern[step] == 'l':  # Legato marker
    voice.set_slide_enable(1)
    voice.set_freq(next_freq)  # No gate retrigger
else:
    voice.set_slide_enable(0)
    voice.gate(1)
    voice.set_freq(next_freq)
```

## Testing Strategy

### Phase 1: Individual Module Tests
1. **Oscillators**: A/B test each waveform, verify no clicks
2. **Distortion**: Test drive 0→1, verify mix control
3. **LFOs**: Verify smooth modulation, no zipper noise
4. **Slide**: Test immediate vs slide modes

### Phase 2: Integration Tests
1. Saw + Distortion = aggressive lead
2. Square + Slide + Acid = 303 bass
3. LFO1 + Voice2 filter = wobble bass
4. All modules together = complex patch

### Phase 3: Performance Tests
1. CPU usage with all modules active
2. Latency measurements
3. Pattern save/load with new parameters

## Success Criteria

✅ **Oscillators**
- Clean waveform switching without clicks
- Audible timbral difference between waveforms
- No aliasing below 5kHz

✅ **Distortion**
- Adds harmonics without uncontrolled clipping
- Transparent at mix=0
- Maintains perceived loudness

✅ **LFOs**
- Smooth modulation without stepping
- Rate/depth changes without artifacts
- Fixed routing works as designed

✅ **Slide**
- Authentic 303-style pitch glides
- Instant switch between modes
- No clicks or pops

## Risk Mitigation

**Risk**: Waveform aliasing  
**Mitigation**: Band-limited tables with order=12

**Risk**: CPU overload with all modules  
**Mitigation**: Profile each addition, optimize hot paths

**Risk**: Parameter explosion in UI  
**Mitigation**: Logical grouping, sensible defaults

**Risk**: Breaking existing patterns  
**Mitigation**: Backward compatibility, default to sine

## Implementation Schedule

**Week 1** (Current):
- Day 1-2: Oscillator types ⚡
- Day 3-4: Distortion module
- Day 5: Testing & demos

**Week 2**:
- Day 1-2: LFO modules
- Day 3-4: Slide/glide
- Day 5: Integration testing

**Week 3**:
- Additional envelopes
- Performance optimization
- Documentation

## Notes

- Research documents in `project/docs/research/`
- Each module self-registers with schema
- Maintain headless operation (no UI)
- Test with chronusctl.py after each addition

---
*Living document - update as implementation proceeds*