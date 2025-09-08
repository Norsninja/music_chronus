# Chronus Pet Implementation Plan
**Plan Date:** 2025-01-08  
**Project:** Music Chronus Terminal Visualizer Virtual Pet  
**Version:** 1.0.0

## 1. Executive Summary

This plan details the implementation of a virtual pet feature for the Music Chronus terminal visualizer that reacts to musical quality through intelligent scoring algorithms and auto-scales as new synthesizer modules are added. The pet will live in the existing visualizer's unused bottom panel space, providing visual feedback on the musical experience through animated states ranging from sleeping to transcendent, all while maintaining the engine's critical 5.3ms audio latency requirement.

## 2. Problem Statement

The current terminal visualizer effectively displays audio levels and spectrum data but lacks an engaging visual element that responds to the quality and complexity of the music being created. Users have no immediate visual feedback about whether their musical choices are creating interesting, dynamic compositions. Additionally, as new synthesizer modules are added to the engine, any hardcoded scoring system would quickly become outdated and require manual maintenance.

## 3. Proposed Solution

Implement a dynamic virtual pet system that:
- Lives in the bottom panel of the existing Rich-based terminal visualizer
- Automatically discovers available synthesizer parameters via the engine's schema system
- Scores musical quality based on energy variance, spectral balance, and parameter utilization
- Displays pet states through ASCII animations that reflect the current musical excitement level
- Requires zero manual updates when new modules are added to the engine

## 4. Scope Definition

### In Scope
- Virtual pet display class with 6 animated states (sleeping, waking, vibing, dancing, raving, transcendent)
- Integration into existing visualizer.py without breaking current functionality
- Musical quality scoring based on existing OSC broadcast data (/viz/levels, /viz/spectrum)
- Auto-discovery of engine modules via /engine/schema OSC query
- Smooth state transitions with buffering to prevent jitter
- Performance optimization to maintain <10ms total processing time
- Clean separation from core visualizer code for maintainability

### Out of Scope
- GUI-based pet display (terminal-only for this implementation)
- Machine learning or neural network-based behavior systems
- Pet interaction or user control features
- Persistent pet state/memory between sessions
- Multi-pet systems or breeding mechanics
- Sound generation by the pet itself
- External plugin loading system (will use internal module discovery only)
- Mobile or web-based visualization

## 5. Success Criteria

### Functional Requirements Met
- Pet displays correctly in bottom panel without overlapping other visualizer elements
- Pet state changes reflect musical quality within 100ms of audio events
- All 6 pet states are visually distinct and smoothly animated
- Auto-discovery correctly identifies all engine modules without manual configuration

### Performance Benchmarks Achieved
- Total pet system processing time: <10ms per update cycle
- Animation frame rate: stable 10-15 FPS without flicker
- Memory usage: <50MB additional RAM consumption
- CPU usage: <5% additional on modern hardware

### Quality Metrics Satisfied
- Musical quality scoring correlates with subjective listening experience (verified through testing)
- Pet behavior feels responsive and organic, not mechanical
- State transitions are smooth without jarring jumps
- System continues working correctly as new modules are added

### User Acceptance Criteria
- Pet enhances rather than distracts from the music creation experience
- Visual feedback helps users understand their musical choices
- System requires no user configuration or maintenance
- Documentation clearly explains pet behavior patterns

## 6. Technical Approach

### Architecture Decisions and Rationale

**Component Architecture**: Modular design with clear separation of concerns
- `ChronusPet` class: Core pet logic and state management
- `MusicQualityScorer` class: Scoring algorithms and parameter analysis
- `PetAnimator` class: ASCII animation and rendering
- `SchemaDiscovery` class: Auto-discovery and module tracking

**Technology Stack Choices**
- **Rich Library** (existing): Terminal UI framework for flicker-free animation via Live context
- **Python threading** (existing): Non-blocking OSC communication and data processing
- **Collections.deque** (existing): Efficient circular buffers for historical data
- **NumPy** (if needed): Fast array operations for variance calculations

