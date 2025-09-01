#!/usr/bin/env python3
"""
AudioSupervisor v2 - Slot-Based Architecture
Implements Senior Dev's recommended approach:
1. Rings tied to slots (slot0/slot1), not workers
2. Workers move between slots on failover  
3. Audio callback switches which slot to read from
4. Commands broadcast or routed to active slot
5. No ring swapping - preserves worker-ring relationship
"""

import multiprocessing as mp
import numpy as np
import sounddevice as sd
import time
import signal
import os
import sys
from pythonosc import dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
import threading
from struct import pack

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import validated ring classes from supervisor.py
from .supervisor import CommandRing

# Import our modules
from .module_host import ModuleHost, pack_command_v2, unpack_command_v2, CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL
from .modules.simple_sine import SimpleSine
from .modules.adsr import ADSR
from .modules.biquad_filter import BiquadFilter

# Audio configuration
SAMPLE_RATE = 44100
BUFFER_SIZE = 256
NUM_CHANNELS = 1
NUM_BUFFERS = 8  # Senior Dev's recommendation

# Ring buffer configuration
COMMAND_RING_SLOTS = 32

# Heartbeat monitoring (with relaxed timeout as proven in surgical)
HEARTBEAT_TIMEOUT = 0.05  # 50ms relaxed timeout
STARTUP_GRACE_PERIOD = 1.0  # 1 second grace period for heartbeat detection


class AudioRing:
    """
    Sequential audio ring buffer from supervisor_v2_surgical.py
    Fixed to read sequentially, not skip buffers
    """
    
    def __init__(self, num_buffers=NUM_BUFFERS):
        self.num_buffers = num_buffers
        self.buffer_size = BUFFER_SIZE
        
        # Shared memory indices
        self.head = mp.Value('i', 0, lock=False)
        self.tail = mp.Value('i', 0, lock=False)
        
        # Pre-allocate numpy array in shared memory
        self.data = mp.Array('f', num_buffers * BUFFER_SIZE, lock=False)
        self.np_data = np.frombuffer(self.data, dtype=np.float32).reshape(num_buffers, BUFFER_SIZE)
        
        # Pre-allocate individual buffer views
        self.buffers = [self.np_data[i] for i in range(num_buffers)]
    
    def write(self, audio_data):
        """Producer writes next buffer"""
        next_head = (self.head.value + 1) % self.num_buffers
        
        # Check if full
        if next_head == self.tail.value:
            # Ring full - drop frame
            return False
        
        # Copy data to buffer
        idx = self.head.value
        np.copyto(self.buffers[idx], audio_data[:BUFFER_SIZE])
        
        # Update head
        self.head.value = next_head
        return True
    
    def read_latest(self):
        """
        Consumer reads next buffer SEQUENTIALLY (Senior Dev's fix)
        No skipping - reads each buffer in order
        """
        # Check if empty
        if self.head.value == self.tail.value:
            return None
        
        # Read from tail sequentially
        idx = self.tail.value
        buffer = self.buffers[idx].copy()  # Return copy to avoid races
        
        # Advance tail by ONE (sequential reading)
        self.tail.value = (self.tail.value + 1) % self.num_buffers
        
        return buffer
    
    def reset(self):
        """Reset to empty state"""
        self.head.value = 0
        self.tail.value = 0


