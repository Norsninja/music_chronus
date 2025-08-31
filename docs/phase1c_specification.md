# Phase 1C: Process Supervision Specification

**Version**: 1.0
**Date**: 2025-08-31
**Status**: Approved by Senior Dev
**Goal**: Fault-tolerant audio engine with imperceptible failover

## Executive Summary

Phase 1C adds process supervision to the audio engine, enabling automatic recovery from worker crashes with zero audio interruption. Using manual Process management, sentinel monitoring, and hot-standby failover, the system maintains continuous audio output even during failures.

## Architecture Overview (Revised)

```
┌──────────────────────────────────────────────────────┐
│              Main Process (Supervisor)                │
│                                                       │
│  ┌─────────────────────────────────────────────┐    │
│  │      OSC Control Thread (Port 5005)         │    │
│  │      - Receives parameter changes           │    │
│  │      - Broadcasts to BOTH workers           │    │
│  └────────────┬───────────┬────────────────────┘    │
│               ↓           ↓                          │
│     Primary Cmd Ring   Standby Cmd Ring              │
│               ↓           ↓                          │
│  ┌─────────────────────────────────────────────┐    │
│  │      Audio Callback (sounddevice)           │    │
│  │      - Reads from active_ring               │    │
│  │      - Continuous output (never stops)      │    │
│  └─────────────────────────────────────────────┘    │
│               ↑                                      │
│        active_ring pointer                           │
│               ↑                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │    Monitor Thread (2ms polling)             │    │
│  │    - Monitors BOTH sentinels                │    │
│  │    - Checks heartbeats                      │    │
│  │    - Switches active_ring on failure        │    │
│  └─────────────────────────────────────────────┘    │
└───────────────┬──────────────┬──────────────────────┘
                ↓              ↓
    ┌──────────────────┐  ┌──────────────────┐
    │  Primary Worker  │  │  Standby Worker  │
    │  - DSP only      │  │  - DSP only      │
    │  - Lockstep      │  │  - Lockstep      │
    │  - Audio Ring    │  │  - Audio Ring    │
    └──────────────────┘  └──────────────────┘
    
Key Insight: Both workers render continuously with identical state.
Failover = atomic pointer switch. Zero audio interruption.

## Detailed Specifications

### 1. Ring Buffer Architecture

**Pre-allocated Audio Rings**:
```python
class AudioRing:
    """Lock-free SPSC ring for audio buffers"""
    def __init__(self, num_buffers=4, frames_per_buffer=256):
        # Cache-line aligned indices
        self.head = mp.Value('Q', 0, lock=False)  # Written by producer
        self._pad1 = mp.Array('c', 56)  # 64-byte alignment
        self.tail = mp.Value('Q', 0, lock=False)  # Written by consumer
        self._pad2 = mp.Array('c', 56)
        
        # Audio data storage
        total_frames = num_buffers * frames_per_buffer
        self.buffer = mp.Array('f', total_frames, lock=False)  # float32
        self.sequence = mp.Array('Q', num_buffers, lock=False)  # Buffer sequence numbers
        
    def write(self, audio_data, seq_num):
        """Producer writes buffer (worker)"""
        next_head = (self.head.value + 1) % self.num_buffers
        if next_head == self.tail.value:
            return False  # Ring full
        
        # Write audio and sequence
        offset = self.head.value * self.frames_per_buffer
        self.buffer[offset:offset+len(audio_data)] = audio_data
        self.sequence[self.head.value] = seq_num
        
        # Update head (memory barrier implicit)
        self.head.value = next_head
        return True
    
    def read_latest(self):
        """Consumer reads newest buffer (main process)"""
        if self.head.value == self.tail.value:
            return None  # Empty
        
        # Find newest complete buffer
        newest_idx = (self.head.value - 1) % self.num_buffers
        
        # Read audio
        offset = newest_idx * self.frames_per_buffer
        audio = self.buffer[offset:offset+self.frames_per_buffer]
        
        # Advance tail to newest (skip old buffers)
        self.tail.value = self.head.value
        return audio
```

**Command Rings** (reuse from IPC-04):
```python
class CommandRing(SPSCRingBuffer):
    """Command ring with coalescing on overflow"""
    def write_command(self, param, value):
        # If full, coalesce by keeping latest per param
        if self.is_full():
            self.coalesce_by_param()
        return self.write(pack_command(param, value))
