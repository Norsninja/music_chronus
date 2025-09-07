# Music Chronus - Complete Musical Capabilities Guide

**Research Date**: 2025-01-07  
**Engine Version**: Pyo-based with 5.3ms latency  
**Control Protocol**: OSC over UDP (port 5005)

## Executive Summary

Music Chronus provides a powerful real-time electronic music synthesizer with 4-voice polyphony, TB-303 style acid filtering, comprehensive effects processing, and integrated sequencing. Critical findings: the system achieves professional-grade 5.3ms latency using pyo's C backend, features battle-tested parameter ranges from extensive research, and supports both direct OSC control and high-level sequencing patterns.

## Voice System Architecture

### 4-Voice Polyphonic Engine

**voice1-4**: Independent polyphonic voices  
**voice2 special**: Routes through TB-303 style acid filter  
**Signal chain**: Oscillator → ADSR → Biquad Filter → Effects Sends → Master

### Voice Parameters & Musical Ranges

#### Oscillator Control
```bash
# Frequency Control
/mod/voiceN/freq <20-5000>              # Hz
```
**Musical Ranges**:
- **Bass**: 55-220Hz (A1-A3) - deep sub-bass to mid-bass
- **Lead**: 220-880Hz (A3-A5) - cutting lead lines  
- **Pad**: 130-520Hz (C3-C5) - warm chord voicings
- **Percussion**: 80-200Hz - synthetic kick fundamentals

**Sweet Spots**:
- **110Hz**: Classic acid bassline fundamental
- **220Hz**: Punchy mid-bass for techno
- **440Hz**: Reference A4 for tuning leads
- **880Hz**: Bright lead tones that cut through mix

#### Waveform Selection
```bash
/mod/voiceN/osc/type <0-2>              # Waveform type
```
- **0**: Sine - clean, pure tones for bass and pads
- **1**: Saw - rich harmonics, perfect for leads and bass
- **2**: Square - hollow, woody character for leads

#### Amplitude Control
```bash
/mod/voiceN/amp <0-1>                   # Voice amplitude
```
**Musical Applications**:
- **0.1-0.3**: Background pads, subtle textures
- **0.3-0.6**: Main bass and rhythm elements  
- **0.6-0.8**: Lead lines and prominent parts
- **0.8-1.0**: Accent hits and climax sections

### Filter System (Per Voice)

#### Cutoff Frequency
```bash
/mod/voiceN/filter/freq <50-8000>       # Hz
```
**Musical Sweet Spots**:
- **200-400Hz**: Dark, muffled bass (classic 303 closed)
- **800-1200Hz**: Warm, round bass tones
- **1500-2500Hz**: Open, bright tones (classic 303 open)
- **3000-5000Hz**: Cutting leads, percussive attacks
- **6000-8000Hz**: Brilliant, airy textures

#### Resonance/Q Factor
```bash
/mod/voiceN/filter/q <0.5-10>           # Resonance amount
```
**Musical Applications**:
- **0.5-1.5**: Natural, gentle filtering
- **2.0-4.0**: Sweet spot for musical resonance
- **5.0-7.0**: Aggressive acid filtering  
- **8.0-10.0**: Extreme, screaming resonance (use sparingly)

### ADSR Envelope Shaping

#### Attack Time
```bash
/mod/voiceN/adsr/attack <0.001-2>       # Seconds
```
**Musical Applications**:
- **0.001-0.01s**: Sharp, percussive attacks (kicks, plucks)
- **0.01-0.05s**: Punchy attacks with slight softness
- **0.1-0.3s**: Gentle swells for pads
- **0.5-2.0s**: Cinematic rises and buildups

#### Decay Time
```bash
/mod/voiceN/adsr/decay <0-2>            # Seconds  
```
**Musical Applications**:
- **0-0.05s**: No decay, immediate sustain
- **0.1-0.3s**: Classic analog decay for plucks
- **0.5-1.0s**: Slow decay for evolving textures
- **1.0-2.0s**: Long decay for ambient sounds

#### Sustain Level
```bash
/mod/voiceN/adsr/sustain <0-1>          # Level (0-100%)
```
**Musical Applications**:
- **0**: Full decay to silence (pluck/stab sounds)
- **0.3-0.5**: Partial sustain for evolving tones
- **0.7-0.9**: Strong sustain for held notes
- **1.0**: No decay, sustain at full level

