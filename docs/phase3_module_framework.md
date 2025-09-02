# Phase 3: Module Framework & Dynamic Routing

**Start Date**: 2025-09-02  
**Status**: In Progress  
**Goal**: Transform the modular synthesizer into a dynamically patchable system with safe module updates

## Executive Summary

Phase 3 adds dynamic module routing, parameter metadata, and safe patch updates to our synthesizer. Instead of dangerous hot-reload, we leverage our existing slot-based architecture for live patch changes with <50ms interruption.

## Architecture Overview

```
User Patches → OSC Commands → Standby Slot Rebuild → Validate → Commit → Slot Swap
                                        ↓
                              [PatchRouter DAG]
                                        ↓
                          [ModuleRegistry + Lazy Load]
                                        ↓
                              [Enhanced BaseModule]
```

## Key Components

### 1. Parameter Metadata System

**ParamSpec Class**
```python
class ParamSpec:
    name: str                    # Parameter identifier
    param_type: type            # float, int, bool
    range: Tuple[float, float]  # (min, max)
    default: float              # Initial value
    units: str                  # "Hz", "dB", "ms"
    smoothing_mode: str         # "linear", "exponential", "none"
    smoothing_coeff: float      # 0.99 for one-pole filter
```

**Enhanced BaseModule**
```python
class BaseModule:
    def get_param_specs(self) -> Dict[str, ParamSpec]
    def prepare(self) -> None           # One-time setup
    def set_param(self, name: str, value: float, immediate: bool = False)
    def set_gate(self, value: bool)
    def process_buffer(self, input: np.ndarray, output: np.ndarray)
```

### 2. Module Registry

**Features:**
- Decorator-based registration: `@register_module("sine")`
- Lazy imports only when building patches
- RT-safety validation before registration
- Module versioning support

**Implementation:**
```python
class ModuleRegistry:
    def register(self, module_id: str, module_class: Type[BaseModule])
    def discover_modules(self, path: str = "modules/")
    def create_instance(self, module_id: str, module_type: str) -> BaseModule
    def validate_rt_safety(self, module_class: Type[BaseModule]) -> bool
```

### 3. PatchRouter (DAG)

**Features:**
- Directed Acyclic Graph for signal flow
- Kahn's algorithm for topological sorting
- Cycle detection prevents feedback loops
- Pre-allocated edge buffers (32 max connections)

**Implementation:**
```python
class PatchRouter:
    def connect(self, source_id: str, dest_id: str) -> bool
    def disconnect(self, source_id: str, dest_id: str) -> bool
    def get_processing_order(self) -> List[str]
    def validate_graph(self) -> bool  # Cycle detection
    def allocate_edge_buffers(self)   # Pre-allocate all buffers
```

### 4. Patch Update Flow

**Process-Based Updates (No Hot-Reload):**
1. All patch edits route to standby slot
2. Standby rebuilds graph in background
3. Validate graph (cycles, RT-safety)
4. Warm buffers with test signal
5. Signal ready for swap
6. Supervisor switches slots at buffer boundary
7. Old slot becomes new standby

**OSC Commands:**
```
/patch/connect <source> <dest>    # Add connection
/patch/disconnect <source> <dest> # Remove connection
/patch/create <id> <type>         # Create module instance
/patch/delete <id>                # Remove module
/patch/commit                     # Apply changes (triggers swap)
/patch/abort                      # Cancel pending changes
```

## Implementation Plan

### Day 1: Foundation (ParamSpec + BaseModule)
- [x] Document Phase 3 plan
- [ ] Update sprint.md
- [ ] Implement ParamSpec class
- [ ] Enhance BaseModule with param specs
- [ ] Add smoothing algorithms

### Day 2: Registry & Discovery
- [ ] Implement ModuleRegistry
- [ ] Add @register_module decorator
- [ ] Module discovery system
- [ ] RT-safety validation
- [ ] Lazy import mechanism

