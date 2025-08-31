Feature: IPC-01 - OSC Message Latency Between Processes
  As a modular synthesizer system
  I want OSC messages to travel quickly between modules
  So that control signals feel instantaneous to musicians

  Background:
    Given two separate Python processes are running
    And both processes use python-osc library
    And they communicate over localhost (127.0.0.1)
    And UDP transport is used (not TCP)

  Scenario: Single OSC message latency
    Given Process A is running an OSC server on port 5000
    And Process B is ready to send OSC messages
    When Process B sends an OSC message "/test/ping" with timestamp
    And Process A receives the message and sends back "/test/pong"
    Then the round-trip time should be less than 5ms
    And the one-way latency should be less than 2.5ms

  Scenario: Burst of OSC messages
    Given the OSC server and client are connected
    When 100 messages are sent in rapid succession
    Then all messages should arrive in order
    And average latency should remain under 5ms
    And no messages should be dropped

  Scenario: Concurrent OSC communication
    Given 4 module processes are running (like VCO, VCF, LFO, ADSR)
    When each sends 10 messages to the others simultaneously
    Then all messages should arrive within 10ms
    And no race conditions should occur

  # Why These Requirements:
  # - Musical control needs to feel "instant" to humans
  # - 5ms for control is imperceptible when combined with 6ms audio
  # - Multiple modules will be sending messages simultaneously
  # - We're using UDP for speed over reliability

  # Test Implementation Notes:
  # - Use multiprocessing to create truly separate processes
  # - Use time.perf_counter_ns() for nanosecond precision
  # - Test both directions (bidirectional communication)
  # - Include message payload size variations

  # Acceptance Criteria:
  # - Average latency: <2ms (ideal)
  # - Maximum latency: <5ms (required)
  # - Message loss: 0% on localhost
  # - Throughput: >1000 messages/second

  # Expected Results:
  # - Localhost UDP should give us <1ms typically
  # - Python overhead might add 1-2ms
  # - Total should be well under our 5ms target