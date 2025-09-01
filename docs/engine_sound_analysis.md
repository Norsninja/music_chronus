# Engine Sound Analysis - Current System State
Date: 2025-09-01
Investigator: Chronus Nexus

## Executive Summary
The synthesizer produces an "engine-like" sound instead of clean tones. While the system is technically functioning (audio is produced, commands are received), the DSP output is corrupted or modulated in an unintended way.

## What We Know Works

### Successfully Fixed Issues
1. **CommandRing truncation bug** - FIXED
   - Was truncating Protocol v2 packets at first null byte
   - Now returns full 64-byte packets
   - Commands now reach modules intact

2. **Missing process_commands() call** - FIXED
   - Worker loop now calls host.process_commands()
   - Commands are applied at buffer boundaries

3. **Audio path is active**
   - Sound IS produced (not silence)
   - Frequency changes ARE audible
   - Gate on/off works
   - System responds to OSC commands

### System Architecture (Current)
```
OSC Client (port 5005)
    ↓
AudioSupervisor (coordinator)
    ├── Primary Worker (PID: 639489)
    │   └── ModuleHost → SimpleSine → ADSR → BiquadFilter
    ├── Standby Worker (PID: 639490)
    │   └── ModuleHost → SimpleSine → ADSR → BiquadFilter
    ↓
Audio Callback
    ├── Reads from: self.active_ring (either primary or standby)
    └── Outputs to: SoundDevice → PulseAudio → Windows
```

## The "Engine Sound" Problem

### Symptoms
- Sound described as "engine-like"
- Rapid oscillation/modulation
- Pitch changes work but tone quality is wrong
- Sounds "cool but not right for testing"

### Potential Causes (Most to Least Likely)

#### 1. Buffer Discontinuities (MOST LIKELY)
The audio callback reads from `self.active_ring.read_latest()` which might be:
- Getting partial buffers during writes
- Switching between old/new buffers rapidly
- Missing synchronization between worker writes and callback reads

**Evidence:** Engine sounds often come from rapid buffer switching creating a "chopping" effect.

#### 2. Both Workers Processing (POSSIBLE)
If both primary AND standby workers are:
- Processing audio simultaneously
- Writing to their rings
- And the callback is somehow reading from both

This would create interference patterns.

**Evidence:** Two workers are running (PIDs 639489, 639490).

#### 3. Phase Accumulator Issues
SimpleSine might have:
- Phase wraparound problems
- Discontinuous phase updates
- Floating point precision issues

**Evidence:** The pitch changes correctly, suggesting phase accumulation works somewhat.

#### 4. Sample Rate Mismatch
If modules process at one rate but output at another:
- SAMPLE_RATE = 44100 (defined)
- But actual output rate might differ
- Creates aliasing/modulation

#### 5. Ring Buffer Corruption
The AudioRing might be:
- Wrapping incorrectly
- Returning old data mixed with new
- Having race conditions in read_latest()

## What The Code Shows

### Audio Callback (supervisor_v2_fixed.py:339)
```python
def audio_callback(self, outdata, frames, time_info, status):
    buffer = self.active_ring.read_latest()  # Gets latest buffer
    if buffer is not None:
        np.copyto(outdata[:, 0], buffer, casting='no')
```
- Only reads from ONE ring (active_ring)
- Should prevent dual-worker interference

### Worker Processing (supervisor_v2_fixed.py:238)
```python
host.process_commands()
audio_buffer = host.process_chain()
audio_ring.write(audio_buffer, buffer_seq)
```
- Each worker processes independently
- Writes complete buffers to its ring

### Module Chain (module_host.py:276)
```python
module.process_buffer(current_buf, next_buf)
```
- Modules process in sequence
- Uses pre-allocated buffers

## Diagnostic Tests Needed

1. **Check if both workers are writing**
   - Add logging to show which worker is active
   - Verify only one ring is being read

2. **Buffer continuity test**
   - Log buffer sequence numbers
   - Check for gaps or duplicates

3. **Disable modules selectively**
   - Try just sine (no ADSR/filter)
   - Isolate which module causes corruption

4. **Check timing**
   - Log buffer generation rate
   - Verify 256 samples @ 44100Hz = 5.8ms per buffer

## Immediate Actions

1. **Add verbose logging** to see:
   - Which worker is active
   - Buffer sequence numbers
   - RMS values per buffer

2. **Test with single worker**
   - Disable standby worker
   - See if engine sound persists

3. **Bypass module chain**
   - Generate simple test tone directly
   - Verify audio path is clean

## Conclusion

The system is "almost working" - all the infrastructure is correct, commands flow properly, and audio is produced. The engine-like sound suggests a timing or synchronization issue in the audio pipeline, most likely buffer discontinuities or rapid switching between buffers. The fix will likely be in the AudioRing.read_latest() method or the synchronization between worker writes and callback reads.