### Day 3: DAG Router
- [ ] Implement PatchRouter class
- [ ] Kahn's topological sort
- [ ] Cycle detection (DFS-based)
- [ ] Edge buffer pre-allocation
- [ ] Graph validation

### Day 4: Integration
- [ ] Integrate PatchRouter with ModuleHost
- [ ] Standby slot rebuilding logic
- [ ] Extended OSC commands
- [ ] Patch commit flow
- [ ] Slot swap coordination

### Day 5: Testing & Validation
- [ ] Unit tests for all components
- [ ] Integration test: sine → filter patch
- [ ] Patch update during audio playback
- [ ] 10-minute soak test
- [ ] Performance benchmarks

## Technical Constraints

### Real-Time Guarantees
- **Zero allocations** in audio callback
- **No imports** in active slot
- **No locks/syscalls** in process_buffer()
- **Boundary-only** parameter updates
- **Pre-allocated** buffers for all operations

### Memory Layout
```
MAX_MODULES = 16        # Per patch
MAX_EDGES = 32         # Connections
BUFFER_SIZE = 256      # Samples
EDGE_BUFFER_POOL = MAX_EDGES * BUFFER_SIZE * 4  # ~32KB
```

### Development vs Production

**Development Mode** (`CHRONUS_DEV_RELOAD=1`):
- Allow module reload for testing
- Never during audio callbacks
- Clear warnings about RT violations

**Production Mode** (default):
- Process-based updates only
- Standby slot rebuilding
- Atomic slot swaps
- Zero glitches guaranteed

## Success Criteria

### Performance
- [ ] Patch updates complete in <100ms
- [ ] Zero allocations in audio path
- [ ] <0.1% none_reads during updates
- [ ] Failover still <50ms

### Functionality
- [ ] Create arbitrary module graphs
- [ ] Live patch editing without audio interruption
- [ ] Parameter smoothing prevents clicks
- [ ] Cycle prevention works correctly

### Stability
- [ ] 10-minute continuous operation
- [ ] 50+ patch commits without degradation
- [ ] Memory usage remains constant
- [ ] CPU usage <10% for 5-module patch

## Risk Mitigation

### Identified Risks
1. **Graph rebuild time** - Mitigated by standby slot approach
2. **Cycle creation** - Prevented by validation before commit
3. **Memory fragmentation** - Solved by pre-allocation
4. **Import overhead** - Lazy loading only during rebuild

### Fallback Strategy
If patch commit fails:
- Standby slot remains unchanged
- Active audio continues
- Error reported via OSC
- User can abort or retry

## Module Examples

### Simple Sine with Metadata
```python
@register_module("sine")
class SimpleSine(BaseModule):
    def get_param_specs(self):
        return {
            "freq": ParamSpec(
                name="frequency",
                param_type=float,
                range=(20.0, 20000.0),
                default=440.0,
                units="Hz",
                smoothing_mode="exponential",
                smoothing_coeff=0.9995
            ),
            "gain": ParamSpec(
                name="gain",
                param_type=float,
                range=(0.0, 1.0),
                default=0.5,
                units="",
                smoothing_mode="linear",
                smoothing_coeff=0.99
            )
        }
```

### Example Patch
```python
# Create modules
registry.create_instance("osc1", "sine")
registry.create_instance("filt1", "biquad_filter")
registry.create_instance("env1", "adsr")

# Connect them
router.connect("osc1", "filt1")
router.connect("filt1", "env1")
router.connect("env1", "output")

# Get processing order
order = router.get_processing_order()
# Result: ["osc1", "filt1", "env1"]
```

## References

- Research document: `project/docs/realtime_audio_module_system_research_2025-09-02.md`
- Senior Dev feedback: Incorporated throughout
- VST3 parameter model: Inspiration for ParamSpec
- JUCE AudioProcessorGraph: Reference for DAG implementation

---

*Phase 3 transforms our synthesizer from a fixed chain to a fully modular, patchable instrument while maintaining our <50ms failover and zero-allocation guarantees.*