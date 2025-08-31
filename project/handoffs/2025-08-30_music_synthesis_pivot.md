# Session Handoff: Python Modular Synthesis Architecture Discovery

**Created**: 2025-08-30 14:34:16  
**From Session**: opus-4-1-20250805  
**To**: Next Chronus Instance  
**Context Window**: 61% - Still functional

## 🎯 Critical Context

Pivoted from TidalCycles/SuperCollider (6-layer audio routing nightmare in WSL2) to Python-based modular synthesis. Discovered comprehensive architectural blueprint for Python real-time audio that solves all latency/GIL issues using multi-process architecture with rtmixer and dual IPC strategy.

## ✅ What Was Accomplished

### 1. Audio Pipeline Setup

- Configured PulseAudio bridge from WSL2 to Windows host (tcp:172.21.240.1:4713)
- Validated audio output through Python/paplay
- Created basic synthesis modules using NumPy/SciPy

### 2. TidalCycles Investigation and Abandonment

- Attempted full TidalCycles/SuperCollider/JACK setup
- Encountered insurmountable complexity: TidalCycles → SuperDirt → JACK → ALSA → PulseAudio → Windows
- Confirmed SuperCollider requires JACK, cannot use PulseAudio directly
- Decision: Too many abstraction layers for reliable real-time performance

### 3. Python Synthesis Foundation

- Built working sound generation with NumPy
- Created tmux-controllable music interface
- Implemented basic oscillators, envelopes, and sequencing
- Validated sub-second audio generation and playback

### 4. Architectural Research Discovery

- Found comprehensive blueprint for professional Python modular synthesis
- Key insights: rtmixer for C-level audio callbacks, multiprocessing for true parallelism
- OSC for control signals, shared memory for audio data
- Matches our Eurorack modular vision perfectly

## 🚧 Current Working State

### What IS Working:

- ✅ PulseAudio bridge - WSL2 to Windows audio working perfectly
- ✅ Python audio generation - NumPy synthesis with paplay output
- ✅ Tmux control interface - Can send commands to running music session
- ✅ Basic synthesis - Sine, saw, square waves, ADSR envelopes

### What is PARTIALLY Working:

- ⏳ Sequencing - Basic pattern playback works but lacks proper timing engine
- ⏳ Module system - Have basic modules but not proper multi-process architecture

### What is NOT Working:

- ❌ Real-time performance - Current approach has ~50ms latency, needs rtmixer
- ❌ Proper IPC - No OSC or shared memory implementation yet
- ❌ TidalCycles/SuperCollider - Abandoned due to complexity

### Known Issues:

- 🐛 Python GIL prevents true parallelism in single process
- 🐛 Garbage collection causes audio glitches without C-level callback
- 🐛 Current sequencing uses Python sleep() - not sample-accurate

## 🚨 Next Immediate Steps

1. **Implement rtmixer Audio Server**
   - Create C-callback based audio engine
   - Test latency (target <20ms)

2. **Build First Module with Multiprocessing**
   - VCO module in separate process
   - OSC control implementation
   - Shared memory audio output

3. **Create Session Manager**
   - libtmux integration
   - Command parser for create/patch/set/destroy
   - Module lifecycle management

## 📁 Files Created/Modified

**Created:**

- `/home/norsninja/music_chronus/sprint.md` - Updated project roadmap for modular synthesis
- `/home/norsninja/music_chronus/music_lab.py` - Core synthesis experiments
- `/home/norsninja/music_chronus/live_music.py` - Interactive music interface
- `/home/norsninja/music_chronus/test_sound.py` - Audio pipeline validation
- `/home/norsninja/music_chronus/start_music_pulseaudio.sh` - Audio setup script
- `/home/norsninja/music_chronus/AUDIO_SETUP.md` - WSL2 audio configuration guide

**Modified:**

- `/home/norsninja/music_chronus/CLAUDE.md` - Contains art project context (needs conversion for music)
- `~/.asoundrc` - ALSA configuration for PulseAudio routing

## 💡 Key Insights/Learnings

1. TidalCycles/SuperCollider creates too many abstraction layers for WSL2
2. Python can do real-time audio but ONLY with C-level callbacks (rtmixer)
3. Multi-process architecture bypasses GIL limitations completely
4. OSC + shared memory is industry standard for good reason
5. Eurorack paradigm maps perfectly to software modules
6. Sample-accurate timing requires look-ahead buffering

## 🔧 Technical Notes

- PulseAudio server on Windows: tcp:172.21.240.1:4713
- Sample rate: 44100Hz standard throughout
- Buffer size: 1024 samples recommended for rtmixer
- OSC over UDP for control, multiprocessing.shared_memory for audio
- Each module needs own process to utilize multiple CPU cores
- tmux session "composer" contains current live_music.py instance

## 📊 Progress Metrics

- Phase/Sprint Progress: 15% (foundation validated, architecture defined)
- Tests Passing: Basic audio working
- Context Window at Handoff: 61%

---

_Handoff prepared by Chronus opus-4-1-20250805_  
_Successfully pivoted from TidalCycles to Python modular synthesis with comprehensive architecture blueprint_