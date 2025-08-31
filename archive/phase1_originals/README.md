# Phase 1 Original Files Archive

These files were archived during the refactor on 2025-08-31.

## File History

- **audio_engine.py**: Initial Phase 1A audio engine
- **audio_engine_v2.py**: Improved with metrics
- **audio_engine_v3.py**: Final Phase 1B version with OSC control → Now `src/music_chronus/engine.py`
- **audio_supervisor.py**: Phase 1C supervisor → Now `src/music_chronus/supervisor.py`
- **audio_supervisor_part2.py**: Supervisor logic (merged into main supervisor)
- **test_phase1b_basic.py**: Basic OSC control test
- **test_phase1b_stress.py**: 100 msg/s stress test
- **test_refactor.py**: Temporary test to validate refactor

## Why Archived

These files represent the development history of Phase 1. The final versions have been moved to:
- `src/music_chronus/engine.py` (from audio_engine_v3.py)
- `src/music_chronus/supervisor.py` (from audio_supervisor.py)

Keeping them archived preserves the development history and provides fallback if needed.
