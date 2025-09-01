#!/usr/bin/env python3
"""
Phase 1C: Audio Supervisor with Process Supervision
Minimal combined runner for testing fault-tolerant audio with imperceptible failover
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

# Configuration
SAMPLE_RATE = 44100
BUFFER_SIZE = 256
CHANNELS = 1
NUM_BUFFERS = 4  # Ring buffer depth
DEFAULT_FREQUENCY = 440.0
DEFAULT_AMPLITUDE = 0.5

# Timing constants
POLL_INTERVAL_ACTIVE = 0.002  # 2ms when active
POLL_INTERVAL_IDLE = 0.005   # 5ms when idle
HEARTBEAT_TIMEOUT = 0.015    # 15ms (2.5x buffer period)
BUFFER_PERIOD = BUFFER_SIZE / SAMPLE_RATE  # ~5.8ms


class AudioRing:
    """
    Lock-free SPSC ring buffer for audio data
    Cache-line aligned indices to avoid false sharing
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
        # mp.Array already provides a buffer interface
        self._np_buffer = np.frombuffer(self.buffer, dtype=np.float32)
        
        # Metrics
        self.overruns = mp.Value('Q', 0, lock=False)
        self.underruns = mp.Value('Q', 0, lock=False)
    
    def write(self, audio_data, seq_num):
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
        self.sequence[idx] = seq_num
        
        # Update head (memory barrier implicit in mp.Value)
        self.head.value = next_head
        return True
    
    def read_latest(self):
        """
        Consumer reads newest buffer (main process)
        Implements "latest wins" policy - skips old buffers
        Returns a view, not a copy - zero allocations
        """
        # Check if empty
        if self.head.value == self.tail.value:
            self.underruns.value += 1
            return None
        
        # Find newest complete buffer (one behind head)
        newest_idx = (self.head.value - 1) % self.num_buffers
        
        # Return view into persistent buffer - no allocation!
        offset = newest_idx * self.frames_per_buffer
        audio_view = self._np_buffer[offset:offset + self.frames_per_buffer]
        
        # Advance tail to just behind head (skip old buffers)
        self.tail.value = self.head.value
        
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
    Based on IPC-04 validated pattern
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
        # The packets contain binary data with embedded zeros
        return cmd_data
    
    def has_data(self):
        """Check if ring has data"""
        return self.read_idx.value != self.write_idx.value
    
    def reset(self):
        """Reset ring buffer to clean state"""
        # Zero indices
        self.write_idx.value = 0
        self.read_idx.value = 0
        
        # Zero buffer to prevent garbage interpretation
        # mp.Array is already zero-initialized, but be explicit
        for i in range(self.num_slots * self.slot_size):
            self.buffer[i] = b'\x00'


def pack_command(param: str, value: float) -> bytes:
    """Pack command into binary format"""
    # Format: 16-byte param name + 8-byte float value
    param_bytes = param.encode('utf-8')[:16].ljust(16, b'\x00')
    value_bytes = struct.pack('d', value)
    return param_bytes + value_bytes


def unpack_command(cmd_bytes: bytes) -> Tuple[str, float]:
    """Unpack command from binary format"""
    if len(cmd_bytes) < 24:
        return None, None
    
    param = cmd_bytes[:16].rstrip(b'\x00').decode('utf-8')
    value = struct.unpack('d', cmd_bytes[16:24])[0]
    return param, value


