#!/usr/bin/env python3
"""Debug spectrum data flow"""

from pythonosc import dispatcher, osc_server
import threading
import time

def handle_all(addr, *args):
    if addr.startswith('/viz'):
        if addr == '/viz/spectrum' and args:
            print(f"SPECTRUM: {[f'{x:.2f}' for x in args[:8]]}")
        elif addr == '/viz/levels' and args:
            print(f"LEVELS: {[f'{x:.2f}' for x in args[:4]]}")

# Listen on port 5006 for broadcast data
print("Listening for broadcast data on port 5006...")
print("Start the engine and play some audio to see data")

disp = dispatcher.Dispatcher()
disp.set_default_handler(handle_all)

server = osc_server.ThreadingOSCUDPServer(('127.0.0.1', 5006), disp)
print("Server listening on port 5006")

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nStopping...")
