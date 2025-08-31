#!/usr/bin/env python3
"""
IPC-04: Event Synchronization Test
Testing sub-millisecond event synchronization between processes using socketpair + shared memory

Architecture:
- Socketpair for low-latency wakeups (syscall notification)
- Shared memory ring buffer for command payloads (zero-copy data)
- SPSC (Single Producer Single Consumer) lock-free pattern
- Tests under realistic load: 2 DSP workers + 100 OSC msg/sec
"""

import multiprocessing as mp
import socket
import os
import time
import numpy as np
import ctypes
import struct
from statistics import mean, median, stdev, quantiles
from collections import deque
import asyncio
from pythonosc import osc_server, dispatcher
from pythonosc.udp_client import SimpleUDPClient
import threading

# Test configuration
NUM_MEASUREMENTS = 1000  # Number of RTT measurements
DSP_BUFFER_SIZE = 256  # Samples per buffer
DSP_WORKERS = 2  # Number of DSP worker processes
OSC_RATE = 100  # OSC messages per second
RING_BUFFER_SIZE = 64  # Command ring buffer slots

# Set environment variables for thread control
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'


class SPSCRingBuffer:
    """
    Single Producer Single Consumer lock-free ring buffer
    Uses shared memory for zero-copy command passing
    """
    def __init__(self, size, item_size=64):
        self.size = size
        self.item_size = item_size
        
        # Shared memory for ring buffer data
        self.buffer = mp.Array(ctypes.c_char, size * item_size, lock=False)
        
        # Cache-line aligned indices (avoid false sharing)
        self.write_idx = mp.Value(ctypes.c_uint32, 0, lock=False)
        self._pad1 = mp.Array(ctypes.c_char, 60)  # Padding to 64 bytes
        self.read_idx = mp.Value(ctypes.c_uint32, 0, lock=False)
        self._pad2 = mp.Array(ctypes.c_char, 60)  # Padding to 64 bytes
        
    def write(self, data):
        """Producer writes data (returns False if full)"""
        next_write = (self.write_idx.value + 1) % self.size
        if next_write == self.read_idx.value:
            return False  # Buffer full
        
        # Write data to buffer
        offset = self.write_idx.value * self.item_size
        self.buffer[offset:offset + len(data)] = data
        
        # Update write index (memory barrier implicit in mp.Value)
        self.write_idx.value = next_write
        return True
    
    def read(self):
        """Consumer reads data (returns None if empty)"""
        if self.read_idx.value == self.write_idx.value:
            return None  # Buffer empty
        
        # Read data from buffer
        offset = self.read_idx.value * self.item_size
        data = bytes(self.buffer[offset:offset + self.item_size])
        
        # Update read index
        self.read_idx.value = (self.read_idx.value + 1) % self.size
        return data


def dsp_worker(worker_id, stop_event):
    """
    DSP worker process performing real NumPy operations
    Simulates audio processing load
    """
    print(f"   DSP Worker {worker_id} started (PID: {os.getpid()})")
    
    # Pre-allocate buffers
    buffer = np.zeros(DSP_BUFFER_SIZE, dtype=np.float32)
    filter_state = np.zeros(4, dtype=np.float32)  # IIR filter state
    
    # Simple IIR filter coefficients (butterworth lowpass)
    b = np.array([0.0675, 0.135, 0.0675], dtype=np.float32)
    a = np.array([1.0, -1.143, 0.4128], dtype=np.float32)
    
    iteration = 0
    while not stop_event.is_set():
        # Generate test signal
        t = np.arange(iteration * DSP_BUFFER_SIZE, 
                     (iteration + 1) * DSP_BUFFER_SIZE) / 44100.0
        buffer[:] = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        
        # Apply DSP operations (real work)
        # This uses scipy.signal.lfilter algorithm but implemented manually
        # to avoid imports in the worker
        for i in range(DSP_BUFFER_SIZE):
            # Direct Form II implementation
            w = buffer[i] - a[1] * filter_state[0] - a[2] * filter_state[1]
            buffer[i] = b[0] * w + b[1] * filter_state[0] + b[2] * filter_state[1]
            filter_state[1] = filter_state[0]
            filter_state[0] = w
        
        # Add some more operations to simulate realistic load
        buffer *= 0.5  # Gain
        buffer = np.clip(buffer, -1.0, 1.0)  # Limiting
        
        iteration += 1
        # Process at ~172 Hz (44100/256)
        time.sleep(DSP_BUFFER_SIZE / 44100.0)


