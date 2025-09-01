#!/usr/bin/env python3
"""Test if wildcard OSC mapping works."""

from pythonosc import dispatcher, osc_server
import asyncio
import time

def handle_all(address: str, *args):
    print(f"*** RECEIVED: {address} with args: {args}")

async def main():
    print("Testing wildcard OSC mapping...")
    
    disp = dispatcher.Dispatcher()
    # Test wildcard mapping like supervisor_v2_fixed
    disp.map("/*", handle_all)
    
    server = osc_server.AsyncIOOSCUDPServer(
        ("127.0.0.1", 5007), disp, asyncio.get_event_loop()
    )
    
    transport, protocol = await server.create_serve_endpoint()
    print("OSC server listening on 127.0.0.1:5007")
    print("Waiting for messages...")
    
    # Run for 30 seconds
    await asyncio.sleep(30)
    transport.close()
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())