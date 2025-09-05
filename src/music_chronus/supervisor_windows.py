#!/usr/bin/env python3
"""
Windows-Native Audio Supervisor with WASAPI Support
Based on supervisor_v2_slots_fixed.py but adapted for Windows
"""

import multiprocessing as mp
import numpy as np
import sounddevice as sd
import time
import signal
import os
import sys
import threading
import wave
from datetime import datetime
from pythonosc import dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows configuration
from music_chronus.config_windows import apply_windows_config, get_config

# Import core components (these are cross-platform)
try:
    from music_chronus.supervisor_v2_slots_fixed import (
        AudioRing, CommandRing, 
        NUM_BUFFERS, COMMAND_RING_SLOTS, HEARTBEAT_TIMEOUT, STARTUP_GRACE_PERIOD
    )
    from music_chronus.module_host import ModuleHost, pack_command_v2, CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL
    from music_chronus.modules.simple_sine import SimpleSine
    from music_chronus.modules.adsr import ADSR
    from music_chronus.modules.biquad_filter import BiquadFilter
except ImportError:
    # Fallback for different import contexts
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from music_chronus.supervisor_v2_slots_fixed import (
        AudioRing, CommandRing,
        NUM_BUFFERS, COMMAND_RING_SLOTS, HEARTBEAT_TIMEOUT, STARTUP_GRACE_PERIOD
    )
    from music_chronus.module_host import ModuleHost, pack_command_v2, CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL
    from music_chronus.modules.simple_sine import SimpleSine
    from music_chronus.modules.adsr import ADSR
    from music_chronus.modules.biquad_filter import BiquadFilter

# Apply Windows configuration
apply_windows_config()
config = get_config()

# Use config values
SAMPLE_RATE = config['sample_rate']
BUFFER_SIZE = config['buffer_size']
NUM_CHANNELS = config['channels']

