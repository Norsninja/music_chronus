# CP3 Prime Mechanism - Research Findings & Implementation Plan

**Date**: 2025-09-02  
**Author**: Chronus Nexus  
**Purpose**: Document research findings and corrected implementation plan for review  
**Status**: Ready for Senior Dev review

## Executive Summary

Research reveals the prime_ready infrastructure exists but isn't connected. The core issue is a race condition where the supervisor marks standby as ready BEFORE parameters arrive via OSC. The solution requires passing prime_ready shared values to workers and implementing direct priming via patch_queue.

## Research Findings

### 1. Current Implementation Analysis

#### 1.1 Prime Infrastructure Status
- **Line 341**: `self.prime_ready = [mp.Value('i', 0), mp.Value('i', 0)]` exists but unused
- **Issue**: Created in supervisor but never passed to workers
- **Impact**: Workers cannot signal prime completion to supervisor

#### 1.2 Race Condition in Current Flow
```python
# Line 477: Marks ready BEFORE sending parameters!
self.standby_ready = True  
self.pending_switch = True

# Lines 479-521: Parameters sent AFTER marking ready
for module_id, module_info in modules_to_prime.items():
    # OSC commands sent here - may arrive too late
```

#### 1.3 Worker Spawn Pattern
- **Current**: 8 parameters passed (lines 397-399)
- **Pattern**: mp.Value objects passed directly, not .value
- **Missing**: prime_ready[slot_idx] needs to be 9th parameter

### 2. Critical Code Patterns Discovered

#### 2.1 Parameter Passing to Workers
```python
# Current pattern (line 397-399)
args=(slot_idx, audio_ring, command_ring,
      self.heartbeat_array, self.worker_events[slot_idx],
      self.worker_shutdown_flags[slot_idx], use_router, patch_queue)

# Needed: Add prime_ready[slot_idx] as 9th parameter
```

#### 2.2 Patch Queue Message Structure
```python
# Existing messages
{'type': 'create', 'module_id': str, 'module_type': str}
{'type': 'connect', 'source_id': str, 'dest_id': str}
{'type': 'commit'}
{'type': 'abort'}

# Need to add
{'type': 'prime', 'ops': list, 'warmup': int}
```

#### 2.3 Module Parameter Interface
- **Confirmed**: `set_param(name, value, immediate=True)` supported
- **Gate handling**: ADSR has `set_gate(bool)` method
- **Parameter names**: Must use exact names ('freq' not 'frequency')

#### 2.4 Ring Occupancy Pattern
```python
# Helper exists (lines 124-128)
def ring_occupancy(ring):
    head = ring.head.value
    tail = ring.tail.value
    nb = ring.num_buffers
    return (head - tail + nb) % nb

# Check for buffers
standby_has_audio = (standby_ring.head.value != standby_ring.tail.value)
```

### 3. Senior Dev's Critical Corrections

#### 3.1 Prime Readiness Sharing ✅
**Wrong**: Create mp.Value inside worker  
**Right**: Pass supervisor's prime_ready[slot_idx] to worker

**Implementation**:
```python
# In supervisor.__init__ (already exists at line 341)
self.prime_ready = [mp.Value('i', 0), mp.Value('i', 0)]

# In spawn_worker (add to args)
args=(slot_idx, audio_ring, command_ring,
      self.heartbeat_array, self.worker_events[slot_idx],
      self.worker_shutdown_flags[slot_idx], use_router, patch_queue,
      self.prime_ready[slot_idx])  # NEW: 9th parameter

# In worker_process signature
def worker_process(slot_idx, audio_ring, command_ring, heartbeat_array,
                  worker_event, shutdown_flag, use_router, patch_queue,
                  prime_ready):  # NEW parameter
```

#### 3.2 Audio Callback Swap Gate ✅
**Wrong**: Early return from audio_callback  
**Right**: Always output audio, only skip switch

**Implementation**:
```python
# In audio_callback (around line 630)
if self.pending_switch and self.standby_ready:
    standby_idx = 1 - self.active_idx.value
    
    # Check prime readiness (NEW)
    if self.prime_ready[standby_idx].value != 1:
        # Not primed yet - continue outputting but don't switch
        pass  # Fall through to normal audio output
    else:
        # Check standby has audio
        standby_ring = self.slot1_audio_ring if self.active_idx.value == 0 else self.slot0_audio_ring
        if standby_ring.head.value != standby_ring.tail.value:
            # Perform switch...
```

#### 3.3 Prime Ops Tuple Format ✅
**Wrong**: Mixed 3-tuple and 4-tuple formats  
**Right**: Standardize to 4-tuples

**Format**: `(op_type, module_id, param, value)`
- Parameter ops: `('mod', 'osc1', 'freq', 440.0)`
- Gate ops: `('gate', 'env1', None, 1)`  # param is None

### 4. Implementation Gotchas Found

1. **Patch queue conditional**: Only passed to standby slots (use_router=True)
2. **Module existence**: Must check module exists before calling methods
3. **Parameter aliases**: Some modules use different param names
4. **Queue timing**: Prime commands processed in next cycle, not immediately
5. **Worker respawn**: Clears all local state including patch_modules
6. **Ring checks**: Must verify occupancy to avoid infinite wait

