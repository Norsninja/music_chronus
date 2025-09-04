Feature: Sequencer Integration with Audio System
  As a musician
  I want the sequencer to work seamlessly with the audio engine
  So that I can combine sequencing with live patching

  Background:
    Given the supervisor is running with router mode enabled
    And a patch exists: sine -> adsr -> filter -> output
    And recording is enabled to capture output

  Scenario: Sequencing during patch commit
    Given a sequencer "melody" is playing a pattern
    When I commit a new patch configuration
    Then both slots should receive identical sequencer events
    And no gates should be lost during the swap
    And the recording should have no pops or glitches

  Scenario: Standby slot mirrors sequencer state
    Given slot 0 is primary and slot 1 is standby
    And sequencer "kick" is emitting gates
    When I observe command distribution
    Then both slots should receive:
      | command_type | count_per_second |
      | gate_on      | 2               |
      | gate_off     | 2               |
    And slot states should remain synchronized

  Scenario: RT metrics remain stable during sequencing
    Given baseline metrics without sequencing:
      | metric     | baseline |
      | none_reads | ≤0.1%   |
      | occ0_1k    | ≈0      |
      | underflows | 0       |
    When running 3 sequencers simultaneously for 60 seconds
    Then metrics should remain within tolerance:
      | metric     | maximum  |
      | none_reads | ≤0.5%   |
      | occ0_1k    | ≤1      |
      | underflows | 0       |

  Scenario: Pattern updates are atomic
    Given sequencer "bass" playing pattern "x...x...x...x..."
    And currently between steps 2 and 3
    When I update pattern to "xxxx xxxx xxxx xxxx"
    Then the current cycle should complete with old pattern
    And the next cycle should use the new pattern entirely
    And no partial patterns should ever play

  Scenario: Recording captures sequenced audio cleanly
    Given sequencer "kick" at 120 BPM with pattern "x...x...x...x..."
    When recording for 10 seconds
    Then the WAV file should contain:
      | measurement           | expected              |
      | transient_count      | 20 (±1)              |
      | transient_spacing    | 500ms (±11.6ms)      |
      | zero_crossing_pops   | 0                    |
      | frequency_content    | matches sine module  |