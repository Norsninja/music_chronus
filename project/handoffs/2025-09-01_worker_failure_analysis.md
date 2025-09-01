# Worker Failure Analysis - Supervisor v2 Final

**Date**: 2025-09-01  
**Issue**: Workers dying immediately in supervisor_v2_final.py  
**Status**: CRITICAL - Multiple attempts failed  

## Symptoms

1. **Continuous worker respawning**
   - Standby worker dies within 50ms (heartbeat timeout)
   - New standby spawned immediately
   - Cycle repeats endlessly

2. **Active index wrong**
   - Shows `idx=1` (standby active) instead of `idx=0` (primary active)
   - This suggests primary never started or died immediately

3. **No audio production**
   - `none_reads=500` means no buffers being written
   - RMS=0.000000 confirms silence

## What We Know Works

- `supervisor_v2_surgical.py` runs correctly with `idx=0`
- Both primary and standby workers stay alive in original
- Audio is produced (though failover doesn't work due to premature ring reset)

## What's Different in supervisor_v2_final.py

### 1. Deferred Cleanup Logic
- Added `post_switch_cleanup_pending` flag
- Added `failed_worker_idx` tracking
- Modified `handle_primary_failure()` to not reset rings immediately
- Added `perform_post_switch_cleanup()` method

### 2. Command Broadcasting
- Modified `send_command()` to broadcast during switch
- This shouldn't affect initial startup

### 3. Worker Process Changes
- Changed from manual command unpacking to `host.queue_command()`
- This was to match the original, should be correct

### 4. Initial State
- Both start with `active_idx = 0`
- Both spawn primary then standby
- Something causes immediate switch to standby (idx=1)

## Hypothesis

The workers are crashing immediately on startup, possibly due to:

1. **Import/Module issue** - But imports tested OK
2. **Initialization issue** - Something in worker_process setup
3. **Signal handling issue** - Workers might be receiving SIGTERM immediately
4. **Multiprocessing issue** - Something with how processes are spawned
5. **The deferred cleanup logic** - Maybe triggering incorrectly at startup

## Critical Observation

The diagnostic shows `idx=1` which means:
- Either primary died and we switched to standby
- OR active_idx was incorrectly set to 1 somehow

Since we see continuous "Standby worker hung" messages, it seems like:
1. Primary starts but dies/hangs immediately
2. System switches to standby (idx=1)
3. Standby also dies/hangs
4. System tries to spawn new standby
5. Repeat forever

## Research Needed

1. **Why is primary dying immediately?**
   - Add debug print at start of worker_process
   - Check if worker even starts
   - Log any exceptions

2. **Why does active_idx become 1?**
   - Check if `pending_switch` is somehow set at startup
   - Check if primary failure is detected incorrectly

3. **What's different between working and failing versions?**
   - Line-by-line comparison needed
   - Focus on initialization and worker startup

## Next Steps Recommendation

### Option A: Minimal Debug
Add debug prints to supervisor_v2_final.py:
1. At start of worker_process - "Worker X starting"
2. In monitor when detecting failure - "Detected worker X failure"
3. When switching active_idx - "Switching from X to Y"

### Option B: Incremental Fix
Start from supervisor_v2_surgical.py and add ONLY the deferred cleanup:
1. Keep everything else identical
2. Add only the post_switch_cleanup logic
3. Test each change incrementally

### Option C: Use Simpler Approach
Instead of complex deferred cleanup:
1. Just delay the ring reset by 100ms
2. Or use a lock to prevent concurrent access
3. Or use a different failover mechanism

## Questions for Investigation

1. Does worker_process even start executing?
2. Is the heartbeat array being updated at all?
3. Is there a race condition at startup?
4. Is the monitor thread detecting false failures?

## Personal Assessment

I've been making changes without fully understanding the system. The repeated failures suggest a fundamental issue with how I modified the initialization or monitoring logic. The fact that active_idx is 1 is the key clue - something is causing an immediate failover at startup.

I should have:
1. Added extensive logging first
2. Made smaller, incremental changes
3. Tested each change individually
4. Better understood the worker lifecycle

## Recommendation

**STOP making blind changes**. We need to:
1. Add diagnostic logging to understand what's happening
2. Run with verbose output to see the exact failure sequence
3. Compare line-by-line with working version
4. Consider reverting to a simpler fix approach

The Senior Dev's analysis was correct about the ring reset issue, but my implementation has introduced new bugs that are worse than the original problem.

---
*Analysis prepared after multiple failed attempts*