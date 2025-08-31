Feature: IPC-02 - OSC Message Throughput
  As a real-time modular synthesizer
  I need to handle >1000 OSC messages per second
  So that rapid parameter changes and automation work smoothly

  Background:
    Given python-osc with AsyncIOOSCUDPServer
    And UDP buffer sizes tuned to 4MB
    And localhost communication (no network latency)

  Scenario: Sustained throughput test
    Given an OSC server on port 5005
    And a client sending continuously
    When I send 1000 messages per second for 10 seconds
    Then the server should receive at least 9900 messages (99% success)
    And no more than 100 messages should be dropped
    And average processing time should be under 1ms
    And message order should be preserved (sequence numbers)

  Scenario: Burst handling test
    Given an OSC server with 4MB UDP buffer
    When I send 100 messages in a burst (no delay)
    Then all 100 messages should be received
    And processing should complete within 100ms
    And no buffer overflow should occur
    And messages should maintain correct order

  Scenario: Mixed message sizes
    Given an OSC server handling various message types
    When I send a mix of message sizes:
      | Type | Size | Count | Rate |
      | Parameter | 32 bytes | 500 | 50/sec |
      | Pattern | 256 bytes | 300 | 30/sec |
      | Waveform | 4KB | 20 | 2/sec |
    Then all messages should be processed successfully
    And throughput should remain above 1000 msg/sec
    And latency should stay under 5ms for small messages

  Scenario: Bundle efficiency test
    Given an OSC server supporting bundles
    When I send 10 messages per bundle at 100 bundles/sec
    Then effective rate should be 1000 messages/sec
    And bundle parsing overhead should be under 0.5ms
    And all messages in bundle should process atomically

  Scenario: Concurrent load test
    Given an OSC server running
    And 4 CPU-intensive workers running
    When I send 1000 messages/sec for 30 seconds
    Then packet loss should be under 2%
    And P95 latency should be under 10ms
    And CPU usage should remain under 80%

  Scenario: Multiple client test
    Given an OSC server on port 5005
    When 4 clients each send 250 messages/sec
    Then server should handle 1000 total messages/sec
    And messages from all clients should be processed
    And fair scheduling should prevent starvation

  Scenario: UDP buffer overflow detection
    Given default UDP buffer size (213KB)
    When I send 2000 messages/sec sustained
    Then packet loss should be detected via sequence numbers
    And warning should be logged about buffer size
    And recommendation for buffer tuning should be provided

  Scenario: Latency distribution analysis
    Given 1000 messages/sec load
    When I measure round-trip latency for each message
    Then I should calculate:
      | Metric | Target |
      | P50 (median) | <1ms |
      | P95 | <5ms |
      | P99 | <10ms |
      | P99.9 | <20ms |
    And generate latency histogram
    And identify outliers and their causes

  Scenario: AsyncIO vs Threading comparison
    Given both AsyncIOOSCUDPServer and ThreadingOSCUDPServer
    When I test both with 1000 messages/sec
    Then AsyncIO should show:
      | Metric | Advantage |
      | Throughput | Higher |
      | CPU usage | Lower |
      | Memory | Lower |
      | Latency consistency | Better |
    And document performance differences
    And recommend best option for our use case

  Scenario: Recovery from overload
    Given an OSC server at capacity
    When message rate exceeds 2000/sec for 5 seconds
    Then server should:
      | Action | Result |
      | Drop excess messages | Gracefully |
      | Log overload condition | With timestamp |
      | Recover when load reduces | Within 1 second |
      | Maintain service for critical messages | If prioritized |
    And system should not crash or hang