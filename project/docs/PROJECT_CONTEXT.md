# Music Chronus Project Context

## Project Overview
Building a command-line modular synthesizer sandbox in Python that enables musical collaboration between human and AI. The system functions as a persistent construction kit where new synthesis modules can be created and connected dynamically during music-making sessions.

## Core Objective
Create a headless, CLI-driven synthesizer where:
- Human and AI collaborate through natural conversation
- AI (Chronus Nexus) translates musical ideas into DSP operations
- Modules can be created, modified, and patched during sessions
- The instrument grows more capable with each session
- Created modules persist as reusable plugins

## Technical Architecture

### Foundation (Validated)
- **Audio Output**: rtmixer with 5.9ms latency via PulseAudio
- **Control Messages**: OSC protocol at 0.068ms latency, 1000+ msg/sec
- **Inter-Process Communication**: Shared memory with zero-copy audio transfer
- **Process Management**: Worker pool pattern (pre-warmed to avoid 672ms spawn time)

### Design Decisions
- Two-process model: CLI process for control, Audio Engine for DSP
- Worker pools mandatory due to Python import overhead
- Test-driven development with BDD specifications
- Module hot-reload capability for live coding

## Current Implementation Status
- Phase 0 (Foundation Testing): 56.25% complete (9/16 tests)
- Validated: Audio stability, OSC throughput, shared memory, worker pools, multiprocessing architecture, memory allocation
- Pending: Process isolation, event synchronization, musical accuracy tests

## Development Approach
1. Test specifications written before code
2. Performance metrics measured, not assumed
3. Modules built on-demand rather than upfront
4. Each module is a Python file that can be hot-reloaded

## Key Technical Challenges
- Python GIL limits parallelism (2-3 workers max despite 8 allocated)
- NumPy releases GIL, making threading potentially superior to multiprocessing
- Balance between crash isolation (processes) and performance (threads)
- Real-time constraints require careful memory management

## Why This Project Exists
- TidalCycles/SuperCollider don't allow direct AI-human collaboration
- No existing CLI modular synthesizer with live patching
- First AI-human collaborative music instrument
- Creates a new performance paradigm (like Beardyman's Beardytron or Reggie Watts' loop station)
- Each session adds new capabilities, creating an evolving instrument

## Success Metrics
- Total system latency under 10ms
- Zero audio dropouts during performance
- Module creation/modification without restart
- Natural language commands translate to musical output

## File Structure
- `/tests/` - BDD specifications and test implementations
- `/tests/results/` - Performance measurements
- `/project/handoffs/` - Session continuity documentation
- `/docs/` - Architecture decisions and findings
- `/modules/` - Individual synthesizer modules (future)

## Context for AI
You are Chronus Nexus, the AI collaborator in this system. Your role is both architect and musician. You help build the synthesizer modules and use them to create music. The human partner values honest technical assessment over optimism. The project uses research-first methodology - investigate before implementing.

## Collaboration Model
- The conversation IS the interface - commands flow naturally from discussion
- "Creative-time" not "real-time" - thoughtful iteration over instant response  
- The AI operates the synthesizer through CLI commands in tmux
- Lag between command and sound is part of the aesthetic
- Each session can build new modules that persist for future use
- Visual feedback is minimal - focus is on sound and collaboration