#!/usr/bin/env python3
"""Test if we can receive OSC messages on port 5005."""

from pythonosc import dispatcher, osc_server
import asyncio

def handle_all(address, *args):
    print(f"Received: {address} with args: {args}")

async def main():
    print("Starting test OSC listener on 127.0.0.1:5006...")
    disp = dispatcher.Dispatcher()
    disp.map("/*", handle_all)
    
    server = osc_server.AsyncIOOSCUDPServer(
        ("127.0.0.1", 5006), disp, asyncio.get_event_loop()
    )
    
    transport, protocol = await server.create_serve_endpoint()
    print("Listening for OSC messages on port 5006...")
    print("Send a test message with:")
    print("  client.send_message('/test', 123)")
    
    await asyncio.sleep(30)  # Listen for 30 seconds
    transport.close()

if __name__ == "__main__":
    asyncio.run(main())