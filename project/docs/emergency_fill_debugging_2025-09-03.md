# Emergency Fill Debugging Documentation

**Date**: 2025-09-03  
**Investigators**: Chronus Nexus & Mike  
**Issue**: Persistent emergency fills despite multiple fix attempts

## Executive Summary

Despite implementing Senior Dev's recommended fixes including catch-up override and rebuild mode, emergency fills continue to cascade. The system successfully rebuilds to target occupancy (3 buffers) but immediately drains to 0, suggesting a fundamental timing or consumption issue rather than a simple logic bug.

## Test Results Summary

### Test 1: Original Configuration
- **Settings**: `LEAD_TARGET=3, MAX_CATCHUP=3, EARLY_MARGIN_MS=3, KEEP_AFTER_READ=2, PREFILL=3`
- **Result**: Emergency fills cascading, 0→1→0 oscillation
- **Pattern**: Emergency → occ=1 → immediately emergency again
- **Analysis**: Single buffer produced, consumed immediately, no cushion built

### Test 2: With Catch-up Override (single use)
- **Code Change**: Added `emergency_filled` flag, cleared after one use
- **Location**: Lines 346, 377, 391-395 in supervisor_v3_router.py
- **Result**: Emergency → Catch-up override message → Still emergency fills
- **Pattern**: Override message prints but doesn't prevent next emergency
- **Analysis**: Override executes but insufficient to build cushion

### Test 3: With Rebuild Mode (multiple catch-ups)
- **Code Change**: Keep `emergency_filled` true until reaching lead_target
- **Location**: Lines 391-396, 433-439 in supervisor_v3_router.py
- **Result**: Successfully rebuilds to occ=3, then immediately drops to 0
- **Pattern**: Emergency → Rebuild to 3 → Emergency (cycle repeats)
- **Analysis**: Rebuild logic works perfectly, but ring drains between cycles

### Test 4: Increased Buffers & Margins
- **Settings**: `EARLY_MARGIN_MS=4, KEEP_AFTER_READ=3, PREFILL=5`
- **Code Change**: Made keep_after_read configurable (line 1075)
- **Result**: SAME ISSUE - rebuilds to 3, then emergency
- **Pattern**: Identical to Test 3 despite thicker cushion
- **Analysis**: Problem not related to cushion thickness

## Critical Observations

1. **Rebuild WORKS**: We successfully rebuild from 0→3 in one cycle
2. **Immediate Drain**: Ring drops from 3→0 between producer cycles
3. **Prefill Success**: Initial prefill of 5 buffers works (RMS values good: 0.11-0.17)
4. **Audio Quality**: Non-zero RMS confirms audio generation works
5. **Timing**: Issue occurs after ~10 buffers (Buffer 10 log message)

## Code Changes Made

### 1. Emergency Fill Flag (Lines 346, 377)
```python
emergency_filled = False  # Flag to allow catch-up after emergency fill
# ...
emergency_filled = True  # Set after successful emergency fill
```

### 2. Catch-up Override Logic (Lines 391-396)
```python
allow_immediate = emergency_filled and occ < lead_target and produced_this_cycle < max_catchup
if allow_immediate:
    time_gate = False  # Override time gate for catch-up
```

### 3. Rebuild Complete Detection (Lines 433-439)
```python
if emergency_filled:
    new_occ = ring_occupancy(audio_ring)
    if new_occ >= lead_target or produced_this_cycle >= max_catchup:
        emergency_filled = False
```

### 4. Configurable keep_after_read (Line 1075)
```python
keep_after_read = int(os.environ.get('CHRONUS_KEEP_AFTER_READ', '2'))
```

## Hypothesis Analysis

### ❌ Hypothesis 1: Callback Frequency Mismatch
- **Theory**: Callback called more frequently than expected
- **Evidence Against**: Buffer period calculation correct (512/44100 = 11.6ms)
- **Status**: Unlikely

### ❌ Hypothesis 2: Keep_after_read Logic Issue
- **Theory**: `read_latest_keep` draining too aggressively
- **Evidence Against**: Increasing to keep=3 didn't help
- **Status**: Disproven

