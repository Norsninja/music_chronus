# Slot-Based Failover Architecture

## Overview

The Music Chronus synthesizer implements a dual-slot architecture that provides fault tolerance with <50ms audio interruption. This design ensures continuous music production even when synthesis workers crash or become unresponsive.

## Architecture Rationale

### Why Slots, Not Dynamic Workers?

Early implementations attempted to dynamically swap worker references during failover. This failed because:

1. **Worker-Ring Binding**: Workers hold ring buffer references from spawn time via multiprocessing's pickle mechanism
2. **Reference Immutability**: You cannot change these references after the process has started
3. **Synchronization Complexity**: Trying to coordinate dynamic worker assignment added race conditions

The solution: **Fixed slots with movable workers**

```
Slots (Fixed Infrastructure):
- Slot 0: Primary position with dedicated rings
- Slot 1: Standby position with dedicated rings

Workers (Transient):
- Can fail and be replaced
- Spawn into specific slots
- Bound to slot's rings at spawn time
```

## Switch Flow

### Normal Operation
```
1. Audio callback reads from active slot (e.g., Slot 0)
2. Primary worker processes audio into Slot 0's ring
3. Standby worker processes audio into Slot 1's ring
4. Only active slot's audio reaches speakers
```

### Failover Sequence
```
1. Monitor detects worker failure (heartbeat timeout)
2. Set pending_switch flag
3. Audio callback sees flag and switches active_idx
4. Start using standby slot's audio immediately
5. Spawn replacement worker in failed slot (deferred cleanup)
6. New worker becomes next standby
```

### Command Broadcast Window

During the switch transition (~50ms), commands are broadcast to both slots:

```python
def send_command(self, op, module_id, param_id, value):
    if self.pending_switch:
        # Broadcast to both during transition
        self.slot0_cmd_ring.write(cmd_bytes)
        self.slot1_cmd_ring.write(cmd_bytes)
    else:
        # Normal routing to active slot
        if self.active_idx == 0:
            self.slot0_cmd_ring.write(cmd_bytes)
        else:
            self.slot1_cmd_ring.write(cmd_bytes)
```

This ensures:
- No commands are lost during failover
- Both slots remain synchronized
- Smooth transition when switching

## Per-Process View Rebinding

A critical discovery: NumPy views created in the parent process become stale after fork/spawn.

### The Problem
```python
# Parent process creates shared memory and view
self.data = mp.Array('f', size)
self.np_view = np.frombuffer(self.data)  # Works in parent

# After fork/spawn to child process:
# self.np_view is stale! It doesn't point to shared memory anymore
```

### The Solution
```python
def _ensure_views(self):
    """Rebind numpy views if in a different process"""
    if self._pid != os.getpid():
        # We're in a new process - rebind views
        self._np_data = np.frombuffer(
            self.data, 
            dtype=np.float32
        ).reshape(self.num_buffers, self.buffer_size)
        
        self._buffers = [
            self._np_data[i] 
            for i in range(self.num_buffers)
        ]
        
        self._pid = os.getpid()
```

This pattern ensures:
- Views are valid in each process
- Zero-copy semantics maintained
- Shared memory actually shared

## Deferred Cleanup

Failed workers are not immediately cleaned up. Instead:

1. **Immediate**: Switch audio to standby
2. **Deferred**: After switch completes, clean up failed worker
3. **Background**: Spawn replacement in failed slot

This two-phase approach ensures audio continuity takes priority over process management.

## Last-Good Fallback

The audio callback maintains a `last_good` buffer for each slot:

```python
def audio_callback(self, outdata, frames, time, status):
    # Try to get fresh audio
    buffer_view = ring.read_latest()
    
    if buffer_view is not None:
        # Update last_good with fresh audio
        np.copyto(self.last_good[idx], buffer_view)
    
    # Always output last_good (fresh or cached)
    outdata[:, 0] = self.last_good[idx][:frames]
```

Benefits:
- No silence during ring buffer gaps
- Smooth audio during failover transition
- Natural decay if worker dies mid-note

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Failover detection | ~50ms | Heartbeat timeout |
| Audio switch | <1ms | Index change only |
| Command broadcast | ~1ms | Dual ring writes |
| Worker respawn | ~100ms | Background operation |
| Audio interruption | <50ms | Brief glitch only |

## Key Insights

1. **Rings are infrastructure**: They belong to slots, not workers
2. **Workers are replaceable**: They can fail without destroying infrastructure  
3. **Sequential reading critical**: Must advance tail by one, not jump to head
4. **Views need rebinding**: Per-process rebinding required for shared memory
5. **Deferred cleanup**: Audio continuity before process management

## Testing Failover

```bash
# Terminal 1: Start synthesizer with verbose output
export CHRONUS_VERBOSE=1
python -m src.music_chronus.supervisor_v2_slots_fixed --verbose

# Terminal 2: Send test tone
python -c "from pythonosc import udp_client; c = udp_client.SimpleUDPClient('127.0.0.1', 5005); c.send_message('/test', [])"

# Terminal 3: Kill primary worker to trigger failover
ps aux | grep multiprocessing | grep -v grep
kill -9 <worker_pid>

# Observe: <50ms glitch, then audio continues
```

## Future Enhancements

- **Triple-slot architecture**: Two standbys for cascading failures
- **Predictive failover**: Switch before failure based on performance degradation
- **State synchronization**: Periodic state snapshots between slots
- **Hot-reload modules**: Update DSP code without stopping audio

---

*The slot-based architecture represents a fundamental insight: separate infrastructure from computation. Rings and slots are permanent; workers are ephemeral.*