### Design Patterns

**Observer Pattern**: Pet subscribes to audio data broadcasts
```python
class ChronusPet:
    def __init__(self, visualizer):
        self.visualizer = visualizer
        self.subscribe_to_audio_updates()
```

**State Machine Pattern**: Clean state transitions with defined rules
```python
class PetStateMachine:
    states = ['sleeping', 'waking', 'vibing', 'dancing', 'raving', 'transcendent']
    transitions = {
        'sleeping': {'condition': lambda s: s.energy > 0.1, 'next': 'waking'},
        'waking': {'condition': lambda s: s.energy > 0.3, 'next': 'vibing'},
        # ...
    }
```

### Data Flow and System Interactions

1. **Audio Data Input** → OSC broadcasts from engine (/viz/levels, /viz/spectrum)
2. **Schema Query** → Periodic /engine/schema requests for module discovery
3. **Quality Scoring** → Analysis of audio features and parameter utilization
4. **State Calculation** → Mapping scores to pet emotional states
5. **Animation Rendering** → ASCII frame selection and display via Rich

### Specific Code Integration Points

**File: visualizer.py**
- Lines 67-71: Modify layout to add pet panel
- Lines 290-294: Add pet update call in update_display()
- Lines 34-62: Add pet-related data structures to __init__
- After line 339: Add new ChronusPet class definition

**File: engine_pyo.py** (read-only reference)
- Lines 900-951: Existing update_status() broadcasts we'll consume
- Lines 1647-1681: capture_all_states() pattern for state discovery
- Lines 486-656: Parameter registry structure we'll query

## 7. Integration Points

### Exact Files and Line Numbers for Modifications

**Primary Integration: visualizer.py**
```python
# Line 67-71: Modify layout structure
self.layout["main"].split_column(
    Layout(name="top_row"),    # New: Contains levels, spectrum, messages
    Layout(name="pet", size=8)  # New: Pet display area
)
self.layout["top_row"].split_row(
    Layout(name="levels", ratio=1),
    Layout(name="spectrum", ratio=2),
    Layout(name="messages", ratio=1)
)

# Line 62: Add pet instance to __init__
self.pet = ChronusPet(self)  # New pet instance

# Line 294: Add pet update in update_display()
self.layout["pet"].update(self.pet.render())  # Update pet display

# After line 339: Add ChronusPet class
class ChronusPet:
    """Virtual pet that reacts to musical quality"""
    # Implementation here
```

### APIs and Interfaces Required

**OSC Message Consumption** (existing, no changes needed)
- `/viz/levels`: Voice level data (4 floats, 0.0-1.0)
- `/viz/spectrum`: Frequency spectrum (8 floats, 0.0-1.0)
- `/engine/schema`: Complete parameter registry (JSON structure)

**New Internal Interfaces**
```python
class MusicQualityScorer:
    def calculate_energy_variance(self, level_history: deque) -> float
    def calculate_spectral_balance(self, spectrum: list) -> float
    def calculate_parameter_utilization(self, schema: dict, current_values: dict) -> float
    def get_composite_score(self) -> float  # 0.0-1.0 normalized
```

### Dependencies on Other Components
- Rich library Layout and Panel classes (already imported)
- OSC dispatcher for message handling (already configured)
- Threading locks for thread-safe data access (already in use)

### Impact on Current Functionality
- No breaking changes to existing visualizer features
- Additional 8 lines of vertical space used in terminal
- Slight increase in update_display() processing time (<10ms)

### Migration Considerations
- Backward compatible: visualizer continues to work without engine changes
- Forward compatible: pet auto-adapts to new engine modules
- No data migration required (stateless between sessions)

## 8. Implementation Phases

### Phase 1: Foundation (2-3 days)

**Deliverables:**
- Basic ChronusPet class with state management
- Integration into visualizer layout
- Simple 4-state animation system (idle, excited, dancing, sleeping)