def audio_worker_process(worker_id: int, cmd_ring: CommandRing, audio_ring: AudioRing, 
                         heartbeat_array, initial_state: dict, 
                         parent_socket: socket.socket, child_socket: socket.socket):
    """
    DSP worker process - generates audio continuously in lockstep
    Both primary and standby run identically
    """
    # Close parent's socket end
    parent_socket.close()
    
    # Set up signal handler for clean exit
    shutdown_flag = False
    def handle_sigterm(signum, frame):
        nonlocal shutdown_flag
        shutdown_flag = True
        print(f"Worker {worker_id} received SIGTERM")
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    # Initialize DSP state from synchronized initial state
    phase = initial_state['phase']
    frequency = initial_state['frequency']
    amplitude = initial_state['amplitude']
    
    # Pre-allocate buffers
    audio_buffer = np.zeros(BUFFER_SIZE, dtype=np.float32)
    phase_increment = 2.0 * np.pi * frequency / SAMPLE_RATE
    
    # Heartbeat counter
    heartbeat_counter = 0
    buffer_seq = 0
    
    role = "Primary" if worker_id == 0 else "Standby"
    print(f"{role} worker started (PID: {os.getpid()})")
    
    # Set socket to non-blocking once (not in loop)
    child_socket.setblocking(False)
    
    # Initialize deadline scheduling
    next_deadline = time.perf_counter() + BUFFER_PERIOD
    
    # Main DSP loop
    while not shutdown_flag:
        try:
            # Check for commands (non-blocking)
            try:
                wakeup = child_socket.recv(1)
                # Got wakeup - check command ring
                while cmd_ring.has_data():
                    cmd_bytes = cmd_ring.read()
                    if cmd_bytes:
                        param, value = unpack_command(cmd_bytes)
                        if param == 'frequency':
                            frequency = value
                            phase_increment = 2.0 * np.pi * frequency / SAMPLE_RATE
                        elif param == 'amplitude':
                            amplitude = value
                        elif param == 'shutdown':
                            print(f"Worker {worker_id} shutting down")
                            shutdown_flag = True
            except (BlockingIOError, socket.error):
                pass  # No commands available
            
            # Generate audio buffer (sine wave)
            t = np.arange(BUFFER_SIZE) * phase_increment + phase
            audio_buffer = amplitude * np.sin(t, dtype=np.float32)
            
            # Update phase (maintain continuity)
            phase = (phase + BUFFER_SIZE * phase_increment) % (2.0 * np.pi)
            
            # Write to audio ring
            audio_ring.write(audio_buffer, buffer_seq)
            buffer_seq += 1
            
            # Update heartbeat
            heartbeat_counter += 1
            heartbeat_array[worker_id] = heartbeat_counter
            
            # Deadline-based pacing for consistent timing
            now = time.perf_counter()
            sleep_s = max(0.0, next_deadline - now)
            
            # Check shutdown before sleeping
            if shutdown_flag:
                break
                
            # Sleep until next deadline
            if sleep_s > 0:
                time.sleep(sleep_s)
            
            # Schedule next deadline
            next_deadline += BUFFER_PERIOD
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Worker {worker_id} error: {e}")
            break
    
    print(f"Worker {worker_id} exiting")


class AudioWorker:
    """Wrapper for a worker process with monitoring info"""
    
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
            # Send shutdown command
            self.cmd_ring.write(pack_command('shutdown', 0))
            self.send_wakeup()
            
            # Wait briefly for clean shutdown
            self.process.join(timeout=1.0)
            
            # Force terminate if still alive
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1.0)
            
            # Force kill if still alive
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=1.0)
        
        # Close socket
        if self.parent_socket:
            self.parent_socket.close()


@dataclass
class SupervisorMetrics:
    """Metrics tracking for supervisor"""
    crash_count: int = 0
    replacements: int = 0
    failovers: int = 0
    commands_sent: int = 0
    detection_times_ns: List[int] = field(default_factory=list)
    failover_times_ns: List[int] = field(default_factory=list)
    rebuild_times_ns: List[int] = field(default_factory=list)
    shm_leaks: int = 0
    spare_ready: bool = True
    last_failure_time: Optional[float] = None
    
    def record_failover(self, time_ns: int, cause: str):
        """Record failover event"""
        self.failovers += 1
        self.failover_times_ns.append(time_ns)
        self.last_failure_time = time.monotonic()
        print(f"Failover completed in {time_ns/1_000_000:.2f}ms (cause: {cause})")
    
    def get_percentile(self, data_ns: List[int], percentile: int) -> float:
        """Get percentile in milliseconds"""
        if not data_ns:
            return 0.0
        sorted_data = sorted(data_ns)
        idx = int(len(sorted_data) * percentile / 100)
        idx = min(idx, len(sorted_data) - 1)
        return sorted_data[idx] / 1_000_000  # Convert to ms


