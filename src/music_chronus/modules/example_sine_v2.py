"""
Example SimpleSine module using the enhanced BaseModuleV2
Demonstrates ParamSpec integration and proper module structure
"""

import numpy as np
from typing import Dict
from .base_v2 import BaseModuleV2
from ..param_spec import ParamSpec, ParamType, SmoothingMode, CommonParams


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
        
        # Pre-compute index array for vectorized operations
        self.index_array = np.arange(self.buffer_size, dtype=np.float64)
    
    def process_buffer(self, input_buffer: np.ndarray, output_buffer: np.ndarray) -> None:
        """
        Generate sine wave (ALLOCATION-FREE and VECTORIZED).
        
        Uses vectorized numpy operations for optimal CPU performance.
        """
        # Get current parameter values (already smoothed)
        freq = self.params["frequency"]
        gain = self.params["gain"]
        phase_offset = self.params["phase_offset"]
        
        # Calculate phase increment per sample
        phase_inc = self.two_pi * freq / self.sr
        
        # Vectorized phase calculation:
        # 1. Multiply indices by phase increment (in-place)
        np.multiply(self.index_array, phase_inc, out=self.phase_buffer)
        
        # 2. Add current phase and offset (in-place)
        np.add(self.phase + phase_offset, self.phase_buffer, out=self.phase_buffer)
        
        # 3. Wrap phase values to [0, 2π] (in-place)
        np.mod(self.phase_buffer, self.two_pi, out=self.phase_buffer)
        
        # Update phase accumulator for next buffer
        self.phase = (self.phase + self.buffer_size * phase_inc) % self.two_pi
        
        # Generate sine wave directly into output buffer
        np.sin(self.phase_buffer, out=output_buffer)
        
        # Apply gain (in-place)
        np.multiply(output_buffer, gain, out=output_buffer)
    
    def reset(self) -> None:
        """Reset oscillator state"""
        self.phase = 0.0


# Import the centralized registration decorator
from ..module_registry import register_module

# Register this module with the central registry
@register_module("sine_v2")
class RegisteredSimpleSineV2(SimpleSineV2):
    """Registered version of SimpleSineV2 with optimal vectorized operations"""
    pass