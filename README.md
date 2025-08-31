# Music Chronus
## AI-Collaborative Command-Line Modular Synthesizer

> *"Yo! Chronus, drop in some kick and snare for a DnB song..."*

A real-time modular synthesizer built for human-AI collaboration. Create music through conversation, build instruments on demand, and explore sounds that emerge from the space between human creativity and algorithmic precision.

**Status**: Phase 0 Complete (12/16 tests) + Phase 1A Complete | **Performance**: 5.9ms latency, zero underruns | **Architecture**: Validated & Working

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
| **Total Latency** | <20ms | **5.9ms** | ✅ Professional grade |
| **Audio Stability** | 0 dropouts | **Perfect** | ✅ 60+ second stress tests |
| **Control Response** | <5ms | **0.068ms** | ✅ Instant parameter changes |
| **Module Loading** | <100ms | **0.02ms** | ✅ Hot-swappable modules |
| **Throughput** | 1000 msg/sec | **1000+** | ✅ Handles rapid automation |

### Key Technical Discoveries

1. **Worker Pool Architecture Required** - On-demand process spawning takes 672ms (impossible for real-time), worker pools achieve 0.02ms
2. **Multiprocessing Beats Threading** - 5.7x faster for small audio buffers despite Python GIL
3. **Memory Bandwidth Limits Parallelism** - 2-3 concurrent workers max, regardless of CPU cores
4. **Zero-Copy Audio Transfer** - Shared memory achieves 0.042ms overhead between modules

## Current Architecture

```
Human Commands → CLI Process → OSC Messages (0.068ms) → Worker Pool
                                                           ↓
                                                      Synthesis Modules
                                                           ↓  
                                              Shared Memory (0.042ms)
                                                           ↓
                                               Audio Server (rtmixer)
                                                           ↓
                                                   Output (5.9ms)
                                                           ↓
                                                      Speakers
```

**Total System Latency: ~6ms** (14ms headroom vs industry standard 20ms target)

## Musical Philosophy

My music preferences are raw, authentic, aggressive sounding music - even classical has to be "driving." My DJing evolved from house music to techno to DnB. DnB is the most fun, along with hard, dark, organic sounding house/techno.

This isn't trying to copy Ableton or Studio One. It's creating a new category: **collaborative musical instruments** where human creativity directs AI implementation in real-time.

## Current Status

**Phase 0: Foundation Testing** - ✅ COMPLETE (12/16 tests, 4 MUS tests deferred)
- ✅ Audio performance validated (5.9ms latency, zero dropouts)
- ✅ Control systems proven (sub-millisecond response)  
- ✅ Architecture decided (multiprocessing + worker pools)
- ✅ Process management working (crash isolation, clean shutdown)

**Phase 1A: Core Audio Engine** - ✅ COMPLETE 
- ✅ **Working audio engine** - 60+ seconds continuous playback, zero underruns
- ✅ **Phase accumulator synthesis** - Clean 440Hz sine wave generation
- ✅ **Performance metrics** - 0.023ms mean callback, 6% CPU usage
- ✅ **Lock-free architecture** - Real-time safe audio generation
- ✅ **Clean lifecycle management** - Graceful start/stop with resource cleanup

**Phase 1B: Control Integration** - 🔄 IN PROGRESS
- OSC control thread for real-time parameter changes
- Lock-free parameter exchange between control and audio threads  
- **Goal**: Live frequency control while maintaining zero underruns

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

### Running the Phase 1A Audio Engine

```bash
# Activate environment
source venv/bin/activate

# Test the working audio engine
python3 audio_engine_v2.py

# Commands:
# start - Begin 440Hz sine wave generation
# stop  - Stop audio engine
# status - Show performance metrics
# quit  - Exit

# Run 60-second stability test
python3 test_60s_stability.py
```

**Expected Output**: Zero underruns, ~0.02ms callback times, 6% CPU usage

### Future Module System

The completed system will support:
```bash
# Load and connect modules
> load oscillator
> load filter
> patch oscillator > filter > output

# Set parameters
> set oscillator.freq 440
> set filter.cutoff 1000

# Create sequences
> sequence kick: x...x...x...x...
> play
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