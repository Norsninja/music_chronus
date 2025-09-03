# WSL2 Audio Caveats

**Last Updated**: 2025-09-03  
**Status**: Known limitations documented

## Overview

WSL2's audio bridge through PulseAudio to Windows introduces artifacts that cannot be fixed at the application level. This affects ALL audio applications running in WSL2, not just our synthesizer.

## Known Issues

### Audio Artifacts
- **Symptom**: Ethereal popping/clicking sounds, similar to vinyl record noise
- **Frequency**: Intermittent, increases with system load
- **Root Cause**: WSL2 PulseAudio bridge buffering and timing
- **First Reported**: 2022 (ongoing GitHub issues)
- **Status**: Not fixable in application code

### Test Results
Simple audio tests confirm WSL2 is the source:
- Python sounddevice playback: POPPING
- WAV file playback (aplay): POPPING  
- ALSA speaker-test: Minimal popping (different audio path)

## Mitigation Strategies

### Windows Host Settings

#### Power Management
```powershell
# Run as Administrator
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  # High Performance
powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR CPMINCORES 100
powercfg /setactive SCHEME_CURRENT
```

#### Audio Configuration
1. Open Sound Settings → Device Properties
2. Set Default Format: 44100 Hz, 16 bit
3. Disable all enhancements
4. Disable exclusive mode (allows system sounds)

#### WSL2 Configuration
Create/edit `%USERPROFILE%\.wslconfig`:
```ini
[wsl2]
processors=4  # Adjust based on your CPU
memory=8GB    # Sufficient for audio processing
```

### PulseAudio Tuning

#### Option 1: Increase Buffer Size
Create `~/.pulse/daemon.conf` in WSL2:
```ini
default-fragments = 8
default-fragment-size-msec = 10
```

#### Option 2: External PulseAudio Server
Run PulseAudio natively on Windows and connect from WSL2:
```bash
# In WSL2
export PULSE_SERVER=tcp:$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):4713
```

### Application-Level Workarounds

#### Use Matrix B or D Configuration
```bash
# Matrix B (balanced)
export CHRONUS_LEAD_TARGET=3
export CHRONUS_MAX_CATCHUP=3

# Matrix D (maximum stability)
export CHRONUS_KEEP_AFTER_READ=3
export CHRONUS_PREFILL_BUFFERS=5
```

#### Larger Audio Buffers
```bash
export CHRONUS_BUFFER_SIZE=1024  # Double the buffer size
export CHRONUS_NUM_BUFFERS=32    # More buffers for stability
```

## Verification Methods

### Test WSL2 Audio Path
```python
import sounddevice as sd
import numpy as np

# If this has pops, it's WSL2, not your application
sr = 44100
t = np.linspace(0, 3, sr * 3)
audio = 0.2 * np.sin(2 * np.pi * 440 * t)
sd.play(audio, sr)
sd.wait()
```

### Offline Rendering Test
Generate audio to file, then play on Windows to verify clean output:
```bash
# Future: python tools/render_wav.py --patch sine --output test.wav
# Copy to Windows and play to confirm no artifacts in generation
```

## Deployment Recommendations

### Development (WSL2)
- Accept minor artifacts as known limitation
- Use for coding, testing logic, not audio quality
- Document that pops are environmental, not bugs

### Production/Performance
- **Option 1**: Native Linux (preferred)
  - Dual boot or dedicated machine
  - Full ALSA/JACK support
  - Zero WSL2 overhead
  
- **Option 2**: Windows Native
  - Install Python directly on Windows
  - Use WASAPI exclusive mode or ASIO
  - Bypass WSL2 entirely

### Testing Strategy
1. Develop and test logic in WSL2
2. Validate audio quality on native platform
3. Document environment in bug reports

## Summary

WSL2 audio artifacts are a **known infrastructure limitation**, not application bugs. Our synthesizer code is production-ready; the deployment environment determines audio quality.

For clean audio: Deploy on native Linux or Windows native.  
For development: WSL2 is acceptable with documented caveats.

## References

- [WSL2 Audio Issues (GitHub)](https://github.com/microsoft/WSL/issues?q=audio+pops)
- [PulseAudio on WSL2 Guide](https://github.com/microsoft/wslg/wiki/PulseAudio-Support)
- [Windows Audio Latency](https://docs.microsoft.com/en-us/windows-hardware/drivers/audio/low-latency-audio)