**Acceptance Criteria:**
- Pet displays in bottom panel without breaking layout
- Manual state changes work correctly
- Animations cycle smoothly at 10 FPS

**Files to Create/Modify:**
```python
# visualizer.py modifications:
# Lines 67-71: Layout restructuring
# Line 62: Add self.pet = ChronusPet(self)
# Line 294: Add self.layout["pet"].update(self.pet.render())
# Lines 340-500 (new): ChronusPet class implementation

# New file: pet_animations.py
# Lines 1-50: ASCII frame definitions
PET_FRAMES = {
    'sleeping': ["(-_-)", "(-.-)", "(-.-)zzZ"],
    'vibing': ["(◕‿◕)", "(◔‿◔)", "(◕‿◕)"],
    'dancing': ["♪(┌・。・)┌", "♪└(・。・)┘♪", "♪┌(・。・)┐♪"],
    'raving': ["\\(^o^)/", "\\(≧∇≦)/", "\\(^▽^)/"]
}
```

**Verification Commands:**
```bash
# Test pet display without audio
python visualizer.py  # Should show pet in bottom panel

# Test with engine running
python engine_pyo.py &
python visualizer.py  # Pet should appear with live data
```

### Phase 2: Core Features (3-4 days)

**Deliverables:**
- MusicQualityScorer implementation with variance calculation
- Schema discovery via OSC query
- Dynamic state transitions based on scores
- Extended to 6 states (add waking, transcendent)

**Acceptance Criteria:**
- Pet responds to actual music quality changes
- Schema query successfully discovers all modules
- State transitions feel natural and responsive

**Specific Integration Points:**
```python
# visualizer.py additions:
# Lines 501-650 (new): MusicQualityScorer class
class MusicQualityScorer:
    def __init__(self, pet):
        self.pet = pet
        self.level_history = deque(maxlen=30)  # 3 seconds at 10Hz
        self.spectrum_history = deque(maxlen=30)
        self.discovered_modules = {}
        
    def update(self, levels, spectrum):
        # Calculate energy variance (lines 510-525)
        self.level_history.append(levels)
        if len(self.level_history) > 10:
            energy = [sum(l**2) for l in self.level_history]
            variance = np.var(energy) if energy else 0
            self.energy_variance = min(variance / 1000, 1.0)
        
        # Calculate spectral balance (lines 526-540)
        self.spectrum_history.append(spectrum)
        # Implementation following research patterns

# Lines 651-700 (new): SchemaDiscovery class
class SchemaDiscovery:
    def query_schema(self):
        # Send /engine/schema OSC message
        # Parse response and update discovered_modules
```

**Files to Modify:**
```python
# visualizer.py:
# Line 99: Add schema query handler
self.dispatcher.map("/engine/schema/response", self.handle_schema_response)

# Lines 170-190 (new): Schema response handler
def handle_schema_response(self, addr: str, *args):
    """Process schema discovery response"""
    if self.pet:
        self.pet.discovery.update_modules(args[0])
```

### Phase 3: Polish & Testing (2-3 days)

**Deliverables:**
- Smooth animation transitions with easing
- Performance optimization and profiling
- Achievement/combo system for extended engagement
- Comprehensive documentation

**Acceptance Criteria:**
- All animations smooth without flicker
- Total processing time <10ms verified
- Edge cases handled gracefully
- Documentation complete with examples

**Specific Optimizations:**
```python
# visualizer.py optimizations:
# Lines 400-420: Pre-compute all animation frames
class ChronusPet:
    def __init__(self):
        self._precompute_frames()
        
    def _precompute_frames(self):
        # Pre-render all ASCII frames at startup
        self.rendered_frames = {}
        for state, frames in PET_FRAMES.items():
            self.rendered_frames[state] = [
                Panel(Text(frame, justify="center"), 
                      box=box.ROUNDED, 
                      border_style=self._get_border_style(state))
                for frame in frames
            ]

# Lines 450-470: Buffered state transitions
def update_state(self, new_state):
    if new_state != self.target_state:
        self.target_state = new_state
        self.transition_progress = 0.0
    
    # Smooth transition over 500ms
    if self.current_state != self.target_state:
        self.transition_progress += 0.02  # 50 FPS * 0.02 = 1 second
        if self.transition_progress >= 1.0:
            self.current_state = self.target_state
```

