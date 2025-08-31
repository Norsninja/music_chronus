#!/usr/bin/env python3
"""
IPC-03: Shared Memory Audio Transfer Test
Testing zero-copy audio transfer between processes using shared memory

Based on research showing mp.Array with np.frombuffer for zero-copy access
"""

import multiprocessing as mp
import ctypes
import numpy as np
import time
import psutil
import os
from statistics import mean, stdev

# Audio configuration
SAMPLE_RATE = 44100
BUFFER_SIZE = 256  # samples per buffer
NUM_BUFFERS = 100  # how many buffers to test
CHANNELS = 1

def producer_process(shared_arr, ready_event, done_event, num_buffers):
    """
    Producer process that generates audio and writes to shared memory.
    This simulates a VCO or other audio-generating module.
    """
    print(f"   Producer started (PID: {os.getpid()})")
    
    # Get NumPy view of shared memory (zero-copy!)
    # When passed to subprocess, shared_arr is already the raw array
    audio_buffer = np.frombuffer(shared_arr, dtype=np.float32)
    audio_buffer = audio_buffer.reshape(-1, BUFFER_SIZE)
    
    # Generate test audio (different frequency sines)
    for buffer_idx in range(num_buffers):
        # Generate a sine wave
        freq = 440 + buffer_idx * 10  # Vary frequency
        t = np.linspace(
            buffer_idx * BUFFER_SIZE / SAMPLE_RATE,
            (buffer_idx + 1) * BUFFER_SIZE / SAMPLE_RATE,
            BUFFER_SIZE,
            endpoint=False
        )
        samples = 0.5 * np.sin(2 * np.pi * freq * t).astype(np.float32)
        
        # Write to shared memory (no lock needed for single writer)
        buffer_row = buffer_idx % audio_buffer.shape[0]
        audio_buffer[buffer_row, :] = samples
        
        # Signal that buffer is ready
        ready_event.set()
        
        # Simulate real-time (5.8ms per buffer at 44.1kHz)
        time.sleep(BUFFER_SIZE / SAMPLE_RATE)
    
    done_event.set()
    print(f"   Producer finished")

def consumer_process(shared_arr, ready_event, done_event, result_queue):
    """
    Consumer process that reads audio from shared memory.
    This simulates the Audio Server reading from modules.
    """
    print(f"   Consumer started (PID: {os.getpid()})")
    
    # Get NumPy view of shared memory (zero-copy!)
    # When passed to subprocess, shared_arr is already the raw array
    audio_buffer = np.frombuffer(shared_arr, dtype=np.float32)
    audio_buffer = audio_buffer.reshape(-1, BUFFER_SIZE)
    
    transfer_times = []
    buffers_read = 0
    
    while not done_event.is_set() or ready_event.is_set():
        # Wait for producer to signal
        if ready_event.wait(timeout=0.1):
            start_time = time.perf_counter()
            
            # Read from shared memory (zero-copy access)
            buffer_row = buffers_read % audio_buffer.shape[0]
            samples = audio_buffer[buffer_row, :]  # This is a view, not a copy!
            
            # Verify we got valid audio (non-zero)
            if np.any(samples != 0):
                buffers_read += 1
                
                # Measure transfer time
                transfer_time = time.perf_counter() - start_time
                transfer_times.append(transfer_time * 1000)  # Convert to ms
            
            ready_event.clear()
    
    # Send results back
    result_queue.put({
        'buffers_read': buffers_read,
        'transfer_times': transfer_times
    })
    print(f"   Consumer finished")

def test_zero_copy_verification():
    """Verify that shared memory is truly zero-copy"""
    
    print("\n1. Testing zero-copy property...")
    
    # Create shared memory
    size = BUFFER_SIZE * 10  # Small test
    shared_arr = mp.Array(ctypes.c_float, size)
    
    # Get NumPy views
    arr1 = np.frombuffer(shared_arr.get_obj(), dtype=np.float32)
    arr2 = np.frombuffer(shared_arr.get_obj(), dtype=np.float32)
    
    # Modify through one view
    arr1[0] = 42.0
    
    # Check if visible through other view (proves zero-copy)
    if arr2[0] == 42.0:
        print("   ✓ Zero-copy verified: Changes visible immediately")
        
        # Check memory addresses
        if arr1.__array_interface__['data'][0] == arr2.__array_interface__['data'][0]:
            print("   ✓ Same memory address confirmed")
        return True
    else:
        print("   ✗ Not zero-copy!")
        return False

