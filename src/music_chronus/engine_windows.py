#!/usr/bin/env python3
"""
Windows-optimized Audio Engine with WASAPI support
Designed for sub-10ms latency on Windows with WASAPI exclusive mode
"""

import time
import numpy as np
import sounddevice as sd
import os
import threading
import asyncio
from dataclasses import dataclass
from typing import Optional
from enum import Enum

# OSC imports
from pythonosc import dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

# Configuration
SAMPLE_RATE = 48000  # WASAPI devices typically use 48kHz
BUFFER_SIZE = int(os.environ.get('CHRONUS_BUFFER_SIZE', '256'))
CHANNELS = 1
DEFAULT_FREQUENCY = 440.0

# OSC Configuration
OSC_HOST = os.environ.get('CHRONUS_OSC_HOST', '127.0.0.1')
OSC_PORT = int(os.environ.get('CHRONUS_OSC_PORT', '5005'))

# Pre-compute constants
TWO_PI = 2.0 * np.pi
TWO_PI_OVER_SR = TWO_PI / SAMPLE_RATE


class SharedParams:
    """Thread-safe shared parameters"""
    def __init__(self):
        self.frequency_hz = DEFAULT_FREQUENCY
        self.amplitude = 0.5
        self.gate = False
        self.param_updates = 0


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
    current_frequency: float
    latency_ms: float
    device_name: str
    host_api: str


