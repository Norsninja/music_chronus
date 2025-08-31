#!/usr/bin/env python3
"""
IPC-02: OSC Throughput Test
Testing >1000 messages per second throughput for real-time control

Based on research showing:
- python-osc AsyncIO server best for I/O-bound operations
- UDP buffers need tuning to 4MB for high throughput
- Sequence numbers essential for packet loss detection
"""

import asyncio
import time
import socket
import statistics
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import List, Dict, Tuple
import random

from pythonosc import dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer, ThreadingOSCUDPServer
from pythonosc import udp_client
from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.osc_bundle_builder import OscBundleBuilder

# Test configuration
TEST_HOST = "127.0.0.1"
TEST_PORT = 5005
TARGET_THROUGHPUT = 1000  # messages per second
SUSTAINED_DURATION = 10  # seconds for sustained test
BURST_SIZE = 100  # messages in burst test

# UDP buffer sizes (4MB as per research)
UDP_BUFFER_SIZE = 4 * 1024 * 1024  # 4MB

@dataclass
class MessageStats:
    """Statistics for message processing."""
    received_count: int = 0
    dropped_count: int = 0
    out_of_order: int = 0
    processing_times: List[float] = None
    latencies: List[float] = None
    last_sequence: int = -1
    
    def __post_init__(self):
        if self.processing_times is None:
            self.processing_times = []
        if self.latencies is None:
            self.latencies = []
    
    def calculate_percentiles(self, data: List[float]) -> Dict[str, float]:
        """Calculate latency percentiles."""
        if not data:
            return {"p50": 0, "p95": 0, "p99": 0, "p99.9": 0}
        
        sorted_data = sorted(data)
        n = len(sorted_data)
        
        return {
            "p50": sorted_data[int(n * 0.50)],
            "p95": sorted_data[int(n * 0.95)],
            "p99": sorted_data[int(n * 0.99)],
            "p99.9": sorted_data[min(int(n * 0.999), n-1)]
        }

class ThroughputTester:
    """OSC throughput testing framework."""
    
    def __init__(self, host=TEST_HOST, port=TEST_PORT):
        self.host = host
        self.port = port
        self.stats = MessageStats()
        self.server = None
        self.transport = None
        self.protocol = None
        self.start_time = None
        
    def setup_dispatcher(self):
        """Create OSC message dispatcher."""
        disp = dispatcher.Dispatcher()
        
        # Test message handler
        disp.map("/test/*", self.handle_test_message)
        
        # Throughput test handler
        disp.map("/throughput/*", self.handle_throughput_message)
        
        # Bundle test handler  
        disp.map("/bundle/*", self.handle_bundle_message)
        
        return disp
    
    def handle_test_message(self, address, *args):
        """Handle basic test messages."""
        if len(args) >= 2:
            sequence = args[0]
            timestamp = args[1]
            
            # Calculate latency
            current_time = time.perf_counter()
            latency = (current_time - timestamp) * 1000  # Convert to ms
            self.stats.latencies.append(latency)
    
    def handle_throughput_message(self, address, *args):
        """Handle throughput test messages with sequence tracking."""
        receive_time = time.perf_counter()
        
        if len(args) >= 2:
            sequence = args[0]
            send_time = args[1]
            
            # Track sequence for packet loss detection
            if sequence > self.stats.last_sequence + 1:
                # Packets were dropped
                dropped = sequence - self.stats.last_sequence - 1
                self.stats.dropped_count += dropped
            elif sequence < self.stats.last_sequence:
                # Out of order packet
                self.stats.out_of_order += 1
            
            self.stats.last_sequence = sequence
            self.stats.received_count += 1
            
            # Calculate processing time
            if self.start_time:
                processing_time = (receive_time - self.start_time) * 1000
                self.stats.processing_times.append(processing_time)
            
            # Calculate latency
            latency = (receive_time - send_time) * 1000
            self.stats.latencies.append(latency)
    
    def handle_bundle_message(self, address, *args):
        """Handle bundled messages."""
        # Bundles are automatically unpacked by pythonosc
        self.stats.received_count += 1
    
    async def start_asyncio_server(self, buffer_size=None):
        """Start AsyncIO OSC server."""
        disp = self.setup_dispatcher()
        
        # Create server
        server = AsyncIOOSCUDPServer(
            (self.host, self.port),
            disp,
            asyncio.get_event_loop()
        )
        
        # Start server and get transport
        self.transport, self.protocol = await server.create_serve_endpoint()
        
        # Try to set buffer size on the transport's socket if available
        if buffer_size and hasattr(self.transport, 'get_extra_info'):
            sock = self.transport.get_extra_info('socket')
            if sock:
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffer_size)
                    # Verify it was set
                    actual_size = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
                    print(f"      UDP buffer size set to: {actual_size / 1024 / 1024:.1f}MB")
                except Exception as e:
                    print(f"      Warning: Could not set UDP buffer size: {e}")
        
        self.start_time = time.perf_counter()
        return server
    
    def start_threading_server(self, buffer_size=None):
        """Start Threading OSC server for comparison."""
        disp = self.setup_dispatcher()
        
        if buffer_size:
            # Note: ThreadingOSCUDPServer doesn't support custom socket directly
            # This is a limitation we'll document
            server = ThreadingOSCUDPServer((self.host, self.port), disp)
            # Try to set buffer size after creation
            try:
                server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffer_size)
            except:
                pass
        else:
            server = ThreadingOSCUDPServer((self.host, self.port), disp)
        
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        self.server = server
        self.start_time = time.perf_counter()
        return server
    
    def stop_server(self):
        """Stop the server."""
        if self.transport:
            self.transport.close()
            self.transport = None
        if self.server:
            self.server.shutdown()
            self.server = None
        self.protocol = None
    
    def reset_stats(self):
        """Reset statistics for new test."""
        self.stats = MessageStats()

