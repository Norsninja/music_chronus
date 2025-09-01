#!/usr/bin/env python3
"""
AudioSupervisor v3 Fixed - Proper double buffering instead of ring buffer
Based on findings that AudioRing's view mechanism causes corruption
"""

import os
import sys
import time
import signal
import struct
import multiprocessing as mp
from multiprocessing import connection
import numpy as np
import sounddevice as sd
from collections import deque
from pythonosc import udp_client
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
import asyncio
import threading

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.music_chronus.supervisor import CommandRing
from src.music_chronus.module_host import ModuleHost
from src.music_chronus.modules.simple_sine import SimpleSine
from src.music_chronus.modules.adsr import ADSR
from src.music_chronus.modules.biquad_filter import BiquadFilter

# Constants
SAMPLE_RATE = 44100
BUFFER_SIZE = 256
CHANNELS = 1
COMMAND_RING_SLOTS = 64
OSC_PORT = 5005

# Isolation modes via environment variables
PRIMARY_ONLY = os.environ.get('PRIMARY_ONLY', '0') == '1'
NO_MODULES = os.environ.get('NO_MODULES', '0') == '1'
NO_MONITOR = os.environ.get('NO_MONITOR', '0') == '1'
DEBUG_LEVEL = int(os.environ.get('DEBUG_LEVEL', '1'))

# Worker timing
POLL_INTERVAL_ACTIVE = 0.002
POLL_INTERVAL_IDLE = 0.010
HEARTBEAT_TIMEOUT = 0.050

# Module parameters
DEFAULT_FREQ = 440.0
DEFAULT_GAIN = 0.5
DEFAULT_CUTOFF = 10000.0
DEFAULT_Q = 0.7


class DoubleBuffer:
    """
    Simple double buffer implementation
    No views, proper copying, buffer swapping at boundaries
    """
    def __init__(self, buffer_size=BUFFER_SIZE):
        self.buffer_size = buffer_size
        # Two buffers in shared memory
        self.buffer_a = mp.Array('f', buffer_size, lock=True)
        self.buffer_b = mp.Array('f', buffer_size, lock=True)
        # Which buffer is active for reading (0=A, 1=B)
        self.active_buffer = mp.Value('i', 0, lock=True)
        # Sequence number for synchronization
        self.sequence = mp.Value('Q', 0, lock=True)
        
    def write(self, data):
        """Writer puts data in inactive buffer and swaps"""
        with self.active_buffer.get_lock():
            # Get inactive buffer
            if self.active_buffer.value == 0:
                # A is active for reading, write to B
                with self.buffer_b.get_lock():
                    self.buffer_b[:] = data
            else:
                # B is active for reading, write to A
                with self.buffer_a.get_lock():
                    self.buffer_a[:] = data
            
            # Swap buffers atomically
            self.active_buffer.value = 1 - self.active_buffer.value
            self.sequence.value += 1
    
    def read(self):
        """Reader gets copy of active buffer"""
        with self.active_buffer.get_lock():
            if self.active_buffer.value == 0:
                # A is active
                with self.buffer_a.get_lock():
                    # Return a copy, not a view!
                    return np.array(self.buffer_a[:], dtype=np.float32)
            else:
                # B is active  
                with self.buffer_b.get_lock():
                    return np.array(self.buffer_b[:], dtype=np.float32)


