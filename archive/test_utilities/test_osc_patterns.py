#!/usr/bin/env python3
"""Test OSC pattern matching - verify Senior Dev's diagnosis."""

from pythonosc import dispatcher, osc_server
import asyncio

def handle_single(address: str, *args):
    print(f"SINGLE (/*): {address} with {args}")

def handle_double(address: str, *args):
    print(f"DOUBLE (/*/*): {address} with {args}")

def handle_triple(address: str, *args):
    print(f"TRIPLE (/*/*/*): {address} with {args}")

def handle_default(address: str, *args):
    print(f"DEFAULT: {address} with {args}")

async def main():
    print("Testing OSC pattern matching")
    print("-" * 40)
    
    disp = dispatcher.Dispatcher()
    disp.map("/*", handle_single)
    disp.map("/*/*", handle_double)
    disp.map("/*/*/*", handle_triple)
    disp.set_default_handler(handle_default)
    
    server = osc_server.AsyncIOOSCUDPServer(
        ("127.0.0.1", 5008), disp, asyncio.get_event_loop()
    )
    
    transport, protocol = await server.create_serve_endpoint()
    print("Server ready on port 5008")
    print("Send test messages to see which patterns match")
    print("-" * 40)
    
    await asyncio.sleep(30)
    transport.close()

if __name__ == "__main__":
    asyncio.run(main())