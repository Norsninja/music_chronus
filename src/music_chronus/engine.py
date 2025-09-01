#!/usr/bin/env python3
"""
Phase 1B: Audio Engine with OSC Control Integration
Adds real-time frequency control via OSC messages while maintaining zero underruns
"""

import time
import numpy as np
import sounddevice as sd
import os
import array
import psutil
import threading
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from enum import Enum

# OSC imports
from pythonosc import dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

# Configuration
SAMPLE_RATE = 44100
BUFFER_SIZE = int(os.environ.get('CHRONUS_BUFFER_SIZE', '256'))
CHANNELS = 1
DEFAULT_FREQUENCY = 440.0  # A4 note

# OSC Configuration (can be overridden by environment)
OSC_HOST = os.environ.get('CHRONUS_OSC_HOST', '127.0.0.1')
OSC_PORT = int(os.environ.get('CHRONUS_OSC_PORT', '5005'))

# Frequency bounds
MIN_FREQ = 20.0
MAX_FREQ = 20000.0

# Pre-compute constants for callback efficiency
TWO_PI = 2.0 * np.pi
TWO_PI_OVER_SR = TWO_PI / SAMPLE_RATE
PHASE_WRAP_THRESHOLD = 1000 * TWO_PI  # Wrap every ~1000 cycles


class SharedParams:
    """
    Python-native shared parameters for lock-free exchange
    GIL provides atomicity for Python primitives
    """
    def __init__(self):
        # Control parameters
        self.frequency_hz = DEFAULT_FREQUENCY  # Python float
        self.seq = 0                           # Python int
        
        # Metrics
        self.param_updates_received = 0
        self.param_updates_applied = 0
        self.last_update_timestamp = 0.0
        
        # Latency sampling (every Nth update)
        self.latency_sample_interval = 10
        self.latency_samples = []  # In samples, not ms
        self.max_latency_samples = 100  # Keep last 100 measurements


