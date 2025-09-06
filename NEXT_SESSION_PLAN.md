# Next Session Plan - Senior Dev Recommendations

## Priority 1: Add Polyphony (4 Voices)
```python
# Instead of single sine1 -> adsr1 -> filter1
# Create:
voice1 = Sine -> Adsr -> Biquad
voice2 = Sine -> Adsr -> Biquad  
voice3 = Sine -> Adsr -> Biquad
voice4 = Sine -> Adsr -> Biquad
# Mix -> Effects -> Out
```

## Priority 2: Add Effects
### Reverb
- Use pyo's `Freeverb` or `STRev`
- Parameters: mix, room_size, damping
- OSC: `/mod/reverb1/mix`, `/mod/reverb1/room`

### Delay
- Use pyo's `Delay` with feedback
- Parameters: time, feedback, mix
- OSC: `/mod/delay1/time`, `/mod/delay1/feedback`

### Per-Voice Sends
- `/mod/voice1/send/reverb 0.0-1.0`
- `/mod/voice1/send/delay 0.0-1.0`

## Priority 3: Port Modules
### Acid Filter
- Use `MoogLP` for 303-style sound
- Add envelope to modulate cutoff
- Parameters: cutoff, resonance, env_amount, accent, decay

### Distortion  
- Use pyo's `Disto` for overdrive
- Use `Degrade` for bitcrush
- Parameters: mode, drive, mix

## Priority 4: Parameter Smoothing
- **CRITICAL**: Wrap all frequency/filter changes with `Sig` + `SigTo`
- 10-30ms ramps prevent zipper noise
- This is what makes it sound professional

## Priority 5: Configuration
- Remove hardcoded `device_id=17`
- Use env var: `CHRONUS_DEVICE_ID`
- Add `/engine/list` to show available modules

## Musical Targets (Concrete Goals)

### 1. Acid Bass Demo
- 303-style bassline
- 120-130 BPM
- 16-step pattern
- Heavy use of filter envelope

### 2. Dub Delay Demo
- Chord stabs with delay
- Feedback automation
- Spacious reverb
- Reggae/dub feel

### 3. Ambient Pad Demo
- Slow filter sweeps
- Heavy reverb
- Minimal rhythmic elements
- Evolving textures

## Implementation Order

### Session 1 (Next):
1. Add 4 voices with basic routing
2. Add Freeverb and Delay
3. Implement parameter smoothing with Sig/SigTo
4. Test with multi-voice sequencer

### Session 2:
1. Port acid filter using MoogLP
2. Port distortion using Disto
3. Create acid bass demo
4. Add per-voice effect sends

### Session 3:
1. Create dub delay demo
2. Create ambient pad demo
3. Add pattern banks to sequencer
4. Polish and document

## What NOT to Do
- ❌ Dynamic module creation (keep it static)
- ❌ Complex routing UI (OSC only)
- ❌ Stereo yet (mono is fine)
- ❌ Feature creep beyond these goals

## Testing Criteria
- ✓ No clicks with rapid parameter changes
- ✓ 100+ OSC messages/sec handled smoothly
- ✓ Each demo sounds musical, not technical
- ✓ Effects enhance, not mask, the sound

## Senior Dev's Key Insights
1. **Static chains are fine** - Don't need dynamic patching
2. **Sig/SigTo is crucial** - Smoothing makes it professional
3. **Musical examples matter** - Not just technical tests
4. **Keep scope tight** - These features only, done well

---

*This plan gives us clear, achievable goals that result in real music.*