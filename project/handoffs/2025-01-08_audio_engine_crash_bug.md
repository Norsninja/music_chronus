# Critical Bug: Audio Engine Failure with Distortion

**Created**: 2025-01-08  
**Severity**: CRITICAL  
**Status**: Unresolved - Requires Investigation  
**Impact**: Complete audio failure, no recovery without engine restart

## 🚨 Bug Description

The pyo audio engine completely fails (audio "squelches out" and goes silent) when certain parameter combinations are reached. This occurs consistently at Bar 3 of the Industrial Nightmare composition, suggesting it's triggered by specific parameter values rather than duration.

## Reproduction Steps

1. Start `engine_pyo.py`
2. Start `visualizer.py` 
3. Run `python chronus_song_industrial_nightmare.py`
4. Audio fails at exactly Bar 3 of intro phase (approximately 5-6 seconds in)

## Symptoms

1. **Audio Output**: Complete silence after a "squelch" sound
2. **Engine Process**: Still running (no crash or error messages)
3. **OSC Communication**: Still responsive to commands
4. **Visualizer**: Initially crashed with NaN values, now handles them but audio still fails
5. **Recovery**: Only engine restart recovers audio

## Attempted Fixes That FAILED

1. **Reduced resonance**: 0.98 → 0.75 - Still crashes
2. **Reduced acid drive**: 1.0 → 0.5 - Still crashes  
3. **Reduced master distortion**: 1.0 → 0.2 starting value - Still crashes
4. **Lower overall levels**: All voices at 0.2 amplitude - Still crashes

## Suspected Causes

### Primary Hypothesis: Parameter Combination at Bar 3
```python
# Bar 3 executes this code:
drive = 0.2 + (3 * 0.02)  # = 0.26
self.osc.set_distortion(drive=0.26, mix=0.23)
```
This seemingly mild distortion increase triggers failure.

### Possible Root Causes:

1. **Feedback Loop**: Distortion + resonance creating positive feedback
2. **NaN Propagation**: Invalid values propagating through DSP chain
3. **Buffer Overflow**: Audio buffers exceeding safe ranges
4. **Pyo Server State**: Server enters error state but doesn't report it
5. **Filter Self-Oscillation**: Even at 0.75 resonance with distortion

## Critical Code Locations

**engine_pyo.py**:
- Lines 850-859: Bandpass spectrum analyzer (might generate NaN)
- Lines 600-650: DistortionModule implementation
- Lines 400-450: AcidModule with resonance control
- Lines 924-936: Spectrum broadcast (sending NaN values)

**chronus_song_industrial_nightmare.py**:
- Lines 79-84: Bar loop where crash occurs
- Line 82: `set_distortion()` call that triggers failure

## Data When Crash Occurs

- Kick pattern: 'X...X...X...X...'
- Distortion: drive=0.26, mix=0.23
- Acid: cutoff=150, res=0.75, drive=0.5
- Voice1: freq=45Hz, amp=0.2
- No other voices active yet

## Required Investigation

### 1. Engine-Side Debugging
```python
# Add to engine_pyo.py before line 850:
def check_audio_health(self):
    """Monitor for NaN/Inf in audio chain"""
    try:
        master_val = self.master.get()
        if math.isnan(master_val) or math.isinf(master_val):
            print(f"[ERROR] Invalid audio value detected: {master_val}")
            # Attempt recovery?
    except:
        pass
```

### 2. Distortion Module Analysis
- Check if pyo's Disto object has overflow protection
- Test distortion in isolation with extreme values
- Monitor for value ranges exceeding [-1, 1]

### 3. Protection Mechanisms Needed
```python
# Potential fix in DistortionModule:
class DistortionModule:
    def __init__(self, source, name="dist1"):
        # Add limiter before distortion
        self.limiter = Compress(source, thresh=-3, ratio=100)  
        self.distortion = Disto(self.limiter, ...)
```

### 4. Test Minimal Reproduction
```python
# Minimal test case:
from pythonosc import udp_client
import time

c = udp_client.SimpleUDPClient('127.0.0.1', 5005)

# Start simple kick
c.send_message('/seq/add', ['kick', 'voice1', 'X...X...X...X...', 45, 60])
c.send_message('/seq/start', [])

# Wait then add distortion gradually
for i in range(10):
    drive = i * 0.05
    print(f"Setting distortion to {drive}")
    c.send_message('/mod/dist1/drive', drive)
    c.send_message('/mod/dist1/mix', drive)
    time.sleep(2)
    # Does it fail at a specific value?
```

## Temporary Workaround

For now, avoid using distortion in compositions:
```python
# Comment out all distortion calls:
# self.osc.set_distortion(drive=0.3, mix=0.3, tone=0.2)
```

## Next Steps

1. **Add comprehensive logging** to engine audio chain
2. **Test each DSP module in isolation** with extreme values
3. **Implement audio limiting/protection** before distortion
4. **Consider alternative distortion algorithm** (waveshaping vs Disto)
5. **Add server health monitoring** to detect error states

## Session Context

- Fixed OSC handler return value bugs successfully
- Created ChronusOSC wrapper for cleaner command interface
- Built 3 complete songs (Techno Journey, Acid Dreams work fine)
- Industrial Nightmare exposes critical engine vulnerability
- Visualizer now handles NaN values properly

## Priority for Next Session

**CRITICAL**: This bug makes the engine unusable for heavy/distorted music. Must be fixed before creating more aggressive compositions.

---
_This is a show-stopper bug that needs thorough investigation with the codebase-researcher and technical-scout agents in the next session._