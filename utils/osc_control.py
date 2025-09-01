#!/usr/bin/env python3
"""
OSC Control Utility for Music Chronus Synthesizer
Simple command-line interface to control the synthesizer.
"""

import argparse
import time
from pythonosc import udp_client

class SynthController:
    def __init__(self, host='127.0.0.1', port=5005):
        self.client = udp_client.SimpleUDPClient(host, port)
        print(f"Connected to synthesizer at {host}:{port}")
    
    def set_param(self, module, param, value):
        """Set a module parameter."""
        addr = f'/mod/{module}/{param}'
        self.client.send_message(addr, value)
        print(f"Sent: {addr} = {value}")
    
    def gate(self, module, state):
        """Control gate (on/off)."""
        addr = f'/gate/{module}'
        self.client.send_message(addr, state)
        print(f"Gate: {module} = {state}")
    
    def test_tone(self, freq=440.0, duration=2.0):
        """Play a test tone."""
        print(f"\nPlaying {freq}Hz for {duration}s...")
        
        # Setup parameters
        self.set_param('sine', 'gain', 0.3)
        self.set_param('sine', 'freq', freq)
        self.set_param('filter', 'cutoff', 10000.0)
        self.set_param('filter', 'q', 0.707)
        self.set_param('adsr', 'attack', 10.0)
        self.set_param('adsr', 'decay', 100.0)
        self.set_param('adsr', 'sustain', 0.7)
        self.set_param('adsr', 'release', 200.0)
        
        # Gate on
        self.gate('adsr', 'on')
        time.sleep(duration)
        
        # Gate off
        self.gate('adsr', 'off')
        print("Done!")
    
    def play_scale(self):
        """Play a C major scale."""
        notes = [
            ('C4', 261.63),
            ('D4', 293.66),
            ('E4', 329.63),
            ('F4', 349.23),
            ('G4', 392.00),
            ('A4', 440.00),
            ('B4', 493.88),
            ('C5', 523.25)
        ]
        
        print("\nPlaying C major scale...")
        self.set_param('sine', 'gain', 0.3)
        self.gate('adsr', 'on')
        
        for note, freq in notes:
            print(f"  {note}: {freq}Hz")
            self.set_param('sine', 'freq', freq)
            time.sleep(0.3)
        
        self.gate('adsr', 'off')
        print("Done!")

def main():
    parser = argparse.ArgumentParser(description='Control Music Chronus Synthesizer')
    parser.add_argument('--host', default='127.0.0.1', help='OSC host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5005, help='OSC port (default: 5005)')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Test tone command
    test_parser = subparsers.add_parser('test', help='Play test tone')
    test_parser.add_argument('--freq', type=float, default=440.0, help='Frequency in Hz')
    test_parser.add_argument('--duration', type=float, default=2.0, help='Duration in seconds')
    
    # Scale command
    scale_parser = subparsers.add_parser('scale', help='Play C major scale')
    
    # Set parameter command
    set_parser = subparsers.add_parser('set', help='Set module parameter')
    set_parser.add_argument('module', help='Module name (sine, adsr, filter)')
    set_parser.add_argument('param', help='Parameter name')
    set_parser.add_argument('value', type=float, help='Parameter value')
    
    # Gate command
    gate_parser = subparsers.add_parser('gate', help='Control gate')
    gate_parser.add_argument('module', help='Module name (usually adsr)')
    gate_parser.add_argument('state', choices=['on', 'off'], help='Gate state')
    
    args = parser.parse_args()
    
    # Create controller
    controller = SynthController(args.host, args.port)
    
    # Execute command
    if args.command == 'test':
        controller.test_tone(args.freq, args.duration)
    elif args.command == 'scale':
        controller.play_scale()
    elif args.command == 'set':
        controller.set_param(args.module, args.param, args.value)
    elif args.command == 'gate':
        controller.gate(args.module, args.state)
    else:
        print("No command specified. Use -h for help.")
        print("\nQuick test: python osc_control.py test")

if __name__ == '__main__':
    main()