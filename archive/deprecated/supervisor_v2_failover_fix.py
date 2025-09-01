#!/usr/bin/env python3
"""
AudioSupervisor v2 with FIXED failover logic
Based on supervisor_v2_surgical.py with corrected worker management
"""

import multiprocessing as mp
import numpy as np
import sounddevice as sd
import time
import signal
import os
import sys
from pythonosc.osc_server import AsyncIOOSCUDPServer, BlockingOSCUDPServer
from pythonosc.dispatcher import Dispatcher
import asyncio
import threading
from struct import pack
from collections import deque
import argparse

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.music_chronus.module_host import ModuleHost
from src.music_chronus.modules.simple_sine import SimpleSine
from src.music_chronus.modules.adsr import ADSR
from src.music_chronus.modules.biquad_filter import BiquadFilter
from src.music_chronus.protocol import (
    CMD_OP_SET_PARAM, CMD_OP_GATE, CMD_OP_RESET,
    CMD_TYPE_FLOAT, CMD_TYPE_BOOL,
    pack_command_v2, unpack_command_v2
)

# Audio settings
SAMPLE_RATE = 44100
BUFFER_SIZE = 256
NUM_CHANNELS = 1
NUM_BUFFERS = 8  # Ring depth for jitter tolerance

# Command ring
COMMAND_RING_SLOTS = 32

# Monitoring
HEARTBEAT_TIMEOUT = 0.05  # 50ms relaxed timeout


class AudioRing:
    """
    Lock-free SPSC ring buffer for audio data
    Senior Dev's surgical implementation
    """
    
    def __init__(self, num_buffers=NUM_BUFFERS, frames_per_buffer=BUFFER_SIZE):
        self.num_buffers = num_buffers
        self.frames_per_buffer = frames_per_buffer
        
        # Cache-line aligned indices (64-byte alignment)
        self.head = mp.Value('Q', 0, lock=False)  # Written by producer
        self._pad1 = mp.Array('c', 56)  # Padding to 64 bytes
        self.tail = mp.Value('Q', 0, lock=False)  # Written by consumer  
        self._pad2 = mp.Array('c', 56)
        
        # Audio data storage
        total_frames = num_buffers * frames_per_buffer
        self.buffer = mp.Array('f', total_frames, lock=False)  # float32
        self.sequence = mp.Array('Q', num_buffers, lock=False)  # Buffer sequence numbers
        
        # Create persistent NumPy view to avoid allocations
        self._np_buffer = np.frombuffer(self.buffer, dtype=np.float32)
        
        # Metrics
        self.overruns = mp.Value('Q', 0, lock=False)
        self.underruns = mp.Value('Q', 0, lock=False)
    
    def write(self, audio_data):
        """
        Producer writes buffer (worker process)
        Returns True on success, False if ring full
        """
        next_head = (self.head.value + 1) % self.num_buffers
        
        # Check if full
        if next_head == self.tail.value:
            self.overruns.value += 1
            return False
        
        # Write audio data
        idx = self.head.value
        offset = idx * self.frames_per_buffer
        self.buffer[offset:offset + len(audio_data)] = audio_data
        
        # Update head (memory barrier implicit in mp.Value)
        self.head.value = next_head
        return True
    
    def read_latest(self):
        """
        Consumer reads buffer sequentially
        FIXED: Sequential reading for proper audio continuity
        """
        # Check if empty
        if self.head.value == self.tail.value:
            self.underruns.value += 1
            return None
        
        # Read from tail (oldest unread buffer)
        idx = self.tail.value
        offset = idx * self.frames_per_buffer
        audio_view = self._np_buffer[offset:offset + self.frames_per_buffer]
        
        # Advance tail by one (sequential reading)
        self.tail.value = (self.tail.value + 1) % self.num_buffers
        
        return audio_view
    
    def reset(self):
        """Reset ring to initial state"""
        self.head.value = 0
        self.tail.value = 0
        self.overruns.value = 0
        self.underruns.value = 0