## Corrected Implementation Plan

### Phase 1: Infrastructure Connection (30 min)

#### Step 1.1: Pass prime_ready to Worker
```python
# In spawn_worker() - line ~397
args=(slot_idx, audio_ring, command_ring,
      self.heartbeat_array, self.worker_events[slot_idx],
      self.worker_shutdown_flags[slot_idx], use_router, patch_queue,
      self.prime_ready[slot_idx])  # ADD THIS

# In worker_process() - line ~57
def worker_process(slot_idx, audio_ring, command_ring, heartbeat_array,
                  worker_event, shutdown_flag, use_router, patch_queue,
                  prime_ready):  # ADD THIS
```

#### Step 1.2: Reset prime_ready on Spawn/Abort
```python
# In spawn_worker() - after line ~374
self.prime_ready[slot_idx].value = 0  # Reset on spawn

# In worker patch abort handler - line ~194
if prime_ready:
    prime_ready.value = 0  # Reset on abort
```

### Phase 2: Prime Operation Handler (45 min)

#### Step 2.1: Add Prime Handler to Worker
```python
# In worker_process, patch queue handling - after line ~140
elif cmd_type == 'prime':
    prime_ops = patch_cmd.get('ops', [])
    warmup_count = patch_cmd.get('warmup', 8)
    
    print(f"[WORKER {slot_idx}] Applying {len(prime_ops)} prime operations")
    
    # Apply all operations with immediate=True
    for op_type, module_id, param, value in prime_ops:
        if module_id not in patch_modules:
            print(f"[WORKER {slot_idx}] Warning: module {module_id} not found")
            continue
            
        module = patch_modules[module_id]
        
        if op_type == 'mod':
            module.set_param(param, value, immediate=True)
            print(f"[WORKER {slot_idx}] Set {module_id}.{param} = {value}")
            
        elif op_type == 'gate':
            # param is None for gate ops
            if hasattr(module, 'set_gate'):
                module.set_gate(bool(value))
            else:
                module.set_param('gate', float(value), immediate=True)
            print(f"[WORKER {slot_idx}] Set {module_id} gate = {value}")
    
    # Warmup: Generate buffers to stabilize
    print(f"[WORKER {slot_idx}] Warming up with {warmup_count} buffers...")
    warmup_results = []
    
    for i in range(warmup_count):
        output = module_host.process_chain()
        rms = np.sqrt(np.mean(output ** 2))
        warmup_results.append(rms)
        
        if i < 3:  # Log first few
            print(f"[WORKER {slot_idx}] Warmup {i}: RMS={rms:.6f}")
    
    # Check for non-silent output
    max_rms = max(warmup_results)
    if max_rms > 0.001:
        print(f"[WORKER {slot_idx}] Prime complete! Max RMS={max_rms:.4f}")
        if prime_ready:
            prime_ready.value = 1  # Signal supervisor
        patch_ready = True
    else:
        print(f"[WORKER {slot_idx}] WARNING: Warmup silent, max RMS={max_rms:.6f}")
        # Don't set prime_ready if silent
```

### Phase 3: Supervisor Prime Dispatch (45 min)

#### Step 3.1: Replace OSC Priming
```python
# In handle_patch_commit() - replace lines ~479-521
def handle_patch_commit(self, unused_addr):
    if not self.router_enabled:
        return
    
    # Save pending patch for priming
    modules_to_prime = dict(self.pending_patch)
    
    print(f"[OSC] /patch/commit - Building patch with {len(modules_to_prime)} modules")
    
    # Send commit to standby worker
    if self.patch_queue:
        self.patch_queue.put({'type': 'commit'})
        time.sleep(0.02)  # Brief wait for DAG build
        
        # Build prime operations (4-tuple format)
        prime_ops = []
        
        for module_id, module_info in modules_to_prime.items():
            module_type = module_info.get('type', '')
            
            # Oscillators
            if 'sine' in module_type or 'osc' in module_id:
                prime_ops.append(('mod', module_id, 'freq', 440.0))
                prime_ops.append(('mod', module_id, 'gain', 0.2))
            
            # Envelopes  
            elif 'adsr' in module_type or 'env' in module_id:
                prime_ops.append(('mod', module_id, 'attack', 10.0))
                prime_ops.append(('mod', module_id, 'decay', 50.0))
                prime_ops.append(('mod', module_id, 'sustain', 0.7))
                prime_ops.append(('mod', module_id, 'release', 200.0))
                prime_ops.append(('gate', module_id, None, 1))  # Gate on
            
            # Filters
            elif 'filter' in module_type or 'filt' in module_id:
                prime_ops.append(('mod', module_id, 'cutoff', 2000.0))
                prime_ops.append(('mod', module_id, 'q', 1.0))
        
        # Send prime command to standby
        print(f"[OSC] Sending {len(prime_ops)} prime ops to standby worker")
        self.patch_queue.put({
            'type': 'prime',
            'ops': prime_ops,
            'warmup': 8
        })
        
        # Wait for prime completion with timeout
        standby_idx = 1 - self.active_idx.value
        start_time = time.perf_counter()
        timeout = 0.5  # 500ms timeout
        
        while time.perf_counter() - start_time < timeout:
            if self.prime_ready[standby_idx].value == 1:
                print(f"[OSC] Standby primed in {(time.perf_counter() - start_time)*1000:.1f}ms")
                self.standby_ready = True
                self.pending_switch = True
                break
            time.sleep(0.01)  # Check every 10ms
        else:
            print(f"[OSC] WARNING: Prime timeout after {timeout}s")
            # Could still mark ready and hope for the best
            self.standby_ready = True
            self.pending_switch = True
```

