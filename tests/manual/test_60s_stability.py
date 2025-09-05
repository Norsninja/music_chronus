#!/usr/bin/env python3
"""
60-Second Stability Test for Windows Supervisor
As required by Senior Dev for Phase 1 validation
"""

from pythonosc import udp_client
import time
import datetime

def run_60s_test():
    """Run 60-second stability test with OSC commands"""
    
    print("\n" + "="*60)
    print("60-SECOND STABILITY TEST")
    print(f"Started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    # Create OSC client
    client = udp_client.SimpleUDPClient('127.0.0.1', 5005)
    
    # Initial setup
    print("Initializing synthesizer...")
    client.send_message('/frequency', 440.0)
    client.send_message('/amplitude', 0.3)
    client.send_message('/gate', 1.0)
    
    start_time = time.time()
    test_duration = 60  # seconds
    
    # Test pattern: cycle through frequencies
    frequencies = [220, 440, 880, 440, 330, 440, 550, 440]
    freq_index = 0
    
    print(f"Running test for {test_duration} seconds...")
    print("Progress: ", end="", flush=True)
    
    last_print = 0
    while time.time() - start_time < test_duration:
        elapsed = time.time() - start_time
        
        # Print progress dots
        if int(elapsed) % 10 == 0 and int(elapsed) > last_print:
            print(f"\n  [{int(elapsed)}/{test_duration}s]", end=" ", flush=True)
            last_print = int(elapsed)
        elif int(elapsed) % 2 == 0 and int(elapsed) > last_print:
            print(".", end="", flush=True)
            last_print = int(elapsed)
        
        # Change frequency every 5 seconds
        if int(elapsed) % 5 == 0 and elapsed - int(elapsed) < 0.1:
            new_freq = frequencies[freq_index % len(frequencies)]
            client.send_message('/frequency', float(new_freq))
            freq_index += 1
        
        # Send occasional amplitude changes
        if int(elapsed) % 7 == 0 and elapsed - int(elapsed) < 0.1:
            amp = 0.2 + (0.3 * (freq_index % 3) / 2)
            client.send_message('/amplitude', amp)
        
        time.sleep(0.1)
    
    # Turn off
    print(f"\n\nTest duration completed: {time.time() - start_time:.1f} seconds")
    print("Turning off synthesizer...")
    client.send_message('/gate', 0.0)
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("Check supervisor output for final metrics")
    print("="*60)

if __name__ == "__main__":
    run_60s_test()
    print("\n✅ 60-second stability test completed")
    print("Please check supervisor metrics for:")
    print("  - Total callbacks (should be ~5600)")
    print("  - Underruns (should be 0)")
    print("  - Callback timing (min/mean/max)")
    print("\nPress 'r' in supervisor window to record 10s WAV")
    print("Press 'q' in supervisor window to quit")