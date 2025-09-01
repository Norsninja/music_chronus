#!/usr/bin/env python3
"""Minimal test of OSC server like in supervisor_v2_fixed."""

from pythonosc import dispatcher, osc_server
import asyncio
import threading
import time

class TestOSC:
    def __init__(self):
        self.osc_thread = None
        self.osc_loop = None
        
    def handle_osc_message(self, address: str, *args):
        print(f"*** RECEIVED: {address} with args: {args}")
        
    def start_osc_server(self):
        """Start OSC server exactly like supervisor_v2_fixed"""
        try:
            host = '127.0.0.1'
            port = 5005
            
            disp = dispatcher.Dispatcher()
            disp.map("/*", self.handle_osc_message)
            
            async def run_server():
                server = osc_server.AsyncIOOSCUDPServer(
                    (host, port), disp, asyncio.get_event_loop()
                )
                transport, protocol = await server.create_serve_endpoint()
                print(f"OSC server listening on {host}:{port}")
                
                # Keep running
                await asyncio.Future()
            
            # Run in thread
            def run_loop():
                self.osc_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.osc_loop)
                self.osc_loop.run_until_complete(run_server())
            
            self.osc_thread = threading.Thread(target=run_loop, daemon=True)
            self.osc_thread.start()
            
            time.sleep(0.1)
            return True
            
        except Exception as e:
            print(f"Failed to start OSC server: {e}")
            return False

if __name__ == "__main__":
    test = TestOSC()
    test.start_osc_server()
    print("Test OSC server running. Send messages to port 5005")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")