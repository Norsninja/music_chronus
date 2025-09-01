#!/usr/bin/env python3
"""
RT Guard Test: Real-time performance under load
Requirement: Zero underruns with 256 buffer @ 100 msg/s OSC
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
import threading
from pythonosc import udp_client
from music_chronus import AudioSupervisor

def test_rt_guard():
    """Test real-time performance under OSC load"""
    print("RT Guard Test: 100 msg/s OSC Load")
    print("=" * 40)
    
    # Start supervisor
    supervisor = AudioSupervisor()
    
    print("Starting AudioSupervisor...")
    if not supervisor.start():
        print("❌ Failed to start supervisor")
        return False
    
    # Let it stabilize
    time.sleep(2)
    
    # Get initial metrics
    initial_status = supervisor.get_status()
    initial_underruns = initial_status['metrics']['underruns']
    print(f"Initial state: {initial_underruns} underruns")
    
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    # Test parameters
    test_duration = 10.0  # 10 seconds
    msg_per_second = 100
    msg_interval = 1.0 / msg_per_second
    
    print(f"\nSending {msg_per_second} OSC messages/second for {test_duration}s...")
    print("Message pattern: frequency sweeps and gate triggers")
    
    # OSC load generator
    stop_flag = threading.Event()
    messages_sent = 0
    
    def osc_load_generator():
        nonlocal messages_sent
        freq = 220.0
        freq_step = 1.0
        
        while not stop_flag.is_set():
            # Send various OSC messages
            client.send_message("/mod/sine/freq", freq)
            messages_sent += 1
            
            # Sweep frequency
            freq += freq_step
            if freq > 880 or freq < 220:
                freq_step = -freq_step
            
            # Occasionally send other messages
            if messages_sent % 10 == 0:
                client.send_message("/gate/adsr", "on")
                messages_sent += 1
            elif messages_sent % 10 == 5:
                client.send_message("/gate/adsr", "off")
                messages_sent += 1
            
            if messages_sent % 20 == 0:
                client.send_message("/mod/filter/cutoff", 1000 + (messages_sent % 1000))
                messages_sent += 1
            
            time.sleep(msg_interval)
    
    # Start OSC load in thread
    osc_thread = threading.Thread(target=osc_load_generator, daemon=True)
    osc_thread.start()
    
    # Monitor metrics during test
    start_time = time.time()
    sample_interval = 1.0  # Check every second
    underrun_samples = []
    cpu_samples = []
    
    while time.time() - start_time < test_duration:
        time.sleep(sample_interval)
        
        status = supervisor.get_status()
        current_underruns = status['metrics']['underruns']
        underrun_samples.append(current_underruns)
        
        # Note: CPU monitoring would require additional metrics
        # For now, we focus on underruns
    
    # Stop OSC load
    stop_flag.set()
    osc_thread.join(timeout=1.0)
    
    # Get final metrics
    time.sleep(1)  # Let system settle
    final_status = supervisor.get_status()
    final_underruns = final_status['metrics']['underruns']
    total_buffers = final_status['metrics']['buffers_processed']
    failovers = final_status['metrics']['failover_count']
    
    # Calculate results
    new_underruns = final_underruns - initial_underruns
    actual_msg_rate = messages_sent / test_duration
    
    print(f"\nTest Complete:")
    print(f"  Duration: {test_duration}s")
    print(f"  Messages sent: {messages_sent}")
    print(f"  Actual rate: {actual_msg_rate:.1f} msg/s")
    print(f"  Buffers processed: {total_buffers}")
    print(f"  Underruns: {new_underruns}")
    print(f"  Failovers: {failovers}")
    
    # Stop supervisor
    supervisor.stop()
    
    # Evaluate results
    print("\n" + "=" * 40)
    if new_underruns == 0:
        print(f"✅ RT GUARD PASSED: Zero underruns at {actual_msg_rate:.0f} msg/s")
        return True
    else:
        print(f"❌ RT GUARD FAILED: {new_underruns} underruns at {actual_msg_rate:.0f} msg/s")
        return False


def test_burst_load():
    """Test handling of OSC message bursts"""
    print("\nBurst Load Test")
    print("=" * 40)
    
    supervisor = AudioSupervisor()
    
    print("Starting AudioSupervisor...")
    if not supervisor.start():
        print("❌ Failed to start supervisor")
        return False
    
    time.sleep(2)
    
    # Get initial metrics
    initial_status = supervisor.get_status()
    initial_underruns = initial_status['metrics']['underruns']
    
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("Sending burst of 1000 messages...")
    burst_start = time.time()
    
    # Send burst
    for i in range(1000):
        freq = 220 + (i % 660)  # Sweep 220-880Hz
        client.send_message("/mod/sine/freq", freq)
        
        if i % 100 == 0:
            client.send_message("/gate/adsr", "on" if i % 200 == 0 else "off")
    
    burst_time = time.time() - burst_start
    burst_rate = 1000 / burst_time
    
    print(f"Burst complete: {burst_rate:.0f} msg/s")
    
    # Let system process
    time.sleep(2)
    
    # Check results
    final_status = supervisor.get_status()
    new_underruns = final_status['metrics']['underruns'] - initial_underruns
    
    supervisor.stop()
    
    if new_underruns == 0:
        print(f"✅ BURST TEST PASSED: Handled {burst_rate:.0f} msg/s burst")
        return True
    else:
        print(f"❌ BURST TEST FAILED: {new_underruns} underruns during burst")
        return False


if __name__ == "__main__":
    import sys
    
    print("Real-Time Guard Test Suite")
    print("=" * 40)
    print("Testing audio stability under OSC load")
    print("Buffer: 256 samples @ 44.1kHz (~5.8ms)")
    print()
    
    # Check for audio device
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print(f"Audio device available: {sd.default.device}")
    except Exception as e:
        print(f"⚠️  Warning: Audio device check failed: {e}")
        print("Tests may fail if no audio device available")
    
    print()
    
    # Run tests
    try:
        guard_passed = test_rt_guard()
        burst_passed = test_burst_load()
        
        print("\n" + "=" * 40)
        print("FINAL RESULTS")
        print("=" * 40)
        
        if guard_passed and burst_passed:
            print("✅ ALL RT TESTS PASSED")
            print("System maintains real-time performance under load")
            sys.exit(0)
        else:
            print("❌ SOME RT TESTS FAILED")
            print("System may have real-time issues under load")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        print("Note: These tests require an audio device")
        sys.exit(1)