#### Release Time
```bash
/mod/voiceN/adsr/release <0.01-3>       # Seconds
```
**Musical Applications**:
- **0.01-0.1s**: Abrupt cuts, staccato playing
- **0.2-0.5s**: Natural instrument-like releases
- **0.5-1.5s**: Smooth, flowing releases
- **2.0-3.0s**: Extended ambient tails

### Slide/Portamento System

#### Slide Time Control
```bash
/mod/voiceN/slide_time <0-1.5>          # Seconds
```
**Musical Applications**:
- **0**: No portamento, instant frequency changes
- **0.05-0.2s**: Fast slides for subtle glides
- **0.2-0.5s**: Classic synth portamento
- **0.5-1.5s**: Dramatic pitch sweeps and effects

## TB-303 Acid Filter (voice2)

### Core Acid Parameters

#### Cutoff Frequency
```bash
/mod/acid1/cutoff <80-5000>             # Base cutoff Hz
```
**Classic TB-303 Sweet Spots**:
- **150-300Hz**: Deep, closed acid bass
- **800-1200Hz**: Mid-range squelch
- **1500-2000Hz**: Classic open acid sound
- **2500-4000Hz**: Bright, aggressive leads

#### Resonance Amount  
```bash
/mod/acid1/res <0-0.98>                 # Resonance (avoid 1.0)
```
**Musical Applications**:
- **0.2-0.4**: Gentle filtering, musical resonance
- **0.45-0.65**: Classic TB-303 sweet spot
- **0.7-0.85**: Aggressive squelch and scream
- **0.9-0.98**: Extreme resonance (use carefully)

#### Envelope Modulation
```bash
/mod/acid1/env_amount <0-5000>          # Hz modulation depth
```
**Sweet Spots**:
- **500-1000Hz**: Subtle filter movement
- **1500-2500Hz**: Classic acid sweep range
- **3000-4000Hz**: Dramatic filter sweeps
- **4000-5000Hz**: Extreme modulation effects

#### Envelope Decay
```bash
/mod/acid1/decay <0.02-1.0>             # Seconds
```
**Musical Applications**:
- **0.02-0.1s**: Fast, percussive filter hits
- **0.15-0.3s**: Classic TB-303 timing
- **0.4-0.7s**: Slow, evolving filter sweeps
- **0.8-1.0s**: Extended filter movements

### Acid Character Controls

#### Pre-Filter Drive
```bash
/mod/acid1/drive <0-1>                  # Distortion amount
```
**Musical Applications**:
- **0-0.2**: Clean, pure acid tone
- **0.2-0.4**: Subtle harmonic enhancement
- **0.5-0.7**: Aggressive bite and grit
- **0.8-1.0**: Heavy saturation and crunch

#### Wet/Dry Mix
```bash
/mod/acid1/mix <0-1>                    # Processed/original mix
```
**Applications**:
- **0**: Bypass acid filter (clean voice2)
- **0.5**: Parallel processing, half acid/half clean
- **0.8-1.0**: Full acid processing (typical)

#### Volume Compensation
```bash
/mod/acid1/vol_comp <0-1>               # Resonance compensation
```
**Settings**:
- **0.3-0.5**: Moderate compensation
- **0.5**: Balanced compensation (default)
- **0.7-0.8**: Strong compensation for high resonance

## LFO Modulation System

### LFO1 - Wobble Bass (voice2 filter)

#### Rate Control
```bash
/mod/lfo1/rate <0.01-10>                # Hz
```
**Musical Applications**:
- **0.05-0.2Hz**: Slow, hypnotic wobbles (4-20 second cycles)
- **0.25-0.5Hz**: Classic dubstep wobble (2-4 second cycles)
- **0.5-1.0Hz**: Fast wobble bass effects
- **2.0-4.0Hz**: Tremolo-like rapid modulation

#### Depth Control
```bash
/mod/lfo1/depth <0-1>                   # Modulation amount
```
**Musical Applications**:
- **0.3-0.5**: Subtle filter movement
- **0.6-0.8**: Strong wobble character (recommended)
- **0.9-1.0**: Extreme filter sweeps

**Pre-configured routing**: LFO1 → voice2 filter cutoff (±800Hz range)

### LFO2 - Tremolo (voice3 amplitude)

