# Pattern Save/Load Implementation Plan
**Date**: 2025-01-07  
**Author**: Chronus Nexus  
**Status**: Ready for Senior Dev Review

## Executive Summary

This document outlines the implementation plan for pattern save/load functionality in Music Chronus. After reviewing the codebase and analyzing potential friction points, we've identified critical issues that need addressing and propose a refined architecture that maintains consistency with existing patterns.

## Critical Issues Identified

### 1. Architecture Mismatch - Methods in Wrong Classes
**Problem**: Initial plan placed `save_pattern()` and `load_pattern()` in PyoEngine, but also needed `snapshot()` from SequencerManager.  
**Friction**: Creates circular dependency and unclear responsibility boundaries.  
**Solution**: Keep snapshot/apply_snapshot in SequencerManager, file operations in PyoEngine which owns the sequencer.

### 2. Missing Import Dependencies
**Problem**: Need `import shutil`, `import os`, `from copy import deepcopy` but not present.  
**Friction**: Runtime errors when implementing.  
**Solution**: Add imports at top of engine_pyo.py.

### 3. Track Dataclass Serialization Issue
**Problem**: Track's `__dict__` works for serialization, but deserialization needs careful type handling.  
**Friction**: `Track(**track_dict)` might fail if JSON converts all numbers to float.  
**Solution**: Type coercion in apply_snapshot, validate data types match Track expectations.

### 4. Bar Alignment Complexity
**Problem**: Bar alignment needs to wait for `global_step % 16 == 0`.  
**Friction**: How to delay loading without blocking OSC thread?  
**Solution**: Set a `pending_snapshot` flag and check in `_tick()` method.

### 5. Module State Application Order
**Problem**: Some parameters might depend on others (e.g., filter freq before Q).  
**Friction**: Random dict iteration could cause parameter conflicts.  
**Solution**: Apply in deterministic order: voices → effects → acid.

### 6. File Path Creation
**Problem**: Directories might not exist (patterns/slots/, patterns/temp/, etc.).  
**Friction**: First save will fail with FileNotFoundError.  
**Solution**: Use `os.makedirs(exist_ok=True)` in PyoEngine `__init__`.

### 7. Windows-Specific Path Issues
**Problem**: Forward slashes in paths, potential issues with `os.replace()`.  
**Friction**: Windows might need different atomic move strategy.  
**Solution**: Use `pathlib.Path` and platform-specific atomic operations.

### 8. Thread Safety Gap
**Problem**: File operations happen outside lock, could corrupt during concurrent saves.  
**Friction**: Two simultaneous saves to same slot = corruption.  
**Solution**: Add file operation lock or queue saves.

### 9. OSC Argument Type Coercion
**Problem**: OSC args come as strings, need int conversion for slot.  
**Friction**: `int(args[0])` will crash if args[0] is float string "1.0".  
**Solution**: Use `int(float(args[0]))` for robust conversion.

### 10. Missing Error Feedback
**Problem**: OSC handlers return bool but user gets no feedback.  
**Friction**: User won't know if save/load failed.  
**Solution**: Print status messages in handlers with self.verbose check.

## Revised Architecture

### SequencerManager Methods
```python
def snapshot(self) -> dict:
    """
    Returns serializable dict of sequencer state.
    Thread-safe with deep copy to avoid mutations.
    """
    
def apply_snapshot(self, snapshot: dict, immediate: bool = False):
    """
    Restores sequencer state.
    immediate=False: Sets pending_snapshot for bar-aligned loading
    immediate=True: Applies immediately (for testing)
    """
```

### PyoEngine Methods
```python
def save_pattern(self, slot: int) -> bool:
    """
    Orchestrates full save: sequencer + modules.
    Handles atomic file operations.
    """
    
def load_pattern(self, slot: int, immediate: bool = False) -> bool:
    """
    Orchestrates full load: sequencer + modules.
    Validates data before applying.
    """
    
def capture_all_states(self) -> dict:
    """
    Combines sequencer.snapshot() + module states.
    Returns complete pattern data.
    """
    
def restore_all_states(self, data: dict, immediate: bool = False):
    """
    Applies sequencer + module states in correct order.
    Handles version compatibility.
    """
```

