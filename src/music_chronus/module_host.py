"""
ModuleHost - Orchestrates DSP module chain
Phase 2: Zero-allocation module management

Responsibilities:
1. Manage ordered chain of modules
2. Pre-allocate all intermediate buffers
3. Process commands at buffer boundaries
4. Route audio through module chain
5. Maintain failover determinism
"""

import numpy as np
import struct
from collections import OrderedDict
from typing import Dict, Optional, List, Tuple, Any
from .modules.base import BaseModule


# Maximum modules in chain (pre-allocate buffers)
MAX_MODULES = 8

# Command Protocol v2 constants
CMD_OP_SET = 0
CMD_OP_GATE = 1
CMD_OP_PATCH = 2

CMD_TYPE_FLOAT = 0
CMD_TYPE_INT = 1
CMD_TYPE_BOOL = 2


def pack_command_v2(op: int, dtype: int, module_id: str, param: str, value: float) -> bytes:
    """
    Pack command into 64-byte struct for Command Protocol v2.
    
    Args:
        op: Operation (0=set, 1=gate, 2=patch)
        dtype: Data type (0=float, 1=int, 2=bool)
        module_id: Module identifier (ASCII, max 16 chars)
        param: Parameter name (ASCII, max 16 chars)
        value: Parameter value
        
    Returns:
        64-byte command packet
    """
    # Validate module_id and param are ASCII
    if not module_id.replace('_', '').replace('-', '').isalnum():
        raise ValueError(f"Invalid module_id: {module_id}")
    if not param.replace('_', '').replace('-', '').isalnum():
        raise ValueError(f"Invalid param: {param}")
        
    # Create 64-byte buffer
    cmd = bytearray(64)
    
    # Pack header
    cmd[0] = op
    cmd[1] = dtype
    # bytes 2-15 are reserved (stay zero)
    
    # Pack strings (ASCII only, null-padded)
    module_bytes = module_id.encode('ascii')[:16].ljust(16, b'\0')
    param_bytes = param.encode('ascii')[:16].ljust(16, b'\0')
    
    cmd[16:32] = module_bytes
    cmd[32:48] = param_bytes
    
    # Pack value based on type
    if dtype == CMD_TYPE_FLOAT:
        struct.pack_into('d', cmd, 48, float(value))
    elif dtype == CMD_TYPE_INT:
        struct.pack_into('q', cmd, 48, int(value))
    elif dtype == CMD_TYPE_BOOL:
        struct.pack_into('q', cmd, 48, 1 if value else 0)
    else:
        raise ValueError(f"Invalid dtype: {dtype}")
        
    return bytes(cmd)


def unpack_command_v2(cmd_bytes: bytes) -> Tuple[int, int, str, str, Any]:
    """
    Unpack 64-byte command from Command Protocol v2.
    
    Args:
        cmd_bytes: 64-byte command packet
        
    Returns:
        Tuple of (op, dtype, module_id, param, value)
    """
    if len(cmd_bytes) != 64:
        raise ValueError(f"Command must be 64 bytes, got {len(cmd_bytes)}")
        
    op = cmd_bytes[0]
    dtype = cmd_bytes[1]
    
    # Extract strings (strip null padding)
    module_id = cmd_bytes[16:32].rstrip(b'\0').decode('ascii')
    param = cmd_bytes[32:48].rstrip(b'\0').decode('ascii')
    
    # Extract value based on type
    if dtype == CMD_TYPE_FLOAT:
        value = struct.unpack_from('d', cmd_bytes, 48)[0]
    elif dtype == CMD_TYPE_INT:
        value = struct.unpack_from('q', cmd_bytes, 48)[0]
    elif dtype == CMD_TYPE_BOOL:
        value = struct.unpack_from('q', cmd_bytes, 48)[0] != 0
    else:
        # Unknown type, return raw bytes
        value = cmd_bytes[48:56]
        
    return op, dtype, module_id, param, value