#### Rate Control
```bash
/mod/lfo2/rate <0.01-10>                # Hz
```
**Musical Applications**:
- **2.0-4.0Hz**: Classic tremolo effect
- **4.0-6.0Hz**: Fast tremolo for leads
- **6.0-8.0Hz**: Rapid amplitude modulation
- **8.0-10.0Hz**: Extreme flutter effects

#### Depth Control
```bash
/mod/lfo2/depth <0-1>                   # Tremolo intensity
```
**Musical Applications**:
- **0.1-0.3**: Subtle amplitude variation (recommended)
- **0.4-0.6**: Noticeable tremolo effect
- **0.7-1.0**: Dramatic amplitude modulation

**Pre-configured routing**: LFO2 → voice3 amplitude (0.2-1.0 range)

## Effects Processing

### Master Distortion (dist1)

#### Drive Amount
```bash
/mod/dist1/drive <0-1>                  # Distortion intensity
```
**Musical Applications**:
- **0-0.2**: Subtle warmth and harmonic enhancement
- **0.2-0.4**: Moderate crunch for character
- **0.4-0.6**: Heavy distortion for aggressive sounds
- **0.6-1.0**: Extreme saturation (use sparingly)

#### Wet/Dry Mix
```bash
/mod/dist1/mix <0-1>                    # Processed signal mix
```
**Applications**:
- **0**: Bypass (clean signal)
- **0.3-0.5**: Parallel distortion (retains dynamics)
- **0.7-0.9**: Mostly distorted with clean blend
- **1.0**: Full distortion processing

#### Tone Control
```bash
/mod/dist1/tone <0-1>                   # Brightness control
```
**Applications**:
- **0-0.3**: Dark, muffled distortion
- **0.4-0.6**: Balanced tone (recommended)
- **0.7-1.0**: Bright, cutting distortion

### Global Reverb (reverb1)

#### Wet/Dry Mix
```bash
/mod/reverb1/mix <0-1>                  # Reverb amount
```
**Musical Applications**:
- **0.1-0.3**: Subtle space and width
- **0.3-0.5**: Moderate reverb for leads
- **0.5-0.7**: Ambient, spacious sounds
- **0.8-1.0**: Deep ambient textures

#### Room Size
```bash
/mod/reverb1/room <0-1>                 # Space size
```
**Applications**:
- **0-0.3**: Tight, small room reverb
- **0.4-0.6**: Medium hall reverb
- **0.7-0.9**: Large space reverb
- **1.0**: Infinite, ambient space

#### Damping Control
```bash
/mod/reverb1/damp <0-1>                 # High frequency damping
```
**Applications**:
- **0-0.3**: Bright, metallic reverb
- **0.4-0.6**: Natural reverb decay
- **0.7-1.0**: Dark, warm reverb tails

### Per-Voice Reverb Sends
```bash
/mod/voiceN/send/reverb <0-1>           # Send level per voice
```

### Global Delay (delay1)

#### Delay Time
```bash
/mod/delay1/time <0.1-0.6>              # Seconds
```
**Musical Applications**:
- **0.125s**: 1/8 note at 120 BPM
- **0.25s**: 1/4 note at 120 BPM  
- **0.375s**: Dotted 1/4 note at 120 BPM
- **0.5s**: 1/2 note at 120 BPM

#### Feedback Amount
```bash
/mod/delay1/feedback <0-0.7>            # Repetition amount
```
**Applications**:
- **0.1-0.3**: Subtle echo enhancement
- **0.3-0.5**: Moderate delay repeats
- **0.5-0.7**: Strong delay patterns (max safe value)

#### Mix Control
```bash
/mod/delay1/mix <0-1>                   # Wet/dry balance
```

#### Filtering Controls
```bash
/mod/delay1/lowcut <20-1000>            # High-pass filter Hz
/mod/delay1/highcut <1000-10000>        # Low-pass filter Hz
```

### Per-Voice Delay Sends
```bash
/mod/voiceN/send/delay <0-1>            # Send level per voice
```

## Integrated Sequencer System

### Pattern Notation
- **X**: Accent hit (velocity 1.0, filter boost)
- **x**: Normal hit (velocity 0.6)  
- **.**: Rest (no trigger)

### Sequencer Control
```bash
/seq/start                              # Start sequencer
/seq/stop                               # Stop and gate off all voices
/seq/bpm <30-300>                       # Set tempo
/seq/swing <0-0.6>                      # Add timing swing
/seq/clear                              # Remove all tracks
```