def osc_background_load(stop_event):
    """
    Generate OSC background traffic at specified rate
    """
    print(f"   OSC Generator started (PID: {os.getpid()})")
    
    # Create OSC client
    client = SimpleUDPClient("127.0.0.1", 8001)
    
    msg_count = 0
    while not stop_event.is_set():
        # Send parameter update message
        param_name = f"param_{msg_count % 10}"
        param_value = np.random.random()
        client.send_message(f"/module/{param_name}", param_value)
        
        msg_count += 1
        time.sleep(1.0 / OSC_RATE)


def measure_socketpair_latency(iterations=NUM_MEASUREMENTS, with_load=True):
    """
    Measure socketpair RTT/2 latency under load
    """
    print("\n=== Testing Socketpair + Shared Memory Pattern ===")
    
    # Create socketpair for signaling
    parent_sock, child_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    
    # Make sockets non-blocking for audio callback simulation
    parent_sock.setblocking(False)
    child_sock.setblocking(False)
    
    # Create ring buffer for commands
    ring_buffer = SPSCRingBuffer(RING_BUFFER_SIZE)
    
    # Start load generators if requested
    stop_event = mp.Event()
    processes = []
    
    if with_load:
        print(f"Starting load generators: {DSP_WORKERS} DSP workers + {OSC_RATE} OSC/sec")
        
        # Start DSP workers
        for i in range(DSP_WORKERS):
            p = mp.Process(target=dsp_worker, args=(i, stop_event))
            p.start()
            processes.append(p)
        
        # Start OSC generator in thread
        osc_thread = threading.Thread(target=osc_background_load, args=(stop_event,))
        osc_thread.daemon = True
        osc_thread.start()
        
        # Let load stabilize
        time.sleep(1.0)
    
    # Measure latencies
    latencies = []
    command_id = 0
    
    def audio_callback_process(child_sock, ring_buffer, ready_event, done_event):
        """
        Simulated audio callback process
        Receives wakeup via socket, reads command from ring buffer
        """
        ready_event.set()
        
        for _ in range(iterations):
            # Wait for wakeup signal (blocking read OK in test)
            child_sock.setblocking(True)
            try:
                wakeup = child_sock.recv(1)
            except:
                break
            
            # Read command from ring buffer (would be non-blocking in real callback)
            cmd_data = ring_buffer.read()
            if cmd_data:
                # Parse command timestamp
                cmd_id, timestamp = struct.unpack('!Qd', cmd_data[:16])
                
                # Send acknowledgment with original timestamp
                ack_data = struct.pack('!Qd', cmd_id, timestamp)
                child_sock.send(ack_data)
        
        done_event.set()
    
    # Start audio callback simulator
    ready_event = mp.Event()
    done_event = mp.Event()
    
    audio_proc = mp.Process(target=audio_callback_process, 
                           args=(child_sock, ring_buffer, ready_event, done_event))
    audio_proc.start()
    ready_event.wait()
    
    print(f"Measuring {iterations} round-trips...")
    
    # Perform measurements
    for i in range(iterations):
        # Prepare command
        timestamp = time.perf_counter()
        cmd_data = struct.pack('!Qd', command_id, timestamp)
        cmd_data += b'\x00' * (ring_buffer.item_size - len(cmd_data))  # Pad to item size
        
        # Write command to ring buffer
        if not ring_buffer.write(cmd_data):
            print(f"   Warning: Ring buffer full at iteration {i}")
            continue
        
        # Send wakeup signal
        parent_sock.send(b'!')
        
        # Wait for acknowledgment
        parent_sock.setblocking(True)
        parent_sock.settimeout(0.01)  # 10ms timeout
        try:
            ack_data = parent_sock.recv(16)
            ack_id, orig_timestamp = struct.unpack('!Qd', ack_data)
            
            # Calculate RTT/2
            rtt = time.perf_counter() - orig_timestamp
            latency = rtt / 2.0
            latencies.append(latency * 1000)  # Convert to ms
            
        except socket.timeout:
            print(f"   Warning: Timeout at iteration {i}")
        
        command_id += 1
        
        # Small delay between measurements
        time.sleep(0.001)
    
    # Stop load generators
    if with_load:
        stop_event.set()
        for p in processes:
            p.join(timeout=2)
            if p.is_alive():
                p.terminate()
    
    # Wait for audio process
    done_event.wait(timeout=2)
    audio_proc.join(timeout=1)
    if audio_proc.is_alive():
        audio_proc.terminate()
    
    # Close sockets
    parent_sock.close()
    child_sock.close()
    
    return latencies


