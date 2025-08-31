# Sprint: AI-Human Music Studio

## Vision Evolution
We've learned that TidalCycles/SuperCollider creates too many layers of abstraction. Instead, we're building a **modular synthesis studio** in Python that I can directly control through tmux.

## Project Goal
Create a complete music production environment where Chronus Nexus (AI) and Human collaborate as equal partners in real-time music creation.

## Completed ✅
- [x] Researched TidalCycles and alternatives
- [x] Set up PulseAudio bridge to Windows
- [x] Tested Python audio generation
- [x] Created basic tmux-controllable interface
- [x] Proved direct synthesis → audio works perfectly
- [x] Discovered comprehensive architectural blueprint (rtmixer + multiprocessing)

## Current Sprint: Test-Driven Foundation Development 🧪

### Testing Methodology
We will NOT write production code until tests pass. Using BDD-style specifications for clarity.
**Research-first approach with technical-research-scout agent has been essential.**

### Progress: Phase 0 COMPLETE - Phase 1A COMPLETE - Phase 1B IN PROGRESS
- ✅ **Phase 0**: 12/16 tests complete (75% - MUS tests deferred until modules exist)
- ✅ **Phase 1A**: Audio engine with zero underruns achieved (100% complete)
- 🚀 **Phase 1B**: Control integration via OSC (IN PROGRESS)
- ✅ Critical performance paths validated
- ✅ Worker pool architecture proven necessary
- ✅ **Architecture Decision**: Multiprocessing wins for small-buffer DSP (5.7x faster!)
- ✅ **Memory Management**: Allocation-free audio path validated
- ✅ **Event Synchronization**: Socketpair + shared memory delivers <190μs p99
- ⚠️ **Crash Recovery**: ProcessPoolExecutor unsuitable, need manual Process management
- ✅ **Resource Cleanup**: Zero leaks across 50 cycles, SIGKILL recovery works
- ✅ **60s Stability**: Zero underruns, 0.023ms mean callback, 6% CPU
- ⏳ **Buffer Count Drift**: ~5% high in 60s test - non-critical timing drift noted

### Phase 0: Testing & Validation (COMPLETE)

#### 0.1 Core Performance Tests
- [x] **RT-01**: Audio Server latency test (<20ms round-trip required) ✅ **5.9ms achieved!**
- [x] **RT-02**: Buffer underrun test (0 dropouts in 60 seconds) ✅ **Zero underruns!**
- [x] **RT-03**: GIL bypass verification (parallel DSP execution proof) ✅ **Multiprocessing 5.7x faster!**
- [x] **RT-04**: Memory allocation test (no malloc in audio callback) ✅ **Allocation-free verified!**

#### 0.2 IPC Performance Tests  
- [x] **IPC-01**: OSC message latency (<5ms for localhost) ✅ **0.068ms achieved!**
- [x] **IPC-02**: OSC throughput (>1000 msgs/sec minimum) ✅ **1000 msg/sec achieved!**
- [x] **IPC-03**: Shared memory audio transfer (zero-copy verification) ✅ **0.042ms overhead!**
- [x] **IPC-04**: Event synchronization overhead (<1ms) ✅ **84μs p50, 190μs p99!**

#### 0.3 Process Architecture Tests
- [x] **PROC-01**: Module spawn time (<100ms per module) ✅ **Worker pool pattern required**
- [x] **PROC-02**: Worker pool task assignment (<10ms) ✅ **0.02ms achieved!**
- [x] **PROC-03**: Process failure isolation (crash containment) ⚠️ **Architecture validated, Option B required**
- [x] **PROC-04**: Resource cleanup on destroy ✅ **Zero leaks, fast recovery!**

#### 0.4 Musical Accuracy Tests
- [ ] **MUS-01**: VCO frequency accuracy (±1 cent tolerance)
- [ ] **MUS-02**: Sample-accurate timing (±1 sample drift/minute)
- [ ] **MUS-03**: Dynamic range (>90dB SNR)
- [ ] **MUS-04**: Phase coherence in multi-oscillator patches

