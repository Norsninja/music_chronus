# Manual Testing Guide for CP3 Router Audio

## Quick Start

### Terminal 1: Start the Supervisor
```bash
cd music_chronus
source venv/bin/activate
CHRONUS_ROUTER=1 python src/music_chronus/supervisor_v3_router.py
```

You should see:
- "Starting AudioSupervisor v3 with router support"
- "Audio started - Press Ctrl+C to stop"
- "Router mode active - use /patch/* commands to build graphs"

### Terminal 2: Run the Musical Demo
```bash
cd music_chronus
source venv/bin/activate
python test_musical_demo.py
```

This will play:
1. C major scale ascending
2. C major scale descending  
3. "Mary Had a Little Lamb" melody

## Manual Commands for Testing

If you want to test manually with individual commands:

### Terminal 2: Send OSC Commands

```bash
source venv/bin/activate

# Create a simple test patch
python -c "
from pythonosc import udp_client
import time

c = udp_client.SimpleUDPClient('127.0.0.1', 5005)

# Create modules
c.send_message('/patch/create', ['osc1', 'simple_sine'])
time.sleep(0.1)
c.send_message('/patch/create', ['env1', 'adsr'])
time.sleep(0.1)

# Connect them
c.send_message('/patch/connect', ['osc1', 'env1'])
time.sleep(0.1)

# Commit the patch (activates it)
c.send_message('/patch/commit', [])
time.sleep(0.5)

# Set parameters
c.send_message('/mod/osc1/freq', 440.0)
c.send_message('/mod/osc1/gain', 0.3)

print('Patch ready! Send gate commands to play notes.')
"
```

### Play Individual Notes

```bash
# Play A4 (440Hz)
python -c "
from pythonosc import udp_client
import time
c = udp_client.SimpleUDPClient('127.0.0.1', 5005)
c.send_message('/gate/env1', 1)  # Note on
time.sleep(0.5)
c.send_message('/gate/env1', 0)  # Note off
"

# Play C4 (261Hz)
python -c "
from pythonosc import udp_client
import time
c = udp_client.SimpleUDPClient('127.0.0.1', 5005)
c.send_message('/mod/osc1/freq', 261.63)
c.send_message('/gate/env1', 1)
time.sleep(0.5)
c.send_message('/gate/env1', 0)
"

# Play E4 (329Hz)
python -c "
from pythonosc import udp_client
import time
c = udp_client.SimpleUDPClient('127.0.0.1', 5005)
c.send_message('/mod/osc1/freq', 329.63)
c.send_message('/gate/env1', 1)
time.sleep(0.5)
c.send_message('/gate/env1', 0)
"
```

## Interactive Python Session

For more interactive control:

```python
# Start python interpreter
python

>>> from pythonosc import udp_client
>>> import time
>>> c = udp_client.SimpleUDPClient('127.0.0.1', 5005)

# Now you can send commands interactively:
>>> c.send_message('/mod/osc1/freq', 440.0)
>>> c.send_message('/gate/env1', 1)  # Start note
>>> c.send_message('/gate/env1', 0)  # Stop note

# Change frequency while playing
>>> c.send_message('/gate/env1', 1)
>>> c.send_message('/mod/osc1/freq', 220.0)  # Lower octave
>>> time.sleep(0.5)
>>> c.send_message('/mod/osc1/freq', 440.0)  # Back to A4
>>> time.sleep(0.5)
>>> c.send_message('/gate/env1', 0)

# Adjust filter cutoff for different timbres
>>> c.send_message('/mod/filter1/cutoff', 500.0)  # Dark sound
>>> c.send_message('/mod/filter1/cutoff', 4000.0)  # Bright sound
```

## What You Should Hear

1. **test_musical_demo.py**: 
   - Clear ascending and descending scales
   - Recognizable "Mary Had a Little Lamb" melody
   - Each note should have a quick attack and smooth release

2. **Manual testing**:
   - Individual notes at specified frequencies
   - Smooth envelope transitions (no clicks)
   - Filter changes should alter the timbre

## Troubleshooting

If you don't hear audio:
1. Check PulseAudio is running: `pactl info`
2. Verify the supervisor shows "Audio started"
3. Make sure you ran `/patch/commit` after creating modules
4. Check volume isn't muted

## Expected Console Output

In the supervisor terminal, you should see:
- Module creation messages when building patch
- "Patch committed and ready" after commit
- RMS values showing audio is being generated
- Possible failover messages as slots switch

---
*The router mode synthesizer is fully functional and ready for musical exploration!*