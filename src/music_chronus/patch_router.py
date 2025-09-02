"""
PatchRouter - DAG-based signal routing for modular synthesis
Phase 3: Module Framework

Provides:
- Directed Acyclic Graph for signal flow
- Kahn's algorithm for topological sorting  
- Cycle detection to prevent feedback loops
- Pre-allocated edge buffers for zero-copy routing
"""

import numpy as np
from typing import Dict, List, Set, Tuple, Optional
from collections import deque, defaultdict
from .modules.base_v2 import BaseModuleV2


class PatchRouter:
    """
    Manages signal routing between modules using a DAG.
    
    Ensures:
    - No cycles (feedback loops)
    - Correct processing order
    - Zero-allocation audio routing
    - Pre-allocated edge buffers
    """
    
    # Maximum limits for pre-allocation
    MAX_MODULES = 16
    MAX_EDGES = 32
    
    def __init__(self, buffer_size: int = 256):
        """
        Initialize the patch router.
        
        Args:
            buffer_size: Audio buffer size in samples
        """
        self.buffer_size = buffer_size
        
        # Graph structure
        self.modules: Dict[str, BaseModuleV2] = {}
        self.adjacency_list: Dict[str, Set[str]] = defaultdict(set)
        self.in_degree: Dict[str, int] = defaultdict(int)
        
        # Pre-allocated edge buffers (32 max connections)
        self.edge_buffers = np.zeros((self.MAX_EDGES, buffer_size), dtype=np.float32)
        self.edge_buffer_map: Dict[Tuple[str, str], int] = {}
        self.next_buffer_idx = 0
        
        # Processing order cache
        self._processing_order: Optional[List[str]] = None
        self._order_valid = False
    
    def add_module(self, module_id: str, module: BaseModuleV2) -> bool:
        """
        Add a module to the patch.
        
        Args:
            module_id: Unique identifier for the module
            module: Module instance
            
        Returns:
            True if added successfully, False if at capacity
        """
        if len(self.modules) >= self.MAX_MODULES:
            print(f"[Router] Cannot add module '{module_id}' - at max capacity ({self.MAX_MODULES})")
            return False
        
        if module_id in self.modules:
            print(f"[Router] Module '{module_id}' already exists")
            return False
        
        self.modules[module_id] = module
        self.adjacency_list[module_id] = set()
        self.in_degree[module_id] = 0
        self._order_valid = False
        
        print(f"[Router] Added module: {module_id}")
        return True
    
    def remove_module(self, module_id: str) -> bool:
        """
        Remove a module and all its connections.
        
        Args:
            module_id: Module to remove
            
        Returns:
            True if removed, False if not found
        """
        if module_id not in self.modules:
            return False
        
        # Remove all edges involving this module
        for source in list(self.adjacency_list.keys()):
            if module_id in self.adjacency_list[source]:
                self.disconnect(source, module_id)
        
        # Remove module as source
        if module_id in self.adjacency_list:
            for dest in list(self.adjacency_list[module_id]):
                self.disconnect(module_id, dest)
        
        # Clean up module
        del self.modules[module_id]
        if module_id in self.adjacency_list:
            del self.adjacency_list[module_id]
        if module_id in self.in_degree:
            del self.in_degree[module_id]
        
        self._order_valid = False
        print(f"[Router] Removed module: {module_id}")
        return True
    
    def connect(self, source_id: str, dest_id: str) -> bool:
        """
        Create a connection between two modules.
        
        Args:
            source_id: Source module ID
            dest_id: Destination module ID
            
        Returns:
            True if connected, False if invalid or would create cycle
        """
        # Validate modules exist
        if source_id not in self.modules or dest_id not in self.modules:
            print(f"[Router] Cannot connect - module not found")
            return False
        
        # Check if already connected
        if dest_id in self.adjacency_list[source_id]:
            print(f"[Router] Already connected: {source_id} -> {dest_id}")
            return True
        
        # Check edge buffer capacity
        if self.next_buffer_idx >= self.MAX_EDGES:
            print(f"[Router] Cannot connect - at max edge capacity ({self.MAX_EDGES})")
            return False
        
        # Temporarily add edge to check for cycles
        self.adjacency_list[source_id].add(dest_id)
        self.in_degree[dest_id] += 1
        
        # Check for cycles using DFS
        if self._has_cycle():
            # Revert the edge
            self.adjacency_list[source_id].remove(dest_id)
            self.in_degree[dest_id] -= 1
            print(f"[Router] Cannot connect {source_id} -> {dest_id} - would create cycle")
            return False
        
        # Allocate edge buffer
        edge_key = (source_id, dest_id)
        self.edge_buffer_map[edge_key] = self.next_buffer_idx
        self.next_buffer_idx += 1
        
        self._order_valid = False
        print(f"[Router] Connected: {source_id} -> {dest_id}")
        return True
    
    def disconnect(self, source_id: str, dest_id: str) -> bool:
        """
        Remove a connection between two modules.
        
        Args:
            source_id: Source module ID
            dest_id: Destination module ID
            
        Returns:
            True if disconnected, False if not connected
        """
        if source_id not in self.adjacency_list:
            return False
        
        if dest_id not in self.adjacency_list[source_id]:
            return False
        
        # Remove edge
        self.adjacency_list[source_id].remove(dest_id)
        self.in_degree[dest_id] -= 1
        
        # Free edge buffer
        edge_key = (source_id, dest_id)
        if edge_key in self.edge_buffer_map:
            # Note: In production, we'd recycle this buffer index
            del self.edge_buffer_map[edge_key]
        
        self._order_valid = False
        print(f"[Router] Disconnected: {source_id} -> {dest_id}")
        return True
    
    def get_processing_order(self) -> List[str]:
        """
        Get the topological processing order using Kahn's algorithm.
        
        Returns:
            List of module IDs in processing order
        """
        if self._order_valid and self._processing_order is not None:
            return self._processing_order
        
        # Kahn's algorithm for topological sort
        in_degree_copy = self.in_degree.copy()
        queue = deque()
        
        # Find all nodes with no incoming edges
        for module_id in self.modules:
            if in_degree_copy[module_id] == 0:
                queue.append(module_id)
        
        processing_order = []
        
        while queue:
            current = queue.popleft()
            processing_order.append(current)
            
            # Remove edges from current node
            for neighbor in self.adjacency_list[current]:
                in_degree_copy[neighbor] -= 1
                if in_degree_copy[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check if all nodes were processed (no cycles)
        if len(processing_order) != len(self.modules):
            print("[Router] Warning: Graph has cycles!")
            return []
        
        self._processing_order = processing_order
        self._order_valid = True
        return processing_order
    
    def _has_cycle(self) -> bool:
        """
        Check if the graph has a cycle using DFS.
        
        Returns:
            True if cycle detected, False otherwise
        """
        # Color-based DFS cycle detection
        # White (0): Not visited, Gray (1): In progress, Black (2): Completed
        colors = {node: 0 for node in self.modules}
        
        def dfs(node: str) -> bool:
            colors[node] = 1  # Mark as in progress
            
            for neighbor in self.adjacency_list[node]:
                if colors[neighbor] == 1:  # Back edge found
                    return True
                if colors[neighbor] == 0 and dfs(neighbor):
                    return True
            
            colors[node] = 2  # Mark as completed
            return False
        
        # Check from all unvisited nodes
        for node in self.modules:
            if colors[node] == 0:
                if dfs(node):
                    return True
        
        return False
    
    def validate_graph(self) -> bool:
        """
        Validate the graph structure.
        
        Returns:
            True if valid (no cycles), False otherwise
        """
        return not self._has_cycle()
    
    def get_edge_buffer(self, source_id: str, dest_id: str) -> Optional[np.ndarray]:
        """
        Get the pre-allocated buffer for an edge.
        
        Args:
            source_id: Source module ID
            dest_id: Destination module ID
            
        Returns:
            Buffer array or None if edge doesn't exist
        """
        edge_key = (source_id, dest_id)
        if edge_key not in self.edge_buffer_map:
            return None
        
        buffer_idx = self.edge_buffer_map[edge_key]
        return self.edge_buffers[buffer_idx]
    
    def clear(self):
        """Clear all modules and connections"""
        self.modules.clear()
        self.adjacency_list.clear()
        self.in_degree.clear()
        self.edge_buffer_map.clear()
        self.next_buffer_idx = 0
        self._processing_order = None
        self._order_valid = False
        
        # Zero out buffers
        self.edge_buffers.fill(0.0)
    
    def get_connections(self) -> List[Tuple[str, str]]:
        """
        Get all connections as a list of tuples.
        
        Returns:
            List of (source, dest) tuples
        """
        connections = []
        for source, dests in self.adjacency_list.items():
            for dest in dests:
                connections.append((source, dest))
        return connections
    
    def get_module_inputs(self, module_id: str) -> List[str]:
        """
        Get all modules that feed into the given module.
        
        Args:
            module_id: Target module
            
        Returns:
            List of source module IDs
        """
        inputs = []
        for source, dests in self.adjacency_list.items():
            if module_id in dests:
                inputs.append(source)
        return inputs
    
    def get_module_outputs(self, module_id: str) -> List[str]:
        """
        Get all modules that receive from the given module.
        
        Args:
            module_id: Source module
            
        Returns:
            List of destination module IDs
        """
        if module_id not in self.adjacency_list:
            return []
        return list(self.adjacency_list[module_id])
    
    def to_dict(self) -> dict:
        """
        Serialize router state to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            "modules": list(self.modules.keys()),
            "connections": self.get_connections(),
            "processing_order": self.get_processing_order() if self.modules else None
        }
    
    def __repr__(self) -> str:
        """String representation"""
        return (f"PatchRouter(modules={len(self.modules)}, "
                f"connections={sum(len(d) for d in self.adjacency_list.values())})")


# Example usage and testing
if __name__ == "__main__":
    # Create router
    router = PatchRouter(buffer_size=256)
    
    # Create mock modules for testing
    class MockModule(BaseModuleV2):
        def get_param_specs(self):
            return {}
        def initialize(self):
            pass
        def process_buffer(self, input_buffer, output_buffer):
            pass
    
    # Add modules
    osc1 = MockModule(44100, 256)
    filt1 = MockModule(44100, 256)
    env1 = MockModule(44100, 256)
    
    router.add_module("osc1", osc1)
    router.add_module("filt1", filt1)
    router.add_module("env1", env1)
    
    # Create patch
    router.connect("osc1", "filt1")
    router.connect("filt1", "env1")
    
    # Get processing order
    order = router.get_processing_order()
    print(f"Processing order: {order}")
    
    # Try to create a cycle (should fail)
    success = router.connect("env1", "osc1")
    print(f"Cycle connection attempt: {success}")
    
    # Validate
    print(f"Graph valid: {router.validate_graph()}")
    print(f"Router state: {router.to_dict()}")