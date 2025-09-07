#!/usr/bin/env python3
"""
Chronus Control Tool - Query and control the Music Chronus engine
A simple command-line tool for discovering parameters and controlling the synthesizer
"""

import sys
import json
import argparse
from pythonosc import udp_client
import time

class ChronusCtl:
    def __init__(self, host="127.0.0.1", port=5005):
        self.client = udp_client.SimpleUDPClient(host, port)
        self.host = host
        self.port = port
    
    def schema(self, format_type="stdout"):
        """Request and display the engine schema"""
        print(f"[chronusctl] Requesting schema from {self.host}:{self.port}...")
        self.client.send_message("/engine/schema", [format_type])
        
        if format_type == "file":
            print("[chronusctl] Check engine output for file export status")
    
    def status(self):
        """Request engine status"""
        print(f"[chronusctl] Requesting status from {self.host}:{self.port}...")
        self.client.send_message("/engine/status", [])
    
    def seq_status(self):
        """Request sequencer status"""
        print(f"[chronusctl] Requesting sequencer status from {self.host}:{self.port}...")
        self.client.send_message("/seq/status", [])
    
    def list_modules(self):
        """Request module list (human-readable)"""
        print(f"[chronusctl] Requesting module list from {self.host}:{self.port}...")
        self.client.send_message("/engine/list", [])
    
    def start(self):
        """Start the engine"""
        print("[chronusctl] Starting engine...")
        self.client.send_message("/engine/start", [])
    
    def stop(self):
        """Stop the engine"""
        print("[chronusctl] Stopping engine...")
        self.client.send_message("/engine/stop", [])
    
    def seq_start(self):
        """Start the sequencer"""
        print("[chronusctl] Starting sequencer...")
        self.client.send_message("/seq/start", [])
    
    def seq_stop(self):
        """Stop the sequencer"""
        print("[chronusctl] Stopping sequencer...")
        self.client.send_message("/seq/stop", [])
    
    def set_param(self, module_id, param, value):
        """Set a parameter value"""
        path = f"/mod/{module_id}/{param}"
        print(f"[chronusctl] Setting {path} = {value}")
        self.client.send_message(path, [float(value)])
    
    def gate(self, module_id, state):
        """Set gate state"""
        path = f"/gate/{module_id}"
        value = 1 if state else 0
        print(f"[chronusctl] Setting {path} = {value}")
        self.client.send_message(path, [value])
    
    def quick_test(self):
        """Quick test: play a note"""
        print("[chronusctl] Quick test: playing a note...")
        self.client.send_message("/mod/voice1/freq", [440.0])
        self.client.send_message("/gate/voice1", [1])
        time.sleep(1)
        self.client.send_message("/gate/voice1", [0])
        print("[chronusctl] Test complete")

def main():
    parser = argparse.ArgumentParser(
        description="Chronus Control Tool - Query and control the Music Chronus engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  chronusctl schema                  # Get full parameter schema
  chronusctl schema --format file    # Export schema to file
  chronusctl status                   # Get engine status
  chronusctl seq-status              # Get sequencer status
  chronusctl list                    # List all modules
  chronusctl start                   # Start engine
  chronusctl stop                    # Stop engine
  chronusctl seq-start              # Start sequencer
  chronusctl seq-stop               # Stop sequencer
  chronusctl set voice1 freq 440    # Set parameter
  chronusctl gate voice1 on         # Gate on
  chronusctl gate voice1 off        # Gate off
  chronusctl test                   # Quick audio test
        """
    )
    
    parser.add_argument("--host", default="127.0.0.1", help="OSC server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5005, help="OSC server port (default: 5005)")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Schema command
    schema_parser = subparsers.add_parser("schema", help="Get engine parameter schema")
    schema_parser.add_argument("--format", choices=["stdout", "json", "file"], default="stdout",
                              help="Output format (default: stdout)")
    
    # Status commands
    subparsers.add_parser("status", help="Get engine status")
    subparsers.add_parser("seq-status", help="Get sequencer status")
    subparsers.add_parser("list", help="List all modules (human-readable)")
    
    # Control commands
    subparsers.add_parser("start", help="Start engine")
    subparsers.add_parser("stop", help="Stop engine")
    subparsers.add_parser("seq-start", help="Start sequencer")
    subparsers.add_parser("seq-stop", help="Stop sequencer")
    
    # Parameter control
    set_parser = subparsers.add_parser("set", help="Set a parameter value")
    set_parser.add_argument("module", help="Module ID (e.g., voice1, acid1)")
    set_parser.add_argument("param", help="Parameter path (e.g., freq, filter/freq)")
    set_parser.add_argument("value", type=float, help="Value to set")
    
    # Gate control
    gate_parser = subparsers.add_parser("gate", help="Control gate")
    gate_parser.add_argument("module", help="Module ID (e.g., voice1)")
    gate_parser.add_argument("state", choices=["on", "off", "1", "0"], help="Gate state")
    
    # Test command
    subparsers.add_parser("test", help="Quick audio test")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Create controller
    ctl = ChronusCtl(args.host, args.port)
    
    # Execute command
    if args.command == "schema":
        ctl.schema(args.format)
    elif args.command == "status":
        ctl.status()
    elif args.command == "seq-status":
        ctl.seq_status()
    elif args.command == "list":
        ctl.list_modules()
    elif args.command == "start":
        ctl.start()
    elif args.command == "stop":
        ctl.stop()
    elif args.command == "seq-start":
        ctl.seq_start()
    elif args.command == "seq-stop":
        ctl.seq_stop()
    elif args.command == "set":
        ctl.set_param(args.module, args.param, args.value)
    elif args.command == "gate":
        state = args.state in ["on", "1"]
        ctl.gate(args.module, state)
    elif args.command == "test":
        ctl.quick_test()
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()

if __name__ == "__main__":
    main()