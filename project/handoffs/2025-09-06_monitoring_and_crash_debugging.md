# Session Handoff: Engine Monitoring and Crash Debugging

**Created**: 2025-09-06 14:45  
**From Session**: Chronus Nexus  
**To**: Next Chronus Instance  
**Context Window**: 85% - Near Limit

## 🎯 Critical Context

Successfully fixed acid module signal graph issue (accent envelope calculation was breaking pyo connectivity). Implemented real-time monitoring system for engine visibility but demo still crashes around bar 25-32 when hi-hats enter. Senior Dev identified likely cause as threading.Timer explosion in sequencer (if used).

## ✅ What Was Accomplished

### 1. Fixed Acid Module Signal Flow

- Identified accent envelope calculation breaking pyo signal graph
- Created acid_working.py without accent system
- Incremental testing isolated exact breaking point
- All acid features work except accent

### 2. Implemented Real-Time Monitoring System

- Added PeakAmp monitoring to engine_pyo.py
- Creates engine_status.txt (one-line current status)
- Creates engine_log.txt (last 100 events)
- Tracks audio level, message count, active gates
- Provides AI visibility without human feedback

## 🚧 Current Working State

### What IS Working:

- ✅ Acid filter module - All features except accent
- ✅ 4-voice polyphony with effects
- ✅ Real-time monitoring system
- ✅ OSC control and routing
- ✅ Simple demos and tests

### What is PARTIALLY Working:

- ⏳ acid_journey_demo.py - Runs until bar 25-32 then audio stops
- ⏳ Engine visibility - Have audio level but need more server diagnostics

### What is NOT Working:

- ❌ Complex demos with hi-hats - Audio stops at high activity
- ❌ Accent system in acid - Breaks signal graph

### Known Issues:

- 🐛 Demo crashes at bar 25-32 when hi-hats enter - No error, just silence
- 🐛 Engine requires restart after crash - Becomes unresponsive

## 🚨 Next Immediate Steps

1. **Test with monitoring active**
   - Run acid_journey_demo.py
   - Check engine_status.txt and engine_log.txt when crash occurs
   - Identify if messages still arriving after silence

2. **Add server diagnostics**
   - Log server.getIsStarted() status
   - Check for thread accumulation
   - Monitor CPU usage during crash

3. **Fix based on Senior Dev analysis**
   - Check if demos use threading.Timer
   - If yes, replace with event queue
   - Test if it's OSC flooding or thread explosion

## 📁 Files Created/Modified

**Created:**

- `pyo_modules/acid_working.py` - Working acid without accent
- `pyo_modules/acid_incremental.py` - Debug version for testing
- `examples/test_crash_diagnosis.py` - Diagnostic tests
- `project/docs/2025-09-06_debugging_engine_crash.md` - Analysis document

**Modified:**

- `engine_pyo.py` - Added monitoring system
- `pyo_modules/voice.py` - Reverted to simple version for debugging

## 💡 Key Insights/Learnings

- Pyo signal graphs break silently when nodes disconnect
- Multiplying by 0 in signal chain can break connectivity
- Need AI-readable feedback for audio debugging
- Senior Dev identified threading.Timer as likely crash cause
- The demos don't actually use sequencer class, just time.sleep()

## 🔧 Technical Notes

- Monitor with: open('engine_status.txt').read()
- Check log with: open('engine_log.txt').read()
- Audio level 0.0000 = silence, >0.001 = sound playing
- Accent calculation: self.main_env + (self.accent_env * self.accent * self.accent_weight) breaks when accent=0

## 📊 Progress Metrics

- Acid Module Implementation: 95% (missing accent)
- Monitoring System: 100%
- Crash Debugging: 40%
- Context Window at Handoff: 85%

---

_Handoff prepared by Chronus Nexus_  
_Implemented monitoring for AI visibility but demo crash at bar 25-32 still unresolved_