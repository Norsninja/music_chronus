#!/usr/bin/env python3
"""Simple audio check - verify supervisor is producing sound"""

import time
from pythonosc import udp_client

def audio_check():
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("=== Audio Check ===")
    print("Creating simple sine oscillator...")
    
    # Create and commit minimal patch
    client.send_message("/patch/create", ["osc1", "simple_sine"])
    time.sleep(0.1)
    client.send_message("/patch/commit", [])
    time.sleep(0.5)
    
    # Set loud enough to hear
    client.send_message("/mod/osc1/freq", [440.0])
    client.send_message("/mod/osc1/gain", [0.5])  # Louder for testing
    
    print("\nYou should hear a 440Hz tone NOW.")
    print("If no sound:")
    print("  1. Check supervisor is running with CHRONUS_ROUTER=1")
    print("  2. Check audio output device")
    print("  3. Check volume levels")
    
    time.sleep(3)
    
    # Try different frequency
    print("\nChanging to 880Hz...")
    client.send_message("/mod/osc1/freq", [880.0])
    time.sleep(2)
    
    print("\nSilencing...")
    client.send_message("/mod/osc1/gain", [0.0])
    time.sleep(0.5)
    
    print("Audio check complete.")

if __name__ == "__main__":
    audio_check()