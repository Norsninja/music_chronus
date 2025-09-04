# Sequencer Timing Implementation Issue Report

**Date**: 2025-09-03  
**Reporter**: Chronus Nexus  
**Issue**: Emergency fill cascade after implementing epoch-based sequencer timing

## Critical Issue

After implementing the Senior Dev's epoch-based timing fix for the sequencer, the server experiences continuous emergency fills, indicating the audio callback is starving for buffers. This occurs even with the sequencer thread disabled.

## Symptoms

```
[WORKER 0] EMERGENCY FILL: occ=0, producing one buffer immediately
[WORKER 0] Emergency fill complete: RMS=0.0000, new occ=1
[WORKER 0] Buffer 200: Silent buffer (RMS=0.000000), occ=1
[WORKER 0] EMERGENCY FILL: occ=0, producing one buffer immediately
```

This repeats continuously, flooding the console and indicating severe timing problems.

## Changes Made (In Order)

### 1. Initial Epoch-Based Timing Implementation
**File**: `/home/norsninja/music_chronus/src/music_chronus/sequencer.py`  
**Lines**: 323-406 (run() method completely replaced)

Changed from delta-accumulation approach to epoch-based:
- Replaced countdown `buffers_until_next_step` with absolute `next_step_buffer`
- Added `global_next_buffer` monotonic counter from epoch
- Implemented while-loop catch-up mechanism per Senior Dev spec
- Added `gate_off_buffer` absolute timing for gate releases

Key implementation:
```python
def run(self):
    self.epoch_time = time.perf_counter()
    self.global_next_buffer = 0
    
    while self.running:
        now = time.perf_counter()
        current_buffer = int((now - self.epoch_time) / self.buffer_period)
        
        while self.global_next_buffer <= current_buffer:
            # Process sequencers at exact buffer boundaries
            for seq in self.sequencers.values():
                if self.global_next_buffer == seq.next_step_buffer:
                    # Emit events
                    seq.next_step_buffer += seq.buffers_per_step
            self.global_next_buffer += 1
```

### 2. Fixed Dynamic Sequencer Creation
**File**: `/home/norsninja/music_chronus/src/music_chronus/sequencer.py`  
**Lines**: 159-177 (create_sequencer method)

Added initialization of timing attributes when sequencers created after thread start:
```python
seq.next_step_buffer = getattr(self, 'global_next_buffer', 0)
seq.gate_off_buffer = None
seq.buffers_per_step = seq.calculate_buffers_per_step(self.buffer_period)
seq.pending_config = None
```

### 3. Updated BPM Change to Use Pending Config
**File**: `/home/norsninja/music_chronus/src/music_chronus/sequencer.py`  
**Lines**: 233-239

Changed BPM updates to queue for boundary application:
```python
if seq.pending_config is None:
    seq.pending_config = {}
seq.pending_config['bpm'] = data
```

### 4. Added Safety Limits to Prevent Runaway
**File**: `/home/norsninja/music_chronus/src/music_chronus/sequencer.py`  
**Lines**: 374-439

Added catch-up limit to prevent infinite loops:
```python
max_catchup = 100
catchup_count = 0

while self.global_next_buffer <= current_buffer and catchup_count < max_catchup:
    # Process events
    catchup_count += 1

if catchup_count >= max_catchup:
    self.global_next_buffer = current_buffer + 1  # Jump ahead
```

### 5. Added Minimum Sleep to Prevent CPU Spinning
**File**: `/home/norsninja/music_chronus/src/music_chronus/sequencer.py`  
**Lines**: 441-446

Changed sleep calculation to always sleep at least 1ms:
```python
sleep_time = max(0.001, min(time_to_next, self.buffer_period * 0.5))
time.sleep(sleep_time)  # Always sleep
```

### 6. Disabled Sequencer Thread (Debugging)
**File**: `/home/norsninja/music_chronus/src/music_chronus/supervisor_v3_router.py`  
**Lines**: 1042-1044

Commented out sequencer thread start:
```python
# TEMPORARILY DISABLED: Debugging emergency fill issue
# self.sequencer_manager.start()
```

## Investigation Results

1. **Initial hypothesis**: Sequencer thread was blocking/spinning and preventing worker from producing buffers
   - **Result**: Disabling sequencer thread did NOT fix the issue
   - **Conclusion**: Problem is elsewhere in the system

2. **Current state**: Emergency fills occur even with sequencer disabled
   - This suggests the issue was introduced by changes to shared code
   - OR there's a regression in the worker/supervisor communication

## Possible Root Causes

1. **Import side effects**: The sequencer module import might have changed timing
2. **Shared memory corruption**: Command ring modifications might have issues  
3. **Worker startup timing**: Changes to initialization sequence
4. **GC or threading interaction**: Python GIL contention

## What Was Working Before

Before sequencer implementation:
- Zero emergency fills during normal operation
- Steady buffer production/consumption
- occ (occupancy) stayed at healthy levels (1-2)
- Clean patch commits and audio generation

## Recommended Investigation

1. **Diff check**: Compare current supervisor_v3_router.py with last known working version
2. **Import isolation**: Check if importing sequencer module causes side effects
3. **Buffer timing**: Verify buffer period calculations haven't changed
4. **Ring buffer state**: Check if CommandRing is being corrupted
5. **Worker process health**: Verify workers are actually processing buffers

## Files Modified

- `/home/norsninja/music_chronus/src/music_chronus/sequencer.py` - Extensive changes to run() method
- `/home/norsninja/music_chronus/src/music_chronus/supervisor_v3_router.py` - Added sequencer integration, currently disabled

## Rollback Option

To restore working state:
1. Comment out sequencer import and initialization in supervisor_v3_router.py
2. OR revert to commit before sequencer integration

## Senior Dev Action Items

1. Review epoch-based implementation for logic errors
2. Check if buffer timing math is correct
3. Investigate why emergency fills cascade even with sequencer disabled
4. Determine if issue is in sequencer code or integration
5. Consider if Python threading is appropriate for buffer-accurate timing

---
*Report prepared for Senior Dev review*  
*System is currently unusable due to emergency fill cascade*