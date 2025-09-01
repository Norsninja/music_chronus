#!/usr/bin/env python3
"""Debug who's sending SIGTERM to workers."""

import os
import signal
import time
import multiprocessing as mp
import traceback

os.environ['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'

def test_worker(worker_id):
    """Test worker that reports signal info."""
    import os
    import signal
    import sys
    
    def handle_sigterm(signum, frame):
        # Get parent process info
        ppid = os.getppid()
        print(f"Worker {worker_id} (PID {os.getpid()}) received SIGTERM")
        print(f"  Parent PID: {ppid}")
        print(f"  Frame: {frame}")
        print(f"  Stack trace:")
        traceback.print_stack(frame)
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    print(f"Worker {worker_id} started (PID {os.getpid()}, Parent {os.getppid()})")
    
    # Just loop and wait
    counter = 0
    while True:
        time.sleep(0.1)
        counter += 1
        if counter % 10 == 0:
            print(f"Worker {worker_id} still alive (10s)")

# Test 1: Simple process without supervisor
print("=" * 60)
print("TEST 1: Simple worker process")
print("=" * 60)

proc = mp.Process(target=test_worker, args=(99,))
proc.start()
print(f"Main: Started worker, PID {proc.pid}")

# Wait a bit
time.sleep(2)
print(f"Main: Worker alive? {proc.is_alive()}")

if proc.is_alive():
    print("Main: Terminating worker...")
    proc.terminate()
    proc.join()
else:
    print("Main: Worker died on its own!")

print("\n" + "=" * 60)
print("TEST 2: Check for signal inheritance")
print("=" * 60)

# Set up a signal handler in parent to see if it's inherited
def parent_sigterm(signum, frame):
    print("PARENT received SIGTERM!")

signal.signal(signal.SIGTERM, parent_sigterm)

proc2 = mp.Process(target=test_worker, args=(100,))
proc2.start()
print(f"Main: Started worker 2, PID {proc2.pid}")

time.sleep(2)
print(f"Main: Worker 2 alive? {proc2.is_alive()}")

if proc2.is_alive():
    proc2.terminate()
    proc2.join()

print("\nTests complete")