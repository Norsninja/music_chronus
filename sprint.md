# Sprint: Audio Module Expansion 🎛️

## Current State: Pattern System Complete ✅

After successful pattern save/load implementation:
- **Pattern management**: 128 slots with atomic save/load
- **Sequencer integration**: Bar-aligned loading, self-maintaining registry
- **Performance**: 15ms save, 25ms load, zero dropouts
- **Architecture proven**: Pyo engine with 5.3ms latency

## What We Have Now

### Working Components
- ✅ **engine_pyo.py** - Headless synthesizer with OSC control
- ✅ **Pattern save/load** - Complete with atomic operations
- ✅ **Integrated sequencer** - Pattern-based with bar alignment
- ✅ **Self-maintaining schema** - Auto-updates with map_route()
- ✅ **4-voice polyphony** - With effects sends
- ✅ **Acid filter** - TB-303 style on voice2

### Ready for Enhancement
- **Voice module** - Has stubs for slide/waveforms
- **OSC routing** - Extensible for new parameters
- **Effects chain** - Ready for distortion insert

## Current Sprint: Audio Module Implementation 🎛️

### Update (2025-01-09): Noise Generator Integration 🔊

After successful music creation workflow and agent development, expanding voice architecture with noise generators for professional drum synthesis.

#### Phase 1: Foundation (In Progress)
- [ ] Add noise oscillators to Voice class (white, pink, brown)
- [ ] Extend Selector from 3 to 6 waveform sources
- [ ] Update validation logic for indices 0-5
- [ ] Manual test of noise output

#### Phase 2: Core Features
- [ ] Implement amplitude calibration (0.7x white, 0.85x pink, 1.0x brown)
- [ ] Update schema registry documentation
- [ ] Verify OSC control for all waveforms

#### Phase 3: Polish & Testing
- [ ] Create comprehensive test suite
- [ ] Build drum synthesis examples (kick, snare, hi-hat)
- [ ] Performance benchmarks (<5% CPU increase)
- [ ] Documentation updates

### Week 1 Tasks (2025-01-07 - 2025-01-11) ✅ COMPLETED AHEAD OF SCHEDULE

#### Day 1: Oscillator Types ✅ COMPLETE
- [x] **Implement Saw/Square waveforms** - Using Selector pattern with 3 oscillators
- [x] **Add OSC routes** - `/mod/voiceN/osc/type <0|1|2>` (0=sine, 1=saw, 2=square)
- [x] **Test click-free switching** - Equal-power crossfade verified
- [x] **Update schema registry** - All parameters auto-registered
- [x] **Demo: Waveform comparison** - Comprehensive A/B testing

#### Day 1: Distortion Module ✅ COMPLETE (AHEAD OF SCHEDULE)
- [x] **Create DistortionModule class** - Using pyo Disto (4x faster than tanh)
- [x] **Insert in signal chain** - Master insert between mixer and effects
- [x] **Add OSC routes** - `/mod/dist1/drive|mix|tone` with equal-loudness mixing
- [x] **Test CPU impact** - Negligible overhead with proper implementation
- [x] **Demo: Techno/Industrial** - From subtle warmth to extreme saturation

#### Day 1: Integration & Documentation ✅ COMPLETE
- [x] **Combined tests** - All waveforms + distortion combinations tested
- [x] **Pattern compatibility** - Save/load includes new module states
- [x] **Performance verified** - Click-free operation with smooth parameters
- [x] **Technical documentation** - Comprehensive implementation analysis

### Week 1 Continuation: LFO Implementation ✅ COMPLETE

#### LFO Modules (Completed 2025-01-07)
- [x] **Research review** - Three iterations to achieve pattern compliance
- [x] **Create SimpleLFOModule class** - Fixed routing: LFO1→Voice2 filter, LFO2→Voice3 amp
- [x] **Add OSC routes** - `/mod/lfo1/rate|depth`, `/mod/lfo2/rate|depth`
- [x] **Test modulation smoothness** - Verified smooth, no artifacts
- [x] **Demo: Wobble bass** - LFO1 modulating voice2 filter (tested and audible)
- [x] **Demo: Tremolo** - LFO2 modulating voice3 amplitude (tested and audible)
- [x] **Schema registry integration** - Dynamic registration via register_module_schema()

### Week 2: Terminal Visualizer 📊 IN PROGRESS (2025-01-08)

#### Phase 1: Foundation (Days 1-3) 🚧
- [ ] **Basic visualizer scaffold** - Rich UI framework setup
- [ ] **OSC listener thread** - Monitor port 5005 messages
- [ ] **Status file reader** - Parse engine_status.txt
- [ ] **Panel layout** - Meters, spectrum, messages areas

#### Phase 2: Core Features (Days 4-7)
- [ ] **Audio level meters** - Peak hold with VU decay
- [ ] **FFT spectrum analyzer** - 8-band frequency display
- [ ] **OSC message monitor** - Scrolling message history
- [ ] **Voice state indicators** - Gate on/off, parameters

#### Phase 3: Polish (Days 8-10)
- [ ] **Performance optimization** - Target <5% CPU usage
- [ ] **Color schemes** - CGA/EGA retro palettes
- [ ] **Error handling** - Graceful disconnection/reconnection
- [ ] **Documentation** - Usage guide and configuration

### Week 2: Slide/Glide Implementation ✅ COMPLETE (2025-01-07)

