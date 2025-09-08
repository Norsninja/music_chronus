#!/usr/bin/env python3
"""Test Phase 2 visualizer features"""

from pythonosc import udp_client
import time

def test_visualizer():
    c = udp_client.SimpleUDPClient('127.0.0.1', 5005)
    
    print("Testing Phase 2 visualizer features...")
    
    # Test 1: Single voice with varying frequencies
    print("\n1. Testing voice levels - sweeping frequencies")
    for freq in [110, 220, 440, 880, 1760]:
        c.send_message('/mod/voice1/freq', float(freq))
        c.send_message('/gate/voice1', 1)
        time.sleep(0.5)
        c.send_message('/gate/voice1', 0)
        time.sleep(0.2)
    
    # Test 2: Multiple voices - should show in individual meters
    print("\n2. Testing multiple voice levels")
    for i in range(1, 5):
        c.send_message(f'/mod/voice{i}/freq', float(220 * i))
        c.send_message(f'/gate/voice{i}', 1)
    time.sleep(2)
    for i in range(1, 5):
        c.send_message(f'/gate/voice{i}', 0)
    
    # Test 3: Sequencer for continuous spectrum display
    print("\n3. Testing sequencer with patterns (spectrum should react)")
    c.send_message('/seq/add', ['kick', 'voice1', 'X...X...X...X...', 60.0, 200.0])
    c.send_message('/seq/add', ['bass', 'voice2', 'x.x.x.x.x.x.x.x.', 110.0, 800.0])
    c.send_message('/seq/add', ['hihat', 'voice3', 'xxxxxxxxxxxxxxxx', 8000.0, 12000.0])
    c.send_message('/seq/start', None)
    
    print("\nSequencer running - watch the spectrum analyzer!")
    print("Voice levels should show individual activity")
    print("Spectrum should show bass (left), mids, and highs (right)")
    
    time.sleep(10)
    
    # Cleanup
    c.send_message('/seq/stop', None)
    c.send_message('/seq/clear', None)
    
    print("\nTest complete!")

if __name__ == "__main__":
    test_visualizer()
