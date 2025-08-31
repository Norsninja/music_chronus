# Music Chronus Test Suite

## Important Test Requirements

### ⚠️ Audio Device Isolation Required

**CRITICAL**: All audio tests must be run with **no background audio** playing. Background audio causes:
- Device contention and underruns
- False lockstep test failures
- Inaccurate timing measurements
- Resource allocation conflicts

Before running tests:
1. Stop all music/video players
2. Close browser tabs playing audio
3. Ensure no other audio applications are running
4. Verify PulseAudio is available: `pactl info`

## Test Organization

### Phase 0: Foundation Tests (75% Complete)
Located in `/tests/` directory:
- `test_RT*.py` - Real-time performance tests
- `test_IPC*.py` - Inter-process communication tests
- `test_PROC*.py` - Process architecture tests
- `test_MUS*.py` - Musical accuracy tests (deferred until modules exist)

### Phase 1 Tests
Located in project root:
- `test_supervisor.py` - Comprehensive supervisor test suite (7 scenarios)
- `test_failover_quick.py` - Focused failover timing test
- `test_phase1b_*.py` - OSC control integration tests

## Running Tests

### Virtual Environment Required
```bash
# Always activate venv first
source venv/bin/activate

# Run individual test
python test_failover_quick.py

# Run with clean audio pipeline
killall -9 pulseaudio  # Reset if having issues
python test_supervisor.py
```

### Quick Validation
For rapid validation of core functionality:
```bash
python test_failover_quick.py
```

Expected output:
- Detection time: <10ms
- Switch time: <1ms
- No audio underruns

### Comprehensive Testing
For full test suite (requires clean audio):
```bash
python test_supervisor.py
```

Tests:
1. Smoke test - Basic functionality
2. Lockstep test - Worker synchronization
3. Clean exit failover - SIGTERM handling
4. SIGKILL failover - Hard termination
5. Hang detection - Heartbeat timeout
6. Standby crash - Respawn capability
7. Resource hygiene - 50 cycles, zero leaks

## Performance Targets

| Test | Target | Note |
|------|--------|------|
| Detection p95 | <10ms | Sentinel trigger to handler |
| Switch completion | <10ms | Handler to standby active |
| Rebuild time | <500ms | New standby spawn |
| Audio continuity | Zero gap | No underruns during failover |
| Resource leaks | Zero | Across 50+ cycles |

## Common Issues

### "FD already registered" Errors
- **Cause**: Stale sentinel references after failover
- **Fix**: Applied in audio_supervisor.py - monitor refreshes worker refs

### Lockstep Test Failures
- **Cause**: Background audio interference
- **Fix**: Stop all audio before testing

### SIGTERM Not Detected
- **Cause**: Worker needs signal handler
- **Fix**: Applied - workers handle SIGTERM for clean exit

### High Underrun Count
- **Cause**: Audio device contention or CPU load
- **Fix**: Isolate audio device, close other applications

## Test Development Guidelines

1. **Isolation**: Each test should be independent
2. **Timing**: Use `time.monotonic_ns()` for precision
3. **Cleanup**: Always stop supervisor in finally blocks
4. **Assertions**: Verify both success and timing constraints
5. **Documentation**: Log why tests might fail

## Debugging Tips

- Use filtered output: `python test.py 2>/dev/null | grep "✅\|❌"`
- Check audio device: `pactl list sinks`
- Monitor processes: `watch -n 0.5 'ps aux | grep chronus'`
- Verify no leaks: `lsof -p <PID> | wc -l`

---

*Remember: Clean audio environment is essential for accurate test results!*