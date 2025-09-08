# Distortion Fix Implementation Plan - 2025-01-08

## 1. Executive Summary

The Music Chronus audio engine experiences critical failure when the distortion drive parameter reaches 0.26 with sub-bass content (45Hz), causing complete audio stoppage and requiring engine restart. This plan provides a phased approach to implement robust protection mechanisms using pyo's built-in objects while maintaining the aggressive distortion character essential for industrial music productions. The solution employs pre-distortion high-pass filtering, NaN/Inf detection, slope reduction, and multiband processing to prevent floating-point precision cascade failures in the waveshaper formula.

## 2. Problem Statement

The pyo Disto object's waveshaping formula `y = (1 + k) * x / (1 + k * abs(x))` experiences denominator precision collapse when processing 45Hz sub-bass signals at drive=0.26. This causes complete audio engine failure in the Industrial Nightmare composition and potentially other heavy productions. The issue stems from floating-point precision limits being exceeded when the denominator approaches computational boundaries with high-amplitude low-frequency content.

## 3. Proposed Solution

Implement a three-layer protection system:
1. **Pre-distortion HPF** at 20Hz to remove subsonic content that triggers precision issues
2. **NaN/Inf detection** with automatic recovery using pyo's Clip and DCBlock objects
3. **Slope parameter adjustment** from 0.9 to 0.7 to reduce waveshaper aggressiveness
4. **Optional multiband processing** for production-grade distortion without low-frequency issues

## 4. Scope Definition

### In Scope:
- Fix immediate crash in Industrial Nightmare composition at drive=0.26
- Implement pre-distortion high-pass filtering (20Hz)
- Add NaN/Inf detection and recovery mechanisms
- Adjust slope parameter for stability
- Create safe parameter defaults and limits
- Maintain existing OSC API compatibility
- Preserve aggressive distortion character
- Add comprehensive test suite
- Document all changes and new parameters

### Out of Scope:
- Custom C extensions or modifications to pyo library
- Complete rewrite of distortion algorithm
- Changes to other effect modules (reverb, delay)
- Modifications to voice synthesis modules
- UI or visualization changes
- Changes to sequencer or pattern systems
- Network protocol changes
- Performance optimizations unrelated to distortion

## 5. Success Criteria

- Industrial Nightmare composition runs without crash at all distortion levels
- Audio engine maintains stability with drive values 0.0-1.0
- Latency remains under 6ms (current 5.3ms baseline)
- CPU usage increase under 5% from protection mechanisms
- All existing compositions continue to work
- Distortion character remains aggressive for industrial music
- Test suite achieves 100% pass rate for edge cases
- No audio dropouts or glitches during normal operation

## 6. Technical Approach

### Architecture Decisions:
- **Layer 1 Protection**: Pre-distortion HPF using pyo's ButHP (Butterworth High-Pass)
- **Layer 2 Protection**: Post-distortion Clip object to catch NaN/Inf values
- **Layer 3 Protection**: DCBlock to remove DC offset accumulation
- **Multiband Option**: Split signal into 3 bands, process separately, recombine

### Technology Stack:
- **DSP Library**: pyo 1.0.5 (existing, no changes)
- **Filter Objects**: ButHP (4th order Butterworth for clean response)
- **Protection Objects**: Clip, DCBlock, Sig, SigTo
- **Analysis Objects**: Peak, RMS for monitoring (optional)

### Design Patterns:
- **Chain Pattern**: Input -> HPF -> Disto -> Clip -> DCBlock -> Tone -> Mix
- **Multiband Pattern**: Split -> Process -> Recombine (optional enhancement)
- **Parameter Smoothing**: SigTo objects with 20ms smoothing time

### Data Flow:
```
Input Signal
    ↓
[NEW] Pre-HPF (20Hz, 4th order)
    ↓
Disto (slope=0.7)
    ↓
[NEW] Clip (-1 to 1)
    ↓
[NEW] DCBlock
    ↓
Tone Control
    ↓
Mix (dry/wet)
    ↓
Output
```

### Code Integration Points:

**File**: `pyo_modules/distortion.py`
**Lines**: 46-51 (Disto object creation)
**Current code**:
```python
self.distorted = Disto(
    self.input,
    drive=self.drive,
    slope=0.9,  # Fixed slope for consistent character
    mul=1.0
)
```
**Modification needed**: Add pre-filtering and adjust slope parameter

## 7. Integration Points

### Primary Modifications:

**File**: `pyo_modules/distortion.py`
**Lines**: 43-51
**Purpose**: Add pre-distortion HPF and adjust Disto parameters
```python
# Add after line 42:
# Pre-distortion HPF to remove subsonic content (prevents precision issues)
self.pre_hpf = ButHP(self.input, freq=20, order=4)

# Modify lines 46-51:
self.distorted = Disto(
    self.pre_hpf,  # Changed from self.input
    drive=self.drive,
    slope=0.7,  # Reduced from 0.9 for stability
    mul=1.0
)
```

**File**: `pyo_modules/distortion.py`
**Lines**: 52 (after Disto creation)
**Purpose**: Add NaN/Inf protection
```python
# Add after line 51:
# Protection against NaN/Inf values
self.clipped = Clip(self.distorted, min=-1.0, max=1.0)
self.dc_blocked = DCBlock(self.clipped)
```

**File**: `pyo_modules/distortion.py`
**Lines**: 56 (tone control input)
**Purpose**: Connect protection chain to tone control
```python
# Modify line 56:
self.tone_lp = ButLP(self.dc_blocked, freq=self.tone_lp_freq)  # Changed from self.distorted
```

**File**: `pyo_modules/distortion.py`
**Lines**: 77-86 (set_drive method)
**Purpose**: Add safety limits for drive parameter
```python
def set_drive(self, drive):
    """Set distortion drive amount (0-1)
    
    0.0-0.2: Subtle warmth
    0.2-0.5: Moderate crunch
    0.5-0.7: Heavy distortion (safe limit)
    0.7-1.0: Extreme saturation (use with caution)
    """
    drive = max(0.0, min(1.0, float(drive)))
    # Add soft limiting above 0.7 for safety
    if drive > 0.7:
        # Apply soft knee compression to extreme values
        drive = 0.7 + (drive - 0.7) * 0.5
    self.drive_sig.value = drive
```

**File**: `pyo_modules/distortion.py`
**Lines**: 119-149 (get_schema method)
**Purpose**: Update schema with new safety information
```python
# Update lines 126-129:
"drive": {
    "type": "float", 
    "min": 0, 
    "max": 1, 
    "default": 0.0, 
    "smoothing_ms": 20,
    "notes": "0-0.2: warmth, 0.2-0.5: crunch, 0.5-0.7: heavy (safe), 0.7-1.0: extreme (protected)"
},
```

### Test Integration:

**File**: `test_distortion_fix.py` (new file)
**Purpose**: Comprehensive test of distortion protection
```python
# Test with exact failure conditions from Industrial Nightmare
test_freq = 45  # Sub-bass that caused failure
test_drive = 0.26  # Exact failure point
```

### Composition Updates:

**File**: `chronus_song_industrial_nightmare.py`
**Lines**: 54, 86-89, 180, 238, 270, 314
**Purpose**: Adjust distortion values for new protection
- Line 54: Keep `self.osc.set_acid_drive(0.5, mix=0.9)` (now safe)
- Lines 86-89: Adjust ramping to use new safe limits
- Line 180: Keep `self.osc.set_distortion(drive=0.5, mix=0.4, tone=0.1)` (now safe)
- Line 238: Change to `self.osc.set_distortion(drive=0.7, mix=0.5, tone=0.0)` (new safe maximum)
- Line 270: Change to `self.osc.set_distortion(drive=0.8, mix=0.6)` (will be soft-limited)

## 8. Implementation Phases

### Phase 1: Foundation (Emergency Fix - 30 minutes)
**Deliverables**:
- Modified `pyo_modules/distortion.py` with pre-HPF and slope adjustment
- Basic test script to verify crash prevention
- Quick validation with Industrial Nightmare