## Implementation Details

### 1. Data Structure
```json
{
  "chronus_version": "1.0.0",
  "schema_version": "1.0",
  "timestamp": 1704654321.456,
  "metadata": {
    "name": "Pattern 1",
    "genre": "techno",
    "tags": ["acid", "303"]
  },
  "sequencer": {
    "bpm": 120.0,
    "swing": 0.0,
    "running": false,
    "global_step": 0,
    "tracks": {
      "kick": {
        "name": "kick",
        "voice_id": "voice1",
        "pattern": "X...X...X...X...",
        "notes": [55.0],
        "base_freq": 55.0,
        "base_amp": 0.5,
        "filter_freq": 150.0,
        "accent_boost": 1500.0,
        "reverb_send": 0.0,
        "delay_send": 0.0,
        "gate_frac": 0.2,
        "note_index": 0
      }
    }
  },
  "modules": {
    "voice1": {
      "freq": 55.0,
      "amp": 0.5,
      "filter_freq": 150.0,
      "filter_q": 2.0,
      "adsr": {
        "attack": 0.001,
        "decay": 0.05,
        "sustain": 0.0,
        "release": 0.1
      },
      "reverb_send": 0.0,
      "delay_send": 0.0
    },
    "reverb1": {
      "mix": 0.3,
      "room": 0.5,
      "damp": 0.5
    },
    "delay1": {
      "time": 0.25,
      "feedback": 0.4,
      "mix": 0.3,
      "lowcut": 100.0,
      "highcut": 5000.0
    },
    "acid1": {
      "cutoff": 1500.0,
      "res": 0.45,
      "env_amount": 2500.0,
      "decay": 0.25,
      "drive": 0.2,
      "mix": 1.0,
      "vol_comp": 0.5
    }
  }
}
```

### 2. File Operations Strategy

```python
def save_pattern_atomic(self, slot: int, data: dict) -> bool:
    """Atomic write with Windows compatibility"""
    from pathlib import Path
    import tempfile
    
    slot_dir = Path("patterns/slots")
    slot_path = slot_dir / f"slot_{slot:03d}.json"
    
    # Write to temp file in same directory (for atomic rename)
    with tempfile.NamedTemporaryFile(
        mode='w',
        dir=slot_dir,
        suffix='.tmp',
        delete=False
    ) as tmp:
        json.dump(data, tmp, indent=2)
        tmp_path = Path(tmp.name)
    
    # Backup existing if present
    if slot_path.exists():
        backup_path = Path("patterns/backups") / f"slot_{slot:03d}_{int(time.time())}.backup"
        shutil.copy2(slot_path, backup_path)
    
    # Atomic replace (Windows-safe)
    try:
        tmp_path.replace(slot_path)  # pathlib's replace is atomic on Windows
        return True
    except Exception as e:
        print(f"[PATTERN] Save failed: {e}")
        tmp_path.unlink(missing_ok=True)
        return False
```

### 3. Bar Alignment Implementation

```python
# In SequencerManager
def apply_snapshot(self, snapshot: dict, immediate: bool = False):
    """Apply snapshot with optional bar alignment"""
    if immediate:
        self._apply_snapshot_immediate(snapshot)
    else:
        with self.lock:
            self.pending_snapshot = snapshot
            self.pending_snapshot_bar = (self.global_step // 16 + 1) * 16
            print(f"[SEQ] Pattern queued for bar {self.pending_snapshot_bar // 16}")

def _tick(self):
    """Modified tick to check for pending snapshots"""
    # Check for pending snapshot at bar boundary
    with self.lock:
        if self.pending_snapshot and self.global_step >= self.pending_snapshot_bar:
            snapshot = self.pending_snapshot
            self.pending_snapshot = None
            self.pending_snapshot_bar = None
    
    if snapshot:
        self._apply_snapshot_immediate(snapshot)
        print(f"[SEQ] Pattern loaded at bar {self.global_step // 16}")
    
    # Continue normal tick processing...
```

