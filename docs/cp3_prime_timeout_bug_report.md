# CP3 Prime Timeout Bug Report

**Date**: 2025-09-03  
**Author**: Chronus Nexus  
**Status**: Critical bug preventing patch switching

## Executive Summary

Testing revealed that the prime mechanism fails to signal readiness, causing all patch commits to timeout. The supervisor never switches to the new worker, resulting in audio from the wrong slot with popping artifacts. This is a critical bug that prevents the system from functioning.

## Test Configuration

- WSL2 with increased limits (10GB RAM)
- CHRONUS_BUFFER_SIZE=512
- CHRONUS_NUM_BUFFERS=32
- CHRONUS_ROUTER=1

## Observed Behavior

### 1. Prime Timeout Failure
```
[WORKER 1] Warmup 0: RMS=0.166747
[WORKER 1] Prime complete! Max RMS=0.1667
[WORKER 1] Prefilling ring with 4 buffers...
[WORKER 1] Prefill 4: RMS=0.1524
[OSC] WARNING: Prime timeout after 0.5s - NOT switching
```

Worker completes all priming steps but supervisor times out waiting for `prime_ready` signal.

### 2. Consequences
- Supervisor remains on old slot (no modules)
- Audio comes from stale buffers (popping artifacts)
- Occupancy stays at 0-1 (no active worker producing)
- Filter has no effect (wrong slot active)
- Pattern: intermittent popping with silence

### 3. Root Cause Analysis

Located in `supervisor_v3_router.py`:

**Line 254-255**: Worker checks and sets prime_ready
```python
if prime_ready:
    prime_ready.value = 1  # Signal supervisor
```

**Line 599**: Supervisor waits for signal
```python
if self.prime_ready[standby_idx].value == 1:
```

The `prime_ready` shared value is either:
- Not being passed correctly to worker
- None/undefined in worker context
- Not properly initialized

## Test Results Summary

### Buffer Size Testing
| Config | None-reads | Audio Quality | Notes |
|--------|------------|---------------|-------|
| 512/16 | 0.1% | Popping | Prime fails, wrong slot |
| 512/24 | 0.1% | Popping | Same issue |
| 512/32 | 0.1% | Popping | Same issue |
| 384/24 | 49.3% | Severe artifacts | System can't keep up |

### Key Finding
**512 samples is the practical minimum** for Python under WSL2. Even with increased RAM, 384 samples causes severe buffer starvation (49% none-reads).

## Critical Code Path

1. **Supervisor creates shared values** (line 341):
```python
self.prime_ready = [mp.Value('i', 0), mp.Value('i', 0)]
```

2. **Passed to worker** (line 403):
```python
prime_ready[slot_idx]  # Should be passed as parameter
```

3. **Worker receives it** (line 57):
```python
def worker_process(..., prime_ready, ...):
```

4. **Worker sets it** (line 255):
```python
prime_ready.value = 1  # This fails silently
```

## Recommended Fix

1. **Verify prime_ready is passed correctly** to worker_process
2. **Add debug logging** to confirm prime_ready is not None
3. **Check shared memory permissions** between processes
4. **Consider increasing timeout** from 0.5s as temporary workaround

## Impact

- **Severity**: CRITICAL - System non-functional
- **Affected**: All patch commits fail
- **Workaround**: None - requires code fix

## Additional Observations

### What Works
- OSC communication ✓
- Worker spawning ✓
- Module creation ✓
- Audio callback ✓
- Low none-reads at 512 samples ✓

### What Doesn't Work
- Prime signaling ✗
- Slot switching ✗
- Clean audio (due to wrong slot) ✗
- 384 sample buffers (49% none-reads) ✗

## Next Steps for Senior Dev

1. Fix prime_ready passing/initialization
2. Add diagnostic logging for shared value state
3. Test prime mechanism in isolation
4. Consider fallback if prime_ready not available
5. Document minimum buffer size requirement (512)

## Files to Review

- `/src/music_chronus/supervisor_v3_router.py`
  - Line 254-255: Worker prime signaling
  - Line 341: prime_ready initialization  
  - Line 403: Passing to worker
  - Line 599: Supervisor checking signal

---
*Report prepared for Senior Dev review*  
*System currently non-functional due to prime timeout bug*