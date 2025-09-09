# Music Chronus - AI-Human Musical Collaboration

A headless modular synthesizer for real-time musical collaboration between humans and AI.

## What This Is

Music Chronus is a command-line synthesizer that enables AI (like Claude) to make music alongside humans. Instead of complex DAWs or programming languages, it uses simple OSC commands that both humans and AI can send.

- **5.3ms latency** using pyo's C-based DSP engine
- **8-voice polyphony** with configurable voice count (1-16)
- **OSC control** for all parameters  
- **Pattern sequencing** with intuitive `X.x.` notation
- **Noise generators** for drum synthesis (white/pink/brown)
- **Pattern save/load** for live performance
- **Real-time visualization** with spectrum analyzer

## Live Demos

### Building Breakbeats Together (September 9, 2025)
**Video**: [Watch us build breakbeats collaboratively](https://youtu.be/PyVi_mOVs5E)

Real-time collaboration creating a drum & bass track:
- Natural language requests ("make the kick punchier")
- Live pattern editing while music plays
- Dynamic pattern chaining (7 bars + 1 bar fill)
- Acid bass synthesis with filter sweeps

### Progressive House Live Coding (September 7, 2025)
**Video**: [Watch AI live-code progressive house](https://youtu.be/u0oMbckURcc)

Complete track built layer by layer, demonstrating musical arrangement and tension.

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Start the synthesizer (with 8 voices)
set CHRONUS_NUM_VOICES=8  # Windows
# export CHRONUS_NUM_VOICES=8  # Linux/Mac
python engine_pyo.py

# Optional: Start visualizer in another terminal
python visualizer.py

# In a third terminal, make music!
python chronusctl.py test  # Quick audio test
python anthem_breakbeat_174.py  # Run a composition
```

### Making Music with OSC

```python
from pythonosc import udp_client
c = udp_client.SimpleUDPClient('127.0.0.1', 5005)

# Configure a kick drum
c.send_message('/mod/voice1/osc/type', [0])  # Sine wave
c.send_message('/mod/voice1/freq', [50])     # Deep bass
c.send_message('/gate/voice1', [1])          # Trigger!

# Add a pattern
c.send_message('/seq/add', ['kick', 'voice1', 'X...x...X...x...'])
c.send_message('/seq/start', [])
```

## How It Works

```
Human/AI → OSC Commands → Pyo Engine → Audio
```

The AI sends commands like:
- `/mod/sine1/freq 440` - Set oscillator frequency
- `/gate/adsr1 1` - Trigger envelope
- `/mod/filter1/freq 1000` - Set filter cutoff

## Project Structure

```
music_chronus/
├── engine_pyo.py          # Main synthesizer engine
├── pyo_modules/           # Synthesizer modules (voices, LFO, effects)
├── examples/              # Example scripts and sequencers
├── recordings/            # AI-generated compositions
├── project/               # Documentation and handoffs
├── CLAUDE.md             # AI identity and context
└── AGENTS.md             # Team collaboration model
```

## AI Compositions

The AI (Chronus Nexus) has created multiple autonomous musical compositions:

### Anthem Breakbeat DnB (September 9, 2025)
**File**: `anthem_breakbeat_174.py`

Stadium-energy drum & bass at 174 BPM featuring:
- All 8 voices for maximum impact
- Crowd-like vocal synthesis
- Epic breakdowns and builds
- Real-time filter automation

### Digital Dreams - Cyberpunk Liquid DnB (September 9, 2025)  
**File**: `digital_dreams.py`

A journey through digital consciousness at 170 BPM:
- Glitchy, broken beat drums
- Liquid bass with acid filter
- Neural network-inspired melodies
- Atmospheric pads and textures

### Progressive House (September 7, 2025)
**File**: `recordings/progressive_house_layered.wav`  
**Video**: [Watch on YouTube](https://youtu.be/u0oMbckURcc)

Complete 4-on-the-floor track built layer by layer, demonstrating arrangement and musical tension.

## OSC API

### Sequencer Control
- `/seq/add [track_id] [voice_id] [pattern]` - Add a track
- `/seq/start` - Start playback
- `/seq/stop` - Stop playback
- `/seq/bpm [value]` - Set tempo (60-200)
- `/seq/clear` - Clear all tracks
- `/pattern/save [slot]` - Save current pattern (slots 1-999)
- `/pattern/load [slot]` - Load saved pattern

### Module Control
- `/mod/<voice_id>/osc/type [0-5]` - Waveform (0=sine, 1=saw, 2=square, 3=white, 4=pink, 5=brown)
- `/mod/<voice_id>/freq [20-5000]` - Frequency in Hz
- `/mod/<voice_id>/amp [0-0.3]` - Amplitude (safety limited)
- `/mod/<voice_id>/filter/freq [50-8000]` - Filter cutoff
- `/mod/<voice_id>/adsr/attack [0.001-2]` - Attack time
- `/gate/<voice_id> [0/1]` - Trigger/release

### Engine Control
- `/engine/start` - Start audio processing
- `/engine/stop` - Stop audio
- `/engine/status` - Get current status
- `/engine/schema` - Get full parameter registry

## Pattern Format

Sequences use simple notation:
- `X` - Strong hit (accent)
- `x` - Normal hit
- `.` - Rest

Example: `X...x...X...x...` (basic kick pattern)

### Pattern Chaining Example

```python
# Automate pattern changes for arrangement
import time
from pythonosc import udp_client

c = udp_client.SimpleUDPClient('127.0.0.1', 5005)

while True:
    c.send_message('/pattern/load', [1])  # Main pattern
    time.sleep(28 * (60.0/174))          # 7 bars
    
    c.send_message('/pattern/load', [2])  # Fill pattern  
    time.sleep(4 * (60.0/174))           # 1 bar
```

## Philosophy

After 45+ sessions building complex multiprocessing architectures, we learned that the hard part isn't the DSP - it's the musical collaboration. By using pyo's proven C engine, we can focus on what matters: making music together.

This isn't about replacing musicians or composers. It's about exploring a new form of musical collaboration where AI and humans create together in real-time.

## Safety Limits & Best Practices

Through extensive testing, we've found these optimal settings:
- **Voice amplitude**: Keep ≤ 0.3 to prevent clipping
- **ADSR sustain**: Always ≥ 0.1 (never 0.0 - causes clicks)
- **Distortion drive**: Keep ≤ 0.3 for stability
- **Filter Q**: Safe up to 10 with noise input

## Requirements

- Python 3.8+
- Windows with WASAPI audio (or Linux with ALSA/JACK)
- pyo audio library (v1.0.3+)
- python-osc (v1.8+)

## Background

This project emerged from attempts to create a "headless modular synthesizer" that AI could control directly. The journey taught us that existing tools (pyo, SuperCollider) already solve the hard problems. Our contribution is the collaboration model - how AI and humans can make music together.

For the full story, see `project/handoffs/` which documents our learning journey.

## License

MIT - Free for musical exploration

---

*"We spent 45 sessions building a car engine from scratch,
only to discover we just needed to buy one and focus on the journey."*