**Test Files to Create:**
```python
# test_pet_performance.py (new file)
# Lines 1-50: Performance benchmarking
import time
import cProfile

def test_pet_update_performance():
    """Verify pet update stays under 10ms"""
    pet = ChronusPet(None)
    start = time.perf_counter()
    for _ in range(100):
        pet.update([0.5]*4, [0.3]*8)
    elapsed = (time.perf_counter() - start) / 100
    assert elapsed < 0.010, f"Pet update took {elapsed*1000:.2f}ms"
```

## 9. Risk Assessment

### Technical Risks

**Risk 1: Performance Impact on Audio Latency**
- **Likelihood:** Medium
- **Impact:** High (audio glitches unacceptable)
- **Mitigation:** Profile all pet operations, use separate thread for heavy calculations
- **Contingency:** Reduce animation frame rate or disable complex scoring if needed

**Risk 2: OSC Message Processing Overload**
- **Likelihood:** Low
- **Impact:** Medium (missed messages, lag)
- **Mitigation:** Use existing buffering, process in batches
- **Contingency:** Reduce OSC query frequency, cache schema data longer

**Risk 3: Terminal Compatibility Issues**
- **Likelihood:** Medium (Windows vs Unix differences)
- **Impact:** Low (visual glitches only)
- **Mitigation:** Test on all platforms, use Rich's cross-platform abstractions
- **Contingency:** Provide fallback ASCII-only mode

### Mitigation Strategies

1. **Performance Monitoring**: Add timing metrics to all pet operations
2. **Feature Flags**: Allow disabling pet via command-line argument
3. **Graceful Degradation**: Pet becomes static image if processing fails
4. **Incremental Rollout**: Test each phase thoroughly before proceeding

### Dependencies That Could Cause Delays

- Rich library updates breaking API compatibility (low risk)
- Engine OSC broadcast changes (low risk, we control both sides)
- NumPy installation issues on some systems (medium risk, make optional)

## 10. Estimated Timeline

### Phase Breakdown
- **Phase 1 (Foundation):** 2-3 days
  - Day 1: Pet class structure and layout integration
  - Day 2: Basic animations and state management
  - Day 3: Testing and refinement

- **Phase 2 (Core Features):** 3-4 days
  - Day 1: Musical quality scorer implementation
  - Day 2: Schema discovery and auto-scaling
  - Day 3: Dynamic state transitions
  - Day 4: Integration testing

- **Phase 3 (Polish):** 2-3 days
  - Day 1: Animation smoothing and transitions
  - Day 2: Performance optimization
  - Day 3: Documentation and final testing

### Critical Path
1. Layout integration (blocks all other work)
2. Basic pet class (blocks scoring integration)
3. Schema discovery (blocks auto-scaling features)
4. Performance optimization (blocks release)

### Buffer Time
- 2 additional days for unexpected issues
- 1 day for platform-specific testing
- **Total Timeline: 10-13 days**

### Milestone Checkpoints
- **Day 3:** Basic pet visible and animating
- **Day 7:** Pet responding to music
- **Day 10:** Feature complete and optimized

## 11. Alternatives Considered

### Alternative 1: External Pet Process
- **Approach:** Separate Python process for pet logic
- **Pros:** Complete isolation, can't affect audio
- **Cons:** Complex IPC, synchronization issues
- **Decision:** Rejected - adds complexity without clear benefit

### Alternative 2: Web-Based Visualization
- **Approach:** Browser-based pet with WebSocket connection
- **Pros:** Rich graphics, cross-platform
- **Cons:** Requires web server, higher latency
- **Decision:** Rejected - violates terminal-only constraint

