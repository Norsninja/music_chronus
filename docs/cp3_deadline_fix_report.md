# CP3 Deadline Scheduling Fix - Implementation Report

**Date**: 2025-09-02  
**Implemented By**: Chronus Nexus  
**Reviewed By**: Mike (User)  
**For Review By**: Senior Dev  

## Executive Summary

Implemented deadline scheduling in `supervisor_v3_router.py` as specified. The fix improved audio quality (tone is "clearer") but artifacts remain, described as "buffering" sounds. Root cause analysis suggests additional issues beyond timing.

## Implementation Details

### Changes Made to `supervisor_v3_router.py`

**Lines Modified**: 113-252 (approximately 40 lines changed)

#### 1. Added Timing Initialization (Lines 117-119)
```python
# Timing for buffer production (deadline scheduling)
buffer_period = BUFFER_SIZE / SAMPLE_RATE  # 5.33ms at 256/48000
next_buffer_time = time.monotonic() + buffer_period
```

#### 2. Wrapped Audio Generation in Deadline Check (Lines 213-247)
```python
# Generate audio on deadline schedule
current_time = time.monotonic()
if current_time >= next_buffer_time - 0.001:  # 1ms early is OK
    # Generate audio
    output_buffer = module_host.process_chain()
    # ... existing RMS logging and ring write ...
    
    # Calculate next buffer time
    next_buffer_time += buffer_period
    
    # Prevent drift - if we're way behind, reset
    if next_buffer_time < current_time - 0.1:
        next_buffer_time = current_time + buffer_period
```

#### 3. Replaced Fixed Sleep with Smart Sleep (Lines 249-252)
```python
# Smart sleep based on deadline
sleep_time = next_buffer_time - time.monotonic()
if sleep_time > 0.0001:  # Only sleep if we have time
    time.sleep(min(sleep_time, 0.001))  # Sleep up to deadline, max 1ms
```

### Implementation Matches Senior Dev Specification

✅ Location correct: `worker_process()` function  
✅ Timing init after module_host setup  
✅ Deadline check with 1ms early margin  
✅ Drift protection at 100ms threshold  
✅ Smart sleep implementation  
✅ Command draining preserved  
✅ No allocations in hot path  

## Test Results

### 1. Audio Verification Test
- **Result**: ✅ PASS - Audio output confirmed working
- **Details**: User heard two test tones (440Hz and 880Hz)

### 2. Oscillator-Only Test (Critical)
- **Result**: ⚠️ PARTIAL - Tone clearer but artifacts remain
- **User Feedback**: 
  - "The tone is clear"
  - "But there are artifacts, like buffering or something"
  - Tone continued generating correctly
  
### 3. Integration Tests
- **Result**: ✅ PASS - All 5 tests passing
- **Details**: No allocation regressions, router functionality intact

### 4. Subjective Audio Quality
- **Pre-fix**: "Gritty" artifacts throughout
- **Post-fix**: "Clearer" tone but "buffering" artifacts persist

## Analysis of Remaining Issues

### Observed Symptoms
1. Tone is clearer than before (deadline scheduling helped)
2. Artifacts described as "buffering" sounds
3. Pure sine wave still not completely clean
4. Artifacts present even with static parameters (no freq/gain changes)

### Likely Root Causes (In Order of Probability)

#### 1. Buffer Underruns Still Occurring
Despite deadline scheduling, the worker might still miss deadlines occasionally:
- Sleep granularity issues (1ms max sleep vs 5.33ms buffer period)
- Command processing taking too long occasionally
- GC or other system interrupts

#### 2. Ring Buffer Synchronization Issues
The audio ring might have read/write pointer conflicts:
- Writer (worker) and reader (audio callback) timing mismatch
- Ring buffer size might be too small for current latency
- Potential for reading partially written buffers

#### 3. Phase Discontinuities in SimpleSine
The oscillator might have subtle phase issues:
- Phase wrapping at line 107-108 uses modulo which could cause jumps
- Float32 precision issues accumulating over time
- Buffer boundary phase calculations might not be perfectly continuous

#### 4. Sample Rate Mismatch
Possible mismatch between:
- Worker production rate (based on SAMPLE_RATE constant)
- Actual audio device sample rate
- Could cause periodic buffer repeats or drops

## Recommendations for Senior Dev

### Immediate Diagnostics Needed

1. **Add buffer production metrics**:
```python
# In worker loop, track actual vs expected timing
actual_period = current_time - last_buffer_time
if abs(actual_period - buffer_period) > 0.001:
    print(f"Timing drift: expected {buffer_period:.3f}ms, got {actual_period:.3f}ms")
```

2. **Monitor ring buffer state**:
- Check for buffer underruns in audio callback
- Log when ring.write() returns False (buffer full)
- Track none-reads percentage

3. **Verify sample rate**:
- Confirm audio device is actually at 48000Hz
- Check if PulseAudio is resampling

### Potential Fixes to Consider

1. **More aggressive deadline scheduling**:
```python
# Process buffer earlier (2-3ms early instead of 1ms)
if current_time >= next_buffer_time - 0.003:
```

2. **Continuous phase tracking in SimpleSine**:
```python
# Use fmod instead of modulo for smoother wrapping
self._phase = math.fmod(self._phase, self._two_pi)
```

3. **Increase ring buffer size**:
- Current size might be too tight for router mode overhead
- Try doubling buffer count in ring

4. **Pre-compute multiple buffers**:
- Generate 2-3 buffers ahead during idle time
- Trade memory for timing resilience

## Conclusion

The deadline scheduling implementation is correct and follows Senior Dev's specification exactly. It provided partial improvement (clearer tone) but didn't eliminate all artifacts. The "buffering" description suggests the issue is now intermittent timing misses rather than consistent free-running chaos.

**Next Steps**:
1. Add detailed timing metrics to identify exact miss patterns
2. Check ring buffer health and audio callback statistics  
3. Consider more aggressive scheduling or buffer pre-computation
4. Investigate SimpleSine phase continuity

The surgical fix was correctly applied, but additional issues remain that need deeper investigation.

---
*Report prepared for Senior Dev review*  
*Deadline scheduling implemented, artifacts reduced but not eliminated*