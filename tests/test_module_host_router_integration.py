"""
Test ModuleHost router integration (CP2)
Non-audio integration test for router-based processing

Tests:
- Router-based DAG processing
- Zero allocations in steady state
- Stable output with connected modules
"""

import pytest
import numpy as np
import tracemalloc
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from music_chronus.module_host import ModuleHost
from music_chronus.patch_router import PatchRouter
from music_chronus.modules.base_v2 import BaseModuleV2
from music_chronus.param_spec import CommonParams


class PassThroughFilter(BaseModuleV2):
    """Simple pass-through filter for testing"""
    
    def get_param_specs(self):
        return {
            "gain": CommonParams.gain(default=1.0)
        }
    
    def initialize(self):
        pass
    
    def process_buffer(self, input_buffer, output_buffer):
        # Simple pass-through with gain
        gain = self.params["gain"]
        np.multiply(input_buffer, gain, out=output_buffer)


class TestSineGenerator(BaseModuleV2):
    """Test sine generator (simplified)"""
    
    def get_param_specs(self):
        return {
            "frequency": CommonParams.frequency(default=440.0),
            "gain": CommonParams.gain(default=0.5)
        }
    
    def initialize(self):
        self.phase = 0.0
        self.two_pi = 2.0 * np.pi
    
    def process_buffer(self, input_buffer, output_buffer):
        # Generate simple sine wave
        freq = self.params["frequency"]
        gain = self.params["gain"]
        phase_inc = self.two_pi * freq / self.sr
        
        for i in range(len(output_buffer)):
            output_buffer[i] = gain * np.sin(self.phase)
            self.phase = (self.phase + phase_inc) % self.two_pi