class ModuleHost:
    """
    Manages a chain of DSP modules with zero-allocation processing.
    
    Pre-allocates all buffers and processes modules in sequence.
    Commands are applied at buffer boundaries for click-free operation.
    """
    
    def __init__(self, sample_rate: int, buffer_size: int):
        """
        Initialize ModuleHost with pre-allocated buffers.
        
        Args:
            sample_rate: System sample rate
            buffer_size: Buffer size in samples
        """
        self.sr = sample_rate
        self.buffer_size = buffer_size
        
        # Module chain (OrderedDict preserves insertion order)
        self.modules: OrderedDict[str, BaseModule] = OrderedDict()
        
        # Pre-allocate intermediate buffers
        # One extra for input/output flexibility
        self.chain_buffers = [
            np.zeros(buffer_size, dtype=np.float32)
            for _ in range(MAX_MODULES + 1)
        ]
        
        # Command queue (applied at buffer boundaries)
        self.pending_commands: List[bytes] = []
        
        # Statistics
        self.buffers_processed = 0
        self.commands_processed = 0
        
    def add_module(self, module_id: str, module: BaseModule) -> bool:
        """
        Add a module to the chain.
        
        Args:
            module_id: Unique identifier for the module
            module: Module instance
            
        Returns:
            True if added successfully
        """
        if len(self.modules) >= MAX_MODULES:
            return False
            
        if module_id in self.modules:
            return False
            
        self.modules[module_id] = module
        return True
        
    def remove_module(self, module_id: str) -> bool:
        """
        Remove a module from the chain.
        
        Args:
            module_id: Module identifier
            
        Returns:
            True if removed successfully
        """
        if module_id in self.modules:
            del self.modules[module_id]
            return True
        return False
        
    def get_module(self, module_id: str) -> Optional[BaseModule]:
        """
        Get a module by ID.
        
        Args:
            module_id: Module identifier
            
        Returns:
            Module instance or None
        """
        return self.modules.get(module_id)
        
    def queue_command(self, cmd_bytes: bytes) -> None:
        """
        Queue a command for processing at next buffer boundary.
        
        Args:
            cmd_bytes: 64-byte command packet
        """
        if len(cmd_bytes) == 64:
            self.pending_commands.append(cmd_bytes)
            
    def process_commands(self) -> None:
        """
        Process all pending commands.
        Called at buffer boundary for click-free parameter changes.
        """
        while self.pending_commands:
            cmd_bytes = self.pending_commands.pop(0)
            
            try:
                op, dtype, module_id, param, value = unpack_command_v2(cmd_bytes)
                
                if op == CMD_OP_SET:
                    # Set parameter
                    module = self.modules.get(module_id)
                    if module:
                        module.set_param(param, value, immediate=False)
                        self.commands_processed += 1
                        
                elif op == CMD_OP_GATE:
                    # Gate control (for ADSR etc)
                    module = self.modules.get(module_id)
                    if module and hasattr(module, 'set_gate'):
                        module.set_gate(bool(value))
                        self.commands_processed += 1
                        
                elif op == CMD_OP_PATCH:
                    # Patching not implemented in MVP
                    pass
                    
            except Exception as e:
                # Invalid command, skip
                # In production, might want to log this
                pass
                
    def process_chain(self, input_buffer: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Process the entire module chain.
        
        CRITICAL: This must be allocation-free!
        
        Args:
            input_buffer: Optional input (for effects chain)
            
        Returns:
            Final output buffer (view into pre-allocated buffer)
        """
        # Process commands at buffer boundary
        self.process_commands()
        
        # Start with input or silence
        if input_buffer is not None:
            np.copyto(self.chain_buffers[0], input_buffer, casting='no')
        else:
            self.chain_buffers[0].fill(0.0)
            
        # Process through chain
        current_buf = self.chain_buffers[0]
        
        for i, (module_id, module) in enumerate(self.modules.items()):
            if not module.active:
                continue
                
            # Get next buffer (cycling through pre-allocated)
            next_buf = self.chain_buffers[(i + 1) % len(self.chain_buffers)]
            
            # Process module
            module.process_buffer(current_buf, next_buf)
            
            # Move to next
            current_buf = next_buf
            
        self.buffers_processed += 1
        return current_buf
        
    def reset(self) -> None:
        """
        Reset all modules to initial state.
        """
        for module in self.modules.values():
            module.prepare()
            
        # Clear buffers
        for buf in self.chain_buffers:
            buf.fill(0.0)
            
        # Clear command queue
        self.pending_commands.clear()
        
        # Reset stats
        self.buffers_processed = 0
        self.commands_processed = 0
        
    def get_stats(self) -> Dict[str, Any]:
        """
        Get host statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            'modules': len(self.modules),
            'module_ids': list(self.modules.keys()),
            'buffers_processed': self.buffers_processed,
            'commands_processed': self.commands_processed,
            'pending_commands': len(self.pending_commands)
        }
        
    def __repr__(self) -> str:
        """String representation."""
        chain = ' → '.join(self.modules.keys()) if self.modules else '(empty)'
        return f"ModuleHost[{chain}]"