async def test_sustained_throughput(use_asyncio=True, duration=SUSTAINED_DURATION):
    """Test sustained message throughput."""
    
    print(f"\n1. Testing sustained throughput ({TARGET_THROUGHPUT} msg/sec for {duration}s)...")
    print(f"   Using {'AsyncIO' if use_asyncio else 'Threading'} server")
    
    tester = ThroughputTester()
    
    # Start server
    if use_asyncio:
        await tester.start_asyncio_server(buffer_size=UDP_BUFFER_SIZE)
    else:
        tester.start_threading_server(buffer_size=UDP_BUFFER_SIZE)
    
    # Give server time to start
    await asyncio.sleep(0.1)
    
    # Create client
    client = udp_client.SimpleUDPClient(TEST_HOST, TEST_PORT)
    
    # Send messages at target rate
    messages_to_send = TARGET_THROUGHPUT * duration
    interval = 1.0 / TARGET_THROUGHPUT
    
    print(f"   Sending {messages_to_send} messages...")
    
    start_time = time.perf_counter()
    
    for sequence in range(messages_to_send):
        # Send message with sequence number and timestamp
        client.send_message("/throughput/test", [sequence, time.perf_counter()])
        
        # Sleep to maintain rate (with occasional checks)
        if sequence % 100 == 0:
            # Check if we're on schedule
            elapsed = time.perf_counter() - start_time
            expected = sequence * interval
            if elapsed < expected:
                await asyncio.sleep(expected - elapsed)
        else:
            await asyncio.sleep(interval)
        
        # Progress update
        if sequence % 1000 == 0 and sequence > 0:
            print(f"      Sent {sequence} messages...")
    
    # Wait for processing to complete
    await asyncio.sleep(0.5)
    
    # Calculate results
    actual_throughput = tester.stats.received_count / duration
    packet_loss = (tester.stats.dropped_count / messages_to_send) * 100
    
    print(f"\n   Results:")
    print(f"      Sent: {messages_to_send}")
    print(f"      Received: {tester.stats.received_count}")
    print(f"      Dropped: {tester.stats.dropped_count}")
    print(f"      Out of order: {tester.stats.out_of_order}")
    print(f"      Actual throughput: {actual_throughput:.1f} msg/sec")
    print(f"      Packet loss: {packet_loss:.2f}%")
    
    if tester.stats.latencies:
        percentiles = tester.stats.calculate_percentiles(tester.stats.latencies)
        print(f"      Latency P50: {percentiles['p50']:.2f}ms")
        print(f"      Latency P95: {percentiles['p95']:.2f}ms")
        print(f"      Latency P99: {percentiles['p99']:.2f}ms")
    
    tester.stop_server()
    
    return {
        'throughput': actual_throughput,
        'packet_loss': packet_loss,
        'latencies': percentiles if tester.stats.latencies else None,
        'received': tester.stats.received_count
    }

