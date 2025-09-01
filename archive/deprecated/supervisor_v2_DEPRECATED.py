"""
AudioSupervisor v2 - Integrates ModuleHost with DSP chain
Changes from v1:
- ModuleHost replaces inline sine generation
- Protocol v2 (64-byte commands)
- OSC routes to module parameters
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
from collections import OrderedDict

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

# Performance targets
TARGET_FAILOVER_MS = 10.0
HEARTBEAT_INTERVAL_MS = 100.0
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
    last_failover_timestamp: Optional[float] = None
    heartbeat_misses: int = 0
    commands_sent: int = 0
    active_worker: int = 0
    timestamp: float = field(default_factory=time.time)


class AudioRing:
    """
    Lock-free SPSC ring buffer for audio samples
    Single writer (worker), single reader (audio callback)
    Based on RT-04 validated pattern
    """
    
    def __init__(self, num_buffers=8):
        self.num_buffers = num_buffers
        self.buffer_size = BUFFER_SIZE
        
        # Shared memory for audio samples
        self.audio_data = mp.Array('f', num_buffers * BUFFER_SIZE, lock=False)
        
        # Sequence number for latest buffer (writer updates)
        self.write_seq = mp.Value('L', 0, lock=False)
        
        # Last read sequence (reader tracks)
        self.read_seq = 0
        
        # Create NumPy view
        self.audio_view = np.frombuffer(self.audio_data, dtype=np.float32).reshape(
            (num_buffers, BUFFER_SIZE)
        )
    
    def write(self, buffer: np.ndarray, seq: int):
        """
        Write buffer to ring (worker side)
        Uses sequence number for slot selection
        """
        slot = seq % self.num_buffers
        self.audio_view[slot, :] = buffer
        self.write_seq.value = seq
    
    def get_latest(self) -> Tuple[np.ndarray, int]:
        """
        Get latest buffer (callback side)
        Returns (buffer, seq_num)
        """
        seq = self.write_seq.value
        if seq == 0:
            return None, 0
        
        slot = seq % self.num_buffers
        return self.audio_view[slot], seq


class CommandRing:
    """
    SPSC ring buffer for commands with coalescing support
    Now uses 64-byte Protocol v2 commands
    """
    
    def __init__(self, num_slots=64):
        self.num_slots = num_slots
        self.slot_size = 64  # Protocol v2 size
        
        # Cache-line aligned indices
        self.write_idx = mp.Value('L', 0, lock=False)
        self._pad1 = mp.Array('c', 60)
        self.read_idx = mp.Value('L', 0, lock=False)
        self._pad2 = mp.Array('c', 60)
        
        # Command data buffer
        self.data = mp.Array('B', num_slots * self.slot_size, lock=False)
        self.data_view = np.frombuffer(self.data, dtype=np.uint8).reshape(
            (num_slots, self.slot_size)
        )
    
    def write(self, cmd_bytes: bytes) -> bool:
        """Write command to ring (supervisor side)"""
        if len(cmd_bytes) != self.slot_size:
            return False
            
        write_pos = self.write_idx.value
        read_pos = self.read_idx.value
        
        next_write = (write_pos + 1) % self.num_slots
        if next_write == read_pos:
            return False  # Ring full
        
        slot = write_pos % self.num_slots
        self.data_view[slot, :] = np.frombuffer(cmd_bytes, dtype=np.uint8)
        
        self.write_idx.value = next_write
        return True
    
    def read(self) -> Optional[bytes]:
        """Read command from ring (worker side)"""
        write_pos = self.write_idx.value
        read_pos = self.read_idx.value
        
        if read_pos == write_pos:
            return None  # No data
        
        slot = read_pos % self.num_slots
        cmd_bytes = bytes(self.data_view[slot, :])
        
        self.read_idx.value = (read_pos + 1) % self.num_slots
        return cmd_bytes
    
    def has_data(self) -> bool:
        """Check if commands available"""
        return self.read_idx.value != self.write_idx.value


class Worker:
    """Wrapper for worker process with socket pair"""
    
    def __init__(self, worker_id: int, process: mp.Process, socket: socket.socket):
        self.worker_id = worker_id
        self.process = process
        self.socket = socket
        self.last_heartbeat = 0
        
    def send_wakeup(self):
        """Send wakeup byte to worker"""
        try:
            self.socket.send(b'!')
        except (BrokenPipeError, ConnectionResetError):
            pass
    
    def is_alive(self) -> bool:
        """Check if worker process is alive"""
        return self.process.is_alive()


def audio_worker_process(worker_id: int, cmd_ring: CommandRing, audio_ring: AudioRing, 
                         heartbeat_array, initial_state: dict, 
                         parent_socket: socket.socket, child_socket: socket.socket):
    """
    DSP worker process with ModuleHost integration
    Replaces inline sine generation with modular synthesis chain
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
    # Convert legacy parameters to module parameters
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
    print(f"{role} worker started with ModuleHost (PID: {os.getpid()})")
    
    # Set socket to non-blocking
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
                        # Process through ModuleHost
                        host.queue_command(cmd_bytes)
            except (BlockingIOError, socket.error):
                pass  # No commands available
            
            # Generate audio buffer through module chain
            audio_buffer = host.process_chain()
            
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
    print(f"Worker {worker_id} exited cleanly")


