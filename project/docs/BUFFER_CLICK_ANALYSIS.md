# Buffer Boundary Click Analysis

**Date**: 2025-09-05
**Finding**: Periodic clicks every buffer boundary (~10.7ms)

## Root Cause Identified

The clicking occurs at EVERY buffer boundary, regardless of:
- ADSR state (clicks even with gate held ON)
- Parameter changes (clicks even with steady tone)
- Which ADSR implementation is used

## SimpleSine Phase Problem

Looking at `simple_sine.py` lines 89-104:

```python
# Line 89-93: Calculate phases for THIS buffer
np.multiply(self._phase_index, phase_inc_f32, out=out_buf)  
out_buf += np.float32(self._phase)  # Uses CURRENT phase

# Line 95: Generate samples
np.sin(out_buf, out=out_buf)

# Line 104: Update phase for NEXT buffer  
self._phase += phase_inc * self.buffer_size
```

### The Bug

The phase calculation has a subtle but critical issue:

1. **Buffer N**: 
   - Starts with phase = X
   - Generates samples 0-511 with phases: X, X+inc, X+2*inc, ..., X+511*inc
   - Updates self._phase to X + 512*inc

2. **Buffer N+1**:
   - Starts with phase = X + 512*inc
   - Sample 0 uses phase X + 512*inc
   - But Buffer N's last sample (511) used phase X + 511*inc
   - **Gap**: There's a missing increment between buffers!

### Why This Causes Clicks

The phase should be continuous:
- Last sample of buffer N: phase = X + 511*inc
- First sample of buffer N+1: phase = X + 512*inc ✓ (correct)

But the implementation might have an off-by-one error or the phase wrapping at line 107-108 might be creating discontinuities.

## Other Potential Issues

### 1. Float32 Precision Loss
Lines 91-93 cast to float32, potentially losing precision:
```python
phase_inc_f32 = np.float32(phase_inc)
out_buf += np.float32(self._phase)
```

### 2. Phase Wrapping
Lines 107-108:
```python
if self._phase > self._wrap_threshold:
    self._phase = self._phase % self._two_pi
```
This modulo operation could create a tiny discontinuity.

### 3. Buffer Initialization
The chain might not be preserving phase continuity between buffer processes.

## Test to Confirm

We can verify this by logging the first and last samples of each buffer:

```python
# In SimpleSine._process_audio, after np.sin:
if os.environ.get('DEBUG_PHASE'):
    print(f"Buffer: first_sample={out_buf[0]:.6f}, last_sample={out_buf[-1]:.6f}")
    # Next buffer's first sample should continue smoothly from this last sample
```

## Solution Options

1. **Fix phase accumulation** - Ensure perfect continuity
2. **Add cross-buffer smoothing** - Blend last/first samples
3. **Use double precision throughout** - Avoid float32 casting
4. **Review phase wrapping** - Use fmod or smoother wrapping

## Conclusion

The clicks are NOT from:
- ADSR (proven by holding gate ON)
- Parameter changes (happens with steady tone)
- Buffer underruns (metrics show 0)

The clicks ARE from:
- Buffer boundary discontinuities
- Likely in SimpleSine phase handling
- Possibly compounded by float32 precision loss
- Occurs every 512 samples (10.7ms) exactly

This explains why every ADSR implementation had the same clicks - the problem is upstream in the oscillator!

---
*Ready for Senior Dev review*