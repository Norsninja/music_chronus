# Phase 1B: Final Implementation Strategy

**Date**: 2025-08-31
**Status**: Ready for Implementation
**Senior Dev Review**: Approved with GIL clarifications

## Key Insight: GIL Provides Atomicity

The critical clarification: **Python-native types are effectively atomic under the GIL**
- Both OSC thread and audio callback hold GIL when executing Python code
- Small assignments/reads of Python ints/floats are atomic from Python's perspective
- No risk of torn 64-bit writes when using Python-native types

## Final Architecture Decision

### Use Python-Native Fields (Option A Refined)

```python
class SharedParams:
    """Simple Python object for parameter exchange"""
    def __init__(self):
        self.frequency_hz = 440.0  # Python float
        self.seq = 0               # Python int
        # Metrics
        self.param_updates_received = 0
        self.param_updates_applied = 0
```

**Why this works**:
- GIL ensures atomic reads/writes of Python primitives
- No NumPy/ctypes complexity needed
- Sequence number pattern still provides race detection
- Simplest possible implementation

### Parameter Exchange Pattern

```python
# OSC Thread (writer)
def on_freq_message(freq):
    # Sanitize first
    freq = max(20.0, min(20000.0, freq))
    
    # Write value THEN bump seq (order matters!)
    shared.frequency_hz = freq
    shared.seq += 1
    shared.param_updates_received += 1

# Audio Callback (reader)
def audio_callback(outdata, frames, time_info, status):
    # Snapshot seq once per buffer
    current_seq = shared.seq
    
    if current_seq != self.last_seq:
        # Read frequency
        freq = shared.frequency_hz
        
        # Double-check seq unchanged (race detection)
        if shared.seq == current_seq:
            # Valid update - apply at boundary
            self.phase_increment = TWO_PI * freq / SAMPLE_RATE
            self.last_seq = current_seq
            shared.param_updates_applied += 1
    
    # Generate audio with current phase_increment
    # ... (existing phase accumulator code)
```

## Implementation Checklist

### 1. SharedParams Class
- [x] Python-native frequency_hz (float)
- [x] Python-native seq (int)
- [x] Metrics counters (received/applied)
- [x] No NumPy, no ctypes, no array.array needed

### 2. OSC Server Setup
- [x] AsyncIOOSCUDPServer on localhost:5005
- [x] Route: `/engine/freq f` → sanitize → update params
- [x] Run in separate thread from audio
- [x] No blocking operations

### 3. Audio Callback Updates
- [x] Read seq once per buffer
- [x] Double-check pattern for race detection
- [x] Apply frequency changes at buffer boundaries only
- [x] Maintain phase continuity (no phase reset)
- [x] No locks, no allocations, no syscalls

### 4. Sanitization
```python
MIN_FREQ = 20.0
MAX_FREQ = 20000.0

def sanitize_frequency(freq):
    """Clamp frequency to valid range"""
    return max(MIN_FREQ, min(MAX_FREQ, freq))
```

### 5. Testing Strategy

**Race Fuzzer Test**:
```python
# Inject random delays between writes
def fuzzy_update(freq):
    shared.frequency_hz = freq
    time.sleep(random.uniform(0, 0.0002))  # 0-200µs
    shared.seq += 1
```
- Run at 100-1000 updates/sec
- Count seq mismatches detected
- Assert audio remains glitch-free

**Latency Sampling**:
- Sample every 10th update
- Record control→apply latency in samples
- Assert p99 ≤ 256 samples + 0.3ms

**Stability Test**:
- 60s run at 100 msg/s
- Zero underruns required
- Record mismatch rate (should be near-zero)

## Do's and Don'ts

### DO:
✅ Keep param exchange in pure Python (no NumPy)
✅ Write frequency THEN bump seq (order matters)
✅ Snapshot seq once per buffer
✅ Apply changes at buffer boundaries only
✅ Maintain phase continuity

### DON'T:
❌ Use NumPy arrays for shared state
❌ Introduce locks in callback
❌ Use mp.Value, Queue, or implicit locks
❌ Reset phase on frequency change
❌ Print/log in audio callback

## Fallback Strategy

Keep Option C (minimal lock on writer) as a switch:
```python
# If empirical tests show issues, add:
self.param_lock = threading.Lock()

# OSC thread only:
with self.param_lock:
    shared.frequency_hz = freq
    shared.seq += 1

# Callback remains lock-free (optimistic read)
```

## Success Metrics

1. **Correctness**: Zero audio glitches
2. **Performance**: p99 latency ≤ 256 samples + 0.3ms
3. **Stability**: 60s @ 100 msg/s with zero underruns
4. **Simplicity**: <50 lines of param exchange code

## Next Steps

1. Implement SharedParams class
2. Add OSC server with /engine/freq handler
3. Update audio callback with seq double-check
4. Run race fuzzer test
5. Validate 60s stability

## Conclusion

The GIL clarification simplifies everything. We can use Python-native types with the sequence number pattern for race detection. This gives us:
- Atomic operations (via GIL)
- Race detection (via seq double-check)
- No locks in callback
- Simple, maintainable code

Ready to implement with confidence!

---
*Final strategy incorporating Senior Dev's GIL clarifications*
*Proceed with Python-native fields + seq double-check pattern*