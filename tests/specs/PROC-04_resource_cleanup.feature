Feature: PROC-04 Resource Cleanup
  As a long-running audio system
  I need reliable resource cleanup on teardown and abnormal exits
  So that the system can run indefinitely without resource leaks

  Background:
    Given we have ProcessPoolExecutor for worker management
    And shared memory segments with JSON registry
    And OSC sockets for control messages
    And target re-init time <1.5s

  Scenario: Clean teardown and re-initialization cycles
    Given a fully initialized audio system with:
      | component         | count |
      | worker_processes  | 4     |
      | shm_segments     | 8     |
      | osc_sockets      | 2     |
      | file_descriptors | ~50   |
    When performing 50 teardown/re-init cycles
    Then each teardown releases all resources:
      | resource         | validation              |
      | processes        | psutil shows terminated |
      | shm_segments     | /dev/shm count unchanged|
      | sockets          | netstat shows closed    |
      | file_descriptors | lsof shows no growth    |
    And each re-init completes within 1.5 seconds
    And no resource leaks accumulate over cycles

  Scenario: SIGKILL cleanup with registry recovery
    Given workers with active shared memory segments
    And JSON registry tracking all segments
    When a worker is killed with SIGKILL
    Then the registry detects orphaned segments
    And explicitly calls unlink() on each orphan
    And /dev/shm shows zero chronus_* segments leaked
    And registry is updated atomically

  Scenario: File descriptor leak prevention
    Given baseline FD count for the process
    When running 50 create/destroy cycles of:
      | resource_type    | operations           |
      | executor        | create, submit, shutdown |
      | shared_memory   | create, write, unlink   |
      | osc_socket      | bind, send, close       |
    Then FD count returns to baseline ±5
    And no zombie processes exist
    And no socket TIME_WAIT accumulation

  Scenario: Memory growth detection
    Given initial RSS memory usage
    When performing 100 allocation/cleanup cycles
    Then RSS memory stays within initial ±10%
    And no monotonic growth trend observed
    And Python gc.collect() shows stable object counts

  Performance Criteria:
    - Teardown time: <500ms for complete cleanup
    - Re-init time: <1.5s to operational state
    - Zero leaks: No resources leaked after 50 cycles
    - FD stability: Count within ±5 of baseline
    - Memory stability: RSS within ±10% over time

  Implementation Notes:
    - Use psutil for process and memory monitoring
    - Check /dev/shm directly for segment leaks
    - Track FDs via /proc/[pid]/fd or lsof
    - Registry cleanup must be atomic (write-temp-rename)
    - Test both graceful shutdown and SIGKILL scenarios