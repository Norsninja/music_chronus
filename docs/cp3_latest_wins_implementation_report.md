# CP3 Latest-Wins Implementation Report

**Date**: 2025-09-02  
**Author**: Chronus Nexus  
**Status**: Implemented as instructed, severe audio regression observed

## Executive Summary

Implemented Senior Dev's instructions for latest-wins reading and ring integrity. Prime mechanism continues to work correctly. However, **severe audio quality regression** observed - returning to known "mosquito sounds" and "engine noise" artifacts. The implementation exposed a critical issue with the `read_latest_drop()` approach.

## What Was Implemented

### ✅ 1. Device Timing and Config Alignment
```
[CONFIG] Requested: SR=44100Hz, BS=256, NB=16
[DEVICE] Actual: SR=44100.0Hz, BS=256, Device=default
```
- Added device info logging at startup
- Confirmed no sample rate or blocksize mismatch
- Added environment variable support for NUM_BUFFERS
- Tested with both NB=8 and NB=16

### ✅ 2. Ring Integrity Instrumentation
Added to AudioRing class:
- Sequence numbers array: `mp.Array('Q', num_buffers)`
- Sequence counter incremented on each write
- `get_stats()` method returning occupancy and last sequence
- Periodic logging in audio callback: `[STATS] occ={occupancy}, seq={last_seq}, none={%}`

### ✅ 3. Latest-Wins Read Implementation
Implemented `read_latest_drop()` in AudioRing:
```python
def read_latest_drop(self):
    if self.head.value == self.tail.value:
        return None
    
    # Get latest buffer (one before head)
    latest_idx = (self.head.value - 1 + self.num_buffers) % self.num_buffers
    
    # Drop backlog by jumping tail to head
    self.tail.value = self.head.value  # <-- PROBLEM: Empties entire ring!
    
    return self._buffers[latest_idx]
```

### ✅ 4. SimpleSine Reverted to Allocation-Free
- Reverted to float32 phase index
- No `.astype()` calls (no allocations)
- In-place operations throughout
- Wrap at 2π instead of 1000×2π

### ✅ 5. Rate-Limited Scheduler Verified
Worker logs confirm:
- Producing 1-2 buffers per cycle
- `late=194` cycles show catch-up behavior
- `occ=2` target briefly achieved
- Period jitter: `period_us≈26198` then `period_us≈8754`

## Test Results

### Configuration Tests

#### Test 1: NUM_BUFFERS=8 (default)
```
[STATS] occ=1, seq=391, none=70.7%
[STATS] occ=0, seq=0, none=68.1%  <-- After switch, ring empty!
[STATS] occ=0, seq=0, none=67.0%
```

#### Test 2: NUM_BUFFERS=16
```
[STATS] occ=0, seq=0, none=69.8%
[STATS] occ=0, seq=0, none=67.2%
[STATS] occ=0, seq=0, none=65.1%
```

### Worker Production Confirmed
```
[WORKER 1] Buffer 10: Audio generated! RMS=0.1399, occ=1
[WORKER 1] Buffer 20: Audio generated! RMS=0.1401, occ=1
[WORKER 1] Buffer 30: Audio generated! RMS=0.1407, occ=1
[WORKER 1] Buffer 40: Audio generated! RMS=0.1414, occ=0  <-- Ring drained!
```

Worker IS producing audio (RMS ~0.14), but ring keeps getting emptied.

## Critical Problem Identified

### The Issue with `read_latest_drop()`

The implementation sets `tail.value = self.head.value`, which **completely empties the ring** on every read. This causes:

1. **Constant underruns**: Ring occupancy drops to 0 immediately
2. **None-reads ~70%**: Most callbacks find empty ring
3. **Audio artifacts**: Playing stale `last_good` buffer repeatedly
4. **"Mosquito/engine" sounds**: Classic symptom of buffer starvation

### Timing Analysis

The callback runs at ~172Hz (44100/256):
- Every ~5.8ms the callback reads
- Sets tail = head (empties ring)
- Producer adds 1-2 buffers
- Next callback finds 0-2 buffers
- Drains them again

This creates a pattern where we're mostly playing the same stale buffer.

### Why Latest-Wins Failed

Senior Dev's instruction "drop backlog" was interpreted as "set tail = head", but this is too aggressive:

**What Senior Dev likely meant:**
- Skip old buffers to get freshest
- Keep ring operational
- Maintain some occupancy

**What was implemented:**
- Empty entire ring on each read
- Destroy all buffering
- Create constant underrun condition

## Observed Audio Quality

**Regression to known issues:**
- "Mosquito sounds" - high-frequency artifacts
- "Engine noise" - repetitive drone
- Gritty, harsh quality
- Worse than before latest-wins

## Metrics Summary

| Metric | Before Latest-Wins | After Latest-Wins |
|--------|-------------------|-------------------|
| None-reads | ~37% | ~70% |
| Ring occupancy | 1-2 | 0-1 |
| Sequence continuity | Monotonic | Resets to 0 |
| Audio quality | Gritty | Severe artifacts |
| Prime mechanism | Working | Still working |

## Critical Questions for Senior Dev

1. **Latest-Wins Clarification**: Should we advance tail to `head-1` instead of `head`? This would read the latest buffer but keep future buffers.

2. **Ring Semantics**: Is the goal to:
   - Skip stale buffers but maintain buffering?
   - Or truly operate with no buffering (direct handoff)?

3. **Alternative Approach**: Should we instead:
   - Read the newest available buffer
   - Advance tail by (occupancy - 1) to keep one buffer?
   - Or use a different strategy entirely?

4. **Buffer Starvation**: With ~70% none-reads, we're clearly starving. Should we:
   - Increase lead target to 3-4?
   - Produce more aggressively?
   - Or fix the read strategy first?

## Proposed Fix (Awaiting Approval)

Instead of `tail = head`, consider:
```python
def read_latest_drop(self):
    if self.head.value == self.tail.value:
        return None
    
    # Calculate occupancy
    occ = (self.head.value - self.tail.value + self.num_buffers) % self.num_buffers
    
    if occ > 1:
        # Skip old buffers, keep the newest
        self.tail.value = (self.head.value - 1 + self.num_buffers) % self.num_buffers
    
    # Read and advance normally
    idx = self.tail.value
    self.tail.value = (self.tail.value + 1) % self.num_buffers
    return self._buffers[idx]
```

This would skip stale buffers when behind, but maintain normal operation otherwise.

## Files Modified

1. `/src/music_chronus/supervisor_v2_slots_fixed.py`:
   - Added sequence numbers to AudioRing
   - Implemented `read_latest_drop()` 
   - Added `get_stats()` method
   - Added NUM_BUFFERS env var support

2. `/src/music_chronus/supervisor_v3_router.py`:
   - Added device config logging
   - Changed to `read_latest_drop()` in callback
   - Added periodic stats logging

3. `/src/music_chronus/modules/simple_sine.py`:
   - Reverted to allocation-free float32

## Recommendation

**DO NOT use current `read_latest_drop()` implementation** - it destroys ring buffer semantics and causes severe audio artifacts. Need Senior Dev's clarification on the intended behavior before proceeding.

The prime mechanism works perfectly. The issue is purely in the ring buffer read strategy.

---
*Report prepared for Senior Dev review*  
*Implementation complete but causing severe regression*  
*Awaiting clarification on latest-wins semantics*