#!/usr/bin/env python3
"""
Windows Configuration Manager for Music Chronus
Handles environment variables and system configuration
"""

import os
import sys
import ctypes
import multiprocessing as mp
from pathlib import Path
from typing import Dict, Any

def load_env_file(env_path: str = ".env.windows") -> Dict[str, str]:
    """Load environment variables from file"""
    env_vars = {}
    
    # Try multiple locations
    locations = [
        Path(env_path),
        Path(__file__).parent.parent.parent / env_path,
        Path.cwd() / env_path
    ]
    
    for location in locations:
        if location.exists():
            with open(location, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            # Remove inline comments
                            if '#' in value:
                                value = value.split('#')[0]
                            env_vars[key.strip()] = value.strip()
            print(f"Loaded config from: {location}")
            break
    else:
        print(f"Warning: No .env.windows file found")
    
    return env_vars

def apply_windows_config():
    """Apply Windows-specific configuration"""
    
    # Load environment variables
    env_vars = load_env_file()
    
    # Apply to os.environ
    for key, value in env_vars.items():
        os.environ[key] = value
    
    # Set multiprocessing start method
    if sys.platform == 'win32':
        try:
            mp.set_start_method('spawn', force=True)
            print("Set multiprocessing start method: spawn")
        except RuntimeError:
            pass  # Already set
    
    # Set process priority if requested
    if os.environ.get('CHRONUS_HIGH_PRIORITY', '0') == '1':
        set_high_priority()
    
    # Register with MMCSS if requested
    if os.environ.get('CHRONUS_MMCSS', '0') == '1':
        register_mmcss()
    
    return env_vars

def set_high_priority():
    """Set Windows process to high priority"""
    if sys.platform != 'win32':
        return
        
    try:
        import psutil
        p = psutil.Process()
        p.nice(psutil.HIGH_PRIORITY_CLASS)
        print("Set process priority: HIGH")
    except ImportError:
        # Fallback to ctypes
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetCurrentProcess()
            HIGH_PRIORITY_CLASS = 0x00000080
            kernel32.SetPriorityClass(handle, HIGH_PRIORITY_CLASS)
            print("Set process priority: HIGH (ctypes)")
        except Exception as e:
            print(f"Failed to set high priority: {e}")

def register_mmcss():
    """Register with Windows Multimedia Class Scheduler Service"""
    if sys.platform != 'win32':
        return
        
    try:
        avrt = ctypes.windll.avrt
        task_handle = ctypes.c_void_p()
        task_index = ctypes.c_ulong()
        
        # Register as "Pro Audio" task
        task_handle = avrt.AvSetMmThreadCharacteristicsW(
            ctypes.c_wchar_p("Pro Audio"),
            ctypes.byref(task_index)
        )
        
        if task_handle:
            # Set to critical priority within Pro Audio class
            avrt.AvSetMmThreadPriority(task_handle, 2)  # AVRT_PRIORITY_HIGH
            print("Registered with Windows MMCSS: Pro Audio")
            return task_handle
    except Exception as e:
        print(f"MMCSS registration failed: {e}")
    
    return None

def get_config() -> Dict[str, Any]:
    """Get parsed configuration values"""
    config = {
        # Audio
        'sample_rate': int(os.environ.get('CHRONUS_SAMPLE_RATE', '48000')),
        'buffer_size': int(os.environ.get('CHRONUS_BUFFER_SIZE', '256')),
        'output_device': int(os.environ.get('CHRONUS_OUTPUT_DEVICE', '-1')),
        'use_wasapi': os.environ.get('CHRONUS_USE_WASAPI', '1') == '1',
        'channels': int(os.environ.get('CHRONUS_CHANNELS', '1')),
        
        # Process
        'pool_size': int(os.environ.get('CHRONUS_POOL_SIZE', '4')),
        'module_timeout': int(os.environ.get('CHRONUS_MODULE_TIMEOUT', '1000')),
        'maxtasks': int(os.environ.get('CHRONUS_MAXTASKS_PER_CHILD', '500')),
        
        # Router
        'use_router': os.environ.get('CHRONUS_ROUTER', '0') == '1',
        'prefill_buffers': int(os.environ.get('CHRONUS_PREFILL_BUFFERS', '3')),
        
        # OSC
        'osc_host': os.environ.get('CHRONUS_OSC_HOST', '127.0.0.1'),
        'osc_port': int(os.environ.get('CHRONUS_OSC_PORT', '5005')),
        
        # Debug
        'debug': os.environ.get('CHRONUS_DEBUG', '0') == '1',
        'metrics': os.environ.get('CHRONUS_METRICS', '1') == '1',
    }
    
    return config

def print_config():
    """Print current configuration"""
    config = get_config()
    
    print("\n" + "="*60)
    print("MUSIC CHRONUS - WINDOWS CONFIGURATION")
    print("="*60)
    
    sections = {
        'Audio': ['sample_rate', 'buffer_size', 'output_device', 'use_wasapi', 'channels'],
        'Process': ['pool_size', 'module_timeout', 'maxtasks'],
        'Router': ['use_router', 'prefill_buffers'],
        'OSC': ['osc_host', 'osc_port'],
        'Debug': ['debug', 'metrics']
    }
    
    for section, keys in sections.items():
        print(f"\n{section}:")
        for key in keys:
            if key in config:
                print(f"  {key}: {config[key]}")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    # Test configuration loading
    apply_windows_config()
    print_config()