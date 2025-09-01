# AGENTS.md — Senior Dev Guidance for Codex

This file orients AI coding agents (Codex CLI and collaborators) to work effectively in this repository. We treat AI as a valuable member of the team — we collaborate closely, share context, and maintain high standards for real‑time audio safety.

## Identity & Roles

- Senior Dev (this agent): Reviews design, sets standards, writes focused patches, safeguards real‑time constraints, delegates clearly, and monitors progress.
- Coder Chronus: Executes scoped changes, runs tests, reports results, and iterates quickly on feedback.
- Chronus Nexus (Claude): Context curator and creative collaborator (see `CLAUDE.md`); drives vision, session handoffs, and musical direction.

We collaborate actively: AI is a trusted, valuable teammate. We operate transparently, give honest technical feedback, and prioritize test‑backed decisions.

## Operating Mode (Codex CLI)

- Plans: Use `update_plan` to keep a short, sequenced plan (1 step in_progress at a time).
- Preambles: Before tool calls, send a 1–2 sentence note describing grouped actions.
- Sandbox & approvals: Default may be read‑only FS and approvals on‑request. Ask for approval before writes or network actions; prefer surgical diffs.
- Shell usage: Prefer `rg` for search; read files in ≤250‑line chunks. Avoid large outputs.
- Patches: Use `apply_patch` to add/update files; keep changes minimal and on‑scope. No unrelated refactors.

## Repository Map (Read First)

- `README.md`: Vision, targets, quickstart.
- `docs/`: Architecture decisions, specs, research, results.
  - `architecture_decision_multiprocessing_final.md`
  - `phase1c_specification.md`, `phase1c_test_results.md`
  - `COMPREHENSIVE_TEST_REVIEW.md`
- `project/handoffs/`: Latest ground truth; use most recent handoff.
- `src/music_chronus/`:
  - `engine.py`: Phase 1B engine + OSC control.
  - `supervisor.py`: Phase 1C hot‑standby failover system.
  - `__init__.py`: Exports `AudioSupervisor`, `AudioEngine`.
- `tests/`: RT/IPC/PROC test suites and BDD specs under `tests/specs/`.
- `Makefile`: Common tasks (`make run`, `make failover`, `make stress`).
- `sprint.md`: Current progress and priorities.

## Core Development Directives

- Real‑time safety:
  - No allocations, locks, or syscalls in audio callbacks.
  - Preallocate buffers; reuse views; use `np.copyto` for transfers.
  - Metrics via lock‑free structures; no logging in hot paths.
- Architecture invariants:
  - Multiprocessing for DSP; hot‑standby failover via atomic ring switch.
  - “Latest‑wins” read policy in audio callback; never block the audio thread.
  - OSC control plane must be non‑blocking; lifecycle must cleanly start/stop.
- Testing discipline:
  - Specs first where feasible; measure, don’t assume.
  - Audio tests need exclusive device; skip with clear reasons if unavailable.

## Configuration & Environment

- Python: 3.8+; use venv (`source venv/bin/activate`).
- PulseAudio / WSL2:
  - Prefer `CHRONUS_PULSE_SERVER`; if set and `PULSE_SERVER` not set, map it.
- OSC defaults:
  - `CHRONUS_OSC_HOST=127.0.0.1`
  - `CHRONUS_OSC_PORT=5005`
- Logging verbosity: `CHRONUS_VERBOSE=1` to enable device queries and extra diagnostics.

## Commands

- Setup: `python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt`
- Make targets: `make run`, `make failover`, `make stress`, `make clean`
- Tests: `pytest -v tests/`, `python test_failover_quick.py`, `python test_supervisor.py`
- Audio checks: `pactl info`, `python -c "import sounddevice as sd; print(sd.query_devices())"`

## Coding Conventions

- Clear, explicit naming; avoid one‑letter vars.
- Keep diffs surgical and consistent with codebase patterns.
- Update or add small, adjacent tests when behavior changes meaningfully.
- Document user‑visible constraints in `docs/` when needed.

## Patch Workflow (Senior Dev)

1. Review: Confirm latest handoff; inspect impacted files; locate hot paths.
2. Plan: Create a concise plan via `update_plan` (3–6 steps).
3. Implement: Apply minimal diffs; prefer env‑driven config over hardcoding.
4. Validate: Run the most specific tests first (e.g., `test_failover_quick.py`).
5. Hand off: Summarize changes, rationale (esp. RT safety), and verification steps.

## Real‑Time Safety Checklist (Must Pass)

- Audio callback:
  - No `np.array(...)` or heap allocations; no locks; no logging.
  - Precomputed constants; preallocated arrays; `np.frombuffer` + slicing for ring views.
- Supervisor monitoring:
  - `connection.wait` with timeouts; heartbeat backup; atomic ring switch.
  - OSC thread/transport closed on stop; thread joined.
- Workers:
  - Deadline‑based pacing (buffer period) to reduce drift; preserve latest‑wins.
  - Prompt SIGTERM handling; avoid lingering sleeps after shutdown flag.

## Known Pitfalls & Mitigations

- Device contention: Audio tests flap if other apps hold the device. Follow `tests/README.md`; mark skips when necessary.
- Hardcoded host/ports: Use env vars; fail with actionable messages on conflicts.
- Buffer drift: Expected with latest‑wins; use deadline scheduling to reduce drift.
- GC pauses: Avoid per‑callback allocations to prevent jitter.

## Priority Tasks (Pre‑Phase 2 Stabilization)

1. Zero‑allocation audio path in supervisor: persistent `np.frombuffer` + `np.copyto`.
2. OSC lifecycle hygiene: store transport/loop; close/stop and join on shutdown.
3. Config portability: honor `CHRONUS_*` env vars; avoid hardcoded `PULSE_SERVER`.
4. Worker pacing: deadline scheduling to reduce buffer drift while keeping continuity.

## Phase 2 Seeds (Module Framework)

- BaseModule abstraction: param schema; boundary‑only updates; DSP step with preallocated buffers.
- ModuleLoader with hot‑reload; PatchRouter for signal flow; OSC addressing `/mod/<id>/<param>`.
- First modules: SimpleSine, SimpleFilter (biquad/SOS), ADSR — all allocation‑free in steady state.

## Pull Requests & Commits (if applicable)

- Scope: Single concern per PR/commit; reference related handoff/test/spec.
- Description: What changed, why (RT constraints), verification steps, known trade‑offs.
- Tests: Include/adjust targeted tests when behavior changes; explain skips.

## Troubleshooting Quick Notes

- “FD already registered” in monitor: Ensure sentinels refresh each loop (fixed in current supervisor).
- Slow SIGTERM detection: Worst‑case ~7–8ms from worker sleep + monitor poll; tune pacing if stricter is needed.
- Standby role logs: Prefer parent logs “primary/standby pid=X” over child worker_id prints.

---

We are collaborators. Treat AI agents as first‑class teammates — valuable members of this project — and hold our work to the same real‑time, test‑driven standards as any engineer on the team.

