#!/usr/bin/env python3
"""
IPC-01: OSC Message Latency Test (Using AsyncIO)
Based on the python-osc documentation for proper async handling
"""

import asyncio
import time
import statistics
from typing import List

from pythonosc import dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc import udp_client

# Test configuration
TEST_PORT = 5556
TEST_HOST = "127.0.0.1"
NUM_MESSAGES = 100
LATENCY_TARGET = 5.0  # 5ms maximum
LATENCY_IDEAL = 2.0   # 2ms ideal

class OSCLatencyTester:
    def __init__(self):
        self.latencies = []
        self.received_count = 0
        self.client = None
        
    def ping_handler(self, address, *args):
        """Handler for /test/ping messages - measures latency"""
        receive_time = time.perf_counter()
        
        if len(args) >= 2:
            msg_id = args[0]
            send_time = args[1]
            
            # Calculate one-way latency
            latency_ms = (receive_time - send_time) * 1000
            self.latencies.append(latency_ms)
            self.received_count += 1
            
            # Optional: Print progress every 20 messages
            if self.received_count % 20 == 0:
                print(f"   Received {self.received_count} messages...")
    
    async def run_test(self):
        """Run the async OSC latency test"""
        
        print("\n" + "="*60)
        print("IPC-01: OSC MESSAGE LATENCY TEST (Async)")
        print("="*60)
        print(f"Testing {NUM_MESSAGES} messages")
        print(f"Target: <{LATENCY_TARGET}ms")
        print("="*60)
        
        # Create dispatcher and map handler
        disp = dispatcher.Dispatcher()
        disp.map("/test/ping", self.ping_handler)
        
        # Create async server
        print("\n1. Starting OSC server...")
        server = AsyncIOOSCUDPServer(
            (TEST_HOST, TEST_PORT), 
            disp, 
            asyncio.get_event_loop()
        )
        
        # Start serving
        transport, protocol = await server.create_serve_endpoint()
        print(f"   ✓ Server listening on {TEST_HOST}:{TEST_PORT}")
        
        # Create client
        print("\n2. Creating OSC client...")
        self.client = udp_client.SimpleUDPClient(TEST_HOST, TEST_PORT)
        print(f"   ✓ Client ready")
        
        # Send messages
        print(f"\n3. Sending {NUM_MESSAGES} test messages...")
        
        for i in range(NUM_MESSAGES):
            msg_id = f"msg_{i}"
            send_time = time.perf_counter()
            
            # Send OSC message
            self.client.send_message("/test/ping", [msg_id, send_time])
            
            # Small async sleep to let server process
            await asyncio.sleep(0.001)  # 1ms between messages
        
        print(f"   ✓ All messages sent")
        
        # Wait for all messages to be processed
        print("\n4. Waiting for processing...")
        await asyncio.sleep(0.5)
        
        # Clean up
        transport.close()
        print("   ✓ Server stopped")
        
        return self.analyze_results()
    
    def analyze_results(self):
        """Analyze latency measurements"""
        
        print("\n" + "="*60)
        print("RESULTS:")
        print("-"*60)
        
        if not self.latencies:
            print("✗ No messages received!")
            return False
        
        # Calculate statistics
        stats = {
            'received': self.received_count,
            'sent': NUM_MESSAGES,
            'success_rate': (self.received_count / NUM_MESSAGES) * 100,
            'mean': statistics.mean(self.latencies),
            'median': statistics.median(self.latencies),
            'min': min(self.latencies),
            'max': max(self.latencies),
            'stdev': statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
        }
        
        print(f"Messages sent:     {stats['sent']}")
        print(f"Messages received: {stats['received']}")
        print(f"Success rate:      {stats['success_rate']:.1f}%")
        print("-"*60)
        print(f"Mean latency:   {stats['mean']:.3f}ms")
        print(f"Median latency: {stats['median']:.3f}ms")
        print(f"Min latency:    {stats['min']:.3f}ms")
        print(f"Max latency:    {stats['max']:.3f}ms")
        print(f"Std deviation:  {stats['stdev']:.3f}ms")
        print("="*60)
        
        # Pass/Fail
        passed = True
        
        if stats['success_rate'] < 100:
            print(f"⚠️  Warning: {100 - stats['success_rate']:.1f}% message loss")
            passed = False
        
        if stats['max'] > LATENCY_TARGET:
            print(f"✗ FAIL: Max latency {stats['max']:.3f}ms exceeds {LATENCY_TARGET}ms target")
            passed = False
        elif stats['mean'] > LATENCY_IDEAL:
            print(f"✓ PASS (Marginal): Mean {stats['mean']:.3f}ms above ideal {LATENCY_IDEAL}ms")
        else:
            print(f"✓ PASS (Excellent): All metrics within ideal targets!")
        
        print("\nWhat this means:")
        if stats['mean'] < 2:
            print("✓ Control signals will feel instantaneous")
            print("✓ Total system latency: ~8ms (6ms audio + 2ms OSC)")
        elif stats['mean'] < 5:
            print("✓ Control signals fast enough for music")
            print("✓ Total system latency: <15ms (acceptable)")
        
        return passed

async def main():
    """Main async function"""
    print("Starting OSC latency test...")
    print("This tests control signal speed in our modular synth.\n")
    
    tester = OSCLatencyTester()
    passed = await tester.run_test()
    
    return passed

if __name__ == "__main__":
    # Run the async test
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        exit(1)