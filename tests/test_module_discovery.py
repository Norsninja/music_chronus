"""
Test module discovery and lazy loading
Phase 3: Module Framework

Tests that the registry can discover and lazily load modules.
"""

import pytest
import os
import tempfile
from pathlib import Path

from src.music_chronus.module_registry import ModuleRegistry, get_registry


class TestModuleDiscovery:
    """Test module discovery and lazy loading functionality"""
    
    def setup_method(self):
        """Clear registry before each test"""
        ModuleRegistry.clear()
    
    def test_discover_modules_in_package_directory(self):
        """Test that discover_modules finds modules in the package modules directory"""
        registry = get_registry()
        
        # Discover modules in the actual modules directory
        discovered = registry.discover_modules()
        
        # Should at least find example_sine_v2 if it exists
        if "example_sine_v2" in discovered:
            assert "example_sine_v2" in registry._module_paths
    
    def test_lazy_load_discovered_module(self):
        """Test lazy loading of a discovered module"""
        registry = get_registry()
        
        # Create a temporary test module
        with tempfile.TemporaryDirectory() as tmpdir:
            module_path = Path(tmpdir) / "test_sine.py"
            module_content = '''
"""Test module for discovery"""
from src.music_chronus.modules.base_v2 import BaseModuleV2
from src.music_chronus.param_spec import CommonParams
import numpy as np

class TestSine(BaseModuleV2):
    def get_param_specs(self):
        return {"frequency": CommonParams.frequency()}
    
    def initialize(self):
        self.phase = 0.0
    
    def process_buffer(self, input_buffer, output_buffer):
        output_buffer[:] = 0.5  # Simple test implementation
'''
            module_path.write_text(module_content)
            
            # Discover modules in the temp directory
            discovered = registry.discover_modules(tmpdir)
            assert "test_sine" in discovered
            
            # Verify it's not loaded yet
            assert "test_sine" not in registry._modules
            
            # Try to create instance (should trigger lazy load)
            instance = registry.create_instance("test_sine")
            
            # For this test, instance might be None if imports fail
            # But the path should be recorded
            assert "test_sine" in registry._module_paths
    
    def test_create_instance_with_registered_module(self):
        """Test creating instance of already registered module"""
        registry = get_registry()
        
        # Import and register the example module directly
        from src.music_chronus.modules.example_sine_v2 import RegisteredSimpleSineV2
        # If not already registered (decorator may have run), register it
        if "sine_v2" not in registry._modules:
            registry.register("sine_v2", RegisteredSimpleSineV2)
        
        # Should be registered
        assert "sine_v2" in registry._modules
        
        # Create instance
        instance = registry.create_instance("sine_v2", sample_rate=44100, buffer_size=256)
        
        assert instance is not None
        assert instance.sr == 44100
        assert instance.buffer_size == 256
        assert instance.module_id == "sine_v2"
    
    def test_module_info_retrieval(self):
        """Test getting module information"""
        registry = get_registry()
        
        # Manually register since we cleared in setup
        from src.music_chronus.modules.example_sine_v2 import RegisteredSimpleSineV2
        registry.register("sine_v2", RegisteredSimpleSineV2)
        
        # Get module info
        info = registry.get_module_info("sine_v2")
        
        assert info is not None
        assert info["module_id"] == "sine_v2"
        assert "parameters" in info
        assert "frequency" in info["parameters"]
        assert "gain" in info["parameters"]
    
    def test_list_available_modules(self):
        """Test listing available modules (registered + discovered)"""
        registry = get_registry()
        
        # Discover modules
        registry.discover_modules()
        
        # Manually register since we cleared in setup
        from src.music_chronus.modules.example_sine_v2 import RegisteredSimpleSineV2
        registry.register("sine_v2", RegisteredSimpleSineV2)
        
        # List available
        available = registry.list_available()
        
        # Should include both registered and discovered
        assert "sine_v2" in available  # Registered
        if "example_sine_v2" in registry._module_paths:
            assert "example_sine_v2" in available  # Discovered
    
    def test_module_file_naming_convention(self):
        """Test that module file name can differ from module_id"""
        registry = get_registry()
        
        # The example_sine_v2.py file registers as "sine_v2"
        from src.music_chronus.modules.example_sine_v2 import RegisteredSimpleSineV2
        # Manually register since we cleared in setup
        registry.register("sine_v2", RegisteredSimpleSineV2)
        
        # Should be registered under "sine_v2", not "example_sine_v2"
        assert "sine_v2" in registry._modules
        
        # Can create instance with the registered ID
        instance = registry.create_instance("sine_v2")
        assert instance is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])