#### Slide/Portamento (Completed 2025-01-07)
- [x] **Phase 1: Voice Module Update**
  - Added `slide_time_sig` and `slide_time` (SigTo smoothed) parameters
  - Inserted Port object after freq SigTo: `ported_freq = Port(self.freq, risetime=slide_time, falltime=slide_time)`
  - Updated all oscillators to use `ported_freq` instead of direct `self.freq`
  - Added `set_slide_time(time)` method with 0-1.5s clamping
  
- [x] **Phase 2: OSC Integration**
  - Added `/mod/voiceN/slide_time` route (0-1.5 seconds)
  - Updated schema registry with slide_time parameter
  - Included in get_status() for pattern save/load
  
- [x] **Phase 3: Testing & Validation**
  - Tested with 110→220→330 Hz frequency steps
  - Verified smooth exponential glides (Port provides this)
  - Confirmed no clicks or artifacts at slide boundaries
  - Tested interaction with active LFOs - works perfectly
  
- [x] **Phase 4: Demo Creation**
  - Created comprehensive test_slide.py with all modes
  - Tested TB-303 style acid slides on voice2
  - Documented optimal slide_time ranges in code

### Week 2: Recording Implementation ⚡ CURRENT (2025-01-07)

#### Research & Design (Completed)
- [x] **Codebase pattern analysis** - Identified module patterns, OSC routes, thread safety
- [x] **Pyo recording research** - Discovered Server.recstart()/recstop() (no Record object!)
- [x] **State management research** - Lock-free patterns, file naming, error handling

#### Implementation Plan (Server-Level Recording)
- [ ] **Phase 1: Recording Infrastructure**
  - Add recording state management to engine_pyo.py
  - Implement thread-safe start_recording()/stop_recording() methods
  - Create recordings/ directory structure
  - Use Server.recordOptions() and recstart()/recstop()
  
- [ ] **Phase 2: OSC Integration**
  - Add `/engine/record/start [filename]` route
  - Add `/engine/record/stop` route
  - Add `/engine/record/status` for state query
  - Update schema registry with recording commands
  
- [ ] **Phase 3: File Management**
  - Implement automatic timestamp-based naming
  - Use atomic file operations (tempfile pattern)
  - Add recording status to engine get_status()
  - Prevent concurrent recording sessions
  
- [ ] **Phase 4: Testing & Validation**
  - Test recording during pattern playback
  - Verify no audio dropouts (maintain 5.3ms latency)
  - Test with all effects and modulations active
  - Confirm WAV file quality and format

### Completed (2025-09-06)

#### Polyphony Implementation ✅
- [x] 4-voice architecture with Sig/SigTo smoothing
- [x] Global reverb/delay with per-voice sends
- [x] Fixed critical effects routing bug (pass Mix at init)
- [x] Full OSC schema with backward compatibility

#### Sequencer Updates ✅
- [x] PolySequencer with swing and note conversion
- [x] Headless operation (removed all user interaction)
- [x] Genre presets (Techno, Ambient, Dub)
- [x] Velocity → Filter/Amp modulation

### Medium-term Goals (Next Month)

#### 4. Live Performance
- [ ] MIDI input support
- [ ] Parameter automation
- [ ] Scene transitions
- [ ] Recording capabilities
- [ ] Live looping

#### 5. Musical Knowledge
- [ ] Chord progressions
- [ ] Scale awareness
- [ ] Genre templates
- [ ] Sound design presets

## Success Metrics

### Technical ✅ (Already Achieved)
- ✅ <10ms latency (5.3ms)
- ✅ Zero dropouts
- ✅ Clean architecture
- ✅ OSC control working

### Musical 🎯 (New Focus)
- [ ] Create 5 different musical styles
- [ ] 10-minute live performance without issues
- [ ] AI can improvise musically
- [ ] Patterns feel "groovy" not mechanical
- [ ] Can create emotional progression

## Development Philosophy

**Before**: How do we make Python do real-time audio?
**Now**: How do we make interesting music together?

The technical foundation is solved. Every session now should produce music, not debug code.

## Session Protocol

1. **Start with sound** - Boot engine, make noise immediately
2. **Musical goal** - "Let's make a techno beat" not "Let's test buffers"
3. **Iterate on music** - Change patterns, add effects, explore
4. **Save what sounds good** - Build a library of patterns/presets
5. **Document musical discoveries** - What combinations work?

## Current Sprint Tasks

### Today (2025-09-06)
- [x] Implement 4-voice polyphony with effects
- [x] Fix critical effects routing bug
- [x] Make sequencer headless
- [x] Port acid_filter to pyo (Complete - MoogLP working)
- [ ] Implement authentic 303 slide/portamento
- [ ] Upgrade oscillators to band-limited waveforms
- [ ] Fix acid input routing (pre-filter tap)

### Next Session
- [ ] Create Acid Bass demo with new modules
- [ ] Create Dub Delay demo  
- [ ] Create Ambient Pad demo
- [ ] 10-minute stability test

## Key Insights

1. **Tools matter** - Right tool (pyo) made everything simple
2. **Music first** - Technical perfection without music is worthless
3. **Collaboration focus** - AI+Human making music, not AI running code
4. **Simplicity wins** - 500 lines that work > 5000 that don't

## Next Session Focus

**Make music, not infrastructure.**

Start the engine, create a beat, add a bassline, apply effects. If we're not making sound in the first 5 minutes, we're doing it wrong.

---

*Updated: 2025-01-07*
*Status: Audio module expansion sprint*
*Next: Oscillator types implementation*
*Plan: project/docs/audio_modules_implementation_plan.md*