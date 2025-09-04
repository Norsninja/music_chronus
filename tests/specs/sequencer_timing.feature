Feature: Sequencer Timing and Synchronization
  As a musician
  I want precise buffer-aligned timing
  So that my patterns stay in sync and sound tight

  Background:
    Given buffer_period is 11.6ms (512 samples at 44100Hz)
    And the SequencerManager thread is running

  Scenario: Gate events align to buffer boundaries
    Given a sequencer "kick" at 120 BPM with division 4
    And pattern "x...x...x...x..."
    When the sequencer runs for 2 seconds
    Then gates should emit exactly on buffer boundaries:
      | step | expected_buffer | tolerance |
      | 0    | 0              | ±1        |
      | 4    | 43             | ±1        |
      | 8    | 86             | ±1        |
      | 12   | 129            | ±1        |
    And no gates should emit between these boundaries

  Scenario: Gate length respects fraction of step duration
    Given a sequencer "hihat" with gate_length 0.25
    And pattern "xxxx"
    When a gate triggers on step 0
    Then gate ON should emit at buffer 0
    And gate OFF should emit at buffer 11 (25% of 43 buffers)

  Scenario: Tempo change applies on next step boundary
    Given a sequencer "bass" running at 120 BPM
    And currently at step 3 with 5 buffers remaining
    When I send "/seq/bpm bass 140"
    Then the tempo should remain 120 BPM for the next 5 buffers
    And change to 140 BPM starting from step 4
    And no steps should be skipped or duplicated

  Scenario: Multiple sequencers maintain sync
    Given sequencer "kick" with 16 steps at 120 BPM
    And sequencer "hihat" with 32 steps at 120 BPM
    When both start simultaneously
    Then their downbeats (step 0) should align every 32 steps
    And they should maintain phase relationship throughout

  Scenario: Reset aligns all sequencers to global downbeat
    Given three sequencers at different positions:
      | seq_id | current_step |
      | kick   | 7           |
      | snare  | 3           |
      | hihat  | 15          |
    When I send "/seq/reset_all"
    Then all sequencers should be at step 0
    And emit their next events simultaneously