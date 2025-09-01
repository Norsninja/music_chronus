# Music Chronus
## AI-Collaborative Command-Line Modular Synthesizer

> *"Yo! Chronus, drop in some kick and snare for a DnB song..."*

A real-time modular synthesizer built for human-AI collaboration. Create music through conversation, build instruments on demand, and explore sounds that emerge from the space between human creativity and algorithmic precision.

**Status**: Phase 2 Complete - Fault-Tolerant Modular Synthesis | **Performance**: 5.8ms latency, <50ms failover | **Architecture**: Slot-based with zero-allocation

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

## Why This Exists

Existing music software wasn't built for AI collaboration. They assume humans operating GUIs or learning complex syntax. We needed something that's:

- **Headless by design** - Works without displays or interactive modes
- **Command-driven** - Natural for AI agents to operate  
- **Modular** - Can grow and adapt to new ideas
- **Real-time** - No waiting for compilation or rendering
- **Collaborative** - Built for human-AI partnership

## What We've Proven (Technical Validation)

Through rigorous testing, we've validated that a Python-based real-time synthesizer is not only possible, but **competitive with professional DAWs**:

| Component | Target | Achieved | Status |
|-----------|--------|----------|--------|
| **Total Latency** | <20ms | **5.8ms** | ✅ Professional grade |
| **Audio Stability** | 0 dropouts | **Perfect** | ✅ 60+ second stress tests |
| **Control Response** | <5ms | **0.068ms** | ✅ Instant parameter changes |
| **Module Loading** | <100ms | **0.02ms** | ✅ Hot-swappable modules |
| **Throughput** | 1000 msg/sec | **1000+** | ✅ Handles rapid automation |
| **Failover Time** | <100ms | **<50ms** | ✅ Near-seamless recovery |

### Key Technical Discoveries

1. **Worker Pool Architecture Required** - On-demand process spawning takes 672ms (impossible for real-time), worker pools achieve 0.02ms
2. **Multiprocessing Beats Threading** - 5.7x faster for small audio buffers despite Python GIL
3. **Memory Bandwidth Limits Parallelism** - 2-3 concurrent workers max, regardless of CPU cores
4. **Zero-Copy Audio Transfer** - Shared memory achieves 0.042ms overhead between modules

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

This isn't trying to copy Ableton or Studio One. It's creating a new category: **collaborative musical instruments** where human creativity directs AI implementation in real-time.

## Current Status

**Phase 0: Foundation Testing** - ✅ COMPLETE (12/16 tests, 4 MUS tests deferred)
- ✅ Audio performance validated (5.8ms latency, zero dropouts)
- ✅ Control systems proven (sub-millisecond response)  
- ✅ Architecture decided (multiprocessing + worker pools)
- ✅ Process management working (crash isolation, clean shutdown)

**Phase 1: Core Audio Engine** - ✅ COMPLETE 
- ✅ **Working audio engine** - 60+ seconds continuous playback, zero underruns
- ✅ **Phase accumulator synthesis** - Clean 440Hz sine wave generation
- ✅ **Performance metrics** - 0.023ms mean callback, 6% CPU usage
- ✅ **Lock-free architecture** - Real-time safe audio generation
- ✅ **OSC control integration** - Live parameter changes with zero underruns

**Phase 2: Modular Synthesis** - ✅ COMPLETE
- ✅ **Fault-tolerant architecture** - <50ms failover with slot-based design
- ✅ **Module chain working** - SimpleSine → ADSR → BiquadFilter
- ✅ **Zero-allocation audio path** - Per-process view rebinding pattern
- ✅ **Command continuity** - Full control before, during, and after failover

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
# Current synthesizer chain: SimpleSine → ADSR → BiquadFilter

# Test commands
/test                       # Play test tone (440Hz)

# Module parameters
/mod/sine/freq <hz>        # Oscillator frequency (20-20000)
/mod/sine/gain <0-1>       # Oscillator gain
/mod/filter/cutoff <hz>    # Filter cutoff frequency
/mod/filter/resonance <q>  # Filter Q factor

# ADSR envelope
/gate/adsr <0|1>           # Gate on/off
/mod/adsr/attack <ms>      # Attack time
/mod/adsr/decay <ms>       # Decay time  
/mod/adsr/sustain <0-1>    # Sustain level
/mod/adsr/release <ms>     # Release time
```

### Environment Variables

```bash
# Enable verbose logging
export CHRONUS_VERBOSE=1

# WSL2/WSLg users - set PulseAudio server
export PULSE_SERVER=/mnt/wslg/PulseServer
```

## Fault Tolerance

The synthesizer implements a dual-slot architecture for seamless failover:

- **Slot 0 (Primary)**: Active audio processing worker
- **Slot 1 (Standby)**: Hot standby ready to take over
- **Failover Time**: <50ms audio interruption on worker crash
- **Command Continuity**: Full control maintained during failover
- **Zero Allocation**: Audio callback uses pre-allocated buffers only

When a worker crashes, the system automatically:
1. Detects failure via heartbeat timeout
2. Switches audio callback to standby slot
3. Spawns replacement worker in failed slot
4. Maintains all parameter states

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

- [Project Vision](docs/PROJECT_VISION.md) - Detailed motivation and goals
- [Technical Review](docs/COMPREHENSIVE_TEST_REVIEW.md) - Complete testing results
- [Architecture Decisions](docs/architecture_decision_worker_pools.md) - Key technical choices
- [Performance Benchmarks](tests/results/) - Detailed test results
- [Current Sprint](sprint.md) - Development progress and next steps

## License

*Open source - encouraging collaborative innovation*

---

*"This is about pioneering a new form of musical expression - one that couldn't exist without AI collaboration."*