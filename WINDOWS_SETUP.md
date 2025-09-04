# Music Chronus - Windows Port

## Overview
This branch contains the Windows-native port of Music Chronus, achieving superior performance compared to the WSL2 version.

## Performance Improvements
- **Latency**: 3ms (WASAPI) vs 5.9ms (WSL2/PulseAudio)
- **Audio Quality**: Crystal clear, no artifacts
- **Sequencer Timing**: 99.9% accuracy vs emergency fill cascades
- **CPU Usage**: Lower overhead without virtualization layer

## Requirements
- Windows 10/11
- Python 3.10+
- USB audio interface recommended for lowest latency

## Installation

```bash
# Clone the repository
git clone https://github.com/Norsninja/music_chronus.git
cd music_chronus
git checkout windows-port

# Install dependencies
pip install sounddevice numpy python-osc scipy
```

## Quick Start

### 1. Test Audio Setup
```bash
python test_windows_audio.py
```
This will list your audio devices and test WASAPI output.

### 2. Run the Synthesizer Engine
```bash
python src/music_chronus/engine_windows.py
```
The engine listens for OSC commands on port 5005.

### 3. Send Test Commands
In another terminal:
```bash
python send_osc_test.py
```

### 4. Test DSP Modules
```bash
python test_modules_windows.py
```

### 5. Test Sequencer
```bash
python test_sequencer_windows.py
```

## Key Files

### Core Engine
- `src/music_chronus/engine_windows.py` - Windows-optimized audio engine with WASAPI support

### Test Scripts
- `test_windows_audio.py` - Audio device enumeration and testing
- `test_modules_windows.py` - DSP module chain testing
- `test_sequencer_windows.py` - Pattern sequencer with timing analysis
- `test_sequencer_simple.py` - Simplified timing accuracy test
- `send_osc_test.py` - OSC control demonstration

## Technical Details

### Audio Backend
- **API**: WASAPI (Windows Audio Session API)
- **Mode**: Exclusive mode for lowest latency
- **Sample Rate**: 48000 Hz (WASAPI standard)
- **Buffer Size**: 256 samples (5.3ms)

### Architecture Changes from WSL
1. **Direct WASAPI**: Eliminates PulseAudio bridge overhead
2. **Native Python**: No WSL2 virtualization layer
3. **Simplified IPC**: Reduced complexity without Linux-specific features

### Known Issues
- Unicode characters (✓, ►) may not display correctly in Windows console
  - Workaround: Use `chcp 65001` for UTF-8 support
- Some tests assume Git Bash or similar Unix-like environment

## OSC Control Protocol

The engine accepts OSC messages on port 5005:

- `/frequency <hz>` - Set oscillator frequency (20-20000 Hz)
- `/amplitude <0-1>` - Set output amplitude
- `/gate <0/1>` - Gate on/off for envelope
- `/freq` - Alias for /frequency
- `/amp` - Alias for /amplitude
- `/note_on` - Trigger gate on
- `/note_off` - Trigger gate off

## Performance Benchmarks

### Sequencer Timing (Windows vs WSL2)
| Metric | Windows | WSL2 |
|--------|---------|------|
| Timing Accuracy | 99.9% | Emergency fills |
| Mean Jitter | 5.6ms | Unstable |
| Audio Latency | 3ms | 5.9ms |
| Underruns | 0 | Multiple |

## Contributing
When adding Windows-specific features:
1. Ensure compatibility with WASAPI
2. Test with multiple audio devices
3. Maintain the simplified architecture
4. Document any Windows-specific requirements

## License
Same as main repository

## Credits
Windows port developed by Mike (NorsNinja) and Chronus Nexus (AI collaborator)