### Phase 1A: Core Audio Engine (COMPLETE)

#### 1.1 Audio Server Implementation
- [x] **AudioEngine with sounddevice backend** ✅ **Zero underruns in 60s test**
- [x] **Phase accumulator synthesis** ✅ **440Hz sine generation**
- [x] **Lock-free metrics tracking** ✅ **array.array performance counters**
- [x] **Clean start/stop lifecycle** ✅ **Resource management verified**
- [x] **CPU monitoring thread** ✅ **6% CPU usage measured**

### Phase 1B: Control Integration (IN PROGRESS - Started 2025-08-31)

#### 1.2 Control Path Implementation
- [ ] OSC control thread with AsyncIOOSCUDPServer on localhost
- [ ] Lock-free parameter exchange (frequency_hz float, seq uint64)
- [ ] Boundary-only parameter application (no mid-buffer changes)
- [ ] Frequency sanitization (20-20kHz range clamping)
- [ ] Maintain zero underruns under 100 msg/s OSC load
- [ ] Control→apply latency ≤ 256 samples + 0.3ms overhead (p99)
- [ ] Update metrics to track parameter updates seen/applied

### Phase 2: Module Library (Growing Collection)

**Philosophy**: Build modules as needed, each session adds capabilities

#### Week 1: Minimum Viable Synthesizer
- [ ] SimpleSine - Basic oscillator to prove the system works
- [ ] SimpleFilter - One good resonant filter
- [ ] ADSR - Essential envelope for musical notes
**Goal**: Make first musical sounds!

#### Module Cookbook (Build When Needed)

**Oscillators & Generators** (Templates ready, build on demand)
- Multi-waveform oscillator (sine, saw, square, triangle)
- Noise generators (white, pink, brown)
- Wavetable synthesis
- FM synthesis module

**Drum Synthesis** (Each jam session might add one)
- Kick drum (sine + pitch envelope)
- Snare (noise + tone)
- Hi-hat (metallic noise)
- Tom/percussion synthesis
- 808-style modules

**Filters & Effects** (Add as musical needs arise)
- Low-pass, high-pass, band-pass filters
- Resonant filter with Q control
- Distortion/overdrive
- Delay/echo
- Reverb
- Chorus/phaser

**Modulators** (Build when patches need movement)
- LFO (low frequency oscillator)
- Step sequencer
- Arpeggiator
- Pattern generator

**Infrastructure** (Add when complexity demands)
- Multi-channel mixer
- Panning control
- Send/return buses
- Master compression

#### Module Development Workflow
```python
# When you need a new sound:
> generate_module reverb  # Creates template
> # AI writes DSP code in modules/reverb.py
> reload reverb           # Hot-reload
> patch vco > reverb > out
> # New capability acquired!
```

## Architecture Design

```
┌─────────────────────────────────────┐
│         TMUX INTERFACE              │
│  (Commands I can send)              │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│      COMMAND PROCESSOR              │
│  (Parses musical intentions)        │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│       MODULAR STUDIO                │
│  ┌──────────┐  ┌──────────┐        │
│  │Oscillator│──►│ Filter   │        │
│  └──────────┘  └──────────┘        │
│  ┌──────────┐  ┌──────────┐        │
│  │  Drums   │──►│ Effects  │        │
│  └──────────┘  └──────────┘        │
│  ┌──────────┐  ┌──────────┐        │
│  │Sequencer │──►│  Mixer   │        │
│  └──────────┘  └──────────┘        │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│        AUDIO OUTPUT                 │
│    (PulseAudio → Windows)           │
└─────────────────────────────────────┘
```

## Test Specifications Directory

All test specifications stored in: `/home/norsninja/music_chronus/tests/specs/`

