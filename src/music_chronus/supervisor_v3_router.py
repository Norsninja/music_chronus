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

# Import for both module and script execution
try:
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
except ImportError:
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

# Check for router mode
USE_ROUTER = os.environ.get('CHRONUS_ROUTER', '0') == '1'


def worker_process(slot_id, audio_ring, command_ring, heartbeat_array, event, shutdown_flag, use_router=False, patch_queue=None):
    """Worker process with optional router support (CP3)
    
    Args:
        patch_queue: Optional Queue for receiving patch build commands (standby only)
    """
    
    print(f"[WORKER] Slot {slot_id} starting, PID={os.getpid()}, router={use_router}")
    
    # Set up signal handling
    def handle_sigterm(signum, frame):
        print(f"Worker {slot_id} received SIGTERM")
        shutdown_flag.set()
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    # Initialize module host with router support based on passed parameter
    # use_router parameter now indicates if this worker is standby
    module_host = ModuleHost(SAMPLE_RATE, BUFFER_SIZE, use_router=use_router)
    
    if use_router:
        # Create and enable router for standby slot
        router = PatchRouter(BUFFER_SIZE)
        module_host.enable_router(router)
        print(f"[WORKER] Slot {slot_id} router enabled")
        
        # Get module registry for dynamic instantiation
        registry = get_registry()
        
        # Track patch state
        patch_modules = {}  # module_id -> module instance
        patch_ready = False
        
        # Access the registered modules directly
        registered_modules = registry._modules
    else:
        # Traditional linear chain (active slot or router disabled)
        sine_module = SimpleSine(SAMPLE_RATE, BUFFER_SIZE)
        adsr_module = ADSR(SAMPLE_RATE, BUFFER_SIZE)
        filter_module = BiquadFilter(SAMPLE_RATE, BUFFER_SIZE)
        
        module_host.add_module("sine1", sine_module)
        module_host.add_module("adsr1", adsr_module)
        module_host.add_module("filter1", filter_module)
        
        # Configure default patch (using correct parameter names)
        sine_module.set_param("freq", 440.0, immediate=True)  # Fixed: freq not frequency
        sine_module.set_param("gain", 0.25, immediate=True)
        adsr_module.set_param("attack", 10.0, immediate=True)
        adsr_module.set_param("decay", 100.0, immediate=True)
        adsr_module.set_param("sustain", 0.7, immediate=True)
        adsr_module.set_param("release", 100.0, immediate=True)
        filter_module.set_param("cutoff", 2000.0, immediate=True)  # Fixed: cutoff not frequency
        filter_module.set_param("q", 1.0, immediate=True)
    
    # Worker main loop
    buffer_count = 0
    last_heartbeat = time.monotonic()
    
    # Refined scheduling - well-behaved producer
    buffer_period = BUFFER_SIZE / SAMPLE_RATE
    next_deadline = time.perf_counter() + buffer_period
    max_catchup = 2  # Limit buffers per cycle
    lead_target = 2  # Desired ring occupancy
    early_margin = 0.002  # 2ms early to absorb jitter
    
    # Helper to check ring occupancy
    def ring_occupancy(ring):
        head = ring.head.value
        tail = ring.tail.value
        nb = ring.num_buffers
        return (head - tail + nb) % nb  # 0..nb-1
    
    # Instrumentation counters (lightweight)
    n = 0  # Total buffers produced
    late_cycles = 0  # Times we needed catch-up
    writes_dropped = 0  # Times ring was full
    last_stats_time = time.perf_counter()
    last_stats_n = 0  # Last n value we printed stats for
    stats_interval = 500  # Report every N buffers
    
    while not shutdown_flag.is_set():
        # Process patch commands if in standby with router
        if use_router and patch_queue:
            if not patch_queue.empty():
                print(f"[WORKER] Processing patch queue...")
                try:
                    patch_cmd = patch_queue.get_nowait()
                    cmd_type = patch_cmd.get('type')
                    
                    if cmd_type == 'create':
                        module_id = patch_cmd['module_id']
                        module_type = patch_cmd['module_type']
                        
                        # Instantiate module via registry
                        if module_type in registered_modules:
                            module_class = registered_modules[module_type]
                            module = module_class(SAMPLE_RATE, BUFFER_SIZE)
                            patch_modules[module_id] = module
                            
                            # Use helper to add to both host and router with work buffer
                            if use_router:
                                module_host.router_add_module(module_id, module)
                            else:
                                module_host.add_module(module_id, module)
                            
                            print(f"[WORKER] Created {module_type} as {module_id}")
                        else:
                            print(f"[WORKER] Unknown module type: {module_type}")
                        
                    elif cmd_type == 'connect':
                        source_id = patch_cmd['source_id']
                        dest_id = patch_cmd['dest_id']
                        
                        # Connect modules using helper
                        if use_router:
                            module_host.router_connect(source_id, dest_id)
                            print(f"[WORKER] Connected {source_id} -> {dest_id}")
                        
                    elif cmd_type == 'commit':
                        # Validate and finalize patch
                        if use_router and router:
                            try:
                                # Get execution order (validates DAG)
                                execution_order = router.get_processing_order()
                                print(f"[WORKER] Execution order: {execution_order}")
                                
                                # Warm up with a few buffers
                                for _ in range(3):
                                    module_host.process_chain()
                                
                                patch_ready = True
                                print(f"[WORKER] Patch committed and ready")
                            except Exception as e:
                                print(f"[WORKER] Patch commit failed: {e}")
                                patch_ready = False
                            
                    elif cmd_type == 'abort':
                        # Clear patch state
                        patch_modules.clear()
                        if use_router and router:
                            router.clear()
                        # Remove all modules from host
                        for mid in list(module_host.modules.keys()):
                            module_host.remove_module(mid)
                        patch_ready = False
                        print(f"[WORKER] Patch aborted")
                        
                except Exception as e:
                    # Queue empty or error
                    pass
        # Update heartbeat
        current_time = time.monotonic()
        if current_time - last_heartbeat > 0.001:  # 1ms resolution
            heartbeat_array[slot_id] = current_time
            last_heartbeat = current_time
        
        # Signal we're starting
        if buffer_count == 0:
            event.set()
        
        # Process commands - FIX: use has_data() instead of is_empty()
        cmd_count = 0
        while command_ring.has_data():
            cmd = command_ring.read()
            if cmd is not None:
                module_host.queue_command(cmd)
                cmd_count += 1
        
        # Verbose logging when enabled
        if cmd_count > 0 and os.environ.get('CHRONUS_VERBOSE'):
            print(f"[WORKER {slot_id}] Processed {cmd_count} commands")
        
        # Rate-limited production (well-behaved producer)
        produced_this_cycle = 0
        now = time.perf_counter()
        
        # Produce at most max_catchup buffers per cycle
        while produced_this_cycle < max_catchup:
            # Check ring occupancy - don't overfill
            occ = ring_occupancy(audio_ring)
            if occ >= min(audio_ring.num_buffers - 1, lead_target):
                break  # Ring has enough buffers
            
            # Check if we're at deadline
            if now < next_deadline - early_margin:
                break  # Not time yet
            
            # Generate audio
            output_buffer = module_host.process_chain()
            
            # Try to write to ring
            if not audio_ring.write(output_buffer):
                writes_dropped += 1
                break  # Ring full
            
            # Update counters
            produced_this_cycle += 1
            n += 1
            buffer_count += 1
            
            # Track if we're catching up
            if produced_this_cycle > 1:
                late_cycles += 1
            
            # Verbose RMS check every 100 buffers
            if os.environ.get('CHRONUS_VERBOSE') and buffer_count % 100 == 0:
                rms = np.sqrt(np.mean(output_buffer ** 2))
                if rms > 0.001:
                    print(f"[WORKER {slot_id}] Audio generated! RMS={rms:.4f}")
                else:
                    print(f"[WORKER {slot_id}] Silent buffer (RMS={rms:.6f})")
            
            # Update deadline for next buffer
            next_deadline += buffer_period
            
            # Update time for next iteration
            now = time.perf_counter()
        
        # Drift/respawn recovery - soft re-anchor if way behind
        if next_deadline < now - 0.05:  # More than 50ms behind
            next_deadline = now + buffer_period
        
        # Print instrumentation stats periodically (only once per 500 buffers)
        if os.environ.get('CHRONUS_VERBOSE') and n >= last_stats_n + stats_interval:
            period_us = int((now - last_stats_time) / stats_interval * 1e6)
            occ = ring_occupancy(audio_ring)
            print(f"[WORKER {slot_id}] occ={occ}, prod={n}, late={late_cycles}, drop={writes_dropped}, period_us≈{period_us}")
            last_stats_time = now
            last_stats_n = n
            
            # Extra debug for router mode (only when we're actually producing buffers)
            if use_router:
                print(f"[WORKER {slot_id}] Router={use_router}, modules: {list(module_host.modules.keys())}")
                for module_id, module in module_host.modules.items():
                    if hasattr(module, 'params'):
                        print(f"  {module_id}: active={module.active}, params={module.params}")
        
        # Smart sleep/yield until next deadline
        sleep_time = next_deadline - time.perf_counter()
        if sleep_time > 0.001:
            time.sleep(0.001)
        elif sleep_time > 0:
            time.sleep(0)  # Cooperative yield
    
    print(f"[WORKER] Slot {slot_id} shutting down")


