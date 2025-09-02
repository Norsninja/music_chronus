"""
Test supervisor patch flow without audio (CP3)
Dry-run test for standby patch building and commit flow

Tests:
- Patch building in standby slot
- Graph validation
- Ready state transitions
- Slot swap simulation
"""

import pytest
import numpy as np
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from music_chronus.module_host import ModuleHost
from music_chronus.patch_router import PatchRouter
from music_chronus.modules.base_v2 import BaseModuleV2
from music_chronus.param_spec import CommonParams


class TestSineModule(BaseModuleV2):
    """Simple test sine module"""
    def get_param_specs(self):
        return {"frequency": CommonParams.frequency()}
    
    def initialize(self):
        self.phase = 0.0
    
    def process_buffer(self, input_buffer, output_buffer):
        output_buffer[:] = 0.5  # Simple test output


class TestFilterModule(BaseModuleV2):
    """Simple test filter module"""
    def get_param_specs(self):
        return {"gain": CommonParams.gain()}
    
    def initialize(self):
        pass
    
    def process_buffer(self, input_buffer, output_buffer):
        np.copyto(output_buffer, input_buffer)  # Pass-through


class MockSupervisor:
    """Mock supervisor for testing patch flow"""
    
    def __init__(self, use_router=True):
        self.active_idx = 0  # Slot 0 is active
        self.standby_ready = False
        self.router_enabled = use_router
        self.pending_patch = {}
        
        # Create standby ModuleHost with router
        self.standby_host = ModuleHost(44100, 256, use_router=use_router)
        if use_router:
            self.standby_router = PatchRouter(256)
            self.standby_host.enable_router(self.standby_router)
        
        # Active host (linear chain)
        self.active_host = ModuleHost(44100, 256, use_router=False)
    
    def handle_patch_create(self, module_id, module_type):
        """Simulate patch create"""
        if not self.router_enabled:
            return False
        
        # Create module based on type (use local test modules)
        if module_type == "test_sine":
            module = TestSineModule(44100, 256)
        elif module_type == "test_filter":
            module = TestFilterModule(44100, 256)
        else:
            return False
        
        # Add to standby host
        success = self.standby_host.router_add_module(module_id, module)
        if success:
            self.pending_patch[module_id] = {'type': module_type}
        return success
    
    def handle_patch_connect(self, source_id, dest_id):
        """Simulate patch connect"""
        if not self.router_enabled:
            return False
        
        return self.standby_host.router_connect(source_id, dest_id)
    
    def handle_patch_commit(self):
        """Simulate patch commit"""
        if not self.router_enabled:
            return False
        
        # Validate graph
        if not self.standby_router.validate_graph():
            return False
        
        # Warm buffers (simulate)
        for _ in range(3):
            self.standby_host.process_chain()
        
        # Mark ready
        self.standby_ready = True
        
        # Simulate slot swap
        self.active_idx = 1 - self.active_idx
        
        # Swap hosts
        self.active_host, self.standby_host = self.standby_host, self.active_host
        
        # Reset standby
        self.standby_ready = False
        self.pending_patch.clear()
        
        return True
    
    def handle_patch_abort(self):
        """Simulate patch abort"""
        self.pending_patch.clear()
        if self.router_enabled and self.standby_router:
            self.standby_router.clear()
        self.standby_ready = False


