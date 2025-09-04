# Emergency Fill Root Cause Analysis

**Date**: 2025-09-03  
**Investigator**: Chronus Nexus  
**Issue**: Continuous emergency fills with silent output (RMS=0.0000)

## Executive Summary

The emergency fill cascade was NOT caused by the sequencer implementation. Root cause analysis revealed multiple architectural issues in the supervisor's worker initialization, specifically around ADSR gate handling and router mode logic. All workers produce silent buffers due to an incorrect gate setting method that leaves the ADSR envelope at zero.

## Issue Symptoms

```
[WORKER 0] Prefill 1: RMS=0.0000
[WORKER 0] EMERGENCY FILL: occ=0, producing one buffer immediately
[WORKER 0] Emergency fill complete: RMS=0.0000, new occ=1
```

- Continuous emergency fills even after adding prefill logic
- All buffers silent (RMS=0.0000) 
- Issue persists with sequencer completely removed
- Affects both Worker 0 (active) and Worker 1 (standby)

## System Architecture Overview

### Router Mode Operation (`CHRONUS_ROUTER=1`)

```
Worker 0 (Active Slot)
├── use_router = False (it's active, not standby)
├── Should start EMPTY in router mode
└── Currently gets hardcoded chain (BUG)

Worker 1 (Standby Slot)  
├── use_router = True (it's standby)
├── Empty PatchRouter awaiting OSC commands
└── Correctly starts empty
```

### Module Processing Pipeline

#### Non-Router Mode (Linear Chain)
```python
# Automatic serial connection
sine1 → adsr1 → filter1
│        │        │
↓        ↓        ↓
generate multiply filter
440Hz    by env   frequencies
```

#### Router Mode (Dynamic Patching)
- Modules added via `/patch/create`
- Connections via `/patch/connect`
- Committed via `/patch/commit`
- Supports complex DAGs

## Root Cause Analysis

### Finding 1: ADSR Gate Never Actually Triggered

**Location**: `supervisor_v3_router.py` line 116

**Current Code**:
```python
adsr_module.set_param("gate", 1.0, immediate=True)  # WRONG!
```

**Why It Fails**:
1. ADSR doesn't handle "gate" via `set_param()`
2. It requires a dedicated `set_gate()` method
3. The ModuleHost normally translates this, but we're calling on bare module
4. Result: Gate remains at 0, envelope stays in IDLE

**Required Fix**:
```python
adsr_module.set_gate(True)  # Correct method
```

### Finding 2: Module Chain Processing Details

**ModuleHost Chain Processing** (`module_host.py` lines 358-371):
```python
current_buf = self.chain_buffers[0]  # Start with silence

for module in modules:
    next_buf = self.chain_buffers[(i + 1)]
    module.process_buffer(current_buf, next_buf)
    current_buf = next_buf  # Chain output→input
    
return current_buf  # Final output
```

**Key Insights**:
- Modules automatically connect in `add_module()` order
- No explicit wiring needed in non-router mode
- Each module's output becomes next module's input

### Finding 3: Why ADSR Outputs Silence

**ADSR Processing Logic** (`adsr.py` lines 194-196):
```python
if in_buf is not None:
    out_buf[i] = in_buf[i] * self._level  # Multiply by envelope
else:
    out_buf[i] = self._level  # Output envelope directly
```

**Critical Understanding**:
- ADSR is a processor, not generator
- It multiplies input by envelope level
- If envelope = 0 (gate not triggered): output = input × 0 = 0
- Even with 440Hz sine input, output is silence

### Finding 4: Router Mode Logic Flaw

**Current Implementation** (`supervisor_v3_router.py` lines 84-118):
```python
if use_router:  # Standby slot
    # Create empty router (CORRECT)
    router = PatchRouter(BUFFER_SIZE)
    module_host.enable_router(router)
else:  # Active slot OR router disabled
    # Create default chain (WRONG for router mode!)
    sine_module = SimpleSine(...)
    adsr_module = ADSR(...)
    filter_module = BiquadFilter(...)
```

