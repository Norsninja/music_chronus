Feature: Pattern Parsing and Manipulation
  As a musician
  I want expressive pattern notation
  So that I can quickly create complex rhythms

  Scenario: Parse basic pattern string
    Given a pattern string "x...x...x...x..."
    When parsed for gate events
    Then it should produce boolean array [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]

  Scenario: Parse pattern with accents
    Given a pattern string "X..x..X..x..X..."
    When parsed with velocity support
    Then it should produce:
      | step | gate | velocity |
      | 0    | 1    | 127      |
      | 3    | 1    | 64       |
      | 6    | 1    | 127      |
      | 9    | 1    | 64       |
      | 12   | 1    | 127      |

  Scenario: Parse parameter lane values
    Given a param lane string "60,0,0,62,0,0,64,0,0,65,0,0,67,0,0,0"
    When parsed as MIDI notes
    Then it should map to frequencies:
      | step | value  |
      | 0    | 261.63 |
      | 3    | 293.66 |
      | 6    | 329.63 |
      | 9    | 349.23 |
      | 12   | 392.00 |

  Scenario: Euclidean rhythm generation
    Given a request for euclidean(5, 16)
    When the pattern is generated
    Then it should produce "x..x..x.x..x...."
    And have exactly 5 triggers distributed across 16 steps

  Scenario: Pattern rotation
    Given a pattern "x...x...x...x..."
    When rotated by 2 steps
    Then it should become "..x...x...x...x."

  Scenario: Pattern length change preserves content
    Given a 16-step pattern "x...x...x...x..."
    When length is changed to 8
    Then pattern should be "x...x..."
    When length is changed back to 16
    Then missing steps should be filled with rests "x...x..........."]