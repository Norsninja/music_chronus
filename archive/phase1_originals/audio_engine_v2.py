#!/usr/bin/env python3
"""
Phase 1A: Audio Engine Core - Audio-only 440Hz sine wave generator
Using sounddevice for continuous playback with clean backend interface
"""

import time
import numpy as np
import sounddevice as sd
import os
import array
import psutil
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from enum import Enum

# Configuration
SAMPLE_RATE = 44100
BUFFER_SIZE = int(os.environ.get('CHRONUS_BUFFER_SIZE', '256'))
CHANNELS = 1
FREQUENCY = 440.0  # Fixed A4 note

# Pre-compute constants for callback efficiency
TWO_PI = 2.0 * np.pi
TWO_PI_OVER_SR = TWO_PI / SAMPLE_RATE
PHASE_INCREMENT_PER_SAMPLE = TWO_PI_OVER_SR * FREQUENCY
PHASE_WRAP_THRESHOLD = 1000 * TWO_PI  # Wrap every ~1000 cycles


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
    
    def __str__(self):
        if self.state == EngineState.RUNNING:
            return (
                f"State: {self.state.value}\n"
                f"Uptime: {self.uptime_seconds:.1f}s\n"
                f"Buffers: {self.total_buffers} "
                f"({'no underruns' if self.underrun_count == 0 else f'{self.underrun_count} underruns'})\n"
                f"Callback: min={self.callback_min_us:.2f}ms "
                f"mean={self.callback_mean_us:.2f}ms "
                f"max={self.callback_max_us:.2f}ms\n"
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
    Phase 1A: Simple callback-based playback
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
        
        # Set PulseAudio environment
        os.environ['PULSE_SERVER'] = 'tcp:172.21.240.1:4713'
        
        # Verify device on init
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


class AudioEngine:
    """
    Minimal audio engine generating a fixed 440Hz sine wave
    Phase 1A: Audio-only, no control path
    """
    
    def __init__(self, backend=None):
        # Engine state
        self.state = EngineState.STOPPED
        self.start_time: Optional[float] = None
        
        # Audio generation state
        self.phase = 0.0
        
        # Pre-allocate buffers
        self.phase_array = np.arange(BUFFER_SIZE, dtype=np.float32) * PHASE_INCREMENT_PER_SAMPLE
        
        # Backend (default to sounddevice)
        if backend is None:
            backend = SoundDeviceBackend(self._generate_audio)
        self.backend = backend
        
        # CPU monitoring
        self.process = psutil.Process()
        self.cpu_thread = None
        self.cpu_percent = 0.0
        self._stop_cpu_monitor = threading.Event()
        
        print(f"AudioEngine initialized: {SAMPLE_RATE}Hz, {BUFFER_SIZE} samples/buffer")
    
    def _generate_audio(self, outdata, frames):
        """
        Generate audio samples - called from audio callback
        NO allocations, NO syscalls, NO locks!
        """
        # Generate sine wave in-place
        phase_values = self.phase_array + self.phase
        np.sin(phase_values, out=outdata[:, 0])
        
        # Update phase
        self.phase += PHASE_INCREMENT_PER_SAMPLE * frames
        
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
        """Start the audio engine"""
        if self.state != EngineState.STOPPED:
            print(f"Cannot start: engine is {self.state.value}")
            return False
        
        self.state = EngineState.STARTING
        
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
        
        print(f"Audio engine started: {FREQUENCY}Hz sine wave")
        return True
    
    def stop(self) -> bool:
        """Stop the audio engine"""
        if self.state != EngineState.RUNNING:
            print(f"Cannot stop: engine is {self.state.value}")
            return False
        
        self.state = EngineState.STOPPING
        
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
        
        return EngineMetrics(
            state=self.state,
            uptime_seconds=uptime,
            total_buffers=backend_metrics['total_buffers'],
            underrun_count=backend_metrics['underrun_count'],
            callback_min_us=backend_metrics['callback_min_us'] / 1000,  # Convert to ms
            callback_mean_us=backend_metrics['callback_mean_us'] / 1000,
            callback_max_us=backend_metrics['callback_max_us'] / 1000,
            cpu_percent=self.cpu_percent
        )


def main():
    """Simple CLI for audio engine"""
    engine = AudioEngine()
    
    print("\n=== Audio Engine CLI ===")
    print("Commands: start, stop, status, quit")
    
    while True:
        try:
            cmd = input("\n> ").strip().lower()
            
            if cmd == "start":
                engine.start()
            elif cmd == "stop":
                engine.stop()
            elif cmd == "status":
                print(engine.get_status())
            elif cmd in ["quit", "exit"]:
                if engine.state == EngineState.RUNNING:
                    engine.stop()
                break
            else:
                print(f"Unknown command: {cmd}")
                
        except (KeyboardInterrupt, EOFError):
            print("\nShutting down...")
            if engine.state == EngineState.RUNNING:
                engine.stop()
            break


if __name__ == "__main__":
    main()