# OSC Quick Reference for Music Chronus

## The Simple Rules
==================================================
AVAILABLE MODULES
==================================================

Voices (voice1-voice8):
  /mod/voiceN/freq <20-5000>
  /mod/voiceN/amp <0-1>
  /mod/voiceN/filter/freq <50-8000>
  /mod/voiceN/filter/q <0.5-10>
  /mod/voiceN/adsr/attack <0.001-2>
  /mod/voiceN/adsr/decay <0-2>
  /mod/voiceN/adsr/sustain <0-1>
  /mod/voiceN/adsr/release <0.01-3>
  /mod/voiceN/send/reverb <0-1>
  /mod/voiceN/send/delay <0-1>
  /gate/voiceN <0|1>

DSP Modules:
  acid1 (TB-303 filter on voice2):
    /mod/acid1/cutoff <80-5000> - Base cutoff Hz
    /mod/acid1/res <0-0.98> - Resonance
    /mod/acid1/env_amount <0-5000> - Envelope depth Hz
    /mod/acid1/decay <0.02-1.0> - Envelope decay s
    /mod/acid1/accent <0-1> - Accent level
    /mod/acid1/cutoff_offset <0-1000> - Accent cutoff boost
    /mod/acid1/res_accent_boost <0-0.4> - Accent resonance
    /mod/acid1/accent_decay <0.02-0.15> - Accent env decay
    /mod/acid1/drive <0-1> - Pre-filter drive
    /mod/acid1/mix <0-1> - Wet/dry mix
    /mod/acid1/vol_comp <0-1> - Resonance compensation
    /gate/acid1 - Optional (auto-triggers with voice2)

Effects:
  /mod/reverb1/mix <0-1>
  /mod/reverb1/room <0-1>
  /mod/reverb1/damp <0-1>
  /mod/delay1/time <0.1-0.6>
  /mod/delay1/feedback <0-0.7>
  /mod/delay1/mix <0-1>

Backward Compatibility (mapped to voice1):
  /mod/sine1/freq
  /mod/filter1/freq|q
  /mod/adsr1/*
  /gate/adsr1
  
1. **Single values**: Can be sent with or without list
   ```python
   client.send_message('/mod/voice1/freq', 440.0)      # ✅ Works
   client.send_message('/mod/voice1/freq', [440.0])    # ✅ Also works
   ```

2. **Multiple values**: MUST be in a list
   ```python
   client.send_message('/seq/add', ['kick', 'voice1', 'X...X...', 60, 200])  # ✅ Correct
   ```

3. **No arguments**: Use empty list
   ```python
   client.send_message('/seq/start', [])   # ✅ Correct
   client.send_message('/seq/start')       # ❌ Will error - needs value argument
   ```

## Common Commands Reference

### Voice Control
```python
# Single values - both formats work
client.send_message('/mod/voice1/freq', 440.0)
client.send_message('/mod/voice1/amp', 0.5)
client.send_message('/mod/voice1/filter/freq', 1000.0)
client.send_message('/gate/voice1', 1)
```

### Sequencer
```python
# Multiple values - MUST use list
client.send_message('/seq/add', ['track_id', 'voice1', 'pattern', freq, filter])
client.send_message('/seq/update/pattern', ['track_id', 'new_pattern'])
client.send_message('/seq/update/notes', ['track_id', 'C4 D4 E4'])

# No args - use empty list
client.send_message('/seq/start', [])
client.send_message('/seq/stop', [])
client.send_message('/seq/clear', [])

# Single value
client.send_message('/seq/bpm', 120)
client.send_message('/seq/swing', 0.2)
```

### Effects
```python
# All single values
client.send_message('/mod/reverb1/mix', 0.3)
client.send_message('/mod/delay1/time', 0.375)
client.send_message('/mod/dist1/drive', 0.3)
client.send_message('/mod/lfo1/rate', 0.5)
```

## Using the ChronusOSC Wrapper

The wrapper handles all formatting for you:

```python
from chronus_osc import ChronusOSC

osc = ChronusOSC()

# Voice control - no need to think about formats
osc.set_voice_freq(1, 440.0)
osc.set_voice_filter(1, freq=1000, q=2.0)
osc.gate_voice(1, True)

# Sequencer - handles list creation
osc.seq_add_track('kick', 'voice1', 'X...X...', base_freq=60)
osc.seq_update_pattern('kick', 'XX..XX..')
osc.seq_start()  # Handles empty list

# Effects - clean interface
osc.set_reverb(mix=0.3, room=0.5)
osc.set_delay(mix=0.2, time=0.375)
```

## Summary

- **Don't overthink it**: Single values work either way
- **Multiple values**: Always use a list
- **No arguments**: Always use empty list `[]`
- **When in doubt**: Use the ChronusOSC wrapper - it handles everything!