### 4. OSC Route Integration

```python
# In setup_osc_server()
self.map_route("/pattern/save", 
    self.handle_pattern_save,
    meta={"args": ["slot_number"], "type": "int", "min": 1, "max": 128,
          "description": "Save current pattern to slot 1-128"})

self.map_route("/pattern/load",
    self.handle_pattern_load,
    meta={"args": ["slot_number", "[immediate]"], "type": "int", "min": 1, "max": 128,
          "description": "Load pattern from slot 1-128"})

self.map_route("/pattern/list",
    self.handle_pattern_list,
    meta={"args": [], "description": "List all saved patterns"})

def handle_pattern_save(self, addr, *args):
    """Handle pattern save with feedback"""
    if not args:
        print("[PATTERN] Error: No slot number provided")
        return
    
    try:
        slot = int(float(args[0]))  # Robust conversion
        if self.save_pattern(slot):
            print(f"[PATTERN] Saved to slot {slot}")
        else:
            print(f"[PATTERN] Failed to save to slot {slot}")
    except ValueError:
        print(f"[PATTERN] Error: Invalid slot number: {args[0]}")
```

## Implementation Order

1. **Phase 1: Foundation** (30 mins)
   - Add required imports
   - Create directory structure in `__init__`
   - Add pending_snapshot fields to SequencerManager

2. **Phase 2: Snapshot Methods** (45 mins)
   - Implement SequencerManager.snapshot()
   - Implement SequencerManager.apply_snapshot()
   - Test with dummy data

3. **Phase 3: Module State Capture** (30 mins)
   - Implement capture_all_states() in PyoEngine
   - Implement restore_all_states() with correct order

4. **Phase 4: File Operations** (45 mins)
   - Implement atomic save_pattern()
   - Implement validated load_pattern()
   - Add list_patterns() for discovery

5. **Phase 5: OSC Integration** (30 mins)
   - Add routes with proper metadata
   - Implement handler methods with feedback
   - Update chronusctl.py with new commands

6. **Phase 6: Testing** (30 mins)
   - Test save/load cycle
   - Test bar-aligned loading
   - Test error cases

## Testing Strategy

### Functional Tests
1. Save pattern with running sequencer
2. Load pattern and verify all parameters restored
3. Test bar-aligned loading doesn't cause glitches
4. Test immediate loading for debugging

### Error Handling Tests
1. Invalid slot numbers (0, 129, -1)
2. Corrupted JSON files
3. Missing directories
4. Concurrent save operations
5. Load non-existent slot

### Performance Tests
1. Save time < 50ms
2. Load time < 100ms
3. No audio dropouts during save/load

## Success Criteria

- ✅ Patterns save/load within performance targets
- ✅ No data loss or corruption
- ✅ Bar-aligned loading prevents glitches
- ✅ All module parameters correctly restored
- ✅ Windows path handling works correctly
- ✅ User receives clear feedback via print messages
- ✅ Schema versioning enables future migrations

## Risk Mitigation

1. **Data Loss**: Atomic writes + automatic backups
2. **Performance**: File I/O in separate thread if needed
3. **Compatibility**: Schema versioning from day 1
4. **Thread Safety**: Reuse existing lock patterns
5. **User Error**: Validate all inputs, clear error messages

## Next Steps

1. Senior Dev review of this plan
2. Implement Phase 1-2 as proof of concept
3. Test core functionality
4. Complete remaining phases
5. Integration testing
6. Update documentation

---

**Ready for Review**: This plan addresses all identified friction points and maintains consistency with the existing codebase patterns. The implementation is broken into testable phases with clear success criteria.