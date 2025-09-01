# Deprecated Supervisor Implementations

This directory contains deprecated supervisor implementations that were part of the journey to achieving <50ms failover.

## Archived Files

These implementations represent the evolution of our fault-tolerant architecture:

- **supervisor_v2.py** - Original dual-worker implementation
- **supervisor_v2_fixed.py** - First attempt at fixing failover issues
- **supervisor_v2_graceful.py** - Added ring swapping (caused engine noise)
- **supervisor_v2_slots.py** - First slot-based attempt (had API issues)
- **supervisor_v2_slot_based.py** - Alternative slot implementation

## Current Production Implementation

The production supervisor is now:
```
src/music_chronus/supervisor_v2_slots_fixed.py
```

This implementation features:
- Slot-based architecture (rings tied to slots, not workers)
- Per-process view rebinding for shared memory
- <50ms failover with audio continuity
- Zero allocations in audio callback
- Full command continuity during failover

## Why These Were Deprecated

Each implementation taught us valuable lessons:

1. **Ring swapping doesn't work** - Workers hold references from spawn time
2. **Views need rebinding** - NumPy views don't survive process boundaries
3. **Sequential reading is critical** - "Latest wins" causes engine noise
4. **Slots > Dynamic workers** - Fixed infrastructure with movable workers

## Do Not Use These Files

These implementations have known issues and should not be used in production. They are preserved for historical reference and learning purposes only.

---

*For the current implementation, see: src/music_chronus/supervisor_v2_slots_fixed.py*