# Phase 1A: Audio Engine Core - Research Findings

**Date**: 2025-08-31
**Status**: Ready for Implementation

## Critical Patterns Validated

### 1. rtmixer Audio Generation
```python
# Use play_ringbuffer() not callbacks
mixer = rtmixer.Mixer(samplerate=44100, blocksize=256, latency='low')
ring_buffer = rtmixer.RingBuffer(elementsize=4, capacity=blocksize*8)
action = mixer.play_ringbuffer(ring_buffer, channels=1, allow_belated=True)
```
- Pre-fill buffer to prevent initial underrun
- Buffer size = nextpow2(blocksize * 8) minimum
- rtmixer.RingBuffer is for C↔Python only, NOT thread communication

### 2. Lock-free SPSC Ring Buffer
```python
# Use ringbuf library (Boost C++ backend, <1ms latency)
import ringbuf
buffer = ringbuf.RingBuffer(format='f', capacity=samples)
```
- Handles underruns with zero-padding
- No false sharing issues
- Production-tested for audio

### 3. Phase Accumulator Synthesis
```python
# Wavetable with linear interpolation
wavetable = np.sin(np.linspace(0, 2*np.pi, 1024, endpoint=False))
phase += frequency * wavetable_size / sample_rate
index = int(phase % wavetable_size)
# Linear interpolation prevents aliasing
```
- 1024 sample wavetable optimal
- Continuous phase prevents clicks
- Sample-accurate frequency changes

### 4. Parameter Updates
```python
# Double-buffer pattern
current_params = {...}
pending_params = {...}
# Apply at buffer boundary only
if update_pending:
    current_params.update(pending_params)
```
- Atomic swaps at buffer boundaries
- No mid-buffer discontinuities
- threading.Event for synchronization

### 5. Thread Coordination
```python
# Audio thread with priority
audio_thread = threading.Thread(target=audio_loop, daemon=False)
os.nice(-10)  # Higher priority if allowed
# Command queue for control
command_queue = queue.Queue(maxsize=100)  # Control only, NOT audio
```

## Critical Warnings

❌ **DON'T**:
- Use Python threads for DSP (5.7x slower than multiprocessing)
- Use queue.Queue for audio data (control messages only)
- Allocate memory in audio callback (guaranteed dropouts)
- Use rtmixer.RingBuffer for thread communication
- Spawn workers on-demand (672ms cost)

✅ **DO**:
- Pre-allocate all buffers
- Use worker pools with pre-imports
- Apply parameter changes at buffer boundaries
- Use shared memory for audio data
- Handle underruns gracefully with zero-padding

## Performance Metrics Confirmed

| Component | Latency | Source |
|-----------|---------|--------|
| rtmixer audio | 5.9ms | RT-01 test |
| Worker pool | 0.02ms | PROC-02 test |
| Shared memory | 0.042ms | IPC-03 test |
| OSC control | 0.068ms | IPC-01 test |
| ringbuf SPSC | <1ms | Research |

## Architecture Validation

Our design is correct:
1. Worker pool eliminates import overhead ✅
2. rtmixer provides low-latency audio ✅
3. Shared memory enables zero-copy ✅
4. OSC handles control messages ✅
5. Multiprocessing beats threading for DSP ✅

## Implementation Structure

```
audio_engine.py
├── AudioEngine (coordinator)
│   ├── start/stop control
│   ├── thread management
│   └── graceful shutdown
├── SineGenerator (DSP)
│   ├── phase accumulator
│   ├── wavetable lookup
│   └── linear interpolation
├── AudioBuffer (communication)
│   ├── ringbuf SPSC
│   ├── underrun handling
│   └── metrics tracking
└── ParameterManager (control)
    ├── double buffering
    ├── atomic updates
    └── boundary application
```

## Next Steps

1. Implement minimal audio engine with continuous sine
2. Add OSC control for frequency changes
3. Verify 60s stability with zero underruns
4. Measure end-to-end latency (command→audio)
5. Add basic CLI for start/stop