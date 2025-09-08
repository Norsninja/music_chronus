# Terminal-Based Music Visualizer Implementation Plan
**Music Chronus Project**  
**Date:** 2025-01-08  
**Document Type:** Technical Architecture Plan

## 1. Executive Summary

This plan outlines the implementation of a real-time terminal-based music visualizer for the Music Chronus project. The visualizer will provide an ASCII/8-bit aesthetic display of audio metrics, OSC traffic monitoring, and pattern visualization, designed for both interactive monitoring and video recording of music sessions. The system will leverage the existing pyo engine's monitoring capabilities while adding non-intrusive spectral analysis and terminal UI components.

## 2. Problem Statement

Currently, the Music Chronus engine operates headlessly with minimal visual feedback limited to status text files. Users need real-time visual feedback showing audio levels, frequency content, active voices, sequencer patterns, and OSC commands to understand what the engine is doing during music creation sessions. This is especially important for video recordings and live performances.

## 3. Proposed Solution

A standalone terminal visualizer that connects to the running engine via OSC monitoring and shared data files, displaying real-time audio analysis, pattern states, and system metrics using an 8-bit retro aesthetic. The visualizer will run in a separate process to avoid impacting audio performance, using the Rich library for terminal UI and extracting audio metrics via OSC broadcast from enhanced pyo analysis objects.

## 4. Scope Definition

### In Scope:
- Real-time audio level meters (VU/peak) for each voice and master output
- FFT spectrum analyzer with frequency bands (bass/mid/high visualization)
- OSC message monitor showing recent commands with timestamp
- Pattern/sequencer visualization showing active tracks and current position
- Voice state indicators (gate on/off, current parameters)
- 8-bit/retro ASCII aesthetic with box-drawing characters
- Recording status indicator
- CPU/memory usage display
- Configurable color schemes (CGA/EGA palettes)