### Track Management
```bash
/seq/add <track_id> <voice_id> <pattern> [base_freq] [filter_freq] [notes]
/seq/remove <track_id>
/seq/update/pattern <track_id> <new_pattern>
/seq/update/notes <track_id> <notes_string>
```

### Musical Pattern Examples

#### Kick Patterns
```bash
/seq/add kick voice1 "X...X...X...X..." 60 200
/seq/add kick voice1 "X...X..X..X....." 60 200    # Syncopated
```

#### Bass Patterns
```bash
/seq/add bass voice2 "x.x.x.x.x.x.x.x." 110 800
/seq/add bass voice2 "X.x.X.x.X.x.X.x." 110 600  # Accented
```

#### Hi-hat Patterns  
```bash
/seq/add hats voice3 "x.x.x.x.x.x.x.X." 1000 4000
/seq/add hats voice3 "xxxx.xx.xxxx.xx." 800 3000  # Busy pattern
```

#### Lead Patterns
```bash
/seq/add lead voice4 "....X.......X..." 440 2000
/seq/add lead voice4 "..x...x...X....." 660 2500  # Syncopated lead
```

## Musical Sweet Spots & Combinations

### Classic Acid Bassline Setup
```bash
# Voice2 for acid bass
/mod/voice2/freq 110                    # A2 fundamental
/mod/voice2/osc/type 1                  # Saw wave
/mod/voice2/amp 0.6                     # Strong level
/mod/voice2/filter/freq 1200            # Mid-range filter

# Acid filter settings
/mod/acid1/cutoff 800                   # Mid-range base
/mod/acid1/res 0.65                     # Strong resonance
/mod/acid1/env_amount 2000              # Good sweep range
/mod/acid1/decay 0.2                    # Classic timing
/mod/acid1/drive 0.3                    # Some bite
/mod/acid1/mix 1.0                      # Full acid processing

# LFO1 wobble
/mod/lfo1/rate 0.25                     # 4-second wobble cycle
/mod/lfo1/depth 0.7                     # Strong modulation
```

### Techno Kick Setup
```bash
# Voice1 for kick
/mod/voice1/freq 60                     # Deep fundamental
/mod/voice1/osc/type 0                  # Sine wave
/mod/voice1/amp 0.8                     # Punchy level
/mod/voice1/filter/freq 200             # Low-pass for thump
/mod/voice1/filter/q 1.0                # Natural Q
/mod/voice1/adsr/attack 0.001           # Sharp attack
/mod/voice1/adsr/decay 0.15             # Quick decay
/mod/voice1/adsr/sustain 0.0            # No sustain
/mod/voice1/adsr/release 0.1            # Quick release
```

### Ambient Pad Setup
```bash
# Voice3 for pad
/mod/voice3/freq 220                    # A3 base
/mod/voice3/osc/type 0                  # Sine wave
/mod/voice3/amp 0.3                     # Subtle level
/mod/voice3/filter/freq 1000            # Open filter
/mod/voice3/filter/q 0.7                # Gentle resonance
/mod/voice3/adsr/attack 0.5             # Slow attack
/mod/voice3/adsr/decay 0.3              # Moderate decay
/mod/voice3/adsr/sustain 0.8            # High sustain
/mod/voice3/adsr/release 1.5            # Long release
/mod/voice3/send/reverb 0.6             # Heavy reverb

# LFO2 tremolo for movement
/mod/lfo2/rate 3.0                      # 3Hz tremolo
/mod/lfo2/depth 0.2                     # Subtle modulation

# Reverb settings for space
/mod/reverb1/mix 0.4                    # Moderate reverb
/mod/reverb1/room 0.8                   # Large space
/mod/reverb1/damp 0.6                   # Warm character
```

