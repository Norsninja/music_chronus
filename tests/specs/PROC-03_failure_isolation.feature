Feature: PROC-03 Process Failure Isolation
  As a real-time audio system
  I need robust worker crash isolation and recovery
  So that music continues uninterrupted when DSP modules fail

  Background:
    Given we have a multiprocessing worker pool architecture
    And shared memory segments for audio/control data
    And hot-standby executor for instant failover
    And target recovery times <10ms failover, <500ms rebuild

  Scenario: Worker crash with hot-standby failover
    Given a primary ProcessPoolExecutor with 4 workers
    And a pre-warmed standby ProcessPoolExecutor
    And active DSP processing on 2 workers
    And OSC control traffic at 100 msg/sec
    When a worker crashes via SIGKILL
    Then heartbeat detection triggers within 10ms p95
    And failover to standby executor within 10ms
    And new tasks are accepted immediately
    And background rebuild completes within 500ms
    And no audio underruns occur
    And control latency stays within IPC-04 bounds

  Scenario: Multiple crash types and recovery
    Given the hot-standby system is active
    When testing crash scenarios:
      | crash_type         | method           | detection_time |
      | unhandled_exception| raise Exception  | <10ms         |
      | abrupt_exit       | os._exit(1)      | <10ms         |
      | hard_kill         | SIGKILL          | <10ms         |
    Then each crash is isolated to single worker
    And other workers continue processing
    And shared memory remains uncorrupted
    And telemetry logs the incident

  Scenario: Shared memory cleanup after crash
    Given a centralized SHM registry at /tmp/chronus_shm_registry.json
    And all segments prefixed with "chronus_"
    And registry tracks: name, size, owner_pid, created_ts
    When a worker crashes leaving segments orphaned
    Then the supervisor detects orphaned segments
    And calls SharedMemory(name).unlink() for each
    And updates the registry atomically
    And verifies /dev/shm has no leaks

  Scenario: Performance during failure cascade
    Given the system is under load
    When inducing 3 crashes over 60 seconds
    Then zero audio dropouts occur
    And p95 control latency remains <0.25ms
    And all crashes recover successfully
    And health metrics show:
      | metric                | value    |
      | total_crashes        | 3        |
      | replacements_created | 3        |
      | standby_ready       | true     |
      | leaked_segments     | 0        |

  Performance Criteria:
    - Detection: p95 < 10ms via heartbeat, p99 < 20ms
    - Failover: New tasks routed within 10ms
    - Recovery: Standby rebuilt < 500ms
    - Memory: Zero SHM leaks verified
    - Continuity: No audio underruns during crashes
    - Control: p95 latency within IPC-04 bounds

  Implementation Notes:
    - Heartbeat via no-op futures with 5ms timeout
    - BrokenProcessPool triggers immediate failover
    - Forkserver preload for faster recovery
    - MKL_NUM_THREADS=1, OMP_NUM_THREADS=1 in workers
    - Atomic registry updates via write-temp-then-rename