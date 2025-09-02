# CP2 Integration Research Report

## Executive Summary

Research findings for integrating PatchRouter into ModuleHost behind CHRONUS_ROUTER flag for CP2.

## Key Findings

### 1. ModuleHost Architecture (`module_host.py`)

**Current Implementation:**
- Uses OrderedDict for linear module chain
- Pre-allocates `MAX_MODULES = 8` intermediate buffers
- Command queue with deque for O(1) operations
- Commands processed at buffer boundaries via `process_commands()`
- Chain processing via `process_chain()` method

**Key Methods:**
- `add_module(module_id, module)` - Adds to OrderedDict
- `queue_command(cmd_bytes)` - Queues 64-byte commands
- `process_commands()` - Applies at buffer boundary
- `process_chain(input_buffer)` - Sequential module processing

**Integration Points:**
- Replace OrderedDict with PatchRouter when flag set
- Modify `process_chain()` to use router's topological order
- Keep command queue and boundary processing unchanged

### 2. Supervisor Slot Architecture (`supervisor_v2_slots_fixed.py`)

**Slot System:**
- Two slots: slot0 and slot1 (one active, one standby)
- Active slot index tracked in `self.active_idx`
- Standby readiness tracked via `self.standby_ready`
- Worker processes in each slot with their own ModuleHost

**Failover Mechanism:**
- Monitor thread checks heartbeats
- On failure: switches `active_idx` to standby slot
- Failed worker respawns in same slot
- No ring buffer swapping - slots are fixed

**Key Insight:** 
Router modifications should happen in standby slot's ModuleHost, not active!

### 3. OSC Server Implementation

**Current Setup:**
- ThreadingOSCUDPServer on port 5005 (default)
- Dispatcher routes patterns to handlers
- Commands packed into 64-byte structs via `pack_command_v2()`

**Current Handlers:**
- `/mod/<module_id>/<param>` - Parameter changes
- `/gate/<module_id>` - Gate control

**Integration for /patch/* commands:**
- Add new dispatcher patterns for `/patch/create`, `/patch/connect`, etc.
- Route to standby slot's ModuleHost
- Validate and warm buffers before marking ready

### 4. Command Flow

**Current:**
1. OSC → pack_command_v2() → 64-byte struct
2. Pushed to command ring
3. Worker pulls from ring
4. ModuleHost.queue_command()
5. ModuleHost.process_commands() at boundary
6. Module.set_param() applied

**With Router:**
1. `/patch/*` commands bypass command ring
2. Direct manipulation of standby ModuleHost's router
3. Build graph, validate, warm buffers
4. Set standby_ready flag
5. `/patch/commit` triggers slot swap

## Integration Strategy for CP2

### Phase 1: ModuleHost Modifications

```python
class ModuleHost:
    def __init__(self, sample_rate, buffer_size, use_router=False):
        # ... existing init ...
        self.use_router = use_router
        if use_router:
            from .patch_router import PatchRouter
            self.router = PatchRouter(buffer_size)
        else:
            self.modules = OrderedDict()
```

### Phase 2: Process Chain Modification

```python
def process_chain(self, input_buffer=None):
    if self.use_router:
        # Get topological order from router
        processing_order = self.router.get_processing_order()
        # Process using router's DAG
        # ... implementation ...
    else:
        # Existing linear chain processing
        # ... current implementation ...
```

### Phase 3: OSC Handlers for /patch/*

```python
def handle_patch_create(unused_addr, module_id, module_type):
    # Only operate on standby slot
    standby_idx = 1 if supervisor.active_idx == 0 else 0
    worker = supervisor.workers[standby_idx]
    # Create module via registry
    # Add to router
    
def handle_patch_connect(unused_addr, source_id, dest_id):
    # Connect in standby router
    # Validate no cycles
```

### Phase 4: Commit Flow

```python
def handle_patch_commit(unused_addr):
    # Validate standby graph
    # Warm buffers (2-3 cycles)
    # Set standby_ready = True
    # Trigger slot swap at next buffer boundary
```

## Critical Requirements

### Zero Allocation
- Router must use pre-allocated edge buffers
- No new allocations during process_chain()
- Maintain boundary-only parameter updates

### Safety
- Router ONLY in standby slot until commit
- Active audio never touches router path
- CHRONUS_ROUTER env flag for opt-in

### Validation
- DAG cycle detection before commit
- Buffer warming before marking ready
- Failover mechanism unchanged

## Test Strategy

### Non-Audio Tests (CP2)
1. ModuleHost with router processes buffers correctly
2. Graph building and validation works
3. Command routing to standby slot only
4. State transitions correct

### Audio Tests (CP3)
1. Start with CHRONUS_ROUTER=1
2. Build patch via OSC
3. Commit and verify continuity
4. Multiple commits over 10 minutes
5. Monitor none_reads < 0.1%

## Risk Mitigation

- **Risk**: Router adds latency
  - **Mitigation**: Pre-computed topological order, cached
  
- **Risk**: Graph has cycles
  - **Mitigation**: Validation before commit, reject invalid
  
- **Risk**: Commit during failover
  - **Mitigation**: Lock mechanism or queue commits

## Implementation Order

1. **First**: Add use_router flag to ModuleHost
2. **Second**: Implement router-based process_chain()
3. **Third**: Add /patch/* OSC handlers (standby only)
4. **Fourth**: Implement commit flow with validation
5. **Fifth**: Add non-audio integration tests
6. **Sixth**: Test with CHRONUS_ROUTER=1

## Open Questions

1. Should we create ModuleHostV2 or modify existing?
2. How to handle module creation - via registry in supervisor?
3. Buffer warming - how many cycles needed?
4. Should commit be synchronous or async?

## Conclusion

The integration is feasible with minimal changes. The key insight is that router operates ONLY in standby slot until commit. This maintains RT guarantees while allowing live patching. The existing slot architecture provides perfect isolation for safe experimentation.

---

*Research completed for CP2 integration planning*