Feature: Windows WASAPI Audio Stability
  As a Windows user of Music Chronus
  I want stable audio output with WASAPI
  So that I can make music without dropouts or glitches

  Background:
    Given Windows environment with WASAPI support
    And supervisor_windows.py is available
    And AB13X USB Audio device at index 17

  Scenario: 60-second stability at BUFFER_SIZE=512
    Given BUFFER_SIZE is set to 512
    And SAMPLE_RATE is set to 48000
    When I run the supervisor for 60 seconds
    And send OSC commands for frequency, amplitude and gate
    Then the audio should play without underruns
    And callback timing min should be less than 1ms
    And callback timing mean should be less than 2ms
    And callback timing max should be less than 5ms
    And total underruns should be 0
    And worker heartbeats should remain active
    And a WAV file should be recorded successfully

  Scenario: Device logging details
    Given the supervisor starts
    When audio device is selected
    Then the following should be logged:
      | Field       | Expected Value            |
      | Device Name | AB13X USB Audio           |
      | Device Index| 17                        |
      | API         | Windows WASAPI            |
      | Sample Rate | 48000 Hz                  |
      | Buffer Size | 512 samples               |
      | Mode        | Shared or Exclusive       |

  Scenario: OSC lifecycle management
    Given the supervisor is running
    When I send a shutdown signal
    Then the OSC server should stop gracefully
    And the OSC thread should be joined
    And transport and loop should be properly closed
    And no hanging threads should remain

  Scenario: Attempt BUFFER_SIZE=256
    Given BUFFER_SIZE is set to 256
    And SAMPLE_RATE is set to 48000
    When I run the supervisor for 30 seconds
    Then I should document the outcome:
      | Metric      | Acceptable Range          |
      | Underruns   | Document if > 0           |
      | Latency     | 5.3ms theoretical         |
      | Stability   | Note any audio artifacts  |
    And recommendation should be made for production buffer size

  Scenario: Metrics collection
    Given the supervisor is running with CHRONUS_METRICS=1
    When 5 seconds have elapsed
    Then performance metrics should be printed including:
      | Metric                | Description               |
      | Callbacks            | Total callback count       |
      | Buffers Processed    | Successfully output buffers|
      | Underruns            | Total underrun count       |
      | Callback Min Time    | Minimum callback duration  |
      | Callback Mean Time   | Average callback duration  |
      | Callback Max Time    | Maximum callback duration  |
      | Worker Heartbeats    | Primary and standby counts |

  Scenario: WAV recording artifact
    Given the supervisor is running
    When recording is triggered for 10 seconds
    Then a WAV file should be saved in music_chronus/recordings/
    And filename should contain:
      | Component | Example                |
      | Prefix    | win_wasapi_            |
      | Device ID | dev17_                 |
      | Sample Rate| 48000hz_              |
      | Buffer Size| 512buf_               |
      | Timestamp | 20250905_093000.wav   |
    And the WAV file should be playable
    And duration should match recording time