class CommandRing:
    """
    SPSC ring buffer for commands with coalescing support
    """
    
    def __init__(self, num_slots=64):
        self.num_slots = num_slots
        self.slot_size = 64  # Bytes per command
        
        # Cache-line aligned indices
        self.write_idx = mp.Value('L', 0, lock=False)
        self._pad1 = mp.Array('c', 60)
        self.read_idx = mp.Value('L', 0, lock=False)
        self._pad2 = mp.Array('c', 60)
        
        # Command storage
        self.buffer = mp.Array('c', num_slots * self.slot_size, lock=False)
        
        # Explicitly zero-initialize to prevent garbage interpretation
        self.reset()
    
    def write(self, command_bytes):
        """Write command to ring"""
        next_write = (self.write_idx.value + 1) % self.num_slots
        
        # Check if full
        if next_write == self.read_idx.value:
            # Ring full - coalesce by dropping oldest
            self.read_idx.value = (self.read_idx.value + 1) % self.num_slots
        
        # Write command
        idx = self.write_idx.value
        offset = idx * self.slot_size
        
        # Ensure command fits in slot
        cmd_data = command_bytes[:self.slot_size]
        if len(cmd_data) < self.slot_size:
            cmd_data += b'\x00' * (self.slot_size - len(cmd_data))
        
        self.buffer[offset:offset + self.slot_size] = cmd_data
        self.write_idx.value = next_write
        return True
    
    def read(self):
        """Read command from ring"""
        # Check if empty
        if self.read_idx.value == self.write_idx.value:
            return None
        
        # Read command
        idx = self.read_idx.value
        offset = idx * self.slot_size
        cmd_data = bytes(self.buffer[offset:offset + self.slot_size])
        
        # Advance read index
        self.read_idx.value = (self.read_idx.value + 1) % self.num_slots
        
        # Protocol v2 uses fixed 64-byte packets - DO NOT trim at null bytes!
        return cmd_data
    
    def has_data(self):
        """Check if ring has data"""
        return self.read_idx.value != self.write_idx.value
    
    def reset(self):
        """Reset ring buffer to clean state"""
        self.write_idx.value = 0
        self.read_idx.value = 0
        # Zero out buffer to prevent garbage interpretation
        for i in range(len(self.buffer)):
            self.buffer[i] = b'\x00'


