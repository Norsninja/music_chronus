# Project Organization Plan

## Current Issues
- Test files scattered in root directory
- Documentation mixed in root with code
- Windows-specific files not clearly separated
- Temporary test scripts in root

## Proper Structure

### `/tests/` - All test files
- `/tests/integration/` - Integration tests (supervisor tests, etc.)
- `/tests/manual/` - Manual test scripts for debugging
- `/tests/specs/` - BDD feature specs (already correct)
- `/tests/results/` - Test output and measurements (already correct)
- `/tests/windows/` - Windows-specific tests

### `/docs/` - All documentation
- `/docs/` - Main documentation (architecture, setup, etc.)
- `/docs/analysis/` - Analysis documents (popping analysis, etc.)
- `/docs/windows/` - Windows-specific documentation

### `/src/music_chronus/` - Source code
- Already properly organized
- Windows supervisor should stay here

### Root directory - Only essential files
- README.md
- CHANGELOG.md
- sprint.md (active sprint tracking)
- .env.windows (config file)
- Makefile
- pyproject.toml
- requirements.txt

## Files to Move

### Test files to `/tests/manual/`:
- test_60s_stability.py
- test_acid_bass_live.py
- test_acid_filter.py
- test_distortion.py
- test_modules_windows.py
- test_osc_send.py
- test_osc_windows.py
- test_sequencer_simple.py
- test_sequencer_windows.py
- test_stability_windows.py
- test_windows_audio.py
- test_declick_patterns.py (if created)

### Documentation to `/docs/`:
- AGENTS.md → /docs/
- CLAUDE.md → /docs/
- MANUAL_TEST_GUIDE.md → /docs/

### Windows docs to `/docs/windows/`:
- WINDOWS_SETUP.md
- WINDOWS_SPRINT.md
- PHASE1_VALIDATION_RESULTS.md

### Analysis docs to `/docs/analysis/`:
- AUDIO_POPPING_ANALYSIS.md
- DECLICK_FIXES_IMPLEMENTED.md

## Commands to Execute

```bash
# Create directories
mkdir -p tests/manual
mkdir -p tests/windows
mkdir -p docs/analysis
mkdir -p docs/windows

# Move test files
mv test_*.py tests/manual/

# Move documentation
mv AGENTS.md docs/
mv CLAUDE.md docs/
mv MANUAL_TEST_GUIDE.md docs/

# Move Windows documentation
mv WINDOWS_*.md docs/windows/
mv PHASE1_VALIDATION_RESULTS.md docs/windows/

# Move analysis documentation
mv AUDIO_POPPING_ANALYSIS.md docs/analysis/
mv DECLICK_FIXES_IMPLEMENTED.md docs/analysis/
```