async def test_burst_handling():
    """Test burst message handling."""
    
    print(f"\n2. Testing burst handling ({BURST_SIZE} messages instantly)...")
    
    tester = ThroughputTester()
    await tester.start_asyncio_server(buffer_size=UDP_BUFFER_SIZE)
    
    # Give server time to start
    await asyncio.sleep(0.1)
    
    # Create client
    client = udp_client.SimpleUDPClient(TEST_HOST, TEST_PORT)
    
    # Send burst
    print(f"   Sending burst of {BURST_SIZE} messages...")
    burst_start = time.perf_counter()
    
    for sequence in range(BURST_SIZE):
        client.send_message("/throughput/burst", [sequence, time.perf_counter()])
    
    burst_send_time = time.perf_counter() - burst_start
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    burst_total_time = time.perf_counter() - burst_start
    
    print(f"\n   Results:")
    print(f"      Messages sent: {BURST_SIZE}")
    print(f"      Messages received: {tester.stats.received_count}")
    print(f"      Send time: {burst_send_time*1000:.1f}ms")
    print(f"      Total processing time: {burst_total_time*1000:.1f}ms")
    print(f"      Success rate: {(tester.stats.received_count/BURST_SIZE)*100:.1f}%")
    
    tester.stop_server()
    
    return tester.stats.received_count == BURST_SIZE

async def test_mixed_sizes():
    """Test handling of mixed message sizes."""
    
    print("\n3. Testing mixed message sizes...")
    
    tester = ThroughputTester()
    await tester.start_asyncio_server(buffer_size=UDP_BUFFER_SIZE)
    
    await asyncio.sleep(0.1)
    
    client = udp_client.SimpleUDPClient(TEST_HOST, TEST_PORT)
    
    # Define message types
    messages_sent = 0
    test_duration = 10  # seconds
    
    print(f"   Sending mixed size messages for {test_duration}s...")
    start_time = time.perf_counter()
    
    while time.perf_counter() - start_time < test_duration:
        # Small parameter message (32 bytes)
        if random.random() < 0.5:  # 50% small messages
            client.send_message("/throughput/param", [messages_sent, time.perf_counter(), 1.234])
        
        # Medium pattern message (256 bytes)
        elif random.random() < 0.8:  # 30% medium messages
            pattern = [random.random() for _ in range(30)]
            client.send_message("/throughput/pattern", [messages_sent, time.perf_counter()] + pattern)
        
        # Large waveform message (4KB)
        else:  # 20% large messages
            waveform = [random.random() for _ in range(500)]
            client.send_message("/throughput/waveform", [messages_sent, time.perf_counter()] + waveform)
        
        messages_sent += 1
        
        # Maintain roughly 1000 msg/sec
        await asyncio.sleep(0.001)
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    actual_throughput = tester.stats.received_count / test_duration
    
    print(f"\n   Results:")
    print(f"      Messages sent: {messages_sent}")
    print(f"      Messages received: {tester.stats.received_count}")
    print(f"      Throughput: {actual_throughput:.1f} msg/sec")
    print(f"      Success rate: {(tester.stats.received_count/messages_sent)*100:.1f}%")
    
    tester.stop_server()
    
    return actual_throughput >= TARGET_THROUGHPUT * 0.9  # 90% of target

async def test_bundle_efficiency():
    """Test message bundling efficiency."""
    
    print("\n4. Testing bundle efficiency...")
    
    tester = ThroughputTester()
    await tester.start_asyncio_server(buffer_size=UDP_BUFFER_SIZE)
    
    await asyncio.sleep(0.1)
    
    client = udp_client.SimpleUDPClient(TEST_HOST, TEST_PORT)
    
    bundles_to_send = 100
    messages_per_bundle = 10
    
    print(f"   Sending {bundles_to_send} bundles with {messages_per_bundle} messages each...")
    
    start_time = time.perf_counter()
    
    for bundle_num in range(bundles_to_send):
        # Create bundle
        bundle_builder = OscBundleBuilder(time.time())
        
        for msg_num in range(messages_per_bundle):
            msg = OscMessageBuilder(address="/bundle/test")
            msg.add_arg(bundle_num * messages_per_bundle + msg_num)
            msg.add_arg(time.perf_counter())
            bundle_builder.add_content(msg.build())
        
        # Send bundle
        bundle = bundle_builder.build()
        client.send(bundle)
        
        # Maintain rate
        await asyncio.sleep(0.01)  # 100 bundles/sec
    
    send_time = time.perf_counter() - start_time
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    total_messages = bundles_to_send * messages_per_bundle
    effective_rate = total_messages / send_time
    
    print(f"\n   Results:")
    print(f"      Bundles sent: {bundles_to_send}")
    print(f"      Total messages: {total_messages}")
    print(f"      Messages received: {tester.stats.received_count}")
    print(f"      Send time: {send_time:.2f}s")
    print(f"      Effective rate: {effective_rate:.1f} msg/sec")
    
    tester.stop_server()
    
    return effective_rate >= TARGET_THROUGHPUT

