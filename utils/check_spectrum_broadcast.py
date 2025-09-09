#!/usr/bin/env python3
"""Check spectrum broadcast specifically"""

from pythonosc import udp_client, dispatcher, osc_server
import threading
import time

print("Checking spectrum broadcast...")
print("-" * 50)

messages = []

def handle_all(addr, *args):
    messages.append((addr, args))
    if addr == '/viz/spectrum':
        print(f"SPECTRUM DATA: {args[:8] if args else 'None'}")
    elif addr == '/viz/levels':
        print(f"LEVELS DATA: {args[:4] if args else 'None'}")

# Listen for broadcasts
disp = dispatcher.Dispatcher()
disp.set_default_handler(handle_all)
server = osc_server.ThreadingOSCUDPServer(('127.0.0.1', 5006), disp)

def run_server():
    server.serve_forever()

thread = threading.Thread(target=run_server, daemon=True)
thread.start()

# Generate audio to trigger spectrum
print("\nGenerating audio...")
c = udp_client.SimpleUDPClient('127.0.0.1', 5005)

# Play strong signal
c.send_message('/mod/voice1/freq', 440.0)
c.send_message('/mod/voice1/amp', 0.8)
c.send_message('/gate/voice1', 1)

print("Listening for 3 seconds...")
time.sleep(3)

c.send_message('/gate/voice1', 0)
server.shutdown()

# Analyze what we received
spectrum_count = sum(1 for addr, _ in messages if addr == '/viz/spectrum')
levels_count = sum(1 for addr, _ in messages if addr == '/viz/levels')

print("\n" + "=" * 50)
print(f"Received {levels_count} /viz/levels messages")
print(f"Received {spectrum_count} /viz/spectrum messages")

if spectrum_count == 0:
    print("\nPROBLEM: No spectrum data being broadcast!")
    print("The engine is not sending /viz/spectrum messages")
