"""
Example SimpleSine module using the enhanced BaseModuleV2
Demonstrates ParamSpec integration and proper module structure
"""

import numpy as np
from typing import Dict
from base_v2 import BaseModuleV2
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from param_spec import ParamSpec, ParamType, SmoothingMode, CommonParams


class SimpleSineV2(BaseModuleV2):
    """
    Simple sine wave oscillator with ParamSpec metadata.
    
    Demonstrates:
    - Parameter specification with units and ranges
    - Proper smoothing for frequency and gain
    - Zero-allocation processing
    """
    
    def get_param_specs(self) -> Dict[str, ParamSpec]:
        """Define parameter specifications"""
        return {
            "frequency": CommonParams.frequency(default=440.0),
            "gain": CommonParams.gain(default=0.5),
            "phase_offset": ParamSpec(
                name="phase_offset",
                param_type=ParamType.FLOAT,
                default=0.0,
                range=(0.0, 2 * np.pi),
                units="radians",
                smoothing_mode=SmoothingMode.NONE,
                description="Initial phase offset"
            )
        }
    
    def initialize(self) -> None:
        """Initialize oscillator state"""
        # Phase accumulator (64-bit for precision)
        self.phase = np.float64(0.0)
        
        # Pre-compute constants
        self.two_pi = np.float64(2.0 * np.pi)
        
        # Pre-allocate working buffer for phase values
        self.phase_buffer = np.zeros(self.buffer_size, dtype=np.float64)
    
    def process_buffer(self, input_buffer: np.ndarray, output_buffer: np.ndarray) -> None:
        """
        Generate sine wave (ALLOCATION-FREE).
        
        Uses phase accumulator with wraparound.
        """
        # Get current parameter values (already smoothed)
        freq = self.params["frequency"]
        gain = self.params["gain"]
        phase_offset = self.params["phase_offset"]
        
        # Calculate phase increment
        phase_inc = self.two_pi * freq / self.sr
        
        # Generate phase values for this buffer
        # Using pre-allocated buffer to avoid allocation
        current_phase = self.phase
        for i in range(self.buffer_size):
            self.phase_buffer[i] = current_phase + phase_offset
            current_phase += phase_inc
            # Wrap phase to prevent overflow
            if current_phase >= self.two_pi:
                current_phase -= self.two_pi
        
        # Store final phase for next buffer
        self.phase = current_phase
        
        # Generate sine wave directly into output
        np.sin(self.phase_buffer, out=output_buffer)
        
        # Apply gain
        output_buffer *= gain
    
    def reset(self) -> None:
        """Reset oscillator state"""
        self.phase = 0.0


# Module registration decorator (will be used by ModuleRegistry)
def register_module(module_id: str):
    """Decorator for registering modules"""
    def decorator(cls):
        cls._module_id = module_id
        return cls
    return decorator


# Register this module
@register_module("sine_v2")
class RegisteredSimpleSineV2(SimpleSineV2):
    """Registered version of SimpleSineV2"""
    pass