class EngineState(Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


@dataclass
class EngineMetrics:
    """Metrics collected from audio engine"""
    state: EngineState
    uptime_seconds: float
    total_buffers: int
    underrun_count: int
    callback_min_us: float
    callback_mean_us: float
    callback_max_us: float
    cpu_percent: float
    # Phase 1B additions
    current_frequency: float
    param_updates_received: int
    param_updates_applied: int
    control_latency_p99_ms: float
    
    def __str__(self):
        if self.state == EngineState.RUNNING:
            return (
                f"State: {self.state.value}\n"
                f"Uptime: {self.uptime_seconds:.1f}s\n"
                f"Frequency: {self.current_frequency:.1f} Hz\n"
                f"Buffers: {self.total_buffers} "
                f"({'no underruns' if self.underrun_count == 0 else f'{self.underrun_count} underruns'})\n"
                f"Callback: min={self.callback_min_us:.2f}ms "
                f"mean={self.callback_mean_us:.2f}ms "
                f"max={self.callback_max_us:.2f}ms\n"
                f"Updates: {self.param_updates_received} received, "
                f"{self.param_updates_applied} applied\n"
                f"Control latency p99: {self.control_latency_p99_ms:.2f}ms\n"
                f"CPU: {self.cpu_percent:.1f}%"
            )
        else:
            return f"State: {self.state.value}"


class AudioBackend(ABC):
    """
    Abstract interface for audio backends
    Allows swapping between sounddevice (now) and rtmixer (later)
    """
    
    @abstractmethod
    def start(self) -> bool:
        """Start audio stream"""
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        """Stop audio stream"""
        pass
    
    @abstractmethod
    def get_metrics(self) -> dict:
        """Get backend-specific metrics"""
        pass


class SoundDeviceBackend(AudioBackend):
    """
    Sounddevice backend for continuous audio generation
    Phase 1B: Supports real-time parameter changes
    """
    
    def __init__(self, callback_func, sample_rate=SAMPLE_RATE, buffer_size=BUFFER_SIZE, channels=CHANNELS):
        self.callback_func = callback_func
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.channels = channels
        self.stream = None
        
        # Metrics (using array for lock-free access from callback)
        # [0] = underrun_count
        # [1] = total_buffers
        # [2] = last_callback_us
        # [3] = min_callback_us (initialized to large value)
        # [4] = max_callback_us
        # [5] = sum_callback_us (for mean calculation)
        self.metrics = array.array('d', [0.0, 0.0, 0.0, 1000000.0, 0.0, 0.0])
        
        # Set PulseAudio environment only if explicitly configured
        pulse_server = os.environ.get('CHRONUS_PULSE_SERVER')
        if pulse_server and 'PULSE_SERVER' not in os.environ:
            os.environ['PULSE_SERVER'] = pulse_server
        # Note: No default set - let system use its native audio configuration
        # For WSL2 users, set CHRONUS_PULSE_SERVER='tcp:172.21.240.1:4713'
        
        # Verify device on init (only if verbose mode)
        if os.environ.get('CHRONUS_VERBOSE') == '1':
            try:
                devices = sd.query_devices()
                default_out = sd.default.device[1]
                print(f"Audio device: {devices[default_out]['name']}")
            except Exception as e:
                print(f"Warning: Could not query audio devices: {e}")
    
    def _audio_callback(self, outdata, frames, time_info, status):
        """
        Sounddevice callback - runs in audio thread
        NO allocations, NO syscalls, NO locks!
        """
        callback_start = time.perf_counter()
        
        # Check for underruns
        if status.output_underflow:
            self.metrics[0] += 1  # underrun_count
        
        # Call the generator function
        self.callback_func(outdata, frames)
        
        # Update metrics (lock-free array access)
        callback_time_us = (time.perf_counter() - callback_start) * 1000000
        self.metrics[1] += 1  # total_buffers
        self.metrics[2] = callback_time_us  # last_callback_us
        self.metrics[3] = min(self.metrics[3], callback_time_us)  # min_callback_us
        self.metrics[4] = max(self.metrics[4], callback_time_us)  # max_callback_us
        self.metrics[5] += callback_time_us  # sum_callback_us
    
    def start(self) -> bool:
        """Start the audio stream"""
        try:
            # Reset metrics
            self.metrics[0] = 0  # underrun_count
            self.metrics[1] = 0  # total_buffers
            self.metrics[2] = 0  # last_callback_us
            self.metrics[3] = 1000000  # min_callback_us
            self.metrics[4] = 0  # max_callback_us
            self.metrics[5] = 0  # sum_callback_us
            
            # Create output stream
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                blocksize=self.buffer_size,
                channels=self.channels,
                dtype='float32',
                latency='low',
                callback=self._audio_callback
            )
            
            self.stream.start()
            return True
            
        except Exception as e:
            print(f"Failed to start audio stream: {e}")
            print("Hint: Check PULSE_SERVER environment variable and PulseAudio connection")
            return False
    
    def stop(self) -> bool:
        """Stop the audio stream"""
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            return True
        except Exception as e:
            print(f"Error stopping audio stream: {e}")
            return False
    
    def get_metrics(self) -> dict:
        """Get backend metrics"""
        total_buffers = int(self.metrics[1])
        mean_callback = 0.0
        if total_buffers > 0:
            mean_callback = self.metrics[5] / total_buffers
        
        return {
            'underrun_count': int(self.metrics[0]),
            'total_buffers': total_buffers,
            'callback_min_us': self.metrics[3],
            'callback_mean_us': mean_callback,
            'callback_max_us': self.metrics[4]
        }


