# Phase 1C: Process Supervision Research Plan

**Date**: 2025-08-31
**Status**: Research Phase
**Goal**: Design robust process supervision for audio worker

## Research Topics

### 1. Manual Process Management (Not ProcessPoolExecutor)

**Why Manual**:
- ProcessPoolExecutor proven unsuitable for real-time (PROC-03)
- Need fine-grained control over worker lifecycle
- Custom sentinel monitoring required
- Hot-standby pattern not supported by stdlib

**Research Questions**:
- How to use multiprocessing.Process directly
- Best practices for process state tracking
- Clean shutdown vs SIGKILL handling
- Resource cleanup patterns

### 2. Sentinel Monitoring via connection.wait()

**Pattern**: Use Pipe/Connection to detect worker death
```python
parent_conn, child_conn = multiprocessing.Pipe()
# In supervisor: connection.wait() blocks until worker dies
# Death detection <10ms requirement
```

**Research Needed**:
- connection.wait() timeout behavior
- False positive detection (spurious wakeups)
- Multiple sentinel monitoring
- Integration with select/poll for multiple workers

### 3. Hot-Standby Failover Architecture

**Requirements**:
- Spare worker pre-warmed and ready
- Failover <10ms after death detection
- State transfer mechanism
- Shared memory handoff

**Research Topics**:
- Pre-warming strategy (imports done, waiting)
- State synchronization between primary/standby
- Atomic switchover mechanism
- Audio continuity during failover

### 4. SPSC Ring Buffer for Control Path

**Migration from direct OSC**:
- OSC thread writes to SPSC ring
- Worker reads from ring
- Socketpair for wakeup notification

**Research**:
- Python SPSC implementations (ringbuf library?)
- Integration with socketpair pattern (IPC-04)
- Memory ordering guarantees
- Overflow handling

### 5. SHM Registry Design

**Purpose**: Track all shared memory allocations
```json
{
  "allocations": [
    {
      "id": "audio_buffer_0",
      "size": 4096,
      "type": "ring_buffer",
      "owner": "worker_1",
      "created": "2025-08-31T10:00:00Z"
    }
  ],
  "stats": {
    "total_allocated": 16384,
    "active_count": 4,
    "leaked_count": 0
  }
}
```

**Research**:
- Atomic JSON updates
- Lock-free reading from workers
- Cleanup on worker death
- Leak detection patterns

### 6. Metrics Collection

**Required Metrics**:
- crash_count
- replacements
- spare_ready
- shm_leaks
- failover_time_ms
- rebuild_time_ms

**Research**:
- Lock-free metric collection
- Aggregation without blocking audio
- History/rolling windows
- Export format

## Quick Wins Before 1C

### 1. Add Amplitude Control
- `/engine/gain` OSC endpoint
- Same lock-free pattern as frequency
- Validates multi-parameter exchange
- ~50 lines of code

### 2. Enhanced Status CLI
- Show applied/received counts
- p95/p99 latency in samples (not just ms)
- CPU% already available
- Better formatting

## Key Patterns to Review

### From IPC-04 (Event Synchronization)
- Socketpair + shared memory pattern
- 84μs p50, 190μs p99 achieved
- Wake notification without polling
- Zero-copy data transfer

### From PROC-04 (Resource Cleanup)
- Zero leaks across 50 cycles achieved
- Fast cleanup patterns
- SIGKILL recovery
- FD and SHM tracking

## Architecture Questions

### Supervisor Responsibilities
1. Start/stop workers
2. Monitor health via sentinel
3. Manage hot-standby
4. Track SHM allocations
5. Collect metrics
6. Handle control routing

### Worker Responsibilities  
1. Run audio engine
2. Read from SPSC ring
3. Report health via sentinel
4. Register SHM usage
5. Clean shutdown on request

### Communication Flow
```
OSC Client
    ↓
OSC Thread (supervisor)
    ↓
SPSC Ring Buffer
    ↓ (socketpair wakeup)
Worker Process
    ↓
Audio Callback
    ↓
Audio Output
```

## Test Strategy for 1C

### Acceptance Tests
- Detect worker death p95 <10ms
- Failover completed <10ms
- Rebuild spare <500ms
- Zero SHM leaks (50 cycles)
- Zero underruns during 3 crashes

### Stress Scenarios
1. Kill worker during audio playback
2. Rapid kill/restart cycles
3. Memory pressure testing
4. Control message during failover
5. Concurrent failures

## Implementation Order

1. **Research Phase** (Current)
   - Understand all patterns
   - Review IPC-04, PROC-04 results
   - Design supervisor API

2. **Quick Wins**
   - Add amplitude control
   - Enhance status display
   - Validate multi-param exchange

3. **Core Supervisor**
   - Manual Process management
   - Sentinel monitoring
   - Basic failover (no standby yet)

4. **Hot-Standby**
   - Pre-warmed spare
   - Fast failover
   - State synchronization

5. **Full Integration**
   - SPSC ring buffer
   - SHM registry
   - Complete metrics

## Research Resources

- multiprocessing.Process docs
- connection.wait() behavior
- Python ringbuf library
- Our IPC-04 test results
- Our PROC-04 test results

## Success Criteria

Phase 1C is complete when:
- Worker crashes don't interrupt audio
- Failover is imperceptible to listener
- System self-heals from failures
- No resource leaks
- Metrics prove reliability

---
*Next: Execute research, then write formal specification*