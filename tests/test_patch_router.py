"""
Test PatchRouter DAG functionality
Phase 3: Module Framework

Tests topological sorting, cycle detection, and edge buffer management.
"""

import pytest
import numpy as np
from src.music_chronus.patch_router import PatchRouter
from src.music_chronus.modules.base_v2 import BaseModuleV2


class MockModule(BaseModuleV2):
    """Mock module for testing"""
    
    def get_param_specs(self):
        return {}
    
    def initialize(self):
        self.processed = False
    
    def process_buffer(self, input_buffer, output_buffer):
        self.processed = True
        output_buffer[:] = 1.0


class TestPatchRouter:
    """Test patch router functionality"""
    
    def setup_method(self):
        """Create fresh router for each test"""
        self.router = PatchRouter(buffer_size=256)
    
    def test_add_remove_modules(self):
        """Test adding and removing modules"""
        mod1 = MockModule(44100, 256)
        mod2 = MockModule(44100, 256)
        
        # Add modules
        assert self.router.add_module("mod1", mod1)
        assert self.router.add_module("mod2", mod2)
        assert len(self.router.modules) == 2
        
        # Try duplicate
        assert not self.router.add_module("mod1", mod1)
        
        # Remove module
        assert self.router.remove_module("mod1")
        assert len(self.router.modules) == 1
        assert "mod1" not in self.router.modules
    
    def test_connect_disconnect(self):
        """Test connecting and disconnecting modules"""
        mod1 = MockModule(44100, 256)
        mod2 = MockModule(44100, 256)
        mod3 = MockModule(44100, 256)
        
        self.router.add_module("mod1", mod1)
        self.router.add_module("mod2", mod2)
        self.router.add_module("mod3", mod3)
        
        # Connect modules
        assert self.router.connect("mod1", "mod2")
        assert self.router.connect("mod2", "mod3")
        
        connections = self.router.get_connections()
        assert ("mod1", "mod2") in connections
        assert ("mod2", "mod3") in connections
        
        # Disconnect
        assert self.router.disconnect("mod1", "mod2")
        connections = self.router.get_connections()
        assert ("mod1", "mod2") not in connections
    
    def test_cycle_detection(self):
        """Test that cycles are prevented"""
        mod1 = MockModule(44100, 256)
        mod2 = MockModule(44100, 256)
        mod3 = MockModule(44100, 256)
        
        self.router.add_module("mod1", mod1)
        self.router.add_module("mod2", mod2)
        self.router.add_module("mod3", mod3)
        
        # Create linear chain
        assert self.router.connect("mod1", "mod2")
        assert self.router.connect("mod2", "mod3")
        
        # Try to create cycle
        assert not self.router.connect("mod3", "mod1")
        
        # Graph should still be valid
        assert self.router.validate_graph()
    
    def test_topological_sort(self):
        """Test Kahn's algorithm for topological sorting"""
        # Create a more complex graph
        modules = {}
        for i in range(5):
            modules[f"mod{i}"] = MockModule(44100, 256)
            self.router.add_module(f"mod{i}", modules[f"mod{i}"])
        
        # Create connections: 0->1, 0->2, 1->3, 2->3, 3->4
        self.router.connect("mod0", "mod1")
        self.router.connect("mod0", "mod2")
        self.router.connect("mod1", "mod3")
        self.router.connect("mod2", "mod3")
        self.router.connect("mod3", "mod4")
        
        # Get processing order
        order = self.router.get_processing_order()
        
        # Verify topological properties
        assert len(order) == 5
        assert order.index("mod0") < order.index("mod1")
        assert order.index("mod0") < order.index("mod2")
        assert order.index("mod1") < order.index("mod3")
        assert order.index("mod2") < order.index("mod3")
        assert order.index("mod3") < order.index("mod4")
    
    def test_edge_buffers(self):
        """Test pre-allocated edge buffer management"""
        mod1 = MockModule(44100, 256)
        mod2 = MockModule(44100, 256)
        
        self.router.add_module("mod1", mod1)
        self.router.add_module("mod2", mod2)
        
        # Connect modules
        self.router.connect("mod1", "mod2")
        
        # Get edge buffer
        buffer = self.router.get_edge_buffer("mod1", "mod2")
        assert buffer is not None
        assert buffer.shape == (256,)
        assert buffer.dtype == np.float32
        
        # Non-existent edge
        buffer = self.router.get_edge_buffer("mod2", "mod1")
        assert buffer is None
    
    def test_module_inputs_outputs(self):
        """Test querying module connections"""
        mod1 = MockModule(44100, 256)
        mod2 = MockModule(44100, 256)
        mod3 = MockModule(44100, 256)
        
        self.router.add_module("mod1", mod1)
        self.router.add_module("mod2", mod2)
        self.router.add_module("mod3", mod3)
        
        # Create connections: 1->2, 3->2
        self.router.connect("mod1", "mod2")
        self.router.connect("mod3", "mod2")
        
        # Check inputs to mod2
        inputs = self.router.get_module_inputs("mod2")
        assert set(inputs) == {"mod1", "mod3"}
        
        # Check outputs from mod1
        outputs = self.router.get_module_outputs("mod1")
        assert outputs == ["mod2"]
        
        # Check mod2 has no outputs
        outputs = self.router.get_module_outputs("mod2")
        assert outputs == []
    
    def test_max_capacity(self):
        """Test that router respects maximum capacity"""
        # Add modules up to limit
        for i in range(PatchRouter.MAX_MODULES):
            mod = MockModule(44100, 256)
            assert self.router.add_module(f"mod{i}", mod)
        
        # Try to add one more
        extra_mod = MockModule(44100, 256)
        assert not self.router.add_module("extra", extra_mod)
    
    def test_clear(self):
        """Test clearing the router"""
        mod1 = MockModule(44100, 256)
        mod2 = MockModule(44100, 256)
        
        self.router.add_module("mod1", mod1)
        self.router.add_module("mod2", mod2)
        self.router.connect("mod1", "mod2")
        
        # Clear everything
        self.router.clear()
        
        assert len(self.router.modules) == 0
        assert len(self.router.get_connections()) == 0
        assert self.router.next_buffer_idx == 0
    
    def test_processing_order_caching(self):
        """Test that processing order is cached until graph changes"""
        mod1 = MockModule(44100, 256)
        mod2 = MockModule(44100, 256)
        
        self.router.add_module("mod1", mod1)
        self.router.add_module("mod2", mod2)
        self.router.connect("mod1", "mod2")
        
        # Get order twice
        order1 = self.router.get_processing_order()
        order2 = self.router.get_processing_order()
        
        # Should be the same object (cached)
        assert order1 is order2
        
        # Add new module
        mod3 = MockModule(44100, 256)
        self.router.add_module("mod3", mod3)
        
        # Order should be recalculated
        order3 = self.router.get_processing_order()
        assert order3 is not order1
    
    def test_serialization(self):
        """Test router state serialization"""
        mod1 = MockModule(44100, 256)
        mod2 = MockModule(44100, 256)
        
        self.router.add_module("mod1", mod1)
        self.router.add_module("mod2", mod2)
        self.router.connect("mod1", "mod2")
        
        state = self.router.to_dict()
        
        assert set(state["modules"]) == {"mod1", "mod2"}
        assert state["connections"] == [("mod1", "mod2")]
        assert state["processing_order"] == ["mod1", "mod2"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])