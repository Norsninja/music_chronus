"""
AudioSupervisor v2 Surgical Fix - Senior Dev's minimal fixes for clean audio
Based on supervisor_v2_fixed.py with:
- last_good buffer fallback
- Synchronized ring switching at buffer boundaries
- Standby readiness check
- Increased ring depth (8 buffers)
- Relaxed heartbeat timeout
- Diagnostic logging
"""

import multiprocessing as mp
from multiprocessing import connection
import numpy as np
import sounddevice as sd
from pythonosc import dispatcher, osc_server
import asyncio
import time
import os
import socket
import threading
import signal
import struct
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

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
BUFFER_PERIOD = BUFFER_SIZE / SAMPLE_RATE  # ~5.8ms

# Performance targets
TARGET_FAILOVER_MS = 10.0
POLL_INTERVAL_ACTIVE = 0.002  # 2ms when active
POLL_INTERVAL_IDLE = 0.005    # 5ms when idle  
HEARTBEAT_TIMEOUT = 0.050     # INCREASED to 50ms per Senior Dev
COMMAND_RING_SLOTS = 64

# Worker pool configuration
WORKER_WARMUP_CYCLES = 10

# INCREASED ring depth for jitter tolerance
NUM_BUFFERS = 8  # Was 4


class AudioRing:
    """
    Enhanced AudioRing with None-read tracking
    Based on original but with diagnostic counters
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
        self._buffer = mp.Array('f', total_frames, lock=False)
        
        # Create numpy view for efficient access (producer side)
        # mp.Array returns a ctypes array, use it directly
        self._np_buffer = np.frombuffer(self._buffer, dtype=np.float32)
        
        # Metrics
        self.overruns = mp.Value('Q', 0, lock=False)
        self.underruns = mp.Value('Q', 0, lock=False)
        self.none_reads = mp.Value('Q', 0, lock=False)  # NEW: Track None returns
    
    def write(self, audio_data: np.ndarray, sequence_num: int) -> bool:
        """
        Producer writes audio (worker process)
        Returns False if ring is full (overrun)
        """
        # Check if full
        next_head = (self.head.value + 1) % self.num_buffers
        if next_head == self.tail.value:
            self.overruns.value += 1
            return False
        
        # Write to current head position
        idx = self.head.value
        offset = idx * self.frames_per_buffer
        self._np_buffer[offset:offset + self.frames_per_buffer] = audio_data
        
        # Advance head
        self.head.value = next_head
        return True
    
    def read_latest(self):
        """
        Consumer reads next buffer (main process)
        Fixed: Read sequentially, don't skip buffers
        Returns a view, not a copy - zero allocations
        """
        # Check if empty
        if self.head.value == self.tail.value:
            self.underruns.value += 1
            self.none_reads.value += 1  # Track None returns
            return None
        
        # Read from tail position (consume in order)
        idx = self.tail.value
        offset = idx * self.frames_per_buffer
        audio_view = self._np_buffer[offset:offset + self.frames_per_buffer]
        
        # Advance tail by one (consume one buffer)
        self.tail.value = (self.tail.value + 1) % self.num_buffers
        
        return audio_view
    
    def reset(self):
        """Reset ring to initial state"""
        self.head.value = 0
        self.tail.value = 0
        self.overruns.value = 0
        self.underruns.value = 0
        self.none_reads.value = 0


@dataclass
class WorkerMetrics:
    """Metrics from worker process"""
    buffers_generated: int = 0
    commands_processed: int = 0
    last_rms: float = 0.0
    worker_id: int = 0


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
    
    # Set default parameters
    default_commands = [
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'freq', 440.0),
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'adsr', 'gain', 0.5),
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'filter', 'cutoff', 10000.0),
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'filter', 'q', 0.707),
    ]
    
    for cmd in default_commands:
        host.queue_command(cmd)
    
    # Warm up the processing chain
    for _ in range(WORKER_WARMUP_CYCLES):
        host.process_commands()
        _ = host.process_chain()
    
    # Processing loop with proper pacing
    buffer_seq = 0
    heartbeat_counter = 0
    last_log_time = time.monotonic()
    
    # Calculate buffer period for pacing
    buffer_period = BUFFER_SIZE / SAMPLE_RATE  # ~5.8ms
    next_buffer_time = time.monotonic()
    
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
                
                # Debug logging if verbose
                if os.environ.get('CHRONUS_VERBOSE'):
                    try:
                        op_code, module_id, param, value = unpack_command_v2(cmd_bytes)
                        if op_code == CMD_OP_SET:
                            print(f"[DEBUG] Worker {worker_id} queued: {module_id}.{param}={value}")
                        elif op_code == CMD_OP_GATE:
                            print(f"[DEBUG] Worker {worker_id} queued gate: {module_id}={value}")
                    except:
                        pass
        
        if shutdown_flag.is_set():
            break
        
        # Process queued commands at buffer boundary
        host.process_commands()
        
        # Generate audio buffer through module chain
        audio_buffer = host.process_chain()
        
        # Diagnostic logging (every 500 buffers to reduce overhead)
        if os.environ.get('CHRONUS_VERBOSE') and buffer_seq % 500 == 0:
            rms = np.sqrt(np.mean(audio_buffer**2))
            print(f"[DIAG] Worker {worker_id}: seq={buffer_seq}, RMS={rms:.6f}")
        
        # Write to audio ring
        audio_ring.write(audio_buffer, buffer_seq)
        buffer_seq += 1
        
        # Update heartbeat
        heartbeat_counter += 1
        heartbeat_array[worker_id] = heartbeat_counter
        
        # Pace buffer production to match consumption rate
        # Sleep until next buffer is needed
        next_buffer_time += buffer_period
        sleep_time = next_buffer_time - time.monotonic()
        if sleep_time > 0:
            time.sleep(sleep_time)
    
    # Clean shutdown
    timestamp = time.monotonic()
    print(f"[{timestamp:.3f}] Worker {worker_id} (PID: {os.getpid()}) exited cleanly")


class AudioSupervisor:
    """
    Supervisor with surgical fixes for clean audio
    """
    
    def __init__(self):
        # Audio rings (INCREASED depth)
        self.primary_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
        self.standby_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
        
        # Command rings
        self.primary_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        self.standby_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        
        # Heartbeat monitoring
        self.heartbeat_array = mp.Array('i', [0, 0])
        
        # Worker events
        self.primary_event = mp.Event()
        self.standby_event = mp.Event()
        
        # Shutdown events
        self.primary_shutdown = mp.Event()
        self.standby_shutdown = mp.Event()
        
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
        
        # Workers
        self.primary_worker = None
        self.standby_worker = None
        
        # Audio stream
        self.stream = None
        
        # Monitor thread
        self.monitor_thread = None
        self.monitor_stop = threading.Event()
        
        # OSC server
        self.osc_thread = None
        self.osc_server = None
        self.osc_loop = None
        
        # Metrics
        self.metrics = self.Metrics()
        
        # CRITICAL: Preallocate last_good buffer
        self.last_good = np.zeros(BUFFER_SIZE, dtype=np.float32)
        
        # Diagnostic counters
        self.callback_count = 0
        self.none_count = 0
        self.last_diag_time = time.monotonic()
    
    class Metrics:
        def __init__(self):
            self.buffers_processed = 0
            self.underruns = 0
            self.overruns = 0
            self.commands_sent = 0
            self.none_reads = 0  # Track None returns
            self.active_worker = 0
            
            # Failover metrics
            self.failover_count = 0
            self.failover_time_ms = 0.0
            self.detection_time_ms = 0.0
            self.switch_time_ms = 0.0
            self.rebuild_time_ms = 0.0
            self.last_failure_time = 0
    
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
        
        # Update metrics
        self.metrics.buffers_processed += 1
        self.callback_count += 1
        
        # Diagnostic logging (every ~50 callbacks)
        if os.environ.get('CHRONUS_VERBOSE') and self.callback_count % 50 == 0:
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
        print("Monitor thread started (surgical fix version)")
        
        # Initialize tracking
        last_heartbeats = [0, 0]
        last_heartbeat_times = [time.monotonic(), time.monotonic()]
        poll_interval = POLL_INTERVAL_ACTIVE
        
        while not self.monitor_stop.is_set():
            try:
                # Get current workers
                workers = [self.primary_worker, self.standby_worker]
                
                # Get sentinels for instant death detection
                sentinels = []
                for w in workers:
                    if w and w.sentinel:
                        sentinels.append(w.sentinel)
                
                if not sentinels:
                    time.sleep(poll_interval)
                    continue
                
                # Check for process death with SHORT timeout
                ready = connection.wait(sentinels, timeout=poll_interval)
                
                if ready:
                    # A worker died - identify which one
                    for i, worker in enumerate(workers):
                        if worker and worker.sentinel in ready:
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
                current_time = time.monotonic()
                for i, worker in enumerate(workers):
                    if not worker:
                        continue
                    
                    current_hb = self.heartbeat_array[i]
                    
                    if current_hb == last_heartbeats[i]:
                        # No heartbeat progress
                        time_since_beat = current_time - last_heartbeat_times[i]
                        
                        if time_since_beat > HEARTBEAT_TIMEOUT:  # Now 50ms
                            detection_time = time.monotonic_ns()
                            
                            if i == self.active_idx:
                                print(f"Active worker hung (heartbeat) - failing over")
                                self.handle_primary_failure(detection_time, cause='heartbeat')
                            else:
                                print(f"Standby worker hung - spawning replacement")
                                self.handle_standby_failure(detection_time, cause='heartbeat')
                    else:
                        last_heartbeats[i] = current_hb
                        last_heartbeat_times[i] = current_time
                
                # Check standby readiness after respawn
                if not self.standby_ready and self.standby_worker:
                    # Simple check: has standby written any buffers?
                    if self.standby_audio_ring.head.value > 0:
                        self.standby_ready = True
                        print("Standby worker ready for failover")
                
                # Dynamic polling adjustment
                if self.metrics.last_failure_time:
                    time_since_failure = current_time - self.metrics.last_failure_time
                    if time_since_failure < 5.0:
                        poll_interval = 0.001  # 1ms when recently unstable
                    elif time_since_failure < 30.0:
                        poll_interval = POLL_INTERVAL_ACTIVE
                    else:
                        poll_interval = POLL_INTERVAL_IDLE
                
            except Exception as e:
                print(f"Monitor thread error: {e}")
                time.sleep(poll_interval)
        
        print("Monitor thread stopped")
    
    def handle_primary_failure(self, detection_time_ns: int, cause: str = 'sentinel'):
        """Handle active worker failure with synchronized switching"""
        
        # Check standby readiness
        if not self.standby_ready:
            print("WARNING: Standby not ready, failover may cause artifacts")
        
        failover_start = time.monotonic_ns()
        
        # Detection time
        self.metrics.detection_time_ms = (failover_start - detection_time_ns) / 1_000_000
        
        # Request synchronized switch (will happen at next buffer boundary)
        if self.active_idx == 0:
            # Switch to standby
            self.pending_switch = True
            self.target_ring = self.standby_audio_ring
            self.target_idx = 1
            
            # Swap worker references
            self.primary_worker, self.standby_worker = self.standby_worker, None
            
            # Reset rings for new standby
            self.primary_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.primary_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        else:
            # Switch back to primary
            self.pending_switch = True
            self.target_ring = self.primary_audio_ring
            self.target_idx = 0
            
            # Swap worker references
            self.standby_worker, self.primary_worker = self.primary_worker, None
            
            # Reset rings
            self.standby_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.standby_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        
        # Switch time
        switch_time_ns = time.monotonic_ns()
        self.metrics.switch_time_ms = (switch_time_ns - failover_start) / 1_000_000
        
        # Spawn replacement standby
        self.spawn_standby_worker()
        
        # Total failover time
        total_time_ms = (time.monotonic_ns() - detection_time_ns) / 1_000_000
        self.metrics.failover_time_ms = total_time_ms
        self.metrics.failover_count += 1
        self.metrics.last_failure_time = time.monotonic()
        
        print(f"Failover complete: detection={self.metrics.detection_time_ms:.2f}ms, "
              f"switch={self.metrics.switch_time_ms:.2f}ms, total={total_time_ms:.2f}ms")
    
    def handle_standby_failure(self, detection_time_ns: int, cause: str = 'sentinel'):
        """Handle standby worker failure - just spawn new one"""
        print(f"Standby failed ({cause}), spawning replacement...")
        
        # Clean up old standby
        if self.standby_worker:
            self.standby_shutdown.set()
            if self.standby_worker.is_alive():
                self.standby_worker.terminate()
                self.standby_worker.join(timeout=0.1)
        
        # Reset for new standby
        if self.active_idx == 0:
            # Primary is active, reset standby rings
            self.standby_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.standby_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        else:
            # Standby is active, reset primary rings
            self.primary_audio_ring = AudioRing(num_buffers=NUM_BUFFERS)
            self.primary_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        
        # Spawn new standby
        self.spawn_standby_worker()
    
    def spawn_standby_worker(self):
        """Spawn a new standby worker"""
        # Mark as not ready until it writes buffers
        self.standby_ready = False
        
        # Clear events and heartbeat
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
        
        print(f"New standby worker spawned")
    
    def send_command(self, command_bytes: bytes):
        """Send command to active worker"""
        if self.active_idx == 0:
            self.primary_cmd_ring.write(command_bytes)
            self.primary_event.set()
        else:
            self.standby_cmd_ring.write(command_bytes)
            self.standby_event.set()
        
        self.metrics.commands_sent += 1
    
    def handle_osc_message(self, address, *args):
        """Handle incoming OSC messages"""
        try:
            # Parse the address
            parts = address.strip('/').split('/')
            
            if len(parts) >= 3 and parts[0] == 'mod':
                module_id = parts[1]
                param = parts[2]
                
                if args and len(args) > 0:
                    value = float(args[0])
                    
                    # Pack and send command
                    cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, param, value)
                    self.send_command(cmd)
                    
                    if os.environ.get('CHRONUS_VERBOSE'):
                        print(f"OSC: Set {module_id}.{param} = {value}")
            
            elif len(parts) >= 2 and parts[0] == 'gate':
                module_id = parts[1]
                if args and len(args) > 0:
                    # Fix: Convert 1/0 or 'on'/'off' properly
                    gate_on = args[0] in [1, '1', 'on', True]
                    
                    # Pack and send gate command
                    cmd = pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, module_id, 'gate', gate_on)
                    self.send_command(cmd)
                    
                    if os.environ.get('CHRONUS_VERBOSE'):
                        print(f"OSC: Gate {module_id} = {'on' if gate_on else 'off'}")
            
        except Exception as e:
            print(f"OSC handler error: {e}")
    
    def start_osc_server(self):
        """Start OSC server with error handling"""
        # Set up dispatcher
        disp = dispatcher.Dispatcher()
        disp.map("/mod/*", self.handle_osc_message)
        disp.map("/gate/*", self.handle_osc_message)
        
        # Create async server function
        async def run_server():
            # Check if port is available
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind(('127.0.0.1', 5005))
                sock.close()
            except OSError:
                print("Warning: Port 5005 already in use, OSC server may not start")
                return
            
            # Create and run server
            try:
                self.osc_server = osc_server.AsyncIOOSCUDPServer(
                    ('127.0.0.1', 5005), disp, asyncio.get_event_loop()
                )
                await self.osc_server.create_serve_endpoint()
                print("OSC server listening on port 5005")
                
                # Keep running
                while True:
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"OSC server error: {e}")
        
        # Run in thread
        def osc_thread_func():
            self.osc_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.osc_loop)
            self.osc_loop.run_until_complete(run_server())
        
        self.osc_thread = threading.Thread(target=osc_thread_func, daemon=True)
        self.osc_thread.start()
    
    def start(self):
        """Start the audio supervisor"""
        print("Starting AudioSupervisor v2 (surgical fix)...")
        print(f"Ring depth: {NUM_BUFFERS} buffers")
        print(f"Heartbeat timeout: {HEARTBEAT_TIMEOUT*1000:.0f}ms")
        
        # Start primary worker
        self.primary_worker = mp.Process(
            target=worker_process,
            args=(0, self.primary_audio_ring, self.primary_cmd_ring,
                  self.heartbeat_array, self.primary_event, self.primary_shutdown)
        )
        self.primary_worker.start()
        
        # Start standby worker
        self.spawn_standby_worker()
        
        # Wait for workers to warm up
        time.sleep(0.1)
        
        # Start monitor thread
        self.monitor_thread = threading.Thread(target=self.monitor_workers, daemon=True)
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
        
        # Stop monitor
        self.monitor_stop.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        
        # Stop audio
        if self.stream:
            self.stream.stop()
            self.stream.close()
        
        # Stop workers
        self.primary_shutdown.set()
        self.standby_shutdown.set()
        
        if self.primary_worker:
            self.primary_worker.terminate()
            self.primary_worker.join(timeout=1)
        
        if self.standby_worker:
            self.standby_worker.terminate()
            self.standby_worker.join(timeout=1)
        
        print("Audio supervisor stopped")
    
    def get_status(self):
        """Get current status"""
        none_reads = (self.primary_audio_ring.none_reads.value + 
                     self.standby_audio_ring.none_reads.value)
        
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
    """Main entry point"""
    # Set up signal handling
    supervisor = None
    
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal")
        if supervisor:
            supervisor.stop()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start supervisor
    supervisor = AudioSupervisor()
    supervisor.start()
    
    # Simple command loop
    print("\nCommands: status, quit")
    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd == 'quit':
                break
            elif cmd == 'status':
                status = supervisor.get_status()
                print(f"Status: {status}")
    except (EOFError, KeyboardInterrupt):
        pass
    
    supervisor.stop()


if __name__ == '__main__':
    main()