### Out of Scope:
- GUI/windowed interface (terminal only)
- Audio waveform oscilloscope (too CPU intensive for terminal)
- Direct audio input processing (uses engine's analysis)
- Interactive controls (read-only visualization)
- MIDI visualization
- Video export functionality
- Cross-network monitoring (localhost only)

## 5. Success Criteria

- **Functional Requirements Met:**
  - Displays real-time audio levels with <50ms latency
  - Shows FFT spectrum with at least 15 FPS update rate
  - Monitors all OSC traffic without dropping messages
  - Pattern display syncs with sequencer playback
  
- **Performance Benchmarks:**
  - CPU usage < 5% on modern systems
  - Memory footprint < 50MB
  - Terminal refresh rate ≥ 20 FPS
  - No audio dropouts or engine performance impact
  
- **Quality Metrics:**
  - Zero crashes during 1-hour continuous operation
  - Graceful handling of engine disconnection/reconnection
  - Clean terminal restoration on exit
  
- **User Acceptance:**
  - Readable at standard terminal sizes (80x24 minimum)
  - Video-recording friendly (no flicker, stable layout)
  - Aesthetically consistent 8-bit appearance

## 6. Technical Approach

### Architecture Overview:
```
┌─────────────────┐     OSC      ┌──────────────┐
│  engine_pyo.py  │────────────> │  visualizer  │
│                 │               │     .py      │
│  - FFT analysis │   Status      │              │
│  - Peak meters  │────────────> │  Rich TUI    │
│  - OSC server   │   Files       │              │
└─────────────────┘               └──────────────┘
```

### Technology Stack:
- **Terminal UI:** Rich library (modern, cross-platform, performant)
- **Audio Analysis:** Pyo FFT and PeakAmp objects in engine
- **OSC Reception:** pythonosc ThreadingOSCUDPServer
- **Data Exchange:** OSC broadcast + status files (engine_status.txt)
- **Threading:** Separate threads for OSC, file monitoring, UI refresh

### Design Patterns:
- **Observer Pattern:** OSC listener updates shared state
- **Producer-Consumer:** Audio metrics queue between engine and visualizer
- **MVC Pattern:** Model (data), View (Rich panels), Controller (update loop)
- **Circular Buffer:** For OSC message history and audio metrics

### Data Flow:
1. Engine computes FFT/peaks using pyo objects (FFT, PeakAmp)
2. Engine broadcasts metrics via OSC (/viz/spectrum, /viz/levels)
3. Visualizer receives OSC messages in background thread
4. Data stored in thread-safe circular buffers
5. UI thread reads buffers and updates Rich panels at 20 FPS

### **REQUIRED: Specific Code Integration Points**

#### Engine Modifications (engine_pyo.py):
- **Lines 845-865:** Extend `setup_monitoring()` to add FFT analysis
- **Lines 880-898:** Modify `update_status()` to broadcast visualization data
- **After line 1250:** Add new OSC handlers for visualization control
- **Lines 848-849:** Replace PeakAmp with parallel FFT + PeakAmp chain

#### New FFT Integration:
```python
# engine_pyo.py, after line 848
self.fft_analyzer = FFT(self.master, size=2048, overlaps=4)
self.spectrum_follower = Follower(self.fft_analyzer['real'], freq=10)
```

#### OSC Broadcast Routes:
```python
# engine_pyo.py, in update_status() around line 890
# Add spectrum broadcast
spectrum_data = self.get_spectrum_bands()
self.broadcast_client.send_message('/viz/spectrum', spectrum_data)

# Add voice levels broadcast  
voice_levels = [self.voices[v].get_level() for v in self.voices]
self.broadcast_client.send_message('/viz/levels', voice_levels)
```

## 7. Integration Points

### Engine Integration (engine_pyo.py):

**File:** `engine_pyo.py`  
**Lines:** 845-865 (setup_monitoring method)  
**Purpose:** Add FFT and enhanced monitoring
**Current code:**
```python
def setup_monitoring(self):
    """Setup real-time audio and message monitoring"""
    # Audio level monitoring
    self.peak_meter = PeakAmp(self.master)
```
**Modification needed:**
Add FFT analyzer and spectrum extraction after peak meter initialization.

**File:** `engine_pyo.py`  
**Lines:** 880-898 (update_status method)  
**Purpose:** Broadcast visualization data via OSC
**Integration:** Add OSC broadcast client and send spectrum/level data to port 5006

**File:** `engine_pyo.py`  
**Lines:** 1200-1250 (OSC handlers section)  
**Purpose:** Add visualization control commands
**New handlers:** `/viz/start`, `/viz/stop`, `/viz/config`

### Pattern Integration:

**File:** `engine_pyo.py`  
**Lines:** 95-100 (SequencerManager._tick)  
**Purpose:** Access current sequencer state
**Integration:** Read `self.tracks` and `self.global_step` for pattern display

### Existing Monitoring Patterns:

**File:** `engine_pyo.py`  
**Lines:** 856-858 (log_buffer usage)  
**Pattern:** Deque-based circular buffer for event history
**Follow:** Use same pattern for OSC message history in visualizer

## 8. Implementation Phases

### **Phase 1: Foundation** (2-3 days)

**Deliverables:**
- Basic visualizer scaffold with Rich UI framework
- OSC listener thread receiving messages on port 5005
- Status file reader for engine_status.txt
- Basic layout with panels for meters, spectrum, messages

**Files to create:**
- `visualizer.py` (main application)
- `viz_components.py` (UI components)
- `viz_data.py` (data models and buffers)

**Acceptance Criteria:**
- Displays static UI layout in terminal
- Receives and logs OSC messages
- Shows engine connection status
- Clean exit with Ctrl+C

**Verification:**
```bash
python visualizer.py
# Should show terminal UI with empty panels
# Should log received OSC messages to console
```

### **Phase 2: Core Features** (3-4 days)

**Primary Features:**
- Audio level meters with peak hold
- FFT spectrum analyzer (8-band display)
- OSC message monitor with scrolling history
- Voice state indicators

**Engine Integration Points:**
- Modify `engine_pyo.py:845-865` to add FFT analyzer
- Modify `engine_pyo.py:880-898` to broadcast viz data
- Add broadcast client initialization around line 850

**Specific Integration:**
```python
# engine_pyo.py line 850, after peak_meter
self.fft_analyzer = FFT(self.master, size=2048, overlaps=4)
self.viz_broadcast = udp_client.SimpleUDPClient('127.0.0.1', 5006)

# engine_pyo.py line 890, in update_status
if hasattr(self, 'fft_analyzer'):
    # Extract spectrum, broadcast to visualizer
    real_data = self.fft_analyzer['real'].get()
    self.viz_broadcast.send_message('/viz/spectrum', real_data[:32])
```

**Initial Testing:**
```bash
# Terminal 1
python engine_pyo.py

# Terminal 2  
python visualizer.py

# Terminal 3
python chronusctl.py test
# Should see levels and spectrum respond
```

### **Phase 3: Polish & Testing** (2-3 days)

**Edge Cases & Optimization:**
- Handle engine disconnection/reconnection gracefully
- Optimize refresh rate based on terminal capabilities
- Add configurable color schemes
- Implement adaptive layout for different terminal sizes

**Performance Optimization:**
- Profile CPU usage, target < 5%
- Implement dirty-rectangle updates
- Add frame rate limiting
- Use numpy for spectrum calculations

**Comprehensive Testing:**
```bash
# Test suite
python tests/test_visualizer.py

# Performance test
python tests/test_viz_performance.py

# Long-running stability test
python visualizer.py --test-mode --duration 3600
```

**Documentation:**
- Create `docs/visualizer_usage.md`
- Add configuration examples
- Document keyboard shortcuts

## 9. Risk Assessment

### Technical Risks:

**Risk:** Terminal refresh causes flicker  
**Likelihood:** Medium  
**Impact:** High (unusable for video)  
**Mitigation:** Use Rich's double-buffering, limit FPS to 20  
**Contingency:** Implement custom refresh with ANSI codes

**Risk:** FFT analysis impacts audio performance  
**Likelihood:** Low  
**Impact:** High (audio dropouts)  
**Mitigation:** Use overlaps=2 instead of 4, smaller FFT size  
**Contingency:** Make FFT optional, fall back to peak-only

**Risk:** OSC message drops under load  
**Likelihood:** Medium  
**Impact:** Medium (missing visual updates)  
**Mitigation:** Use threading, larger receive buffer  
**Contingency:** Sample messages, show "..." for drops

**Risk:** Windows terminal compatibility issues  
**Likelihood:** High  
**Impact:** Medium (degraded appearance)  
**Mitigation:** Test on Windows Terminal, provide fallback ASCII  
**Contingency:** Curses-based alternative implementation

### Dependencies:
- Rich library must support target Python version
- Pyo FFT must provide accessible data
- Terminal must support ANSI escape codes

## 10. Estimated Timeline

**Total Duration:** 7-10 days

- **Phase 1 (Foundation):** Days 1-3
  - Day 1: Project setup, Rich UI scaffold
  - Day 2: OSC listener, data models
  - Day 3: Basic layout and panels

- **Phase 2 (Core Features):** Days 4-7
  - Day 4: Engine FFT integration
  - Day 5: Level meters and spectrum
  - Day 6: OSC monitor, voice states
  - Day 7: Integration testing

- **Phase 3 (Polish):** Days 8-10
  - Day 8: Performance optimization
  - Day 9: Edge cases and error handling
  - Day 10: Documentation and final testing

**Critical Path:** Engine FFT integration → Spectrum display → Performance optimization

**Buffer Time:** 2 days for unexpected issues

## 11. Alternatives Considered

### Alternative 1: Integrated Visualizer in Engine
**Approach:** Build visualization directly into engine_pyo.py  
**Pros:** Direct access to audio buffers, no IPC overhead  
**Cons:** Violates single responsibility, risks audio performance  
**Rationale for rejection:** Engine stability is paramount

### Alternative 2: Web-Based Visualizer
**Approach:** HTML5 canvas with WebSockets  
**Pros:** Rich graphics, easier animations, cross-platform  
**Cons:** Requires browser, not terminal-based, latency  
**Rationale for rejection:** Doesn't meet terminal requirement

### Alternative 3: Curses-Based Implementation
**Approach:** Use Python curses instead of Rich  
**Pros:** Lower level control, potentially faster  
**Cons:** More complex, less portable, no built-in widgets  
**Rationale for rejection:** Rich provides better abstraction

### Alternative 4: Direct Audio Analysis in Visualizer
**Approach:** Visualizer taps audio directly via PyAudio  
**Pros:** Independent of engine, more control  
**Cons:** Duplicate processing, synchronization issues  
**Rationale for rejection:** Inefficient, complex synchronization

**Trade-offs Accepted:**
- Accepting ~50ms visualization latency for engine stability
- Using OSC overhead instead of shared memory for simplicity
- Terminal limitations vs GUI flexibility for recording aesthetic

## 12. References

### Documentation:
- [Pyo FFT Documentation](http://ajaxsoundstudio.com/pyodoc/api/classes/fourier.html)
- [Rich Terminal UI Guide](https://rich.readthedocs.io/)
- [Python-OSC Documentation](https://python-osc.readthedocs.io/)

### Code Examples (existing patterns):
- `engine_pyo.py:856-858` - Circular buffer pattern using deque
- `engine_pyo.py:845-865` - Current monitoring implementation
- `pyo_modules/simple_lfo.py:9-138` - Module pattern to follow

### Industry Best Practices:
- [Real-time FFT Visualization](https://github.com/aiXander/Realtime_PyAudio_FFT)
- [Terminal Animation Techniques](https://github.com/rothgar/awesome-tuis)
- [8-bit Aesthetic Guidelines](https://en.wikipedia.org/wiki/Code_page_437)

### Related Tools:
- Rich - Modern terminal rendering
- ASCIIMATICS - ASCII animations (alternative)
- Blessed - Terminal control (alternative)
- Curses - Low-level terminal control

### Research Documents:
- `project/research/visualizer_codebase_analysis.json` - Engine analysis task
- `project/research/visualizer_task_external.json` - External research task
- `project/research/visualizer_task_internal.json` - Internal patterns task

---

**Next Steps:**
1. Review and approve this plan
2. Create `visualizer.py` scaffold with Rich UI
3. Implement Phase 1 foundation
4. Begin engine FFT integration in parallel

**Success Metrics:**
- Working visualizer demo within 3 days
- Full feature set within 7 days  
- Video-ready quality within 10 days