Feature: IPC-04 Event Synchronization
  As a real-time audio system
  I need sub-millisecond event synchronization between processes
  So that musical events happen precisely when scheduled

  Background:
    Given we have a multiprocessing audio architecture
    And worker processes are running DSP operations
    And OSC control messages are being sent
    And target latency is <1ms for event delivery

  Scenario: Primitive microbenchmark under load
    Given 2 DSP workers performing real NumPy operations
    And 100 OSC messages per second background traffic
    And environment variables MKL_NUM_THREADS=1, OMP_NUM_THREADS=1
    When measuring RTT/2 latency for each IPC primitive
    Then socketpair p50 latency is less than 0.10ms  # Python target (C target: 0.05ms)
    And socketpair p95 latency is less than 0.25ms   # Python target (C target: 0.2ms)
    And socketpair p99 latency is less than 0.5ms
    And socketpair jitter is less than 0.1ms
    And socketpair outperforms other primitives

  Scenario: End-to-end control message to audio application
    Given an OSC control message is sent
    And the message updates a parameter value
    When measuring samples until parameter change is audible
    Then the change applies at the next buffer boundary
    And total latency is less than buffer_duration + 0.3ms
    And no mid-buffer discontinuities occur
    And the audio callback never blocks

  Scenario: Ring buffer overflow prevention
    Given a shared SPSC ring buffer for commands
    When sending bursts of control messages
    Then the ring buffer never overflows
    And backpressure policy keeps latest value per parameter
    And dropped events are measured and logged
    And normal operation shows zero drops

  Scenario: Multi-producer event ordering
    Given multiple control sources sending events
    When events target the same audio module
    Then per-producer FIFO order is maintained
    And events are timestamped in control thread
    And merge order is deterministic

  Performance Criteria:
    - Primitive RTT/2 (Python): p50 < 100μs, p95 < 250μs, p99 < 500μs
    - Primitive RTT/2 (C extension): p50 < 50μs, p95 < 200μs, p99 < 500μs
    - End-to-end latency: < buffer_duration + 0.3ms
    - Audio callback: Zero blocking, zero syscalls
    - Ring buffer: Zero overflows under normal load
    - Event ordering: Strict FIFO per producer
    
  Implementation Notes:
    - ACK pattern used in tests for RTT measurement, not required in production
    - Queue-based IPC excluded from hot path due to blocking nature
    - Targets account for Python function overhead (~10-20μs per call)