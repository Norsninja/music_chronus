"""
Unit tests for Module Registry
Phase 3: Module Framework
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from music_chronus.module_registry import ModuleRegistry, register_module, get_registry
from music_chronus.modules.base_v2 import BaseModuleV2
from music_chronus.param_spec import ParamSpec, ParamType, CommonParams
from typing import Dict


class TestModule(BaseModuleV2):
    """Simple test module for registry testing"""
    
    def get_param_specs(self) -> Dict[str, ParamSpec]:
        return {
            "test_param": ParamSpec(
                name="test_param",
                param_type=ParamType.FLOAT,
                default=1.0,
                range=(0.0, 10.0)
            )
        }
    
    def initialize(self):
        pass
    
    def process_buffer(self, input_buffer, output_buffer):
        output_buffer[:] = input_buffer * self.params["test_param"]


class TestModuleRegistry(unittest.TestCase):
    """Test ModuleRegistry functionality"""
    
    def setUp(self):
        """Clear registry before each test"""
        ModuleRegistry.clear()
    
    def test_singleton_pattern(self):
        """Test that registry is a singleton"""
        registry1 = get_registry()
        registry2 = get_registry()
        self.assertIs(registry1, registry2)
    
    def test_register_module(self):
        """Test module registration"""
        # Register a test module
        ModuleRegistry.register("test_module", TestModule)
        
        # Check it's registered
        self.assertIn("test_module", ModuleRegistry.list_registered())
        
        # Try to register again (should fail)
        with self.assertRaises(ValueError):
            ModuleRegistry.register("test_module", TestModule)
    
    def test_create_instance(self):
        """Test creating module instances"""
        # Register module
        ModuleRegistry.register("test_module", TestModule)
        
        # Create instance
        instance = ModuleRegistry.create_instance("test_module")
        
        self.assertIsNotNone(instance)
        self.assertIsInstance(instance, TestModule)
        self.assertEqual(instance.module_id, "test_module")
        self.assertEqual(instance.sr, 44100)
        self.assertEqual(instance.buffer_size, 256)
    
    def test_create_instance_with_params(self):
        """Test creating instance with custom parameters"""
        ModuleRegistry.register("test_module", TestModule)
        
        instance = ModuleRegistry.create_instance(
            "test_module",
            sample_rate=48000,
            buffer_size=512
        )
        
        self.assertEqual(instance.sr, 48000)
        self.assertEqual(instance.buffer_size, 512)
    
    def test_invalid_module_class(self):
        """Test that non-BaseModuleV2 classes are rejected"""
        class NotAModule:
            pass
        
        with self.assertRaises(ValueError):
            ModuleRegistry.register("bad_module", NotAModule)
    
    def test_module_info(self):
        """Test getting module information"""
        ModuleRegistry.register("test_module", TestModule)
        
        info = ModuleRegistry.get_module_info("test_module")
        
        self.assertIsNotNone(info)
        self.assertEqual(info["module_id"], "test_module")
        self.assertEqual(info["class_name"], "TestModule")
        self.assertIn("parameters", info)
        self.assertIn("test_param", info["parameters"])
    
    def test_list_functions(self):
        """Test listing registered and available modules"""
        # Initially empty
        self.assertEqual(len(ModuleRegistry.list_registered()), 0)
        
        # Register a module
        ModuleRegistry.register("test1", TestModule)
        
        # Should appear in registered list
        registered = ModuleRegistry.list_registered()
        self.assertIn("test1", registered)
        self.assertEqual(len(registered), 1)
    
    def test_rt_safety_validation(self):
        """Test that modules are validated for RT-safety"""
        
        class UnsafeModule(BaseModuleV2):
            """Module that fails RT-safety check"""
            
            def get_param_specs(self):
                return {}
            
            def initialize(self):
                pass
            
            def process_buffer(self, input_buffer, output_buffer):
                pass
            
            def validate_rt_safety(self):
                return False  # Explicitly fail validation
        
        # Should fail to register
        with self.assertRaises(ValueError) as context:
            ModuleRegistry.register("unsafe", UnsafeModule)
        
        self.assertIn("RT-safety", str(context.exception))
    
    def test_decorator_registration(self):
        """Test the @register_module decorator"""
        # Clear registry first
        ModuleRegistry.clear()
        
        # Use decorator to register
        @register_module("decorated_test")
        class DecoratedModule(TestModule):
            pass
        
        # Should be registered
        self.assertIn("decorated_test", ModuleRegistry.list_registered())
        
        # Should have module_id attribute
        self.assertEqual(DecoratedModule._module_id, "decorated_test")
        
        # Should be able to create instance
        instance = ModuleRegistry.create_instance("decorated_test")
        self.assertIsNotNone(instance)


if __name__ == '__main__':
    unittest.main()