def test_alternative_primitives():
    """
    Test alternative IPC primitives for comparison
    Note: Queue is not suitable for hot paths due to blocking nature
    """
    print("\n=== Testing Alternative IPC Primitives ===")
    results = {}
    
    # Test Queue (multiprocessing.Queue) - limited samples due to blocking
    print("\nTesting mp.Queue (limited sample for comparison only)...")
    q = mp.Queue()
    latencies = []
    test_iterations = 20  # Reduced iterations to avoid timeout
    
    def queue_consumer(q, iterations):
        for _ in range(iterations):
            try:
                data = q.get(timeout=0.1)  # Add timeout to prevent hanging
                timestamp = data['timestamp']
                q.put({'timestamp': timestamp, 'ack': True})
            except:
                break
    
    proc = mp.Process(target=queue_consumer, args=(q, test_iterations))
    proc.start()
    
    for i in range(test_iterations):
        timestamp = time.perf_counter()
        q.put({'timestamp': timestamp, 'id': i})
        try:
            ack = q.get(timeout=0.1)  # Add timeout
            latency = (time.perf_counter() - ack['timestamp']) / 2.0
            latencies.append(latency * 1000)
        except:
            print(f"   Queue timeout at iteration {i}")
            break
    
    proc.join(timeout=1)
    if proc.is_alive():
        proc.terminate()
    
    if latencies:
        results['Queue (not for hot path)'] = {
            'p50': median(latencies),
            'p95': quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies),
            'p99': quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies)
        }
    
    # Test Pipe (multiprocessing.Pipe)
    print("Testing mp.Pipe...")
    parent_conn, child_conn = mp.Pipe()
    latencies = []
    
    def pipe_consumer(conn, iterations):
        for _ in range(iterations):
            if conn.poll(timeout=0.1):  # Check if data available
                data = conn.recv()
                conn.send(data)
            else:
                break
    
    proc = mp.Process(target=pipe_consumer, args=(child_conn, 100))
    proc.start()
    
    for i in range(100):
        timestamp = time.perf_counter()
        parent_conn.send({'timestamp': timestamp, 'id': i})
        if parent_conn.poll(timeout=0.1):  # Wait for response
            ack = parent_conn.recv()
            latency = (time.perf_counter() - ack['timestamp']) / 2.0
            latencies.append(latency * 1000)
        else:
            print(f"   Pipe timeout at iteration {i}")
            break
    
    proc.join(timeout=1)
    if proc.is_alive():
        proc.terminate()
    
    if latencies:
        results['Pipe'] = {
            'p50': median(latencies),
            'p95': quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies),
            'p99': quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies)
        }
    
    return results


