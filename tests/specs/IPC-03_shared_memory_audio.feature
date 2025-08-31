Feature: IPC-03 - Shared Memory Audio Transfer
  As a modular synthesizer system
  I want to transfer audio between processes with zero-copy efficiency
  So that multiple modules can generate audio without performance penalties

  Background:
    Given two separate Python processes (producer and consumer)
    And a shared memory buffer for audio data
    And NumPy arrays for audio manipulation
    And synchronization via multiprocessing.Event or similar

  Scenario: Zero-copy audio transfer verification
    Given a producer process generating audio at 44100Hz
    And a consumer process reading that audio
    When 1 second of audio (44100 samples) is transferred
    Then the data should be identical (no corruption)
    And no memory copying should occur (zero-copy)
    And transfer overhead should be <0.1ms per buffer

  Scenario: Continuous audio streaming
    Given a producer generating continuous sine wave
    And a consumer reading in real-time
    When streaming for 10 seconds
    Then no buffer underruns should occur
    And no data corruption should occur
    And CPU usage should remain low (<10% overhead)

  Scenario: Multi-channel audio transfer
    Given 4 channels of audio (like 4 oscillators)
    When all channels write to shared memory simultaneously
    Then all channels should transfer correctly
    And no race conditions should occur
    And total overhead should scale linearly

  # Implementation Requirements:
  # - Use mp.Array(ctypes.c_float, size) for shared memory
  # - Use np.frombuffer() for zero-copy NumPy access
  # - Test both with and without locking
  # - Measure actual memory usage to verify zero-copy

  # Acceptance Criteria:
  # - Zero data corruption
  # - Transfer overhead: <0.1ms per 256-sample buffer
  # - Memory usage: No duplication (verify with memory profiler)
  # - Synchronization overhead: <0.01ms

  # Expected Results:
  # - Shared memory should be essentially instant
  # - Synchronization (Event/Semaphore) might add tiny overhead
  # - Should easily handle multiple audio streams