class AudioSupervisor:
    """
    Main supervisor managing worker processes and audio output
    Audio I/O stays in main process for continuous output
    """
    
    def __init__(self):
        # Pre-allocate rings for primary and standby
        self.primary_audio_ring = AudioRing()
        self.standby_audio_ring = AudioRing()
        
        self.primary_cmd_ring = CommandRing()
        self.standby_cmd_ring = CommandRing()
        
        # Shared heartbeat array
        self.heartbeat_array = mp.Array('Q', 2, lock=False)  # [primary, standby]
        
        # Initial synchronized state
        self.initial_state = {
            'phase': 0.0,
            'frequency': DEFAULT_FREQUENCY,
            'amplitude': DEFAULT_AMPLITUDE
        }
        
        # Workers
        self.primary_worker = None
        self.standby_worker = None
        
        # Active ring pointer (which ring audio callback reads from)
        self.active_ring = self.primary_audio_ring
        self.active_idx = 0  # 0=primary, 1=standby
        
        # Audio stream
        self.audio_stream = None
        
        # Monitor thread
        self.monitor_thread = None
        self.monitor_stop = threading.Event()
        
        # OSC server
        self.osc_server = None
        self.osc_thread = None
        self.osc_loop = None
        self.osc_transport = None
        self.osc_future = None
        
        # Metrics
        self.metrics = SupervisorMetrics()
        
        # State
        self.running = False
        
        print("AudioSupervisor initialized")
    
    def start_workers(self):
        """Start primary and standby workers"""
        # Create primary worker
        self.primary_worker = AudioWorker(
            worker_id=0,
            cmd_ring=self.primary_cmd_ring,
            audio_ring=self.primary_audio_ring,
            heartbeat_array=self.heartbeat_array,
            initial_state=self.initial_state.copy()
        )
        
        # Create standby worker  
        self.standby_worker = AudioWorker(
            worker_id=1,
            cmd_ring=self.standby_cmd_ring,
            audio_ring=self.standby_audio_ring,
            heartbeat_array=self.heartbeat_array,
            initial_state=self.initial_state.copy()
        )
        
        # Start both workers
        if not self.primary_worker.start():
            raise RuntimeError("Failed to start primary worker")
        
        if not self.standby_worker.start():
            raise RuntimeError("Failed to start standby worker")
        
        print(f"Workers started - Primary PID: {self.primary_worker.pid}, Standby PID: {self.standby_worker.pid}")
        self.metrics.spare_ready = True
        
        return True
    
    def audio_callback(self, outdata, frames, time_info, status):
        """
        Main process audio callback - never stops during failover
        Reads from whichever ring is active
        Zero-allocation path using view and copyto
        """
        if status:
            print(f"Audio status: {status}")
        
        # Read from active ring (latest-wins policy) - returns a view
        audio_view = self.active_ring.read_latest()
        
        if audio_view is not None and len(audio_view) == frames:
            # Direct copy from view to output - no allocations
            np.copyto(outdata[:, 0], audio_view, casting='no')
        else:
            # Silence on underrun
            outdata.fill(0)
    
    def monitor_workers(self):
        """
        Monitor thread - checks sentinels and heartbeats
        Runs with 2ms polling interval
        """
        print("Monitor thread started")
        
        # Initialize tracking
        last_heartbeats = [0, 0]
        last_heartbeat_times = [time.monotonic(), time.monotonic()]
        poll_interval = POLL_INTERVAL_ACTIVE
        
        while not self.monitor_stop.is_set():
            try:
                # Get current workers (refreshed each iteration)
                workers = [self.primary_worker, self.standby_worker]
                
                # Get sentinels
                sentinels = []
                for w in workers:
                    if w and w.sentinel:
                        sentinels.append(w.sentinel)
                
                if not sentinels:
                    time.sleep(poll_interval)
                    continue
                
                # Check for process death with timeout
                ready = connection.wait(sentinels, timeout=poll_interval)
                
                if ready:
                    # A worker died - identify which one
                    for i, worker in enumerate(workers):
                        if worker and worker.sentinel in ready:
                            detection_time = time.monotonic_ns()
                            
                            if i == self.active_idx:
                                # Primary died - failover to standby
                                print(f"Primary worker died - failing over to standby")
                                self.handle_primary_failure(detection_time)
                            else:
                                # Standby died - spawn new one
                                print(f"Standby worker died - spawning replacement")
                                self.handle_standby_failure(detection_time)
                            break
                
                # Check heartbeats
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
                                print(f"Primary worker hung (no heartbeat) - failing over")
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
        """Handle primary worker failure - instant failover"""
        failover_start = time.monotonic_ns()
        
        # 1. Atomic switch to standby ring
        self.active_ring = self.standby_audio_ring
        
        # 2. Record metrics
        failover_time = time.monotonic_ns() - failover_start
        self.metrics.record_failover(failover_time, cause)
        self.metrics.crash_count += 1
        
        # 3. Swap worker references (standby becomes primary)
        old_primary = self.primary_worker
        self.primary_worker = self.standby_worker
        self.standby_worker = None
        self.metrics.spare_ready = False
        
        # Swap rings too
        self.primary_audio_ring, self.standby_audio_ring = self.standby_audio_ring, self.primary_audio_ring
        self.primary_cmd_ring, self.standby_cmd_ring = self.standby_cmd_ring, self.primary_cmd_ring
        
        # Update active index (primary is always 0 now after swap)
        self.active_idx = 0
        self.active_ring = self.primary_audio_ring  # Point to the new primary ring
        
        # 4. Clean up dead worker
        if old_primary:
            try:
                old_primary.terminate()
            except:
                pass
        
        # 5. Spawn new standby (background)
        threading.Thread(target=self.spawn_new_standby, daemon=True).start()
    
    def handle_standby_failure(self, detection_time_ns: int, cause: str = 'sentinel'):
        """Handle standby worker failure - spawn replacement"""
        print(f"Standby failed ({cause}) - spawning replacement")
        
        # Clean up dead standby
        if self.standby_worker:
            try:
                self.standby_worker.terminate()
            except:
                pass
        
        self.standby_worker = None
        self.metrics.spare_ready = False
        self.metrics.crash_count += 1
        
        # Spawn replacement
        self.spawn_new_standby()
    
    def spawn_new_standby(self):
        """Spawn a new standby worker"""
        rebuild_start = time.monotonic_ns()
        
        try:
            # Reset standby ring
            self.standby_audio_ring.reset()
            self.standby_cmd_ring = CommandRing()  # Fresh command ring
            
            # Create new standby (always uses slot 1)
            self.standby_worker = AudioWorker(
                worker_id=1,
                cmd_ring=self.standby_cmd_ring,
                audio_ring=self.standby_audio_ring,
                heartbeat_array=self.heartbeat_array,
                initial_state=self.initial_state.copy()
            )
            
            # Update primary worker ID to 0 if it was previously standby
            if self.primary_worker and self.primary_worker.worker_id != 0:
                self.primary_worker.worker_id = 0
            
            # Start standby
            if self.standby_worker.start():
                rebuild_time = time.monotonic_ns() - rebuild_start
                self.metrics.rebuild_times_ns.append(rebuild_time)
                self.metrics.replacements += 1
                self.metrics.spare_ready = True
                print(f"New standby spawned in {rebuild_time/1_000_000:.2f}ms")
            else:
                print("Failed to spawn new standby")
                self.metrics.spare_ready = False
                
        except Exception as e:
            print(f"Error spawning standby: {e}")
            self.metrics.spare_ready = False
    
    def broadcast_command(self, param: str, value: float):
        """Broadcast command to both workers for lockstep operation"""
        cmd = pack_command(param, value)
        
        # Write to both rings
        if self.primary_worker:
            self.primary_cmd_ring.write(cmd)
            self.primary_worker.send_wakeup()
        
        if self.standby_worker:
            self.standby_cmd_ring.write(cmd)
            self.standby_worker.send_wakeup()
        
        self.metrics.commands_sent += 2
    
    def handle_osc_message(self, address: str, *args):
        """Handle OSC control messages"""
        if address == "/engine/freq" and len(args) > 0:
            freq = float(args[0])
            freq = max(20.0, min(20000.0, freq))  # Sanitize
            self.initial_state['frequency'] = freq
            self.broadcast_command('frequency', freq)
            
        elif address == "/engine/gain" and len(args) > 0:
            gain = float(args[0])
            gain = max(0.0, min(1.0, gain))  # Sanitize
            self.initial_state['amplitude'] = gain
            self.broadcast_command('amplitude', gain)
    
    def start_osc_server(self):
        """Start OSC server for control messages"""
        try:
            # Get host/port from environment or use defaults
            host = os.environ.get('CHRONUS_OSC_HOST', '127.0.0.1')
            port = int(os.environ.get('CHRONUS_OSC_PORT', '5005'))
            
            disp = dispatcher.Dispatcher()
            disp.map("/engine/*", self.handle_osc_message)
            
            async def run_server():
                server = osc_server.AsyncIOOSCUDPServer(
                    (host, port), disp, asyncio.get_event_loop()
                )
                transport, protocol = await server.create_serve_endpoint()
                self.osc_transport = transport  # Store for cleanup
                print(f"OSC server listening on {host}:{port}")
                # Create a future that can be cancelled for clean shutdown
                self.osc_future = asyncio.get_event_loop().create_future()
                try:
                    await self.osc_future
                except asyncio.CancelledError:
                    pass  # Clean shutdown
            
            def osc_thread_func():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self.osc_loop = loop  # Store for cleanup
                try:
                    loop.run_until_complete(run_server())
                except RuntimeError:
                    pass  # Loop stopped, normal shutdown
            
            self.osc_thread = threading.Thread(target=osc_thread_func, daemon=True)
            self.osc_thread.start()
            return True
            
        except Exception as e:
            print(f"Failed to start OSC server: {e}")
            return False
    
    def start(self):
        """Start the supervisor system"""
        if self.running:
            return False
        
        print("Starting AudioSupervisor...")
        
        # Start workers first
        if not self.start_workers():
            return False
        
        # Wait for workers to start rendering
        time.sleep(0.1)
        
        # Start monitor thread
        self.monitor_stop.clear()
        self.monitor_thread = threading.Thread(target=self.monitor_workers, daemon=True)
        self.monitor_thread.start()
        
        # Start audio stream (in main process)
        try:
            self.audio_stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BUFFER_SIZE,
                channels=CHANNELS,
                dtype='float32',
                latency='low',
                callback=self.audio_callback
            )
            self.audio_stream.start()
            print(f"Audio stream started: {SAMPLE_RATE}Hz, {BUFFER_SIZE} samples/buffer")
        except Exception as e:
            print(f"Failed to start audio: {e}")
            self.stop()
            return False
        
        # Start OSC server
        self.start_osc_server()
        
        self.running = True
        print("AudioSupervisor running - fault tolerance active")
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
            # Cancel the future to trigger clean shutdown
            if self.osc_loop:
                self.osc_loop.call_soon_threadsafe(self.osc_future.cancel)
        if self.osc_loop and self.osc_loop.is_running():
            self.osc_loop.call_soon_threadsafe(self.osc_loop.stop)
        if self.osc_thread:
            self.osc_thread.join(timeout=2)
        
        # Stop monitor
        self.monitor_stop.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        
        # Stop audio (stays open throughout, close only on shutdown)
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
        
        # Stop workers
        if self.primary_worker:
            self.primary_worker.terminate()
        if self.standby_worker:
            self.standby_worker.terminate()
        
        self.running = False
        print("AudioSupervisor stopped")
    
    def get_status(self):
        """Get supervisor status"""
        status = {
            'running': self.running,
            'active_worker': 'primary' if self.active_idx == 0 else 'standby',
            'spare_ready': self.metrics.spare_ready,
            'crash_count': self.metrics.crash_count,
            'failovers': self.metrics.failovers,
            'commands_sent': self.metrics.commands_sent,
            'primary_pid': self.primary_worker.pid if self.primary_worker else None,
            'standby_pid': self.standby_worker.pid if self.standby_worker else None,
            'primary_heartbeat': self.heartbeat_array[0],
            'standby_heartbeat': self.heartbeat_array[1],
            'primary_ring_underruns': self.primary_audio_ring.underruns.value,
            'standby_ring_underruns': self.standby_audio_ring.underruns.value,
        }
        
        if self.metrics.failover_times_ns:
            status['failover_p95_ms'] = self.metrics.get_percentile(self.metrics.failover_times_ns, 95)
            status['failover_p99_ms'] = self.metrics.get_percentile(self.metrics.failover_times_ns, 99)
        
        return status


# Simple test runner
if __name__ == "__main__":
    print("Phase 1C Audio Supervisor - Combined Implementation")
    print("Run test_supervisor.py to test the system")
    
    # Basic smoke test
    supervisor = AudioSupervisor()
    if supervisor.start():
        print("\nSupervisor started successfully!")
        print("Press Ctrl+C to stop...")
        try:
            while True:
                time.sleep(1)
                status = supervisor.get_status()
                print(f"Status: Active={status['active_worker']} (PID={status['primary_pid'] if status['active_worker'] == 'primary' else status['standby_pid']}), "
                      f"Primary PID={status['primary_pid']}, Standby PID={status['standby_pid']}, "
                      f"Heartbeats=[{status['primary_heartbeat']}, {status['standby_heartbeat']}]")
        except KeyboardInterrupt:
            pass
        finally:
            supervisor.stop()
    else:
        print("Failed to start supervisor")