```

### 2. Lockstep Worker Architecture

**Worker Process (DSP Only)**:
```python
def audio_worker_main(worker_id, cmd_ring, audio_ring, initial_state):
    # Initialize with synchronized state
    phase = initial_state['phase']
    frequency = initial_state['frequency']
    amplitude = initial_state['amplitude']
    
    # Pre-allocate buffers
    audio_buffer = np.zeros(256, dtype=np.float32)
    heartbeat_counter = 0
    buffer_seq = 0
    
    # Close inherited FDs
    close_inherited_fds(except_own=True)
    
    while True:
        # Process commands (broadcast from supervisor)
        if cmd_ring.has_data():
            cmd = cmd_ring.read()
            frequency, amplitude = apply_command(cmd, frequency, amplitude)
        
        # Generate audio (lockstep with other worker)
        generate_sine(audio_buffer, phase, frequency, amplitude)
        phase = update_phase(phase, frequency)
        
        # Write to audio ring
        audio_ring.write(audio_buffer, buffer_seq)
        buffer_seq += 1
        
        # Heartbeat (once per buffer)
        heartbeat_counter += 1
        shared_heartbeat[worker_id] = heartbeat_counter
```

### 3. Dual-Worker Sentinel Monitoring

**Monitor Thread (Both Workers)**:
```python
def monitor_thread(workers, audio_rings, metrics):
    POLL_INTERVAL = 0.002  # 2ms default
    HEARTBEAT_TIMEOUT = 0.015  # 15ms (2.5x buffer period for safety)
    
    # Track both workers
    sentinels = [w.sentinel for w in workers]
    last_heartbeats = [0, 0]
    last_heartbeat_times = [time.monotonic(), time.monotonic()]
    active_idx = 0  # Which ring we're reading from
    
    while True:
        # Use connection.wait with timeout (simpler than manual sleep)
        ready = connection.wait(sentinels, timeout=POLL_INTERVAL)
        
        if ready:
            # Identify which worker died
            for i, sentinel in enumerate(sentinels):
                if sentinel in ready:
                    if i == active_idx:
                        # Primary died - switch to standby
                        handle_primary_death(workers, audio_rings, metrics)
                        active_idx = 1 - active_idx  # Switch
                    else:
                        # Standby died - spawn new one
                        handle_standby_death(workers, metrics)
                    break
        
        # Check heartbeats for both workers
        current_time = time.monotonic()
        for i, worker in enumerate(workers):
            current_hb = shared_heartbeats[i]
            if current_hb == last_heartbeats[i]:
                # No progress - check timeout
                if current_time - last_heartbeat_times[i] > HEARTBEAT_TIMEOUT:
                    if i == active_idx:
                        handle_primary_hang(workers, audio_rings, metrics)
                        active_idx = 1 - active_idx
                    else:
                        handle_standby_hang(workers, metrics)
            else:
                last_heartbeats[i] = current_hb
                last_heartbeat_times[i] = current_time
```

**Dynamic Polling Adjustment**:
```python
# Tighten polling under load
if metrics.recent_failures > 0:
    POLL_INTERVAL = 0.001  # 1ms when unstable
elif time_since_last_command < 1.0:
    POLL_INTERVAL = 0.002  # 2ms when active
else:
    POLL_INTERVAL = 0.005  # 5ms when idle
```

### 4. Failover Mechanism (Simplified)

**Instant Failover (Pointer Switch)**:
```python
def handle_primary_death(workers, audio_rings, metrics):
    start_time = time.monotonic_ns()
    
    # 1. Atomic switch - just change which ring we read!
    supervisor.active_ring = audio_rings[1]  # Switch to standby ring
    
    # 2. Record metrics
    failover_time_ns = time.monotonic_ns() - start_time
    metrics.record_failover(failover_time_ns, 'primary_death')
    
    # 3. Spawn replacement standby (background)
    threading.Thread(target=spawn_new_standby).start()
    
    # 4. Clean up dead worker
    cleanup_worker(workers[0])
    
    # Failover complete - audio never stopped!
```

**Main Process Audio Callback**:
```python
def audio_callback(outdata, frames, time_info, status):
    """Runs in main process - never stops"""
    # Read from whichever ring is active
    audio_data = supervisor.active_ring.read_latest()
    
    if audio_data is not None:
        outdata[:, 0] = audio_data
    else:
        outdata.fill(0)  # Silence on underrun
    
    # Audio device never closes during failover!

### 5. Broadcast Command Routing

**OSC Handler (Broadcasts to Both)**:
```python
def handle_osc_command(address, *args):
    """Broadcast commands to keep workers in lockstep"""
    if address == "/engine/freq":
        freq = sanitize_frequency(args[0])
        cmd = pack_command('frequency', freq)
        
        # Write to BOTH command rings
        primary_cmd_ring.write_command(cmd)
        standby_cmd_ring.write_command(cmd)
        
        # Wake BOTH workers
        primary_socket.send(b'!')
        standby_socket.send(b'!')
        
        metrics.commands_sent += 2
```

**Key Insight**: Both workers process identical commands at identical buffer boundaries, maintaining perfect synchronization.

### 5. Resource Management