def worker_process(slot_id, audio_ring, command_ring, heartbeat_array, event, shutdown_flag):
    """Worker process with diagnostic logging"""
    
    # DIAGNOSTIC: Log worker start
    print(f"[WORKER] Slot {slot_id} starting, PID={os.getpid()}")
    
    # Set up signal handling
    def handle_sigterm(signum, frame):
        print(f"Worker {slot_id} received SIGTERM")
        shutdown_flag.set()
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    # Initialize module host
    module_host = ModuleHost(SAMPLE_RATE, BUFFER_SIZE)
    
    # Create modular chain
    sine_module = SimpleSine(SAMPLE_RATE, BUFFER_SIZE, module_id='sine')
    adsr_module = ADSR(SAMPLE_RATE, BUFFER_SIZE, module_id='adsr')
    filter_module = BiquadFilter(SAMPLE_RATE, BUFFER_SIZE, module_id='filter')
    
    # Register modules (chain order)
    module_host.register_module(sine_module)
    module_host.register_module(adsr_module)
    module_host.register_module(filter_module)
    
    # Buffer for output
    output_buffer = np.zeros(BUFFER_SIZE, dtype=np.float32)
    
    # Timing for buffer production
    last_buffer_time = time.monotonic()
    buffer_period = BUFFER_SIZE / SAMPLE_RATE
    next_buffer_time = last_buffer_time + buffer_period
    
    # Stats
    buffers_produced = 0
    sequence_num = 0
    
    # First heartbeat
    sequence_num += 1
    heartbeat_array[slot_id] = sequence_num
    print(f"[WORKER] Slot {slot_id} first heartbeat: seq={sequence_num}")
    
    while not shutdown_flag.is_set():
        try:
            # Check for commands (non-blocking)
            if event.wait(timeout=0.001):
                event.clear()
                
                # Process all pending commands
                while True:
                    cmd_bytes = command_ring.read()
                    if cmd_bytes is None:
                        break
                    
                    try:
                        op, dtype, module_id, param, value = unpack_command_v2(cmd_bytes)
                        
                        if op == CMD_OP_SET and dtype == CMD_TYPE_FLOAT:
                            module_host.set_parameter(module_id, param, value)
                        elif op == CMD_OP_GATE and dtype == CMD_TYPE_BOOL:
                            module_host.send_gate(module_id, param, value)
                    except Exception as e:
                        pass  # Ignore unpacking errors
            
            # Produce audio buffer at correct rate
            current_time = time.monotonic()
            if current_time >= next_buffer_time - 0.001:  # 1ms early is OK
                # Process module chain
                module_host.process(output_buffer)
                
                # Write to ring
                if audio_ring.write(output_buffer):
                    buffers_produced += 1
                
                # Update heartbeat with sequence number
                sequence_num += 1
                heartbeat_array[slot_id] = sequence_num
                
                # Calculate next buffer time
                next_buffer_time += buffer_period
                
                # Prevent drift - if we're way behind, reset
                if next_buffer_time < current_time - 0.1:
                    next_buffer_time = current_time + buffer_period
                
                # Diagnostic output
                if buffers_produced % 500 == 0:
                    rms = np.sqrt(np.mean(output_buffer**2))
                    print(f"[DIAG] Slot {slot_id}: seq={sequence_num}, RMS={rms:.6f}")
            
            # Small sleep to prevent CPU spinning
            sleep_time = next_buffer_time - time.monotonic()
            if sleep_time > 0.001:
                time.sleep(min(sleep_time, 0.001))
                
        except Exception as e:
            print(f"[WORKER] Slot {slot_id} error: {e}")
            break
    
    print(f"[WORKER] Slot {slot_id} shutting down")


