# Sequencer MVP Acceptance Criteria

## Functional Requirements

### Division Semantics
- Division represents note value: 4 = quarter note, 8 = eighth note, 16 = sixteenth note
- Step duration = (60/BPM) / division
- Pattern length is independent of division (controlled by steps parameter)
- Example: 120 BPM, division=4, pattern "x...x..." = quarter notes every 4 steps

### API Completeness
- [ ] `/seq/create` creates sequencer with defaults
- [ ] `/seq/config` sets BPM, steps, division
- [ ] `/seq/pattern` accepts string notation
- [ ] `/seq/assign` routes to module parameters
- [ ] `/seq/start`, `/seq/stop`, `/seq/reset` control playback
- [ ] `/seq/bpm` changes tempo on boundary
- [ ] `/seq/gate_len` adjusts note duration

### Pattern Behavior
- [ ] Basic patterns: "x...x...x...x..." parse correctly
- [ ] Accent notation: "X" vs "x" produces different velocities
- [ ] Parameter lanes: CSV values map to module parameters
- [ ] Pattern swaps are atomic (no partial patterns)

### Timing Accuracy
- [ ] Steps occur on buffer boundaries (±1 buffer tolerance)
- [ ] Gate length respects configured fraction (rounded to nearest buffer)
- [ ] Tempo changes apply on next step boundary
- [ ] Multiple sequencers maintain phase sync

## Performance Requirements

### RT Metrics (60-second test)
- [ ] none_reads ≤ 0.5% (from baseline ≤0.1%)
- [ ] occ0/1k ≈ 0 (max 1 occurrence)
- [ ] PortAudio flags = 0
- [ ] No buffer underruns
- [ ] CPU usage increase (observe and document, target < 5%)

### Audio Quality
- [ ] No pops in recordings during:
  - [ ] Pattern playback
  - [ ] Tempo changes
  - [ ] Start/stop operations
  - [ ] Pattern updates
- [ ] Transient timing matches expected BPM (±1 buffer / ~11.6ms)

## Integration Requirements

### System Interoperability
- [ ] Works during patch commits
- [ ] Both slots receive identical events
- [ ] No lost gates during failover
- [ ] Recording captures sequenced output cleanly
- [ ] Existing metrics remain stable

### Safety Invariants
- [ ] No allocations in audio callback
- [ ] Sequencer uses CommandRing only
- [ ] Pattern updates via atomic swap
- [ ] No logging in hot paths
- [ ] Thread-safe queue operations

## Test Coverage

### Unit Tests Required
- [ ] `test_seq_pattern_parse` - String to array conversion
- [ ] `test_seq_gate_timing` - Buffer-aligned gate emission
- [ ] `test_seq_param_lane` - Parameter value mapping
- [ ] `test_seq_bpm_change` - Tempo change on boundary
- [ ] `test_seq_start_stop_reset` - State transitions

### Integration Tests Required
- [ ] `test_seq_with_audio` - Full stack with recording
- [ ] `test_seq_during_commit` - Patch swapping interaction
- [ ] `test_seq_multi_track` - Multiple sequencer sync
- [ ] `test_seq_long_run` - 15-minute stability test

## Definition of Done

### MVP Complete When:
1. All unit tests passing
2. All BDD scenarios implemented and green
3. 30-minute continuous run with stable metrics
4. Clean 60-second recording of kick pattern at 120 BPM
5. Tempo change from 120 to 140 BPM without glitches
6. Pattern update during playback works atomically

### Documentation Required:
- [ ] OSC command reference in README
- [ ] Pattern notation guide
- [ ] Example usage patterns
- [ ] Integration notes in sprint.md

## Non-Goals for MVP

These are explicitly OUT of scope for initial implementation:
- Sample-accurate sequencing (buffer-accurate is sufficient)
- External MIDI clock sync
- Network sync (Ableton Link)
- Pattern recording from live input
- Swing/groove timing
- Probability/randomization
- Pattern chaining
- Song mode

## Success Metrics

The sequencer is successful if:
1. I (Chronus) can create drum patterns without Python sleep() delays
2. Patterns can be modified while playing
3. Multiple tracks stay synchronized
4. Audio quality matches our existing high standards
5. The implementation remains simple and maintainable