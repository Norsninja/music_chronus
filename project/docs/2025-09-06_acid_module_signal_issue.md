# Acid Module Signal Routing Issue - Debug Report

**Date**: 2025-09-06  
**Issue**: Acid filter module blocks all audio output from voice2  
**Status**: UNRESOLVED - Need Senior Dev assistance

## Problem Description

After implementing the acid filter module with all PyoObject arithmetic fixes, the engine starts successfully but voice2 produces no audible output when the acid filter is engaged (mix > 0).

## Symptoms

1. **Engine starts without errors** - All modules initialize correctly
2. **Voice1, Voice3, Voice4 work normally** - Produce expected audio
3. **Voice2 with acid mix=0 (bypass)** - Produces ONE brief sound ("blip") then silence
4. **Voice2 with acid mix > 0** - Complete silence, no audio output
5. **Acid filter parameters** - OSC messages received but no audible effect

## Test Results

### Test 1: Basic Voice Test
- Voice1: ✅ Works normally
- Voice2: ❌ One blip then silence (even with acid bypassed)
- Voice3: ✅ Works normally
- Voice4: ✅ Works normally

### Test 2: Acid Mix Levels
- mix=0.0 (bypass): One blip, then silence
- mix=0.25: Silence
- mix=0.5: Silence
- mix=1.0: Silence

### Test 3: Acid Parameters
Tested with various parameter combinations:
- Wide open filter (cutoff=5000, res=0): Silence
- Normal filter (cutoff=1000, res=0.5): Silence
- Minimal processing (no env, no drive): Silence

## Implementation Details

### Current Signal Flow
```
voice2.output → acid1.input → Disto → MoogLP → Clip → Interp(dry,wet,mix) → acid1.output
```

### Engine Routing (engine_pyo.py)
```python
# Line 95-97: Replace voice2 dry signal with acid output
if voice_id == 'voice2':
    dry_signals.append(self.acid1.get_output())
else:
    dry_signals.append(voice.get_dry_signal())
```

### Acid Module Key Components
1. **Input**: Takes voice2's dry signal directly
2. **Envelopes**: Created with numeric values (fixed from PyoObject issue)
3. **Signal chain**: All using PyoObject arithmetic
4. **Output**: Returns self.output (Interp object)

## What We've Verified

### ✅ Fixed Issues
- PyoObject arithmetic for drive/slope mapping
- Numeric values for ADSR parameters
- Proper Clip() usage instead of Python min/max
- References kept to prevent GC

### ✅ Correct Patterns
- Disto receives PyoObjects for drive/slope
- MoogLP receives PyoObjects for freq/res
- All intermediate signals stored as self.* attributes
- Gate routing triggers both voice2 and acid1 envelopes

### ❓ Potential Issues
1. **Signal not computing**: Acid output might not be in active signal graph
2. **Voice2 base issue**: Even bypassed acid (mix=0) only produces one blip
3. **Interp issue**: Wet/dry mixing might not be working correctly
4. **Missing .play() or .out()**: Some PyoObjects might need explicit activation

## Code Sections of Interest

### 1. Acid Output Method (acid.py:254-256)
```python
def get_output(self):
    """Get the processed output signal"""
    return self.output  # self.output is Interp(input, clipped, mix)
```

### 2. Signal Chain Creation (acid.py:113-179)
- Creates complex chain with multiple PyoObject operations
- All stored as instance attributes
- Ends with Interp for wet/dry mix

### 3. Engine Integration (engine_pyo.py:77-82)
```python
self.acid1 = AcidFilter(
    self.voices['voice2'].get_dry_signal(),
    voice_id="acid1",
    server=self.server
)
```

## Questions for Senior Dev

1. **Why does voice2 only produce one blip even with acid bypassed (mix=0)?**
   - This suggests the issue might be in how we're routing voice2's output
   - The Interp with mix=0 should pass the dry signal unchanged

2. **Do we need to explicitly start/play the acid module's signal chain?**
   - Voice module works without explicit .play() or .out()
   - But acid has more complex signal routing

3. **Is the Interp object being computed correctly?**
   - Using: `self.output = Interp(self.input_signal, self.clipped, self.mix)`
   - Should this work as a return value for get_output()?

4. **Could the issue be with how we're consuming acid output in the Mix?**
   - We're putting acid1.get_output() directly into Mix()
   - Is this the right way to route it?

## Next Debugging Steps

1. **Check if voice2 works WITHOUT acid module existing**
   - Comment out acid creation and routing
   - Test if voice2 works normally then

2. **Add debug prints to verify signal flow**
   - Print types of signals at each stage
   - Verify get_output() returns valid PyoObject

3. **Try simpler acid implementation**
   - Start with just passthrough
   - Add components one by one

4. **Test Interp separately**
   - Verify Interp works with our signal setup
   - Try different mix object types

## Files to Review

- `pyo_modules/acid.py` - Full implementation
- `engine_pyo.py` - Lines 77-82 (creation), 89-125 (routing)
- `examples/test_acid_simple.py` - Simplest test case

---

*Report prepared for Senior Dev review*  
*Issue blocks all acid filter functionality*