"""
Sequencer implementation for Music Chronus.
Buffer-quantized timing with atomic pattern updates.
Runs in supervisor thread for RT-safety.
"""

import time
import threading
import queue
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

# Import command packing functions
try:
    from .module_host import pack_command_v2, CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL
except ImportError:
    from music_chronus.module_host import pack_command_v2, CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL


# Import pattern parsing functions from tests (we'll move these here)
def parse_pattern(pattern: str) -> Tuple[List[bool], List[int]]:
    """
    Parse pattern string into gates and velocities.
    'x' = gate with velocity 64
    'X' = gate with velocity 127 (accent)  
    '.' = no gate
    """
    gates = []
    velocities = []
    
    for char in pattern:
        if char == 'X':
            gates.append(True)
            velocities.append(127)
        elif char == 'x':
            gates.append(True)
            velocities.append(64)
        elif char == '.':
            gates.append(False)
            velocities.append(0)
        # Ignore other characters (spaces, etc)
    
    return gates, velocities


def parse_param_lane(values_str: str, steps: int) -> List[float]:
    """
    Parse CSV string or space-separated values into parameter lane.
    Truncate or pad with 0.0 to match steps.
    """
    if not values_str:
        return [0.0] * steps
    
    # Handle both CSV and space-separated
    if ',' in values_str:
        parts = values_str.split(',')
    else:
        parts = values_str.split()
    
    # Convert to floats
    values = []
    for part in parts:
        part = part.strip()
        if part:
            try:
                values.append(float(part))
            except ValueError:
                values.append(0.0)
    
    # Truncate or pad to match steps
    if len(values) > steps:
        return values[:steps]
    else:
        return values + [0.0] * (steps - len(values))


@dataclass
class SequencerState:
    """State for a single sequencer."""
    seq_id: str
    bpm: float = 120.0
    division: int = 4  # 4 = quarter note, 16 = sixteenth
    steps: int = 16
    pattern: str = "x..............."  # Default kick on 1
    gates: List[bool] = field(default_factory=list)
    velocities: List[int] = field(default_factory=list)
    param_lanes: Dict[str, List[float]] = field(default_factory=dict)
    current_step: int = 0
    buffers_until_next_step: int = 0
    gate_length: float = 0.5  # Fraction of step
    is_playing: bool = False
    
    # Assignment targets
    gate_target_module: Optional[str] = None
    gate_target_param: Optional[str] = "gate"  # Usually 'gate'
    param_targets: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # param -> (module, param)
    
    # Pending gate offs (buffer_index -> gate_off needed)
    pending_gate_offs: Dict[int, bool] = field(default_factory=dict)
    
    def __post_init__(self):
        """Parse pattern after initialization."""
        if self.pattern and not self.gates:
            self.gates, self.velocities = parse_pattern(self.pattern)
            # Ensure length matches steps
            if len(self.gates) < self.steps:
                self.gates.extend([False] * (self.steps - len(self.gates)))
                self.velocities.extend([0] * (self.steps - len(self.velocities)))
            elif len(self.gates) > self.steps:
                self.gates = self.gates[:self.steps]
                self.velocities = self.velocities[:self.steps]
    
    def calculate_buffers_per_step(self, buffer_period: float) -> int:
        """Calculate buffers per step based on current BPM and division."""
        beat_duration = 60.0 / self.bpm  # Duration of one beat
        step_duration = beat_duration / (self.division / 4)  # Adjust for division
        return max(1, round(step_duration / buffer_period))
    
    def get_gate_buffers(self, buffers_per_step: int) -> int:
        """Calculate how many buffers the gate should stay on."""
        return max(1, round(self.gate_length * buffers_per_step))


