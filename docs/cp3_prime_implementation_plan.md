# CP3 Direct Priming Implementation Plan

**Date**: 2025-09-02  
**Author**: Chronus Nexus  
**Purpose**: Fix silent buffer issue by implementing direct worker priming  
**Based On**: Senior Dev's analysis and recommendations

## Problem Statement

### Current Issue
- Workers produce silent buffers after patch commit/swap
- 44% none-reads despite healthy ring occupancy (occ=2)
- Brief audio then silence pattern indicates state loss

### Root Cause
- **Current priming via OSC/command rings is unreliable**
  - Commands sent to both slots after commit (lines 476-518)
  - No guarantee commands are processed before swap
  - Commands may arrive after audio generation starts
  - Result: Modules run with default (silent) parameters

### Evidence
```
[WORKER 1] Audio generated! RMS=0.1403  # Brief audio
[WORKER 1] Silent buffer (RMS=0.000000)  # Then silence
[STATS] None reads: 44.40%              # High despite occ=2
```

## Solution Design

### Core Concept
Replace unreliable OSC priming with **direct priming via patch_queue** to standby worker, with warmup and readiness confirmation before swap.

### New Flow
1. **Commit**: Build DAG in standby worker
2. **Prime**: Send parameters directly via patch_queue  
3. **Apply**: Worker sets params with `immediate=True`
4. **Warmup**: Generate 6-8 buffers to stabilize
5. **Verify**: Check for non-silent output
6. **Signal**: Set readiness flag
7. **Swap**: Only when confirmed ready

## Implementation Steps

### Step 1: Add Prime Operation to Patch Queue

**Location**: `supervisor_v3_router.py`

#### 1.1 Extend patch_queue Protocol (Lines ~145-200)
```python
elif cmd_type == 'prime':
    # Prime operations: list of (op_type, module_id, param, value)
    prime_ops = patch_cmd.get('ops', [])
    warmup_count = patch_cmd.get('warmup', 8)
    
    # Apply all prime operations immediately
    for op_type, module_id, param, value in prime_ops:
        if module_id in patch_modules:
            module = patch_modules[module_id]
            
            if op_type == 'mod':
                # Set parameter immediately
                module.set_param(param, value, immediate=True)
                print(f"[WORKER] Primed {module_id}.{param} = {value}")
                
            elif op_type == 'gate':
                # Set gate state (if module supports it)
                if hasattr(module, 'set_gate'):
                    module.set_gate(value)
                else:
                    # Use set_param for gate as fallback
                    module.set_param('gate', 1.0 if value else 0.0, immediate=True)
                print(f"[WORKER] Primed {module_id} gate = {value}")
    
    # Warmup: Process several buffers to stabilize
    print(f"[WORKER] Warming up with {warmup_count} buffers...")
    warmup_rms = []
    for i in range(warmup_count):
        output = module_host.process_chain()
        rms = np.sqrt(np.mean(output ** 2))
        warmup_rms.append(rms)
        if i < 10:  # Log first 10 for debugging
            print(f"[WORKER] Warmup {i}: RMS={rms:.6f}")
    
    # Check if we produced non-silent audio
    max_rms = max(warmup_rms)
    if max_rms > 0.001:
        print(f"[WORKER] Warmup complete - max RMS={max_rms:.4f}")
        patch_ready = True
    else:
        print(f"[WORKER] WARNING: Warmup produced silence!")
        patch_ready = False
```

#### 1.2 Add Readiness Signaling (Lines ~70)
```python
# Add after other shared memory setup
if use_router:
    # Readiness flag for priming confirmation
    prime_ready = mp.Value('i', 0)  # 0=not ready, 1=primed and warm
```

### Step 2: Modify Supervisor Commit Handler

**Location**: `supervisor_v3_router.py`, `handle_patch_commit()` (~line 425)

#### 2.1 Replace OSC Priming with Direct Prime
```python
def handle_patch_commit(self, unused_addr):
    """Handle /patch/commit command (CP3)"""
    if not self.router_enabled:
        return
    
    # Store copy of pending patch before clearing
    modules_to_prime = dict(self.pending_patch)
    
    print(f"[OSC] /patch/commit - Building patch with {len(modules_to_prime)} modules")
    
    # Send commit to standby worker
    if self.patch_queue:
        self.patch_queue.put({'type': 'commit'})
        
        # Wait briefly for DAG build
        time.sleep(0.05)
        
        # Build prime operations based on module types
        prime_ops = []
        for module_id, module_info in modules_to_prime.items():
            module_type = module_info.get('type', '')
            
            # Oscillators
            if 'sine' in module_type or 'osc' in module_id:
                prime_ops.extend([
                    ('mod', module_id, 'freq', 440.0),
                    ('mod', module_id, 'gain', 0.2)
                ])
            
            # Envelopes
            elif 'adsr' in module_type or 'env' in module_id:
                prime_ops.extend([
                    ('mod', module_id, 'attack', 10.0),
                    ('mod', module_id, 'decay', 50.0),
                    ('mod', module_id, 'sustain', 0.7),
                    ('mod', module_id, 'release', 200.0),
                    ('gate', module_id, 1)  # Gate on
                ])
            
            # Filters
            elif 'filter' in module_type or 'filt' in module_id:
                prime_ops.extend([
                    ('mod', module_id, 'cutoff', 2000.0),
                    ('mod', module_id, 'q', 1.0)
                ])
        
        # Send prime command to standby worker
        print(f"[OSC] Sending prime operations to standby worker...")
        self.patch_queue.put({
            'type': 'prime',
            'ops': prime_ops,
            'warmup': 8
        })
        
        # Wait for priming to complete
        time.sleep(0.1)
        
        # Mark ready for switch (but check prime_ready in callback)
        self.standby_ready = True
        self.pending_switch = True
```

