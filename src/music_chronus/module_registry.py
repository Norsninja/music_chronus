"""
Module Registry - Centralized module discovery and registration
Phase 3: Module Framework

Provides:
- Central registry for all DSP modules
- Lazy import mechanism
- Module validation before registration
- Factory pattern for instance creation
"""

import importlib
import importlib.util
import inspect
import os
from typing import Dict, Type, Optional, List, Any
from pathlib import Path

from .modules.base_v2 import BaseModuleV2


class ModuleRegistry:
    """
    Central registry for DSP modules.
    
    Handles module discovery, registration, validation, and instantiation.
    Uses lazy imports to avoid loading modules until needed.
    """
    
    # Class-level registry (singleton pattern)
    _instance = None
    _modules: Dict[str, Type[BaseModuleV2]] = {}
    _module_paths: Dict[str, str] = {}
    _loaded_modules: Dict[str, Any] = {}
    
    def __new__(cls):
        """Singleton pattern - only one registry"""
        if cls._instance is None:
            cls._instance = super(ModuleRegistry, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize registry (only called once due to singleton)"""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            # Registry is already initialized at class level
    
    @classmethod
    def register(cls, module_id: str, module_class: Type[BaseModuleV2]) -> None:
        """
        Register a module class with the registry.
        
        Args:
            module_id: Unique identifier for the module
            module_class: Module class (must inherit from BaseModuleV2)
            
        Raises:
            ValueError: If module_id already registered or class invalid
        """
        if module_id in cls._modules:
            raise ValueError(f"Module '{module_id}' already registered")
        
        if not issubclass(module_class, BaseModuleV2):
            raise ValueError(f"Module must inherit from BaseModuleV2")
        
        # Validate RT-safety (basic check)
        try:
            # Create test instance to validate
            test_instance = module_class(sample_rate=44100, buffer_size=256)
            if not test_instance.validate_rt_safety():
                raise ValueError(f"Module '{module_id}' failed RT-safety validation")
        except Exception as e:
            raise ValueError(f"Module '{module_id}' validation failed: {e}")
        
        cls._modules[module_id] = module_class
        print(f"[Registry] Registered module: {module_id}")
    
    @classmethod
    def discover_modules(cls, path: str = None) -> List[str]:
        """
        Discover modules in the modules directory.
        
        Does NOT import them - only records their locations for lazy loading.
        
        Args:
            path: Directory to search (defaults to src/music_chronus/modules)
            
        Returns:
            List of discovered module IDs
        """
        if path is None:
            # Default to modules directory
            path = os.path.join(os.path.dirname(__file__), 'modules')
        
        discovered = []
        modules_path = Path(path)
        
        # Find all Python files in modules directory
        for file_path in modules_path.glob('*.py'):
            if file_path.name.startswith('_'):
                continue  # Skip private/init files
            
            if file_path.name == 'base.py' or file_path.name == 'base_v2.py':
                continue  # Skip base classes
            
            module_name = file_path.stem
            
            # Store path for lazy loading
            cls._module_paths[module_name] = str(file_path)
            discovered.append(module_name)
            
            print(f"[Registry] Discovered module: {module_name} at {file_path}")
        
        return discovered
    
    @classmethod
    def lazy_load(cls, module_id: str) -> Optional[Type[BaseModuleV2]]:
        """
        Lazy load a module when needed.
        
        Args:
            module_id: Module identifier
            
        Returns:
            Module class or None if not found
        """
        # Check if already loaded
        if module_id in cls._modules:
            return cls._modules[module_id]
        
        # Check if we have a path for it
        if module_id not in cls._module_paths:
            print(f"[Registry] Module '{module_id}' not found")
            return None
        
        try:
            # Import the module
            module_path = cls._module_paths[module_id]
            spec = importlib.util.spec_from_file_location(module_id, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find BaseModuleV2 subclasses
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BaseModuleV2) and 
                    obj != BaseModuleV2):
                    
                    # Check if it has a module_id attribute
                    if hasattr(obj, '_module_id'):
                        cls.register(obj._module_id, obj)
                        return obj
                    else:
                        # Register with file name as ID
                        cls.register(module_id, obj)
                        return obj
            
            print(f"[Registry] No valid module class found in {module_path}")
            return None
            
        except Exception as e:
            print(f"[Registry] Failed to load module '{module_id}': {e}")
            return None
    
    @classmethod
    def create_instance(cls, module_id: str, sample_rate: int = 44100, 
                       buffer_size: int = 256) -> Optional[BaseModuleV2]:
        """
        Create an instance of a registered module.
        
        Args:
            module_id: Module identifier
            sample_rate: Audio sample rate
            buffer_size: Audio buffer size
            
        Returns:
            Module instance or None if not found
        """
        # Try to get the module class (will lazy load if needed)
        module_class = cls.lazy_load(module_id)
        
        if module_class is None:
            print(f"[Registry] Cannot create instance - module '{module_id}' not found")
            return None
        
        try:
            instance = module_class(sample_rate=sample_rate, buffer_size=buffer_size)
            instance.module_id = module_id
            return instance
        except Exception as e:
            print(f"[Registry] Failed to create instance of '{module_id}': {e}")
            return None
    
    @classmethod
    def list_registered(cls) -> List[str]:
        """
        List all registered module IDs.
        
        Returns:
            List of module IDs
        """
        return list(cls._modules.keys())
    
    @classmethod
    def list_available(cls) -> List[str]:
        """
        List all available module IDs (registered + discovered).
        
        Returns:
            List of module IDs
        """
        return list(set(list(cls._modules.keys()) + list(cls._module_paths.keys())))
    
    @classmethod
    def get_module_info(cls, module_id: str) -> Optional[dict]:
        """
        Get information about a module.
        
        Args:
            module_id: Module identifier
            
        Returns:
            Dictionary with module information or None
        """
        module_class = cls.lazy_load(module_id)
        
        if module_class is None:
            return None
        
        # Create temporary instance to get param specs
        try:
            temp_instance = module_class(sample_rate=44100, buffer_size=256)
            param_specs = temp_instance.get_param_specs()
            
            return {
                "module_id": module_id,
                "class_name": module_class.__name__,
                "docstring": module_class.__doc__,
                "parameters": {
                    name: spec.to_dict() 
                    for name, spec in param_specs.items()
                }
            }
        except Exception as e:
            return {
                "module_id": module_id,
                "class_name": module_class.__name__,
                "error": str(e)
            }
    
    @classmethod
    def clear(cls):
        """Clear the registry (mainly for testing)"""
        cls._modules.clear()
        cls._module_paths.clear()
        cls._loaded_modules.clear()


# Module registration decorator
def register_module(module_id: str):
    """
    Decorator for registering modules with the central registry.
    
    Usage:
        @register_module("sine")
        class SimpleSine(BaseModuleV2):
            ...
    
    Args:
        module_id: Unique identifier for the module
    """
    def decorator(cls):
        # Store module_id on the class
        cls._module_id = module_id
        
        # Register with the central registry
        ModuleRegistry.register(module_id, cls)
        
        return cls
    
    return decorator


# Convenience function for getting the singleton
def get_registry() -> ModuleRegistry:
    """Get the global module registry instance"""
    return ModuleRegistry()