def test_shared_memory_audio():
    """Main test for shared memory audio transfer"""
    
    print("\n" + "="*60)
    print("IPC-03: SHARED MEMORY AUDIO TRANSFER TEST")
    print("="*60)
    print(f"Buffer size: {BUFFER_SIZE} samples")
    print(f"Testing {NUM_BUFFERS} buffers")
    print("="*60)
    
    # First verify zero-copy
    if not test_zero_copy_verification():
        return False
    
    print("\n2. Testing audio transfer between processes...")
    
    # Create shared memory for audio
    # Using circular buffer pattern (10 buffers)
    buffer_rows = 10
    shared_size = buffer_rows * BUFFER_SIZE
    shared_arr = mp.Array(ctypes.c_float, shared_size, lock=False)  # No lock needed
    
    # Create synchronization events
    ready_event = mp.Event()
    done_event = mp.Event()
    result_queue = mp.Queue()
    
    # Get initial memory usage
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Start producer and consumer processes
    producer = mp.Process(
        target=producer_process,
        args=(shared_arr, ready_event, done_event, NUM_BUFFERS)
    )
    consumer = mp.Process(
        target=consumer_process,
        args=(shared_arr, ready_event, done_event, result_queue)
    )
    
    print("   Starting processes...")
    start_time = time.perf_counter()
    
    producer.start()
    consumer.start()
    
    # Wait for completion
    producer.join()
    consumer.join()
    
    elapsed_time = time.perf_counter() - start_time
    
    # Get results
    results = result_queue.get()
    
    # Check memory usage (should not have duplicated)
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory
    
    print(f"\n3. Analyzing results...")
    print(f"   Buffers transferred: {results['buffers_read']}/{NUM_BUFFERS}")
    print(f"   Total time: {elapsed_time:.2f}s")
    print(f"   Memory increase: {memory_increase:.1f}MB")
    
    # Calculate statistics
    if results['transfer_times']:
        transfer_stats = {
            'mean': mean(results['transfer_times']),
            'min': min(results['transfer_times']),
            'max': max(results['transfer_times']),
            'stdev': stdev(results['transfer_times']) if len(results['transfer_times']) > 1 else 0
        }
        
        print("\n" + "="*60)
        print("RESULTS:")
        print("-"*60)
        print(f"Transfer Statistics (per {BUFFER_SIZE}-sample buffer):")
        print(f"  Mean:  {transfer_stats['mean']:.4f}ms")
        print(f"  Min:   {transfer_stats['min']:.4f}ms")
        print(f"  Max:   {transfer_stats['max']:.4f}ms")
        print(f"  StDev: {transfer_stats['stdev']:.4f}ms")
        print("-"*60)
        
        # Pass/Fail
        success = True
        if results['buffers_read'] < NUM_BUFFERS:
            print(f"⚠️  Warning: Only {results['buffers_read']}/{NUM_BUFFERS} buffers transferred")
            success = False
        
        if transfer_stats['mean'] > 0.1:  # 0.1ms target
            print(f"⚠️  Transfer overhead {transfer_stats['mean']:.4f}ms above 0.1ms target")
            success = False
        else:
            print(f"✓ PASS: Transfer overhead {transfer_stats['mean']:.4f}ms is excellent!")
        
        if memory_increase > 10:  # Should not duplicate memory
            print(f"⚠️  Memory increased by {memory_increase:.1f}MB (possible copying)")
        else:
            print(f"✓ Zero-copy confirmed: Minimal memory increase ({memory_increase:.1f}MB)")
        
        print("="*60)
        
        return success
    else:
        print("✗ No transfer times recorded")
        return False

def main():
    """Run the complete test suite"""
    
    print("\nStarting shared memory audio transfer test...")
    print("This tests how audio flows from modules to the Audio Server.\n")
    
    success = test_shared_memory_audio()
    
    if success:
        print("\n✓ IPC-03 PASSED: Shared memory audio transfer works!")
        print("\nWhat this means for our synth:")
        print("• Audio can flow between modules with near-zero overhead")
        print("• No memory copying means low CPU usage")
        print("• Multiple oscillators can run in parallel efficiently")
    else:
        print("\n✗ IPC-03 FAILED: Issues with shared memory transfer")
    
    return success

if __name__ == "__main__":
    # Set start method for multiprocessing
    mp.set_start_method('spawn', force=True)
    
    success = main()
    exit(0 if success else 1)