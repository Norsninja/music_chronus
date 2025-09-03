# Changelog

All notable changes to Music Chronus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2025-09-03

### Added
- **Recording capability**: Capture sessions to WAV files via `/record/*` OSC commands
- **CP3 Router**: Dynamic module patching without audio interruption
- **Track A baseline**: Production-quality metrics (occ0/1k≈0, none≤0.1%)
- **Frequency smoothing**: 10ms smoothing reduces DSP discontinuities
- **Historic first**: AI-composed 39-second musical piece through synthesis reasoning
- **Proactive fill**: Emergency buffer generation prevents ring starvation
- **Enhanced instrumentation**: occ0/1k counter tracks ring buffer health
- **Environment knobs**: Tunable parameters for buffer management

### Fixed
- Prime timeout bug via per-worker patch queues
- Frequency change pops via parameter smoothing
- Race conditions in patch commit operations

### Changed
- SimpleSine frequency parameter now smooths over 10ms (was instant)
- Enhanced STATS output includes occ0/1k, underflow, overflow metrics

### Documentation
- WSL2 audio caveats documented (infrastructure limitation confirmed)
- Recording implementation plan with RT-safety constraints
- Track A clean baseline signoff with environment considerations

## [0.2.0] - 2025-08-31

### Added
- **Phase 2 Modular Synthesis**: SimpleSine → ADSR → BiquadFilter chain
- **Fault tolerance**: <50ms failover with dual-slot architecture
- **Zero-allocation audio path**: Pre-allocated buffers throughout
- **Command continuity**: Full control during worker failover

### Fixed
- Buffer allocation patterns for RT-safety
- Worker spawn timing with pre-warmed pools

## [0.1.0] - 2025-08-25

### Added
- **Phase 0 Foundation**: Test-driven architecture validation
- **Phase 1 Core Engine**: Working audio with 5.8ms latency
- **OSC control**: Sub-millisecond parameter updates
- **Performance validation**: Zero dropouts in 60-second tests

### Technical Discoveries
- Worker pool architecture mandatory (672ms spawn time unacceptable)
- Multiprocessing 5.7x faster than threading for small buffers
- Memory bandwidth limits parallelism to 2-3 workers

---

[0.3.0]: https://github.com/yourusername/music_chronus/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/yourusername/music_chronus/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/yourusername/music_chronus/releases/tag/v0.1.0