### Step 3: Add Swap Readiness Barrier

**Location**: `supervisor_v3_router.py`, `audio_callback()` (~line 600)

#### 3.1 Check Prime Readiness Before Swap
```python
# Handle pending switch at buffer boundary
if self.pending_switch and self.standby_ready:
    # Check if standby has primed and warmed up
    standby_idx = 1 - self.active_idx.value
    if hasattr(self, f'worker_{standby_idx}_prime_ready'):
        prime_ready = getattr(self, f'worker_{standby_idx}_prime_ready')
        if not prime_ready.value:
            # Not ready yet, wait
            return
    
    # Check if standby has produced at least one buffer
    standby_ring = self.slot1_audio_ring if self.active_idx.value == 0 else self.slot0_audio_ring
    standby_has_audio = (standby_ring.head.value != standby_ring.tail.value)
    
    if standby_has_audio:
        # Proceed with swap...
```

### Step 4: Enhanced Instrumentation

#### 4.1 Worker: First 10 Buffers After Prime
```python
# In worker, after prime operation
first_buffers_after_prime = 0
prime_complete_time = time.perf_counter()

# In main loop, after audio generation
if first_buffers_after_prime < 10 and patch_ready:
    first_buffers_after_prime += 1
    rms = np.sqrt(np.mean(output_buffer ** 2))
    
    # Log module state for debugging
    state_info = []
    for module_id, module in module_host.modules.items():
        if 'osc' in module_id:
            state_info.append(f"{module_id}(f={module.params.get('freq')},g={module.params.get('gain')})")
        elif 'env' in module_id and hasattr(module, 'stage'):
            state_info.append(f"{module_id}(stage={module.stage})")
        elif 'filt' in module_id:
            state_info.append(f"{module_id}(c={module.params.get('cutoff')})")
    
    print(f"[WORKER {slot_id}] Post-prime {first_buffers_after_prime}: RMS={rms:.4f}, {', '.join(state_info)}")
```

#### 4.2 Supervisor: Active Ring Occupancy
```python
# In audio_callback, every 1000 reads
if self.total_reads % 1000 == 0:
    active_ring = self.slot0_audio_ring if self.active_idx.value == 0 else self.slot1_audio_ring
    active_occ = ring_occupancy(active_ring)  # Need to add this helper
    none_read_pct = (self.none_reads / self.total_reads) * 100
    print(f"[STATS] Active occ={active_occ}, None reads: {none_read_pct:.2f}%, Buffers out: {self.total_reads}")
```

## Testing Strategy

### Test 1: Oscillator Only
```python
# Commands
/patch/create osc1 simple_sine
/patch/commit
# Prime via patch_queue: freq=440, gain=0.2
# Expect: Clean 440Hz tone, RMS ~0.14
```

### Test 2: With Envelope
```python
# Commands
/patch/create osc1 simple_sine
/patch/create env1 adsr
/patch/connect osc1 env1
/patch/commit
# Prime: osc params + ADSR + gate on
# Expect: Attack-decay-sustain curve, no silence
```

### Test 3: Full Chain
```python
# Commands
/patch/create osc1 simple_sine
/patch/create env1 adsr
/patch/create filt1 biquad_filter
/patch/connect osc1 env1
/patch/connect env1 filt1
/patch/commit
# Prime: All params + gate
# Expect: Filtered sustained tone
```

## Success Metrics

### Must Have
- **Zero none-reads** during sustained playback
- **Non-silent warmup** confirmed before swap
- **Stable RMS** after prime (no dropouts)
- **Module state persistence** across swaps

### Nice to Have
- **<10ms prime latency** (from commit to ready)
- **First-buffer audio** (no silence at start)
- **Parameter continuity** during multi-commit

## Risk Mitigation

### If Silent Buffers Persist
1. **Check `prepare()` calls** - Ensure not resetting state
2. **Verify gate persistence** - ADSR shouldn't reset
3. **Sample rate alignment** - Use env overrides
4. **Increase ring depth** - Try NUM_BUFFERS=16
5. **Add module state dumps** - Log all params

### Rollback Plan
Keep current OSC priming code commented but available. Can revert by changing prime type back to OSC commands.

## File Changes Summary

### supervisor_v3_router.py
1. **Worker process** (~lines 140-200): Add 'prime' operation handler
2. **Supervisor init** (~line 330): Add prime_ready flags
3. **handle_patch_commit** (~line 425): Replace OSC with direct prime
4. **audio_callback** (~line 600): Add prime readiness check
5. **Instrumentation**: Add first-10 logging and active occupancy

### No Module Changes Required
- BaseModule already has `set_param(immediate=True)`
- ADSR has gate handling
- No DSP logic changes needed

## Timeline

### Phase 1: Core Implementation (1 hour)
- Add prime operation to worker
- Replace OSC priming in supervisor
- Basic warmup logic

### Phase 2: Readiness Barrier (30 min)
- Add prime_ready signaling
- Gate swap on confirmation
- Test basic flow

### Phase 3: Instrumentation (30 min)
- First-10 buffer logging
- Active ring occupancy
- Module state tracking

### Phase 4: Testing & Tuning (1 hour)
- Test all three scenarios
- Tune warmup count
- Verify metrics

---
*Implementation plan prepared by Chronus Nexus*  
*Based on Senior Dev's analysis and current codebase research*  
*Estimated time: 3 hours for complete implementation*