### ⚠️ Hypothesis 3: Race Condition
- **Theory**: Multiple callbacks execute between producer cycles
- **Evidence For**: Ring drains from 3→0 instantly
- **Possibility**: Callback might be called in bursts under WSL2
- **Status**: Probable

### 🔍 Hypothesis 4: Wrong Ring Being Read
- **Theory**: Callback reading from wrong slot's ring
- **Check Needed**: Verify `active_idx` alignment with Worker 0
- **Status**: Needs investigation

### 🔍 Hypothesis 5: Buffer Size Mismatch
- **Theory**: Callback consuming more than 1 buffer per call
- **Check Needed**: Verify frames parameter matches BUFFER_SIZE
- **Status**: Needs investigation

### 🆕 Hypothesis 6: Burst Consumption Pattern
- **Theory**: WSL2 scheduling causes burst consumption
- **Evidence**: 3+ buffers consumed between producer cycles
- **Math**: 3 buffers × 11.6ms = 34.8ms window
- **Status**: Most likely explanation

## Technical Analysis

### Buffer Timing
- **Buffer Size**: 512 samples
- **Sample Rate**: 44100 Hz
- **Buffer Period**: 512/44100 = 11.61ms
- **Expected Callback Rate**: Every 11.61ms

### Ring Occupancy Pattern
```
Time    Event                           Occupancy
T+0     Prefill complete               5
T+116   Buffer 10 produced             2-3
T+117   Emergency fill triggered       0
T+118   Rebuild to 3                   3
T+230   Emergency fill again           0
```

### Producer Cycle Analysis
- Emergency fill: 1 buffer produced
- Catch-up: 2 additional buffers
- Total: 3 buffers in ~1ms (based on logs)
- Next cycle: occ=0 (all 3 consumed)

## Questions Requiring Investigation

1. **Producer Cycle Duration**: How long between production cycles including sleep?
2. **Callback Frequency**: Is callback actually periodic or bursty?
3. **Active Index**: Is `active_idx.value` correctly pointing to Worker 0?
4. **Frame Count**: Does `frames` parameter equal BUFFER_SIZE (512)?
5. **WSL2 Scheduling**: Are we hitting WSL2-specific timing issues?

## Next Debugging Steps

### Immediate Actions
1. Add cycle timing measurements to producer
2. Log callback invocation frequency
3. Verify active_idx alignment at emergency
4. Check frames parameter value
5. Measure actual time between emergencies

### Code Instrumentation Needed
```python
# In worker_process:
cycle_start = time.perf_counter()
# ... production logic ...
cycle_duration = time.perf_counter() - cycle_start
if cycle_duration > buffer_period * 2:
    print(f"[WARNING] Slow cycle: {cycle_duration*1000:.2f}ms")

# In audio_callback:
self.callback_times.append(time.perf_counter())
if len(self.callback_times) > 10:
    intervals = np.diff(self.callback_times[-10:])
    if np.std(intervals) > 0.002:  # 2ms variance
        print(f"[WARNING] Callback jitter: std={np.std(intervals)*1000:.2f}ms")
```

## Potential Solutions

### If Burst Consumption Confirmed:
1. **Increase Ring Size**: Use 32 buffers instead of 16
2. **Reduce Sleep Precision**: Less aggressive busy-wait
3. **Producer Anticipation**: Produce ahead of deadline
4. **Double Buffering**: Maintain 2x lead_target

### If WSL2 Scheduling Issue:
1. **Native Linux**: Test on bare metal Linux
2. **RT Priority**: Request real-time scheduling
3. **Larger Buffers**: Increase BUFFER_SIZE to 1024
4. **Callback Smoothing**: Average multiple buffers

## Conclusion

The emergency fill issue appears to be a timing/scheduling problem rather than a logic bug. The rebuild mechanism works correctly (achieving occ=3) but the ring drains completely between producer cycles, suggesting either:

1. The producer cycle takes too long (>35ms)
2. The callback consumes buffers in bursts
3. WSL2 introduces scheduling jitter

The next session should focus on timing measurements to identify the exact cause.

---
*Document prepared by Chronus Nexus*  
*Status: Issue persists, root cause narrowing to timing/scheduling*