class AudioSupervisor:
    """
    Supervisor with ModuleHost integration
    Manages dual workers for fault-tolerant audio synthesis
    """
    
    def __init__(self):
        # Shared memory structures
        self.primary_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        self.primary_audio_ring = AudioRing()
        
        self.standby_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        self.standby_audio_ring = AudioRing()
        
        # Heartbeat monitoring
        self.heartbeat_array = mp.Array('L', 2, lock=False)
        
        # Worker processes
        self.primary_worker: Optional[Worker] = None
        self.standby_worker: Optional[Worker] = None
        
        # Audio engine
        self.engine = None
        self.stream = None
        
        # Metrics
        self.metrics = AudioMetrics()
        
        # Control state
        self.running = False
        self.active_ring = self.primary_audio_ring
        self.last_seq = 0
        
        # Initial DSP state (shared between workers for lockstep)
        self.initial_state = {
            'phase': 0.0,
            'frequency': 440.0,
            'amplitude': 0.5
        }
        
        # Monitoring
        self.monitor_thread = None
        self.monitor_stop = threading.Event()
        
        # OSC server
        self.osc_server = None
        self.osc_thread = None
        self.osc_loop = None
        self.osc_transport = None
        self.osc_future = None
    
    def create_worker(self, worker_id: int) -> Worker:
        """Create a worker process with ModuleHost"""
        # Create socket pair for wakeup signaling
        parent_sock, child_sock = socket.socketpair()
        
        # Select rings based on worker ID
        if worker_id == 0:
            cmd_ring = self.primary_cmd_ring
            audio_ring = self.primary_audio_ring
        else:
            cmd_ring = self.standby_cmd_ring
            audio_ring = self.standby_audio_ring
        
        # Create process
        process = mp.Process(
            target=audio_worker_process,
            args=(worker_id, cmd_ring, audio_ring, self.heartbeat_array,
                  self.initial_state.copy(), parent_sock, child_sock),
            name=f"AudioWorker-{worker_id}"
        )
        
        # Start process
        process.start()
        
        # Close child socket in parent
        child_sock.close()
        
        return Worker(worker_id, process, parent_sock)
    
    def audio_callback(self, outdata, frames, time_info, status):
        """
        Real-time audio callback - reads from active ring
        Zero modifications needed - just reads latest buffer
        """
        if status:
            self.metrics.underruns += 1
        
        # Get latest buffer from active ring
        buffer, seq = self.active_ring.get_latest()
        
        if buffer is not None and seq > self.last_seq:
            # Copy to output (maintains existing pattern)
            np.copyto(outdata[:, 0], buffer, casting='no')
            self.last_seq = seq
        else:
            # No new data - output silence
            outdata.fill(0)
        
        self.metrics.buffers_processed += 1
    
    def perform_failover(self):
        """Switch active audio source to standby worker"""
        start_time = time.perf_counter()
        
        # Simple atomic switch
        if self.active_ring == self.primary_audio_ring:
            self.active_ring = self.standby_audio_ring
            self.metrics.active_worker = 1
            print("Failover: Switched to standby worker")
        else:
            self.active_ring = self.primary_audio_ring
            self.metrics.active_worker = 0
            print("Failover: Switched to primary worker")
        
        # Track metrics
        failover_time = (time.perf_counter() - start_time) * 1000
        self.metrics.failover_count += 1
        self.metrics.failover_time_ms = failover_time
        self.metrics.last_failover_timestamp = time.time()
        
        print(f"Failover completed in {failover_time:.2f}ms")
    
    def monitor_workers(self):
        """Monitor worker health and perform failover if needed"""
        last_heartbeats = [0, 0]
        
        while not self.monitor_stop.is_set():
            time.sleep(HEARTBEAT_INTERVAL_MS / 1000.0)
            
            # Check heartbeats
            current_heartbeats = [
                self.heartbeat_array[0],
                self.heartbeat_array[1]
            ]
            
            # Check primary worker
            if self.primary_worker and current_heartbeats[0] == last_heartbeats[0]:
                self.metrics.heartbeat_misses += 1
                if self.metrics.active_worker == 0:
                    print(f"Primary worker heartbeat missed (was {last_heartbeats[0]})")
                    if self.standby_worker and self.standby_worker.is_alive():
                        self.perform_failover()
            
            # Check standby worker
            if self.standby_worker and current_heartbeats[1] == last_heartbeats[1]:
                self.metrics.heartbeat_misses += 1
                if self.metrics.active_worker == 1:
                    print(f"Standby worker heartbeat missed (was {last_heartbeats[1]})")
                    if self.primary_worker and self.primary_worker.is_alive():
                        self.perform_failover()
            
            last_heartbeats = current_heartbeats.copy()
    
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
        Maps OSC addresses to Protocol v2 commands
        """
        parts = address.split('/')
        
        # Module parameter control: /mod/<module>/<param> <value>
        if len(parts) >= 4 and parts[1] == 'mod':
            module_id = parts[2]
            param = parts[3]
            
            if len(args) > 0:
                value = float(args[0])
                
                # Create Protocol v2 command
                cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, param, value)
                self.broadcast_command_raw(cmd)
                
                # Update initial state for new workers
                if module_id == 'sine' and param == 'freq':
                    self.initial_state['frequency'] = value
                elif module_id == 'sine' and param == 'gain':
                    self.initial_state['amplitude'] = value
        
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
                
                # Create gate command
                cmd = pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, module_id, 'gate', 1 if gate_on else 0)
                self.broadcast_command_raw(cmd)
        
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
    
    def start_osc_server(self):
        """Start OSC server for control messages"""
        try:
            # Get host/port from environment or use defaults
            host = os.environ.get('CHRONUS_OSC_HOST', '127.0.0.1')
            port = int(os.environ.get('CHRONUS_OSC_PORT', '5005'))
            
            disp = dispatcher.Dispatcher()
            # Map all OSC addresses to our handler
            disp.map("/*", self.handle_osc_message)
            
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
        
        print("Starting AudioSupervisor v2 with ModuleHost...")
        
        # Create workers
        self.primary_worker = self.create_worker(0)
        self.standby_worker = self.create_worker(1)
        
        # Wait for workers to warm up
        print(f"Warming up workers ({WORKER_WARMUP_CYCLES} cycles)...")
        time.sleep(BUFFER_PERIOD * WORKER_WARMUP_CYCLES)
        
        # Start monitoring thread
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
        print("AudioSupervisor v2 running - ModuleHost synthesis active")
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
        # Send shutdown command using Protocol v2
        shutdown_cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'system', 'shutdown', 1.0)
        
        for worker in [self.primary_worker, self.standby_worker]:
            if worker:
                # Try graceful shutdown first
                if worker.worker_id == 0:
                    self.primary_cmd_ring.write(shutdown_cmd)
                else:
                    self.standby_cmd_ring.write(shutdown_cmd)
                worker.send_wakeup()
                
                # Wait briefly for graceful exit
                worker.process.join(timeout=0.5)
                
                # Force terminate if needed
                if worker.process.is_alive():
                    worker.process.terminate()
                    worker.process.join(timeout=0.5)
                    if worker.process.is_alive():
                        worker.process.kill()
                        worker.process.join()
                
                # Close socket
                worker.socket.close()
        
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
                'heartbeat_misses': self.metrics.heartbeat_misses,
                'commands_sent': self.metrics.commands_sent,
                'active_worker': self.metrics.active_worker,
            },
            'workers': {
                'primary': {
                    'alive': self.primary_worker.is_alive() if self.primary_worker else False,
                    'heartbeat': self.heartbeat_array[0] if self.primary_worker else 0,
                },
                'standby': {
                    'alive': self.standby_worker.is_alive() if self.standby_worker else False,
                    'heartbeat': self.heartbeat_array[1] if self.standby_worker else 0,
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
    
    print("\nModuleHost Synthesis Active!")
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
    exit(main())