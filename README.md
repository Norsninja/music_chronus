# Music Chronus
## Headless Modular Synthesizer Studio for Human-AI Music Creation

> *"Yo! Chronus, drop in some kick and snare for a DnB song..."*

A real-time modular synthesizer built for human-AI collaboration. Create music through conversation, build instruments on demand, and explore sounds that emerge from the space between human creativity and algorithmic precision.

**This synthesizer contains no AI** - it's a headless instrument designed for CLI-based agentic AI (Claude Code, Gemini CLI, GPT's Codex) to use alongside humans. Both are equal musicians sharing the same tool.

**Status**: Phase 3 Complete - Dynamic Routing & Recording | **Performance**: 5.8ms latency, <50ms failover | **First AI Composition**: [39-second musical piece](recordings/chronus_first_musical_session.wav) (Sept 3, 2025)

---

## The Vision

This project solves a creative problem: **I want to collaborate with AI to make music.**

Instead of fighting with complex syntax or GUI limitations, imagine having a conversation like this:

```
You: "Chronus, drop a dirty bass at 175 BPM"
AI:  > load bass_module
     > set bass.freq 55
     > set bass.distortion 0.7
     > sequence bass: x.x.x.x.x.x.x.x.

You: "Nice! Now add a 303-style synth with call and response"
AI:  > load tb303_module  
     > patch tb303 > filter > delay
     > sequence tb303: ..x...x.x.x.....x
```

This is **collaborative music creation** - not just using AI as a tool, but as a creative partner.

## 🎵 Listen: First AI-Human Musical Collaboration
**[recordings/chronus_first_musical_session.wav](recordings/chronus_first_musical_session.wav)** - September 3, 2025

*Before diving into why and how, hear what we've created together: 39 seconds of an AI (Chronus Nexus) composing music by thinking through synthesis parameters - not ML generation, but reasoning about frequencies, envelopes, and signal flow.*

## Why This Exists

We tried TidalCycles (which is excellent) but needed something more direct for AI operation. Existing music software wasn't built for AI collaboration - they assume humans operating GUIs or learning complex syntax. We needed something that's:

- **Headless by design** - Works without displays or interactive modes
- **Command-driven** - Natural for AI agents to operate  
- **Modular** - Can grow and adapt to new ideas
- **Real-time** - No waiting for compilation or rendering
- **Collaborative** - Built for human-AI partnership

## What We've Proven

We've built a real-time synthesizer in Python that works. It's fast enough for live performance (5.8ms latency), stable enough for recording (zero dropouts), and flexible enough for AI to operate alongside humans.

**[See detailed technical metrics →](docs/TECHNICAL.md)**

## Current Architecture

```
Human Commands → CLI Process → OSC Messages (0.068ms) → Worker Pool
                                                           ↓
                                                   [Slot 0: Primary]
                                                   [Slot 1: Standby]
                                                           ↓
                                                      Synthesis Modules
                                                           ↓  
                                              Shared Memory (0.042ms)
                                                           ↓
                                               Audio Server (rtmixer)
                                                           ↓
                                                   Output (5.8ms)
                                                           ↓
                                                      Speakers
```

**Total System Latency: ~6ms** (14ms headroom vs industry standard 20ms target)
**Fault Tolerance: <50ms failover** with dual-slot architecture

## Musical Philosophy

My music preferences are raw, authentic, aggressive sounding music - even classical has to be "driving." My DJing evolved from house music to techno to DnB. DnB is the most fun, along with hard, dark, organic sounding house/techno.

### AI Collaboration: Look Mum, We Use a Computer...
On September 3, 2025, Chronus Nexus (AI) and I created our first musical piece together. Not through ML models or pattern matching, but through the AI reasoning about synthesis parameters and musical structure. The AI operates the synthesizer just like I do - through commands and parameter control.

This isn't trying to copy Ableton or Studio One. It's creating a new category: **collaborative musical instruments** where human creativity and AI reasoning merge in real-time.

## Current Status

The synthesizer is **ready for music creation**. We've proven it works, recorded our first session, and validated the architecture. The aspirational vision of "drop a dirty bass" is getting closer with each session.

**Latest Achievement**: First AI-composed music through synthesis reasoning (not ML generation)

