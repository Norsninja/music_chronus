#!/usr/bin/env python3
"""Test which port the visualizer can bind to"""

from pythonosc import dispatcher, osc_server
import time

print("Testing OSC port binding...")

# Test port 5006
try:
    disp = dispatcher.Dispatcher()
    server = osc_server.ThreadingOSCUDPServer(('127.0.0.1', 5006), disp)
    print("SUCCESS: Can bind to port 5006")
    server.shutdown()
except Exception as e:
    print(f"FAILED: Cannot bind to port 5006 - {e}")

# Test port 5007  
try:
    disp = dispatcher.Dispatcher()
    server = osc_server.ThreadingOSCUDPServer(('127.0.0.1', 5007), disp)
    print("SUCCESS: Can bind to port 5007")
    server.shutdown()
except Exception as e:
    print(f"FAILED: Cannot bind to port 5007 - {e}")

print("\nIf port 5006 failed, something else is using it.")
print("If port 5007 succeeded, the visualizer can use it.")
