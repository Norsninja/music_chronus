# Natural Language to OSC Mapping Contract

**Version**: 1.0  
**Date**: 2025-09-01  
**Purpose**: Define how Chronus Nexus interprets musical intent into OSC commands

## Overview

This document defines the mapping between natural language musical instructions and OSC (Open Sound Control) messages that control the Music Chronus synthesizer.

## Core Principles

1. **Musical Intent First** - Commands express musical goals, not technical parameters
2. **Context Aware** - Previous commands provide context for ambiguous instructions
3. **Safe Defaults** - Ambiguous commands use musically sensible defaults
4. **Gradual Changes** - Large parameter jumps are smoothed unless "immediate" is specified

## Command Categories

### 1. Note/Pitch Commands

**Natural Language Patterns:**
- "play [note]" → Set oscillator frequency
- "play [note] [octave]" → Specific octave
- "go up/down [interval]" → Relative pitch change
- "glide to [note]" → Portamento

**OSC Mappings:**
```
"play C4" → /mod/sine/freq 261.63
"play A above middle C" → /mod/sine/freq 440.0
"go up a fifth" → /mod/sine/freq [current * 1.5]
"glide to E3" → /mod/sine/glide_time 200
              → /mod/sine/freq 164.81
```

### 2. Volume/Dynamics Commands

**Natural Language Patterns:**
- "louder/quieter" → Adjust gain ±20%
- "volume [0-10]" → Set absolute level
- "fade in/out" → Gradual change
- "[pp|p|mp|mf|f|ff]" → Musical dynamics

**OSC Mappings:**
```
"louder" → /mod/sine/gain [current * 1.2]
"volume 7" → /mod/sine/gain 0.7
"fade out" → /mod/adsr/release 2000
           → /gate/adsr off
"play forte" → /mod/sine/gain 0.8
```

### 3. Timbre/Tone Commands

**Natural Language Patterns:**
- "brighter/darker" → Adjust filter cutoff
- "add warmth" → Lower cutoff, increase resonance
- "make it harsh" → Add harmonics/distortion
- "smooth/mellow" → Reduce high frequencies

**OSC Mappings:**
```
"brighter" → /mod/filter/cutoff [current * 1.5]
"add warmth" → /mod/filter/cutoff 800
             → /mod/filter/q 2.0
"darker tone" → /mod/filter/cutoff [current * 0.7]
```

### 4. Rhythm/Timing Commands

**Natural Language Patterns:**
- "faster/slower" → Adjust tempo/rate
- "play [duration]" → Note length
- "staccato/legato" → Adjust envelope
- "add swing" → Timing variation

**OSC Mappings:**
```
"play short notes" → /mod/adsr/attack 5
                   → /mod/adsr/release 50
"legato" → /mod/adsr/attack 50
         → /mod/adsr/release 500
"faster attack" → /mod/adsr/attack [current * 0.5]
```

### 5. Modulation Commands

**Natural Language Patterns:**
- "add vibrato" → LFO to pitch
- "wobble the filter" → LFO to cutoff
- "tremolo" → LFO to amplitude
- "slow/fast modulation" → LFO rate

**OSC Mappings:**
```
"add vibrato" → /mod/lfo/freq 5.0
              → /mod/lfo/depth 0.1
              → /mod/lfo/shape 0  # sine
              → /patch lfo sine.freq_mod

"wobble bass" → /mod/lfo/freq 0.5
              → /mod/lfo/depth 0.8
              → /patch lfo filter.cutoff_mod
```

### 6. Effects Commands

**Natural Language Patterns:**
- "add reverb/delay/echo" → Effect amount
- "dry/wet" → Effect mix
- "spacious/tight" → Room size
- "feedback" → Delay feedback

**OSC Mappings:**
```
"add reverb" → /mod/reverb/mix 0.3
             → /mod/reverb/size 0.7
"more echo" → /mod/delay/mix [current + 0.2]
            → /mod/delay/feedback 0.6
```

## Complex Mappings

### Musical Phrases
```
"play a mysterious chord"
→ /mod/sine/freq 220.0   # A3
→ /mod/sine2/freq 277.18  # C#4
→ /mod/sine3/freq 329.63  # E4
→ /mod/filter/cutoff 600
→ /mod/reverb/mix 0.5
```

### Style Presets
```
"techno bass"
→ /mod/sine/shape 3      # saw wave
→ /mod/filter/mode 0      # lowpass
→ /mod/filter/cutoff 200
→ /mod/filter/q 5.0
→ /mod/adsr/attack 0
→ /mod/adsr/decay 100
→ /mod/adsr/sustain 0.3
```

### Relative Commands
```
"make it more like a flute"
→ /mod/sine/shape 0       # sine
→ /mod/filter/cutoff 4000
→ /mod/adsr/attack 30
→ /mod/lfo/freq 4.5       # vibrato
→ /mod/lfo/depth 0.05
```

## Context Resolution

The system maintains context to resolve ambiguous commands:

```python
context = {
    "last_note": "C4",
    "last_octave": 4,
    "current_scale": "major",
    "tempo": 120,
    "key": "C"
}

# "play the fifth" uses context
# → Resolves to G4 if last_note was C4
```

## Safety Limits

All parameters are bounded to prevent damage:

- Frequency: 20Hz - 20kHz
- Gain: 0.0 - 1.0 (with compression above 0.9)
- Filter Q: 0.1 - 20.0
- LFO rate: 0.01Hz - 20Hz

## Implementation Example

```python
class NLtoOSC:
    def parse(self, text: str) -> List[OSCMessage]:
        """Convert natural language to OSC messages"""
        
        # Tokenize and identify intent
        tokens = text.lower().split()
        messages = []
        
        if "play" in tokens:
            # Extract note/frequency
            note = self.extract_note(tokens)
            freq = self.note_to_freq(note)
            messages.append(("/mod/sine/freq", freq))
            
        if "louder" in tokens:
            current = self.context.get("gain", 0.5)
            messages.append(("/mod/sine/gain", min(1.0, current * 1.2)))
            
        return messages
```

## Testing Commands

```bash
# Test natural language parsing
echo "play a warm C major chord" | python nl_to_osc.py

# Expected output:
/mod/sine/freq 261.63
/mod/sine2/freq 329.63
/mod/sine3/freq 392.0
/mod/filter/cutoff 800
/mod/filter/q 2.0
```

## Future Extensions

1. **Chord Recognition**: "play Cmaj7" → Multiple oscillator frequencies
2. **Progression**: "play I-IV-V-I" → Sequence of changes
3. **Emotional Mapping**: "make it sad" → Minor key, slower, reverb
4. **Genre Templates**: "dubstep wobble" → Complex LFO+filter setup
5. **Performance Gestures**: "crescendo" → Gradual volume increase

---

This contract enables Chronus Nexus to interpret musical intent and translate it into precise OSC commands for real-time synthesis control.