#!/usr/bin/env python3
"""
AudioSupervisor v2 - Graceful Version
Based on supervisor_v2_surgical.py with Senior Dev's incremental fixes:
1. Startup grace period for heartbeat detection
2. Proper deferred ring cleanup
3. Command broadcasting during switch
4. Fixed OSC patterns
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
        # Zero the buffers
        self.np_data.fill(0)


def worker_process(worker_id, audio_ring, command_ring, heartbeat_array, event, shutdown_flag):
    """Worker process with diagnostic logging"""
    
    # DIAGNOSTIC: Log worker start
    print(f"[WORKER] Worker {worker_id} starting, PID={os.getpid()}")
    
    # Set up signal handling
    def handle_sigterm(signum, frame):
        print(f"Worker {worker_id} received SIGTERM")
        shutdown_flag.set()
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    # Create module host and chain
    host = ModuleHost(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    
    # Create modules
    sine = SimpleSine(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    adsr = ADSR(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    biquad = BiquadFilter(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    
    # Register modules
    host.add_module('sine', sine)
    host.add_module('adsr', adsr)
    host.add_module('filter', biquad)
    
    # Set default parameters
    default_commands = [
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'freq', 440.0),
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'adsr', 'gain', 0.5),
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'filter', 'cutoff', 10000.0),
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'filter', 'q', 0.707),
    ]
    
    for cmd in default_commands:
        host.queue_command(cmd)
    
    # Warm up the processing chain (no explicit connect needed)
    for _ in range(10):
        host.process_commands()
        _ = host.process_chain()
    
    # Main processing loop
    seq = 0
    buffer_period = BUFFER_SIZE / SAMPLE_RATE  # ~5.8ms at 256/44100
    next_buffer_time = time.monotonic()
    
    # DIAGNOSTIC: Log first heartbeat
    first_heartbeat_logged = False
    
    while not shutdown_flag.is_set():
        # Check for wakeup (no wait - produce as fast as possible)
        if event.is_set():
            event.clear()
        
        # Always drain command ring (not just on wakeup)
        while command_ring.has_data():
            cmd_bytes = command_ring.read()
            if cmd_bytes and len(cmd_bytes) >= 64:
                # Queue command for processing at buffer boundary
                host.queue_command(cmd_bytes)
        
        if shutdown_flag.is_set():
            break
        
        # Process any queued commands at buffer boundary
        host.process_commands()
        
        # Generate audio
        output = host.process_chain()
        
        # Write to ring
        if output is not None:
            audio_ring.write(output)
        
        # Update heartbeat
        heartbeat_array[worker_id] = seq
        
        # DIAGNOSTIC: Log first heartbeat
        if not first_heartbeat_logged and seq == 1:
            print(f"[WORKER] Worker {worker_id} first heartbeat: seq={seq}")
            first_heartbeat_logged = True
        
        # Increment sequence
        seq += 1
        
        # Diagnostic output every 500 buffers if verbose
        if os.environ.get('CHRONUS_VERBOSE') and seq % 500 == 0:
            rms = np.sqrt(np.mean(output**2)) if output is not None else 0.0
            print(f"[DIAG] Worker {worker_id}: seq={seq}, RMS={rms:.6f}")
        
        # Pace production to match consumption rate
        next_buffer_time += buffer_period
        sleep_time = next_buffer_time - time.monotonic()
        if sleep_time > 0:
            time.sleep(sleep_time)
        elif sleep_time < -0.001:
            # We're behind - reset timing
            next_buffer_time = time.monotonic()
    
    print(f"[WORKER] Worker {worker_id} shutting down")


class AudioSupervisor:
    """
    Audio supervisor with Senior Dev's fixes:
    1. Startup grace period
    2. Deferred ring cleanup
    3. Command broadcasting
    4. Fixed OSC patterns
    """
    
    def __init__(self):
        # Ring buffers
        self.primary_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
        self.primary_cmd_ring = CommandRing(num_slots=COMMAND_RING_SLOTS)
        self.standby_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
        self.standby_cmd_ring = CommandRing(num_slots=COMMAND_RING_SLOTS)
        
        # Events
        self.primary_event = mp.Event()
        self.standby_event = mp.Event()
        
        # Shutdown flags
        self.primary_shutdown = mp.Event()
        self.standby_shutdown = mp.Event()
        
        # Active tracking
        self.active_idx = 0
        self.active_ring = self.primary_audio_ring
        
        # Ring switch synchronization
        self.pending_switch = False
        self.target_ring = None
        self.target_idx = 0
        
        # SENIOR DEV'S FIX: Deferred cleanup tracking
        self.post_switch_cleanup_pending = False
        self.failed_side = None  # 'primary' or 'standby'
        
        # Standby readiness tracking
        self.standby_ready = False
        self.standby_warmup_buffers = 0
        
        # Workers
        self.primary_worker = None
        self.standby_worker = None
        
        # Heartbeat monitoring
        self.heartbeat_array = mp.Array('i', [0, 0])
        
        # SENIOR DEV'S FIX: Startup grace period tracking
        self.startup_time = None
        self.startup_deadline = None
        
        # Audio stream
        self.stream = None
        
        # Monitor thread
        self.monitor_thread = None
        self.monitor_stop = threading.Event()
        
        # OSC server
        self.osc_server = None
        self.osc_thread = None
        
        # Last good buffer (Senior Dev's fallback)
        self.last_good = np.zeros(BUFFER_SIZE, dtype=np.float32)
        self.none_count = 0
        self.diag_counter = 0
        self.last_diag_time = 0
        
        # Metrics
        class Metrics:
            def __init__(self):
                self.buffers_processed = 0
                self.underruns = 0
                self.commands_sent = 0
                self.failover_count = 0
                self.failover_time_ms = 0.0
                self.detection_time_ms = 0.0
                self.switch_time_ms = 0.0
                self.last_failure_time = 0
        
        self.metrics = Metrics()
    
    def audio_callback(self, outdata, frames, time_info, status):
        """
        Real-time audio callback with deferred switch
        """
        if status:
            self.metrics.underruns += 1
        
        # CRITICAL: Handle pending switch at buffer boundary
        if self.pending_switch and self.target_ring:
            # Perform the switch
            self.active_ring = self.target_ring
            self.active_idx = self.target_idx
            self.pending_switch = False
            
            # SENIOR DEV'S FIX: Mark cleanup as pending
            self.post_switch_cleanup_pending = True
            
            if os.environ.get('CHRONUS_VERBOSE'):
                print(f"[SWITCH] Completed ring switch to idx {self.active_idx}")
        
        # Get latest buffer from active ring
        buffer = self.active_ring.read_latest()
        
        # Update last_good if we have new data
        if buffer is not None:
            np.copyto(self.last_good, buffer)
        else:
            self.none_count += 1
        
        # ALWAYS output last_good (prevents discontinuities)
        np.copyto(outdata[:, 0], self.last_good, casting='no')
        
        self.metrics.buffers_processed += 1
        
        # Diagnostics
        if os.environ.get('CHRONUS_VERBOSE'):
            self.diag_counter += 1
            if self.diag_counter % 100 == 0:
                current_time = time.monotonic()
                if current_time - self.last_diag_time > 0.5:
                    rms = np.sqrt(np.mean(self.last_good**2))
                    print(f"[DIAG] Callback: idx={self.active_idx}, buffers={self.metrics.buffers_processed}, " +
                          f"none_reads={self.none_count}, RMS={rms:.6f}")
                    self.last_diag_time = current_time
    
    def monitor_workers(self):
        """
        Monitor thread with STARTUP GRACE PERIOD
        """
        print("[MONITOR] Monitor thread started (graceful version)")
        
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
                for i, worker in enumerate([self.primary_worker, self.standby_worker]):
                    if worker and hasattr(worker, 'sentinel'):
                        if not worker.is_alive():
                            detection_time = time.monotonic_ns()
                            
                            if i == self.active_idx:
                                print(f"[MONITOR] Active worker died (sentinel) - failing over")
                                self.handle_primary_failure(detection_time)
                            else:
                                print(f"[MONITOR] Standby worker died (sentinel) - spawning replacement")
                                self.handle_standby_failure(detection_time)
                            break
                
                # SENIOR DEV'S FIX: Skip heartbeat checks during startup grace period
                if self.startup_deadline and current_time < self.startup_deadline:
                    # During grace period - skip heartbeat timeout checks
                    # But still update last_heartbeats if they change
                    for i in range(2):
                        if i == 0 and self.primary_worker is None:
                            continue
                        if i == 1 and self.standby_worker is None:
                            continue
                        
                        current_hb = self.heartbeat_array[i]
                        if current_hb > last_heartbeats[i]:
                            last_heartbeats[i] = current_hb
                            last_heartbeat_times[i] = current_time
                            if os.environ.get('CHRONUS_VERBOSE'):
                                print(f"[MONITOR] Worker {i} heartbeat update during grace: {current_hb}")
                else:
                    # After grace period - normal heartbeat checking
                    for i in range(2):
                        if i == 0 and self.primary_worker is None:
                            continue
                        if i == 1 and self.standby_worker is None:
                            continue
                        
                        current_hb = self.heartbeat_array[i]
                        
                        if current_hb == last_heartbeats[i]:
                            # No heartbeat progress
                            time_since_beat = current_time - last_heartbeat_times[i]
                            
                            if time_since_beat > HEARTBEAT_TIMEOUT:
                                detection_time = time.monotonic_ns()
                                
                                if i == self.active_idx:
                                    print(f"[MONITOR] Active worker hung (heartbeat) - failing over")
                                    self.handle_primary_failure(detection_time, cause='heartbeat')
                                else:
                                    print(f"[MONITOR] Standby worker hung - spawning replacement")
                                    self.handle_standby_failure(detection_time, cause='heartbeat')
                        else:
                            last_heartbeats[i] = current_hb
                            last_heartbeat_times[i] = current_time
                
                # Check standby readiness after respawn
                if not self.standby_ready and self.standby_worker:
                    if self.standby_audio_ring.head.value > 0:
                        self.standby_ready = True
                        print("[MONITOR] Standby worker ready for failover")
                
                # Dynamic polling adjustment
                if self.metrics.failover_count > 0 and \
                   (current_time - self.metrics.last_failure_time) < 1.0:
                    time.sleep(0.001)  # Recent failure - poll faster
                else:
                    time.sleep(0.01)  # Normal operation
                    
            except Exception as e:
                print(f"[MONITOR] Monitor error: {e}")
                time.sleep(0.01)
        
        print("[MONITOR] Monitor thread stopped")
    
    def handle_primary_failure(self, detection_time_ns, cause='sentinel'):
        """
        SENIOR DEV'S FIX: Only set switch flags, don't touch rings
        """
        if not self.standby_ready:
            print("[FAILOVER] WARNING: Standby not ready, failover may cause artifacts")
        
        failover_start = time.monotonic_ns()
        self.metrics.detection_time_ms = (failover_start - detection_time_ns) / 1_000_000
        
        # SENIOR DEV'S FIX: Only set switch flags, no ring operations
        if self.active_idx == 0:
            # Switch to standby
            print("[FAILOVER] Setting pending switch from primary to standby")
            self.pending_switch = True
            self.target_ring = self.standby_audio_ring
            self.target_idx = 1
            self.failed_side = 'primary'
        else:
            # Switch back to primary
            print("[FAILOVER] Setting pending switch from standby to primary")
            self.pending_switch = True
            self.target_ring = self.primary_audio_ring
            self.target_idx = 0
            self.failed_side = 'standby'
        
        # DO NOT reset rings or spawn workers here!
        
        # Record metrics
        switch_time_ns = time.monotonic_ns()
        self.metrics.switch_time_ms = (switch_time_ns - failover_start) / 1_000_000
        total_time_ms = (time.monotonic_ns() - detection_time_ns) / 1_000_000
        self.metrics.failover_time_ms = total_time_ms
        self.metrics.failover_count += 1
        self.metrics.last_failure_time = time.monotonic()
        
        print(f"[FAILOVER] Failover initiated: detection={self.metrics.detection_time_ms:.2f}ms, " +
              f"total={total_time_ms:.2f}ms")
    
    def handle_standby_failure(self, detection_time_ns, cause='sentinel'):
        """Handle standby worker failure (not currently active)"""
        print(f"[STANDBY] Standby failed ({cause}) - will spawn replacement")
        
        # Kill standby if still running
        if self.active_idx == 0:
            # Primary is active, standby failed
            if self.standby_worker and self.standby_worker.is_alive():
                self.standby_worker.terminate()
                self.standby_worker.join(timeout=0.1)
            
            # Reset standby rings for new worker
            self.standby_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.standby_cmd_ring = CommandRing(num_slots=COMMAND_RING_SLOTS)
        else:
            # Standby is active, primary failed
            if self.primary_worker and self.primary_worker.is_alive():
                self.primary_worker.terminate()
                self.primary_worker.join(timeout=0.1)
            
            # Reset primary rings for new worker
            self.primary_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.primary_cmd_ring = CommandRing(num_slots=COMMAND_RING_SLOTS)
        
        # Spawn new standby
        self.spawn_standby_worker()
    
    def perform_post_switch_cleanup(self):
        """
        SENIOR DEV'S FIX: Clean up failed worker AFTER switch
        """
        print(f"[CLEANUP] Performing post-switch cleanup for failed {self.failed_side}")
        
        if self.failed_side == 'primary':
            # Primary failed, now using standby
            if self.primary_worker and self.primary_worker.is_alive():
                self.primary_worker.terminate()
                self.primary_worker.join(timeout=0.1)
            
            # Move standby to primary slot (worker AND rings)
            self.primary_worker = self.standby_worker
            self.primary_audio_ring = self.standby_audio_ring
            self.primary_cmd_ring = self.standby_cmd_ring
            self.primary_event = self.standby_event
            self.standby_worker = None
            
            # Create new rings for new standby
            self.standby_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.standby_cmd_ring = CommandRing(num_slots=COMMAND_RING_SLOTS)
            self.standby_event = mp.Event()
            
        elif self.failed_side == 'standby':
            # Standby failed (was active), now using primary
            if self.standby_worker and self.standby_worker.is_alive():
                self.standby_worker.terminate()
                self.standby_worker.join(timeout=0.1)
            
            # Move primary to standby slot (worker AND rings)
            self.standby_worker = self.primary_worker
            self.standby_audio_ring = self.primary_audio_ring
            self.standby_cmd_ring = self.primary_cmd_ring
            self.standby_event = self.primary_event
            self.primary_worker = None
            
            # Create new rings for new primary
            self.primary_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.primary_cmd_ring = CommandRing(num_slots=COMMAND_RING_SLOTS)
            self.primary_event = mp.Event()
        
        # Spawn replacement standby
        self.spawn_standby_worker()
        
        # Clear failed side tracking
        self.failed_side = None
        
        print("[CLEANUP] Post-switch cleanup complete")
    
    def spawn_standby_worker(self):
        """Spawn a new standby worker"""
        self.standby_ready = False
        
        if self.active_idx == 0:
            # Primary is active, spawn standby
            self.standby_shutdown.clear()
            self.standby_event.clear()
            self.heartbeat_array[1] = 0
            
            self.standby_worker = mp.Process(
                target=worker_process,
                args=(1, self.standby_audio_ring, self.standby_cmd_ring,
                      self.heartbeat_array, self.standby_event, self.standby_shutdown)
            )
            self.standby_worker.start()
        else:
            # Standby is active, spawn primary
            self.primary_shutdown.clear()
            self.primary_event.clear()
            self.heartbeat_array[0] = 0
            
            self.primary_worker = mp.Process(
                target=worker_process,
                args=(0, self.primary_audio_ring, self.primary_cmd_ring,
                      self.heartbeat_array, self.primary_event, self.primary_shutdown)
            )
            self.primary_worker.start()
        
        print(f"[SPAWN] New standby worker spawned")
    
    def send_command(self, command_bytes: bytes):
        """
        ALWAYS broadcast to keep standby in sync
        """
        # Always send to both workers to keep them synchronized
        if self.primary_worker:
            self.primary_cmd_ring.write(command_bytes)
            self.primary_event.set()
        if self.standby_worker:
            self.standby_cmd_ring.write(command_bytes)
            self.standby_event.set()
        
        if os.environ.get('CHRONUS_VERBOSE') and (self.pending_switch or self.post_switch_cleanup_pending):
            print("[COMMAND] Broadcasting during switch")
        
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
        print("Starting AudioSupervisor v2 (graceful version)...")
        print(f"Ring depth: {NUM_BUFFERS} buffers")
        print(f"Heartbeat timeout: {HEARTBEAT_TIMEOUT*1000}ms")
        print(f"Startup grace period: {STARTUP_GRACE_PERIOD}s")
        
        # SENIOR DEV'S FIX: Set startup grace period
        self.startup_time = time.monotonic()
        self.startup_deadline = self.startup_time + STARTUP_GRACE_PERIOD
        
        # Spawn primary worker
        self.primary_shutdown.clear()
        self.primary_event.clear()
        self.primary_worker = mp.Process(
            target=worker_process,
            args=(0, self.primary_audio_ring, self.primary_cmd_ring,
                  self.heartbeat_array, self.primary_event, self.primary_shutdown)
        )
        self.primary_worker.start()
        
        # Spawn standby worker
        self.spawn_standby_worker()
        
        # Start monitor thread
        self.monitor_thread = threading.Thread(target=self.monitor_workers)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        # Start OSC server
        self.start_osc_server()
        
        # Start audio stream
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BUFFER_SIZE,
            channels=NUM_CHANNELS,
            dtype=np.float32,
            callback=self.audio_callback,
            finished_callback=lambda: print("Audio stream finished")
        )
        self.stream.start()
        
        print("Audio supervisor started successfully")
        print("Waiting for standby to become ready...")
    
    def stop(self):
        """Stop the audio supervisor"""
        print("Stopping audio supervisor...")
        
        # Stop monitoring
        self.monitor_stop.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        
        # Stop workers
        self.primary_shutdown.set()
        self.standby_shutdown.set()
        
        if self.primary_worker:
            self.primary_worker.terminate()
            self.primary_worker.join(timeout=1.0)
        
        if self.standby_worker:
            self.standby_worker.terminate()
            self.standby_worker.join(timeout=1.0)
        
        # Stop audio
        if self.stream:
            self.stream.stop()
            self.stream.close()
        
        # Stop OSC
        if self.osc_server:
            self.osc_server.shutdown()
        
        print("Audio supervisor stopped")
    
    def get_status(self):
        """Get current status"""
        return {
            'active_worker': self.active_idx,
            'standby_ready': self.standby_ready,
            'buffers_processed': self.metrics.buffers_processed,
            'none_reads': self.none_count,
            'underruns': self.metrics.underruns,
            'commands_sent': self.metrics.commands_sent,
            'failover_count': self.metrics.failover_count,
            'last_failover_ms': self.metrics.failover_time_ms
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Audio Supervisor v2 (graceful)')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose output')
    args = parser.parse_args()
    
    if args.verbose:
        os.environ['CHRONUS_VERBOSE'] = '1'
    
    # Set up signal handling
    supervisor = AudioSupervisor()
    
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal")
        supervisor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Set multiprocessing start method if not already set
    try:
        mp.set_start_method('forkserver')
    except RuntimeError:
        pass  # Already set
    
    try:
        supervisor.start()
        
        # Interactive loop
        print("\nCommands: status, quit")
        while True:
            try:
                cmd = input("> ").strip().lower()
                
                if cmd == 'quit':
                    break
                elif cmd == 'status':
                    status = supervisor.get_status()
                    print(f"Status: {status}")
                elif cmd == '':
                    continue
                else:
                    print(f"Unknown command: {cmd}")
                    
            except EOFError:
                break
            except KeyboardInterrupt:
                break
        
        supervisor.stop()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        supervisor.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()