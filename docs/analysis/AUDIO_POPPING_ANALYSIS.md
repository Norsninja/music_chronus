# Audio Popping/Clicking Analysis - Music Chronus

**Date**: 2025-09-05  
**Analyzed by**: Chronus Nexus  
**Issue**: Periodic popping/clicking sounds at buffer boundaries

## Executive Summary

The popping occurs at buffer boundaries due to multiple discontinuity sources in the signal chain. The issue is compounded by the interaction between SimpleSine → ADSR → BiquadFilter modules.

## Root Causes Identified

### 1. ADSR Gate Transitions (PRIMARY CAUSE)

**Location**: `adsr.py` lines 146-151

**Issue**: When gate turns ON, ADSR enters ATTACK stage but **does not reset level to 0**. If the envelope was previously at any non-zero level (e.g., during RELEASE), there's an instant jump causing a click.

```python
if self._gate:
    # Gate on - start attack (allow retrigger)
    self._stage = self.ATTACK
    # BUG: _level is NOT reset here!
```

**Impact**: Every gate-on event creates a discontinuity from current level to attack slope.

### 2. Buffer Initialization Issue

**Location**: `module_host.py` line 355

**Issue**: The first buffer in the chain is filled with zeros when no input:
```python
self.chain_buffers[0].fill(0.0)
```

But SimpleSine is a **generator** that ignores input and writes its own output. This means the first buffer might contain stale data or zeros that don't match the sine phase continuity.

### 3. Frequency Change Discontinuities

**Location**: `simple_sine.py` lines 85-86, 104

**Issue**: When frequency changes, phase increment changes immediately at buffer boundary:
```python
freq = float(self.params["freq"])
phase_inc = self._two_pi_over_sr * freq
# ...
self._phase += phase_inc * self.buffer_size
```

While there IS 10ms smoothing configured for frequency (line 39), the phase accumulator still jumps because the new increment is applied to the entire buffer retrospectively.

### 4. Filter Coefficient Updates

**Location**: `biquad_filter.py` lines 175-176

**Issue**: Filter coefficients update at buffer boundaries. Even with 25ms smoothing on cutoff/Q parameters, the actual coefficient calculation happens instantly, potentially causing subtle clicks when filter characteristics change dramatically.

### 5. Parameter Smoothing Limitations

**Location**: `base.py` lines 133-138

**Issue**: The smoothing uses exponential (one-pole) filtering which updates **once per buffer**, not per-sample:
```python
alpha = 1.0 / (1.0 + smooth_samples / self.buffer_size)
new_value = current + alpha * (target - current)
```

This means parameter changes create a step at each buffer boundary rather than a smooth ramp across the buffer.

## Why It's Worse in Full Chain vs Unit Tests

1. **Accumulation**: Each module adds its own potential discontinuity
2. **ADSR Multiplication**: The ADSR multiplies the input signal, amplifying any existing discontinuities
3. **Filter Resonance**: The BiquadFilter can emphasize discontinuities, especially with high Q values
4. **Buffer Timing**: The rigid buffer-boundary updates create synchronized discontinuities every 512 samples (10.7ms)

## Proposed Fixes

### Fix 1: Reset ADSR Level on Gate-On
```python
# In adsr.py, line 148
if self._gate:
    # Gate on - start attack (allow retrigger)
    self._stage = self.ATTACK
    self._level = 0.0  # ADD THIS: Reset to zero for click-free retrigger
```

### Fix 2: Add Gate Smoothing
```python
# In adsr.py, add very short ramp on gate transitions
if self._gate and old_gate != self._gate:
    self._stage = self.ATTACK
    # Add 1ms ramp from current level to 0
    self._ramp_samples = int(0.001 * self.sr)
    self._ramp_start = self._level
    self._ramp_target = 0.0
```

### Fix 3: Per-Sample Parameter Smoothing
Instead of one-step-per-buffer smoothing, implement true per-sample ramping:
```python
# In base.py _process_audio wrapper
if param_changing:
    ramp = np.linspace(old_value, new_value, self.buffer_size)
    # Apply ramp per-sample in the processing loop
```

### Fix 4: Phase-Coherent Frequency Changes
```python
# In simple_sine.py
# Store old frequency and interpolate phase increment across buffer
if abs(self._last_freq - freq) > 0.01:
    # Interpolate phase increment across this buffer
    phase_inc_start = self._two_pi_over_sr * self._last_freq
    phase_inc_end = self._two_pi_over_sr * freq
    # Create ramp for smooth transition
```

### Fix 5: Soft-Clip Output
Add a very gentle soft-clipper at the final output to round off any remaining discontinuities:
```python
# In supervisor audio callback
# Gentle tanh limiting to smooth sharp edges
output = np.tanh(buffer * 0.9) * 1.1
```

## Immediate Workaround

For testing, you can reduce the popping by:
1. Using longer ADSR attack times (>20ms)
2. Avoiding rapid gate on/off
3. Using lower filter Q values
4. Making frequency changes more gradually

## Testing Recommendations

1. Create a test that monitors zero-crossings and identifies discontinuities
2. Record the raw output and analyze in an audio editor for visual confirmation
3. Test each module in isolation first, then in combination
4. Use a test signal (not sine) to better hear the artifacts

## Conclusion

The popping is primarily caused by the ADSR not resetting its level on gate-on events, combined with buffer-boundary parameter updates that create synchronized discontinuities. The issue is fixable with relatively small code changes, primarily in the ADSR module and potentially adding per-sample smoothing for critical parameters.

---
*Analysis complete - Ready to implement fixes*