**[Full development history →](docs/TECHNICAL.md#development-phases)**

## Development Approach

- **Test-Driven Development** - All performance claims backed by empirical testing
- **Research-First** - Technical decisions based on investigation, not assumptions  
- **Modular Construction Kit** - Build instruments as needed, not everything upfront
- **Collaborative Evolution** - The instrument grows with each musical session

## Technology Stack

- **Python 3** - Core language with multiprocessing
- **rtmixer** - C-level audio callbacks for minimal latency
- **NumPy/SciPy** - DSP operations (pre-imported in worker pools)
- **python-osc** - Real-time control messaging
- **Shared Memory** - Zero-copy audio transfer between modules
- **tmux** - Session management for AI collaboration

## System Requirements & Installation

### Requirements
- Python 3.8+
- Ubuntu/Debian (WSL2 supported)
- PulseAudio configured (for WSL2 → Windows audio)

### Installation

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y libportaudio2 libportaudio2-dev libsndfile1 libsndfile1-dev libpulse-dev pulseaudio-utils

# Setup Python environment
./setup.sh
# Or manually:
# python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Verify audio configuration
pactl info
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

### Testing

We follow Test-Driven Development:

```bash
# Run all tests
pytest tests/

# Run specific test category
pytest tests/test_RT* -v  # Real-time performance tests
pytest tests/test_IPC* -v # Communication tests
```

## Project Structure

```
music_chronus/
├── audio_engine_v2.py        # Phase 1A: Working audio engine
├── test_60s_stability.py     # Audio engine validation test
├── tests/
│   ├── specs/                # BDD test specifications  
│   ├── results/              # Performance benchmarks
│   └── test_*.py             # Test implementations
├── docs/
│   ├── phase1a_research.md   # Audio engine implementation patterns
│   └── COMPREHENSIVE_TEST_REVIEW.md  # Complete test results
├── project/handoffs/         # Session continuity
├── sprint.md                 # Current development status  
├── CLAUDE.md                 # AI collaborator context
└── requirements.txt          # Dependencies
```

## Future Vision

This isn't just about making sounds - it's about pioneering human-AI collaboration in creative domains. Future evolution includes:

- **Multimodal AI Integration** - Real-time models that can "hear" and provide feedback
- **Expanded Module Library** - Community-contributed instruments and effects
- **Session Recording** - Document and share collaborative music creation
- **Live Performance** - AI as bandmate, not just tool

## Getting Started

### Quick Start

```bash
# 1. Activate environment
source venv/bin/activate

# 2. Start the synthesizer
make run
# Or directly: python -m src.music_chronus.supervisor_v2_slots_fixed

# 3. From another terminal, send OSC commands:
# Test tone
python -c "from pythonosc import udp_client; client = udp_client.SimpleUDPClient('127.0.0.1', 5005); client.send_message('/test', [])"

# Control frequency
python -c "from pythonosc import udp_client; client = udp_client.SimpleUDPClient('127.0.0.1', 5005); client.send_message('/mod/sine/freq', 880.0)"

# Gate control
python -c "from pythonosc import udp_client; client = udp_client.SimpleUDPClient('127.0.0.1', 5005); client.send_message('/gate/adsr', 1)"

# Filter control
python -c "from pythonosc import udp_client; client = udp_client.SimpleUDPClient('127.0.0.1', 5005); client.send_message('/mod/filter/cutoff', 1000.0)"
```

**Expected Output**: Clean sine wave with ADSR envelope and filtering, <50ms failover on worker crash

### Working OSC Commands

```python
# Recording (NEW - Capture your sessions!)
/record/start [filename]    # Start recording to WAV
/record/stop               # Stop and save recording
/record/status            # Show recording state

# Dynamic Patching (Router Mode)
/patch/create <id> <type>           # Create module instance
/patch/connect <source> <dest>      # Connect modules
/patch/commit                       # Activate patch with <50ms switch
/patch/abort                        # Cancel patch building

# Module Control
/mod/<module>/<param> <value>      # Set any module parameter
/gate/<module> <0|1>               # Gate control for envelopes

# Examples
/mod/sine/freq 440.0              # Oscillator frequency
/mod/filter/cutoff 2000.0         # Filter cutoff
/mod/adsr/attack 10.0             # ADSR attack time (ms)
```

### Environment Variables

```bash
# Enable verbose logging
export CHRONUS_VERBOSE=1

# WSL2/WSLg users - set PulseAudio server
export PULSE_SERVER=/mnt/wslg/PulseServer
```

## Recording Sessions

Capture your musical collaborations to WAV files:

```bash
# Start recording with auto-generated filename
/record/start                    # Creates recording_YYYYMMDD_HHMMSS.wav

# Start with custom filename
/record/start my_session.wav    # Creates recordings/my_session.wav

# Stop and save
/record/stop                    # Saves file and reports duration
```

**Why Record?** 
- Bypass WSL2 playback artifacts (recordings are clean!)
- Document human-AI musical collaboration
- Share your creations
- Analyze synthesis quality

**[Technical details →](docs/TECHNICAL.md#recording-technical-details)**

## Troubleshooting

### No Audio Output
```bash
# Check PulseAudio is running
pactl info

# For WSL2 users, set PULSE_SERVER
export PULSE_SERVER=/mnt/wslg/PulseServer

# Verify audio devices
python -c "import sounddevice; print(sounddevice.query_devices())"
```

### OSC Commands Not Working
```bash
# Verify OSC server is listening
netstat -tuln | grep 5005

# Test with simple message
python -c "from pythonosc import udp_client; client = udp_client.SimpleUDPClient('127.0.0.1', 5005); client.send_message('/test', [])"
```

### Worker Crashes
```bash
# Enable verbose logging to see failover
export CHRONUS_VERBOSE=1
python -m src.music_chronus.supervisor_v2_slots_fixed --verbose
```

## Contributing

This project is in active development. We welcome:
- **Musicians** interested in AI collaboration
- **Developers** excited about real-time audio in Python
- **Researchers** exploring human-AI creative partnerships
- **Anyone** curious about the future of music creation

## Documentation

- [Technical Details](docs/TECHNICAL.md) - Performance metrics, architecture, WSL2 notes
- [Recording Implementation](docs/recording_feature_implementation_plan.md) - How recording works
- [WSL2 Audio Caveats](docs/wsl2_audio_caveats.md) - Known issues and workarounds
- [First Session Analysis](recordings/README.md) - About the historic first AI composition
- [Current Sprint](sprint.md) - Development progress and next steps

## License

*Open source - encouraging collaborative innovation*

---

*"This is about pioneering a new form of musical expression - one that couldn't exist without AI collaboration."*