### Lead Synth Setup
```bash
# Voice4 for lead
/mod/voice4/freq 440                    # A4 reference
/mod/voice4/osc/type 1                  # Saw wave
/mod/voice4/amp 0.7                     # Prominent level
/mod/voice4/filter/freq 2500            # Bright filter
/mod/voice4/filter/q 3.0                # Resonant bite
/mod/voice4/adsr/attack 0.01            # Quick attack
/mod/voice4/adsr/decay 0.2              # Moderate decay
/mod/voice4/adsr/sustain 0.6            # Partial sustain
/mod/voice4/adsr/release 0.3            # Natural release
/mod/voice4/send/delay 0.4              # Delay for width

# Delay settings for lead
/mod/delay1/time 0.375                  # Dotted 1/4 note
/mod/delay1/feedback 0.4                # Moderate repeats
/mod/delay1/mix 0.3                     # Moderate wet level
/mod/delay1/highcut 4000                # Filter delay for clarity
```

### Frequency Reference Guide

#### Standard Musical Notes (Hz)
- **C2**: 65.4Hz - Sub-bass fundamental
- **A2**: 110Hz - Classic bass tuning
- **C3**: 130.8Hz - Mid-bass range
- **A3**: 220Hz - Upper bass/low mid
- **C4**: 261.6Hz - Middle C
- **A4**: 440Hz - Concert pitch reference
- **C5**: 523.3Hz - Upper mid-range
- **A5**: 880Hz - Lead/melody range

#### Filter Cutoff Reference
- **80-150Hz**: Sub-bass fundamentals only
- **150-400Hz**: Bass range, muffled character
- **400-800Hz**: Low-mids, warm tones
- **800-1600Hz**: Mid-range, presence
- **1600-3200Hz**: Upper mids, brightness
- **3200-6400Hz**: High frequencies, air
- **6400Hz+**: Extreme highs, sparkle

## Control Methods

### Direct OSC Control
```python
from pythonosc import udp_client
client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

# Play note
client.send_message("/mod/voice1/freq", 440)
client.send_message("/gate/voice1", 1)
```

### Command Line Tools
```bash
# Get full schema
python chronusctl.py schema

# Quick test
python chronusctl.py test  

# Set parameter
python chronusctl.py set voice1 freq 440

# Gate control
python chronusctl.py gate voice1 on
```

### Pattern Management
```bash
# Save current pattern
python -c "from pythonosc import udp_client; c = udp_client.SimpleUDPClient('127.0.0.1', 5005); c.send_message('/pattern/save', [1])"

# Load pattern from slot
python -c "from pythonosc import udp_client; c = udp_client.SimpleUDPClient('127.0.0.1', 5005); c.send_message('/pattern/load', [1])"
```

## System Performance & Technical Specifications

### Audio Performance
- **Latency**: 5.3ms (256 samples @ 48kHz)
- **Sample Rate**: 48kHz (configurable)  
- **Buffer Size**: 256 samples (configurable)
- **Polyphony**: 4 voices + effects processing
- **Audio Backend**: pyo with C-based DSP

### Parameter Smoothing
- **Voice Parameters**: 20ms smoothing time
- **Filter Parameters**: 20ms smoothing time
- **Gate Operations**: Instantaneous (no smoothing)
- **LFO Parameters**: 20ms smoothing time

### Threading & Timing
- **Sequencer**: Separate daemon thread
- **OSC Server**: Background thread
- **Timing Precision**: ~1ms (not sample-accurate)
- **Pattern Support**: Unlimited length patterns

### Safety Limits
- **Delay Feedback**: Max 0.7 to prevent runaway
- **Filter Q**: Max 10.0 to prevent instability
- **All Parameters**: Clamped to safe ranges
- **Emergency Stop**: Always available via `/seq/stop`

---

## Quick Start Musical Examples

### 30-Second Acid Techno Loop
```bash
# Start engine
python engine_pyo.py

# Set up acid bassline
python -c "
from pythonosc import udp_client
c = udp_client.SimpleUDPClient('127.0.0.1', 5005)
c.send_message('/seq/add', ['bass', 'voice2', 'X.x.X.x.X.x.X.x.'])
c.send_message('/seq/add', ['kick', 'voice1', 'X...X...X...X...'])
c.send_message('/seq/bpm', [125])
c.send_message('/seq/start', [])
"
```

### Live Parameter Tweaking
```bash
# Sweep acid filter while playing
python -c "
import time
from pythonosc import udp_client
c = udp_client.SimpleUDPClient('127.0.0.1', 5005')
for freq in range(200, 2000, 100):
    c.send_message('/mod/acid1/cutoff', freq)
    time.sleep(0.2)
"
```

This guide provides comprehensive coverage of all Music Chronus capabilities with practical parameter values tested through extensive research and real-world usage patterns.