class SequencerManager(threading.Thread):
    """
    Manages all sequencers, runs in supervisor thread.
    Emits commands via CommandRing to both slots.
    """
    
    def __init__(self, slot0_command_ring, slot1_command_ring, 
                 sample_rate: int = 44100, buffer_size: int = 512):
        """Initialize sequencer manager."""
        super().__init__(daemon=True)
        
        # Command rings for both slots
        self.slot0_command_ring = slot0_command_ring
        self.slot1_command_ring = slot1_command_ring
        
        # Audio timing
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.buffer_period = buffer_size / sample_rate
        
        # Sequencer registry
        self.sequencers: Dict[str, SequencerState] = {}
        self.update_queues: Dict[str, queue.Queue] = {}
        
        # Master timing
        self.epoch_time = time.perf_counter()
        self.buffer_counter = 0
        self.last_tick_time = self.epoch_time
        
        # Control
        self.running = True
        self.verbose = int(os.environ.get('CHRONUS_VERBOSE', '0')) > 0
        
    def create_sequencer(self, seq_id: str) -> bool:
        """Create a new sequencer with defaults."""
        if seq_id in self.sequencers:
            return False
        
        seq = SequencerState(seq_id=seq_id)
        
        # Initialize timing attributes for epoch-based scheduler
        seq.next_step_buffer = getattr(self, 'global_next_buffer', 0)
        seq.gate_off_buffer = None
        seq.buffers_per_step = seq.calculate_buffers_per_step(self.buffer_period)
        seq.pending_config = None
        
        self.sequencers[seq_id] = seq
        self.update_queues[seq_id] = queue.Queue(maxsize=100)
        
        if self.verbose:
            print(f"[SEQ] Created sequencer '{seq_id}'")
        return True
    
    def queue_update(self, seq_id: str, update_type: str, data: any):
        """Queue an update for atomic application."""
        if seq_id not in self.update_queues:
            return False
        
        try:
            self.update_queues[seq_id].put_nowait((update_type, data))
            return True
        except queue.Full:
            return False
    
    def process_updates(self, seq: SequencerState):
        """Drain update queue and apply atomically."""
        if seq.seq_id not in self.update_queues:
            return
        
        updates = self.update_queues[seq.seq_id]
        
        # Drain all pending updates
        while not updates.empty():
            try:
                update_type, data = updates.get_nowait()
                
                if update_type == 'config':
                    # Update BPM, steps, division
                    bpm, steps, division = data
                    seq.bpm = bpm
                    seq.steps = steps
                    seq.division = division
                    # Recalculate timing on next tick
                    
                elif update_type == 'pattern':
                    # Atomic pattern swap
                    pattern_str = data
                    gates, velocities = parse_pattern(pattern_str)
                    # Pad or truncate
                    if len(gates) < seq.steps:
                        gates.extend([False] * (seq.steps - len(gates)))
                        velocities.extend([0] * (seq.steps - len(velocities)))
                    elif len(gates) > seq.steps:
                        gates = gates[:seq.steps]
                        velocities = velocities[:seq.steps]
                    # Atomic swap
                    seq.gates = gates
                    seq.velocities = velocities
                    seq.pattern = pattern_str
                    
                elif update_type == 'param_lane':
                    # Update parameter lane
                    param_name, values = data
                    seq.param_lanes[param_name] = parse_param_lane(values, seq.steps)
                    
                elif update_type == 'assign_gate':
                    # Assign gate target
                    seq.gate_target_module = data
                    seq.gate_target_param = 'gate'
                    
                elif update_type == 'assign_param':
                    # Assign parameter target
                    param_name, module_id, module_param = data
                    seq.param_targets[param_name] = (module_id, module_param)
                    
                elif update_type == 'bpm':
                    # Queue BPM change for next boundary
                    if not hasattr(seq, 'pending_config'):
                        seq.pending_config = {}
                    if seq.pending_config is None:
                        seq.pending_config = {}
                    seq.pending_config['bpm'] = data
                    
                elif update_type == 'gate_length':
                    seq.gate_length = max(0.01, min(1.0, data))
                    
                elif update_type == 'start':
                    seq.is_playing = True
                    # Initialize timing state for epoch-based scheduler
                    if not hasattr(seq, 'next_step_buffer'):
                        seq.next_step_buffer = 0
                    if not hasattr(seq, 'buffers_per_step'):
                        seq.buffers_per_step = seq.calculate_buffers_per_step(self.buffer_period)
                    # Start from next available buffer
                    seq.next_step_buffer = getattr(self, 'global_next_buffer', 0)
                    seq.gate_off_buffer = None
                    seq.current_step = 0
                    if self.verbose:
                        print(f"[SEQ] Starting sequencer '{seq.seq_id}' at buffer {seq.next_step_buffer}")
                    
                elif update_type == 'stop':
                    seq.is_playing = False
                    
                elif update_type == 'reset':
                    seq.current_step = 0
                    # Reset to start from next global buffer
                    seq.next_step_buffer = getattr(self, 'global_next_buffer', 0)
                    seq.gate_off_buffer = None
                    seq.buffers_per_step = seq.calculate_buffers_per_step(self.buffer_period)
                    
            except queue.Empty:
                break
    
    def emit_command(self, module_id: str, param: str, value: float, is_gate: bool = False):
        """Emit command to both slots via CommandRing."""
        # Pack command based on type
        # Note: pack_command_v2 signature is (op, dtype, module_id, param, value)
        if is_gate:
            cmd_bytes = pack_command_v2(
                CMD_OP_GATE,
                CMD_TYPE_BOOL,
                module_id,
                'gate',
                1 if value > 0 else 0
            )
        else:
            cmd_bytes = pack_command_v2(
                CMD_OP_SET,
                CMD_TYPE_FLOAT,
                module_id,
                param,
                value
            )
        
        # Write to both slots
        if self.slot0_command_ring:
            self.slot0_command_ring.write(cmd_bytes)
        if self.slot1_command_ring:
            self.slot1_command_ring.write(cmd_bytes)
    
    def process_step(self, seq: SequencerState, buffer_index: int):
        """Process one sequencer step."""
        # Emit gate if there's one at this step
        if seq.gates[seq.current_step] and seq.gate_target_module:
            # Gate ON
            self.emit_command(seq.gate_target_module, 'gate', 1.0, is_gate=True)
            
            # Schedule gate OFF
            buffers_per_step = seq.calculate_buffers_per_step(self.buffer_period)
            gate_buffers = seq.get_gate_buffers(buffers_per_step)
            gate_off_buffer = buffer_index + gate_buffers
            seq.pending_gate_offs[gate_off_buffer] = True
            
            if self.verbose:
                print(f"[SEQ] {seq.seq_id} step {seq.current_step}: gate ON, off at buffer {gate_off_buffer}")
        
        # Emit parameter values for this step
        for param_name, values in seq.param_lanes.items():
            if param_name in seq.param_targets and seq.current_step < len(values):
                value = values[seq.current_step]
                if value > 0:  # Only emit non-zero values
                    module_id, module_param = seq.param_targets[param_name]
                    self.emit_command(module_id, module_param, value, is_gate=False)
        
        # Advance to next step
        seq.current_step = (seq.current_step + 1) % seq.steps
    
    def process_gate_offs(self, seq: SequencerState, buffer_index: int):
        """Process any pending gate offs for this buffer."""
        if buffer_index in seq.pending_gate_offs:
            if seq.gate_target_module:
                self.emit_command(seq.gate_target_module, 'gate', 0.0, is_gate=True)
                if self.verbose:
                    print(f"[SEQ] {seq.seq_id}: gate OFF at buffer {buffer_index}")
            del seq.pending_gate_offs[buffer_index]
        
        # Clean up old gate offs that we've passed
        to_remove = [b for b in seq.pending_gate_offs if b < buffer_index]
        for b in to_remove:
            del seq.pending_gate_offs[b]
    
    def run(self):
        """Main sequencer thread loop with epoch-based timing."""
        print("[SEQ] SequencerManager thread started")
        
        # Initialize timing state
        self.epoch_time = time.perf_counter()
        # Start from "now" to avoid initial catch-up
        self.global_next_buffer = 0  # Will be immediately updated in the loop
        
        # Initialize per-sequencer timing state
        # These will be stored as attributes on each SequencerState
        for seq in self.sequencers.values():
            seq.next_step_buffer = 0
            seq.gate_off_buffer = None
            seq.buffers_per_step = seq.calculate_buffers_per_step(self.buffer_period)
            seq.pending_config = None  # For tempo changes at boundaries
        
        while self.running:
            now = time.perf_counter()
            
            # Calculate current buffer index from epoch
            current_buffer = int((now - self.epoch_time) / self.buffer_period)
            
            # Process events with while loop until caught up
            # Safety: Limit catch-up to prevent runaway loops
            max_catchup = 100  # Maximum buffers to process in one iteration
            catchup_count = 0
            
            while self.global_next_buffer <= current_buffer and catchup_count < max_catchup:
                # Process each sequencer
                for seq in self.sequencers.values():
                    # Apply pending updates from queue
                    self.process_updates(seq)
                    
                    if not seq.is_playing:
                        continue
                    
                    # Check if time to emit gate-off
                    if seq.gate_off_buffer is not None and self.global_next_buffer == seq.gate_off_buffer:
                        # Emit gate-off command
                        if seq.gate_target_module:
                            cmd = pack_command_v2(
                                op=CMD_OP_GATE,
                                dtype=CMD_TYPE_BOOL,
                                module_id=seq.gate_target_module,
                                param='gate',
                                value=0.0
                            )
                            self.slot0_command_ring.write(cmd)
                            self.slot1_command_ring.write(cmd)
                        # Clear gate-off buffer
                        seq.gate_off_buffer = None
                    
                    # Check if time to emit next step
                    if self.global_next_buffer == seq.next_step_buffer:
                        if self.verbose:
                            print(f"[SEQ] Processing step {seq.current_step} for '{seq.seq_id}' at buffer {self.global_next_buffer}")
                        
                        # Apply pending config changes at boundary if any
                        if hasattr(seq, 'pending_config') and seq.pending_config:
                            config = seq.pending_config
                            seq.bpm = config.get('bpm', seq.bpm)
                            seq.division = config.get('division', seq.division)
                            seq.pending_config = None
                            # Recompute buffers_per_step from this boundary
                            seq.buffers_per_step = seq.calculate_buffers_per_step(self.buffer_period)
                        
                        # Process current step
                        self.process_step(seq, self.global_next_buffer)
                        
                        # Calculate gate-off buffer if gate was triggered
                        if seq.current_step < len(seq.gates) and seq.gates[seq.current_step]:
                            gate_buffers = seq.get_gate_buffers(seq.buffers_per_step)
                            seq.gate_off_buffer = seq.next_step_buffer + gate_buffers
                        
                        # Advance to next step
                        seq.current_step = (seq.current_step + 1) % seq.steps
                        
                        # Set next step buffer (absolute position)
                        seq.next_step_buffer += seq.buffers_per_step
                
                # Increment global buffer counter
                self.global_next_buffer += 1
                catchup_count += 1
            
            # If we hit the catch-up limit, jump to current
            if catchup_count >= max_catchup:
                if self.verbose:
                    print(f"[SEQ] Hit catch-up limit, jumping from buffer {self.global_next_buffer} to {current_buffer}")
                self.global_next_buffer = current_buffer + 1
            
            # Calculate sleep time to next buffer
            time_to_next = ((self.global_next_buffer * self.buffer_period) - (now - self.epoch_time))
            sleep_time = max(0.001, min(time_to_next, self.buffer_period * 0.5))  # Minimum 1ms sleep
            
            # Always sleep to prevent CPU spinning
            time.sleep(sleep_time)
        
        print("[SEQ] SequencerManager thread stopped")