class AudioSupervisor:
    """Audio supervisor with slot-based failover"""
    
    def __init__(self):
        # Ensure forkserver start method (done safely)
        if mp.get_start_method(allow_none=True) != 'forkserver':
            try:
                mp.set_start_method('forkserver', force=True)
            except RuntimeError:
                pass  # Already set
        
        # Ring buffers - tied to slots, not workers
        self.slot0_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
        self.slot0_cmd_ring = CommandRing(num_slots=COMMAND_RING_SLOTS)
        self.slot1_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
        self.slot1_cmd_ring = CommandRing(num_slots=COMMAND_RING_SLOTS)
        
        # Events - tied to slots
        self.slot0_event = mp.Event()
        self.slot1_event = mp.Event()
        
        # Workers - can move between slots
        self.slot0_worker = None
        self.slot1_worker = None
        
        # Heartbeat monitoring
        self.heartbeat_array = mp.Array('i', [0, 0])
        
        # Shutdown flags - tied to slots
        self.slot0_shutdown = mp.Event()
        self.slot1_shutdown = mp.Event()
        
        # Spawn slot0 worker (initially active)
        self.slot0_shutdown.clear()
        self.slot0_event.clear()
        self.heartbeat_array[0] = 0
        
        self.slot0_worker = mp.Process(
            target=worker_process,
            args=(0, self.slot0_audio_ring, self.slot0_cmd_ring,
                  self.heartbeat_array, self.slot0_event, self.slot0_shutdown)
        )
        self.slot0_worker.start()
        
        # Active tracking
        self.active_idx = 0  # Start with slot0
        self.active_ring = self.slot0_audio_ring
        
        # Failover state
        self.pending_switch = False
        self.target_idx = None
        self.target_ring = None
        
        # SENIOR DEV'S FIX: Track post-switch cleanup
        self.post_switch_cleanup_pending = False
        self.failed_slot = None  # Which slot failed
        
        # Standby readiness
        self.standby_ready = False
        
        # Metrics
        self.metrics = type('Metrics', (), {
            'buffers_processed': 0,
            'switches_performed': 0,
            'none_reads': 0,
            'commands_sent': 0,
            'failover_count': 0,
            'last_failover_ms': 0
        })()
        
        # Audio callback state
        self.last_good = np.zeros(BUFFER_SIZE, dtype=np.float32)
        self.none_count = 0  # Track None reads
        
        # Monitor thread
        self.monitor_stop = threading.Event()
        self.monitor_thread = threading.Thread(target=self.monitor_workers, daemon=True)
        
        # OSC server
        self.osc_server = None
        self.osc_thread = None
        
        # Diagnostic tracking
        self.last_diag_time = time.monotonic()
        
        # Startup timestamp
        self.startup_time = time.monotonic()
        
        # Track worker spawn time for grace period
        self.slot0_spawn_time = self.startup_time
        self.slot1_spawn_time = None
        
        # Spawn slot1 worker (initially standby)
        self.spawn_slot1_worker()
    
    def spawn_slot1_worker(self):
        """Spawn slot1 worker (standby)"""
        self.standby_ready = False
        self.slot1_spawn_time = time.monotonic()
        
        self.slot1_shutdown.clear()
        self.slot1_event.clear()
        self.heartbeat_array[1] = 0
        
        self.slot1_worker = mp.Process(
            target=worker_process,
            args=(1, self.slot1_audio_ring, self.slot1_cmd_ring,
                  self.heartbeat_array, self.slot1_event, self.slot1_shutdown)
        )
        self.slot1_worker.start()
        
        print("[SPAWN] New slot1 worker spawned")
    
    def audio_callback(self, outdata, frames, time_info, status):
        """Real-time audio callback - Senior Dev's approved version"""
        if status:
            print(f"[AUDIO] Status: {status}")
        
        # SENIOR DEV'S FIX: Handle pending switch at buffer boundary
        if self.pending_switch and self.target_idx is not None:
            # Perform the switch
            self.active_idx = self.target_idx
            self.active_ring = self.target_ring
            self.pending_switch = False
            
            # Mark for post-switch cleanup
            self.post_switch_cleanup_pending = True
            
            print(f"[SWITCH] Completed switch to slot {self.active_idx}")
            self.metrics.switches_performed += 1
        
        # Read from active ring
        buffer = self.active_ring.read_latest()
        
        if buffer is not None:
            # Good buffer - use it and save as last_good
            np.copyto(self.last_good, buffer)
            outdata[:] = buffer.reshape(-1, 1)
        else:
            # No buffer available - use last_good to avoid discontinuity
            outdata[:] = self.last_good.reshape(-1, 1)
            self.none_count += 1
            self.metrics.none_reads += 1
        
        self.metrics.buffers_processed += 1
        
        # Diagnostic output
        if os.environ.get('CHRONUS_VERBOSE'):
            current_time = time.monotonic()
            if current_time - self.last_diag_time > 1.0:
                if buffer is not None:
                    rms = np.sqrt(np.mean(buffer**2))
                else:
                    rms = np.sqrt(np.mean(self.last_good**2))
                print(f"[DIAG] Callback: idx={self.active_idx}, buffers={self.metrics.buffers_processed}, " +
                      f"none_reads={self.none_count}, RMS={rms:.6f}")
                self.last_diag_time = current_time
    
    def monitor_workers(self):
        """
        Monitor thread with STARTUP GRACE PERIOD
        """
        print("[MONITOR] Monitor thread started (slot-based version)")
        
        # Initialize tracking
        last_heartbeats = [0, 0]
        last_heartbeat_times = [time.monotonic(), time.monotonic()]
        
        while not self.monitor_stop.is_set():
            try:
                current_time = time.monotonic()
                
                # SENIOR DEV'S FIX: Handle post-switch cleanup
                if self.post_switch_cleanup_pending:
                    self.perform_post_switch_cleanup()
                    self.post_switch_cleanup_pending = False
                
                # Check process sentinel first (always, no grace period)
                for slot in [0, 1]:
                    worker = self.slot0_worker if slot == 0 else self.slot1_worker
                    spawn_time = self.slot0_spawn_time if slot == 0 else self.slot1_spawn_time
                    
                    if worker and hasattr(worker, 'sentinel'):
                        if not worker.is_alive():
                            detection_time = time.monotonic_ns()
                            
                            # Only switch if this is the active slot
                            if slot == self.active_idx and not self.pending_switch:
                                self.handle_slot_failure(slot, detection_time)
                            elif slot != self.active_idx:
                                # Standby died - just log it
                                print(f"[MONITOR] Standby slot {slot} died (non-critical)")
                
                # Check heartbeats (with grace period)
                for slot in [0, 1]:
                    spawn_time = self.slot0_spawn_time if slot == 0 else self.slot1_spawn_time
                    
                    # SENIOR DEV'S FIX: Grace period for new workers
                    if spawn_time and (current_time - spawn_time) < STARTUP_GRACE_PERIOD:
                        # During grace period - just track heartbeat
                        current_hb = self.heartbeat_array[slot]
                        if current_hb != last_heartbeats[slot]:
                            if os.environ.get('CHRONUS_VERBOSE'):
                                print(f"[MONITOR] Slot {slot} heartbeat update during grace: {current_hb}")
                            last_heartbeats[slot] = current_hb
                            last_heartbeat_times[slot] = current_time
                        continue
                    
                    # After grace period - check for timeouts
                    current_hb = self.heartbeat_array[slot]
                    
                    if current_hb != last_heartbeats[slot]:
                        # Heartbeat updated
                        last_heartbeats[slot] = current_hb
                        last_heartbeat_times[slot] = current_time
                        
                        # Check if standby is ready
                        if slot != self.active_idx and not self.standby_ready:
                            if current_hb > 1:  # Has produced at least one buffer
                                self.standby_ready = True
                                print("[MONITOR] Standby slot ready for failover")
                    else:
                        # Check for timeout
                        if current_time - last_heartbeat_times[slot] > HEARTBEAT_TIMEOUT:
                            # Worker appears hung
                            detection_time = time.monotonic_ns()
                            
                            if slot == self.active_idx and not self.pending_switch:
                                print(f"[MONITOR] Active slot {slot} heartbeat timeout")
                                self.handle_slot_failure(slot, detection_time)
                
                time.sleep(0.01)  # 10ms monitoring interval
                
            except Exception as e:
                print(f"[MONITOR] Error: {e}")
                time.sleep(0.1)
    
    def handle_slot_failure(self, failed_slot, detection_time):
        """
        Handle failure of a slot - SENIOR DEV'S TWO-PHASE APPROACH
        Phase 1: Set switch flags only
        Phase 2: Clean up after switch (in monitor thread)
        """
        print(f"[FAILOVER] Slot {failed_slot} failed, initiating failover")
        
        # Determine target slot
        target_slot = 1 if failed_slot == 0 else 0
        target_ring = self.slot1_audio_ring if target_slot == 1 else self.slot0_audio_ring
        
        # Check if standby is ready
        if not self.standby_ready:
            print("[FAILOVER] WARNING: Standby not ready, failover may cause glitch")
        
        # PHASE 1: Set switch flags (don't touch rings or workers yet)
        self.pending_switch = True
        self.target_idx = target_slot
        self.target_ring = target_ring
        self.failed_slot = failed_slot  # Remember which slot failed
        
        # Track failover metrics
        self.metrics.failover_count += 1
        switch_time = time.monotonic_ns()
        self.metrics.last_failover_ms = (switch_time - detection_time) / 1_000_000
        
        print(f"[FAILOVER] Pending switch to slot {target_slot}")
    
    def perform_post_switch_cleanup(self):
        """
        SENIOR DEV'S FIX: Clean up failed slot AFTER switch
        No ring swapping - just terminate failed worker and spawn replacement
        """
        print(f"[CLEANUP] Performing post-switch cleanup for failed slot {self.failed_slot}")
        
        if self.failed_slot == 0:
            # Slot0 failed
            if self.slot0_worker and self.slot0_worker.is_alive():
                self.slot0_worker.terminate()
                self.slot0_worker.join(timeout=0.1)
            
            # Spawn new worker for slot0 (using slot0's rings)
            self.slot0_shutdown.clear()
            self.slot0_event.clear()
            self.heartbeat_array[0] = 0
            self.slot0_spawn_time = time.monotonic()
            
            self.slot0_worker = mp.Process(
                target=worker_process,
                args=(0, self.slot0_audio_ring, self.slot0_cmd_ring,
                      self.heartbeat_array, self.slot0_event, self.slot0_shutdown)
            )
            self.slot0_worker.start()
            
        elif self.failed_slot == 1:
            # Slot1 failed  
            if self.slot1_worker and self.slot1_worker.is_alive():
                self.slot1_worker.terminate()
                self.slot1_worker.join(timeout=0.1)
            
            # Spawn new worker for slot1 (using slot1's rings)
            self.slot1_shutdown.clear()
            self.slot1_event.clear()
            self.heartbeat_array[1] = 0
            self.slot1_spawn_time = time.monotonic()
            
            self.slot1_worker = mp.Process(
                target=worker_process,
                args=(1, self.slot1_audio_ring, self.slot1_cmd_ring,
                      self.heartbeat_array, self.slot1_event, self.slot1_shutdown)
            )
            self.slot1_worker.start()
        
        # Reset standby readiness (new worker needs to prove itself)
        self.standby_ready = False
        
        # Clear failed slot tracking
        self.failed_slot = None
        
        print("[CLEANUP] Post-switch cleanup complete")
    
    def send_command(self, command_bytes):
        """
        Send command to workers
        SENIOR DEV'S RECOMMENDATION: Broadcast during switch, otherwise active-only
        """
        # During switch or cleanup: broadcast to both slots
        if self.pending_switch or self.post_switch_cleanup_pending:
            if self.slot0_worker:
                self.slot0_cmd_ring.write(command_bytes)
                self.slot0_event.set()
            if self.slot1_worker:
                self.slot1_cmd_ring.write(command_bytes)
                self.slot1_event.set()
            
            if os.environ.get('CHRONUS_VERBOSE'):
                print("[COMMAND] Broadcasting during switch")
        else:
            # Normal operation: send to active slot only (reduce overhead)
            if self.active_idx == 0 and self.slot0_worker:
                self.slot0_cmd_ring.write(command_bytes)
                self.slot0_event.set()
            elif self.active_idx == 1 and self.slot1_worker:
                self.slot1_cmd_ring.write(command_bytes)
                self.slot1_event.set()
        
        self.metrics.commands_sent += 1
    
    def handle_osc_message(self, address, *args):
        """Handle incoming OSC messages with debug"""
        try:
            if os.environ.get('CHRONUS_VERBOSE'):
                print(f"[OSC] Received: {address} {args}")
            
            parts = address.strip('/').split('/')
            
            # Module parameter: /mod/<module>/<param>
            if len(parts) == 3 and parts[0] == 'mod':
                module_id = parts[1]
                param = parts[2]
                
                if args and len(args) > 0:
                    value = float(args[0])
                    
                    # Pack and send command
                    cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, param, value)
                    self.send_command(cmd)
                    
                    if os.environ.get('CHRONUS_VERBOSE'):
                        print(f"[OSC] Set {module_id}.{param} = {value}")
            
            # Gate control: /gate/<module>
            elif len(parts) == 2 and parts[0] == 'gate':
                module_id = parts[1]
                if args and len(args) > 0:
                    # Fix: Convert properly
                    gate_on = args[0] in [1, '1', 'on', True]
                    
                    # Pack and send gate command
                    cmd = pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, module_id, 'gate', gate_on)
                    self.send_command(cmd)
                    
                    if os.environ.get('CHRONUS_VERBOSE'):
                        print(f"[OSC] Gate {module_id} = {'on' if gate_on else 'off'}")
            
            # Test signal
            elif address == '/test':
                print("[OSC] Test signal received")
                test_commands = [
                    pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'freq', 440.0),
                    pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'gain', 0.3),
                    pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, 'adsr', 'gate', True),
                ]
                for cmd in test_commands:
                    self.send_command(cmd)
                    
        except Exception as e:
            print(f"[OSC] Handler error: {e}")
    
    def start_osc_server(self):
        """Start OSC server with FIXED patterns"""
        disp = dispatcher.Dispatcher()
        
        # SENIOR DEV'S FIX: Use /** for multi-level matching
        disp.map("/mod/*/*", self.handle_osc_message)
        disp.map("/gate/*", self.handle_osc_message)
        disp.map("/test", self.handle_osc_message)
        
        # Optional default handler for debugging
        if os.environ.get('CHRONUS_VERBOSE'):
            disp.set_default_handler(self.handle_osc_message)
        
        self.osc_server = ThreadingOSCUDPServer(("127.0.0.1", 5005), disp)
        self.osc_thread = threading.Thread(target=self.osc_server.serve_forever)
        self.osc_thread.daemon = True
        self.osc_thread.start()
        print("[OSC] OSC server listening on port 5005")
    
    def start(self):
        """Start the audio supervisor with grace period"""
        print("Starting AudioSupervisor v2 (slot-based architecture)...")
        print(f"Ring depth: {NUM_BUFFERS} buffers")
        print(f"Heartbeat timeout: {HEARTBEAT_TIMEOUT*1000:.1f}ms")
        print(f"Startup grace period: {STARTUP_GRACE_PERIOD}s")
        
        # Start monitor thread
        self.monitor_thread.start()
        
        # Start OSC server
        self.start_osc_server()
        
        # Start audio
        with sd.OutputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BUFFER_SIZE,
            channels=NUM_CHANNELS,
            dtype='float32',
            callback=self.audio_callback
        ):
            print("Audio supervisor started successfully")
            print("Waiting for standby to become ready...")
            
            # Wait for standby
            wait_start = time.monotonic()
            while not self.standby_ready and (time.monotonic() - wait_start) < 5.0:
                time.sleep(0.1)
            
            if self.standby_ready:
                print("Standby ready - failover protection active")
            else:
                print("WARNING: Standby not ready after 5 seconds")
            
            print("\nCommands: status, quit")
            
            # Main loop
            try:
                while True:
                    cmd = input("> ").strip().lower()
                    
                    if cmd == 'quit':
                        break
                    elif cmd == 'status':
                        self.print_status()
                    else:
                        print(f"Unknown command: {cmd}")
                        
            except KeyboardInterrupt:
                print("\nShutting down...")
    
    def print_status(self):
        """Print current status"""
        print("\n=== Audio Supervisor Status ===")
        print(f"Active slot: {self.active_idx}")
        print(f"Standby ready: {self.standby_ready}")
        print(f"Pending switch: {self.pending_switch}")
        print(f"Buffers processed: {self.metrics.buffers_processed}")
        print(f"None reads: {self.metrics.none_reads}")
        print(f"Commands sent: {self.metrics.commands_sent}")
        print(f"Switches performed: {self.metrics.switches_performed}")
        print(f"Failover count: {self.metrics.failover_count}")
        if self.metrics.failover_count > 0:
            print(f"Last failover time: {self.metrics.last_failover_ms:.2f}ms")
        print(f"Slot0 heartbeat: {self.heartbeat_array[0]}")
        print(f"Slot1 heartbeat: {self.heartbeat_array[1]}")
        print("==============================\n")
    
    def stop(self):
        """Stop the supervisor"""
        print("Stopping audio supervisor...")
        
        # Stop monitor
        self.monitor_stop.set()
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
        
        # Stop workers
        self.slot0_shutdown.set()
        self.slot1_shutdown.set()
        
        if self.slot0_worker:
            self.slot0_worker.terminate()
            self.slot0_worker.join(timeout=0.5)
        
        if self.slot1_worker:
            self.slot1_worker.terminate()
            self.slot1_worker.join(timeout=0.5)
        
        # Stop OSC
        if self.osc_server:
            self.osc_server.shutdown()
        
        print("Audio supervisor stopped")


def main():
    """Main entry point with argument parsing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Audio Supervisor v2 - Slot-Based')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()
    
    if args.verbose:
        os.environ['CHRONUS_VERBOSE'] = '1'
    
    supervisor = AudioSupervisor()
    
    try:
        supervisor.start()
    finally:
        supervisor.stop()


if __name__ == "__main__":
    main()