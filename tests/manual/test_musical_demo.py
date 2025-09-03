#!/usr/bin/env python
"""Musical demonstration of CP3 router - plays a simple melody"""

from pythonosc import udp_client
import time
import sys

def main():
    client = udp_client.SimpleUDPClient('127.0.0.1', 5005)
    
    print("=== CP3 Musical Demo ===\n")
    print("Starting musical demonstration...")
    print("Make sure supervisor is running with: CHRONUS_ROUTER=1 python src/music_chronus/supervisor_v3_router.py\n")
    
    # Wait a moment
    time.sleep(1)
    
    # Build the patch
    print("1. Building synthesizer patch...")
    client.send_message('/patch/create', ['osc1', 'simple_sine'])
    time.sleep(0.1)
    client.send_message('/patch/create', ['env1', 'adsr'])
    time.sleep(0.1)
    client.send_message('/patch/create', ['filter1', 'biquad_filter'])
    time.sleep(0.1)
    
    print("2. Connecting modules: osc1 -> env1 -> filter1")
    client.send_message('/patch/connect', ['osc1', 'env1'])
    time.sleep(0.1)
    client.send_message('/patch/connect', ['env1', 'filter1'])
    time.sleep(0.1)
    
    print("3. Committing patch (switching to active slot)...")
    client.send_message('/patch/commit', [])
    time.sleep(0.5)  # Give it time to switch
    
    # Configure the synthesizer
    print("4. Configuring synthesizer parameters...")
    client.send_message('/mod/osc1/gain', 0.3)
    time.sleep(0.05)
    
    # Set ADSR envelope
    client.send_message('/mod/env1/attack', 0.01)   # Fast attack
    client.send_message('/mod/env1/decay', 0.1)     # Quick decay
    client.send_message('/mod/env1/sustain', 0.7)   # Medium sustain
    client.send_message('/mod/env1/release', 0.2)   # Medium release
    time.sleep(0.05)
    
    # Configure filter
    client.send_message('/mod/filter1/cutoff', 2000.0)
    client.send_message('/mod/filter1/q', 2.0)
    time.sleep(0.05)
    
    print("\n5. Playing a simple melody...\n")
    
    # C major scale frequencies
    notes = [
        ('C4', 261.63),
        ('D4', 293.66),
        ('E4', 329.63),
        ('F4', 349.23),
        ('G4', 392.00),
        ('A4', 440.00),
        ('B4', 493.88),
        ('C5', 523.25),
    ]
    
    # Play scale up
    print("   Scale ascending...")
    for note, freq in notes:
        print(f"   {note} ({freq:.0f}Hz)")
        client.send_message('/mod/osc1/freq', freq)
        client.send_message('/gate/env1', 1)  # Note on
        time.sleep(0.2)
        client.send_message('/gate/env1', 0)  # Note off
        time.sleep(0.05)
    
    time.sleep(0.5)
    
    # Play scale down
    print("\n   Scale descending...")
    for note, freq in reversed(notes):
        print(f"   {note} ({freq:.0f}Hz)")
        client.send_message('/mod/osc1/freq', freq)
        client.send_message('/gate/env1', 1)  # Note on
        time.sleep(0.2)
        client.send_message('/gate/env1', 0)  # Note off
        time.sleep(0.05)
    
    time.sleep(0.5)
    
    # Play a simple melody
    print("\n   Playing 'Mary Had a Little Lamb'...")
    melody = [
        ('E4', 329.63, 0.3),
        ('D4', 293.66, 0.3),
        ('C4', 261.63, 0.3),
        ('D4', 293.66, 0.3),
        ('E4', 329.63, 0.3),
        ('E4', 329.63, 0.3),
        ('E4', 329.63, 0.6),
        
        ('D4', 293.66, 0.3),
        ('D4', 293.66, 0.3),
        ('D4', 293.66, 0.6),
        
        ('E4', 329.63, 0.3),
        ('G4', 392.00, 0.3),
        ('G4', 392.00, 0.6),
    ]
    
    for note, freq, duration in melody:
        client.send_message('/mod/osc1/freq', freq)
        client.send_message('/gate/env1', 1)  # Note on
        time.sleep(duration)
        client.send_message('/gate/env1', 0)  # Note off
        time.sleep(0.05)
    
    print("\n6. Demo complete!")
    print("\nYou can continue sending commands manually, or Ctrl+C to stop the supervisor.")

if __name__ == '__main__':
    main()