**The Problem**:
- `use_router` indicates if THIS WORKER is standby
- But doesn't check if SYSTEM is in router mode
- Worker 0 gets default chain even when system expects dynamic patching

**Correct Logic Should Be**:
```python
if USE_ROUTER:  # System in router mode
    if is_standby:
        # Standby: Create router for building patches
    else:
        # Active: Start empty, wait for committed patches
else:  # Traditional mode
    if not is_standby:
        # Active: Create default chain
```

### Finding 5: Prefill Timing Issue

**Added Prefill** (lines 120-130):
- Prefills 3 buffers before main loop
- But still produces silence due to gate issue
- Prefill happens AFTER module setup, so inherits the silence problem

## Module-Specific Analysis

### SimpleSine Module
- **Type**: Generator (ignores input)
- **Defaults**: freq=440Hz, gain=0.5
- **Status**: Parameters set correctly
- **Output**: Should generate 440Hz tone

### ADSR Module  
- **Type**: Processor (needs input)
- **Gate Handling**: Requires `set_gate()` not `set_param("gate")`
- **Envelope Stages**: IDLE → ATTACK → DECAY → SUSTAIN → RELEASE → IDLE
- **Current State**: Stuck in IDLE (envelope=0) due to gate not triggered

### BiquadFilter Module
- **Type**: Processor
- **Input**: Receives silence from ADSR
- **Output**: Filtered silence = silence

## Why Emergency Fills Cascade

1. **Initial State**: Ring empty (occ=0)
2. **Prefill Attempt**: Generates 3 silent buffers
3. **Audio Callback Starts**: Consumes buffers faster than produced
4. **Emergency Trigger**: occ=0 detected, emergency fill
5. **Silent Output**: Emergency fill produces RMS=0.0000
6. **Repeat**: Callback consumes, ring empties, emergency triggered

The emergency fills are a symptom, not the cause. The real issue is all audio generation produces silence.

## Architectural Recommendations

### 1. Fix ADSR Gate Method
Change line 116 from:
```python
adsr_module.set_param("gate", 1.0, immediate=True)
```
To:
```python
adsr_module.set_gate(True)
```

### 2. Fix Router Mode Initialization
Worker 0 should check system router mode:
```python
if USE_ROUTER:
    # Both workers start empty in router mode
    if is_standby:
        setup_router()
    # else: active starts empty
else:
    # Traditional mode - active gets default chain
    if not is_standby:
        setup_default_chain()
```

### 3. Improve Prefill Validation
Add RMS checking during prefill:
```python
if rms < 0.001:
    print(f"WARNING: Prefill producing silence!")
```

### 4. Consider Module Active State
Verify all modules have `active=True` before processing.

## Testing Recommendations

1. **Immediate Test**: Fix gate method and verify non-zero RMS
2. **Router Mode Test**: Ensure Worker 0 starts empty when `CHRONUS_ROUTER=1`
3. **Traditional Mode Test**: Verify default chain works with `CHRONUS_ROUTER=0`
4. **Sequencer Integration**: Only after core audio works

## Lessons Learned

1. **Method Signatures Matter**: `set_param()` vs `set_gate()` have different behaviors
2. **Router Mode Complexity**: The `use_router` flag indicates worker role, not system mode
3. **Silent Failures**: ADSR silently outputs zeros when gate not triggered
4. **Emergency Fills Are Symptoms**: They indicate consumption > production, not the root cause
5. **Module Chain Dependencies**: Processor modules need valid input to produce output

## Conclusion

The emergency fill cascade was caused by a simple but critical bug: using the wrong method to trigger the ADSR gate. This left the envelope at zero, causing the entire audio chain to produce silence. The issue was compounded by architectural confusion around router mode initialization.

The sequencer implementation was completely unrelated to this issue and can be safely re-integrated once the core audio pipeline is fixed.

---
*Analysis prepared by Chronus Nexus*  
*Ready for Senior Dev review and remediation*