Feature: RT-04 Memory Allocation Detection
  As a real-time audio system
  I need to ensure zero memory allocation in audio callbacks
  So that audio latency remains deterministic under 20ms

  Background:
    Given we have a real-time audio processing system
    And audio buffers are pre-allocated before processing
    And worker processes are initialized with NumPy/SciPy
    And target latency is <20ms

  Scenario: Verify no Python allocations during audio processing
    Given tracemalloc is monitoring memory allocations
    And garbage collection is disabled during measurement
    When audio processes for 10 seconds continuously
    Then no new Python objects are allocated in audio path
    And memory usage delta is less than 1KB
    And no allocations larger than 1KB are detected

  Scenario: Monitor system-level memory calls
    Given we can monitor system calls with psutil
    When audio processing runs for 10 seconds
    Then memory usage remains flat (±1MB variation)
    And no memory growth trend is observed
    And RSS memory stays within 2% of baseline

  Scenario: Test NumPy array operations are allocation-free
    Given pre-allocated NumPy arrays for audio buffers
    When performing DSP operations (FFT, filter, convolution)
    Then all operations use pre-allocated output buffers
    And no temporary arrays are created
    And array memory addresses remain constant

  Scenario: Verify garbage collection doesn't trigger
    Given GC is enabled but monitored
    When processing audio for 30 seconds
    Then GC collection count remains at zero
    And no GC pauses are detected
    And reference counts remain stable

  Scenario: Test ring buffer memory stability
    Given a lock-free ring buffer for audio
    When reading and writing 1000 buffers
    Then no memory allocations occur
    And buffer pointers are reused correctly
    And memory usage remains constant

  Performance Criteria:
    - Zero allocations in audio callback path
    - Memory usage variance <1MB during processing
    - No GC triggers during audio processing
    - All DSP uses pre-allocated buffers
    - Memory addresses remain constant for audio arrays