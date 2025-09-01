# Debugging Session Findings - 2025-09-01

## Problem Statement
The synthesizer appears to be fully functional but produces no audible output when controlled via OSC commands in tmux.

## What's Working ✅

### 1. Audio System
- **Direct audio tests work**: `test_audio_direct.py` produces audible sound
- **PulseAudio configured correctly**: Using `unix:/mnt/wslg/PulseServer`
- **sounddevice can output audio**: Test tones are audible when run directly

### 2. OSC Communication
- **Senior Dev's fix applied successfully**: Changed from `/*` pattern to specific patterns
  - `/mod/*/*` for module parameters
  - `/gate/*` for gate control  
  - `/engine/*` for legacy control
  - Default handler as catch-all
- **Messages are being received**: With `CHRONUS_VERBOSE=1`, we see:
  ```
  OSC recv: /mod/sine/freq (440.0,)
  OSC recv: /mod/sine/gain (0.7,)
  OSC recv: /gate/adsr ('on',)
  ```

### 3. Process Architecture
- **Workers start correctly**: 
  ```
  Primary worker started with ModuleHost (PID: 507813)
  Standby worker started with ModuleHost (PID: 507814)
  ```
- **Audio stream initialized**: `Audio stream started: 44100Hz, 256 samples`
- **OSC server listening**: `OSC server listening on 127.0.0.1:5005`

## What's NOT Working ❌

### No Audio Output Despite:
1. OSC messages being received
2. Workers running with ModuleHost
3. Audio callback active (no underruns reported)
4. Test claiming "ALL TESTS PASSED"

## Key Discoveries

### 1. OSC Pattern Matching Issue (FIXED)
- **Root Cause**: The wildcard pattern `/*` only matches single segments
- **Solution**: Use specific patterns for each endpoint type
- **Credit**: Senior Dev identified this immediately

### 2. PulseAudio Server Configuration (FIXED)
- **Root Cause**: Using wrong PULSE_SERVER (tcp:172.21.240.1:4713 instead of unix:/mnt/wslg/PulseServer)
- **Solution**: Set correct PULSE_SERVER environment variable

### 3. Audio Pipeline Mystery (CURRENT ISSUE)
The audio generation chain SHOULD work as follows:
1. OSC command received → ✅ Confirmed via verbose logs
2. Command packed into Protocol v2 → Assumed working
3. Command sent to workers via shared memory → Unknown
4. Workers process command in ModuleHost → Unknown
5. ModuleHost generates audio:
   - SimpleSine generates sine wave
   - ADSR applies envelope (needs gate ON)
   - BiquadFilter filters the signal
6. Audio written to shared memory ring → Unknown
7. Audio callback reads from ring → Unknown
8. sounddevice outputs audio → System capable but no sound

## Suspected Issues

### 1. Command Delivery to Workers
- Commands may not be reaching workers via shared memory
- The `broadcast_command_raw()` may not be waking workers

### 2. Module Processing Chain
- ModuleHost starts with silence buffer
- SimpleSine should generate into output buffer (ignoring input)
- ADSR needs gate to be ON to pass signal
- **Possible issue**: Gate command not being processed by ADSR

### 3. Audio Ring Buffer
- Workers may not be writing to audio rings
- Audio callback may be reading empty/silent buffers

### 4. Worker Audio Generation Loop
- Workers may not be calling `host.process_chain()` 
- Timing/synchronization issue with buffer generation

## Test Anomaly
The `test_modulehost_fixed.py` reports "ALL TESTS PASSED" but:
- No audio was heard during the test
- The test measures failover timing, not audio output
- The test doesn't verify actual sound generation

## Next Steps to Investigate

1. **Verify command delivery**: Add logging to see if workers receive commands
2. **Check audio buffer content**: Log if buffers contain non-zero data
3. **Trace ADSR gate state**: Confirm gate is actually being set to ON
4. **Monitor worker processing**: Verify `process_chain()` is being called
5. **Inspect audio callback**: Check if receiving non-silent buffers

## Environment Details
- WSL2 on Windows
- PulseAudio via WSLg
- Python 3.12 with virtual environment
- Using multiprocessing with shared memory
- OSC via python-osc library

## Critical Code Paths
- OSC Handler: `/src/music_chronus/supervisor_v2_fixed.py:555` (handle_osc_message)
- Command Broadcast: `/src/music_chronus/supervisor_v2_fixed.py:543` (broadcast_command_raw)
- Worker Process: `/src/music_chronus/supervisor_v2_fixed.py:148` (audio_worker_process)
- Audio Callback: `/src/music_chronus/supervisor_v2_fixed.py:324` (audio_callback)
- Module Processing: `/src/music_chronus/module_host.py:244` (process_chain)

---
*Session ongoing - audio generation issue not yet resolved*