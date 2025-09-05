#!/usr/bin/env python3
"""
CLI OSC Control - Send commands to the running synthesizer
Usage: python osc_control.py <command> [args]

Examples:
  python osc_control.py freq 440
  python osc_control.py gate 1
  python osc_control.py filter_cutoff 800
  python osc_control.py play_pattern
"""

import sys
from pythonosc import udp_client
import time

# OSC client
client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

def send_command(cmd, *args):
    """Send OSC command"""
    if cmd == "freq" or cmd == "frequency":
        client.send_message("/frequency", float(args[0]))
        print(f"Set frequency: {args[0]}Hz")
        
    elif cmd == "amp" or cmd == "amplitude":
        client.send_message("/amplitude", float(args[0]))
        print(f"Set amplitude: {args[0]}")
        
    elif cmd == "gate":
        client.send_message("/gate", int(args[0]))
        print(f"Gate: {'ON' if int(args[0]) else 'OFF'}")
        
    elif cmd == "note_on":
        client.send_message("/note_on", 1)
        print("Note ON")
        
    elif cmd == "note_off":
        client.send_message("/note_off", 0)
        print("Note OFF")
        
    # Filter controls (if engine supports them)
    elif cmd == "filter_cutoff":
        client.send_message("/filter/cutoff", float(args[0]))
        print(f"Filter cutoff: {args[0]}Hz")
        
    elif cmd == "filter_res" or cmd == "filter_resonance":
        client.send_message("/filter/resonance", float(args[0]))
        print(f"Filter resonance: {args[0]}")
        
    # Preset patterns
    elif cmd == "play_pattern":
        pattern = "X...x...X...x..." if not args else args[0]
        print(f"Playing pattern: {pattern}")
        for char in pattern:
            if char == 'X':
                client.send_message("/frequency", 110.0)
                client.send_message("/amplitude", 0.6)
                client.send_message("/gate", 1)
            elif char == 'x':
                client.send_message("/frequency", 82.5)
                client.send_message("/amplitude", 0.4)
                client.send_message("/gate", 1)
            else:
                client.send_message("/gate", 0)
            time.sleep(0.125)
        
    elif cmd == "bass_drop":
        print("BASS DROP!")
        # Sweep from high to low
        for freq in [440, 220, 110, 55]:
            client.send_message("/frequency", freq)
            client.send_message("/gate", 1)
            time.sleep(0.25)
        client.send_message("/gate", 0)
        
    elif cmd == "acid_sweep":
        print("Acid sweep!")
        client.send_message("/amplitude", 0.5)
        # Sweep cutoff up
        for cutoff in range(200, 2000, 100):
            client.send_message("/filter/cutoff", cutoff)
            client.send_message("/frequency", 55)
            client.send_message("/gate", 1)
            time.sleep(0.05)
        client.send_message("/gate", 0)
        
    else:
        print(f"Unknown command: {cmd}")
        print("\nAvailable commands:")
        print("  freq <hz>         - Set frequency")
        print("  amp <0-1>         - Set amplitude")
        print("  gate <0/1>        - Gate on/off")
        print("  note_on           - Trigger note")
        print("  note_off          - Release note")
        print("  filter_cutoff <hz>- Set filter cutoff")
        print("  filter_res <0-1>  - Set filter resonance")
        print("  play_pattern [pat]- Play a pattern")
        print("  bass_drop         - Drop the bass!")
        print("  acid_sweep        - Acid filter sweep")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python osc_control.py <command> [args]")
        print("Example: python osc_control.py freq 440")
        sys.exit(1)
    
    cmd = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    send_command(cmd, *args)