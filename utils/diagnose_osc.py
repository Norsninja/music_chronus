#!/usr/bin/env python3
"""Diagnose OSC communication issues"""

from pythonosc import udp_client, dispatcher, osc_server
import threading
import time

print("OSC Diagnostic Tool")
print("=" * 50)

# Test 1: Check if engine is broadcasting
print("\n1. Testing if engine is broadcasting to port 5006...")
received_5006 = []

def handle_5006(addr, *args):
    received_5006.append((addr, args))
    print(f"   Received on 5006: {addr} with {len(args) if args else 0} args")

try:
    disp = dispatcher.Dispatcher()
    disp.set_default_handler(handle_5006)
    server = osc_server.ThreadingOSCUDPServer(('127.0.0.1', 5006), disp)
    
    def run_server():
        server.serve_forever()
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    print("   Listening on port 5006...")
    
    # Trigger some audio to generate broadcast
    c = udp_client.SimpleUDPClient('127.0.0.1', 5005)
    c.send_message('/gate/voice1', 1)
    time.sleep(2)
    c.send_message('/gate/voice1', 0)
    
    time.sleep(1)
    server.shutdown()
    
    if received_5006:
        print(f"   SUCCESS: Received {len(received_5006)} messages on port 5006")
        for addr, args in received_5006[:5]:
            print(f"      {addr}")
    else:
        print("   PROBLEM: No messages received on port 5006")
        print("   Engine may not be broadcasting")
        
except Exception as e:
    print(f"   ERROR: Could not listen on port 5006 - {e}")
    print("   Another process is using this port")

print("\n" + "=" * 50)
print("Diagnosis complete")