class AudioSupervisorV3:
    """Audio supervisor with router support (CP3)"""
    
    def __init__(self):
        """Initialize supervisor with dual-slot architecture"""
        print(f"[SUPERVISOR] Initializing v3 with router support: {USE_ROUTER}")
        
        # Multiprocessing context - use default to match ring buffer context
        # Note: Was using spawn but caused context mismatch with imported rings
        self.ctx = mp
        
        # Audio callback state - zero-allocation pattern from v2
        self.last_good = np.zeros(BUFFER_SIZE, dtype=np.float32)
        
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
        
        # Patch communication (CP3) - for standby slot only
        self.patch_queue = mp.Queue(maxsize=100) if USE_ROUTER else None
        
        # Prime readiness flags (one per worker)
        self.prime_ready = [mp.Value('i', 0), mp.Value('i', 0)]
        
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
        self.target_idx = None  # For buffer-boundary switching
        
        # Initialize with slot 0 as active
        self.spawn_slot0_worker()
        self.spawn_slot1_worker()
    
    def spawn_worker(self, slot_idx, is_standby):
        """Generic worker spawner that sets router based on standby role"""
        if self.workers[slot_idx] is not None:
            self.workers[slot_idx].terminate()
            self.workers[slot_idx].join(timeout=0.5)
        
        self.worker_events[slot_idx].clear()
        self.worker_shutdown_flags[slot_idx].clear()
        
        # Mark standby as not ready when respawning
        if is_standby:
            self.standby_ready = False
        
        # Select appropriate rings based on slot
        audio_ring = self.slot0_audio_ring if slot_idx == 0 else self.slot1_audio_ring
        command_ring = self.slot0_command_ring if slot_idx == 0 else self.slot1_command_ring
        
        # Router enabled only for standby role
        use_router = self.router_enabled and is_standby
        patch_queue = self.patch_queue if is_standby else None
        
        self.workers[slot_idx] = self.ctx.Process(
            target=worker_process,
            args=(slot_idx, audio_ring, command_ring,
                  self.heartbeat_array, self.worker_events[slot_idx],
                  self.worker_shutdown_flags[slot_idx], use_router, patch_queue)
        )
        self.workers[slot_idx].start()
        
        # Track spawn time
        if slot_idx == 0:
            self.slot0_spawn_time = time.monotonic()
        else:
            self.slot1_spawn_time = time.monotonic()
    
    def spawn_slot0_worker(self, is_standby=False):
        """Spawn slot0 worker with specified role"""
        self.spawn_worker(0, is_standby)
    
    def spawn_slot1_worker(self, is_standby=True):
        """Spawn slot1 worker with specified role"""
        self.spawn_worker(1, is_standby)
    
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
        
        # Send to standby worker via patch queue
        if self.patch_queue:
            self.patch_queue.put({
                'type': 'create',
                'module_id': module_id,
                'module_type': module_type
            })
    
    def handle_patch_connect(self, unused_addr, source_id, dest_id):
        """Handle /patch/connect command (CP3)"""
        if not self.router_enabled:
            return
        
        print(f"[OSC] /patch/connect {source_id} {dest_id}")
        
        # Store connection
        if source_id in self.pending_patch:
            self.pending_patch[source_id]['connections'].append(dest_id)
        
        # Send to standby worker via patch queue
        if self.patch_queue:
            self.patch_queue.put({
                'type': 'connect',
                'source_id': source_id,
                'dest_id': dest_id
            })
    
    def handle_patch_commit(self, unused_addr):
        """Handle /patch/commit command (CP3)"""
        if not self.router_enabled:
            return
        
        # Store copy of pending patch before clearing
        modules_to_prime = dict(self.pending_patch)
        
        print(f"[OSC] /patch/commit - Building patch with {len(modules_to_prime)} modules")
        
        # Send commit to standby worker
        if self.patch_queue:
            self.patch_queue.put({'type': 'commit'})
            
            # Wait briefly for patch to be built
            time.sleep(0.05)  # 50ms for patch build + warmup
            
            # Mark standby as ready
            self.standby_ready = True
            self.pending_switch = True
            
            # Post-commit priming: Set sensible defaults for any oscillators and envelopes
            print("[OSC] Priming patch with default values...")
            for module_id, module_info in modules_to_prime.items():
                module_type = module_info.get('type', '')
                
                # Prime oscillators with audible settings
                if 'sine' in module_type or 'osc' in module_id:
                    # Set frequency and gain
                    freq_cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, 'freq', 440.0)
                    gain_cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, 'gain', 0.2)
                    self.slot0_command_ring.write(freq_cmd)
                    self.slot1_command_ring.write(freq_cmd)
                    self.slot0_command_ring.write(gain_cmd)
                    self.slot1_command_ring.write(gain_cmd)
                    print(f"[OSC] Primed {module_id}: freq=440, gain=0.2")
                
                # Prime envelopes with reasonable defaults
                elif 'adsr' in module_type or 'env' in module_id:
                    # Set ADSR parameters
                    attack_cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, 'attack', 10.0)
                    decay_cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, 'decay', 50.0)
                    sustain_cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, 'sustain', 0.7)
                    release_cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, 'release', 200.0)
                    
                    for cmd in [attack_cmd, decay_cmd, sustain_cmd, release_cmd]:
                        self.slot0_command_ring.write(cmd)
                        self.slot1_command_ring.write(cmd)
                    
                    # Auto-gate for testing (gate on briefly)
                    gate_on = pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, module_id, 'gate', 1)
                    self.slot0_command_ring.write(gate_on)
                    self.slot1_command_ring.write(gate_on)
                    print(f"[OSC] Primed {module_id}: ADSR defaults + gate on")
                
                # Prime filters with open settings
                elif 'filter' in module_type or 'filt' in module_id:
                    cutoff_cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, 'cutoff', 2000.0)
                    q_cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, 'q', 1.0)
                    self.slot0_command_ring.write(cutoff_cmd)
                    self.slot1_command_ring.write(cutoff_cmd)
                    self.slot0_command_ring.write(q_cmd)
                    self.slot1_command_ring.write(q_cmd)
                    print(f"[OSC] Primed {module_id}: cutoff=2000, q=1.0")
        
        # Clear pending patch
        self.pending_patch.clear()
        
        print("[OSC] Patch committed - standby ready for switch")
    
    def handle_patch_abort(self, unused_addr):
        """Handle /patch/abort command (CP3)"""
        if not self.router_enabled:
            return
        
        print("[OSC] /patch/abort - Clearing pending patch")
        
        # Send abort to standby worker
        if self.patch_queue:
            self.patch_queue.put({'type': 'abort'})
        
        self.pending_patch.clear()
        self.patch_modules.clear()
        self.standby_ready = False
    
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
        
        # Use consistent environment variables
        osc_host = os.environ.get('CHRONUS_OSC_HOST', '127.0.0.1')
        osc_port = int(os.environ.get('CHRONUS_OSC_PORT', '5005'))
        
        self.osc_server = ThreadingOSCUDPServer((osc_host, osc_port), disp)
        self.osc_thread = threading.Thread(target=self.osc_server.serve_forever)
        self.osc_thread.daemon = True
        self.osc_thread.start()
        
        print(f"[OSC] Server listening on {osc_host}:{osc_port}")
        if self.router_enabled:
            print("[OSC] Router mode enabled - /patch/* commands available")
    
    def handle_module_param(self, address, *args):
        """Handle traditional module parameter changes"""
        print(f"[OSC] Received: {address} with args: {args}")
        parts = address.split('/')
        if len(parts) >= 4 and parts[1] == 'mod':
            module_id = parts[2]
            param = parts[3]
            value = args[0] if args else 0.0
            
            # Parameter aliasing for user-friendly names
            param_aliases = {
                'frequency': 'freq',      # SimpleSine uses 'freq'
                'resonance': 'q',         # BiquadFilter uses 'q'
                'filter_mode': 'mode',    # BiquadFilter uses 'mode'
                # Keep originals that are already correct
                'freq': 'freq',
                'gain': 'gain',
                'attack': 'attack',
                'decay': 'decay',
                'sustain': 'sustain',
                'release': 'release',
                'cutoff': 'cutoff',
                'q': 'q',
                'mode': 'mode',
            }
            
            # Apply alias if exists, otherwise use original
            actual_param = param_aliases.get(param, param)
            
            print(f"[OSC] /mod/{module_id}/{param} = {value} (mapped to '{actual_param}')")
            cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, module_id, actual_param, value)
            
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
        """Audio callback - zero-allocation pattern from v2"""
        if status:
            print(f"[AUDIO] Status: {status}")
        
        # Handle pending switch at buffer boundary
        if self.pending_switch and self.standby_ready:
            # Check if standby has produced at least one buffer
            standby_ring = self.slot1_audio_ring if self.active_idx.value == 0 else self.slot0_audio_ring
            standby_has_audio = (standby_ring.head.value != standby_ring.tail.value)
            
            if standby_has_audio:
                old_active = self.active_idx.value
                new_active = 1 - old_active
                self.active_idx.value = new_active
                self.pending_switch = False
                self.target_idx = None
                print(f"[CALLBACK] Switched to slot {new_active}")
                self.failover_count += 1
                
                # Respawn old active as new standby with router capability
                standby_idx = 1 - new_active
                if standby_idx == 0:
                    self.spawn_slot0_worker(is_standby=True)
                else:
                    self.spawn_slot1_worker(is_standby=True)
        
        # Read from active ring using read_latest() - returns view not copy
        active_ring = self.slot0_audio_ring if self.active_idx.value == 0 else self.slot1_audio_ring
        buffer_view = active_ring.read_latest()
        
        if buffer_view is not None:
            # Copy view to last_good (allocation-free)
            np.copyto(self.last_good, buffer_view)
            self.buffers_output += 1
        else:
            # No buffer available - use existing last_good
            self.none_reads += 1
        
        # Copy last_good to output (allocation-free)
        np.copyto(outdata[:, 0], self.last_good)
        self.total_reads += 1
    
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
                        print(f"[STATS] None reads: {none_read_pct:.2f}%, Failovers: {self.failover_count}, Buffers out: {self.total_reads}")
            
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
    # Map CHRONUS_PULSE_SERVER to PULSE_SERVER if needed
    if 'CHRONUS_PULSE_SERVER' in os.environ and 'PULSE_SERVER' not in os.environ:
        os.environ['PULSE_SERVER'] = os.environ['CHRONUS_PULSE_SERVER']
    
    supervisor = AudioSupervisorV3()
    supervisor.run()