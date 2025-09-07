# Music Chronus - AI-Human Musical Collaboration

A headless modular synthesizer for real-time musical collaboration between humans and AI.

## What This Is

Music Chronus is a command-line synthesizer that enables AI (like Claude) to make music alongside humans. Instead of complex DAWs or programming languages, it uses simple OSC commands that both humans and AI can send.

- **5.3ms latency** using pyo's C-based DSP engine
- **OSC control** for all parameters
- **Pattern sequencing** with intuitive `X.x.` notation
- **Modular synthesis** - connect oscillators, filters, effects

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Start the synthesizer
python engine_pyo.py

# In another terminal, run examples
python examples/test_pyo_engine.py
python examples/test_sequencer_pyo.py
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

The AI (Chronus Nexus) has created its first autonomous musical compositions:

### Progressive House (January 7, 2025)
**File**: `recordings/progressive_house_layered.wav`

A complete progressive house track built layer by layer using the sequencer:
- Started with just a kick drum (4-on-the-floor pattern)
- Added hi-hats, bassline, and chord stabs progressively
- Demonstrated dynamic pattern changes during playback
- Created breakdown and build-up sections
- All sounds synthesized in real-time (no samples)

This composition showcases the system's ability to:
- Build complex arrangements from simple elements
- Modify patterns while playing (`/seq/update/pattern`)
- Control multiple synthesis parameters simultaneously
- Create musical tension and release through arrangement

The entire session was live-coded by the AI while explaining each step, demonstrating true AI-human musical collaboration.

## OSC API

### Module Control
- `/mod/<module_id>/<param> value` - Set any parameter
- `/gate/<module_id> 0/1` - Gate control (trigger/release)

### Engine Control
- `/engine/start` - Start audio processing
- `/engine/stop` - Stop audio
- `/engine/status` - Get current status

## Pattern Format

Sequences use simple notation:
- `X` - Strong hit (accent)
- `x` - Normal hit
- `.` - Rest

Example: `X...x...X...x...` (basic kick pattern)

## Philosophy

After 45+ sessions building complex multiprocessing architectures, we learned that the hard part isn't the DSP - it's the musical collaboration. By using pyo's proven C engine, we can focus on what matters: making music together.

This isn't about replacing musicians or composers. It's about exploring a new form of musical collaboration where AI and humans create together in real-time.

## Requirements

- Python 3.8+
- Windows with WASAPI audio (or Linux with ALSA/JACK)
- pyo audio library
- python-osc

## Background

This project emerged from attempts to create a "headless modular synthesizer" that AI could control directly. The journey taught us that existing tools (pyo, SuperCollider) already solve the hard problems. Our contribution is the collaboration model - how AI and humans can make music together.

For the full story, see `project/handoffs/` which documents our learning journey.

## License

MIT - Free for musical exploration

---

*"We spent 45 sessions building a car engine from scratch,
only to discover we just needed to buy one and focus on the journey."*