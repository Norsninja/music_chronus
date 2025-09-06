# Windows Port Audio Investigation - Technical Findings

**Date**: 2024-12-18
**Issue**: Periodic clicking/popping every buffer boundary
**Status**: Root cause identified, solution pending

## Problem Statement

Audio output has periodic clicking/popping every 10.7ms (buffer boundary) on both Windows and WSL versions. Clicking persists regardless of audio content or parameter changes.

## Investigation Timeline

### Phase 1: ADSR Investigation (INCORRECT HYPOTHESIS)
**Hypothesis**: ADSR envelope transitions cause discontinuities

**Tests Performed**:
- Created 3 ADSR implementations (v2_minimal, analog, rc)
- Tested with gate held constant (no transitions)
- Result: Clicking persisted with gate ON

**Conclusion**: ADSR is NOT the cause

### Phase 2: SimpleSine Investigation (INCORRECT HYPOTHESIS)
**Hypothesis**: Phase discontinuity at buffer boundaries

**Analysis**:
- Reviewed phase accumulation math
- Checked float32 precision impact
- Verified modulo wrapping

**Senior Dev Correction**: SimpleSine math is correct and continuous

**Conclusion**: SimpleSine is NOT the cause

### Phase 3: Ring Buffer Analysis (CORRECT DIAGNOSIS)
**Hypothesis**: Worker process can't keep up with audio callback

**Evidence**:
```
Performance Metrics:
Callbacks: 7023
Buffers Processed: 4808
Deficit: 2215 buffers (31.5%)

Production Rate:
Expected: 93.75 buffers/sec (48kHz/512 samples)
Actual: ~64 buffers/sec
Deficit: 31.5% consistently
```

**Conclusion**: Worker produces only 68% of needed buffers

## Root Cause Analysis

### The Buffer Production Deficit

The worker process cannot produce buffers fast enough:
- **Required rate**: 1 buffer per 10.67ms
- **Actual rate**: 1 buffer per ~15.6ms
- **Result**: Audio callback reuses old buffers, creating discontinuities

### Why The Worker Is Slow

1. **Loop Structure Problem** (Partially Fixed):
   - Original: Check buffer deadline AFTER commands/events
   - Fixed: Check buffer deadline FIRST
   - Result: Minimal improvement (31.5% → 31% deficit)

2. **Python Overhead**:
   - Function calls, loop overhead
   - Process communication overhead
   - GIL effects even with multiprocessing

3. **Buffer Size Too Small**:
   - 512 samples = 10.67ms deadline
   - Overhead becomes significant percentage
   - No room for timing variations

## Testing Methodology

### What Worked
```python
# Diagnostic test that revealed the issue:
client.send_message("/gate", 1.0)  # Hold gate ON
# Listen for clicks with NO parameter changes
# Monitor supervisor metrics for deficit growth
```

### What Didn't Work
- Testing modules in isolation (bug only appears in full system)
- Focusing on DSP math (wasn't the problem)
- Using `/module/` OSC patterns (not implemented)

## Critical Discoveries

### 1. OSC Handler Gap
```python
# In supervisor_windows.py:
disp.map("/mod/*/*", self.handle_mod_param)  # Just 'pass' - NOT IMPLEMENTED!
```
Test scripts used wrong pattern, causing initial confusion.

### 2. Metrics Tell The Story
The deficit was visible from the start but we didn't recognize its significance:
```
Callbacks >> Buffers Processed = Clicking
```

### 3. Worker Timing Fix Insufficient
Even after prioritizing buffer production, the fundamental speed issue remains.

## Solutions

### Option 1: Increase Buffer Size (RECOMMENDED)
```python
# In .env.windows:
BUFFER_SIZE=1024  # Was 512

# Effect:
# Period: 21.3ms instead of 10.7ms
# Worker has 2x time to produce buffers
# Should eliminate deficit
```

### Option 2: Optimize Worker
- Remove command processing from audio loop
- Use C extension for buffer production
- Implement proper prefill

### Option 3: Accept Higher Latency
- Use 2048 sample buffers
- 42.7ms latency but guaranteed no clicks
- Suitable for non-realtime applications

## Performance Analysis

### Current State
```
Buffer period: 10.67ms
Worker production time: ~15.6ms
Result: 31.5% deficit, periodic clicks
```

### With 1024 Buffer Size
```
Buffer period: 21.3ms
Worker production time: ~15.6ms (same)
Result: Should achieve >95% production rate
```

## Lessons Learned

1. **Metrics First**: Buffer deficit was the smoking gun from the beginning
2. **Test in Context**: Isolated module tests missed the system-level issue
3. **Question Assumptions**: We assumed DSP problem, was actually scheduling
4. **Senior Dev Wisdom**: Their ring buffer starvation theory was correct
5. **Python Limits**: 10ms is aggressive for Python multiprocessing

## Implementation Status

### Completed
- ✅ Identified root cause (buffer production deficit)
- ✅ Fixed worker loop priority (minimal improvement)
- ✅ Documented OSC handler gaps
- ✅ Created comprehensive test suite

### Pending
- ❌ Increase buffer size to 1024
- ❌ Implement `/mod/*/*` handlers
- ❌ Add buffer prefill
- ❌ Verify clicking elimination

## Files Modified

### Key Changes
- `supervisor_windows.py`: Reordered worker loop, added catch-up
- Created multiple ADSR implementations (all work, none fix clicking)
- Created diagnostic test scripts

### Files to Update
- `.env.windows`: Change BUFFER_SIZE to 1024
- `supervisor_windows.py`: Implement `/mod/*/*` handlers

## Success Criteria

```python
# Metrics showing success:
deficit = (callbacks - buffers_processed) / callbacks
assert deficit < 0.01  # Less than 1% deficit

# Audio validation:
# No periodic clicking at buffer rate
# Clean sine tones with gate held ON
```

## Next Steps

1. **Immediate**: Change BUFFER_SIZE to 1024 in config
2. **Test**: Verify deficit disappears and clicking stops
3. **Optimize**: If needed, implement prefill and better catch-up
4. **Complete**: Fix OSC handlers for full compatibility

---

*Technical investigation complete. Solution identified and ready to implement.*