class OSCController:
    """
    OSC server for real-time parameter control
    Runs in separate thread with AsyncIO
    """
    
    def __init__(self, shared_params: SharedParams):
        self.shared_params = shared_params
        self.server = None
        self.transport = None
        self.loop = None
        self.thread = None
        self._stop_event = threading.Event()
        
    def setup_dispatcher(self):
        """Create OSC message dispatcher"""
        disp = dispatcher.Dispatcher()
        
        # Frequency control endpoint
        disp.map("/engine/freq", self.handle_frequency)
        
        # Future: /engine/status, /engine/sweep, etc.
        
        return disp
    
    def handle_frequency(self, address, *args):
        """
        Handle frequency change messages
        Sanitize and update shared parameters
        """
        if len(args) < 1:
            return
        
        try:
            freq = float(args[0])
            
            # Sanitize frequency
            freq = max(MIN_FREQ, min(MAX_FREQ, freq))
            
            # Update shared parameters (GIL ensures atomicity)
            # Write value THEN bump seq (order matters!)
            self.shared_params.frequency_hz = freq
            self.shared_params.seq += 1
            self.shared_params.param_updates_received += 1
            self.shared_params.last_update_timestamp = time.perf_counter()
            
        except (ValueError, TypeError) as e:
            print(f"Invalid frequency value: {args[0]}")
    
    async def _run_server(self):
        """AsyncIO server coroutine"""
        disp = self.setup_dispatcher()
        
        # Create AsyncIO OSC server
        self.server = AsyncIOOSCUDPServer(
            (OSC_HOST, OSC_PORT),
            disp,
            asyncio.get_event_loop()
        )
        
        self.transport, self.protocol = await self.server.create_serve_endpoint()
        
        print(f"OSC server listening on {OSC_HOST}:{OSC_PORT}")
        print(f"Send frequency changes to: /engine/freq")
        
        # Keep server running until stop event
        while not self._stop_event.is_set():
            await asyncio.sleep(0.1)
        
        self.transport.close()
    
    def _thread_target(self):
        """Thread target function"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._run_server())
        finally:
            self.loop.close()
    
    def start(self):
        """Start OSC server in separate thread"""
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._thread_target, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop OSC server"""
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)


class AudioEngine:
    """
    Audio engine with OSC control integration
    Phase 1B: Real-time frequency control via OSC
    """
    
    def __init__(self, backend=None):
        # Engine state
        self.state = EngineState.STOPPED
        self.start_time: Optional[float] = None
        
        # Shared parameters
        self.shared_params = SharedParams()
        
        # Audio generation state
        self.phase = 0.0
        self.phase_increment = TWO_PI_OVER_SR * DEFAULT_FREQUENCY
        self.last_seq = 0
        
        # Pre-allocate buffers
        self.phase_array = np.arange(BUFFER_SIZE, dtype=np.float32)
        
        # Backend (default to sounddevice)
        if backend is None:
            backend = SoundDeviceBackend(self._generate_audio)
        self.backend = backend
        
        # OSC controller
        self.osc_controller = OSCController(self.shared_params)
        
        # CPU monitoring
        self.process = psutil.Process()
        self.cpu_thread = None
        self.cpu_percent = 0.0
        self._stop_cpu_monitor = threading.Event()
        
        print(f"AudioEngine initialized: {SAMPLE_RATE}Hz, {BUFFER_SIZE} samples/buffer")
        print(f"Phase 1B: OSC control enabled on port {OSC_PORT}")
    
    def _generate_audio(self, outdata, frames):
        """
        Generate audio samples - called from audio callback
        NO allocations, NO syscalls, NO locks!
        Phase 1B: Check for parameter updates at buffer boundary
        """
        # Check for parameter updates (boundary application)
        current_seq = self.shared_params.seq
        
        if current_seq != self.last_seq:
            # Read frequency
            freq = self.shared_params.frequency_hz
            
            # Double-check seq unchanged (race detection)
            if self.shared_params.seq == current_seq:
                # Valid update - apply at this boundary
                self.phase_increment = TWO_PI_OVER_SR * freq
                self.last_seq = current_seq
                self.shared_params.param_updates_applied += 1
                
                # Sample latency occasionally (every Nth update)
                if self.shared_params.param_updates_applied % self.shared_params.latency_sample_interval == 0:
                    latency_samples = (time.perf_counter() - self.shared_params.last_update_timestamp) * SAMPLE_RATE
                    # Store in circular buffer fashion
                    if len(self.shared_params.latency_samples) >= self.shared_params.max_latency_samples:
                        self.shared_params.latency_samples.pop(0)
                    self.shared_params.latency_samples.append(latency_samples)
        
        # Generate sine wave with current frequency
        phase_values = self.phase_array * self.phase_increment + self.phase
        np.sin(phase_values, out=outdata[:, 0])
        
        # Update phase (maintain continuity)
        self.phase += self.phase_increment * frames
        
        # Wrap phase occasionally to prevent numerical issues
        if self.phase > PHASE_WRAP_THRESHOLD:
            self.phase = self.phase % TWO_PI
    
    def _cpu_monitor_thread(self):
        """Monitor CPU usage at 1Hz"""
        while not self._stop_cpu_monitor.wait(1.0):
            try:
                self.cpu_percent = self.process.cpu_percent(interval=None)
            except:
                self.cpu_percent = 0.0
    
    def start(self) -> bool:
        """Start the audio engine and OSC server"""
        if self.state != EngineState.STOPPED:
            print(f"Cannot start: engine is {self.state.value}")
            return False
        
        self.state = EngineState.STARTING
        
        # Start OSC server first
        self.osc_controller.start()
        
        # Start backend
        if not self.backend.start():
            self.state = EngineState.ERROR
            return False
        
        # Start CPU monitoring
        self._stop_cpu_monitor.clear()
        self.cpu_thread = threading.Thread(target=self._cpu_monitor_thread, daemon=True)
        self.cpu_thread.start()
        
        self.start_time = time.time()
        self.state = EngineState.RUNNING
        
        print(f"Audio engine started: {DEFAULT_FREQUENCY}Hz sine wave")
        print(f"OSC control active - send frequency to {OSC_HOST}:{OSC_PORT}/engine/freq")
        return True
    
    def stop(self) -> bool:
        """Stop the audio engine and OSC server"""
        if self.state != EngineState.RUNNING:
            print(f"Cannot stop: engine is {self.state.value}")
            return False
        
        self.state = EngineState.STOPPING
        
        # Stop OSC server
        self.osc_controller.stop()
        
        # Stop CPU monitoring
        self._stop_cpu_monitor.set()
        if self.cpu_thread:
            self.cpu_thread.join(timeout=2)
        
        # Stop backend
        if not self.backend.stop():
            self.state = EngineState.ERROR
            return False
        
        self.state = EngineState.STOPPED
        print("Audio engine stopped")
        return True
    
    def get_status(self) -> EngineMetrics:
        """Get current engine metrics"""
        uptime = 0.0
        if self.start_time and self.state == EngineState.RUNNING:
            uptime = time.time() - self.start_time
        
        # Get backend metrics
        backend_metrics = self.backend.get_metrics()
        
        # Calculate control latency p99
        control_latency_p99_ms = 0.0
        if self.shared_params.latency_samples:
            sorted_samples = sorted(self.shared_params.latency_samples)
            p99_index = int(len(sorted_samples) * 0.99)
            control_latency_p99_ms = (sorted_samples[p99_index] / SAMPLE_RATE) * 1000
        
        return EngineMetrics(
            state=self.state,
            uptime_seconds=uptime,
            total_buffers=backend_metrics['total_buffers'],
            underrun_count=backend_metrics['underrun_count'],
            callback_min_us=backend_metrics['callback_min_us'] / 1000,  # Convert to ms
            callback_mean_us=backend_metrics['callback_mean_us'] / 1000,
            callback_max_us=backend_metrics['callback_max_us'] / 1000,
            cpu_percent=self.cpu_percent,
            current_frequency=self.shared_params.frequency_hz,
            param_updates_received=self.shared_params.param_updates_received,
            param_updates_applied=self.shared_params.param_updates_applied,
            control_latency_p99_ms=control_latency_p99_ms
        )