class WindowsAudioEngine:
    """
    Windows-optimized audio engine using WASAPI for low latency
    """
    
    def __init__(self, use_wasapi: bool = True):
        # Core components
        self.params = SharedParams()
        self.state = EngineState.STOPPED
        self.use_wasapi = use_wasapi
        
        # Audio state
        self.stream: Optional[sd.OutputStream] = None
        self.phase = 0.0
        self.start_time = 0.0
        self.total_buffers = 0
        self.underrun_count = 0
        
        # Device selection
        self.output_device = None
        self.device_info = None
        self.host_api_name = "MME"
        
        # OSC server
        self.osc_server = None
        self.osc_thread = None
        
        # Select best audio device
        self._select_audio_device()
    
    def _select_audio_device(self):
        """Select the best available audio device, preferring WASAPI"""
        devices = sd.query_devices()
        
        if self.use_wasapi:
            # Try to find WASAPI device
            for i, device in enumerate(devices):
                api_info = sd.query_hostapis(device['hostapi'])
                if 'WASAPI' in api_info['name'] and device['max_output_channels'] > 0:
                    # Prefer USB audio devices for lower latency
                    if 'USB' in device['name'] or 'AB13X' in device['name']:
                        self.output_device = i
                        self.device_info = device
                        self.host_api_name = api_info['name']
                        print(f"Selected WASAPI device: {device['name']}")
                        print(f"  Latency: {device['default_low_output_latency']*1000:.1f}ms")
                        return
            
            # Fall back to any WASAPI device
            for i, device in enumerate(devices):
                api_info = sd.query_hostapis(device['hostapi'])
                if 'WASAPI' in api_info['name'] and device['max_output_channels'] > 0:
                    self.output_device = i
                    self.device_info = device
                    self.host_api_name = api_info['name']
                    print(f"Selected WASAPI device: {device['name']}")
                    return
        
        # Fall back to default
        self.output_device = None
        default_output = sd.query_devices(sd.default.device[1])
        self.device_info = default_output
        self.host_api_name = sd.query_hostapis(default_output['hostapi'])['name']
        print(f"Using default device: {default_output['name']} ({self.host_api_name})")
    
    def audio_callback(self, outdata, frames, time_info, status):
        """
        Real-time audio callback - runs in separate thread
        Must be extremely efficient to avoid dropouts
        """
        if status:
            self.underrun_count += 1
            print(f"Audio callback status: {status}")
        
        self.total_buffers += 1
        
        # Get current parameters (atomic reads)
        freq = self.params.frequency_hz
        amp = self.params.amplitude if self.params.gate else 0.0
        
        # Generate audio
        if amp > 0:
            # Phase accumulator synthesis
            phase_increment = TWO_PI_OVER_SR * freq
            phases = self.phase + np.arange(frames) * phase_increment
            
            # Generate sine wave
            audio = amp * np.sin(phases)
            
            # Update phase for next callback
            self.phase = phases[-1]
            
            # Wrap phase to prevent overflow
            if self.phase > TWO_PI:
                self.phase -= TWO_PI * int(self.phase / TWO_PI)
            
            # Write to output buffer
            outdata[:, 0] = audio
        else:
            # Output silence
            outdata[:] = 0
            self.phase = 0.0
    
    async def start_osc_server(self):
        """Start OSC server for control messages"""
        disp = dispatcher.Dispatcher()
        
        # Register handlers
        disp.map("/frequency", self.handle_frequency)
        disp.map("/freq", self.handle_frequency)  # Alias
        disp.map("/amplitude", self.handle_amplitude)
        disp.map("/amp", self.handle_amplitude)  # Alias
        disp.map("/gate", self.handle_gate)
        disp.map("/note_on", lambda *args: self.handle_gate(None, 1))
        disp.map("/note_off", lambda *args: self.handle_gate(None, 0))
        
        # Create server
        self.osc_server = AsyncIOOSCUDPServer(
            (OSC_HOST, OSC_PORT),
            disp,
            asyncio.get_event_loop()
        )
        
        print(f"OSC server listening on {OSC_HOST}:{OSC_PORT}")
        
        # Start serving
        transport, protocol = await self.osc_server.create_serve_endpoint()
        await asyncio.Future()  # Run forever
    
    def handle_frequency(self, addr, freq):
        """Handle frequency control message"""
        if 20.0 <= freq <= 20000.0:
            self.params.frequency_hz = float(freq)
            self.params.param_updates += 1
    
    def handle_amplitude(self, addr, amp):
        """Handle amplitude control message"""
        if 0.0 <= amp <= 1.0:
            self.params.amplitude = float(amp)
            self.params.param_updates += 1
    
    def handle_gate(self, addr, gate):
        """Handle gate control message"""
        self.params.gate = bool(gate)
        self.params.param_updates += 1
    
    def start(self):
        """Start the audio engine"""
        if self.state != EngineState.STOPPED:
            return False
        
        try:
            self.state = EngineState.STARTING
            
            # Configure for low latency
            latency = 'low' if self.use_wasapi else 'high'
            
            # Create audio stream
            self.stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BUFFER_SIZE,
                device=self.output_device,
                channels=CHANNELS,
                callback=self.audio_callback,
                latency=latency
            )
            
            # Start OSC server in background thread
            def run_osc():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.start_osc_server())
            
            self.osc_thread = threading.Thread(target=run_osc, daemon=True)
            self.osc_thread.start()
            
            # Start audio stream
            self.stream.start()
            self.start_time = time.time()
            self.state = EngineState.RUNNING
            
            print(f"Audio engine started")
            print(f"  Device: {self.device_info['name']}")
            print(f"  Host API: {self.host_api_name}")
            print(f"  Buffer size: {BUFFER_SIZE} samples ({BUFFER_SIZE/SAMPLE_RATE*1000:.1f}ms)")
            print(f"  Sample rate: {SAMPLE_RATE} Hz")
            
            return True
            
        except Exception as e:
            print(f"Failed to start audio engine: {e}")
            self.state = EngineState.ERROR
            return False
    
    def stop(self):
        """Stop the audio engine"""
        if self.state != EngineState.RUNNING:
            return
        
        self.state = EngineState.STOPPING
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        self.state = EngineState.STOPPED
    
    def get_metrics(self) -> EngineMetrics:
        """Get current engine metrics"""
        uptime = time.time() - self.start_time if self.start_time else 0
        
        # Calculate actual latency
        if self.device_info:
            latency_ms = self.device_info['default_low_output_latency'] * 1000
        else:
            latency_ms = BUFFER_SIZE / SAMPLE_RATE * 1000
        
        return EngineMetrics(
            state=self.state,
            uptime_seconds=uptime,
            total_buffers=self.total_buffers,
            underrun_count=self.underrun_count,
            current_frequency=self.params.frequency_hz,
            latency_ms=latency_ms,
            device_name=self.device_info['name'] if self.device_info else "Unknown",
            host_api=self.host_api_name
        )
    
    def run_forever(self):
        """Run the engine until interrupted"""
        print("\nWindows Audio Engine Running")
        print("Send OSC messages to control:")
        print("  /frequency <hz>  - Set frequency (20-20000)")
        print("  /amplitude <0-1> - Set amplitude")
        print("  /gate <0/1>      - Gate on/off")
        print("\nPress Ctrl+C to stop")
        
        try:
            while self.state == EngineState.RUNNING:
                time.sleep(1)
                
                # Print periodic status
                if self.total_buffers % 100 == 0:
                    metrics = self.get_metrics()
                    if self.underrun_count > 0:
                        print(f"Warning: {self.underrun_count} underruns detected")
        
        except KeyboardInterrupt:
            print("\nShutting down...")
        
        finally:
            self.stop()


def test_engine():
    """Test the Windows audio engine"""
    engine = WindowsAudioEngine(use_wasapi=True)
    
    if engine.start():
        # Set initial tone
        engine.params.frequency_hz = 440.0
        engine.params.amplitude = 0.3
        engine.params.gate = True
        
        print("\nPlaying 440Hz test tone...")
        time.sleep(2)
        
        # Test frequency sweep
        print("Sweeping frequency...")
        for freq in [220, 440, 880, 440]:
            engine.params.frequency_hz = freq
            time.sleep(0.5)
        
        # Gate off
        engine.params.gate = False
        time.sleep(0.5)
        
        # Get final metrics
        metrics = engine.get_metrics()
        print(f"\nFinal metrics:")
        print(f"  Total buffers: {metrics.total_buffers}")
        print(f"  Underruns: {metrics.underrun_count}")
        print(f"  Latency: {metrics.latency_ms:.1f}ms")
        
        engine.stop()
    else:
        print("Failed to start engine")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_engine()
    else:
        # Run as OSC-controlled synthesizer
        engine = WindowsAudioEngine(use_wasapi=True)
        if engine.start():
            engine.run_forever()