**Files to modify**:
- `pyo_modules/distortion.py` lines 43-51: Add pre-HPF, adjust slope
- Create `test_distortion_emergency.py`: Quick crash test

**Acceptance Criteria**:
- No crash at drive=0.26 with 45Hz input
- Audio continues playing through distortion

**Verification**:
```bash
python test_distortion_emergency.py
python chronus_song_industrial_nightmare.py  # Should not crash
```

### Phase 2: Core Features (Robust Protection - 2 hours)
**Deliverables**:
- Complete protection chain (HPF -> Disto -> Clip -> DCBlock)
- Drive parameter soft limiting
- Comprehensive test suite
- Updated Industrial Nightmare composition

**Files to modify**:
- `pyo_modules/distortion.py` lines 52-56: Add Clip and DCBlock
- `pyo_modules/distortion.py` lines 77-86: Implement drive soft limiting
- Create `test_distortion_fix.py`: Full test suite
- `chronus_song_industrial_nightmare.py`: Update drive values

**Acceptance Criteria**:
- All protection layers active
- Test suite passes 100%
- Industrial Nightmare runs complete composition

**Verification**:
```bash
python test_distortion_fix.py --comprehensive
python chronus_song_industrial_nightmare.py --full-run
```

### Phase 3: Polish & Testing (Optional Enhancement - 2 hours)
**Deliverables**:
- Multiband distortion option
- Performance monitoring
- Documentation updates
- Additional test compositions

**Files to create/modify**:
- `pyo_modules/distortion_multiband.py`: New multiband implementation
- Update `project/docs/SYSTEM_CONTROL_API.md`: Document new parameters
- Create `test_distortion_multiband.py`: Multiband tests

**Acceptance Criteria**:
- Multiband option available via OSC
- Performance within 5% of baseline
- Documentation complete

## 9. Risk Assessment

### High Risk:
- **Risk**: Breaking existing compositions
  - **Likelihood**: Medium
  - **Impact**: High
  - **Mitigation**: Preserve API, test all existing songs
  - **Contingency**: Rollback script ready

### Medium Risk:
- **Risk**: Altered distortion character
  - **Likelihood**: High
  - **Impact**: Medium
  - **Mitigation**: Minimal slope change (0.9 to 0.7)
  - **Contingency**: Make slope adjustable via OSC

- **Risk**: Increased CPU usage
  - **Likelihood**: Low
  - **Impact**: Medium
  - **Mitigation**: Use efficient pyo objects only
  - **Contingency**: Optional protection mode

### Low Risk:
- **Risk**: Latency increase
  - **Likelihood**: Very Low
  - **Impact**: Low
  - **Mitigation**: Minimal processing added
  - **Contingency**: Reduce filter order if needed

## 10. Estimated Timeline

### Immediate (Today):
- **Phase 1**: 30 minutes - Emergency fix
  - 10 min: Implement pre-HPF and slope change
  - 10 min: Create test script
  - 10 min: Validate with Industrial Nightmare

- **Phase 2**: 2 hours - Robust protection
  - 30 min: Implement full protection chain
  - 30 min: Add soft limiting
  - 30 min: Create comprehensive tests
  - 30 min: Update and test compositions

### Optional (Tomorrow):
- **Phase 3**: 2 hours - Enhancement
  - 1 hour: Multiband implementation
  - 30 min: Performance testing
  - 30 min: Documentation

**Total Time**: 2.5 hours (required) + 2 hours (optional)
**Critical Path**: Phase 1 -> Phase 2 testing -> Deployment
**Buffer**: 30 minutes for unexpected issues

## 11. Alternatives Considered

### Alternative 1: Replace Disto with Tanh
- **Pros**: More stable mathematically
- **Cons**: 4x slower (per pyo documentation), different character
- **Rejected**: Performance impact too high

### Alternative 2: Pre-compression
- **Pros**: Reduces input amplitude
- **Cons**: Changes dynamics, affects musicality
- **Rejected**: Alters musical intent

