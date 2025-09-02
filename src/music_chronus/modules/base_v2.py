"""
Enhanced BaseModule with ParamSpec integration
Phase 3: Module Framework with parameter metadata

Extends the original BaseModule with:
- ParamSpec-based parameter definitions
- Type-safe parameter updates
- Automatic range clamping
- Improved smoothing algorithms
"""

import numpy as np
from typing import Dict, Optional, Any
from abc import ABC, abstractmethod

# Import parameter specification system
from ..param_spec import ParamSpec, ParamType, SmoothingMode


class BaseModuleV2(ABC):
    """
    Enhanced base class for DSP modules with parameter metadata.
    
    Guarantees:
    - Zero allocations in process_buffer()
    - Type-safe parameter updates with automatic clamping
    - Configurable smoothing per parameter specification
    - Boundary-only parameter updates (no locking needed)
    """
    
    def __init__(self, sample_rate: int, buffer_size: int):
        """
        Initialize module with fixed buffer size.
        ALL allocations must happen here.
        
        Args:
            sample_rate: System sample rate (typically 44100)
            buffer_size: Buffer size in samples (typically 256)
        """
        self.sr = sample_rate
        self.buffer_size = buffer_size
        
        # Get parameter specifications from subclass
        self.param_specs: Dict[str, ParamSpec] = self.get_param_specs()
        
        # Initialize parameter values to defaults
        self.params: Dict[str, Any] = {}
        self.param_targets: Dict[str, Any] = {}
        self.smoothing_state: Dict[str, float] = {}
        
        # Calculate smoothing coefficients for each parameter
        self.smoothing_coeffs: Dict[str, float] = {}
        
        # Initialize all parameters
        for name, spec in self.param_specs.items():
            self.params[name] = spec.default
            self.param_targets[name] = spec.default
            self.smoothing_state[name] = float(spec.default) if spec.param_type != ParamType.BOOL else spec.default
            self.smoothing_coeffs[name] = spec.calculate_smoothing_coeff(sample_rate)
        
        # Module metadata
        self.module_id = None  # Set by registry/router
        self.active = True
        
        # Call subclass initialization
        self.initialize()
    
    @abstractmethod
    def get_param_specs(self) -> Dict[str, ParamSpec]:
        """
        Define parameter specifications for this module.
        
        Must be implemented by subclasses.
        
        Returns:
            Dictionary mapping parameter names to ParamSpec objects
        """
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """
        Subclass-specific initialization.
        
        Called after base initialization. Use this for:
        - Allocating internal buffers
        - Setting up DSP state
        - Initializing lookup tables
        """
        pass
    
    @abstractmethod
    def process_buffer(self, input_buffer: np.ndarray, output_buffer: np.ndarray) -> None:
        """
        Process one buffer of audio (MUST BE ALLOCATION-FREE).
        
        Args:
            input_buffer: Input audio buffer (read-only)
            output_buffer: Output audio buffer (write-only)
            
        Note:
            - Do NOT allocate any arrays or objects
            - Do NOT call functions that allocate
            - Use pre-allocated buffers only
            - Parameters are already smoothed
        """
        pass
    
    def set_param(self, param: str, value: Any, immediate: bool = False) -> bool:
        """
        Set a parameter value (applied at next buffer boundary).
        
        Args:
            param: Parameter name
            value: Target value (will be clamped to valid range)
            immediate: If True, bypass smoothing
            
        Returns:
            True if parameter exists and was set, False otherwise
        """
        if param not in self.param_specs:
            return False
        
        spec = self.param_specs[param]
        
        # Clamp value to valid range
        clamped_value = spec.clamp_value(value)
        
        if immediate:
            # Immediate update - bypass smoothing
            self.params[param] = clamped_value
            self.param_targets[param] = clamped_value
            self.smoothing_state[param] = float(clamped_value) if spec.param_type != ParamType.BOOL else clamped_value
        else:
            # Set target for smoothing
            self.param_targets[param] = clamped_value
        
        return True
    
    def set_gate(self, value: bool) -> bool:
        """
        Set gate parameter if module has one.
        
        Args:
            value: Gate state (True = on, False = off)
            
        Returns:
            True if gate was set, False if module has no gate
        """
        if "gate" in self.param_specs:
            return self.set_param("gate", value, immediate=True)
        return False
    
    def get_param(self, param: str) -> Optional[Any]:
        """
        Get current parameter value.
        
        Args:
            param: Parameter name
            
        Returns:
            Current value or None if parameter doesn't exist
        """
        return self.params.get(param)
    
    def prepare(self) -> None:
        """
        Prepare for processing (called at buffer boundary).
        
        Updates smoothed parameters before process_buffer().
        """
        self._update_smoothing()
    
    def _update_smoothing(self) -> None:
        """
        Update parameter smoothing (allocation-free).
        
        Applies appropriate smoothing algorithm based on ParamSpec.
        """
        for name, spec in self.param_specs.items():
            if spec.param_type == ParamType.BOOL or spec.smoothing_mode == SmoothingMode.NONE:
                # No smoothing for boolean or unsmoothed params
                self.params[name] = self.param_targets[name]
                continue
            
            target = float(self.param_targets[name])
            current = self.smoothing_state[name]
            
            # Check if we're close enough to snap
            if abs(current - target) < 1e-9:
                self.params[name] = self.param_targets[name]
                self.smoothing_state[name] = target
                continue
            
            # Apply smoothing based on mode
            if spec.smoothing_mode == SmoothingMode.LINEAR:
                # Linear interpolation
                step = self.smoothing_coeffs[name]
                if current < target:
                    new_value = min(current + step * (target - current), target)
                else:
                    new_value = max(current + step * (target - current), target)
                    
            elif spec.smoothing_mode == SmoothingMode.EXPONENTIAL:
                # One-pole lowpass filter
                coeff = self.smoothing_coeffs[name]
                new_value = current + (1.0 - coeff) * (target - current)
                
            elif spec.smoothing_mode == SmoothingMode.LOGARITHMIC:
                # Logarithmic smoothing (good for frequency)
                coeff = self.smoothing_coeffs[name]
                if target > 0 and current > 0:
                    log_current = np.log(current)
                    log_target = np.log(target)
                    log_new = log_current + (1.0 - coeff) * (log_target - log_current)
                    new_value = np.exp(log_new)
                else:
                    # Fallback to linear for zero/negative values
                    new_value = current + (1.0 - coeff) * (target - current)
            else:
                new_value = target
            
            # Snap to target if very close
            if abs(new_value - target) < 1e-6:
                new_value = target
            
            # Update state
            self.smoothing_state[name] = new_value
            self.params[name] = type(self.param_targets[name])(new_value)
    
    def get_state(self) -> dict:
        """
        Get current module state for serialization.
        
        Returns:
            Dictionary containing all parameter values
        """
        return {
            "module_id": self.module_id,
            "params": dict(self.params),
            "active": self.active
        }
    
    def set_state(self, state: dict) -> None:
        """
        Restore module state from dictionary.
        
        Args:
            state: Previously saved state
        """
        if "params" in state:
            for name, value in state["params"].items():
                self.set_param(name, value, immediate=True)
        if "active" in state:
            self.active = state["active"]
    
    def validate_rt_safety(self) -> bool:
        """
        Validate that module is real-time safe.
        
        Subclasses can override to add specific checks.
        
        Returns:
            True if module appears RT-safe
        """
        # Basic check - ensure process_buffer is implemented
        if self.process_buffer == BaseModuleV2.process_buffer:
            return False
        
        # Check that all parameters have specs
        for param in self.params:
            if param not in self.param_specs:
                return False
        
        return True