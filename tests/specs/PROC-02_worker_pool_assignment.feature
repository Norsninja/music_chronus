Feature: PROC-02 - Worker Pool Task Assignment
  As a real-time audio system
  I need to assign audio processing tasks to pre-warmed workers
  So that module creation and audio processing happens within 10ms

  Background:
    Given a system with at least 4 CPU cores
    And shared memory buffers pre-allocated before pool creation
    And workers with numpy, scipy.signal, and pythonosc pre-imported

  Scenario: Cold pool creation and warmup
    Given no existing worker pool
    When I create a pool with 8 workers using forkserver
    Then pool creation should complete within 3 seconds
    And all workers should have libraries pre-imported
    And memory footprint per worker should be 50-100MB

  Scenario: First task assignment (cold)
    Given a newly created worker pool
    When I assign the first audio processing task
    Then assignment should complete within 10ms
    And the task should execute successfully
    And no new process should be spawned

  Scenario: Warm task assignment
    Given a worker pool that has processed at least 10 tasks
    When I assign a new audio processing task
    Then assignment should complete within 2ms
    And the task should execute successfully
    And worker memory should not have grown significantly

  Scenario: Concurrent task assignment
    Given a warmed-up worker pool with 8 workers
    When I assign 8 concurrent audio tasks
    Then all tasks should be assigned within 10ms total
    And all tasks should execute in parallel
    And no task should wait for another to complete

  Scenario: Shared memory access from workers
    Given pre-allocated shared memory audio buffers
    And a worker pool initialized with buffer references
    When a worker writes audio data to shared buffer
    Then the data should be immediately visible to parent process
    And there should be zero memory copy overhead
    And access time should be under 0.1ms

  Scenario: Worker persistence under load
    Given a worker pool with maxtasksperchild=500
    When I process 400 sequential tasks
    Then no workers should respawn during execution
    And task assignment should remain under 2ms
    And total memory growth should be under 200MB

  Scenario: Memory leak detection
    Given a worker pool with maxtasksperchild=None
    When I process 1000 audio tasks with numpy operations
    Then I should measure memory growth per worker
    And memory growth rate should be documented
    And a warning should be raised if growth exceeds 1MB/100 tasks

  Scenario: Worker crash recovery
    Given a healthy worker pool
    When a worker crashes during task execution
    Then the pool should detect the failure within 100ms
    And the pool should remain functional
    And subsequent tasks should complete successfully
    And a new worker should be spawned if needed

  Scenario: Pool saturation handling
    Given a worker pool with 8 workers
    When I submit 16 tasks simultaneously
    Then first 8 tasks should start within 10ms
    And remaining tasks should queue
    And queued tasks should start as workers become available
    And no deadlock should occur

  Scenario: Resource cleanup on shutdown
    Given a worker pool processing audio
    When I terminate the pool
    Then all workers should exit cleanly
    And shared memory should be released
    And no zombie processes should remain
    And cleanup should complete within 1 second