### Alternative 3: Curses-Based Custom Renderer
- **Approach:** Direct curses manipulation for animation
- **Pros:** Maximum control, potentially faster
- **Cons:** Platform-specific code, harder to maintain
- **Decision:** Rejected - Rich provides sufficient performance

### Alternative 4: Simple Loudness-Based Reactions
- **Approach:** Pet reacts only to volume levels
- **Pros:** Very simple to implement
- **Cons:** Boring, doesn't reflect musical quality
- **Decision:** Rejected - doesn't meet quality requirements

### Trade-offs Accepted
- Using Rich's rendering (slight overhead) for maintainability
- Terminal-only display (limited graphics) for consistency
- Stateless between sessions (no memory) for simplicity
- Fixed 6 states (less variety) for predictability

## 12. References

### Documentation
- **Project Instructions:** `CLAUDE.md` - Core mission and constraints
- **System API:** `project/docs/SYSTEM_CONTROL_API.md` - OSC command reference
- **Sprint Goals:** `sprint.md` - Current objectives and progress

### Code Examples and Patterns
- **SimpleLFOModule:** `pyo_modules/simple_lfo.py:109-134` - Schema pattern example
- **Engine Registry:** `engine_pyo.py:486-656` - Parameter registry structure
- **Status Broadcasting:** `engine_pyo.py:900-951` - OSC broadcast pattern
- **State Capture:** `engine_pyo.py:1647-1681` - Complete state pattern

### Related Tools and Libraries
- **Rich Documentation:** https://rich.readthedocs.io/ - Terminal UI framework
- **PyOSC:** https://pypi.org/project/python-osc/ - OSC communication
- **NumPy:** https://numpy.org/ - Efficient array operations

### Research Documents Created by Sub-Agents
- **External Research:** `project/research/virtual_pet_music_visualizer_2025-01-08.md`
  - Terminal animation performance benchmarks
  - Musical quality scoring algorithms
  - Plugin architecture patterns

- **Codebase Research:** `project/research/auto_registration_dynamic_discovery_2025-01-08.md`
  - Schema auto-registration patterns
  - Module discovery mechanisms
  - State broadcasting systems

### Industry Best Practices
- **Sonic Visualiser:** Professional audio analysis patterns
- **Synesthesia VJ:** Real-time music visualization techniques
- **Python Packaging Guide:** Plugin discovery best practices

---

## Implementation Checklist

### Pre-Implementation
- [ ] Review existing visualizer.py code thoroughly
- [ ] Test current visualizer with engine running
- [ ] Verify OSC broadcast data format
- [ ] Set up performance profiling tools

### Phase 1 Tasks
- [ ] Create pet_animations.py with frame definitions
- [ ] Modify visualizer.py layout structure
- [ ] Implement basic ChronusPet class
- [ ] Add pet rendering to update loop
- [ ] Test animations at target frame rate

### Phase 2 Tasks
- [ ] Implement MusicQualityScorer class
- [ ] Add energy variance calculation
- [ ] Create schema discovery mechanism
- [ ] Implement state transition logic
- [ ] Test with various music styles

### Phase 3 Tasks
- [ ] Add animation smoothing
- [ ] Profile and optimize performance
- [ ] Create comprehensive tests
- [ ] Write user documentation
- [ ] Platform compatibility testing

### Verification Commands
```bash
# Test basic functionality
python visualizer.py

# Test with engine
python engine_pyo.py &
python visualizer.py

# Performance profiling
python -m cProfile -o pet_profile.stats visualizer.py
python -c "import pstats; p = pstats.Stats('pet_profile.stats'); p.sort_stats('cumulative').print_stats(20)"

# Memory profiling
python -m memory_profiler visualizer.py
```

This comprehensive plan provides a clear, phased approach to implementing the Chronus pet feature with specific integration points, risk mitigation strategies, and measurable success criteria. The implementation leverages existing engine patterns for auto-discovery and maintains the project's core constraint of sub-10ms processing overhead.