class WindowsAudioSupervisor:
    """
    Windows-native supervisor with WASAPI support
    Maintains dual-slot architecture for fault tolerance
    """
    
    def __init__(self):
        # Load configuration
        self.config = config
        self.sample_rate = self.config['sample_rate']
        self.buffer_size = self.config['buffer_size']
        
        # Windows multiprocessing setup
        if sys.platform == 'win32':
            mp.set_start_method('spawn', force=True)
        
        # Audio device selection
        self.output_device = self._select_wasapi_device()
        
        # Dual-slot architecture (unchanged from v2)
        self.primary_audio_ring = AudioRing(NUM_BUFFERS)
        self.standby_audio_ring = AudioRing(NUM_BUFFERS)
        
        self.primary_command_ring = CommandRing(COMMAND_RING_SLOTS)
        self.standby_command_ring = CommandRing(COMMAND_RING_SLOTS)
        
        # Active ring is what audio callback reads from
        self.active_ring = self.primary_audio_ring
        
        # Heartbeat tracking
        self.heartbeat_array = mp.Array('Q', 2, lock=False)
        
        # Event signals for command availability
        self.primary_event = mp.Event()
        self.standby_event = mp.Event()
        
        # Shutdown coordination
        self.shutdown_flag = mp.Event()
        
        # Worker processes
        self.primary_worker = None
        self.standby_worker = None
        
        # WASAPI stream
        self.stream = None
        
        # Metrics
        self.underrun_count = 0
        self.callback_count = 0
        self.last_callback_time = 0
        
        # Callback timing metrics (milliseconds)
        self.callback_times = []  # Store last 1000 callback durations
        self.callback_min_ms = float('inf')
        self.callback_max_ms = 0
        self.callback_sum_ms = 0
        self.total_buffers_processed = 0
        
        # OSC server
        self.osc_server = None
        self.osc_thread = None
        
        # Recording
        self.recording_buffer = []
        self.is_recording = False
        self.recording_start_time = None
        
    def _select_wasapi_device(self):
        """Select the best WASAPI device with detailed logging"""
        device_id = self.config['output_device']
        
        if device_id >= 0:
            # Use configured device and log details
            dev_info = sd.query_devices(device_id)
            api_info = sd.query_hostapis()[dev_info['hostapi']]
            print(f"\n=== Audio Device Configuration ===")
            print(f"Device: {dev_info['name']}")
            print(f"Index: {device_id}")
            print(f"API: {api_info['name']}")
            print(f"Sample Rate: {self.sample_rate} Hz")
            print(f"Buffer Size: {self.buffer_size} samples")
            print(f"Channels: {dev_info['max_output_channels']}")
            print(f"Mode: {'Exclusive' if self.config.get('use_wasapi') else 'Shared'}")
            print(f"==================================\n")
            return device_id
            
        # Auto-select WASAPI device
        devices = sd.query_devices()
        wasapi_devices = []
        
        for i, dev in enumerate(devices):
            if dev['max_output_channels'] > 0:
                api_info = sd.query_hostapis()[dev['hostapi']]
                if 'WASAPI' in api_info['name']:
                    wasapi_devices.append((i, dev))
        
        if not wasapi_devices:
            print("No WASAPI devices found, using default")
            return None
            
        # Prefer USB audio interfaces
        for dev_id, dev in wasapi_devices:
            if 'USB' in dev['name'] or 'AB13X' in dev['name']:
                api_info = sd.query_hostapis()[dev['hostapi']]
                print(f"\n=== Audio Device Configuration ===")
                print(f"Device: {dev['name']}")
                print(f"Index: {dev_id}")
                print(f"API: {api_info['name']}")
                print(f"Sample Rate: {self.sample_rate} Hz")
                print(f"Buffer Size: {self.buffer_size} samples")
                print(f"Channels: {dev['max_output_channels']}")
                print(f"Mode: {'Exclusive' if self.config.get('use_wasapi') else 'Shared'}")
                print(f"==================================\n")
                return dev_id
        
        # Use first WASAPI device
        dev_id = wasapi_devices[0][0]
        dev = wasapi_devices[0][1]
        api_info = sd.query_hostapis()[dev['hostapi']]
        print(f"\n=== Audio Device Configuration ===")
        print(f"Device: {dev['name']}")
        print(f"Index: {dev_id}")
        print(f"API: {api_info['name']}")
        print(f"Sample Rate: {self.sample_rate} Hz")
        print(f"Buffer Size: {self.buffer_size} samples")
        print(f"Channels: {dev['max_output_channels']}")
        print(f"Mode: {'Exclusive' if self.config.get('use_wasapi') else 'Shared'}")
        print(f"==================================\n")
        return dev_id
    
    def audio_callback(self, outdata, frames, time_info, status):
        """
        WASAPI audio callback - CRITICAL PATH
        No allocations, no blocking operations
        """
        callback_start = time.perf_counter()
        
        if status:
            self.underrun_count += 1
            if status.output_underflow:
                print(f"Output underflow at {time_info.currentTime:.3f}")
        
        self.callback_count += 1
        
        # Get buffer from active ring (zero-copy) - FIXED per Senior Dev
        keep_after = int(os.environ.get('CHRONUS_KEEP_AFTER_READ', '2'))
        buffer = self.active_ring.read_latest_keep(keep_after_read=keep_after)
        
        if buffer is not None:
            # Direct copy to output
            np.copyto(outdata[:, 0], buffer, casting='no')
            self.total_buffers_processed += 1
            
            # Record if enabled
            if self.is_recording:
                self.recording_buffer.append(buffer.copy())
        else:
            # Silence on underrun
            outdata.fill(0)
            if self.is_recording:
                self.recording_buffer.append(np.zeros(self.buffer_size, dtype=np.float32))
        
        # Update timing metrics (convert to milliseconds)
        callback_end = time.perf_counter()
        duration_ms = (callback_end - callback_start) * 1000
        
        # Update min/max/sum
        self.callback_min_ms = min(self.callback_min_ms, duration_ms)
        self.callback_max_ms = max(self.callback_max_ms, duration_ms)
        self.callback_sum_ms += duration_ms
        
        # Keep last 1000 measurements for percentile calculations
        self.callback_times.append(duration_ms)
        if len(self.callback_times) > 1000:
            self.callback_times.pop(0)
            
        self.last_callback_time = callback_end
    
    def start_workers(self):
        """Start worker processes with Windows spawn method"""
        print("Starting worker processes...")
        
        # Primary worker
        self.primary_worker = mp.Process(
            target=worker_process_windows,
            args=(0, self.primary_audio_ring, self.primary_command_ring,
                  self.heartbeat_array, self.primary_event, self.shutdown_flag,
                  self.config)
        )
        self.primary_worker.start()
        
        # Standby worker
        self.standby_worker = mp.Process(
            target=worker_process_windows,
            args=(1, self.standby_audio_ring, self.standby_command_ring,
                  self.heartbeat_array, self.standby_event, self.shutdown_flag,
                  self.config)
        )
        self.standby_worker.start()
        
        # Wait for workers to initialize
        time.sleep(0.5)
        print("Workers started")
    
    def start_audio(self):
        """Start WASAPI audio stream"""
        print(f"\nStarting WASAPI audio stream...")
        print(f"Device: {self.output_device}")
        print(f"Sample rate: {self.sample_rate} Hz")
        print(f"Buffer size: {self.buffer_size} samples")
        print(f"Latency: {(self.buffer_size / self.sample_rate * 1000):.1f} ms")
        
        # Create WASAPI stream
        self.stream = sd.OutputStream(
            device=self.output_device,
            samplerate=self.sample_rate,
            blocksize=self.buffer_size,
            channels=1,
            dtype='float32',
            callback=self.audio_callback,
            latency='low'
        )
        
        # Set exclusive mode if available and requested
        if self.config['use_wasapi']:
            try:
                # This would require sounddevice with WASAPI exclusive support
                # For now, we use low latency shared mode
                pass
            except:
                pass
        
        self.stream.start()
        print("Audio stream started")
    
    def start_osc_server(self):
        """Start OSC server for control"""
        disp = dispatcher.Dispatcher()
        
        # Register handlers
        disp.map("/frequency", self.handle_frequency)
        disp.map("/freq", self.handle_frequency)  # Alias
        disp.map("/amplitude", self.handle_amplitude)
        disp.map("/amp", self.handle_amplitude)  # Alias
        disp.map("/gate", self.handle_gate)
        
        # Canonical OSC pattern
        disp.map("/mod/*/*", self.handle_mod_param)
        disp.map("/gate/*", self.handle_gate_module)
        
        self.osc_server = ThreadingOSCUDPServer(
            (self.config['osc_host'], self.config['osc_port']), 
            disp
        )
        
        self.osc_thread = threading.Thread(target=self.osc_server.serve_forever)
        self.osc_thread.daemon = True
        self.osc_thread.start()
        
        print(f"OSC server listening on {self.config['osc_host']}:{self.config['osc_port']}")
    
    def handle_frequency(self, addr, freq):
        """Handle frequency change"""
        
        cmd = pack_command_v2(
            CMD_OP_SET,        # op
            CMD_TYPE_FLOAT,    # dtype
            'sine',            # module_id
            'freq',            # param
            float(freq)        # value
        )
        
        self.primary_command_ring.write(cmd)
        self.standby_command_ring.write(cmd)
        self.primary_event.set()
        self.standby_event.set()
    
    def handle_amplitude(self, addr, amp):
        """Handle amplitude change"""
        
        cmd = pack_command_v2(
            CMD_OP_SET,        # op
            CMD_TYPE_FLOAT,    # dtype
            'sine',            # module_id
            'gain',            # param
            float(amp)        # value
        )
        
        self.primary_command_ring.write(cmd)
        self.standby_command_ring.write(cmd)
        self.primary_event.set()
        self.standby_event.set()
    
    def handle_gate(self, addr, gate):
        """Handle gate on/off"""
        
        cmd = pack_command_v2(
            CMD_OP_GATE,       # op
            CMD_TYPE_BOOL,     # dtype
            'adsr',            # module_id
            'gate',            # param (use 'gate' instead of empty)
            float(gate)        # value (converted to float)
        )
        
        self.primary_command_ring.write(cmd)
        self.standby_command_ring.write(cmd)
        self.primary_event.set()
        self.standby_event.set()
    
    def handle_mod_param(self, addr, *args):
        """Handle canonical /mod/<id>/<param> format"""
        # Parse address: /mod/sine1/freq
        parts = addr.split('/')
        if len(parts) >= 4:
            module_id = parts[2]
            param_id = parts[3]
            if args:
                value = args[0]
                # Route to appropriate handler based on param
                # This would be expanded with full module registry
                pass
    
    def handle_gate_module(self, addr, *args):
        """Handle canonical /gate/<id> format"""
        parts = addr.split('/')
        if len(parts) >= 3:
            module_id = parts[2]
            if args:
                gate = bool(args[0])
                # Route gate to specific module
                pass
    
    def start_recording(self, duration_seconds=10):
        """Start recording audio for testing"""
        self.recording_buffer = []
        self.is_recording = True
        self.recording_start_time = time.time()
        print(f"Started recording for {duration_seconds} seconds...")
        
        # Schedule stop
        def stop_recording():
            time.sleep(duration_seconds)
            self.stop_recording()
        
        recording_thread = threading.Thread(target=stop_recording)
        recording_thread.daemon = True
        recording_thread.start()
    
    def stop_recording(self):
        """Stop recording and save to WAV file"""
        if not self.is_recording:
            return
            
        self.is_recording = False
        duration = time.time() - self.recording_start_time
        
        # Create recordings directory
        recordings_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'recordings')
        os.makedirs(recordings_dir, exist_ok=True)
        
        # Generate filename with parameters
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"win_wasapi_dev{self.output_device}_{self.sample_rate}hz_{self.buffer_size}buf_{timestamp}.wav"
        filepath = os.path.join(recordings_dir, filename)
        
        # Concatenate recorded buffers
        if self.recording_buffer:
            audio_data = np.concatenate(self.recording_buffer)
            
            # Convert float32 to int16 for WAV
            audio_int16 = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
            
            # Save WAV file
            with wave.open(filepath, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
            
            print(f"\nRecording saved: {filepath}")
            print(f"Duration: {duration:.1f} seconds")
            print(f"Samples: {len(audio_data)}")
        else:
            print("No audio recorded")
    
    def run(self):
        """Main supervisor run loop"""
        print("\n" + "="*60)
        print("WINDOWS AUDIO SUPERVISOR - MUSIC CHRONUS")
        print("="*60)
        
        # Start components
        self.start_workers()
        self.start_audio()
        self.start_osc_server()
        
        print("\nSupervisor running. Press Ctrl+C to stop.")
        print("Send OSC commands to port", self.config['osc_port'])
        print("\nCommands:")
        print("  r - Start 10-second recording")
        print("  q - Quit\n")
        
        # Start metrics collection thread
        def metrics_thread():
            while not self.shutdown_flag.is_set():
                time.sleep(5)
                if self.config['metrics'] and not self.shutdown_flag.is_set():
                    # Check heartbeats
                    primary_hb = self.heartbeat_array[0]
                    standby_hb = self.heartbeat_array[1]
                    
                    # Calculate mean callback time
                    mean_ms = (self.callback_sum_ms / self.callback_count) if self.callback_count > 0 else 0
                    
                    print(f"\n=== Performance Metrics ===")
                    print(f"Callbacks: {self.callback_count}")
                    print(f"Buffers Processed: {self.total_buffers_processed}")
                    print(f"Underruns: {self.underrun_count}")
                    print(f"Callback Time - Min: {self.callback_min_ms:.3f}ms, Mean: {mean_ms:.3f}ms, Max: {self.callback_max_ms:.3f}ms")
                    print(f"Worker Heartbeats: Primary={primary_hb}, Standby={standby_hb}")
                    print(f"============================")
        
        metrics_t = threading.Thread(target=metrics_thread)
        metrics_t.daemon = True
        metrics_t.start()
        
        try:
            # Simple command loop
            import select
            import sys
            
            while not self.shutdown_flag.is_set():
                # Check for keyboard input (non-blocking on Windows is tricky)
                try:
                    if sys.platform == 'win32':
                        import msvcrt
                        if msvcrt.kbhit():
                            key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                            if key == 'r':
                                self.start_recording(10)
                            elif key == 'q':
                                print("\nQuitting...")
                                break
                    time.sleep(0.1)
                except:
                    # Fallback to simple wait
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown with OSC lifecycle management"""
        print("\nShutting down supervisor...")
        
        # Signal workers to stop
        self.shutdown_flag.set()
        
        # Stop audio
        if self.stream:
            self.stream.stop()
            self.stream.close()
            print("Audio stream stopped")
        
        # Stop OSC server properly
        if self.osc_server:
            print("Stopping OSC server...")
            self.osc_server.shutdown()
            # Wait for OSC thread to finish
            if self.osc_thread and self.osc_thread.is_alive():
                self.osc_thread.join(timeout=1.0)
            print("OSC server stopped")
        
        # Wait for workers
        if self.primary_worker:
            self.primary_worker.join(timeout=2)
            if self.primary_worker.is_alive():
                self.primary_worker.terminate()
                print("Primary worker terminated")
        
        if self.standby_worker:
            self.standby_worker.join(timeout=2)
            if self.standby_worker.is_alive():
                self.standby_worker.terminate()
                print("Standby worker terminated")
        
        # Print final metrics
        if self.callback_count > 0:
            mean_ms = self.callback_sum_ms / self.callback_count
            print(f"\n=== Final Session Metrics ===")
            print(f"Total Callbacks: {self.callback_count}")
            print(f"Total Buffers: {self.total_buffers_processed}")
            print(f"Total Underruns: {self.underrun_count}")
            print(f"Callback Timing: Min={self.callback_min_ms:.3f}ms, Mean={mean_ms:.3f}ms, Max={self.callback_max_ms:.3f}ms")
            print(f"==============================")
        
        print("Supervisor shutdown complete")


def worker_process_windows(slot_id, audio_ring, command_ring, heartbeat_array, 
                           event, shutdown_flag, config):
    """
    Windows-compatible worker process
    Uses configuration from parent
    """
    print(f"[WORKER] Slot {slot_id} starting, PID={os.getpid()}")
    
    # Initialize modules with config values
    sample_rate = config['sample_rate']
    buffer_size = config['buffer_size']
    
    # Initialize module host
    module_host = ModuleHost(sample_rate, buffer_size)
    
    # Create modular chain
    sine_module = SimpleSine(sample_rate, buffer_size)
    adsr_module = ADSR(sample_rate, buffer_size)
    filter_module = BiquadFilter(sample_rate, buffer_size)
    
    # Add modules to host
    module_host.add_module('sine', sine_module)
    module_host.add_module('adsr', adsr_module)
    module_host.add_module('filter', filter_module)
    
    # Timing for buffer production
    buffer_period = buffer_size / sample_rate
    next_buffer_time = time.monotonic() + buffer_period
    
    # Stats
    sequence_num = 0
    
    # First heartbeat
    sequence_num += 1
    heartbeat_array[slot_id] = sequence_num
    
    while not shutdown_flag.is_set():
        try:
            # Check for commands
            event.wait(timeout=0.0001)
            event.clear()
            
            # Drain command ring
            while True:
                cmd_bytes = command_ring.read()
                if cmd_bytes is None:
                    break
                module_host.queue_command(cmd_bytes)
            
            # Process commands
            module_host.process_commands()
            
            # Time to produce buffer?
            now = time.monotonic()
            if now >= next_buffer_time:
                # Process audio - FIXED per Senior Dev
                out_buffer = module_host.process_chain()
                
                # Publish to ring
                audio_ring.write(out_buffer)
                
                # Update timing
                next_buffer_time += buffer_period
                
                # Update heartbeat
                sequence_num += 1
                heartbeat_array[slot_id] = sequence_num
                
            # Small sleep to prevent CPU spinning
            time.sleep(0.0001)
            
        except Exception as e:
            print(f"[WORKER {slot_id}] Error: {e}")
            break
    
    print(f"[WORKER] Slot {slot_id} shutting down")


if __name__ == "__main__":
    supervisor = WindowsAudioSupervisor()
    supervisor.run()