def main():
    """
    Run IPC-04 Event Synchronization Test
    """
    print("IPC-04: Event Synchronization Test")
    print("=" * 50)
    
    # Test without load first (baseline)
    print("\n### Baseline Test (No Load) ###")
    baseline_latencies = measure_socketpair_latency(iterations=100, with_load=False)
    
    if baseline_latencies:
        print(f"\nBaseline Results:")
        print(f"   p50: {median(baseline_latencies):.3f}ms")
        print(f"   p95: {quantiles(baseline_latencies, n=20)[18]:.3f}ms")
        print(f"   p99: {quantiles(baseline_latencies, n=100)[98]:.3f}ms")
        print(f"   mean: {mean(baseline_latencies):.3f}ms")
        print(f"   stdev: {stdev(baseline_latencies) if len(baseline_latencies) > 1 else 0:.3f}ms")
    
    # Test under load (main test)
    print("\n### Main Test (Under Load) ###")
    loaded_latencies = measure_socketpair_latency(iterations=NUM_MEASUREMENTS, with_load=True)
    
    if loaded_latencies:
        p50 = median(loaded_latencies)
        p95 = quantiles(loaded_latencies, n=20)[18]
        p99 = quantiles(loaded_latencies, n=100)[98]
        jitter = stdev(loaded_latencies) if len(loaded_latencies) > 1 else 0
        
        print(f"\nResults Under Load:")
        print(f"   p50: {p50:.3f}ms")
        print(f"   p95: {p95:.3f}ms")
        print(f"   p99: {p99:.3f}ms")
        print(f"   mean: {mean(loaded_latencies):.3f}ms")
        print(f"   jitter (stdev): {jitter:.3f}ms")
        print(f"   min: {min(loaded_latencies):.3f}ms")
        print(f"   max: {max(loaded_latencies):.3f}ms")
        
        # Check against spec requirements (Python targets)
        print("\n### Specification Validation (Python Targets) ###")
        print(f"   p50 < 0.10ms: {'✅ PASS' if p50 < 0.10 else '❌ FAIL'} ({p50:.3f}ms)")
        print(f"   p95 < 0.25ms: {'✅ PASS' if p95 < 0.25 else '❌ FAIL'} ({p95:.3f}ms)")
        print(f"   p99 < 0.5ms:  {'✅ PASS' if p99 < 0.5 else '❌ FAIL'} ({p99:.3f}ms)")
        print(f"   jitter < 0.1ms: {'✅ PASS' if jitter < 0.1 else '❌ FAIL'} ({jitter:.3f}ms)")
    
    # Compare with alternatives
    print("\n### Comparison with Alternative Primitives ###")
    alt_results = test_alternative_primitives()
    
    print("\nComparative Results:")
    print(f"{'Primitive':<15} {'p50 (ms)':<12} {'p95 (ms)':<12} {'p99 (ms)':<12}")
    print("-" * 51)
    
    # Add socketpair results
    if loaded_latencies:
        print(f"{'Socketpair':<15} {p50:<12.3f} {p95:<12.3f} {p99:<12.3f} ⭐")
    
    # Add alternative results
    for name, metrics in alt_results.items():
        print(f"{name:<15} {metrics['p50']:<12.3f} {metrics['p95']:<12.3f} {metrics['p99']:<12.3f}")
    
    # Final summary
    print("\n" + "=" * 50)
    if loaded_latencies and p50 < 0.10 and p95 < 0.25 and p99 < 0.5 and jitter < 0.1:
        print("✅ IPC-04 TEST PASSED - All Python target criteria met!")
        print("Note: For C extension implementation, tighter targets apply (p50 < 0.05ms)")
    else:
        print("❌ IPC-04 TEST FAILED - Some criteria not met")
        print("\nAnalysis needed for any failures above.")


if __name__ == "__main__":
    main()