class TestModuleHostRouterIntegration:
    """Test ModuleHost with router enabled"""
    
    def test_router_based_processing(self):
        """Test that router-based processing works correctly"""
        # Create ModuleHost with router enabled
        sample_rate = 44100
        buffer_size = 256
        host = ModuleHost(sample_rate, buffer_size, use_router=True)
        
        # Create and enable router
        router = PatchRouter(buffer_size)
        host.enable_router(router)
        
        # Create modules
        sine = TestSineGenerator(sample_rate, buffer_size)
        filter_module = PassThroughFilter(sample_rate, buffer_size)
        
        # Add modules using helper methods
        assert host.router_add_module("sine", sine)
        assert host.router_add_module("filter", filter_module)
        
        # Connect sine -> filter
        assert host.router_connect("sine", "filter")
        
        # Process some buffers
        outputs = []
        for _ in range(10):
            output = host.process_chain()
            outputs.append(output.copy())  # Copy for analysis
        
        # Verify output shape and type
        assert all(o.shape == (buffer_size,) for o in outputs)
        assert all(o.dtype == np.float32 for o in outputs)
        
        # Verify non-zero output (sine is generating)
        assert any(np.abs(o).max() > 0.01 for o in outputs)
        
        # Verify stable RMS (should be consistent after first buffer)
        rms_values = [np.sqrt(np.mean(o**2)) for o in outputs[1:]]
        assert np.std(rms_values) < 0.01  # Low variance in RMS
    
    def test_zero_allocations_steady_state(self):
        """Test that steady-state processing has minimal allocations"""
        # Create ModuleHost with router
        sample_rate = 44100
        buffer_size = 256
        host = ModuleHost(sample_rate, buffer_size, use_router=True)
        
        # Setup router and modules
        router = PatchRouter(buffer_size)
        host.enable_router(router)
        
        sine = TestSineGenerator(sample_rate, buffer_size)
        filter_module = PassThroughFilter(sample_rate, buffer_size)
        
        host.router_add_module("sine", sine)
        host.router_add_module("filter", filter_module)
        host.router_connect("sine", "filter")
        
        # Warm up (first few calls may allocate)
        for _ in range(5):
            host.process_chain()
        
        # Measure allocations during steady state
        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()
        
        # Process many buffers
        N = 200
        for _ in range(N):
            host.process_chain()
        
        snapshot2 = tracemalloc.take_snapshot()
        tracemalloc.stop()
        
        # Compare snapshots
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        
        # Filter for significant allocations (>1KB)
        significant_allocations = [
            stat for stat in top_stats 
            if stat.size_diff > 1024  # More than 1KB allocated
        ]
        
        # Print any significant allocations for debugging
        if significant_allocations:
            print("\nSignificant allocations detected:")
            for stat in significant_allocations[:5]:
                print(f"  {stat}")
        
        # Assert minimal allocations (allow some Python overhead)
        # We're looking for absence of numpy array allocations
        total_allocated = sum(stat.size_diff for stat in top_stats if stat.size_diff > 0)
        bytes_per_iteration = total_allocated / N
        
        # Should be very small per iteration (allowing for Python overhead)
        assert bytes_per_iteration < 100, f"Too many allocations: {bytes_per_iteration} bytes/iteration"
    
    def test_complex_graph_processing(self):
        """Test a more complex graph with multiple connections"""
        sample_rate = 44100
        buffer_size = 256
        host = ModuleHost(sample_rate, buffer_size, use_router=True)
        
        router = PatchRouter(buffer_size)
        host.enable_router(router)
        
        # Create multiple modules
        sine1 = TestSineGenerator(sample_rate, buffer_size)
        sine2 = TestSineGenerator(sample_rate, buffer_size)
        filter1 = PassThroughFilter(sample_rate, buffer_size)
        filter2 = PassThroughFilter(sample_rate, buffer_size)
        
        # Different frequencies for the sines
        sine1.set_param("frequency", 440.0)
        sine2.set_param("frequency", 220.0)
        
        # Add all modules
        host.router_add_module("sine1", sine1)
        host.router_add_module("sine2", sine2)
        host.router_add_module("filter1", filter1)
        host.router_add_module("filter2", filter2)
        
        # Create graph: sine1 -> filter1
        #              sine2 -> filter1
        #              filter1 -> filter2
        host.router_connect("sine1", "filter1")
        host.router_connect("sine2", "filter1")
        host.router_connect("filter1", "filter2")
        
        # Process
        outputs = []
        for _ in range(10):
            output = host.process_chain()
            outputs.append(output.copy())
        
        # Should have mixed signal from both sines
        assert all(o.shape == (buffer_size,) for o in outputs)
        assert any(np.abs(o).max() > 0.5 for o in outputs)  # Should be louder (two sines mixed)
    
    def test_router_helpers(self):
        """Test router helper methods"""
        sample_rate = 44100
        buffer_size = 256
        host = ModuleHost(sample_rate, buffer_size, use_router=True)
        
        router = PatchRouter(buffer_size)
        host.enable_router(router)
        
        sine = TestSineGenerator(sample_rate, buffer_size)
        filter_module = PassThroughFilter(sample_rate, buffer_size)
        
        # Test add
        assert host.router_add_module("sine", sine)
        assert host.router_add_module("filter", filter_module)
        
        # Test connect
        assert host.router_connect("sine", "filter")
        
        # Verify in router
        assert "sine" in host.router.modules
        assert "filter" in host.router.modules
        assert ("sine", "filter") in host.router.get_connections()
        
        # Test disconnect
        assert host.router_disconnect("sine", "filter")
        assert ("sine", "filter") not in host.router.get_connections()
        
        # Test clear
        host.clear_router()
        assert host.router is None
    
    def test_fallback_to_linear_chain(self):
        """Test that linear chain still works when router not enabled"""
        sample_rate = 44100
        buffer_size = 256
        
        # Create without router
        host = ModuleHost(sample_rate, buffer_size, use_router=False)
        
        # Add modules the traditional way
        sine = TestSineGenerator(sample_rate, buffer_size)
        host.add_module("sine", sine)
        
        # Process should use linear chain
        output = host.process_chain()
        
        assert output.shape == (buffer_size,)
        assert output.dtype == np.float32


if __name__ == "__main__":
    pytest.main([__file__, "-v"])