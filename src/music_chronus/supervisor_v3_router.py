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
    # TEMPORARILY COMMENTED: Isolating sequencer import
    # from music_chronus.sequencer import SequencerManager
    from music_chronus.modules.biquad_filter import BiquadFilter

# Check for router mode
USE_ROUTER = os.environ.get('CHRONUS_ROUTER', '0') == '1'


def worker_process(slot_id, audio_ring, command_ring, heartbeat_array, event, shutdown_flag, is_standby=False, patch_queue=None, prime_ready=None):
    """Worker process with optional router support (CP3)
    
    Args:
        patch_queue: Optional Queue for receiving patch build commands (standby only)
        prime_ready: Optional mp.Value to signal priming completion
    """
    
    # Disable GC for deterministic timing
    import gc
    gc.disable()
    
    # Determine if this worker should use router based on system mode and role
    use_router = USE_ROUTER and is_standby
    print(f"[WORKER] Slot {slot_id} starting, PID={os.getpid()}, standby={is_standby}, router={use_router}, GC disabled")
    
    # Set up signal handling
    def handle_sigterm(signum, frame):
        print(f"Worker {slot_id} received SIGTERM")
        shutdown_flag.set()
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    # Initialize module host with router support based on passed parameter
    # Initialize module host
    module_host = ModuleHost(SAMPLE_RATE, BUFFER_SIZE, use_router=use_router)
    
    # Determine what to initialize based on system mode and worker role
    if USE_ROUTER:
        # System is in router mode
        if is_standby:
            # Standby slot: Create and enable router for building patches
            router = PatchRouter(BUFFER_SIZE)
            module_host.enable_router(router)
            print(f"[WORKER] Slot {slot_id} router enabled (standby)")
            
            # Get module registry for dynamic instantiation
            registry = get_registry()
            
            # Track patch state
            patch_modules = {}  # module_id -> module instance
            patch_ready = False
            
            # Access the registered modules directly
            registered_modules = registry._modules
        else:
            # Active slot in router mode: Start empty, wait for committed patches
            print(f"[WORKER] Slot {slot_id} starting empty (active, router mode)")
            router = None
            patch_modules = {}
            patch_ready = False
            registered_modules = {}
    else:
        # Traditional mode (non-router)
        if not is_standby:
            # Active slot: Build default chain
            print(f"[WORKER] Slot {slot_id} building default chain (active, traditional mode)")
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
            adsr_module.set_gate(True)  # FIXED: Use correct method to trigger gate
            filter_module.set_param("cutoff", 2000.0, immediate=True)  # Fixed: cutoff not frequency
            filter_module.set_param("q", 1.0, immediate=True)
        else:
            # Standby slot in traditional mode: Empty
            print(f"[WORKER] Slot {slot_id} starting empty (standby, traditional mode)")
            router = None
            patch_modules = {}
            patch_ready = False
            registered_modules = {}
    
    # Initial prefill to prevent emergency fills at startup
    # Fill the ring with 2-3 buffers before starting main loop
    prefill_count = int(os.environ.get('CHRONUS_PREFILL_BUFFERS', '3'))
    for i in range(prefill_count):
        output_buffer = module_host.process_chain()
        if audio_ring.write(output_buffer):
            if os.environ.get('CHRONUS_VERBOSE'):
                rms = np.sqrt(np.mean(output_buffer ** 2))
                print(f"[WORKER {slot_id}] Prefill {i+1}: RMS={rms:.4f}")
                # Warn if producing silence
                if rms < 0.001:
                    print(f"[WARNING] Worker {slot_id} prefill producing silence (RMS={rms:.4f})")
        else:
            break  # Ring full
    
    # Worker main loop
    buffer_count = 0
    last_heartbeat = time.monotonic()
    
    # Refined scheduling - well-behaved producer
    buffer_period = BUFFER_SIZE / SAMPLE_RATE
    next_deadline = time.perf_counter() + buffer_period
    # Environment-driven tuning knobs (Senior Dev Track A polish)
    max_catchup = int(os.environ.get('CHRONUS_MAX_CATCHUP', '2'))  # Limit buffers per cycle
    lead_target = int(os.environ.get('CHRONUS_LEAD_TARGET', '2'))  # Desired ring occupancy  
    early_margin = float(os.environ.get('CHRONUS_EARLY_MARGIN_MS', '2')) / 1000.0  # Convert ms to seconds
    
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
    emergency_count = 0  # Total emergency fills
    last_stats_time = time.perf_counter()
    last_stats_n = 0  # Last n value we printed stats for
    stats_interval = 500  # Report every N buffers
    
    while not shutdown_flag.is_set():
        # Process patch commands if in standby with router
        if USE_ROUTER and is_standby and patch_queue:
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
                        if USE_ROUTER and is_standby and 'router' in locals() and router:
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
                            
                    elif cmd_type == 'prime':
                        # Prime operation: apply parameters and warm up
                        prime_ops = patch_cmd.get('ops', [])
                        warmup_count = patch_cmd.get('warmup', 8)
                        
                        print(f"[WORKER {slot_id}] Applying {len(prime_ops)} prime operations")
                        
                        # Apply all operations with immediate=True
                        for op_type, module_id, param, value in prime_ops:
                            if module_id not in patch_modules:
                                print(f"[WORKER {slot_id}] Warning: module {module_id} not found")
                                continue
                                
                            module = patch_modules[module_id]
                            
                            if op_type == 'mod':
                                # Set parameter immediately
                                module.set_param(param, value, immediate=True)
                                print(f"[WORKER {slot_id}] Set {module_id}.{param} = {value}")
                                
                            elif op_type == 'gate':
                                # param is None for gate ops, value is 0 or 1
                                if hasattr(module, 'set_gate'):
                                    module.set_gate(bool(value))
                                else:
                                    # Fallback to set_param
                                    module.set_param('gate', float(value), immediate=True)
                                print(f"[WORKER {slot_id}] Set {module_id} gate = {value}")
                        
                        # Warmup: Generate buffers to stabilize
                        print(f"[WORKER {slot_id}] Warming up with {warmup_count} buffers...")
                        warmup_results = []
                        
                        for i in range(warmup_count):
                            output = module_host.process_chain()
                            rms = np.sqrt(np.mean(output ** 2))
                            warmup_results.append(rms)
                            
                            if i < 3:  # Log first few
                                print(f"[WORKER {slot_id}] Warmup {i}: RMS={rms:.6f}")
                        
                        # Check for non-silent output
                        max_rms = max(warmup_results) if warmup_results else 0.0
                        if max_rms > 0.001:
                            print(f"[WORKER {slot_id}] Prime complete! Max RMS={max_rms:.4f}")
                            
                            # Prefill ring with 4 buffers before signaling ready (matches keep_after_read=2)
                            print(f"[WORKER {slot_id}] Prefilling ring with 4 buffers...")
                            for i in range(4):
                                output = module_host.process_chain()
                                if audio_ring.write(output):
                                    rms = np.sqrt(np.mean(output ** 2))
                                    print(f"[WORKER {slot_id}] Prefill {i+1}: RMS={rms:.4f}")
                            
                            # Now signal ready
                            if prime_ready:
                                prime_ready.value = 1  # Signal supervisor
                                print(f"[WORKER {slot_id}] prime_ready set")
                            patch_ready = True
                        else:
                            print(f"[WORKER {slot_id}] WARNING: Warmup silent, max RMS={max_rms:.6f}")
                            # Don't set prime_ready if silent
                            
                    elif cmd_type == 'abort':
                        # Clear patch state
                        patch_modules.clear()
                        if USE_ROUTER and is_standby and 'router' in locals() and router:
                            router.clear()
                        # Remove all modules from host
                        for mid in list(module_host.modules.keys()):
                            module_host.remove_module(mid)
                        patch_ready = False
                        # Reset prime readiness on abort
                        if prime_ready:
                            prime_ready.value = 0
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
        emergency_filled = False  # Flag to allow catch-up after emergency fill
        
        # PROACTIVE EARLY-FILL: Emergency buffer when ring is empty
        # If ring is at 0 and we haven't produced yet, generate ONE buffer immediately
        # without advancing the deadline anchor - prevents ring starvation pops
        occ = ring_occupancy(audio_ring)
        if occ == 0 and produced_this_cycle == 0:
            # Emergency fill - generate exactly one buffer NOW
            emergency_count += 1
            if os.environ.get('CHRONUS_VERBOSE'):
                print(f"[WORKER {slot_id}] EMERGENCY FILL: occ=0, producing one buffer immediately")
            
            output_buffer = module_host.process_chain()
            
            # Try to write to ring
            if audio_ring.write(output_buffer):
                produced_this_cycle += 1
                n += 1
                buffer_count += 1
                
                # CRITICAL FIX: Advance deadline as on-time production
                next_deadline = max(next_deadline, now) + buffer_period
                
                # Log emergency fill success if verbose
                if os.environ.get('CHRONUS_VERBOSE'):
                    rms = np.sqrt(np.mean(output_buffer ** 2))
                    print(f"[WORKER {slot_id}] Emergency fill complete: RMS={rms:.4f}, new occ={ring_occupancy(audio_ring)}")
                
                # Recompute now for next iteration
                now = time.perf_counter()
                # Set flag to allow immediate catch-up in main loop
                emergency_filled = True
            # Continue to main loop to produce more buffers if needed
        
        # Produce at most max_catchup buffers per cycle
        while produced_this_cycle < max_catchup:
            # Check ring occupancy - don't overfill
            occ = ring_occupancy(audio_ring)
            if occ >= min(audio_ring.num_buffers - 1, lead_target):
                break  # Ring has enough buffers
            
            # Check if we're at deadline (with catch-up override after emergency)
            time_gate = now < next_deadline - early_margin
            
            # Rebuild mode: allow immediate production until we reach target or hit max_catchup
            allow_immediate = emergency_filled and occ < lead_target and produced_this_cycle < max_catchup
            
            if allow_immediate:
                if os.environ.get('CHRONUS_VERBOSE'):
                    print(f"[WORKER {slot_id}] Catch-up override: occ={occ}, target={lead_target}, allowing immediate production")
                time_gate = False  # Override time gate for catch-up
            
            if time_gate:
                break  # Not time yet
            
            # Generate audio
            output_buffer = module_host.process_chain()
            
            # Try to write to ring
            if not audio_ring.write(output_buffer):
                writes_dropped += 1
                if os.environ.get('CHRONUS_VERBOSE'):
                    print(f"[WORKER {slot_id}] DEBUG: Write failed after override! Ring full? occ={ring_occupancy(audio_ring)}")
                break  # Ring full
            elif allow_immediate and os.environ.get('CHRONUS_VERBOSE'):
                print(f"[WORKER {slot_id}] DEBUG: Catch-up buffer written successfully, new occ={ring_occupancy(audio_ring)}")
            
            # Update counters
            produced_this_cycle += 1
            n += 1
            buffer_count += 1
            
            # Track if we're catching up
            if produced_this_cycle > 1:
                late_cycles += 1
            
            # Verbose RMS check - more frequent after prime
            log_interval = 10 if buffer_count < 50 else 100
            if os.environ.get('CHRONUS_VERBOSE') and buffer_count % log_interval == 0:
                rms = np.sqrt(np.mean(output_buffer ** 2))
                if rms > 0.001:
                    print(f"[WORKER {slot_id}] Buffer {buffer_count}: Audio generated! RMS={rms:.4f}, occ={occ}")
                else:
                    print(f"[WORKER {slot_id}] Buffer {buffer_count}: Silent buffer (RMS={rms:.6f}), occ={occ}")
            
            # Update deadline for next buffer
            next_deadline += buffer_period
            
            # Update time for next iteration
            now = time.perf_counter()
            
            # Clear emergency flag once we've reached target or can't produce more
            if emergency_filled:
                new_occ = ring_occupancy(audio_ring)
                if new_occ >= lead_target or produced_this_cycle >= max_catchup:
                    emergency_filled = False
                    if os.environ.get('CHRONUS_VERBOSE'):
                        print(f"[WORKER {slot_id}] Rebuild complete: occ={new_occ}, produced={produced_this_cycle}")
        
        # Drift/respawn recovery - soft re-anchor if way behind
        if next_deadline < now - 0.05:  # More than 50ms behind
            next_deadline = now + buffer_period
        
        # Print instrumentation stats periodically (only once per 500 buffers)
        if os.environ.get('CHRONUS_VERBOSE') and n >= last_stats_n + stats_interval:
            period_us = int((now - last_stats_time) / stats_interval * 1e6)
            occ = ring_occupancy(audio_ring)
            emergency_per_1k = emergency_count * 1000 // max(1, n)
            print(f"[WORKER {slot_id}] occ={occ}, prod={n}, late={late_cycles}, drop={writes_dropped}, "
                  f"emergency={emergency_count} ({emergency_per_1k}/1k), period_us≈{period_us}")
            print(f"[WORKER {slot_id}] Config: lead_target={lead_target}, max_catchup={max_catchup}, "
                  f"early_margin_ms={early_margin*1000:.1f}, buffer_period_ms={buffer_period*1000:.2f}")
            last_stats_time = now
            last_stats_n = n
            
            # Extra debug for router mode (only when we're actually producing buffers)
            if use_router:
                print(f"[WORKER {slot_id}] Router={use_router}, modules: {list(module_host.modules.keys())}")
                for module_id, module in module_host.modules.items():
                    if hasattr(module, 'params'):
                        print(f"  {module_id}: active={module.active}, params={module.params}")
        
        # Two-phase sleep with busy-wait for precise timing
        # Per Senior Dev: extend to 3ms tail for better timing stability
        now_ns = time.perf_counter_ns()
        deadline_ns = int(next_deadline * 1e9)
        time_until_deadline_ns = deadline_ns - now_ns
        
        if time_until_deadline_ns > 3_000_000:  # > 3ms
            # Coarse sleep until ~3ms before deadline
            time.sleep((time_until_deadline_ns - 3_000_000) / 1e9)
        
        # Busy-wait for the final ≤3ms (actually ≤1ms per Senior Dev)
        while time.perf_counter_ns() < deadline_ns - 1_000_000:  # Until 1ms before
            pass  # Spin
        
        # Final precise wait
        while time.perf_counter_ns() < deadline_ns:
            pass  # Spin until exact deadline
    
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
        # Per-worker patch queues to avoid race conditions (Senior Dev fix)
        self.patch_queues = [mp.Queue(maxsize=100), mp.Queue(maxsize=100)] if USE_ROUTER else [None, None]
        
        # Prime readiness flags (one per worker)
        self.prime_ready = [mp.Value('i', 0), mp.Value('i', 0)]
        
        # Spawn times
        self.slot0_spawn_time = 0
        self.slot1_spawn_time = 0
        
        # Standby readiness
        self.standby_ready = False
        
        # Router state (CP3)
        self.router_enabled = USE_ROUTER
        
        # Recording state
        self.recording = False
        self.record_buffer = []
        self.record_filename = None
        self.record_start_time = None
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
        
        # Senior Dev's instrumentation (Track A polish)
        self.occ_zero_count = 0    # Counter for occupancy==0 events
        self.underflow_count = 0   # Counter for PortAudio underflows
        self.overflow_count = 0    # Counter for PortAudio overflows
        
        # Monitoring
        self.monitor_thread = None
        self.pending_switch = False
        self.target_idx = None  # For buffer-boundary switching
        
        # Initialize sequencer manager
        # TEMPORARILY COMMENTED: Isolating sequencer
        # self.sequencer_manager = SequencerManager(
        #     self.slot0_command_ring, 
        #     self.slot1_command_ring,
        #     sample_rate=SAMPLE_RATE,
        #     buffer_size=BUFFER_SIZE
        # )
        
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
        
        # Reset prime readiness when spawning
        self.prime_ready[slot_idx].value = 0
        
        # Mark standby as not ready when respawning
        if is_standby:
            self.standby_ready = False
        
        # Select appropriate rings based on slot
        audio_ring = self.slot0_audio_ring if slot_idx == 0 else self.slot1_audio_ring
        command_ring = self.slot0_command_ring if slot_idx == 0 else self.slot1_command_ring
        
        # Pass is_standby to worker to determine its role
        # use_router is True only when both system is in router mode AND worker is standby
        use_router = USE_ROUTER and is_standby
        # Pass the specific queue for this slot (only standby gets it in router mode)
        patch_queue = self.patch_queues[slot_idx] if (USE_ROUTER and is_standby) else None
        
        self.workers[slot_idx] = self.ctx.Process(
            target=worker_process,
            args=(slot_idx, audio_ring, command_ring,
                  self.heartbeat_array, self.worker_events[slot_idx],
                  self.worker_shutdown_flags[slot_idx], is_standby, patch_queue,
                  self.prime_ready[slot_idx])  # Pass prime_ready to worker
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
        if USE_ROUTER:
            # Route to standby worker only
            standby_idx = 1 - self.active_idx.value
            print(f"[OSC] Routing patch create to standby slot {standby_idx}")
            self.patch_queues[standby_idx].put({
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
        if USE_ROUTER:
            # Route to standby worker only
            standby_idx = 1 - self.active_idx.value
            print(f"[OSC] Routing patch connect to standby slot {standby_idx}")
            self.patch_queues[standby_idx].put({
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
        if USE_ROUTER:
            # Route to standby worker only
            standby_idx = 1 - self.active_idx.value
            print(f"[OSC] Routing patch commit to standby slot {standby_idx}")
            self.patch_queues[standby_idx].put({'type': 'commit'})
            
            # Wait briefly for DAG build
            time.sleep(0.02)  # 20ms for patch build
            
            # Build prime operations (4-tuple format)
            prime_ops = []
            
            for module_id, module_info in modules_to_prime.items():
                module_type = module_info.get('type', '')
                
                # Oscillators
                if 'sine' in module_type or 'osc' in module_id:
                    prime_ops.append(('mod', module_id, 'freq', 440.0))
                    prime_ops.append(('mod', module_id, 'gain', 0.2))
                
                # Envelopes  
                elif 'adsr' in module_type or 'env' in module_id:
                    prime_ops.append(('mod', module_id, 'attack', 10.0))
                    prime_ops.append(('mod', module_id, 'decay', 50.0))
                    prime_ops.append(('mod', module_id, 'sustain', 0.7))
                    prime_ops.append(('mod', module_id, 'release', 200.0))
                    prime_ops.append(('gate', module_id, None, 1))  # Gate on
                
                # Filters
                elif 'filter' in module_type or 'filt' in module_id:
                    prime_ops.append(('mod', module_id, 'cutoff', 2000.0))
                    prime_ops.append(('mod', module_id, 'q', 1.0))
            
            # Send prime command to standby
            print(f"[OSC] Sending {len(prime_ops)} prime ops to standby worker")
            # Route prime operations to standby worker only
            self.patch_queues[standby_idx].put({
                'type': 'prime',
                'ops': prime_ops,
                'warmup': 8
            })
            
            # Wait for prime completion with timeout
            standby_idx = 1 - self.active_idx.value
            print(f"[OSC] Waiting for standby slot {standby_idx} to prime (active={self.active_idx.value})")
            if os.environ.get('CHRONUS_VERBOSE', '0') == '1':
                print(f"[OSC] Prime flags: slot0={self.prime_ready[0].value}, slot1={self.prime_ready[1].value}")
            start_time = time.perf_counter()
            timeout = 0.5  # 500ms timeout
            
            while time.perf_counter() - start_time < timeout:
                if self.prime_ready[standby_idx].value == 1:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    print(f"[OSC] Standby primed in {elapsed_ms:.1f}ms")
                    self.standby_ready = True
                    self.pending_switch = True
                    break
                time.sleep(0.01)  # Check every 10ms
            else:
                # Timeout - don't switch to potentially silent patch
                print(f"[OSC] WARNING: Prime timeout after {timeout}s - NOT switching")
                self.standby_ready = False  # Don't allow switch
                # Note: standby worker continues trying to prime in background
        
        # Clear pending patch
        self.pending_patch.clear()
    
    def handle_patch_abort(self, unused_addr):
        """Handle /patch/abort command (CP3)"""
        if not self.router_enabled:
            return
        
        print("[OSC] /patch/abort - Clearing pending patch")
        
        # Send abort to standby worker
        if USE_ROUTER:
            # Route to standby worker only
            standby_idx = 1 - self.active_idx.value
            print(f"[OSC] Routing patch abort to standby slot {standby_idx}")
            self.patch_queues[standby_idx].put({'type': 'abort'})
        
        self.pending_patch.clear()
        self.patch_modules.clear()
        self.standby_ready = False
    
    def start_recording(self, filename=None):
        """Start recording audio to WAV file."""
        if self.recording:
            print("[RECORD] Already recording")
            return
        
        # Generate filename if not provided
        if not filename:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.wav"
        
        # Initialize recording
        self.record_buffer = []
        self.record_filename = filename
        self.record_start_time = time.perf_counter()
        self.recording = True
        print(f"[RECORD] Started recording to {filename}")
    
    def stop_recording(self):
        """Stop recording and save WAV file."""
        if not self.recording:
            print("[RECORD] Not recording")
            return
        
        self.recording = False
        
        if self.record_buffer:
            # Concatenate all buffers
            audio_data = np.concatenate(self.record_buffer)
            
            # Convert float32 [-1,1] to int16 for WAV
            audio_int = np.int16(np.clip(audio_data, -1.0, 1.0) * 32767)
            
            # Write WAV file
            from scipy.io import wavfile
            wavfile.write(self.record_filename, int(SAMPLE_RATE), audio_int)
            
            # Calculate duration and size
            duration = len(audio_data) / SAMPLE_RATE
            file_size = len(audio_data) * 2 / 1024 / 1024  # MB
            
            print(f"[RECORD] Saved {duration:.1f}s ({file_size:.1f}MB) to {self.record_filename}")
            
            # Clear buffer to free memory
            self.record_buffer = []
        else:
            print("[RECORD] No audio recorded")
    
    def handle_record_start(self, unused_addr, *args):
        """OSC handler for /record/start [filename]"""
        filename = args[0] if args else None
        self.start_recording(filename)
    
    def handle_record_stop(self, unused_addr):
        """OSC handler for /record/stop"""
        self.stop_recording()
    
    def handle_record_status(self, unused_addr):
        """OSC handler for /record/status"""
        if self.recording:
            duration = time.perf_counter() - self.record_start_time
            buffer_count = len(self.record_buffer)
            memory_mb = buffer_count * BUFFER_SIZE * 4 / 1024 / 1024
            print(f"[RECORD] Recording: {duration:.1f}s, {buffer_count} buffers, {memory_mb:.1f}MB")
        else:
            print("[RECORD] Not recording")
    
    # TEMPORARILY COMMENTED: Isolating sequencer
    # All sequencer handlers commented out
    '''
    def handle_seq_create(self, unused_addr, *args):
        """Create a new sequencer: /seq/create <id>"""
        if args:
            seq_id = str(args[0])
            if self.sequencer_manager.create_sequencer(seq_id):
                print(f"[SEQ] Created sequencer '{seq_id}'")
            else:
                print(f"[SEQ] Sequencer '{seq_id}' already exists")
    
    def handle_seq_config(self, unused_addr, *args):
        """Configure sequencer: /seq/config <id> <bpm> <steps> <division>"""
        if len(args) >= 4:
            seq_id = str(args[0])
            bpm = float(args[1])
            steps = int(args[2])
            division = int(args[3])
            self.sequencer_manager.queue_update(seq_id, 'config', (bpm, steps, division))
            print(f"[SEQ] Configured {seq_id}: {bpm} BPM, {steps} steps, 1/{division} notes")
    
    def handle_seq_pattern(self, unused_addr, *args):
        """Set pattern: /seq/pattern <id> <pattern_string>"""
        if len(args) >= 2:
            seq_id = str(args[0])
            pattern = str(args[1])
            self.sequencer_manager.queue_update(seq_id, 'pattern', pattern)
            print(f"[SEQ] Set pattern for {seq_id}: {pattern}")
    
    def handle_seq_param_lane(self, unused_addr, *args):
        """Set parameter lane: /seq/param_lane <id> <param> <values...>"""
        if len(args) >= 3:
            seq_id = str(args[0])
            param = str(args[1])
            # Combine remaining args as CSV
            values = ','.join(str(v) for v in args[2:])
            self.sequencer_manager.queue_update(seq_id, 'param_lane', (param, values))
            print(f"[SEQ] Set param lane {param} for {seq_id}")
    
    def handle_seq_assign(self, unused_addr, *args):
        """Assign sequencer output: /seq/assign <id> <gate|param> <module> [param_name]"""
        if len(args) >= 3:
            seq_id = str(args[0])
            assign_type = str(args[1])
            module_id = str(args[2])
            
            if assign_type == 'gate':
                self.sequencer_manager.queue_update(seq_id, 'assign_gate', module_id)
                print(f"[SEQ] Assigned {seq_id} gate to {module_id}")
            elif assign_type == 'param' and len(args) >= 5:
                param_name = str(args[3])
                module_param = str(args[4])
                self.sequencer_manager.queue_update(seq_id, 'assign_param', (param_name, module_id, module_param))
                print(f"[SEQ] Assigned {seq_id} param {param_name} to {module_id}.{module_param}")
    
    def handle_seq_start(self, unused_addr, *args):
        """Start sequencer: /seq/start <id>"""
        if args:
            seq_id = str(args[0])
            self.sequencer_manager.queue_update(seq_id, 'start', None)
            print(f"[SEQ] Started {seq_id}")
    
    def handle_seq_stop(self, unused_addr, *args):
        """Stop sequencer: /seq/stop <id>"""
        if args:
            seq_id = str(args[0])
            self.sequencer_manager.queue_update(seq_id, 'stop', None)
            print(f"[SEQ] Stopped {seq_id}")
    
    def handle_seq_reset(self, unused_addr, *args):
        """Reset sequencer: /seq/reset <id>"""
        if args:
            seq_id = str(args[0])
            self.sequencer_manager.queue_update(seq_id, 'reset', None)
            print(f"[SEQ] Reset {seq_id}")
    
    def handle_seq_reset_all(self, unused_addr):
        """Reset all sequencers: /seq/reset_all"""
        for seq_id in self.sequencer_manager.sequencers:
            self.sequencer_manager.queue_update(seq_id, 'reset', None)
        print("[SEQ] Reset all sequencers")
    
    def handle_seq_bpm(self, unused_addr, *args):
        """Change BPM: /seq/bpm <id> <bpm>"""
        if len(args) >= 2:
            seq_id = str(args[0])
            bpm = float(args[1])
            self.sequencer_manager.queue_update(seq_id, 'bpm', bpm)
            print(f"[SEQ] Set {seq_id} to {bpm} BPM")
    
    def handle_seq_gate_len(self, unused_addr, *args):
        """Set gate length: /seq/gate_len <id> <fraction>"""
        if len(args) >= 2:
            seq_id = str(args[0])
            gate_len = float(args[1])
            self.sequencer_manager.queue_update(seq_id, 'gate_length', gate_len)
            print(f"[SEQ] Set {seq_id} gate length to {gate_len}")
    '''
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
        
        # Recording commands
        disp.map("/record/start", self.handle_record_start)
        disp.map("/record/stop", self.handle_record_stop)
        disp.map("/record/status", self.handle_record_status)
        
        # Sequencer commands
        # TEMPORARILY COMMENTED: Isolating sequencer
        # disp.map("/seq/create", self.handle_seq_create)
        # disp.map("/seq/config", self.handle_seq_config)
        # disp.map("/seq/pattern", self.handle_seq_pattern)
        # disp.map("/seq/param_lane", self.handle_seq_param_lane)
        # disp.map("/seq/assign", self.handle_seq_assign)
        # disp.map("/seq/start", self.handle_seq_start)
        # disp.map("/seq/stop", self.handle_seq_stop)
        # disp.map("/seq/reset", self.handle_seq_reset)
        # disp.map("/seq/reset_all", self.handle_seq_reset_all)
        # disp.map("/seq/bpm", self.handle_seq_bpm)
        # disp.map("/seq/gate_len", self.handle_seq_gate_len)
        
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
            # Count specific PortAudio status flags (Senior Dev)
            if status.input_underflow or status.output_underflow:
                self.underflow_count += 1
            if status.input_overflow or status.output_overflow:
                self.overflow_count += 1
            # Only print if verbose
            if os.environ.get('CHRONUS_VERBOSE', '0') == '1':
                print(f"[AUDIO] Status: {status}")
        
        # Handle pending switch at buffer boundary
        if self.pending_switch and self.standby_ready:
            standby_idx = 1 - self.active_idx.value
            
            # Check prime readiness
            prime_ready = self.prime_ready[standby_idx].value == 1
            
            # Check if standby has produced at least one buffer
            standby_ring = self.slot1_audio_ring if self.active_idx.value == 0 else self.slot0_audio_ring
            standby_has_audio = (standby_ring.head.value != standby_ring.tail.value)
            
            if prime_ready and standby_has_audio:
                # Both conditions met - safe to switch
                old_active = self.active_idx.value
                new_active = 1 - old_active
                self.active_idx.value = new_active
                self.pending_switch = False
                self.standby_ready = False  # Reset
                self.target_idx = None
                print(f"[CALLBACK] Switched to slot {new_active} (primed & ready)")
                self.failover_count += 1
                
                # Respawn old active as new standby with router capability
                standby_idx = 1 - new_active
                if standby_idx == 0:
                    self.spawn_slot0_worker(is_standby=True)
                else:
                    self.spawn_slot1_worker(is_standby=True)
            # Note: If not ready, we continue outputting from active slot
            # No early return - always output audio
        
        # Read from active ring using latest-wins with cushion
        active_ring = self.slot0_audio_ring if self.active_idx.value == 0 else self.slot1_audio_ring
        keep_after_read = int(os.environ.get('CHRONUS_KEEP_AFTER_READ', '2'))
        buffer_view = active_ring.read_latest_keep(keep_after_read=keep_after_read)  # Skip stale but keep bigger cushion (reduce popping)
        
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
        
        # Capture buffer for recording if active
        if self.recording:
            self.record_buffer.append(self.last_good.copy())
        
        # Log ring stats periodically with enhanced metrics (Senior Dev)
        if self.total_reads % 1000 == 0:
            # Debug info for frames and active index
            if os.environ.get('CHRONUS_VERBOSE'):
                slot0_occ = self.slot0_audio_ring.get_stats()['occupancy']
                slot1_occ = self.slot1_audio_ring.get_stats()['occupancy']
                print(f"[CALLBACK DEBUG] frames={frames}, active_idx={self.active_idx.value}, ring0_occ={slot0_occ}, ring1_occ={slot1_occ}")
            stats = active_ring.get_stats()
            occupancy = stats['occupancy']
            
            # Count occ==0 events
            if occupancy == 0:
                self.occ_zero_count += 1
            
            none_pct = (self.none_reads / self.total_reads) * 100
            occ_zero_per_1k = self.occ_zero_count  # Reset counter each 1000
            
            # Enhanced stats output
            print(f"[STATS] occ={occupancy}, seq={stats['last_seq']}, none={none_pct:.1f}%, occ0/1k={occ_zero_per_1k}, underflow={self.underflow_count}, overflow={self.overflow_count}")
            
            # Reset occ_zero counter for next 1000 callbacks
            self.occ_zero_count = 0
    
    def run(self):
        """Main supervisor loop"""
        print("Starting AudioSupervisor v3 with router support")
        
        # Start OSC server
        self.start_osc_server()
        
        # Start sequencer manager thread
        # TEMPORARILY DISABLED: Debugging emergency fill issue
        # self.sequencer_manager.start()
        # print("[SEQ] Sequencer manager started")
        
        # Log device and configuration info
        print(f"[CONFIG] Requested: SR={SAMPLE_RATE}Hz, BS={BUFFER_SIZE}, NB={NUM_BUFFERS}")
        
        # Start audio
        stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BUFFER_SIZE,
            channels=NUM_CHANNELS,
            dtype='float32',
            callback=self.audio_callback
        )
        
        with stream:
            # Log actual device settings
            actual_sr = stream.samplerate
            actual_bs = stream.blocksize
            device_info = sd.query_devices(stream.device, 'output')
            print(f"[DEVICE] Actual: SR={actual_sr}Hz, BS={actual_bs}, Device={device_info['name']}")
            
            if actual_sr != SAMPLE_RATE:
                print(f"[WARNING] Sample rate mismatch: requested {SAMPLE_RATE}, got {actual_sr}")
            if actual_bs != BUFFER_SIZE:
                print(f"[WARNING] Blocksize mismatch: requested {BUFFER_SIZE}, got {actual_bs}")
            
            print("Audio started - Press Ctrl+C to stop")
            if self.router_enabled:
                print("Router mode active - use /patch/* commands to build graphs")
            
            try:
                while not self.shutdown.is_set():
                    time.sleep(0.1)
            
            except KeyboardInterrupt:
                print("\nShutting down...")
        
        self.cleanup()
    
    def cleanup(self):
        """Clean shutdown"""
        # Stop recording if active
        if self.recording:
            print("[RECORD] Stopping recording due to shutdown")
            self.stop_recording()
        
        self.shutdown.set()
        
        # Stop sequencer manager
        # TEMPORARILY COMMENTED: Isolating sequencer
        # if hasattr(self, 'sequencer_manager'):
        #     self.sequencer_manager.running = False
        #     self.sequencer_manager.join(timeout=1.0)
        
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