class TestSupervisorPatchFlowDry:
    """Test supervisor patch flow without audio"""
    
    def test_basic_patch_flow(self):
        """Test basic patch create, connect, commit flow"""
        supervisor = MockSupervisor(use_router=True)
        
        # Initially slot 0 is active
        assert supervisor.active_idx == 0
        assert not supervisor.standby_ready
        
        # Create modules in standby
        assert supervisor.handle_patch_create("osc1", "test_sine")
        assert supervisor.handle_patch_create("filt1", "test_filter")
        
        # Connect them
        assert supervisor.handle_patch_connect("osc1", "filt1")
        
        # Verify graph in standby
        assert "osc1" in supervisor.standby_router.modules
        assert "filt1" in supervisor.standby_router.modules
        connections = supervisor.standby_router.get_connections()
        assert ("osc1", "filt1") in connections
        
        # Commit patch
        assert supervisor.handle_patch_commit()
        
        # Verify slot swap occurred
        assert supervisor.active_idx == 1  # Swapped to slot 1
        assert not supervisor.standby_ready  # Reset for new standby
    
    def test_cycle_detection(self):
        """Test that cycles are prevented during patch building"""
        supervisor = MockSupervisor(use_router=True)
        
        # Create modules
        supervisor.handle_patch_create("mod1", "test_sine")
        supervisor.handle_patch_create("mod2", "test_filter")
        supervisor.handle_patch_create("mod3", "test_filter")
        
        # Create valid chain
        supervisor.handle_patch_connect("mod1", "mod2")
        supervisor.handle_patch_connect("mod2", "mod3")
        
        # Try to create cycle
        success = supervisor.handle_patch_connect("mod3", "mod1")
        assert not success  # Should fail due to cycle
        
        # Graph should still be valid without the cycle
        assert supervisor.standby_router.validate_graph()
    
    def test_patch_abort(self):
        """Test patch abort clears pending changes"""
        supervisor = MockSupervisor(use_router=True)
        
        # Start building patch
        supervisor.handle_patch_create("osc1", "test_sine")
        supervisor.handle_patch_create("filt1", "test_filter")
        supervisor.handle_patch_connect("osc1", "filt1")
        
        # Verify patch is pending
        assert len(supervisor.pending_patch) == 2
        assert len(supervisor.standby_router.modules) == 2
        
        # Abort
        supervisor.handle_patch_abort()
        
        # Verify cleared
        assert len(supervisor.pending_patch) == 0
        assert not supervisor.standby_ready
    
    def test_buffer_warming(self):
        """Test that buffers are warmed before marking ready"""
        supervisor = MockSupervisor(use_router=True)
        
        # Create simple patch
        supervisor.handle_patch_create("osc1", "test_sine")
        
        # Before commit, no buffers processed
        assert supervisor.standby_host.buffers_processed == 0
        
        # Commit (includes warming)
        supervisor.handle_patch_commit()
        
        # Should have processed some buffers during warming
        # (In mock, we process 3 buffers)
        assert supervisor.active_host.buffers_processed >= 3
    
    def test_router_disabled_fallback(self):
        """Test that patch commands fail gracefully when router disabled"""
        supervisor = MockSupervisor(use_router=False)
        
        # Router disabled, patch commands should fail
        assert not supervisor.handle_patch_create("osc1", "test_sine")
        assert not supervisor.handle_patch_connect("osc1", "filt1")
        assert not supervisor.handle_patch_commit()
        
        # Active slot unchanged
        assert supervisor.active_idx == 0
    
    def test_state_transitions(self):
        """Test supervisor state transitions during patch flow"""
        supervisor = MockSupervisor(use_router=True)
        
        # Initial state
        assert supervisor.active_idx == 0
        assert not supervisor.standby_ready
        assert len(supervisor.pending_patch) == 0
        
        # Building state
        supervisor.handle_patch_create("osc1", "test_sine")
        assert len(supervisor.pending_patch) == 1
        assert not supervisor.standby_ready
        
        # Ready state (after commit starts)
        supervisor.handle_patch_commit()
        
        # Post-commit state
        assert supervisor.active_idx == 1  # Swapped
        assert not supervisor.standby_ready  # Reset
        assert len(supervisor.pending_patch) == 0  # Cleared
    
    def test_multiple_commits(self):
        """Test multiple patch commits work correctly"""
        supervisor = MockSupervisor(use_router=True)
        
        # First patch
        supervisor.handle_patch_create("osc1", "test_sine")
        supervisor.handle_patch_commit()
        assert supervisor.active_idx == 1
        
        # Second patch (now building in slot 0)
        supervisor.handle_patch_create("osc2", "test_sine")
        supervisor.handle_patch_commit()
        assert supervisor.active_idx == 0  # Back to slot 0
        
        # Third patch
        supervisor.handle_patch_create("osc3", "test_sine")
        supervisor.handle_patch_commit()
        assert supervisor.active_idx == 1  # Back to slot 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])