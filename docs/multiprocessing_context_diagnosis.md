# Multiprocessing Context Mismatch Diagnosis

**Date**: 2025-01-02  
**Issue**: RuntimeError - SemLock fork/spawn context mismatch  
**Severity**: Critical - Prevents supervisor from starting

## Error Message
```
RuntimeError: A SemLock created in a fork context is being shared with a process in a spawn context. 
This is not supported. Please use the same context to create multiprocessing objects and Process.
```

## Timeline of Changes

### What Was Working
- Original supervisor.py and supervisor_v2_slots_fixed.py were functioning
- These used AudioRing and CommandRing classes with multiprocessing primitives
- The system successfully created workers and processed audio

### What We Changed (Phase 3)
1. **Created supervisor_v3_router.py** extending v2 architecture
2. **Added PatchRouter** for DAG-based module routing
3. **Modified ModuleHost** to support router mode
4. **Key Change**: Used explicit spawn context in v3: `self.ctx = mp.get_context('spawn')`

## Root Cause Analysis

### The Problem
1. **AudioRing and CommandRing** (defined in supervisor.py) use raw multiprocessing primitives:
   ```python
   self.head = mp.Value('i', 0, lock=False)  # Uses default context
   self.data = mp.Array('f', num_buffers * BUFFER_SIZE, lock=False)  # Uses default context
   ```

2. **supervisor_v3_router.py** explicitly uses spawn context:
   ```python
   self.ctx = mp.get_context('spawn')
   self.workers[0] = self.ctx.Process(...)  # Process created with spawn
   ```

3. **The Conflict**: When v3 imports AudioRing/CommandRing from v2, those objects were created with the default (fork) context, but v3 tries to pass them to processes created with spawn context.

### Why This Matters
- **Fork context**: Default on Linux, copies memory at fork time
- **Spawn context**: Starts fresh interpreter, pickles objects to send
- **SemLock**: Internal synchronization primitive in mp.Value/mp.Array
- **Incompatibility**: SemLocks created in fork context can't be pickled for spawn context

## Hypothesis

The multiprocessing context mismatch occurs because:
1. AudioRing/CommandRing create their mp.Value/mp.Array with default (fork) context
2. supervisor_v3 uses explicit spawn context for process creation
3. When spawn tries to pickle the rings to send to worker process, it encounters SemLocks created in fork context
4. Python's multiprocessing refuses to allow this cross-context sharing

## Why V2 Worked But V3 Doesn't

**supervisor_v2_slots_fixed.py**:
- Never explicitly set a context
- Everything used default (fork) context
- All objects and processes in same context = no conflict

**supervisor_v3_router.py**:
- Explicitly uses `mp.get_context('spawn')`
- Imports rings from v2 (created with default/fork)
- Mixed contexts = conflict

## Solutions

### Option A: Use Same Context Throughout (Recommended)
Make AudioRing and CommandRing accept a context parameter:
```python
class AudioRing:
    def __init__(self, num_buffers=NUM_BUFFERS, ctx=None):
        if ctx is None:
            ctx = mp.get_context()
        self.head = ctx.Value('i', 0, lock=False)
        self.data = ctx.Array('f', num_buffers * BUFFER_SIZE, lock=False)
```

Then in v3:
```python
self.ctx = mp.get_context('spawn')
self.slot0_audio_ring = AudioRing(ctx=self.ctx)
```

### Option B: Remove Explicit Context in V3
Remove the explicit spawn context and use default:
```python
# Instead of: self.ctx = mp.get_context('spawn')
# Just use default mp.Process
```
**Downside**: Less control, platform-dependent behavior

### Option C: Create V3-Specific Ring Classes
Copy AudioRing/CommandRing into v3 and modify to use spawn context.
**Downside**: Code duplication

## Immediate Fix for Testing

The quickest fix for testing is Option B - remove explicit spawn context:

In supervisor_v3_router.py, change:
```python
# From:
self.ctx = mp.get_context('spawn')
# To:
self.ctx = mp  # Use default context
```

## Long-term Recommendation

Implement Option A - make ring classes context-aware. This provides:
- Flexibility to choose context
- Consistency across all components
- Future-proof for different platforms

## Additional Notes

1. **Why spawn was used**: Spawn is more portable (works on Windows) and avoids fork issues with threads
2. **Fork safety**: Fork can be problematic with threads, numpy, and certain libraries
3. **Performance**: Fork is faster (copy-on-write) but spawn is safer

## Testing Impact

This issue prevents any audio testing until resolved. Once fixed:
- All existing tests should still pass
- Audio processing should work as before
- Router functionality will be available

## File Locations

- **Error source**: supervisor_v3_router.py:189-208
- **Ring definitions**: supervisor.py:119+, supervisor_v2_slots_fixed.py:50+
- **Context usage**: supervisor_v3_router.py:155

---

*Diagnosis prepared for Senior Dev review*