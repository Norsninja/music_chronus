# OSC Quick Reference for Music Chronus

## The Simple Rules

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