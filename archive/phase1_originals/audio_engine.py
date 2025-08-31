#!/usr/bin/env python3
"""
Phase 1A: Audio Engine Core - Audio-only 440Hz sine wave generator
No control path, no OSC, just pure audio generation with metrics
"""

import time
import numpy as np
import rtmixer
import sounddevice as sd
import os
import array
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
PHASE_INCREMENT_PER_BUFFER = PHASE_INCREMENT_PER_SAMPLE * BUFFER_SIZE
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


class AudioEngine:
    """
    Minimal audio engine generating a fixed 440Hz sine wave
    Phase 1A: Audio-only, no control path
    """
    
    def __init__(self):
        # Engine state
        self.state = EngineState.STOPPED
        self.mixer: Optional[rtmixer.Mixer] = None
        self.start_time: Optional[float] = None
        
        # Audio generation state
        self.phase = 0.0
        
        # Pre-allocate output buffer
        self.output_buffer = np.zeros(BUFFER_SIZE, dtype=np.float32)
        
        # Pre-compute phase values for entire buffer (more efficient)
        self.phase_array = np.arange(BUFFER_SIZE, dtype=np.float32) * PHASE_INCREMENT_PER_SAMPLE
        
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
        
        print(f"AudioEngine initialized: {SAMPLE_RATE}Hz, {BUFFER_SIZE} samples/buffer")
    
    def _audio_generator(self):
        """
        Generator function for continuous audio output.
        This runs in the audio callback thread - NO allocations, NO syscalls!
        """
        # Local references for efficiency
        phase = self.phase
        phase_increment = PHASE_INCREMENT_PER_BUFFER
        phase_array = self.phase_array
        output_buffer = self.output_buffer
        metrics = self.metrics
        
        while True:
            callback_start = time.perf_counter()
            
            # Generate sine wave (in-place operation, no allocation)
            np.sin(phase_array + phase, out=output_buffer)
            
            # Update phase
            phase += phase_increment
            
            # Wrap phase occasionally to prevent numerical issues
            if phase > PHASE_WRAP_THRESHOLD:
                phase = phase % TWO_PI
            
            # Update metrics (lock-free array access)
            callback_time_us = (time.perf_counter() - callback_start) * 1000000
            metrics[1] += 1  # total_buffers
            metrics[2] = callback_time_us  # last_callback_us
            metrics[3] = min(metrics[3], callback_time_us)  # min_callback_us
            metrics[4] = max(metrics[4], callback_time_us)  # max_callback_us
            metrics[5] += callback_time_us  # sum_callback_us
            
            # Yield audio data to rtmixer
            yield output_buffer
        
        # Save phase for next start (if we ever stop/restart)
        self.phase = phase
    
    def start(self) -> bool:
        """Start the audio engine"""
        if self.state != EngineState.STOPPED:
            print(f"Cannot start: engine is {self.state.value}")
            return False
        
        try:
            self.state = EngineState.STARTING
            
            # Reset metrics
            self.metrics[0] = 0  # underrun_count
            self.metrics[1] = 0  # total_buffers
            self.metrics[2] = 0  # last_callback_us
            self.metrics[3] = 1000000  # min_callback_us (large initial value)
            self.metrics[4] = 0  # max_callback_us
            self.metrics[5] = 0  # sum_callback_us
            
            # Create mixer with low latency settings
            self.mixer = rtmixer.Mixer(
                samplerate=SAMPLE_RATE,
                blocksize=BUFFER_SIZE,
                channels=CHANNELS,
                latency='low'
            )
            
            # Start the mixer context
            self.mixer.__enter__()
            
            # Start playing from generator
            self.mixer.play_iterable(
                self._audio_generator(),
                channels=CHANNELS,
                start=0,
                allow_belated=False
            )
            
            self.start_time = time.time()
            self.state = EngineState.RUNNING
            
            print(f"Audio engine started: {FREQUENCY}Hz sine wave")
            return True
            
        except Exception as e:
            self.state = EngineState.ERROR
            print(f"Failed to start audio engine: {e}")
            print("Hint: Check PULSE_SERVER environment variable and PulseAudio connection")
            return False
    
    def stop(self) -> bool:
        """Stop the audio engine"""
        if self.state != EngineState.RUNNING:
            print(f"Cannot stop: engine is {self.state.value}")
            return False
        
        try:
            self.state = EngineState.STOPPING
            
            # Stop the mixer
            if self.mixer:
                self.mixer.__exit__(None, None, None)
                self.mixer = None
            
            self.state = EngineState.STOPPED
            print("Audio engine stopped")
            return True
            
        except Exception as e:
            self.state = EngineState.ERROR
            print(f"Error stopping audio engine: {e}")
            return False
    
    def get_status(self) -> EngineMetrics:
        """Get current engine metrics"""
        uptime = 0.0
        if self.start_time and self.state == EngineState.RUNNING:
            uptime = time.time() - self.start_time
        
        # Calculate mean callback time
        total_buffers = int(self.metrics[1])
        mean_callback = 0.0
        if total_buffers > 0:
            mean_callback = self.metrics[5] / total_buffers
        
        # Get CPU usage (simplified - in production would use psutil)
        cpu_percent = 0.0
        if self.state == EngineState.RUNNING:
            # Rough estimate based on callback time vs buffer duration
            buffer_duration_us = (BUFFER_SIZE / SAMPLE_RATE) * 1000000
            cpu_percent = (mean_callback / buffer_duration_us) * 100
        
        return EngineMetrics(
            state=self.state,
            uptime_seconds=uptime,
            total_buffers=total_buffers,
            underrun_count=int(self.metrics[0]),
            callback_min_us=self.metrics[3] / 1000,  # Convert to ms
            callback_mean_us=mean_callback / 1000,   # Convert to ms
            callback_max_us=self.metrics[4] / 1000,  # Convert to ms
            cpu_percent=cpu_percent
        )


def main():
    """Test the audio engine directly"""
    engine = AudioEngine()
    
    print("\n=== Audio Engine Test ===")
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
            elif cmd == "quit":
                if engine.state == EngineState.RUNNING:
                    engine.stop()
                break
            else:
                print(f"Unknown command: {cmd}")
                
        except KeyboardInterrupt:
            print("\nShutting down...")
            if engine.state == EngineState.RUNNING:
                engine.stop()
            break


if __name__ == "__main__":
    main()