Feature: RT-03 GIL Bypass Verification
  As a synthesizer architect
  I need to verify NumPy operations bypass the GIL
  So that I can choose between threading and multiprocessing for DSP

  Background:
    Given we have a system with multiple CPU cores
    And NumPy/SciPy are available for DSP operations
    And we need <20ms latency for real-time audio

  Scenario: Verify NumPy releases GIL for array operations
    Given I have NumPy arrays of size 4096 samples
    When I perform FFT operations in multiple threads
    Then the operations should run in parallel
    And achieve speedup proportional to CPU cores (up to memory bandwidth limit)
    And threading should outperform multiprocessing for these operations

  Scenario: Measure actual parallelism with threading
    Given I spawn 8 threads performing NumPy DSP operations
    When I measure CPU utilization and timing
    Then I should see 2-4 threads running simultaneously (memory bandwidth limited)
    And total time should be less than sequential execution time / 2
    And no significant GIL contention should be observed

  Scenario: Compare threading vs multiprocessing for DSP workloads
    Given identical DSP operations (FFT, filtering, convolution)
    When I run them with both threading and multiprocessing
    Then threading should have lower memory usage (shared arrays)
    And threading should have faster parameter updates (no serialization)
    And threading should have lower latency (no IPC overhead)
    But multiprocessing should provide better fault isolation

  Scenario: Identify memory bandwidth bottleneck
    Given I increase the number of parallel workers from 1 to 8
    When measuring throughput for memory-intensive operations
    Then throughput should plateau at 2-3 workers
    And this limit should be similar for both threading and multiprocessing
    And CPU utilization should be less than 100% when bottlenecked

  Scenario: Test hybrid architecture feasibility
    Given a process with internal thread pool for DSP
    When I run multiple DSP operations within the thread pool
    Then threads should achieve parallel execution via GIL release
    And the process boundary should provide fault isolation
    And total latency should remain under 20ms target

  Performance Criteria:
    - Threading speedup: >2x for 4+ cores with NumPy operations
    - Memory usage: Threading should use <25% of multiprocessing memory
    - Parameter update latency: <0.1ms for threading, >1ms for multiprocessing
    - Fault isolation: Process crash should not affect other processes
    - Memory bandwidth ceiling: 2-3 parallel operations maximum