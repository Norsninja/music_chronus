#!/usr/bin/env python3
"""
Minimal supervisor to test ring buffer theory
Implements Senior Dev's timing recommendations
"""

import numpy as np
import sounddevice as sd
import time
import multiprocessing as mp
from multiprocessing import shared_memory
import signal
import sys

# Configuration
SAMPLE_RATE = 48000
BUFFER_SIZE = 512
NUM_BUFFERS = 8
PREFILL_BUFFERS = 4
LEAD_TARGET = 3
MAX_CATCHUP = 2

class SimpleRing:
    """Minimal ring buffer with occupancy tracking"""
    def __init__(self, num_buffers, buffer_size):
        self.num_buffers = num_buffers
        self.buffer_size = buffer_size
        self.buffers = [np.zeros(buffer_size, dtype=np.float32) for _ in range(num_buffers)]
        self.write_idx = 0
        self.read_idx = 0
        self.occupancy = 0
        self.lock = mp.Lock()
        
    def write(self, data):
        with self.lock:
            if self.occupancy >= self.num_buffers:
                return False  # Full
            np.copyto(self.buffers[self.write_idx], data)
            self.write_idx = (self.write_idx + 1) % self.num_buffers
            self.occupancy += 1
            return True
            
    def read(self):
        with self.lock:
            if self.occupancy == 0:
                return None  # Empty
            data = self.buffers[self.read_idx].copy()
            self.read_idx = (self.read_idx + 1) % self.num_buffers
            self.occupancy -= 1
            return data
            
    def get_occupancy(self):
        with self.lock:
            return self.occupancy

def producer_process(ring, stop_event):
    """Producer with deadline-based timing and catch-up"""
    print(f"Producer starting...")
    
    # Simple sine generator
    sample_rate = SAMPLE_RATE
    buffer_size = BUFFER_SIZE
    freq = 440.0
    phase = 0.0
    phase_inc = 2 * np.pi * freq / sample_rate
    
    buffer = np.zeros(buffer_size, dtype=np.float32)
    buffer_period = buffer_size / sample_rate
    
    # Prefill ring
    print(f"Prefilling {PREFILL_BUFFERS} buffers...")
    for _ in range(PREFILL_BUFFERS):
        for i in range(buffer_size):
            buffer[i] = np.sin(phase) * 0.5
            phase += phase_inc
            if phase > 2 * np.pi:
                phase -= 2 * np.pi
        ring.write(buffer)
    
    # Start deadline-based production
    next_deadline = time.monotonic()
    buffers_produced = 0
    
    while not stop_event.is_set():
        now = time.monotonic()
        
        # Check if we need to produce
        if now >= next_deadline:
            # Check occupancy for catch-up
            occupancy = ring.get_occupancy()
            
            # Determine how many buffers to produce
            if occupancy < LEAD_TARGET:
                # Need catch-up
                buffers_to_produce = min(MAX_CATCHUP, LEAD_TARGET - occupancy + 1)
            else:
                buffers_to_produce = 1
            
            # Produce buffers
            for _ in range(buffers_to_produce):
                for i in range(buffer_size):
                    buffer[i] = np.sin(phase) * 0.5
                    phase += phase_inc
                    if phase > 2 * np.pi:
                        phase -= 2 * np.pi
                
                if ring.write(buffer):
                    buffers_produced += 1
                else:
                    print(f"Ring full! Occupancy: {occupancy}")
            
            # Update deadline (Senior Dev's formula)
            next_deadline = max(next_deadline, now) + buffer_period
            
            # Periodic status
            if buffers_produced % 100 == 0:
                print(f"Produced: {buffers_produced}, Occupancy: {occupancy}")
        
        # Small sleep to avoid busy-wait
        time.sleep(0.0001)
    
    print(f"Producer stopped. Total produced: {buffers_produced}")

def main():
    """Main supervisor with improved timing"""
    print("MINIMAL TEST SUPERVISOR")
    print("=" * 50)
    print(f"Sample rate: {SAMPLE_RATE}")
    print(f"Buffer size: {BUFFER_SIZE}")
    print(f"Prefill: {PREFILL_BUFFERS}")
    print(f"Lead target: {LEAD_TARGET}")
    print()
    
    # Create shared ring buffer
    manager = mp.Manager()
    ring = manager.Namespace()
    ring.buffers = manager.list([manager.list([0.0]*BUFFER_SIZE) for _ in range(NUM_BUFFERS)])
    ring.write_idx = 0
    ring.read_idx = 0
    ring.occupancy = 0
    ring.lock = manager.Lock()
    
    # Simplified ring operations
    class ManagedRing:
        def __init__(self, ring_ns):
            self.ring = ring_ns
            
        def write(self, data):
            with self.ring.lock:
                if self.ring.occupancy >= NUM_BUFFERS:
                    return False
                for i, val in enumerate(data):
                    self.ring.buffers[self.ring.write_idx][i] = float(val)
                self.ring.write_idx = (self.ring.write_idx + 1) % NUM_BUFFERS
                self.ring.occupancy += 1
                return True
                
        def read(self):
            with self.ring.lock:
                if self.ring.occupancy == 0:
                    return None
                data = np.array(self.ring.buffers[self.ring.read_idx], dtype=np.float32)
                self.ring.read_idx = (self.ring.read_idx + 1) % NUM_BUFFERS
                self.ring.occupancy -= 1
                return data
                
        def get_occupancy(self):
            with self.ring.lock:
                return self.ring.occupancy
    
    managed_ring = ManagedRing(ring)
    
    # Start producer
    stop_event = mp.Event()
    producer = mp.Process(target=producer_process, args=(managed_ring, stop_event))
    producer.start()
    
    # Wait for prefill
    time.sleep(0.1)
    
    # Audio callback tracking
    callbacks = 0
    none_reads = 0
    last_report_time = time.time()
    
    def audio_callback(outdata, frames, time_info, status):
        nonlocal callbacks, none_reads, last_report_time
        
        callbacks += 1
        buffer = managed_ring.read()
        
        if buffer is None:
            none_reads += 1
            outdata[:] = 0  # Silence
        else:
            outdata[:, 0] = buffer  # Left
            outdata[:, 1] = buffer  # Right
        
        # Report once per second
        now = time.time()
        if now - last_report_time > 1.0:
            occupancy = managed_ring.get_occupancy()
            print(f"Callbacks: {callbacks}, None reads: {none_reads}, Occupancy: {occupancy}")
            last_report_time = now
    
    # Start audio
    print("Starting audio stream...")
    stream = sd.OutputStream(
        callback=audio_callback,
        samplerate=SAMPLE_RATE,
        blocksize=BUFFER_SIZE,
        channels=2,
        dtype='float32'
    )
    
    with stream:
        print("Playing... Press Ctrl+C to stop")
        print()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
    
    # Cleanup
    stop_event.set()
    producer.join(timeout=2)
    if producer.is_alive():
        producer.terminate()
    
    print(f"\nFinal stats:")
    print(f"Total callbacks: {callbacks}")
    print(f"None reads: {none_reads} ({100*none_reads/callbacks:.1f}%)")
    print(f"Final occupancy: {managed_ring.get_occupancy()}")

if __name__ == "__main__":
    main()