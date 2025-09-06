#!/usr/bin/env python3
"""
Musical Demo - A simple musical piece using pyo engine
Shows what we can create with our simplified architecture
"""

import time
from pythonosc import udp_client

def main():
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("Musical Demo - Simple Ambient Piece")
    print("=" * 50)
    print("\nMake sure engine_pyo.py is running!")
    print("\nCreating a 30-second ambient piece...\n")
    
    # Set up ambient parameters
    client.send_message("/mod/adsr1/attack", 0.5)
    client.send_message("/mod/adsr1/decay", 0.3)
    client.send_message("/mod/adsr1/sustain", 0.4)
    client.send_message("/mod/adsr1/release", 2.0)
    
    # Wide filter for ambient sound
    client.send_message("/mod/filter1/freq", 2000)
    client.send_message("/mod/filter1/q", 1.0)
    
    # Chord progression - Am, F, C, G
    chord_progressions = [
        # Am (A, C, E)
        [220.0, 261.63, 329.63],
        # F (F, A, C)
        [174.61, 220.0, 261.63],
        # C (C, E, G)
        [261.63, 329.63, 392.0],
        # G (G, B, D)
        [196.0, 246.94, 293.66]
    ]
    
    chord_names = ["Am", "F", "C", "G"]
    
    print("Playing chord progression: Am - F - C - G")
    print("-" * 40)
    
    # Play progression twice
    for repeat in range(2):
        print(f"\nPass {repeat + 1}:")
        
        for i, (chord, name) in enumerate(zip(chord_progressions, chord_names)):
            print(f"  Playing {name} chord...")
            
            # Play each note of the chord with slight delay for texture
            for j, freq in enumerate(chord):
                # Slightly detune for richness
                detune = 1.0 + (j * 0.002)
                client.send_message("/mod/sine1/freq", freq * detune)
                client.send_message("/gate/adsr1", 1.0)
                time.sleep(0.15)  # Slight arpeggio effect
            
            # Hold the chord
            time.sleep(2.0)
            
            # Release all notes
            client.send_message("/gate/adsr1", 0.0)
            
            # Space between chords
            time.sleep(1.5)
    
    # Ending - single low note
    print("\nEnding with low drone...")
    client.send_message("/mod/adsr1/release", 4.0)
    client.send_message("/mod/sine1/freq", 110.0)  # Low A
    client.send_message("/mod/filter1/freq", 500)  # Darker filter
    client.send_message("/gate/adsr1", 1.0)
    time.sleep(1.0)
    client.send_message("/gate/adsr1", 0.0)
    
    # Let release tail fade out
    time.sleep(4.0)
    
    print("\n" + "=" * 50)
    print("Demo complete!")
    print("\nWhat we created:")
    print("- Ambient chord progression")
    print("- Dynamic filter and ADSR settings")
    print("- Musical structure (intro, progression, ending)")
    print("- All with simple OSC commands to pyo")
    print("\nThis is what our system can do - make music!")

if __name__ == "__main__":
    main()