async def compare_asyncio_vs_threading():
    """Compare AsyncIO vs Threading server performance."""
    
    print("\n5. Comparing AsyncIO vs Threading servers...")
    
    # Test AsyncIO
    print("\n   Testing AsyncIO server:")
    asyncio_results = await test_sustained_throughput(use_asyncio=True, duration=5)
    
    # Test Threading
    print("\n   Testing Threading server:")
    threading_results = await test_sustained_throughput(use_asyncio=False, duration=5)
    
    # Compare results
    print("\n   Comparison:")
    print(f"      AsyncIO throughput: {asyncio_results['throughput']:.1f} msg/sec")
    print(f"      Threading throughput: {threading_results['throughput']:.1f} msg/sec")
    
    if asyncio_results['throughput'] > threading_results['throughput']:
        improvement = ((asyncio_results['throughput'] - threading_results['throughput']) / 
                      threading_results['throughput']) * 100
        print(f"      AsyncIO is {improvement:.1f}% faster")
    else:
        improvement = ((threading_results['throughput'] - asyncio_results['throughput']) / 
                      asyncio_results['throughput']) * 100
        print(f"      Threading is {improvement:.1f}% faster")
    
    return asyncio_results, threading_results

async def main():
    """Run complete OSC throughput test suite."""
    
    print("\n" + "="*60)
    print("IPC-02: OSC THROUGHPUT TEST")
    print("="*60)
    print(f"Target: {TARGET_THROUGHPUT} messages/second")
    print(f"UDP Buffer: {UDP_BUFFER_SIZE / 1024 / 1024:.1f}MB")
    print("="*60)
    
    results = {}
    
    # Test 1: Sustained throughput
    sustained_result = await test_sustained_throughput()
    results['sustained'] = sustained_result
    await asyncio.sleep(0.5)  # Allow port to release
    
    # Test 2: Burst handling
    burst_result = await test_burst_handling()
    results['burst'] = burst_result
    await asyncio.sleep(0.5)  # Allow port to release
    
    # Test 3: Mixed sizes
    mixed_result = await test_mixed_sizes()
    results['mixed'] = mixed_result
    await asyncio.sleep(0.5)  # Allow port to release
    
    # Test 4: Bundle efficiency
    bundle_result = await test_bundle_efficiency()
    results['bundle'] = bundle_result
    await asyncio.sleep(0.5)  # Allow port to release
    
    # Test 5: AsyncIO vs Threading
    asyncio_result, threading_result = await compare_asyncio_vs_threading()
    results['asyncio'] = asyncio_result
    results['threading'] = threading_result
    
    # Summary
    print("\n" + "="*60)
    print("RESULTS SUMMARY:")
    print("-"*60)
    
    success = True
    
    # Sustained throughput check
    if results['sustained']['throughput'] >= TARGET_THROUGHPUT * 0.99:
        print(f"✓ Sustained throughput: {results['sustained']['throughput']:.1f} msg/sec")
    else:
        print(f"✗ Sustained throughput: {results['sustained']['throughput']:.1f} msg/sec (target: {TARGET_THROUGHPUT})")
        success = False
    
    # Packet loss check
    if results['sustained']['packet_loss'] <= 1.0:
        print(f"✓ Packet loss: {results['sustained']['packet_loss']:.2f}%")
    else:
        print(f"✗ Packet loss: {results['sustained']['packet_loss']:.2f}% (target: <1%)")
        success = False
    
    # Latency check
    if results['sustained']['latencies']:
        latencies = results['sustained']['latencies']
        if latencies['p99'] <= 10.0:
            print(f"✓ P99 latency: {latencies['p99']:.2f}ms")
        else:
            print(f"✗ P99 latency: {latencies['p99']:.2f}ms (target: <10ms)")
            success = False
    
    # Other tests
    print(f"{'✓' if results['burst'] else '✗'} Burst handling: {'Passed' if results['burst'] else 'Failed'}")
    print(f"{'✓' if results['mixed'] else '✗'} Mixed sizes: {'Passed' if results['mixed'] else 'Failed'}")
    print(f"{'✓' if results['bundle'] else '✗'} Bundle efficiency: {'Passed' if results['bundle'] else 'Failed'}")
    
    print("="*60)
    
    if success:
        print("\n✓ IPC-02 PASSED: OSC can handle >1000 messages/second")
        print("\nWhat this means:")
        print("• Control messages can handle rapid parameter changes")
        print("• System can support complex automation")
        print("• Multiple modules can communicate efficiently")
    else:
        print("\n✗ IPC-02 FAILED: OSC throughput below requirements")
        print("\nRecommendations:")
        print("• Consider switching to osc4py3")
        print("• Increase UDP buffer sizes")
        print("• Optimize message handlers")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)