def worker_process(worker_id: int, 
                  double_buffer: DoubleBuffer,
                  command_ring: CommandRing,
                  heartbeat_array,
                  event: mp.Event,
                  shutdown_flag: mp.Event):
    """
    Worker process with proper double buffering
    """
    # Install signal handlers
    def handle_sigterm(signum, frame):
        timestamp = time.monotonic()
        print(f"[{timestamp:.3f}] Worker {worker_id} (PID: {os.getpid()}) received SIGTERM")
        shutdown_flag.set()
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    print(f"Worker {worker_id} (PID: {os.getpid()}) started at {time.monotonic():.3f}")
    
    # Initialize module host and chain
    if not NO_MODULES:
        host = ModuleHost(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
        
        # Create module chain
        sine = SimpleSine(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
        adsr = ADSR(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
        filt = BiquadFilter(sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE)
        
        # Register modules
        host.add_module('sine', sine)
        host.add_module('adsr', adsr)
        host.add_module('filter', filt)
        
        # Set initial parameters
        host.queue_command(struct.pack('<2sH4s8xf32x', b'OP', 1, b'sine', DEFAULT_FREQ))
        host.queue_command(struct.pack('<2sH4s8xf32x', b'OP', 1, b'adsr', DEFAULT_GAIN))
        host.queue_command(struct.pack('<2sH4s8xf32x', b'OP', 1, b'filt', DEFAULT_CUTOFF))
        host.queue_command(struct.pack('<2sH4s4s4xf32x', b'OP', 1, b'filt', b'q', DEFAULT_Q))
        
        print(f"Worker {worker_id}: Module chain initialized")
    else:
        host = None
        print(f"Worker {worker_id}: NO_MODULES mode - generating pure sine")
    
    # Main processing loop
    buffer_seq = 0
    heartbeat_counter = 0
    phase = 0.0  # Track phase continuously for pure sine
    last_log_time = time.monotonic()
    buffer_rms_sum = 0.0
    buffer_count = 0
    
    while not shutdown_flag.is_set():
        try:
            # Wait for wakeup or timeout
            if event.wait(timeout=0.005):  # 5ms timeout for ~200Hz update rate
                event.clear()
            
            # Drain command ring
            while command_ring.has_data():
                cmd_bytes = command_ring.read()
                if host and cmd_bytes and len(cmd_bytes) >= 64:
                    try:
                        # Try to decode for debug
                        op_code = cmd_bytes[:2]
                        if op_code == b'OP':
                            _, _, module_id_raw, param_raw, value = struct.unpack('<2sH4s8xf32x', cmd_bytes)
                            module_id = module_id_raw.rstrip(b'\x00').decode('ascii', errors='ignore')
                            param = param_raw.rstrip(b'\x00').decode('ascii', errors='ignore')
                            host.queue_command(cmd_bytes)
                            if DEBUG_LEVEL >= 2:
                                print(f"[DEBUG] Worker {worker_id} queued: {module_id}.{param}={value}")
                    except:
                        # If unpacking fails, just queue it
                        host.queue_command(cmd_bytes)
            
            if shutdown_flag.is_set():
                break
            
            # Generate audio
            if host:
                # Process queued commands at buffer boundary
                host.process_commands()
                # Generate audio buffer through module chain
                audio_buffer = host.process_chain()
            else:
                # NO_MODULES mode - pure sine with continuous phase
                phase_step = 2 * np.pi * DEFAULT_FREQ / SAMPLE_RATE
                t = np.arange(BUFFER_SIZE) * phase_step + phase
                audio_buffer = (DEFAULT_GAIN * np.sin(t)).astype(np.float32)
                # Update phase for next buffer (wrap at 2*pi to avoid overflow)
                phase = (phase + BUFFER_SIZE * phase_step) % (2 * np.pi)
            
            # Calculate RMS for logging
            rms = np.sqrt(np.mean(audio_buffer**2))
            buffer_rms_sum += rms
            buffer_count += 1
            
            # Level 1 logging: every 50 buffers (~290ms)
            if DEBUG_LEVEL >= 1 and buffer_seq % 50 == 0:
                avg_rms = buffer_rms_sum / max(buffer_count, 1)
                print(f"[LOG1] Worker {worker_id}: seq={buffer_seq}, avg_RMS={avg_rms:.6f}, non-zero={avg_rms > 1e-6}")
                buffer_rms_sum = 0.0
                buffer_count = 0
            
            # Write to double buffer (handles synchronization internally)
            double_buffer.write(audio_buffer)
            buffer_seq += 1
            
            # Update heartbeat
            heartbeat_counter += 1
            heartbeat_array[worker_id] = heartbeat_counter
            
        except Exception as e:
            print(f"Worker {worker_id} error: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"Worker {worker_id} (PID: {os.getpid()}) exiting at {time.monotonic():.3f}")


class AudioSupervisor:
    """
    Supervisor with fixed double buffering
    """
    
    def __init__(self):
        print(f"\n=== AudioSupervisor v3 Fixed ===")
        print(f"PRIMARY_ONLY: {PRIMARY_ONLY}")
        print(f"NO_MODULES: {NO_MODULES}")
        print(f"NO_MONITOR: {NO_MONITOR}")
        print(f"DEBUG_LEVEL: {DEBUG_LEVEL}")
        print(f"Using: Double buffering (not ring buffer)")
        print(f"================================\n")
        
        # Double buffers (not ring buffers!)
        self.primary_buffer = DoubleBuffer()
        self.standby_buffer = DoubleBuffer() if not PRIMARY_ONLY else None
        
        # Command rings
        self.primary_cmd_ring = CommandRing(COMMAND_RING_SLOTS)
        self.standby_cmd_ring = CommandRing(COMMAND_RING_SLOTS) if not PRIMARY_ONLY else None
        
        # Heartbeat monitoring
        self.heartbeat_array = mp.Array('i', [0, 0])
        
        # Worker events
        self.primary_event = mp.Event()
        self.standby_event = mp.Event() if not PRIMARY_ONLY else None
        
        # Shutdown events
        self.primary_shutdown = mp.Event()
        self.standby_shutdown = mp.Event() if not PRIMARY_ONLY else None
        
        # Active buffer tracking
        self.active_idx = 0
        self.active_buffer = self.primary_buffer
        
        # Workers
        self.primary_worker = None
        self.standby_worker = None
        
        # Audio stream
        self.stream = None
        
        # OSC server
        self.osc_server = None
        self.osc_thread = None
        
        # Monitor thread
        self.monitor_thread = None
        self.monitor_stop = threading.Event()
        
        # Metrics
        self.metrics = self.Metrics()
        
        # Debug tracking
        self.callback_counter = 0
        self.last_callback_log = time.monotonic()
        self.last_sequence = 0
    
    class Metrics:
        def __init__(self):
            self.buffers_processed = 0
            self.underruns = 0
            self.overruns = 0
            self.commands_sent = 0
            self.active_worker = 0
            self.failover_count = 0
            self.duplicate_buffers = 0
    
    def start_workers(self):
        """Start worker processes"""
        # Always start primary
        self.primary_worker = mp.Process(
            target=worker_process,
            args=(0, self.primary_buffer, self.primary_cmd_ring,
                  self.heartbeat_array, self.primary_event, self.primary_shutdown)
        )
        self.primary_worker.start()
        print(f"Primary worker started (PID: {self.primary_worker.pid})")
        
        # Start standby unless PRIMARY_ONLY
        if not PRIMARY_ONLY:
            self.standby_worker = mp.Process(
                target=worker_process,
                args=(1, self.standby_buffer, self.standby_cmd_ring,
                      self.heartbeat_array, self.standby_event, self.standby_shutdown)
            )
            self.standby_worker.start()
            print(f"Standby worker started (PID: {self.standby_worker.pid})")
        else:
            print("PRIMARY_ONLY mode - no standby worker")
    
    def audio_callback(self, outdata, frames, time_info, status):
        """Real-time audio callback with proper double buffering"""
        if status:
            self.metrics.underruns += 1
            if DEBUG_LEVEL >= 1:
                print(f"[UNDERRUN] Status: {status}")
        
        # Get buffer from active double buffer (returns a copy, not a view!)
        buffer = self.active_buffer.read()
        
        # Check for duplicate buffers
        current_seq = self.active_buffer.sequence.value
        if current_seq == self.last_sequence:
            self.metrics.duplicate_buffers += 1
        self.last_sequence = current_seq
        
        # Level 1 logging: every ~1 second
        self.callback_counter += 1
        current_time = time.monotonic()
        if DEBUG_LEVEL >= 1 and (current_time - self.last_callback_log) >= 1.0:
            if buffer is not None:
                rms = np.sqrt(np.mean(buffer**2))
                print(f"[LOG1] Callback: active_idx={self.active_idx}, " +
                      f"buffers={self.metrics.buffers_processed}, " +
                      f"underruns={self.metrics.underruns}, " +
                      f"duplicates={self.metrics.duplicate_buffers}, " +
                      f"RMS={rms:.6f}")
            else:
                print(f"[LOG1] Callback: active_idx={self.active_idx}, " +
                      f"buffers={self.metrics.buffers_processed}, " +
                      f"underruns={self.metrics.underruns}, " +
                      f"buffer=None")
            self.last_callback_log = current_time
        
        if buffer is not None and len(buffer) == frames:
            # Copy to output
            np.copyto(outdata[:, 0], buffer, casting='no')
        else:
            # No data or wrong size - output silence
            outdata.fill(0)
        
        self.metrics.buffers_processed += 1
    
    def handle_osc_command(self, address, *args):
        """Handle OSC commands"""
        if DEBUG_LEVEL >= 2:
            print(f"[OSC] Received: {address} {args}")
        
        # Parse command
        parts = address.strip('/').split('/')
        if len(parts) < 2:
            return
        
        target = parts[0]
        command = parts[1]
        
        if target == 'engine':
            if command == 'freq' and args:
                self.send_parameter_update('sine', 'freq', float(args[0]))
            elif command == 'gain' and args:
                self.send_parameter_update('adsr', 'gain', float(args[0]))
            elif command == 'gate' and args:
                self.send_gate_command(int(args[0]))
            elif command == 'filter' and len(args) >= 2:
                self.send_parameter_update('filter', args[0], float(args[1]))
    
    def send_parameter_update(self, module_id: str, param: str, value: float):
        """Send parameter update to workers"""
        cmd = struct.pack('<2sH4s8xf32x', 
                         b'OP', 1, 
                         module_id[:4].encode('ascii').ljust(4, b'\x00'),
                         value)
        
        if param != 'freq':  # Add param to command for non-freq
            cmd = struct.pack('<2sH4s4s4xf32x',
                            b'OP', 1,
                            module_id[:4].encode('ascii').ljust(4, b'\x00'),
                            param[:4].encode('ascii').ljust(4, b'\x00'),
                            value)
        
        # Send to active worker
        if self.active_idx == 0:
            self.primary_cmd_ring.write(cmd)
            self.primary_event.set()
        elif not PRIMARY_ONLY:
            self.standby_cmd_ring.write(cmd)
            self.standby_event.set()
        
        self.metrics.commands_sent += 1
        if DEBUG_LEVEL >= 2:
            print(f"[OSC] Sent: {module_id}.{param}={value}")
    
    def send_gate_command(self, gate: int):
        """Send gate command"""
        cmd = struct.pack('<2sH4s8xf32x',
                         b'GT', 1,
                         b'adsr',
                         float(gate))
        
        # Send to active worker
        if self.active_idx == 0:
            self.primary_cmd_ring.write(cmd)
            self.primary_event.set()
        elif not PRIMARY_ONLY:
            self.standby_cmd_ring.write(cmd)
            self.standby_event.set()
        
        self.metrics.commands_sent += 1
        if DEBUG_LEVEL >= 1:
            print(f"[OSC] Gate: {gate}")
    
    def start_osc_server(self):
        """Start OSC server"""
        dispatcher = Dispatcher()
        dispatcher.map("/engine/*", self.handle_osc_command)
        
        async def start_server():
            self.osc_server = AsyncIOOSCUDPServer(
                ("127.0.0.1", OSC_PORT), dispatcher, asyncio.get_event_loop()
            )
            transport, protocol = await self.osc_server.create_serve_endpoint()
            print(f"OSC server listening on port {OSC_PORT}")
            await asyncio.get_event_loop().create_future()
        
        def run_event_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(start_server())
        
        self.osc_thread = threading.Thread(target=run_event_loop, daemon=True)
        self.osc_thread.start()
    
    def start(self):
        """Start the audio supervisor"""
        print("Starting AudioSupervisor v3 Fixed...")
        
        # Start workers
        self.start_workers()
        time.sleep(0.1)  # Let workers initialize
        
        # Start OSC server
        self.start_osc_server()
        
        # Start audio stream
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BUFFER_SIZE,
            channels=CHANNELS,
            dtype='float32',
            callback=self.audio_callback
        )
        self.stream.start()
        
        print("Audio stream started")
        print("\nSend OSC commands to test:")
        print("  /engine/gate 1       - Turn on")
        print("  /engine/freq 440     - Set frequency")
        print("  /engine/gain 0.5     - Set volume")
        print("  /engine/gate 0       - Turn off")
    
    def stop(self):
        """Stop the supervisor"""
        print("\nStopping AudioSupervisor...")
        
        # Stop audio
        if self.stream:
            self.stream.stop()
            self.stream.close()
        
        # Stop workers
        if self.primary_worker:
            self.primary_shutdown.set()
            self.primary_worker.terminate()
            self.primary_worker.join(timeout=1.0)
        
        if self.standby_worker and not PRIMARY_ONLY:
            self.standby_shutdown.set()
            self.standby_worker.terminate()
            self.standby_worker.join(timeout=1.0)
        
        print("Supervisor stopped")
    
    def print_status(self):
        """Print current status"""
        print(f"\n=== Status ===")
        print(f"Active: Worker {self.active_idx}")
        print(f"Buffers: {self.metrics.buffers_processed}")
        print(f"Underruns: {self.metrics.underruns}")
        print(f"Duplicate buffers: {self.metrics.duplicate_buffers}")
        print(f"Commands sent: {self.metrics.commands_sent}")


def main():
    """Main entry point"""
    supervisor = AudioSupervisor()
    
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal")
        supervisor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        supervisor.start()
        
        # Simple command loop
        print("\nCommands: status, stop, quit")
        while True:
            try:
                cmd = input("> ").strip().lower()
                if cmd in ['quit', 'stop', 'exit']:
                    break
                elif cmd == 'status':
                    supervisor.print_status()
            except EOFError:
                break
    finally:
        supervisor.stop()


if __name__ == '__main__':
    main()