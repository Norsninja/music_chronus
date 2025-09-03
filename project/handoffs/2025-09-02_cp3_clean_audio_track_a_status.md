# Session Handoff: CP3 Clean Audio — Track A Status

Created: 2025-09-02  
From Session: Senior Dev + Chronus Nexus  
To: Next Chronus Instance  
Context Window: Near limit

## Critical Context

We achieved clean audio with Track A at 44100 Hz, BUFFER_SIZE=512, NUM_BUFFERS=16 using:
- Direct priming (immediate params/gate) on standby, warmup verification, and readiness flag.
- Swap gating on prime_ready + standby ring has data, plus prefill (4 buffers) before signaling ready.
- Latest‑wins read with cushion (read_latest_keep, keep_after_read=2); never tail=head.
- Anchored worker scheduler with coarse sleep (~3 ms) + ≤1 ms busy‑wait tail; GC disabled in workers.
- Filter smoothing (cutoff/Q) increased to 25 ms to remove zippering.

Result: 0.0–0.2% none‑reads, “beautiful and crisp” audio, stable multi‑commit swaps. 384/256 remain aspirational under WSL2 without Track B.

## What Was Accomplished

1) Router audio unblocked (CP3)
- Removed per‑buffer prepare() in ModuleHost router path (no state reset).
- Added lazy per‑module work buffers; ensured router helpers used for dynamic modules.

2) Standby priming path
- Prime via patch_queue with immediate params + gate, then warmup buffers and verify RMS.
- Added prime_ready shared flag; supervisor swaps only when primed and data present.
- Prefill 4 buffers on standby ring before setting prime_ready=1.

3) Audio path stability (Track A)
- Latest‑wins with cushion: read one near‑latest buffer per callback and leave ≥2 buffer cushion after swap.
- Anchored scheduling: coarse sleep ~3 ms, ≤1 ms busy‑wait tail; max catch‑up=2; soft re‑anchor on >50 ms late.
- GC disabled in workers to reduce jitter.
- Filter smoothing: cutoff/Q at 25 ms.

4) Clean audio at 512/16
- None‑reads ~0.0–0.2%; stable RMS; no “mosquito/engine” artifacts.
- Full chain (osc → ADSR → filter) stable; live parameter sweeps smooth.
- Multi‑commit/prime/swap cycles (≥3) clean with state persistence.

## Current Working State

Working
- Prime mechanism: ~10 ms priming; warmup verified; prefill(4); readiness signaled.
- Router/patch building and swaps clean; fault‑tolerant slot architecture intact.
- Audio callback: zero‑allocation, latest‑wins read with cushion.
- Modules: SimpleSine allocation‑free; ADSR/biquad functioning; filter smoothing prevents zippering.

Partial / Deferred
- Lower latency at 384/256: feasible with Track B (triple‑buffer + JIT/native DSP) and/or host tuning. Under WSL2, jitter often exceeds the 8.7 ms budget at 384 with cross‑process IPC.

## Known Issues

- WSL2 audio path/scheduling adds jitter; 384 can starve the callback despite latest‑wins. 512 hides this safely.
- ADSR/biquad are per‑sample Python loops; tighter buffers increase overhead and jitter sensitivity.
- Ring handoff remains more sensitive than a triple‑buffer “published index” design at low blocksizes.

## Next Steps

Short‑term (stability)
- Soak at 512/16 for 30–60 minutes: log none‑reads %, active ring occupancy, worker late cycles every 1000 callbacks.
- Multi‑commit stress (≥3 swaps); confirm post‑swap occupancy ≥2 during first few callbacks.
- Live sweeps of cutoff/gain; confirm no zippering with 25 ms smoothing.

Track B prep (optional, lower latency)
- Prototype triple‑buffer latest‑wins for the audio path behind CHRONUS_TRIPLE=1 (writer rotates 0/1/2, atomically publishes index; callback copies). Keep prime/warmup/prefill; prefill all 3 frames before swap.
- Consider JIT (Numba @njit) for ADSR and biquad loops to reduce Python overhead at smaller buffers.
- A/B at 384, then 256; accept only if none‑reads ≤1–2% and audio remains clean.

## Runtime Recommendations (locked for Track A)

Environment
- CHRONUS_SAMPLE_RATE=44100  
- CHRONUS_BUFFER_SIZE=512  
- CHRONUS_NUM_BUFFERS=16  
- CHRONUS_ROUTER=1

Audio path
- Latest‑wins read with read_latest_keep(keep_after_read=2). Do not set tail=head.
- Standby prime: warmup + prefill(4) before prime_ready=1.
- Worker: GC disabled; coarse sleep ~3 ms + ≤1 ms busy‑wait; anchored schedule; max catch‑up=2; lead target=2.
- Filter smoothing: cutoff/q = 25 ms. Gain smoothing ~5–10 ms.

WSL2 host tips
- Windows power plan: High/Ultimate Performance; avoid core parking; keep timer resolution low. Ensure device SR=44100 Hz.

## Files Modified (recent highlights)

- src/music_chronus/supervisor_v3_router.py — prime path, swap gate, timing, prefill, logs
- src/music_chronus/supervisor_v2_slots_fixed.py — AudioRing integrity, latest‑wins keep
- src/music_chronus/modules/biquad_filter.py — cutoff/Q smoothing 25 ms
- src/music_chronus/modules/simple_sine.py — allocation‑free steady state retained
- docs/ — cp3_prime_implementation_report.md, cp3_latest_wins_implementation_report.md, cp3_track_a_improvements_report.md

## Progress & Metrics

- Clean audio achieved at 512/16 (none‑reads 0.0–0.2%)
- Prime latency ~10 ms; swaps clean; full chain stable
- Lower latency deferred to Track B prototype + host tuning

---

Handoff prepared by Senior Dev / Chronus Nexus  
Track A clean audio baseline established; proceed with soak and optional Track B exploration

