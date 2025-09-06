# Windows Port Commit Plan

## Files to Commit

### Core Windows Implementation
- ✅ `.env.windows` - Windows environment configuration
- ✅ `src/music_chronus/config_windows.py` - Windows configuration manager
- ✅ `src/music_chronus/supervisor_windows.py` - Windows WASAPI supervisor

### Tests (Moved to proper location)
- ✅ `tests/manual/test_*.py` - All manual test files
- ✅ `tests/specs/rt_audio_windows.feature` - BDD test specification

### Documentation (Organized)
- ✅ `docs/windows/WINDOWS_SETUP.md` - Windows setup guide
- ✅ `docs/windows/WINDOWS_SPRINT.md` - Sprint planning
- ✅ `docs/windows/PHASE1_VALIDATION_RESULTS.md` - Test results
- ✅ `docs/analysis/AUDIO_POPPING_ANALYSIS.md` - Popping analysis
- ✅ `docs/MANUAL_TEST_GUIDE.md` - Manual testing guide
- ✅ `docs/PROJECT_ORGANIZATION_PLAN.md` - Organization plan

### Operational Scripts (Stay in root)
- ✅ `osc_control.py` - OSC command-line controller
- ✅ `record_session.py` - Recording utility

### Additional Modules (Question: Should these be included?)
- ❓ `src/music_chronus/modules/acid_filter.py` - Acid filter module
- ❓ `src/music_chronus/modules/distortion.py` - Distortion module

### Files NOT to Commit
- ❌ `recordings/*.wav` - Audio recordings (too large)
- ❌ `nul` - Accidental file
- ❌ SimpleSine changes (rolled back)
- ❌ ADSR/base.py changes (not saved)

## Modified Files to Review
- `AGENTS.md` - Updated with windows-port context
- `run_supervisor_router.py` - Minor changes

## Deleted Files (Moved, not deleted)
These show as deleted but were actually moved:
- `MANUAL_TEST_GUIDE.md` → `docs/`
- `WINDOWS_SETUP.md` → `docs/windows/`
- `test_*.py` → `tests/manual/`

## Commit Message Suggestion

```
feat: Windows native port with WASAPI audio support

Phase 1 Implementation Complete:
- Windows-native supervisor with WASAPI support
- Dual-slot fault-tolerant architecture 
- Zero underruns over 60-second test
- Callback timing: min 0.009ms, mean 0.028ms, max 0.252ms
- Total system latency: ~6ms (target <10ms)

Added:
- Windows configuration system (.env.windows, config_windows.py)
- WASAPI supervisor with metrics and recording
- Comprehensive test suite for Windows
- BDD test specifications
- Process priority and MMCSS registration

Organized:
- Moved tests to /tests/manual/
- Documentation to /docs/windows/ and /docs/analysis/
- Kept operational scripts in root

Performance validated:
- 60-second stability test passed
- Zero audio dropouts
- Metrics well within targets

Known issues:
- Audio popping at buffer boundaries (documented in analysis)
- Needs thin wrapper refactor to reduce code duplication

Co-Authored-By: Chronus Nexus <noreply@anthropic.com>
```