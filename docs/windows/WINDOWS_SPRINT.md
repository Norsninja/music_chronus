# Music Chronus - Windows Native Sprint Plan
**Last Updated**: 2025-09-05  
**Sprint Duration**: 4 weeks  
**Goal**: Port the full modular synthesizer architecture to Windows while maintaining our vision

## 🎯 Sprint Objective

Build a Windows-native modular synthesizer that:
- Preserves our dual-slot supervisor architecture for fault tolerance
- Achieves 3ms latency with WASAPI exclusive mode
- Enables hot-reload and dynamic module creation
- Supports natural language musical commands
- Maintains process isolation for stability

## 📋 Current Status

### ✅ Completed
- [x] Research Windows multiprocessing (spawn, forkserver, shared memory)
- [x] Sprint planning and architecture documentation
- [x] Performance benchmarks validated (<2ms pool assignment)

### 🚀 Ready to Implement
- [ ] Phase 0: Baseline configuration - **IN PROGRESS**
- [ ] Phase 1: WASAPI in supervisors
- [ ] Phase 2: OSC canonicalization
- [ ] Phase 2.5: Module sandbox pool
- [ ] Phase 3-7: Full architecture

### ✅ Proven on Windows
- 3ms audio latency achieved with WASAPI
- 99.9% sequencer timing accuracy
- Distortion and acid filter modules working
- Recording capability functional

### ⚠️ Missing Critical Features
- Process isolation for modules
- Hot-reload capability
- Dynamic module creation
- Natural language interface
- Worker pool for module sandboxing

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────┐
│            SUPERVISOR PROCESS                │
│                                              │
│  ┌──────────────┐    ┌──────────────┐      │
│  │ ACTIVE SLOT  │    │ STANDBY SLOT │      │
│  │              │    │              │      │
│  │ Direct DSP   │    │ Module Pool  │      │
│  │ (No IPC)     │    │ (4 workers)  │      │
│  │ 3ms latency  │    │ Build/Test   │      │
│  └──────────────┘    └──────────────┘      │
│         ▲                    │              │
│         │      commit        │              │
│         └────────────────────┘              │
└─────────────────────────────────────────────┘
```

## 📅 Phase Breakdown

### Phase 0: Baseline Configuration ⏱️ Day 1
- [ ] Confirm WASAPI device selection (48kHz, 256 samples)
- [ ] Set Windows High Performance power plan
- [ ] Validate AB13X USB Audio device
- [ ] Document env variables and defaults

### Phase 1: WASAPI in Supervisors ⏱️ Days 2-3
- [ ] Add Windows device selection to supervisor_v2_slots
- [ ] Force `spawn` start method on Windows
- [ ] Maintain zero-allocation callbacks
- [ ] Test with existing modules

### Phase 2: OSC Canonicalization ⏱️ Day 4
- [ ] Implement `/mod/<id>/<param>` pattern
- [ ] Add `/gate/<id>` standard
- [ ] Create compatibility aliases
- [ ] Update all test scripts

### Phase 2.5: Module Sandbox Pool 🔑 ⏱️ Days 5-8
- [ ] Implement Windows-compatible worker pool
- [ ] Add to standby slot only
- [ ] Preload DSP libraries in initializer
- [ ] Test crash containment
- [ ] Validate build/warmup/test cycle

### Phase 3: Sequencer Re-enable ⏱️ Days 9-10
- [ ] Wire SequencerManager back into v3
- [ ] Emit to both command rings
- [ ] Test pattern persistence across commits
- [ ] Validate timing accuracy

### Phase 4: Router Commit Flow ⏱️ Days 11-12
- [ ] Set Windows defaults for env knobs
- [ ] Document minimal "no-knob" flow
- [ ] Test patch building and commit
- [ ] Measure commit latency

### Phase 5: Windows Test Suite ⏱️ Days 13-15
- [ ] Port ring buffer tests
- [ ] Create WASAPI integration tests
- [ ] Add module sandbox tests
- [ ] Write sequencer timing tests
- [ ] Mark Linux tests as skipped

### Phase 6: Performance Validation ⏱️ Days 16-17
- [ ] 60-second underrun-free operation
- [ ] Failover <50ms measurement
- [ ] Sequencer jitter ±1 buffer
- [ ] Module spawn <100ms

### Phase 7: Natural Language Parser 🚀 ⏱️ Days 18-21
- [ ] Design grammar for musical commands
- [ ] Build intent → OSC mapper
- [ ] Add context cache for current patch
- [ ] Create command snapshots
- [ ] E2E validation tests

### Phase 8: Documentation & Polish ⏱️ Days 22-24
- [ ] Update README for Windows
- [ ] Create module development guide
- [ ] Document natural language commands
- [ ] Performance tuning guide
- [ ] Record demo session

## 🎮 Success Criteria

### Core Functionality
- [x] 3ms audio latency maintained
- [ ] Zero dropouts in 60-second test
- [ ] Module hot-reload without audio interruption
- [ ] Process crash doesn't stop audio
- [ ] Natural language commands work

### Performance Metrics
- Audio latency: <10ms (3ms achieved ✅)
- Module spawn: <100ms
- Failover time: <50ms
- Sequencer accuracy: 99.9%
- Command processing: <5ms

### Architectural Goals
- [ ] Dual-slot supervisor operational
- [ ] Module sandbox pool working
- [ ] OSC canonicalization complete
- [ ] Router commit flow stable
- [ ] Natural language integrated

## 🛠️ Technical Details

See [WINDOWS_IMPLEMENTATION.md](./project/docs/WINDOWS_IMPLEMENTATION.md) for:
- Detailed architecture diagrams
- Code examples
- API specifications
- Testing procedures
- Performance benchmarks

## 🔧 Environment Configuration

```bash
# Required for Windows operation
CHRONUS_ROUTER=1                  # Enable router mode
CHRONUS_BUFFER_SIZE=256          # 5.3ms at 48kHz
CHRONUS_PREFILL_BUFFERS=3        # Default for Windows
CHRONUS_LEAD_TARGET=2            # Ring buffer lead
CHRONUS_MAX_CATCHUP=2            # Catchup limit
CHRONUS_EARLY_MARGIN_MS=2        # Timing margin
CHRONUS_KEEP_AFTER_READ=2        # Buffer retention
```

## 📊 Risk Management

| Risk | Mitigation | Status |
|------|------------|--------|
| Windows spawn() overhead | Pre-warmed worker pool | Planned |
| IPC latency in audio path | Standby-only pool, no active IPC | Designed |
| Module crashes | Process isolation in sandbox | Planned |
| WASAPI exclusive conflicts | Fallback to shared mode | Ready |
| Natural language complexity | Start with simple grammar | Planned |

## 🚀 Next Actions

1. **Immediate**: Set up Windows development environment
2. **Today**: Begin Phase 0 baseline configuration
3. **This Week**: Complete Phases 1-2.5 (WASAPI + Module Pool)
4. **Sprint Goal**: Full architecture operational on Windows

## 📝 Notes

- Keep `engine_windows.py` as harness/fallback for testing
- Supervisors remain the production path
- Module pool in standby only (no IPC in hot path)
- Natural language is our key differentiator from DAWs

---
*Sprint Owner*: Mike & Chronus Nexus  
*Architecture Review*: Senior Dev  
*Target Completion*: End of Week 4