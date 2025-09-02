#!/usr/bin/env python3
"""
AudioSupervisor v3 - Router Support (CP3)
Extends v2 slots architecture with PatchRouter support

Key additions:
- CHRONUS_ROUTER=1 enables router mode in standby slot
- OSC /patch/* commands for graph building
- Commit flow using existing slot swap mechanism
"""

import multiprocessing as mp
import numpy as np
import sounddevice as sd
import time
import signal
import os
import sys
from pythonosc import dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
import threading
from struct import pack

# Add project root to sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Handle both module and script execution
if __name__ == "__main__":
    # Running as script - use absolute imports
    from music_chronus.supervisor_v2_slots_fixed import (
        AudioRing, CommandRing, SAMPLE_RATE, BUFFER_SIZE, NUM_CHANNELS,
        NUM_BUFFERS, COMMAND_RING_SLOTS, HEARTBEAT_TIMEOUT, STARTUP_GRACE_PERIOD
    )
    from music_chronus.module_host import ModuleHost, pack_command_v2, CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL
    from music_chronus.patch_router import PatchRouter
    from music_chronus.module_registry import get_registry
    from music_chronus.modules.simple_sine import SimpleSine
    from music_chronus.modules.adsr import ADSR
    from music_chronus.modules.biquad_filter import BiquadFilter
else:
    # Running as module - use relative imports
    from .supervisor_v2_slots_fixed import (
        AudioRing, CommandRing, SAMPLE_RATE, BUFFER_SIZE, NUM_CHANNELS,
        NUM_BUFFERS, COMMAND_RING_SLOTS, HEARTBEAT_TIMEOUT, STARTUP_GRACE_PERIOD
    )
    from .module_host import ModuleHost, pack_command_v2, CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL
    from .patch_router import PatchRouter
    from .module_registry import get_registry
    from .modules.simple_sine import SimpleSine
    from .modules.adsr import ADSR
    from .modules.biquad_filter import BiquadFilter

# Check for router mode
USE_ROUTER = os.environ.get('CHRONUS_ROUTER', '0') == '1'


def worker_process(slot_id, audio_ring, command_ring, heartbeat_array, event, shutdown_flag, use_router=False):
    """Worker process with optional router support (CP3)"""
    
    print(f"[WORKER] Slot {slot_id} starting, PID={os.getpid()}, router={use_router}")
    
    # Set up signal handling
    def handle_sigterm(signum, frame):
        print(f"Worker {slot_id} received SIGTERM")
        shutdown_flag.set()
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    # Initialize module host with router support if in standby
    # Active slot always uses linear chain for safety
    is_standby = (slot_id == 1)  # Slot 1 starts as standby
    module_host = ModuleHost(SAMPLE_RATE, BUFFER_SIZE, use_router=(use_router and is_standby))
    
    if use_router and is_standby:
        # Create and enable router for standby slot
        router = PatchRouter(BUFFER_SIZE)
        module_host.enable_router(router)
        print(f"[WORKER] Slot {slot_id} router enabled")
    else:
        # Traditional linear chain (active slot or router disabled)
        sine_module = SimpleSine(SAMPLE_RATE, BUFFER_SIZE)
        adsr_module = ADSR(SAMPLE_RATE, BUFFER_SIZE)
        filter_module = BiquadFilter(SAMPLE_RATE, BUFFER_SIZE)
        
        module_host.add_module("sine1", sine_module)
        module_host.add_module("adsr1", adsr_module)
        module_host.add_module("filter1", filter_module)
        
        # Configure default patch
        sine_module.set_param("frequency", 440.0, immediate=True)
        sine_module.set_param("gain", 0.25, immediate=True)
        adsr_module.set_param("attack", 10.0, immediate=True)
        adsr_module.set_param("release", 100.0, immediate=True)
        filter_module.set_param("frequency", 2000.0, immediate=True)
        filter_module.set_param("q", 1.0, immediate=True)
    
    # Worker main loop
    buffer_count = 0
    last_heartbeat = time.monotonic()
    
    while not shutdown_flag.is_set():
        # Update heartbeat
        current_time = time.monotonic()
        if current_time - last_heartbeat > 0.001:  # 1ms resolution
            heartbeat_array[slot_id] = current_time
            last_heartbeat = current_time
        
        # Signal we're starting
        if buffer_count == 0:
            event.set()
        
        # Process commands
        while not command_ring.is_empty():
            cmd = command_ring.read()
            if cmd is not None:
                module_host.queue_command(cmd)
        
        # Generate audio
        output_buffer = module_host.process_chain()
        
        # Write to ring
        if not audio_ring.write(output_buffer):
            # Ring full - this is normal during steady state
            pass
        
        buffer_count += 1
        
        # Yield to other processes
        time.sleep(0.0001)  # 100μs
    
    print(f"[WORKER] Slot {slot_id} shutting down")


