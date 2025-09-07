# Debugging Engine Crash - System Analysis Document

**Date**: 2025-09-06  
**Author**: Chronus Nexus  
**Purpose**: Document system architecture and methodical debugging approach

## 1. System Architecture Overview

### Components:
```
[Python Script] --OSC--> [engine_pyo.py] --Audio--> [Pyo Server] ---> [Audio Output]
                              |
                              ├── Voice1 (Sine → ADSR → Filter)
                              ├── Voice2 (Sine → ADSR → Filter → ACID)
                              ├── Voice3 (Sine → ADSR → Filter)
                              ├── Voice4 (Sine → ADSR → Filter)
                              ├── Reverb Bus (global)
                              └── Delay Bus (global)
```

### Data Flow:
1. **OSC Messages** arrive on port 5005 (UDP)
2. **engine_pyo.py** routes messages to appropriate handlers
3. **Voice/Effect modules** update their pyo parameters
4. **Pyo Server** (C backend) processes audio in real-time
5. **Audio output** via system audio device

### Key Facts:
- Pyo runs its audio processing in C, not Python
- OSC handling happens in a separate thread
- All voices share the same pyo server instance
- Acid filter is an insert on voice2's pre-filter signal

## 2. The Problem

### Observed Behavior:
1. Demo script `acid_journey_demo.py` runs normally until bars 25-32
2. At this point, audio stops but no error messages appear
3. Engine becomes unresponsive - subsequent runs produce no audio
4. Engine must be restarted to recover

### What Happens at Bars 25-32:
- Hi-hat pattern begins (voice3 with rapid gates)
- Filter automation continues (sine wave LFO modulation)
- All 3 voices are active simultaneously
- Approximately 16 gates/second being triggered

## 3. Current State of Debugging

### What We Know:
1. **Simple patterns work** - The intro (bars 1-24) plays fine
2. **Acid filter works** - We fixed the signal graph issue earlier
3. **Individual components work** - Each voice works in isolation
4. **No error output** - Engine doesn't report errors when it fails

### What We Don't Know:
1. Is the pyo server actually crashing or just going silent?
2. Are OSC messages still being received after the failure?
3. Is there a buffer overflow or thread deadlock?
4. Is it a specific parameter value or rate of change?

## 4. Proposed Debugging Methodology

### Goal:
Identify the exact cause of engine failure through systematic testing with proper observation methods.

### Testing Approach:

#### Step 1: Add Observability
Before any testing, we need to see what's happening:
- Add message counting to track OSC throughput
- Add periodic status printing to confirm engine is alive
- Monitor pyo server status
- Log the last successful operations before failure

#### Step 2: Isolate Variables
Test ONE thing at a time:
- **Test A**: Hi-hat pattern alone (no other voices)
- **Test B**: Three voices without hi-hats
- **Test C**: Rapid parameter changes without gates
- **Test D**: Rapid gates without parameter changes

#### Step 3: Measure Limits
Once we identify the problematic component:
- Find the threshold (how many messages/second?)
- Determine if it's cumulative or instantaneous
- Test recovery methods

#### Step 4: Implement Solution
Based on findings:
- Rate limiting if it's message flooding
- Buffer management if it's overflow
- Thread synchronization if it's deadlock
- Parameter validation if it's value-related

## 5. Critical Questions to Answer

1. **Does the pyo server actually crash or just stop processing?**
   - Test: Check if server.getIsStarted() returns False after failure

2. **Are OSC messages still being received?**
   - Test: Add counter that prints every 10th message

3. **Is it the NUMBER of messages or the RATE?**
   - Test: Same number of messages at different rates

4. **Does it happen at a specific moment or build up?**
   - Test: Monitor resource usage over time

## 6. Next Steps

**DO NOT PROCEED WITHOUT APPROVAL**

Once approved, the plan is:
1. Create a modified engine with debugging output
2. Create focused test scripts for each hypothesis
3. Run tests methodically, documenting results
4. Identify root cause
5. Implement minimal fix
6. Verify fix doesn't break other functionality

## 7. Success Criteria

We will know we've succeeded when:
- We can reproduce the failure reliably
- We understand exactly why it fails
- We can prevent the failure
- The full demo runs without issues
- The fix doesn't impact performance

---

**Status**: AWAITING APPROVAL

Please review this document and confirm:
1. Do you agree with the system architecture description?
2. Is the debugging methodology sound?
3. Should we proceed with Step 1 (Add Observability)?