def main():
    """Enhanced CLI for audio engine with OSC control"""
    engine = AudioEngine()
    
    print("\n=== Phase 1B: Audio Engine with OSC Control ===")
    print("Commands: start, stop, status, freq <hz>, quit")
    print("OSC: Send messages to localhost:5005/engine/freq")
    print("Example: oscsend localhost 5005 /engine/freq f 880.0")
    
    while True:
        try:
            cmd = input("\n> ").strip().lower().split()
            
            if not cmd:
                continue
            
            if cmd[0] == "start":
                engine.start()
            elif cmd[0] == "stop":
                engine.stop()
            elif cmd[0] == "status":
                print(engine.get_status())
            elif cmd[0] == "freq" and len(cmd) > 1:
                try:
                    freq = float(cmd[1])
                    # Use OSC controller directly for testing
                    engine.osc_controller.handle_frequency("/engine/freq", freq)
                    print(f"Set frequency to {freq} Hz")
                except ValueError:
                    print(f"Invalid frequency: {cmd[1]}")
            elif cmd[0] in ["quit", "exit"]:
                if engine.state == EngineState.RUNNING:
                    engine.stop()
                break
            else:
                print(f"Unknown command: {' '.join(cmd)}")
                
        except (KeyboardInterrupt, EOFError):
            print("\nShutting down...")
            if engine.state == EngineState.RUNNING:
                engine.stop()
            break


if __name__ == "__main__":
    main()