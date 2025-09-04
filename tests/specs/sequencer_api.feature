Feature: Sequencer API Behavior
  As a musician (human or AI)
  I want to control rhythmic patterns via OSC commands
  So that I can create evolving, synchronized musical sequences

  Background:
    Given the supervisor is running with SequencerManager
    And the audio engine is initialized at 44100Hz with 512-sample buffers

  Scenario: Create and configure a basic sequencer
    When I send OSC command "/seq/create kick"
    Then a sequencer with id "kick" should exist
    And it should have default values:
      | property  | value |
      | bpm       | 120   |
      | steps     | 16    |
      | division  | 4     |
      | pattern   | x...............  |
    
  Scenario: Configure sequencer parameters
    Given a sequencer "kick" exists
    When I send OSC command "/seq/config kick 140 8 16"
    Then the sequencer "kick" should have:
      | property  | value |
      | bpm       | 140   |
      | steps     | 8     |
      | division  | 16    |

  Scenario: Set pattern string
    Given a sequencer "kick" exists
    When I send OSC command "/seq/pattern kick x...x...x...x..."
    Then the pattern should parse to [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]
    
  Scenario: Assign sequencer to module parameter
    Given a sequencer "kick" exists
    And a module "adsr" exists in the patch
    When I send OSC command "/seq/assign kick gate adsr"
    Then sequencer "kick" should target module "adsr" parameter "gate"

  Scenario: Start and stop sequencing
    Given a sequencer "kick" with pattern "x...x...x...x..."
    And it is assigned to "adsr" gate
    When I send OSC command "/seq/start kick"
    Then the sequencer should emit gate events on steps 0, 4, 8, 12
    When I send OSC command "/seq/stop kick"
    Then no further events should be emitted

  Scenario: Reset sequencer to step 0
    Given a sequencer "kick" is playing at step 7
    When I send OSC command "/seq/reset kick"
    Then the current_step should be 0
    And the next gate should emit on step 0 of the pattern