### Phase 4: Audio Callback Gate (30 min)

#### Step 4.1: Add Prime Check to Swap Logic
```python
# In audio_callback() - around line 630
if self.pending_switch and self.standby_ready:
    standby_idx = 1 - self.active_idx.value
    
    # Check prime readiness (NEW)
    prime_ready = self.prime_ready[standby_idx].value == 1
    
    # Check standby has audio
    standby_ring = self.slot1_audio_ring if self.active_idx.value == 0 else self.slot0_audio_ring
    standby_has_audio = (standby_ring.head.value != standby_ring.tail.value)
    
    if prime_ready and standby_has_audio:
        # Safe to switch - both conditions met
        print(f"[AUDIO] Switching to slot {standby_idx} (primed & ready)")
        
        # Perform the switch...
        old_idx = self.active_idx.value
        self.active_idx.value = standby_idx
        
        # Reset flags
        self.pending_switch = False
        self.standby_ready = False
        
        # Respawn old worker as new standby
        self.spawn_worker(old_idx, is_standby=True)
    else:
        # Not ready yet - keep outputting from active
        if not prime_ready:
            pass  # Waiting for prime completion
        elif not standby_has_audio:
            pass  # Waiting for first buffer
```

## Testing Strategy

### Test 1: Single Oscillator
```bash
/patch/create osc1 simple_sine
/patch/commit
# Expect: Immediate 440Hz tone, no silence
```

### Test 2: Oscillator + ADSR
```bash
/patch/create osc1 simple_sine  
/patch/create env1 adsr
/patch/connect osc1 env1
/patch/commit
# Expect: Attack-decay-sustain envelope, no silence
```

### Test 3: Full Chain
```bash
/patch/create osc1 simple_sine
/patch/create env1 adsr
/patch/create filt1 biquad_filter
/patch/connect osc1 env1
/patch/connect env1 filt1
/patch/commit
# Expect: Filtered envelope tone, no silence
```

### Test 4: Multi-Commit Cycles
```bash
# Commit 1: Just oscillator
/patch/create osc1 simple_sine
/patch/commit

# Commit 2: Add envelope
/patch/create env1 adsr
/patch/connect osc1 env1
/patch/commit

# Commit 3: Add filter
/patch/create filt1 biquad_filter
/patch/connect env1 filt1
/patch/commit

# Expect: Each transition smooth, no silence
```

## Success Metrics

### Must Have
- ✅ Zero none-reads during sustained playback (<1%)
- ✅ Non-silent warmup confirmed before swap
- ✅ Stable RMS after prime (no dropouts)
- ✅ Module state persistence across swaps

### Performance Targets
- Prime completion: <50ms typical
- First audio: Within 1 buffer after swap
- CPU overhead: <1% for priming
- Memory: Zero allocations

## Risk Analysis

### Risk 1: Silent Warmup
**Mitigation**: Log module state, verify parameters applied

### Risk 2: Prime Timeout
**Mitigation**: 500ms timeout, proceed anyway with warning

### Risk 3: Race on prime_ready
**Mitigation**: Use atomic mp.Value, no locks needed

### Risk 4: Module not found
**Mitigation**: Check existence before operations

## Implementation Order

1. **Pass prime_ready to workers** (foundational)
2. **Add prime handler to worker** (core logic)
3. **Update supervisor commit** (dispatch)
4. **Add swap gate check** (safety)
5. **Reset on spawn/abort** (cleanup)
6. **Test and iterate** (validation)

## Files to Modify

1. **supervisor_v3_router.py**:
   - Line ~397: Add prime_ready to spawn args
   - Line ~57: Add to worker_process signature  
   - Line ~140-200: Add prime handler
   - Line ~479-521: Replace OSC priming
   - Line ~630: Add swap gate check
   - Line ~374: Reset on spawn
   - Line ~194: Reset on abort

2. **No other files need changes** - modules already support immediate=True

## Estimated Timeline

- Phase 1 (Infrastructure): 30 minutes
- Phase 2 (Prime Handler): 45 minutes  
- Phase 3 (Supervisor): 45 minutes
- Phase 4 (Swap Gate): 30 minutes
- Testing: 30 minutes
- **Total: ~3 hours**

---
*Research completed and plan prepared by Chronus Nexus*  
*Ready for Senior Dev review*  
*All Senior Dev corrections incorporated*