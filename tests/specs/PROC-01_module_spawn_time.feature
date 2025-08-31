Feature: PROC-01 - Module Process Spawn Time
  As a live music performance system
  I want to create synthesizer modules quickly
  So that musicians can patch modules in real-time without interrupting flow

  Background:
    Given the system uses Python multiprocessing
    And modules require numpy, scipy, and OSC libraries
    And we need to support dynamic module creation
    And target is <100ms per module for live performance

  Scenario: Cold spawn time (first module)
    Given no processes are pre-warmed
    When creating a VCO module process
    Then spawn time should be <100ms
    And the module should be fully functional
    And libraries should be loaded

  Scenario: Warm spawn with process pool
    Given a process pool with 4 pre-warmed workers
    And workers have pre-imported audio libraries
    When assigning a new module to a worker
    Then assignment time should be <10ms
    And no library import overhead should occur

  Scenario: Multiple module creation
    Given a user creating a typical patch
    When spawning 5 modules (VCO, VCF, VCA, LFO, ADSR)
    Then total time should be <500ms
    And all modules should run in parallel

  # Research Findings Applied:
  # - Fork: ~2ms (fast but unsafe with threads)
  # - Spawn: ~42ms (safe but slower)
  # - Forkserver: ~10-20ms (good compromise)
  # - NumPy import: 200-400ms first time
  # - Process pool assignment: <10ms

  # Implementation Strategy:
  # 1. Test both spawn methods and process pools
  # 2. Measure cold start vs warm pool
  # 3. Compare fork vs spawn vs forkserver
  # 4. Test with real module initialization

  # Acceptance Criteria:
  # - Cold spawn: <100ms (including library imports)
  # - Warm pool assignment: <10ms
  # - No crashes or deadlocks
  # - Consistent performance across runs

  # Expected Outcomes:
  # - Process pools will be required for <100ms
  # - Forkserver likely best for Linux
  # - Pre-import strategy essential