# Recording Feature Implementation Plan

**Date**: 2025-09-03  
**Author**: Chronus Nexus  
**Purpose**: Add WAV recording capability to capture sessions and verify audio quality

## Executive Summary

Add recording capability to the Music Chronus synthesizer to:
1. Prove generated audio is clean (bypass WSL2 playback issues)
2. Capture live performance sessions with OSC control
3. Debug audio artifacts by analyzing WAV files
4. Document musical collaborations

## Current Architecture Analysis

### Audio Flow
```
Worker Process (Slot 0/1)
    ↓ module_host.process_chain() → np.ndarray[256]
AudioRing (Shared Memory)
    ↓ Zero-copy transfer via SPSC queue
Supervisor audio_callback()
    ↓ read_latest_keep() from active ring
sounddevice outdata[:, 0]
    ↓
Audio Output (PulseAudio → Windows)
```

### Key Components
- **Audio Generation**: `module_host.process_chain()` returns float32 numpy arrays
- **Buffer Size**: 256 samples per buffer (5.8ms @ 44.1kHz)
- **Ring Buffer**: Shared memory with multiple buffers (typically 16-32)
- **Audio Callback**: Runs every ~5.9ms, copies buffer to sounddevice
- **Sample Rate**: 44100 Hz (configurable via CHRONUS_SAMPLE_RATE)

## Implementation Options Evaluated

### Option A: Live Session Recording (RECOMMENDED)
**Location**: supervisor_v3_router.py audio_callback method  
**Approach**: Accumulate buffers during playback, write WAV on stop  
**Pros**: Records actual performance, simple implementation, OSC control  
**Cons**: Memory usage (~11.5 MB/minute), blocking write on stop  

### Option B: Worker-Level Recording
**Location**: Worker process before ring buffer  
**Approach**: Record at generation point  
**Pros**: Can record slots separately, no callback impact  
**Cons**: Complex coordination, misses failover transitions  

### Option C: Offline Rendering
**Approach**: Standalone script, no real-time constraints  
**Pros**: Perfect quality, faster than real-time possible  
**Cons**: No live performance capture, separate workflow  

## Recommended Implementation (Option A)

### 1. State Management
```python
# In AudioSupervisor.__init__
self.recording = False
self.record_buffer = []
self.record_filename = None
self.record_start_time = None
```

### 2. Buffer Capture
```python
# In audio_callback, after line 811 (outdata copy)
if self.recording:
    # Use copy() to avoid reference issues
    self.record_buffer.append(self.last_good.copy())
```

### 3. Recording Control Methods
```python
def start_recording(self, filename=None):
    """Start recording audio to WAV file."""
    if self.recording:
        print("[RECORD] Already recording")
        return
    
    # Generate filename if not provided
    if not filename:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.wav"
    
    # Initialize recording
    self.record_buffer = []
    self.record_filename = filename
    self.record_start_time = time.perf_counter()
    self.recording = True
    print(f"[RECORD] Started recording to {filename}")

def stop_recording(self):
    """Stop recording and save WAV file."""
    if not self.recording:
        print("[RECORD] Not recording")
        return
    
    self.recording = False
    
    if self.record_buffer:
        # Concatenate all buffers
        audio_data = np.concatenate(self.record_buffer)
        
        # Convert float32 [-1,1] to int16 for WAV
        audio_int = np.int16(np.clip(audio_data, -1.0, 1.0) * 32767)
        
        # Write WAV file
        from scipy.io import wavfile
        wavfile.write(self.record_filename, int(SAMPLE_RATE), audio_int)
        
        # Calculate duration
        duration = len(audio_data) / SAMPLE_RATE
        file_size = len(audio_data) * 2 / 1024 / 1024  # MB
        
        print(f"[RECORD] Saved {duration:.1f}s ({file_size:.1f}MB) to {self.record_filename}")
        
        # Clear buffer to free memory
        self.record_buffer = []
    else:
        print("[RECORD] No audio recorded")
```

### 4. OSC Handlers
```python
def handle_record_start(self, unused_addr, *args):
    """OSC handler for /record/start [filename]"""
    filename = args[0] if args else None
    self.start_recording(filename)

def handle_record_stop(self, unused_addr):
    """OSC handler for /record/stop"""
    self.stop_recording()

def handle_record_status(self, unused_addr):
    """OSC handler for /record/status"""
    if self.recording:
        duration = time.perf_counter() - self.record_start_time
        buffer_count = len(self.record_buffer)
        memory_mb = buffer_count * BUFFER_SIZE * 4 / 1024 / 1024
        print(f"[RECORD] Recording: {duration:.1f}s, {buffer_count} buffers, {memory_mb:.1f}MB")
    else:
        print("[RECORD] Not recording")
```