**SHM Registry Format**:
```json
{
  "version": "1.0",
  "timestamp": "2025-08-31T10:00:00Z",
  "allocations": [
    {
      "id": "audio_state_001",
      "type": "SharedAudioState",
      "size_bytes": 128,
      "owner_pid": 12345,
      "owner_start_time": 1234567890.123,
      "created": "2025-08-31T10:00:00Z",
      "last_accessed": "2025-08-31T10:00:05Z"
    },
    {
      "id": "ring_buffer_001",
      "type": "SPSCRingBuffer",
      "size_bytes": 4096,
      "owner_pid": 12345,
      "created": "2025-08-31T10:00:00Z"
    }
  ],
  "stats": {
    "total_allocated_bytes": 4224,
    "active_allocations": 2,
    "leaked_allocations": 0,
    "lifetime_allocations": 52
  }
}
```

**Cleanup Protocol**:
```python
def cleanup_worker(worker):
    # 1. Close sentinel to prevent spurious signals
    if worker.sentinel:
        worker.sentinel.close()
    
    # 2. Terminate with timeout
    worker.process.terminate()
    worker.process.join(timeout=1.0)
    
    # 3. Force kill if needed
    if worker.process.is_alive():
        worker.process.kill()
        worker.process.join(timeout=1.0)
    
    # 4. Update registry
    shm_registry.release_allocations(worker.pid, worker.start_time)
    
    # 5. Close any leaked FDs
    cleanup_inherited_fds(worker.pid)
```

### 6. Metrics Collection

**Required Metrics**:
```python
class SupervisorMetrics:
    def __init__(self):
        # Failure tracking
        self.crash_count = 0
        self.replacements = 0
        self.detection_cause = []  # 'sentinel' or 'heartbeat'
        
        # Timing (stored in nanoseconds)
        self.detection_times_ns = []  # Death → detection
        self.failover_times_ns = []   # Detection → standby active
        self.rebuild_times_ns = []    # Start → new standby ready
        
        # Resource tracking
        self.shm_leaks = 0
        self.fd_leaks = 0
        
        # State
        self.spare_ready = True
        self.last_failure_time = None
    
    def get_percentiles(self, data_ns, percentiles=[50, 95, 99]):
        """Calculate percentiles in milliseconds"""
        if not data_ns:
            return {p: 0.0 for p in percentiles}
        sorted_data = sorted(data_ns)
        return {
            p: sorted_data[int(len(sorted_data) * p/100)] / 1_000_000
            for p in percentiles
        }
```

## Acceptance Criteria

### Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| Death detection p95 | <10ms | Sentinel trigger → handler entry |
| Failover completion | <10ms | Handler entry → standby active |
| Standby rebuild | <500ms | Spawn → pre-warmed ready |
| Audio continuity | Zero underruns | During 3 induced crashes |
| Resource leaks | Zero | Across 50 kill/restart cycles |

### Test Scenarios

1. **Clean Exit Test**
   - Worker calls `sys.exit(0)`
   - Verify identical handling to crash

2. **SIGKILL Test**
   - `os.kill(worker.pid, signal.SIGKILL)`
   - Verify failover within 10ms

3. **Hang Simulation**
   - Worker stops incrementing heartbeat
   - Verify detection within 12ms

4. **Cascade Failure**
   - Kill primary, then kill standby during activation
   - Verify system recovers

5. **Resource Leak Test**
   - 50 cycles of kill/restart
   - Verify no FD or SHM leaks

## Implementation Plan

### Phase 1: Core Supervisor (Week 1)
- Manual Process management
- Basic sentinel monitoring
- Simple failover (no standby)

### Phase 2: Hot-Standby (Week 2)
- Pre-warmed standby process
- Instant failover mechanism
- Standby rebuild automation

### Phase 3: Full Integration (Week 3)
- SPSC ring buffer integration
- Socketpair wakeup pattern
- SHM registry implementation

### Phase 4: Hardening (Week 4)
- Edge case handling
- Resource leak prevention
- Performance optimization

## Risk Mitigation

### Risk: Spurious Ready Signals
**Mitigation**: Close inherited pipe FDs in children after spawn

### Risk: PID Reuse
**Mitigation**: Track workers by (PID, start_time) tuple

### Risk: Standby Failure During Activation
**Mitigation**: Immediate fallback to spawn new primary

### Risk: Memory Corruption During Failover
**Mitigation**: Atomic routing switch before any state changes

## Success Metrics

- **Reliability**: 99.99% uptime (< 1 minute downtime/week)
- **Performance**: Imperceptible failover to human listener
- **Resources**: Zero leaks after 1000 cycles
- **Recovery**: Self-healing from any failure mode

## Conclusion

Phase 1C transforms the audio engine from a single point of failure into a fault-tolerant system capable of transparent recovery. The combination of sentinel monitoring, hot-standby failover, and shared memory continuity ensures uninterrupted audio even during worker crashes.

---
*Specification approved - Ready for implementation*