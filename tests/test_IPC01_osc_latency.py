#!/usr/bin/env python3
"""
IPC-01: OSC Message Latency Test
Testing how fast Open Sound Control messages travel between processes

OSC is like MIDI but better - it's the modern standard for music software
to communicate. We'll use it for all our control signals.
"""

import time
import multiprocessing
import queue
import statistics
from typing import List, Tuple
import socket

# We'll install python-osc if not already installed
try:
    from pythonosc import dispatcher, osc_server, udp_client
    from pythonosc.osc_message_builder import OscMessageBuilder
except ImportError:
    print("ERROR: python-osc not installed")
    print("Run: pip install python-osc")
    exit(1)

# Test configuration
TEST_PORT = 5555  # Port for OSC communication
TEST_HOST = "127.0.0.1"  # Localhost
NUM_MESSAGES = 100  # How many messages to test
LATENCY_TARGET = 5.0  # 5ms maximum acceptable
LATENCY_IDEAL = 2.0  # 2ms ideal target

class OSCLatencyTester:
    """Measures OSC message latency between processes"""
    
    def __init__(self):
        self.results = []
        self.message_times = {}
        
    def server_process(self, ready_queue: multiprocessing.Queue, 
                       result_queue: multiprocessing.Queue,
                       test_duration: int = 10):
        """
        This runs in a separate process as our OSC server.
        It receives messages and sends back timing information.
        """
        # Track received messages
        received_times = {}
        
        def handle_ping(unused_addr, *args):
            """
            This function is called when we receive a /test/ping message.
            We immediately record when we received it.
            
            Args come as: [msg_id, send_time]
            """
            receive_time = time.perf_counter()
            if len(args) >= 2:
                msg_id = args[0]
                send_time = args[1]
                received_times[msg_id] = (send_time, receive_time)
            
        # Create OSC dispatcher (routes messages to handler functions)
        disp = dispatcher.Dispatcher()
        disp.map("/test/ping", handle_ping)
        
        # Create and start the server
        server = osc_server.ThreadingOSCUDPServer(
            (TEST_HOST, TEST_PORT), disp
        )
        
        # Tell the main process we're ready
        ready_queue.put("ready")
        
        # Run for specified duration
        server.timeout = test_duration
        server.serve_forever()
        
        # Send results back to main process
        result_queue.put(received_times)
    
    def run_latency_test(self) -> dict:
        """Main test that coordinates everything"""
        
        print("\n" + "="*60)
        print("IPC-01: OSC MESSAGE LATENCY TEST")
        print("="*60)
        print(f"Testing {NUM_MESSAGES} messages over localhost UDP")
        print(f"Target: <{LATENCY_TARGET}ms per message")
        print("="*60)
        
        # Step 1: Start the server process
        print("\n1. Starting OSC server process...")
        ready_queue = multiprocessing.Queue()
        result_queue = multiprocessing.Queue()
        
        server_proc = multiprocessing.Process(
            target=self.server_process,
            args=(ready_queue, result_queue, 5)  # Run for 5 seconds
        )
        server_proc.start()
        
        # Wait for server to be ready
        try:
            ready_signal = ready_queue.get(timeout=2)
            print(f"   ✓ Server ready on {TEST_HOST}:{TEST_PORT}")
        except queue.Empty:
            print("   ✗ Server failed to start")
            server_proc.terminate()
            return None
        
        # Step 2: Create client and send messages
        print("\n2. Sending test messages...")
        client = udp_client.SimpleUDPClient(TEST_HOST, TEST_PORT)
        
        send_times = {}
        latencies = []
        
        print(f"   Sending {NUM_MESSAGES} messages...")
        for i in range(NUM_MESSAGES):
            msg_id = f"msg_{i}"
            
            # Record send time with nanosecond precision
            send_time = time.perf_counter()
            send_times[msg_id] = send_time
            
            # Send OSC message with ID and timestamp
            client.send_message("/test/ping", [msg_id, send_time])
            
            # Small delay to avoid overwhelming
            time.sleep(0.001)  # 1ms between messages
            
            # Show progress
            if (i + 1) % 20 == 0:
                print(f"   Sent {i + 1}/{NUM_MESSAGES} messages")
        
        print(f"   ✓ All messages sent")
        
        # Step 3: Wait a moment for all messages to be processed
        time.sleep(0.5)
        
        # Step 4: Stop server and get results
        print("\n3. Collecting results...")
        server_proc.terminate()
        server_proc.join(timeout=2)
        
        try:
            received_times = result_queue.get(timeout=1)
            print(f"   ✓ Received data for {len(received_times)} messages")
        except queue.Empty:
            print("   ✗ No results received from server")
            return None
        
        # Step 5: Calculate latencies
        print("\n4. Analyzing latencies...")
        for msg_id, (send_time, receive_time) in received_times.items():
            latency_ms = (receive_time - send_time) * 1000
            latencies.append(latency_ms)
        
        if not latencies:
            print("   ✗ No latency measurements collected")
            return None
        
        # Calculate statistics
        stats = {
            'count': len(latencies),
            'mean': statistics.mean(latencies),
            'median': statistics.median(latencies),
            'min': min(latencies),
            'max': max(latencies),
            'stdev': statistics.stdev(latencies) if len(latencies) > 1 else 0,
            'success_rate': (len(latencies) / NUM_MESSAGES) * 100
        }
        
        return stats
    
    def print_results(self, stats: dict) -> bool:
        """Print test results and determine pass/fail"""
        
        print("\n" + "="*60)
        print("RESULTS:")
        print("-"*60)
        print(f"Messages sent:     {NUM_MESSAGES}")
        print(f"Messages received: {stats['count']}")
        print(f"Success rate:      {stats['success_rate']:.1f}%")
        print("-"*60)
        print(f"Mean latency:   {stats['mean']:.3f}ms")
        print(f"Median latency: {stats['median']:.3f}ms")
        print(f"Min latency:    {stats['min']:.3f}ms")
        print(f"Max latency:    {stats['max']:.3f}ms")
        print(f"Std deviation:  {stats['stdev']:.3f}ms")
        print("="*60)
        
        # Determine pass/fail
        passed = True
        if stats['max'] > LATENCY_TARGET:
            print(f"✗ FAIL: Max latency {stats['max']:.3f}ms exceeds {LATENCY_TARGET}ms target")
            passed = False
        elif stats['mean'] > LATENCY_IDEAL:
            print(f"✓ PASS (Marginal): Mean {stats['mean']:.3f}ms above ideal {LATENCY_IDEAL}ms")
        else:
            print(f"✓ PASS (Excellent): All metrics within ideal targets!")
        
        if stats['success_rate'] < 100:
            print(f"⚠️  Warning: {100 - stats['success_rate']:.1f}% message loss")
            passed = False
        
        return passed

def main():
    """Run the complete test"""
    
    print("\nStarting OSC latency test between processes...")
    print("This tests control signal speed for our modular synth.\n")
    
    # Make sure we can bind to the port
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_socket.bind((TEST_HOST, TEST_PORT))
        test_socket.close()
    except OSError as e:
        print(f"ERROR: Cannot bind to {TEST_HOST}:{TEST_PORT}")
        print(f"Reason: {e}")
        print("\nTry a different port or wait a moment and retry.")
        return False
    
    tester = OSCLatencyTester()
    stats = tester.run_latency_test()
    
    if stats:
        passed = tester.print_results(stats)
        
        print("\nWhat this means for our synthesizer:")
        if stats['mean'] < 2:
            print("✓ Control signals will feel instantaneous")
            print("✓ LFOs and envelopes will modulate smoothly")
            print("✓ Your commands will execute immediately")
        elif stats['mean'] < 5:
            print("✓ Control signals will be fast enough")
            print("✓ Total latency still under 20ms with audio")
        else:
            print("⚠️  Control might feel sluggish")
            print("⚠️  Need to investigate network configuration")
        
        return passed
    else:
        print("\n✗ Test failed to complete")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)