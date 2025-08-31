# Architecture Decision: Worker Pool Pattern

## Date: 2025-08-30
## Status: Decided

## Context

Initial architecture assumed on-demand process spawning when users create modules:
```
user: create vco --id 1
system: spawn new process for VCO
```

PROC-01 testing revealed this is not viable.

## Problem

Process spawn times with required libraries:
- Cold spawn with numpy + scipy + OSC: 672ms
- Spawn method alone: 140ms  
- Forkserver: 97ms
- Fork: 3ms (but unsafe with threads)

672ms is unacceptable for live music performance. Even 97ms breaks flow.

## Decision

Use pre-warmed worker pool pattern instead of on-demand spawning.

## Implementation

### Startup Phase
```python
# At application start
worker_pool = multiprocessing.Pool(
    processes=8,  # 2x CPU cores for headroom
    initializer=preload_all_libraries,
    maxtasksperchild=None  # Workers live forever
)
# Cost: 2-3 seconds one-time
```

### Module Creation
```python
# When user creates module
def create_module(module_type, module_id):
    # Instead of: spawn_new_process()
    # We do:
    worker_pool.apply_async(
        run_module, 
        args=(module_type, module_id)
    )
    # Cost: <10ms
```

### Worker Initialization
```python
def preload_all_libraries():
    # Pre-import everything workers need
    import numpy as np
    import scipy.signal
    import scipy.fft
    from pythonosc import udp_client, osc_server
    import rtmixer
    
    # Store as globals for fast access
    globals().update(locals())
```

## Architecture Changes

### Before (Original Design)
```
Session Manager
    ├── spawn VCO process
    ├── spawn VCF process  
    └── spawn LFO process
    (each spawn = 600-700ms)
```

### After (Worker Pool)
```
Session Manager
    ├── Worker Pool (8 processes, pre-warmed)
         ├── Worker 1: running VCO
         ├── Worker 2: running VCF
         ├── Worker 3: running LFO
         └── Workers 4-8: idle, ready
    (assignment = <10ms)
```

## Trade-offs

### Pros
- Module assignment: <10ms (meets real-time requirement)
- No repeated library import cost
- More stable (workers already running)
- Can handle CPU cores * 2 concurrent modules
- Predictable resource usage

### Cons  
- Application startup: 2-3 seconds (one-time)
- Fixed maximum modules (pool size)
- Memory overhead of idle workers (~50MB each)
- More complex module lifecycle management

## Alternatives Considered

1. **Threading instead of processes**
   - Rejected: GIL limits parallel DSP
   - Exception: Could use for GIL-releasing operations

2. **Lazy loading libraries**
   - Rejected: Still 200-400ms for numpy alone
   
3. **Fork with careful thread management**
   - Rejected: Too risky with OSC threads and audio callbacks

## Consequences

1. Module creation becomes task assignment, not process spawning
2. Need to implement module-to-worker allocation logic
3. Must handle worker failure and restart
4. Session manager becomes more complex
5. But achieves <20ms total system latency

## Validation

PROC-01 test results prove this is necessary:
- Fork: 3ms (unsafe)
- Forkserver: 97ms (too slow)  
- Spawn: 140ms (too slow)
- Cold with imports: 672ms (impossible)
- Pool assignment: <10ms (viable)

## Additional Notes

Start method should be 'forkserver' on Linux for safety and performance balance.

Pool size = 2 * CPU cores gives headroom for parallel processing without oversubscription.

Workers should never die (maxtasksperchild=None) to avoid respawn cost.

Consider hybrid approach: core modules in processes, lightweight control in threads.