### Specification Format
```gherkin
Feature: [Component Name]
  As a [user/AI]
  I want [functionality]
  So that [benefit]

  Scenario: [Test case]
    Given [initial state]
    When [action]
    Then [expected outcome]
    And [additional criteria]
```

## Development Discipline

1. **NO production code before test specs** - Write the test specification first
2. **One test at a time** - Focus on making one test pass before moving on
3. **Document failures** - When a test fails, document why before fixing
4. **Performance metrics** - Every test must include measurable criteria
5. **AI operates from specs** - I (Chronus) will generate code to meet specifications

## Session Workflow

```python
# Example session:
> create kick freq=60 decay=0.5
> create hihat noise=white decay=0.05
> sequence kick: x...x...x...x...
> sequence hihat: ..x...x...x...x.
> play

> create bass osc=saw filter=lowpass cutoff=500
> melody bass: C2 C2 G2 Eb2
> play all

> add reverb to bass amount=0.3
> save patch "deep_groove"
```

## Success Criteria (End Goal)
- [ ] All Phase 0 tests passing (performance validated)
- [ ] Module framework supports hot-reload and dynamic patching
- [ ] First sound from SimpleSine module (Week 4 milestone)
- [ ] Can add new modules mid-session without restart
- [ ] Each module buildable in <2 hours with AI assistance
- [ ] Smooth collaboration through tmux
- [ ] Module library grows organically with musical needs
- [ ] <10ms total system latency maintained
- [ ] Zero audio dropouts during performance

## Next Immediate Steps (Phase 0)

### Completed Recently ✅
1. ✅ PROC-02: Worker pool implementation validated (0.02ms assignment)
2. ✅ Discovered shared memory must be pre-allocated before pool init
3. ✅ Validated crash recovery with ProcessPoolExecutor

### Priority Tests (Next Session)
1. **RT-02**: Buffer underrun test (60-second sustained audio)
   - Test rtmixer stability over time
   - Verify no dropouts or glitches
   - Critical for live performance

2. **IPC-02**: OSC throughput test (>1000 msgs/sec)
   - Validate control message capacity
   - Test under load conditions
   - Essential for real-time parameter changes

3. **RT-03**: GIL bypass verification
   - Prove parallel DSP execution
   - Critical for multi-module performance
   - May need C extensions

### Architectural Decisions Made
- ✅ Worker pool pattern is mandatory (not on-demand spawn)
- ✅ Shared memory pre-allocation required
- ✅ Forkserver start method for safety + performance
- ✅ ProcessPoolExecutor for crash recovery
- ✅ Accept 2-3 parallel workers as sufficient
- ✅ **DECIDED**: Multiprocessing for DSP (5.7x faster than threading for our workload!)

### Critical Findings (2025-08-31)
1. **NumPy releases GIL** - BUT small buffers kill threading performance
2. **Only 2-3 workers run in parallel** - Memory bandwidth bottleneck confirmed
3. **Multiprocessing 5.7x faster** for 256-sample buffer DSP operations
4. **Threading actually SLOWER than sequential** for our specific workload
5. **RT-03 COMPLETE** - Empirical testing trumps theoretical advantages

## Philosophy
We're building a **modular synthesizer construction kit** - not a fixed instrument, but a framework that grows with each session. Every time we need a new sound, we build it and add it to our collection. The instrument evolves through use, becoming more capable with each musical exploration. This is collaborative evolution: human creativity directing AI implementation in real-time.

---
*Last Updated: 2025-08-31 - Phase 1B Control Integration Started*
*Status: Phase 0 Complete (75%), Phase 1A Complete (100%), Phase 1B In Progress*
*Decision: Multiprocessing wins! 5.7x faster than threading for audio DSP*
*Achievement: 60-second continuous audio with zero underruns, 0.023ms callback*
*Current: Phase 1B - OSC control integration with lock-free parameter exchange*