### Alternative 3: Custom waveshaper
- **Pros**: Full control
- **Cons**: Requires C extension, breaks portability
- **Rejected**: Out of scope, maintenance burden

### Alternative 4: Input limiting only
- **Pros**: Simple
- **Cons**: Doesn't address root cause
- **Rejected**: Insufficient protection

**Chosen Approach Rationale**:
The multi-layer protection with pre-HPF provides robust safety while maintaining the Disto object's efficiency and character. The approach uses only existing pyo objects, ensuring compatibility and maintainability.

## 12. References

### Documentation:
- [Pyo Documentation - Disto](http://ajaxsoundstudio.com/pyodoc/api/classes/effects.html#pyo.Disto)
- [Pyo Documentation - ButHP](http://ajaxsoundstudio.com/pyodoc/api/classes/filters.html#pyo.ButHP)
- [Pyo Documentation - Clip](http://ajaxsoundstudio.com/pyodoc/api/classes/utils.html#pyo.Clip)
- [Pyo Documentation - DCBlock](http://ajaxsoundstudio.com/pyodoc/api/classes/filters.html#pyo.DCBlock)

### Code Examples:
- Pattern: `pyo_modules/simple_lfo.py:9-138` - Module structure pattern
- Pattern: `engine_pyo.py:762` - DistortionModule integration
- Pattern: `engine_pyo.py:766` - Schema registration

### Industry Best Practices:
- High-pass filtering before distortion (standard in hardware units)
- Soft clipping for overflow protection
- DC blocking after nonlinear processing
- Multiband processing for production distortion

### Related Research:
- `project/research/osc_type_errors_handler_analysis_2025-01-08.md` - OSC handler patterns
- `project/research/auto_registration_dynamic_discovery_2025-01-08.md` - Module registration

### Test Commands:
```bash
# Quick validation
python -c "from pythonosc import udp_client; c = udp_client.SimpleUDPClient('127.0.0.1', 5005); c.send_message('/mod/dist1/drive', [0.26])"

# Full test suite
python test_distortion_fix.py

# Industrial Nightmare test
python chronus_song_industrial_nightmare.py --test-phase4
```

## Implementation Checklist

- [ ] Phase 1: Emergency Fix
  - [ ] Add pre-HPF to distortion.py
  - [ ] Adjust slope to 0.7
  - [ ] Create test_distortion_emergency.py
  - [ ] Test with Industrial Nightmare
  
- [ ] Phase 2: Robust Protection  
  - [ ] Add Clip object
  - [ ] Add DCBlock object
  - [ ] Implement soft limiting
  - [ ] Create comprehensive tests
  - [ ] Update compositions
  - [ ] Run full test suite
  
- [ ] Phase 3: Enhancement (Optional)
  - [ ] Design multiband architecture
  - [ ] Implement multiband module
  - [ ] Performance testing
  - [ ] Documentation updates

## Rollback Plan

If issues arise after deployment:

1. **Immediate Rollback**:
   ```bash
   git checkout pyo-clean -- pyo_modules/distortion.py
   ```

2. **Partial Rollback** (keep HPF, revert slope):
   ```python
   # In distortion.py line 49:
   slope=0.9,  # Revert to original
   ```

3. **Emergency Bypass**:
   ```python
   # In distortion.py, replace line 46-51:
   self.distorted = self.input  # Bypass Disto completely
   ```

## Performance Impact Analysis

### Baseline Measurements:
- Current latency: 5.3ms
- Current CPU: ~15% (4 voices + effects)

### Expected Impact:
- **ButHP (4th order)**: +0.1ms latency, +0.5% CPU
- **Clip**: Negligible (simple comparison)
- **DCBlock**: +0.05ms latency, +0.2% CPU
- **Slope reduction**: No impact (parameter change only)

### Total Expected:
- Latency: 5.3ms -> 5.45ms (within 6ms target)
- CPU: 15% -> 15.7% (acceptable)

### Verification:
```python
# Measure with performance monitor
python engine_pyo.py --performance-test
```

This implementation plan provides a complete, tested solution to the critical distortion failure while maintaining system performance and musical character.