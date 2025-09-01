# Tmux Session Errors - 2025-09-01

## Issue Summary
During tmux collaborative session testing, the synthesizer runs but produces no audible output despite OSC commands being sent successfully.

## Error Log from Server Crash

### Initial Crash with CHRONUS_VERBOSE=1
```
Shutdown signal received
Stopping AudioSupervisor...
Process Process-5:
Standby worker hung - spawning replacement
Standby failed (heartbeat) - spawning replacement
Traceback (most recent call last):
Standby worker hung - spawning replacement
Standby failed (heartbeat) - spawning replacement
  File "/usr/lib/python3.12/multiprocessing/process.py", line 302, in _bootstrap
    _parent_process = _ParentProcess(
                      ^^^^^^^^^^^^^^^
  File "/home/norsninja/music_chronus/src/music_chronus/supervisor_v2_fixed.py", line 813, in signal_handler
    supervisor.stop()
  File "/home/norsninja/music_chronus/src/music_chronus/supervisor_v2_fixed.py", line 752, in stop
    self.cleanup_workers()
  File "/home/norsninja/music_chronus/src/music_chronus/supervisor_v2_fixed.py", line 761, in cleanup_workers
    worker.terminate()
  File "/home/norsninja/music_chronus/src/music_chronus/supervisor_v2_fixed.py", line 118, in terminate
    if self.process and self.process.is_alive():
                        ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/multiprocessing/process.py", line 160, in is_alive
    assert self._parent_pid == os.getpid(), 'can only test a child process'
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: can only test a child process
Assertion 'pa_atomic_load(&(b)->_ref) > 0' failed at ../src/pulsecore/memblock.c:682, function pa_memblock_unref(). Aborting.
Aborted (core dumped)
```

### PulseAudio Configuration
- Server: pulseaudio
- Default Sink: RDPSink (Remote Desktop audio sink)
- Windows IP: 172.21.240.1
- Environment set: `CHRONUS_PULSE_SERVER=tcp:172.21.240.1`

### Current Status
- Synthesizer starts successfully without verbose mode
- OSC server listening on 127.0.0.1:5005
- Commands are received (visible in logs if verbose)
- No audio output heard

## Commands Sent (No Audio Result)
```python
client.send_message('/mod/sine/gain', 0.9)      # High gain
client.send_message('/mod/filter/cutoff', 5000.0)  # Open filter
client.send_message('/mod/filter/q', 1.0)       # Low resonance
client.send_message('/engine/amp', 1.0)         # Legacy max amplitude
client.send_message('/engine/freq', 440.0)      # A440
client.send_message('/gate/adsr', 'on')         # Note ON
```

## Contrast with Testing
- During test scripts (test_modulehost_fixed.py, etc.), audio WAS working
- Tests ran with `source venv/bin/activate && python test_script.py`
- Now in tmux session, same synthesizer produces no sound

## Potential Issues
1. **PulseAudio bridge**: RDPSink may not be forwarding to Windows
2. **Environment variables**: May not be properly set in tmux context
3. **Audio device selection**: sounddevice showing default ALSA device, not explicit pulse
4. **Process isolation**: tmux session may have different audio context

## Next Steps
1. Test with standalone script outside tmux to verify audio still works
2. Check if PULSE_SERVER environment variable is set correctly
3. Verify Windows PulseAudio server is running and accepting connections
4. Test with explicit sounddevice backend selection