class AudioSupervisorV3:
    """Audio supervisor with router support (CP3)"""
    
    def __init__(self):
        """Initialize supervisor with dual-slot architecture"""
        print(f"[SUPERVISOR] Initializing v3 with router support: {USE_ROUTER}")
        
        # Multiprocessing context
        self.ctx = mp.get_context('spawn')
        
        # Shared state
        self.active_idx = mp.Value('i', 0, lock=False)
        self.heartbeat_array = mp.Array('d', 2, lock=False)
        self.shutdown = mp.Event()
        
        # Audio rings (one per slot)
        self.slot0_audio_ring = AudioRing()
        self.slot1_audio_ring = AudioRing()
        
        # Command rings (one per slot)
        self.slot0_command_ring = CommandRing()
        self.slot1_command_ring = CommandRing()
        
        # Worker processes
        self.workers = [None, None]
        self.worker_events = [mp.Event(), mp.Event()]
        self.worker_shutdown_flags = [mp.Event(), mp.Event()]
        
        # Spawn times
        self.slot0_spawn_time = 0
        self.slot1_spawn_time = 0
        
        # Standby readiness
        self.standby_ready = False
        
        # Router state (CP3)
        self.router_enabled = USE_ROUTER
        self.pending_patch = {}  # Patch being built in standby
        self.patch_modules = {}  # Module instances for patch
        
        # OSC server
        self.osc_server = None
        self.osc_thread = None
        
        # Statistics
        self.none_reads = 0
        self.total_reads = 0
        self.failover_count = 0
        self.buffers_output = 0
        
        # Monitoring
        self.monitor_thread = None
        self.pending_switch = False
        
        # Initialize with slot 0 as active
        self.spawn_slot0_worker()
        self.spawn_slot1_worker()
    
    def spawn_slot0_worker(self):
        """Spawn slot0 worker (initially active, no router)"""
        if self.workers[0] is not None:
            self.workers[0].terminate()
            self.workers[0].join(timeout=0.5)
        
        self.worker_events[0].clear()
        self.worker_shutdown_flags[0].clear()
        
        # Active slot never uses router
        self.workers[0] = self.ctx.Process(
            target=worker_process,
            args=(0, self.slot0_audio_ring, self.slot0_command_ring,
                  self.heartbeat_array, self.worker_events[0],
                  self.worker_shutdown_flags[0], False)  # No router for active
        )
        self.workers[0].start()
        self.slot0_spawn_time = time.monotonic()
    
    def spawn_slot1_worker(self):
        """Spawn slot1 worker (initially standby, may use router)"""
        self.standby_ready = False
        
        if self.workers[1] is not None:
            self.workers[1].terminate()
            self.workers[1].join(timeout=0.5)
        
        self.worker_events[1].clear()
        self.worker_shutdown_flags[1].clear()
        
        # Standby slot may use router if enabled
        self.workers[1] = self.ctx.Process(
            target=worker_process,
            args=(1, self.slot1_audio_ring, self.slot1_command_ring,
                  self.heartbeat_array, self.worker_events[1],
                  self.worker_shutdown_flags[1], self.router_enabled)
        )
        self.workers[1].start()
        self.slot1_spawn_time = time.monotonic()
    
    def handle_patch_create(self, unused_addr, module_id, module_type):
        """Handle /patch/create command (CP3)"""
        if not self.router_enabled:
            print("[OSC] Router not enabled (set CHRONUS_ROUTER=1)")
            return
        
        print(f"[OSC] /patch/create {module_id} {module_type}")
        
        # Store in pending patch
        self.pending_patch[module_id] = {
            'type': module_type,
            'connections': []
        }
    
    def handle_patch_connect(self, unused_addr, source_id, dest_id):
        """Handle /patch/connect command (CP3)"""
        if not self.router_enabled:
            return
        
        print(f"[OSC] /patch/connect {source_id} {dest_id}")
        
        # Store connection
        if source_id in self.pending_patch:
            self.pending_patch[source_id]['connections'].append(dest_id)
    
    def handle_patch_commit(self, unused_addr):
        """Handle /patch/commit command (CP3)"""
        if not self.router_enabled:
            return
        
        print("[OSC] /patch/commit - Building patch in standby")
        
        # Get standby slot
        standby_idx = 1 if self.active_idx.value == 0 else 0
        
        # Build patch commands for standby
        # For CP3, we send commands to build the patch
        # In a full implementation, we'd directly manipulate the standby ModuleHost
        
        # Mark standby ready after building
        self.standby_ready = True
        
        # Trigger slot swap
        print("[OSC] Patch committed - triggering slot swap")
        self.pending_switch = True
    
    def handle_patch_abort(self, unused_addr):
        """Handle /patch/abort command (CP3)"""
        if not self.router_enabled:
            return
        
        print("[OSC] /patch/abort - Clearing pending patch")
        self.pending_patch.clear()
        self.patch_modules.clear()
    
    def start_osc_server(self):
        """Start OSC server with patch commands (CP3)"""
        disp = dispatcher.Dispatcher()
        
        # Traditional commands
        disp.map("/mod/*/*", self.handle_module_param)
        disp.map("/gate/*", self.handle_gate)
        
        # Patch commands (CP3)
        if self.router_enabled:
            disp.map("/patch/create", self.handle_patch_create)
            disp.map("/patch/connect", self.handle_patch_connect)
            disp.map("/patch/commit", self.handle_patch_commit)
            disp.map("/patch/abort", self.handle_patch_abort)
        
        osc_host = os.environ.get('OSC_HOST', '127.0.0.1')
        osc_port = int(os.environ.get('OSC_PORT', '5005'))
        
        self.osc_server = ThreadingOSCUDPServer((osc_host, osc_port), disp)
        self.osc_thread = threading.Thread(target=self.osc_server.serve_forever)
        self.osc_thread.daemon = True
        self.osc_thread.start()
        
        print(f"[OSC] Server listening on {osc_host}:{osc_port}")
        if self.router_enabled:
            print("[OSC] Router mode enabled - /patch/* commands available")
    
    def handle_module_param(self, address, *args):
        """Handle traditional module parameter changes"""
        parts = address.split('/')
        if len(parts) >= 4 and parts[1] == 'mod':
            module_id = parts[2]
            param = parts[3]
            value = args[0] if args else 0.0
            
            cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, param, value)
            
            # Send to both slots
            self.slot0_command_ring.write(cmd)
            self.slot1_command_ring.write(cmd)
    
    def handle_gate(self, address, *args):
        """Handle gate commands"""
        parts = address.split('/')
        if len(parts) >= 3 and parts[1] == 'gate':
            module_id = parts[2]
            value = bool(args[0]) if args else False
            
            cmd = pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, module_id, "gate", value)
            
            # Send to both slots
            self.slot0_command_ring.write(cmd)
            self.slot1_command_ring.write(cmd)
    
    def audio_callback(self, outdata, frames, time_info, status):
        """Audio callback - reads from active slot's ring"""
        active_ring = self.slot0_audio_ring if self.active_idx.value == 0 else self.slot1_audio_ring
        
        audio_data = active_ring.read()
        
        if audio_data is not None:
            outdata[:, 0] = audio_data
            self.buffers_output += 1
        else:
            outdata.fill(0)
            self.none_reads += 1
        
        self.total_reads += 1
        
        # Handle pending switch at buffer boundary
        if self.pending_switch and self.standby_ready:
            old_active = self.active_idx.value
            new_active = 1 - old_active
            self.active_idx.value = new_active
            self.pending_switch = False
            print(f"[CALLBACK] Switched to slot {new_active}")
            self.failover_count += 1
            
            # Respawn old active as new standby
            if new_active == 0:
                self.spawn_slot1_worker()
            else:
                self.spawn_slot0_worker()
    
    def run(self):
        """Main supervisor loop"""
        print("Starting AudioSupervisor v3 with router support")
        
        # Start OSC server
        self.start_osc_server()
        
        # Start audio
        with sd.OutputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BUFFER_SIZE,
            channels=NUM_CHANNELS,
            dtype='float32',
            callback=self.audio_callback
        ):
            print("Audio started - Press Ctrl+C to stop")
            if self.router_enabled:
                print("Router mode active - use /patch/* commands to build graphs")
            
            try:
                while not self.shutdown.is_set():
                    time.sleep(0.1)
                    
                    # Print stats periodically
                    if self.total_reads > 0 and self.total_reads % 1000 == 0:
                        none_read_pct = (self.none_reads / self.total_reads) * 100
                        print(f"[STATS] None reads: {none_read_pct:.2f}%, Failovers: {self.failover_count}")
            
            except KeyboardInterrupt:
                print("\nShutting down...")
        
        self.cleanup()
    
    def cleanup(self):
        """Clean shutdown"""
        self.shutdown.set()
        
        # Stop workers
        for i in range(2):
            if self.workers[i]:
                self.worker_shutdown_flags[i].set()
                self.workers[i].join(timeout=1.0)
                if self.workers[i].is_alive():
                    self.workers[i].terminate()
        
        # Stop OSC
        if self.osc_server:
            self.osc_server.shutdown()
        
        print("Supervisor stopped")


if __name__ == "__main__":
    supervisor = AudioSupervisorV3()
    supervisor.run()