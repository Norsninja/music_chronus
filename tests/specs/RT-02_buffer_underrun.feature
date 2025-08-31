Feature: RT-02 - Buffer Underrun Detection and Prevention
  As a real-time audio system
  I need to sustain continuous audio playback without dropouts
  So that live music performance is reliable and glitch-free

  Background:
    Given rtmixer is configured with appropriate buffer sizes
    And the system has real-time audio capabilities
    And garbage collection can be controlled

  Scenario: Clean 60-second playback
    Given a buffer size of 256 frames
    And a sample rate of 44100 Hz
    When I generate a continuous sine wave for 60 seconds
    And monitor rtmixer statistics every 100ms
    Then output_underflow count should be 0
    And audio playback should not stop
    And all buffers should be delivered on time

  Scenario: Playback under normal load
    Given a buffer size of 256 frames
    And normal system activity (file I/O, network)
    When I play continuous audio for 60 seconds
    And perform typical synthesizer operations:
      | Operation | Frequency |
      | Parameter changes | 10 per second |
      | Module creation | 1 per second |
      | Pattern updates | 2 per second |
    Then underrun count should be less than 5
    And no audible glitches should occur
    And recovery should be automatic

  Scenario: Stress test with GC pressure
    Given a buffer size of 256 frames
    And garbage collection enabled
    When I play continuous audio for 60 seconds
    And randomly trigger GC every 5-10 seconds
    And allocate/deallocate large objects
    Then underrun count should be less than 10
    And underruns should not cluster (max 2 consecutive)
    And system should remain responsive

  Scenario: Multiple buffer size validation
    Given sample rate of 44100 Hz
    When I test each buffer size:
      | Buffer Size | Max Underruns | Latency Target |
      | 128 frames  | 20           | 2.9ms         |
      | 256 frames  | 5            | 5.8ms         |
      | 512 frames  | 1            | 11.6ms        |
    Then each configuration should meet its underrun target
    And latency measurements should match targets ±10%
    And 512-frame buffer should be rock-solid

  Scenario: Concurrent DSP load test
    Given a buffer size of 256 frames
    And 4 worker processes running DSP algorithms
    When I play continuous audio for 60 seconds
    And workers process simulated module workloads:
      | Module Type | Processing Time |
      | VCO        | 0.5ms          |
      | Filter     | 1.0ms          |
      | Reverb     | 2.0ms          |
      | Delay      | 0.8ms          |
    Then total underrun count should be less than 10
    And workers should not block audio thread
    And shared memory transfers should remain fast

  Scenario: System configuration validation
    Given the Linux audio environment
    When I check system configuration
    Then the following should be verified:
      | Configuration | Expected State |
      | RT priorities available | Yes |
      | Memory locking allowed | Yes |
      | Audio group membership | Yes |
      | CPU governor | performance |
    And warnings should be logged for suboptimal configs
    And test should proceed with degraded expectations if needed

  Scenario: Underrun recovery behavior
    Given a buffer size of 256 frames
    When an underrun occurs during playback
    Then rtmixer should report it via fetch_and_reset_stats()
    And the underrun timestamp should be logged
    And audio should continue without manual intervention
    And subsequent buffers should play normally

  Scenario: Memory allocation stress
    Given a buffer size of 256 frames
    And audio process with disabled GC
    When I play audio for 60 seconds
    And continuously allocate numpy arrays (100MB/sec)
    And free them after random delays
    Then underrun count should be less than 15
    And memory usage should remain bounded
    And no memory leaks should occur

  Scenario: Import delay protection
    Given audio is playing continuously
    When a new module requires library import
    Then the import should happen in a separate process
    And audio thread should never perform imports
    And underrun count should remain 0
    And module should initialize within 100ms

  Scenario: Statistical analysis of underruns
    Given 60 seconds of audio with induced underruns
    When I analyze the underrun pattern
    Then I should measure:
      | Metric | Calculation |
      | Total count | Sum of all underruns |
      | Mean interval | Average time between underruns |
      | Clustering coefficient | Consecutive underrun ratio |
      | Recovery time | Time to stable playback |
    And generate a distribution histogram
    And identify systematic vs random patterns