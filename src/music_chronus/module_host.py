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
from collections import OrderedDict, deque
from typing import Dict, Optional, List, Tuple, Any, Deque
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
        module_id: Module identifier ([a-z0-9_]{1,16})
        param: Parameter name ([a-z0-9_]{1,16})
        value: Parameter value
        
    Returns:
        64-byte command packet
    """
    # Validate module_id and param match [a-z0-9_]{1,16}
    # Strict ASCII policy: lowercase letters, digits, underscore only
    if not module_id.replace('_', '').isalnum() or not module_id.replace('_', '').islower():
        raise ValueError(f"Invalid module_id: {module_id} (must be [a-z0-9_]{{1,16}})")
    if not param.replace('_', '').isalnum() or not param.replace('_', '').islower():
        raise ValueError(f"Invalid param: {param} (must be [a-z0-9_]{{1,16}})")
        
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
    
    def __init__(self, sample_rate: int, buffer_size: int, use_router: bool = False):
        """
        Initialize ModuleHost with pre-allocated buffers.
        
        Args:
            sample_rate: System sample rate
            buffer_size: Buffer size in samples
            use_router: Enable PatchRouter support (default False)
        """
        self.sr = sample_rate
        self.buffer_size = buffer_size
        self.use_router = use_router
        
        # Module chain (OrderedDict preserves insertion order)
        self.modules: OrderedDict[str, BaseModule] = OrderedDict()
        
        # Pre-allocate intermediate buffers
        # One extra for input/output flexibility
        self.chain_buffers = [
            np.zeros(buffer_size, dtype=np.float32)
            for _ in range(MAX_MODULES + 1)
        ]
        
        # Command queue (applied at buffer boundaries)
        # Using deque for O(1) popleft() instead of list.pop(0) which is O(n)
        self.pending_commands: Deque[bytes] = deque()
        
        # Statistics
        self.buffers_processed = 0
        self.commands_processed = 0
        
        # Router support (CP2)
        self.router = None
        self.work_buffers: Dict[str, np.ndarray] = {}
        self._processing_order: Optional[List[str]] = None
        self._order_valid = False
        
        # Pre-allocate mixing buffer for router mode
        self.mix_buffer = np.zeros(buffer_size, dtype=np.float32) if use_router else None
        
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
    
    def enable_router(self, router) -> None:
        """
        Enable router-based processing (CP2).
        
        Args:
            router: PatchRouter instance
        """
        if not self.use_router:
            raise ValueError("ModuleHost not configured for router (use_router=False)")
        
        from .patch_router import PatchRouter
        if not isinstance(router, PatchRouter):
            raise ValueError("router must be a PatchRouter instance")
        
        self.router = router
        self._order_valid = False
        
        # Pre-allocate work buffers for all modules in router
        for module_id in router.modules.keys():
            if module_id not in self.work_buffers:
                self.work_buffers[module_id] = np.zeros(self.buffer_size, dtype=np.float32)
    
    def clear_router(self) -> None:
        """Clear router and return to linear chain mode."""
        self.router = None
        self._order_valid = False
        # Keep work_buffers allocated to avoid re-allocation if router re-enabled
    
    def router_add_module(self, module_id: str, module: BaseModule) -> bool:
        """
        Add module to both host and router (CP2 helper).
        
        Args:
            module_id: Module identifier
            module: Module instance
            
        Returns:
            True if successful
        """
        if not self.router:
            return False
        
        # Add to host's module collection
        if not self.add_module(module_id, module):
            return False
        
        # Add to router
        if not self.router.add_module(module_id, module):
            self.remove_module(module_id)  # Rollback
            return False
        
        # Pre-allocate work buffer
        if module_id not in self.work_buffers:
            self.work_buffers[module_id] = np.zeros(self.buffer_size, dtype=np.float32)
        
        self._order_valid = False
        return True
    
    def router_connect(self, source_id: str, dest_id: str) -> bool:
        """Connect modules in router (CP2 helper)."""
        if not self.router:
            return False
        success = self.router.connect(source_id, dest_id)
        if success:
            self._order_valid = False
        return success
    
    def router_disconnect(self, source_id: str, dest_id: str) -> bool:
        """Disconnect modules in router (CP2 helper)."""
        if not self.router:
            return False
        success = self.router.disconnect(source_id, dest_id)
        if success:
            self._order_valid = False
        return success
        
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
            cmd_bytes = self.pending_commands.popleft()  # O(1) with deque
            
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
        
        # Router path (CP2)
        if self.use_router and self.router:
            return self._process_router_chain(input_buffer)
        
        # Linear chain path (original)
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
    
    def _process_router_chain(self, input_buffer: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Process modules using router's DAG topology (CP2).
        
        CRITICAL: This must be allocation-free!
        
        Args:
            input_buffer: Optional input
            
        Returns:
            Output buffer (for CP2, assumes single sink)
        """
        # Get/cache processing order
        if not self._order_valid:
            self._processing_order = self.router.get_processing_order()
            self._order_valid = True
        
        if not self._processing_order:
            # Empty graph or error
            self.chain_buffers[0].fill(0.0)
            self.buffers_processed += 1
            return self.chain_buffers[0]
        
        # Process each module in topological order
        last_module_id = None
        for module_id in self._processing_order:
            module = self.modules.get(module_id)
            if not module or not module.active:
                continue
            
            # Prepare module (boundary updates)
            if hasattr(module, 'prepare'):
                module.prepare()
            
            # Get input connections
            input_modules = self.router.get_module_inputs(module_id)
            
            # Mix inputs into module's input buffer
            # Using mix_buffer as temporary input
            if input_modules:
                # Start with zeros
                self.mix_buffer.fill(0.0)
                
                # Mix all inputs
                for source_id in input_modules:
                    if source_id in self.work_buffers:
                        # Add source output to mix (in-place)
                        np.add(self.mix_buffer, self.work_buffers[source_id], out=self.mix_buffer)
            else:
                # No inputs - use external input or silence
                if input_buffer is not None and module_id == self._processing_order[0]:
                    # First module gets external input
                    np.copyto(self.mix_buffer, input_buffer, casting='no')
                else:
                    self.mix_buffer.fill(0.0)
            
            # Process module
            module.process_buffer(self.mix_buffer, self.work_buffers[module_id])
            
            # Copy output to edge buffers for downstream modules
            output_modules = self.router.get_module_outputs(module_id)
            for dest_id in output_modules:
                edge_buffer = self.router.get_edge_buffer(module_id, dest_id)
                if edge_buffer is not None:
                    np.copyto(edge_buffer, self.work_buffers[module_id], casting='no')
            
            last_module_id = module_id
        
        self.buffers_processed += 1
        
        # Return last module's output (single sink assumption for CP2)
        if last_module_id and last_module_id in self.work_buffers:
            return self.work_buffers[last_module_id]
        else:
            return self.chain_buffers[0]  # Fallback
        
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