# Phase 1B: Control Integration Plan

**Created**: 2025-08-31
**Status**: In Progress
**Senior Chronus Review**: Approved

## Objective
Add OSC control path to the audio engine for real-time parameter changes while maintaining zero underruns.

## Architecture Overview

```
OSC Client (User/AI)
    ↓ UDP
AsyncIOOSCUDPServer (localhost:5005)
    ↓ Lock-free write
Shared State (frequency_hz, seq)
    ↓ Lock-free read
Audio Callback (boundary application)
    ↓
Audio Output (modified frequency)
```

## Implementation Details

### 1. OSC Control Thread
- **Framework**: python-osc with AsyncIOOSCUDPServer
- **Endpoint**: localhost:5005 (validated in IPC-01/02 tests)
- **Routes**:
  - `/engine/freq <float>` - Set frequency in Hz
  - `/engine/status` - Request status (optional for Phase 1B)
- **Threading**: Runs in separate thread from audio callback
- **No blocking**: AsyncIO ensures non-blocking message handling

### 2. Lock-free Parameter Exchange

```python
# Shared state structure (pseudo-code)
class SharedParams:
    frequency_hz: float  # Target frequency
    seq: uint64         # Sequence number (increments on change)
```

**Update Path** (OSC thread):
1. Receive OSC message
2. Validate and sanitize frequency (20-20000 Hz)
3. Write frequency_hz
4. Increment seq (atomic)

**Read Path** (Audio callback):
1. Read seq at buffer start
2. If seq changed from last seen:
   - Read frequency_hz
   - Apply at next buffer boundary
   - Update phase increment
3. Continue synthesis with new frequency

### 3. Boundary-Only Application
- Parameter changes ONLY applied between buffers
- No mid-buffer frequency changes (prevents clicks)
- Phase continuity maintained across frequency changes
- Phase increment recalculated: `2π * frequency / sample_rate`

### 4. Frequency Sanitization
```python
MIN_FREQ = 20.0    # Hz
MAX_FREQ = 20000.0 # Hz

def sanitize_frequency(freq):
    return max(MIN_FREQ, min(MAX_FREQ, freq))
```

### 5. Metrics Updates
Track in shared state:
- `param_updates_received`: Count of OSC messages
- `param_updates_applied`: Count of actual frequency changes
- `last_update_latency_samples`: Samples between receive and apply
- Expose via status endpoint or CLI

## Acceptance Criteria

### Functional Requirements
- [x] Frequency changes via OSC reliably update the tone
- [x] No audible glitches or clicks during frequency changes
- [x] Frequency range properly clamped (20-20kHz)

### Performance Requirements
- [x] p99 control→apply latency ≤ 256 samples (5.8ms) + 0.3ms overhead
- [x] 60-second run under 100 msg/s OSC load with zero underruns
- [x] No ring buffer overruns
- [x] CPU usage remains <10%

### Implementation Requirements
- [x] NO allocations in audio callback
- [x] NO locks in audio callback
- [x] NO syscalls in audio callback
- [x] Status shows stable metrics

## Test Strategy

### 1. Basic Frequency Change Test
```bash
# Start engine
python audio_engine_v3.py &

# Send frequency changes
oscsend localhost 5005 /engine/freq f 440.0
sleep 1
oscsend localhost 5005 /engine/freq f 880.0
sleep 1
oscsend localhost 5005 /engine/freq f 220.0
```

### 2. Load Test (100 msg/s)
```python
# Automated test sending 100 OSC messages/second
# Verify zero underruns over 60 seconds
```

### 3. Latency Measurement
- Timestamp OSC message send
- Monitor when frequency actually changes in audio
- Verify p99 < 256 samples + 0.3ms

## Environment Settings
```bash
export PULSE_SERVER=tcp:172.21.240.1:4713
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1
export CHRONUS_BUFFER_SIZE=256
```

## Implementation Files
- `audio_engine_v3.py` - Main engine with OSC control
- `test_phase1b_control.py` - Test suite for control integration
- `test_osc_load.py` - 100 msg/s load test

## Risk Mitigation
- **GIL Contention**: AsyncIO in separate thread minimizes GIL interaction
- **Race Conditions**: Lock-free design with sequence numbers
- **Audio Glitches**: Boundary-only application prevents discontinuities
- **Memory Barriers**: Use appropriate atomic operations for seq

## Success Metrics
- Zero underruns during normal operation
- <6ms total control→audio latency
- Smooth frequency sweeps without artifacts
- Stable performance under load

## Notes from Senior Chronus
- rtmixer deferred for scheduled buffers (not needed for continuous generation)
- Buffer count drift (~5%) noted but non-critical
- Keep threading minimal (audio + OSC only)
- GC disable not necessary but acceptable if already done

---
*Phase 1B brings the synthesizer to life with real-time control*