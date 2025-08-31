Feature: RT-01 - Audio Server Round-Trip Latency
  As a real-time music system
  I want to achieve minimal latency from command to audio output
  So that musicians can perform without perceptible delay

  Background:
    Given the WSL2 PulseAudio bridge is configured at tcp:172.21.240.1:4713
    And rtmixer is installed with sounddevice backend
    And the system sample rate is 44100 Hz
    And the buffer size is 256 samples (5.8ms theoretical minimum)

  Scenario: Measure baseline audio output latency
    Given an rtmixer Audio Server process is running
    And the server is configured with a single output channel
    When a trigger command is sent at timestamp T0
    And the trigger generates a 1ms click at 1kHz
    Then audio output should begin within 20ms of T0
    And the measurement should be repeatable within ±2ms variance

  Scenario: Sustained audio without dropouts
    Given the Audio Server is producing a continuous 440Hz sine wave
    When the system runs for 60 seconds
    Then there should be 0 buffer underruns
    And the audio callback should never block
    And CPU usage should remain below 25% for the audio process

  Scenario: Command-to-audio response time
    Given the Audio Server is idle
    When an OSC message "/test/beep 1000" is sent at time T0
    Then a 1kHz beep should be audible at time T0 + latency
    And latency should be less than 20ms
    And this should hold true for 100 consecutive commands

  # Test Implementation Notes:
  # - Use high-precision timers (time.perf_counter_ns())
  # - Record audio loopback for objective measurement
  # - Test both with and without other system load
  # - Document WSL2-specific overhead separately

  # Acceptance Criteria:
  # - Maximum acceptable latency: 20ms
  # - Target latency: <10ms
  # - Required reliability: 99.9% of commands meet latency target
  # - Zero tolerance for audio dropouts during normal operation

  # Measurement Method:
  # 1. Send trigger via OSC with timestamp
  # 2. Generate distinctive audio marker (click/beep)
  # 3. Record output via loopback
  # 4. Analyze recording to find marker onset
  # 5. Calculate time difference

  # Known Constraints:
  # - WSL2 adds ~5-10ms overhead vs native Linux
  # - PulseAudio TCP bridge adds ~2-5ms
  # - Windows audio subsystem adds ~5-10ms
  # - Total system overhead: ~12-25ms expected

  # Failure Conditions:
  # - Latency >20ms = FAIL (not suitable for live performance)
  # - Any audio dropout = FAIL (breaks musical flow)
  # - Variance >5ms = FAIL (unpredictable timing)