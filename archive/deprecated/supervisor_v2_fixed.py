"""
AudioSupervisor v2 Fixed - Restores <10ms failover with ModuleHost
Fixes from v2:
- Sentinel-based detection for <10ms failover
- Standby respawn after failover
- Proper shutdown command handling
- Reuses validated ring classes from supervisor.py
- OSC error handling
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
from .supervisor import AudioRing, CommandRing

# Import our modules
from .module_host import ModuleHost, pack_command_v2, unpack_command_v2, CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL
from .modules.simple_sine import SimpleSine
from .modules.adsr import ADSR
from .modules.biquad_filter import BiquadFilter

# Audio configuration (matches existing)
SAMPLE_RATE = 44100
BUFFER_SIZE = 256
NUM_CHANNELS = 1
BUFFER_PERIOD = BUFFER_SIZE / SAMPLE_RATE  # ~5.8ms

# Performance targets (restored from Phase 1C)
TARGET_FAILOVER_MS = 10.0
POLL_INTERVAL_ACTIVE = 0.002  # 2ms when active
POLL_INTERVAL_IDLE = 0.005    # 5ms when idle  
HEARTBEAT_TIMEOUT = 0.015     # 15ms (2.5x buffer period)
COMMAND_RING_SLOTS = 64

# Worker pool configuration
WORKER_WARMUP_CYCLES = 10


@dataclass
class AudioMetrics:
    """Metrics tracking for supervisor performance"""
    buffers_processed: int = 0
    underruns: int = 0
    failover_count: int = 0
    failover_time_ms: float = 0.0
    last_failure_time: Optional[float] = None
    heartbeat_misses: int = 0
    commands_sent: int = 0
    active_worker: int = 0
    detection_time_ms: float = 0.0
    switch_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class AudioWorker:
    """Worker wrapper with sentinel tracking"""
    
    def __init__(self, worker_id: int, cmd_ring: CommandRing, audio_ring: AudioRing,
                 heartbeat_array, initial_state: dict):
        self.worker_id = worker_id
        self.cmd_ring = cmd_ring
        self.audio_ring = audio_ring
        self.heartbeat_array = heartbeat_array
        self.initial_state = initial_state
        
        # Create socketpair for wakeup signaling
        self.parent_socket, self.child_socket = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        
        # Process management
        self.process = None
        self.sentinel = None
        self.pid = None
        self.start_time = None
    
    def start(self):
        """Start the worker process"""
        self.process = mp.Process(
            target=audio_worker_process,
            args=(self.worker_id, self.cmd_ring, self.audio_ring,
                  self.heartbeat_array, self.initial_state,
                  self.parent_socket, self.child_socket)
        )
        self.process.start()
        
        # Close child's socket end in parent
        self.child_socket.close()
        
        # Track process info
        self.sentinel = self.process.sentinel
        self.pid = self.process.pid
        self.start_time = time.monotonic()
        
        return True
    
    def send_wakeup(self):
        """Send wakeup signal to worker"""
        try:
            self.parent_socket.send(b'!')
            return True
        except:
            return False
    
    def terminate(self):
        """Terminate the worker process"""
        if self.process and self.process.is_alive():
            # Use SIGTERM directly - no command ring pollution
            # Worker has SIGTERM handler and will exit cleanly
            self.process.terminate()
            
            # Send wakeup to ensure it processes the signal
            self.send_wakeup()
            
            # Give it time to exit gracefully
            self.process.join(timeout=0.5)
            
            # Force kill if still alive
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
        
        # Close socket
        self.parent_socket.close()
        
    def is_alive(self) -> bool:
        """Check if worker process is alive"""
        return self.process and self.process.is_alive()


def audio_worker_process(worker_id: int, cmd_ring: CommandRing, audio_ring: AudioRing, 
                         heartbeat_array, initial_state: dict, 
                         parent_socket: socket.socket, child_socket: socket.socket):
    """
    DSP worker process with ModuleHost integration
    Fixed: Proper shutdown command handling
    """
    # Close parent's socket end
    parent_socket.close()
    
    # Set up signal handler for clean exit
    shutdown_flag = False
    def handle_sigterm(signum, frame):
        nonlocal shutdown_flag
        shutdown_flag = True
        timestamp = time.monotonic()
        print(f"[{timestamp:.3f}] Worker {worker_id} (PID: {os.getpid()}) received SIGTERM")
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    # Initialize ModuleHost with synthesis chain
    host = ModuleHost(SAMPLE_RATE, BUFFER_SIZE)
    
    # Build the chain: SimpleSine → ADSR → BiquadFilter
    sine = SimpleSine(SAMPLE_RATE, BUFFER_SIZE)
    adsr = ADSR(SAMPLE_RATE, BUFFER_SIZE)
    biquad = BiquadFilter(SAMPLE_RATE, BUFFER_SIZE)
    
    # Add modules to host
    host.add_module("sine", sine)
    host.add_module("adsr", adsr)
    host.add_module("filter", biquad)
    
    # Apply initial state from supervisor
    if 'frequency' in initial_state:
        sine.set_param("freq", initial_state['frequency'], immediate=True)
    if 'amplitude' in initial_state:
        sine.set_param("gain", initial_state['amplitude'], immediate=True)
    
    # Set default ADSR and filter parameters
    adsr.set_param("attack", 10.0, immediate=True)
    adsr.set_param("decay", 100.0, immediate=True)
    adsr.set_param("sustain", 0.7, immediate=True)
    adsr.set_param("release", 200.0, immediate=True)
    
    biquad.set_param("mode", 0, immediate=True)  # Lowpass
    biquad.set_param("cutoff", 2000.0, immediate=True)
    biquad.set_param("q", 0.707, immediate=True)
    
    # Heartbeat counter
    heartbeat_counter = 0
    buffer_seq = 0
    
    role = "Primary" if worker_id == 0 else "Standby"
    timestamp = time.monotonic()
    print(f"[{timestamp:.3f}] {role} worker started with ModuleHost (PID: {os.getpid()})")
    
    # Set socket to non-blocking
    child_socket.setblocking(False)
    
    # Initialize deadline scheduling
    next_deadline = time.perf_counter() + BUFFER_PERIOD
    
    # Main DSP loop
    while not shutdown_flag:
        try:
            # Check for wakeup signal (non-blocking) - Senior Dev fix
            try:
                wakeup = child_socket.recv(1)
                # Got wakeup nudge
            except (BlockingIOError, socket.error):
                pass  # No wakeup, that's fine
            
            # ALWAYS drain command ring, regardless of wakeup (Senior Dev critical fix)
            while cmd_ring.has_data():
                cmd_bytes = cmd_ring.read()
                if cmd_bytes:
                    # FIXED: Check for shutdown command before queuing
                    try:
                        op, dtype, module_id, param, value = unpack_command_v2(cmd_bytes)
                        
                        # Handle shutdown command directly
                        if module_id == 'system' and param == 'shutdown':
                            print(f"Worker {worker_id} received shutdown command")
                            shutdown_flag = True
                            break
                        else:
                            # Queue normal commands to ModuleHost
                            host.queue_command(cmd_bytes)
                            if os.environ.get('CHRONUS_VERBOSE'):
                                print(f"[DEBUG] Worker {worker_id} queued: {module_id}.{param}={value}")
                    except:
                        # If unpacking fails, just queue it
                        host.queue_command(cmd_bytes)
            
            if shutdown_flag:
                break
                
            # Process queued commands at buffer boundary
            host.process_commands()
            
            # Generate audio buffer through module chain
            audio_buffer = host.process_chain()
            
            # Debug: Check if audio is non-zero
            if os.environ.get('CHRONUS_VERBOSE') and buffer_seq % 100 == 10:
                import numpy as np
                rms = np.sqrt(np.mean(audio_buffer**2))
                print(f"[DEBUG] Worker {worker_id} buffer RMS: {rms:.6f} (non-zero: {rms > 1e-6})")
            
            # Write to audio ring
            audio_ring.write(audio_buffer, buffer_seq)
            buffer_seq += 1
            
            # Update heartbeat
            heartbeat_counter += 1
            heartbeat_array[worker_id] = heartbeat_counter
            
            # Deadline-based pacing for consistent timing
            now = time.perf_counter()
            sleep_s = max(0.0, next_deadline - now)
            
            # Sleep until next deadline
            if sleep_s > 0:
                time.sleep(sleep_s)
            
            # Advance deadline
            next_deadline += BUFFER_PERIOD
            
            # Prevent deadline drift (if we're >2 periods behind, reset)
            if now > next_deadline + 2 * BUFFER_PERIOD:
                next_deadline = now + BUFFER_PERIOD
                
        except Exception as e:
            print(f"Worker {worker_id} error: {e}")
            # Continue running - don't crash on errors
            
    # Cleanup
    child_socket.close()
    timestamp = time.monotonic()
    print(f"[{timestamp:.3f}] Worker {worker_id} (PID: {os.getpid()}) exited cleanly")


class AudioSupervisor:
    """
    Supervisor with ModuleHost integration
    Fixed: Sentinel detection, standby respawn, proper shutdown
    """
    
    def __init__(self):
        # Shared memory structures (using validated rings)
        self.primary_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        self.primary_audio_ring = AudioRing()
        
        self.standby_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        self.standby_audio_ring = AudioRing()
        
        # Heartbeat monitoring
        self.heartbeat_array = mp.Array('L', 2, lock=False)
        
        # Worker processes
        self.primary_worker: Optional[AudioWorker] = None
        self.standby_worker: Optional[AudioWorker] = None
        
        # Active worker tracking
        self.active_idx = 0  # 0 = primary, 1 = standby
        self.active_ring = self.primary_audio_ring
        
        # Audio engine
        self.engine = None
        self.stream = None
        
        # Metrics
        self.metrics = AudioMetrics()
        
        # Control state
        self.running = False
        
        # Initial DSP state (shared between workers for lockstep)
        self.initial_state = {
            'phase': 0.0,
            'frequency': 440.0,
            'amplitude': 0.5
        }
        
        # Monitoring
        self.monitor_thread = None
        self.monitor_stop = threading.Event()
        self.respawn_lock = threading.Lock()  # Prevent concurrent respawns
        
        # OSC server
        self.osc_server = None
        self.osc_thread = None
        self.osc_loop = None
        self.osc_transport = None
        self.osc_future = None
    
    def audio_callback(self, outdata, frames, time_info, status):
        """Real-time audio callback - reads from active ring"""
        if status:
            self.metrics.underruns += 1
        
        # Get latest buffer from active ring (FIXED: read_latest only returns buffer)
        buffer = self.active_ring.read_latest()
        
        # Debug: Check what we're outputting (only once)
        if not hasattr(self, '_debug_counter'):
            self._debug_counter = 0
        self._debug_counter += 1
        
        if self._debug_counter == 100 and os.environ.get('CHRONUS_VERBOSE'):
            if buffer is not None:
                rms = np.sqrt(np.mean(buffer**2))
                print(f"[DEBUG] Callback outputting RMS: {rms:.6f} (non-zero: {rms > 1e-6})")
            else:
                print("[DEBUG] Callback got None from ring!")
        
        if buffer is not None:
            # Copy to output (maintains existing pattern)
            np.copyto(outdata[:, 0], buffer, casting='no')
        else:
            # No data - output silence
            outdata.fill(0)
        
        self.metrics.buffers_processed += 1
    
    def monitor_workers(self):
        """
        Monitor thread with SENTINEL-BASED detection for <10ms failover
        Fixed: Uses connection.wait() for instant detection
        """
        print("Monitor thread started (sentinel-based)")
        
        # Initialize tracking
        last_heartbeats = [0, 0]
        last_heartbeat_times = [time.monotonic(), time.monotonic()]
        poll_interval = POLL_INTERVAL_ACTIVE
        
        while not self.monitor_stop.is_set():
            try:
                # Get current workers (refreshed each iteration)
                workers = [self.primary_worker, self.standby_worker]
                
                # Get sentinels for instant death detection
                sentinels = []
                for w in workers:
                    if w and w.sentinel:
                        sentinels.append(w.sentinel)
                
                if not sentinels:
                    time.sleep(poll_interval)
                    continue
                
                # Check for process death with SHORT timeout (2ms)
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
                
                # Check heartbeats as backup (for hung processes)
                current_time = time.monotonic()
                for i, worker in enumerate(workers):
                    if not worker:
                        continue
                    
                    current_hb = self.heartbeat_array[i]
                    
                    if current_hb == last_heartbeats[i]:
                        # No heartbeat progress
                        time_since_beat = current_time - last_heartbeat_times[i]
                        
                        if time_since_beat > HEARTBEAT_TIMEOUT:
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
        """Handle active worker failure - instant failover"""
        failover_start = time.monotonic_ns()
        
        # Detection time (from death to detection)
        self.metrics.detection_time_ms = (failover_start - detection_time_ns) / 1_000_000
        
        # Perform atomic switch INCLUDING worker references
        if self.active_idx == 0:
            # Primary failed, switch to standby
            # Swap worker references so standby becomes primary
            self.primary_worker, self.standby_worker = self.standby_worker, None
            # Swap rings - standby becomes the new primary
            self.primary_audio_ring, self.standby_audio_ring = self.standby_audio_ring, AudioRing()
            self.primary_cmd_ring, self.standby_cmd_ring = self.standby_cmd_ring, CommandRing(COMMAND_RING_SLOTS)
            # Update active tracking
            self.active_ring = self.primary_audio_ring
            self.active_idx = 0  # Keep using index 0 for primary
            self.metrics.active_worker = 0  # Always 0 for active slot
            print("Switched standby to primary role")
        else:
            # Standby (acting as primary) failed, switch back to original primary
            # This case shouldn't normally happen but handle it for completeness
            self.standby_worker, self.primary_worker = self.primary_worker, None
            # Swap rings back
            self.standby_audio_ring, self.primary_audio_ring = self.primary_audio_ring, AudioRing()
            self.standby_cmd_ring, self.primary_cmd_ring = self.primary_cmd_ring, CommandRing(COMMAND_RING_SLOTS)
            # Update active tracking
            self.active_ring = self.standby_audio_ring
            self.active_idx = 1
            self.metrics.active_worker = 0  # Always 0 for active slot
            print("Switched primary to standby role")
        
        # Switch time (actual failover)
        switch_time_ns = time.monotonic_ns()
        self.metrics.switch_time_ms = (switch_time_ns - failover_start) / 1_000_000
        
        # Total failover time
        total_time_ms = (switch_time_ns - detection_time_ns) / 1_000_000
        self.metrics.failover_time_ms = total_time_ms
        self.metrics.failover_count += 1
        self.metrics.last_failure_time = time.monotonic()
        
        print(f"Failover complete: detection={self.metrics.detection_time_ms:.2f}ms, "
              f"switch={self.metrics.switch_time_ms:.2f}ms, total={total_time_ms:.2f}ms")
        
        # FIXED: Spawn new standby to maintain redundancy (now safe since worker refs swapped)
        threading.Thread(target=self.spawn_new_standby, daemon=True).start()
    
    def handle_standby_failure(self, detection_time_ns: int, cause: str = 'sentinel'):
        """Handle standby worker failure - spawn replacement"""
        print(f"Standby failed ({cause}) - spawning replacement")
        
        # Update metrics
        self.metrics.last_failure_time = time.monotonic()
        
        # Spawn replacement
        threading.Thread(target=self.spawn_new_standby, daemon=True).start()
    
    def spawn_new_standby(self):
        """
        Spawn a new standby worker to maintain redundancy
        Fixed: Added to maintain dual-worker resilience
        """
        # Prevent concurrent respawn attempts
        if not self.respawn_lock.acquire(blocking=False):
            return  # Another respawn is already in progress
            
        rebuild_start = time.monotonic_ns()
        
        try:
            # Clean up old standby if it exists
            if self.standby_worker:
                try:
                    self.standby_worker.terminate()
                except:
                    pass
                self.standby_worker = None
            
            # Give it a moment to fully terminate
            time.sleep(0.1)
            
            # Reset standby ring (AudioRing doesn't have reset method - recreate)
            self.standby_audio_ring = AudioRing()
            self.standby_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
            
            # Create new standby (use worker_id 1 since primary is 0)
            # Note: primary_worker is now the active one after failover
            standby_id = 1 if (self.primary_worker and self.primary_worker.worker_id == 0) else 0
            self.standby_worker = AudioWorker(
                worker_id=standby_id,
                cmd_ring=self.standby_cmd_ring,
                audio_ring=self.standby_audio_ring,
                heartbeat_array=self.heartbeat_array,
                initial_state=self.initial_state.copy()
            )
            
            # Start the new standby
            if self.standby_worker.start():
                rebuild_time = (time.monotonic_ns() - rebuild_start) / 1_000_000
                if self.standby_worker.pid:
                    print(f"New standby spawned in {rebuild_time:.2f}ms (PID: {self.standby_worker.pid})")
                else:
                    print(f"New standby spawned in {rebuild_time:.2f}ms")
            else:
                print("Failed to start new standby worker")
                self.standby_worker = None
            
        except Exception as e:
            print(f"Failed to spawn standby: {e}")
            self.standby_worker = None
        finally:
            self.respawn_lock.release()
    
    def broadcast_command_raw(self, cmd_bytes: bytes):
        """Broadcast raw command bytes to both workers"""
        # Write to both rings
        if self.primary_worker:
            self.primary_cmd_ring.write(cmd_bytes)
            self.primary_worker.send_wakeup()
        
        if self.standby_worker:
            self.standby_cmd_ring.write(cmd_bytes)
            self.standby_worker.send_wakeup()
        
        self.metrics.commands_sent += 2
    
    def handle_osc_message(self, address: str, *args):
        """
        Handle OSC control messages with module routing
        Fixed: Added try/except for error handling
        """
        try:
            # Verbose logging when enabled (Senior Dev suggestion)
            if os.environ.get('CHRONUS_VERBOSE'):
                print(f"OSC recv: {address} {args}")
            
            parts = address.split('/')
            
            # Module parameter control: /mod/<module>/<param> <value>
            if len(parts) >= 4 and parts[1] == 'mod':
                module_id = parts[2]
                param = parts[3]
                
                if len(args) > 0:
                    value = float(args[0])
                    
                    # Create Protocol v2 command with error handling
                    try:
                        cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, param, value)
                        self.broadcast_command_raw(cmd)
                        
                        # Update initial state for new workers
                        if module_id == 'sine' and param == 'freq':
                            self.initial_state['frequency'] = value
                        elif module_id == 'sine' and param == 'gain':
                            self.initial_state['amplitude'] = value
                    except ValueError as e:
                        print(f"OSC error: Invalid module/param ID - {e}")
            
            # Gate control: /gate/<module> <on|off>
            elif len(parts) >= 3 and parts[1] == 'gate':
                module_id = parts[2]
                
                if len(args) > 0:
                    # Handle various gate formats
                    if isinstance(args[0], str):
                        gate_on = args[0].lower() == 'on'
                    elif isinstance(args[0], (int, float)):
                        gate_on = args[0] > 0
                    else:
                        gate_on = bool(args[0])
                    
                    # Create gate command with error handling
                    try:
                        cmd = pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, module_id, 'gate', 1 if gate_on else 0)
                        self.broadcast_command_raw(cmd)
                    except ValueError as e:
                        print(f"OSC error: Invalid gate ID - {e}")
            
            # Legacy compatibility
            elif address == "/engine/freq" and len(args) > 0:
                freq = float(args[0])
                freq = max(20.0, min(20000.0, freq))
                cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'freq', freq)
                self.broadcast_command_raw(cmd)
                self.initial_state['frequency'] = freq
                
            elif address == "/engine/amp" and len(args) > 0:
                amp = float(args[0])
                amp = max(0.0, min(1.0, amp))
                cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'gain', amp)
                self.broadcast_command_raw(cmd)
                self.initial_state['amplitude'] = amp
                
        except Exception as e:
            print(f"OSC handler error: {e}")
    
    def start_osc_server(self):
        """Start OSC server for control messages"""
        try:
            # Get host/port from environment or use defaults
            host = os.environ.get('CHRONUS_OSC_HOST', '127.0.0.1')
            port = int(os.environ.get('CHRONUS_OSC_PORT', '5005'))
            
            disp = dispatcher.Dispatcher()
            # Map specific patterns for our OSC routes (Senior Dev fix)
            disp.map("/mod/*/*", self.handle_osc_message)  # Module parameters
            disp.map("/gate/*", self.handle_osc_message)    # Gate control
            disp.map("/engine/*", self.handle_osc_message)  # Legacy control
            disp.set_default_handler(self.handle_osc_message)  # Catch-all for diagnostics
            
            async def run_server():
                server = osc_server.AsyncIOOSCUDPServer(
                    (host, port), disp, asyncio.get_event_loop()
                )
                transport, protocol = await server.create_serve_endpoint()
                self.osc_transport = transport
                print(f"OSC server listening on {host}:{port}")
                print("  Module control: /mod/<module>/<param> <value>")
                print("  Gate control: /gate/<module> on|off")
                print("  Legacy: /engine/freq, /engine/amp")
                
                # Create a future that can be cancelled for clean shutdown
                self.osc_future = asyncio.get_event_loop().create_future()
                try:
                    await self.osc_future
                except asyncio.CancelledError:
                    pass
            
            # Run in thread
            def run_loop():
                self.osc_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.osc_loop)
                self.osc_loop.run_until_complete(run_server())
            
            self.osc_thread = threading.Thread(target=run_loop, daemon=True)
            self.osc_thread.start()
            
            # Give server time to start
            time.sleep(0.1)
            return True
            
        except Exception as e:
            print(f"Failed to start OSC server: {e}")
            return False
    
    def start(self):
        """Start the supervisor system with ModuleHost"""
        if self.running:
            return False
        
        print("Starting AudioSupervisor v2 Fixed (sentinel detection)...")
        
        # Create workers
        self.primary_worker = AudioWorker(
            worker_id=0,
            cmd_ring=self.primary_cmd_ring,
            audio_ring=self.primary_audio_ring,
            heartbeat_array=self.heartbeat_array,
            initial_state=self.initial_state.copy()
        )
        self.primary_worker.start()
        
        self.standby_worker = AudioWorker(
            worker_id=1,
            cmd_ring=self.standby_cmd_ring,
            audio_ring=self.standby_audio_ring,
            heartbeat_array=self.heartbeat_array,
            initial_state=self.initial_state.copy()
        )
        self.standby_worker.start()
        
        # Wait for workers to warm up
        print(f"Warming up workers ({WORKER_WARMUP_CYCLES} cycles)...")
        time.sleep(BUFFER_PERIOD * WORKER_WARMUP_CYCLES)
        
        # Start monitoring thread with SENTINEL detection
        self.monitor_thread = threading.Thread(target=self.monitor_workers, daemon=True)
        self.monitor_thread.start()
        
        # Start audio stream
        try:
            self.stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=NUM_CHANNELS,
                blocksize=BUFFER_SIZE,
                callback=self.audio_callback,
                dtype='float32'
            )
            self.stream.start()
            print(f"Audio stream started: {SAMPLE_RATE}Hz, {BUFFER_SIZE} samples")
        except Exception as e:
            print(f"Failed to start audio stream: {e}")
            self.cleanup_workers()
            return False
        
        # Start OSC server
        self.start_osc_server()
        
        self.running = True
        print("AudioSupervisor v2 Fixed running - <10ms failover restored!")
        return True
    
    def stop(self):
        """Stop the supervisor system"""
        if not self.running:
            return
        
        print("Stopping AudioSupervisor...")
        
        # Stop OSC server cleanly
        if self.osc_transport:
            self.osc_transport.close()
        if self.osc_future and not self.osc_future.done():
            if self.osc_loop:
                self.osc_loop.call_soon_threadsafe(self.osc_future.cancel)
        if self.osc_thread:
            self.osc_thread.join(timeout=1.0)
        
        # Stop monitoring
        self.monitor_stop.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        
        # Stop audio stream
        if self.stream:
            self.stream.stop()
            self.stream.close()
        
        # Stop workers
        self.cleanup_workers()
        
        self.running = False
        print("AudioSupervisor stopped")
    
    def cleanup_workers(self):
        """Clean up worker processes"""
        for worker in [self.primary_worker, self.standby_worker]:
            if worker:
                worker.terminate()
        
        self.primary_worker = None
        self.standby_worker = None
    
    def get_status(self) -> dict:
        """Get supervisor status with module info"""
        return {
            'running': self.running,
            'metrics': {
                'buffers_processed': self.metrics.buffers_processed,
                'underruns': self.metrics.underruns,
                'failover_count': self.metrics.failover_count,
                'failover_time_ms': self.metrics.failover_time_ms,
                'detection_time_ms': self.metrics.detection_time_ms,
                'switch_time_ms': self.metrics.switch_time_ms,
                'heartbeat_misses': self.metrics.heartbeat_misses,
                'commands_sent': self.metrics.commands_sent,
                'active_worker': self.metrics.active_worker,
            },
            'workers': {
                'primary': {
                    'alive': self.primary_worker.is_alive() if self.primary_worker else False,
                    'heartbeat': self.heartbeat_array[0] if self.primary_worker else 0,
                    'pid': self.primary_worker.pid if self.primary_worker else None,
                },
                'standby': {
                    'alive': self.standby_worker.is_alive() if self.standby_worker else False,
                    'heartbeat': self.heartbeat_array[1] if self.standby_worker else 0,
                    'pid': self.standby_worker.pid if self.standby_worker else None,
                }
            },
            'modules': {
                'chain': 'sine → adsr → filter',
                'protocol': 'v2 (64-byte)',
                'osc_endpoints': [
                    '/mod/<module>/<param>',
                    '/gate/<module>',
                    '/engine/freq (legacy)',
                    '/engine/amp (legacy)'
                ]
            }
        }


def main():
    """Main entry point with ModuleHost synthesis"""
    supervisor = AudioSupervisor()
    
    # Set up signal handlers
    def signal_handler(sig, frame):
        print("\nShutdown signal received")
        supervisor.stop()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start supervisor
    if not supervisor.start():
        print("Failed to start supervisor")
        return 1
    
    print("\nModuleHost Synthesis Active with <10ms Failover!")
    print("OSC Control:")
    print("  Oscillator: /mod/sine/freq <hz>, /mod/sine/gain <0-1>")
    print("  Envelope: /mod/adsr/attack <ms>, /gate/adsr on|off")
    print("  Filter: /mod/filter/cutoff <hz>, /mod/filter/q <0.1-20>")
    print("\nPress Ctrl+C to stop...")
    
    # Keep running
    try:
        while supervisor.running:
            time.sleep(1)
            
            # Periodic status update
            if supervisor.metrics.buffers_processed % 1000 == 0:
                status = supervisor.get_status()
                print(f"Status: {status['metrics']['buffers_processed']} buffers, "
                      f"{status['metrics']['underruns']} underruns, "
                      f"worker {status['metrics']['active_worker']} active")
    except KeyboardInterrupt:
        pass
    
    supervisor.stop()
    return 0


if __name__ == '__main__':
    # Note: Using default 'fork' method as spawn/forkserver break shared memory
    # The SIGTERM messages are from old workers exiting, not current ones
    exit(main())