def worker_process(worker_id: int,
                  audio_ring: AudioRing,
                  command_ring: CommandRing,
                  heartbeat_array,
                  event,
                  shutdown_flag):
    """
    Worker process with ModuleHost integration
    """
    # Set up signal handling
    def handle_sigterm(signum, frame):
        # Add timestamp and PID for clarity
        timestamp = time.monotonic()
        print(f"[{timestamp:.3f}] Worker {worker_id} (PID: {os.getpid()}) received SIGTERM")
        shutdown_flag.set()
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ignore Ctrl+C in worker
    
    # Initialize module host
    host = ModuleHost(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    
    # Create and register modules
    sine = SimpleSine(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    adsr = ADSR(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    filt = BiquadFilter(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
    
    host.add_module('sine', sine)
    host.add_module('adsr', adsr)
    host.add_module('filter', filt)
    
    # Build chain: sine -> adsr -> filter
    host.connect('sine', 'adsr')
    host.connect('adsr', 'filter')
    
    # Prepare modules
    host.prepare()
    
    buffer_period = BUFFER_SIZE / SAMPLE_RATE
    next_buffer_time = time.monotonic()
    seq = 0
    
    # Verbose diagnostics
    verbose = os.environ.get('CHRONUS_VERBOSE')
    diag_interval = 500  # buffers
    last_diag = 0
    
    # Initial parameters
    sine.set_param('freq', 440.0)
    sine.set_param('gain', 0.3)
    filt.set_param('cutoff', 10000.0)
    filt.set_param('q', 0.707)
    adsr.set_param('attack', 10.0)
    adsr.set_param('decay', 100.0)
    adsr.set_param('sustain', 0.7)
    adsr.set_param('release', 200.0)
    
    try:
        while not shutdown_flag.is_set():
            # Process commands
            if event.is_set():
                event.clear()
                while True:
                    cmd_data = command_ring.read()
                    if cmd_data is None:
                        break
                    
                    try:
                        op, typ, module_id, param, value = unpack_command_v2(cmd_data)
                        
                        if op == CMD_OP_SET_PARAM and typ == CMD_TYPE_FLOAT:
                            if module_id == b'sine':
                                if param == 'freq':
                                    sine.set_param('freq', value)
                                elif param == 'gain':
                                    sine.set_param('gain', value)
                            elif module_id == b'filter':
                                if param == 'cutoff':
                                    filt.set_param('cutoff', value)
                                elif param == 'q':
                                    filt.set_param('q', value)
                            elif module_id == b'adsr':
                                if param in ['attack', 'decay', 'sustain', 'release']:
                                    adsr.set_param(param, value)
                        
                        elif op == CMD_OP_GATE and typ == CMD_TYPE_BOOL:
                            if module_id == b'adsr':
                                adsr.set_gate(bool(value))
                        
                    except Exception as e:
                        if verbose:
                            print(f"Worker {worker_id}: Command error: {e}")
            
            # Process commands from ModuleHost's queue
            host.process_commands()
            
            # Process audio chain
            output = host.process_chain()
            
            # Write to ring
            if output is not None:
                audio_ring.write(output)
            
            # Update heartbeat
            heartbeat_array[worker_id] = seq
            seq += 1
            
            # Diagnostic output
            if verbose and seq - last_diag >= diag_interval:
                rms = np.sqrt(np.mean(output**2)) if output is not None else 0.0
                print(f"[DIAG] Worker {worker_id}: seq={seq}, RMS={rms:.6f}")
                last_diag = seq
            
            # Precise timing
            next_buffer_time += buffer_period
            sleep_time = next_buffer_time - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif sleep_time < -0.001:  # More than 1ms behind
                # Reset timing
                next_buffer_time = time.monotonic()
    
    except Exception as e:
        print(f"Worker {worker_id} error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"Worker {worker_id} (PID: {os.getpid()}) shutting down")


class AudioSupervisor:
    """
    FIXED VERSION: Corrected failover logic
    """
    
    def __init__(self):
        # Process management
        self.primary_worker = None
        self.standby_worker = None
        
        # Shared memory rings
        self.primary_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
        self.primary_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        self.standby_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
        self.standby_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        
        # Events for command notification
        self.primary_event = mp.Event()
        self.standby_event = mp.Event()
        
        # Shutdown flags
        self.primary_shutdown = mp.Event()
        self.standby_shutdown = mp.Event()
        
        # Heartbeat monitoring
        self.heartbeat_array = mp.Array('i', [0, 0])
        
        # Active tracking
        self.active_idx = 0
        self.active_ring = self.primary_audio_ring
        
        # Ring switch synchronization (Senior Dev's design)
        self.pending_switch = False
        self.target_ring = None
        self.target_idx = 0
        
        # Standby readiness tracking
        self.standby_ready = False
        self.standby_warmup_buffers = 0
        
        # Audio stream
        self.stream = None
        
        # Monitor thread
        self.monitor_thread = None
        self.monitor_stop = threading.Event()
        
        # OSC server
        self.osc_server = None
        self.osc_thread = None
        
        # Senior Dev's additions
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
        
        # Failover state tracking (FIX)
        self.active_worker_ref = None  # Reference to actual active worker
        self.standby_worker_ref = None  # Reference to actual standby worker
    
    def audio_callback(self, outdata, frames, time_info, status):
        """
        Real-time audio callback with last_good fallback
        Senior Dev's surgical fix implementation
        """
        if status:
            self.metrics.underruns += 1
        
        # CRITICAL: Handle pending switch at buffer boundary
        if self.pending_switch and self.target_ring:
            self.active_ring = self.target_ring
            self.active_idx = self.target_idx
            self.pending_switch = False
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
                if current_time - self.last_diag_time > 0.5:  # At most every 0.5s
                    rms = np.sqrt(np.mean(self.last_good**2))
                    print(f"[DIAG] Callback: idx={self.active_idx}, buffers={self.metrics.buffers_processed}, " +
                          f"none_reads={self.none_count}, RMS={rms:.6f}")
                    self.last_diag_time = current_time
    
    def monitor_workers(self):
        """
        Monitor thread with RELAXED heartbeat timeout
        """
        print("Monitor thread started (failover fix version)")
        
        # Initialize tracking
        last_heartbeats = [0, 0]
        last_heartbeat_times = [time.monotonic(), time.monotonic()]
        
        while not self.monitor_stop.is_set():
            try:
                current_time = time.monotonic()
                
                # Check process sentinel first (faster than heartbeat)
                for i, worker in enumerate([self.primary_worker, self.standby_worker]):
                    if worker and hasattr(worker, 'sentinel'):
                        # Use timeout=0 for non-blocking check
                        if not worker.is_alive():
                            detection_time = time.monotonic_ns()
                            
                            if i == self.active_idx:
                                # Primary died - failover to standby
                                print(f"Active worker died (sentinel) - failing over")
                                self.handle_primary_failure(detection_time)
                            else:
                                # Standby died - spawn new one
                                print(f"Standby worker died (sentinel) - spawning replacement")
                                self.handle_standby_failure(detection_time)
                            break
                
                # Check heartbeats with RELAXED timeout
                for i in range(2):
                    if i == 0 and self.primary_worker is None:
                        continue
                    if i == 1 and self.standby_worker is None:
                        continue
                    
                    current_hb = self.heartbeat_array[i]
                    
                    if current_hb == last_heartbeats[i]:
                        # No heartbeat progress - check timeout
                        if current_time - last_heartbeat_times[i] > HEARTBEAT_TIMEOUT:
                            detection_time = time.monotonic_ns()
                            
                            if i == self.active_idx:
                                print(f"Active worker hung (heartbeat) - failing over")
                                self.handle_primary_failure(detection_time, cause='heartbeat')
                            else:
                                print(f"Standby worker hung - spawning replacement")
                                self.handle_standby_failure(detection_time, cause='heartbeat')
                    else:
                        # Worker is making progress
                        last_heartbeats[i] = current_hb
                        last_heartbeat_times[i] = current_time
                
                # Check standby readiness after respawn
                if not self.standby_ready and self.standby_worker:
                    # Check if standby has written any buffers
                    if self.standby_audio_ring.head.value > 0:
                        self.standby_ready = True
                        print("Standby worker ready for failover")
                
                # Dynamic polling adjustment
                if self.metrics.failover_count > 0 and \
                   (current_time - self.metrics.last_failure_time) < 1.0:
                    # Recent failure - poll faster
                    time.sleep(0.001)
                else:
                    # Normal operation - relaxed polling
                    time.sleep(0.01)
                    
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(0.01)
        
        print("Monitor thread stopped")
    
    def handle_primary_failure(self, detection_time_ns, cause='sentinel'):
        """Handle active worker failure with FIXED switching logic"""
        
        # Check standby readiness
        if not self.standby_ready:
            print("WARNING: Standby not ready, failover may cause artifacts")
        
        failover_start = time.monotonic_ns()
        
        # Detection time
        self.metrics.detection_time_ms = (failover_start - detection_time_ns) / 1_000_000
        
        # FIX: Properly track which worker becomes active
        if self.active_idx == 0:
            # Primary was active, switch to standby
            print(f"Switching from primary (idx=0) to standby (idx=1)")
            
            # Request synchronized switch
            self.pending_switch = True
            self.target_ring = self.standby_audio_ring
            self.target_idx = 1
            
            # FIX: Keep the standby worker reference as it becomes active
            self.active_worker_ref = self.standby_worker
            
            # Kill the failed primary if still running
            if self.primary_worker and self.primary_worker.is_alive():
                self.primary_worker.terminate()
                self.primary_worker.join(timeout=0.1)
            
            # Clear primary worker reference
            self.primary_worker = None
            
        else:
            # Standby was active, switch to primary
            print(f"Switching from standby (idx=1) to primary (idx=0)")
            
            # Request synchronized switch
            self.pending_switch = True
            self.target_ring = self.primary_audio_ring
            self.target_idx = 0
            
            # FIX: Keep the primary worker reference as it becomes active
            self.active_worker_ref = self.primary_worker
            
            # Kill the failed standby if still running
            if self.standby_worker and self.standby_worker.is_alive():
                self.standby_worker.terminate()
                self.standby_worker.join(timeout=0.1)
            
            # Clear standby worker reference
            self.standby_worker = None
        
        # Switch time
        switch_time_ns = time.monotonic_ns()
        self.metrics.switch_time_ms = (switch_time_ns - failover_start) / 1_000_000
        
        # Spawn replacement standby AFTER switch is set up
        self.spawn_standby_worker()
        
        # Total failover time
        total_time_ms = (time.monotonic_ns() - detection_time_ns) / 1_000_000
        self.metrics.failover_time_ms = total_time_ms
        self.metrics.failover_count += 1
        self.metrics.last_failure_time = time.monotonic()
        
        print(f"Failover complete: detection={self.metrics.detection_time_ms:.2f}ms, " +
              f"switch={self.metrics.switch_time_ms:.2f}ms, total={total_time_ms:.2f}ms")
    
    def handle_standby_failure(self, detection_time_ns, cause='sentinel'):
        """Handle standby worker failure"""
        print(f"Standby failed ({cause}) - spawning replacement")
        
        # Kill standby if still running
        if self.active_idx == 0:
            # Primary is active, standby failed
            if self.standby_worker and self.standby_worker.is_alive():
                self.standby_worker.terminate()
                self.standby_worker.join(timeout=0.1)
            
            # Reset standby rings for new worker
            self.standby_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.standby_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        else:
            # Standby is active, primary failed
            if self.primary_worker and self.primary_worker.is_alive():
                self.primary_worker.terminate()
                self.primary_worker.join(timeout=0.1)
            
            # Reset primary rings for new worker
            self.primary_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.primary_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        
        # Spawn new standby
        self.spawn_standby_worker()
    
    def spawn_standby_worker(self):
        """Spawn a new standby worker (FIXED)"""
        # Mark as not ready until it writes buffers
        self.standby_ready = False
        
        # FIX: Check actual active index after switch
        actual_active_idx = self.target_idx if self.pending_switch else self.active_idx
        
        if actual_active_idx == 0:
            # Primary is (or will be) active, spawn standby
            print("Spawning new standby worker (idx=1)")
            
            # Clear events and heartbeat for standby
            self.standby_shutdown.clear()
            self.standby_event.clear()
            self.heartbeat_array[1] = 0
            
            # Reset standby rings
            self.standby_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.standby_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
            
            self.standby_worker = mp.Process(
                target=worker_process,
                args=(1, self.standby_audio_ring, self.standby_cmd_ring,
                      self.heartbeat_array, self.standby_event, self.standby_shutdown)
            )
            self.standby_worker.start()
            self.standby_worker_ref = self.standby_worker
            
        else:
            # Standby is (or will be) active, spawn primary
            print("Spawning new primary worker (idx=0)")
            
            # Clear events and heartbeat for primary
            self.primary_shutdown.clear()
            self.primary_event.clear()
            self.heartbeat_array[0] = 0
            
            # Reset primary rings
            self.primary_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.primary_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
            
            self.primary_worker = mp.Process(
                target=worker_process,
                args=(0, self.primary_audio_ring, self.primary_cmd_ring,
                      self.heartbeat_array, self.primary_event, self.primary_shutdown)
            )
            self.primary_worker.start()
            self.primary_worker_ref = self.primary_worker
        
        print(f"New standby worker spawned")
    
    def send_command(self, command_bytes: bytes):
        """Send command to BOTH workers (active processes it, standby stays in sync)"""
        # Send to primary if alive
        if self.primary_worker:
            self.primary_cmd_ring.write(command_bytes)
            self.primary_event.set()
        
        # Send to standby if alive
        if self.standby_worker:
            self.standby_cmd_ring.write(command_bytes)
            self.standby_event.set()
        
        self.metrics.commands_sent += 1
    
    def handle_osc_message(self, address, *args):
        """Handle incoming OSC messages"""
        try:
            parts = address.strip('/').split('/')
            
            if len(parts) == 3 and parts[0] == 'mod':
                # Module parameter: /mod/<module>/<param>
                module_id = parts[1].encode('ascii')[:16]
                param = parts[2]
                value = float(args[0]) if args else 0.0
                
                cmd = pack_command_v2(CMD_OP_SET_PARAM, CMD_TYPE_FLOAT, 
                                    module_id, param, value)
                self.send_command(cmd)
                
            elif len(parts) == 2 and parts[0] == 'gate':
                # Gate control: /gate/<module>
                module_id = parts[1].encode('ascii')[:16]
                
                # FIX: Proper boolean conversion
                gate_on = args[0] in [1, '1', 'on', True] if args else False
                
                cmd = pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, 
                                    module_id, 'gate', gate_on)
                self.send_command(cmd)
                
            elif address == '/test':
                # Test pattern
                print("Test signal received")
                test_commands = [
                    pack_command_v2(CMD_OP_SET_PARAM, CMD_TYPE_FLOAT, b'sine', 'freq', 440.0),
                    pack_command_v2(CMD_OP_SET_PARAM, CMD_TYPE_FLOAT, b'sine', 'gain', 0.3),
                    pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, b'adsr', 'gate', True),
                ]
                for cmd in test_commands:
                    self.send_command(cmd)
                    
        except Exception as e:
            print(f"OSC handler error: {e}")
    
    def run_osc_server(self):
        """Run OSC server in separate thread"""
        try:
            dispatcher = Dispatcher()
            dispatcher.set_default_handler(self.handle_osc_message)
            
            server = BlockingOSCUDPServer(("127.0.0.1", 5005), dispatcher)
            self.osc_server = server
            
            print("OSC server listening on port 5005")
            server.serve_forever()
        except Exception as e:
            print(f"OSC server error: {e}")
    
    def start(self):
        """Start the audio supervisor"""
        print("Starting AudioSupervisor v2 (failover fix)...")
        print(f"Ring depth: {NUM_BUFFERS} buffers")
        print(f"Heartbeat timeout: {HEARTBEAT_TIMEOUT*1000}ms")
        
        # Spawn primary worker
        self.primary_shutdown.clear()
        self.primary_event.clear()
        self.primary_worker = mp.Process(
            target=worker_process,
            args=(0, self.primary_audio_ring, self.primary_cmd_ring,
                  self.heartbeat_array, self.primary_event, self.primary_shutdown)
        )
        self.primary_worker.start()
        self.active_worker_ref = self.primary_worker
        
        # Spawn standby worker
        print("Spawning initial standby worker")
        self.spawn_standby_worker()
        
        # Start monitor thread
        self.monitor_thread = threading.Thread(target=self.monitor_workers)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        # Start OSC server
        self.osc_thread = threading.Thread(target=self.run_osc_server)
        self.osc_thread.daemon = True
        self.osc_thread.start()
        
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
        none_reads = self.none_count
        
        return {
            'active_worker': self.active_idx,
            'standby_ready': self.standby_ready,
            'buffers_processed': self.metrics.buffers_processed,
            'none_reads': none_reads,
            'callback_none_count': self.none_count,
            'underruns': self.metrics.underruns,
            'commands_sent': self.metrics.commands_sent,
            'failover_count': self.metrics.failover_count,
            'last_failover_ms': self.metrics.failover_time_ms
        }


def main():
    parser = argparse.ArgumentParser(description='Audio Supervisor v2 (failover fix)')
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
    mp.set_start_method('forkserver')
    main()