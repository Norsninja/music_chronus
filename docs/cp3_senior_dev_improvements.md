# CP3 Senior Dev Improvements Implementation Plan

**Date**: 2025-09-03  
**Author**: Chronus Nexus  
**Status**: Planning improvements based on Senior Dev review

## Review Summary
The prime fix is working correctly! Senior Dev confirmed:
- ✅ Root cause correctly identified and fixed
- ✅ Implementation matches specifications
- ✅ No popping confirms fix resolved the issue
- ✅ RT safety and hot paths preserved

## Suggested Improvements

### 1. Standby Index Consistency (Priority: HIGH)
**Issue**: Potential race if failover occurs mid-handler
**Fix**: Capture `standby_idx` once at handler start

```python
def handle_patch_commit(self, unused_addr):
    # Capture once to avoid race
    standby_idx = 1 - self.active_idx.value
    
    # Use throughout handler
    self.patch_queues[standby_idx].put({'type': 'commit'})
    # ... prime operations ...
    self.patch_queues[standby_idx].put({'type': 'prime', ...})
    # ... wait on same standby_idx ...
```

### 2. Drain Patch Queue Loop (Priority: MEDIUM)
**Issue**: Single get_nowait() may leave commands pending
**Fix**: Loop to drain all pending commands

```python
# Current:
if not patch_queue.empty():
    patch_cmd = patch_queue.get_nowait()

# Improved:
while not patch_queue.empty():
    try:
        patch_cmd = patch_queue.get_nowait()
        # Process command
    except queue.Empty:
        break
```

### 3. OSC Parameter Routing Optimization (Priority: LOW)
**Issue**: Sending params to both slots unnecessarily
**Fix**: Route to active only in steady state

```python
def handle_mod_param(self, addr, *args):
    if self.pending_switch:
        # Broadcast during transition
        self.slot0_command_ring.write(cmd)
        self.slot1_command_ring.write(cmd)
    else:
        # Active only in steady state
        active_ring = self.slot0_command_ring if self.active_idx.value == 0 else self.slot1_command_ring
        active_ring.write(cmd)
```

### 4. Verbose Logging Control (Priority: LOW)
**Issue**: Too much output during long sessions
**Fix**: Gate logs under CHRONUS_VERBOSE

```python
if os.environ.get('CHRONUS_VERBOSE', '0') == '1':
    print(f"[OSC] Routing patch create to standby slot {standby_idx}")
    print(f"[WORKER {slot_id}] prime_ready set")
```

### 5. Configurable Prime Timeout (Priority: LOW)
**Issue**: WSL2 jitter may need longer timeout
**Fix**: Environment variable override

```python
timeout = int(os.environ.get('CHRONUS_PRIME_TIMEOUT_MS', '500')) / 1000.0
```

## Verification Requirements

### Multi-Commit Test
```bash
python test_multi_commit.py
```
Expected: Alternating slots, clean tones, no timeouts

### Soak Test
```bash
python test_soak.py 30
```
Expected: 
- none-reads ≤ 0.5%
- Stable occupancy (1-2)
- No artifacts over 30 minutes

## Documentation Updates Needed

1. Add "Race avoidance" note about capturing standby_idx once
2. Reference minimum baseline: 512/16 on WSL2
3. Link to original bug report table showing 384 samples = 49% none-reads

## Implementation Priority

1. **IMMEDIATE**: Standby index consistency (prevents rare race)
2. **NEXT SESSION**: Patch queue draining (reduces latency)
3. **OPTIONAL**: Verbose logging, parameter routing, timeout config

## Track A Baseline Reminder

**Minimum Viable Configuration (WSL2)**:
- BUFFER_SIZE: 512 samples (11.6ms)
- NUM_BUFFERS: 16-32
- Expected: <0.5% none-reads

Lower latencies (384/256) require Track B improvements (triple-buffer, JIT compilation).

---
*Ready for incremental improvements while maintaining stability*