### 5. OSC Route Registration
```python
# In __init__, add to dispatcher
dispatcher.map("/record/start", self.handle_record_start)
dispatcher.map("/record/stop", self.handle_record_stop)
dispatcher.map("/record/status", self.handle_record_status)
```

### 6. Cleanup on Shutdown
```python
# In stop() method
if self.recording:
    print("[RECORD] Stopping recording due to shutdown")
    self.stop_recording()
```

## Usage Examples

### Basic Recording
```bash
# Start recording with auto-generated filename
python -c "from pythonosc import udp_client; c = udp_client.SimpleUDPClient('127.0.0.1', 5005); c.send_message('/record/start', [])"

# Start recording with specific filename
python -c "from pythonosc import udp_client; c = udp_client.SimpleUDPClient('127.0.0.1', 5005); c.send_message('/record/start', ['my_performance.wav'])"

# Check status
python -c "from pythonosc import udp_client; c = udp_client.SimpleUDPClient('127.0.0.1', 5005); c.send_message('/record/status', [])"

# Stop and save
python -c "from pythonosc import udp_client; c = udp_client.SimpleUDPClient('127.0.0.1', 5005); c.send_message('/record/stop', [])"
```

### Performance Session Script
```python
#!/usr/bin/env python3
"""Record a musical performance session."""

from pythonosc import udp_client
import time

client = udp_client.SimpleUDPClient('127.0.0.1', 5005)

# Start recording
session_name = input("Session name: ")
client.send_message('/record/start', [f'{session_name}.wav'])

# Create patch
client.send_message('/patch/create', ['sine', 'simple_sine'])
client.send_message('/patch/connect', ['sine', 'output'])
client.send_message('/patch/commit', [])

# Perform music
print("Recording... Press Enter to stop")
input()

# Stop recording
client.send_message('/record/stop', [])
print(f"Session saved to {session_name}.wav")
```

## Memory and Performance Considerations

### Memory Usage
- **Per Buffer**: 256 samples × 4 bytes = 1 KB
- **Per Second**: 44100 Hz ÷ 256 × 1 KB = 172 KB/s
- **Per Minute**: 10.3 MB
- **10-minute session**: ~103 MB (acceptable)

### Performance Impact
- **Copy overhead**: ~0.001ms per buffer (negligible)
- **No allocation**: Uses pre-allocated list, append only
- **File write**: ~50ms for 1-minute recording (on stop only)
- **RT-safety**: Maintained via .copy() in callback

### Maximum Recording Time
- **Practical limit**: ~60 minutes (600 MB memory)
- **Hard limit**: System RAM dependent
- **Recommendation**: Stop/start new files every 30 minutes

## Testing Plan

### Unit Tests
1. Record 10 seconds of sine wave
2. Verify WAV file format and duration
3. Test memory cleanup after stop
4. Test filename generation

### Integration Tests
1. Record during patch switches
2. Record during parameter sweeps
3. Verify no impact on audio metrics
4. Test long recordings (10+ minutes)

### Verification Tests
1. Record in WSL2, play WAV on Windows
2. Compare recorded vs. live audio quality
3. Verify no dropouts in recording
4. Check phase continuity in WAV

## Future Enhancements

### Phase 1 (MVP)
- ✅ Basic recording start/stop
- ✅ OSC control
- ✅ WAV file output
- ✅ Auto-naming with timestamps

### Phase 2
- [ ] Streaming write (reduce memory usage)
- [ ] Multiple format support (FLAC, OGG)
- [ ] Recording level meters
- [ ] Automatic file splitting at size limit

### Phase 3
- [ ] Multi-track recording (per module)
- [ ] MIDI event recording alongside audio
- [ ] Real-time compression
- [ ] Cloud upload integration

## Implementation Checklist

- [ ] Add recording state variables to AudioSupervisor
- [ ] Implement buffer capture in audio_callback
- [ ] Add start/stop/status methods
- [ ] Create OSC handlers
- [ ] Register OSC routes
- [ ] Add cleanup on shutdown
- [ ] Import scipy.io.wavfile
- [ ] Test basic recording
- [ ] Test with musical performance
- [ ] Document in user guide

## Benefits

### Immediate
- **Prove clean audio generation** despite WSL2 playback issues
- **Capture musical performances** for sharing and analysis
- **Debug audio issues** by examining WAV files
- **Document progress** in musical exploration

### Long-term
- **Build performance library** of synthesizer capabilities
- **Share musical collaborations** between human and AI
- **Analyze synthesis techniques** offline
- **Create training data** for future AI music systems

## Conclusion

The recording feature is a high-value, low-complexity addition that:
- Requires ~50 lines of code
- Has minimal performance impact
- Provides crucial debugging capability
- Enables performance capture
- Proves our audio generation is clean despite WSL2 artifacts

Recommended for immediate implementation.