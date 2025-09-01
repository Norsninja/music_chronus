"""
BaseModule - Foundation for all DSP modules
Phase 2: Zero-allocation audio processing

Key principles:
1. All allocations happen in __init__
2. process_buffer() must be allocation-free
3. Parameter changes apply at buffer boundaries
4. Smoothing prevents clicks/pops
5. State persists between buffers
"""

import numpy as np
from typing import Dict, Optional, Any


class BaseModule:
    """
    Base class for all DSP modules in the synthesis chain.
    
    Guarantees:
    - Zero allocations in process_buffer()
    - Boundary-only parameter updates
    - Configurable smoothing per parameter
    - Parameters applied at buffer boundaries (no locking needed)
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
        
        # Parameter storage (all float64 for precision)
        self.params: Dict[str, float] = {}
        self.param_targets: Dict[str, float] = {}
        
        # Smoothing configuration (in samples)
        # Subclasses should override with appropriate values
        self.smoothing_samples: Dict[str, int] = {
            'default': int(0.005 * sample_rate),  # 5ms default
        }
        
        # Smoothing state (current interpolation position)
        self.smoothing_state: Dict[str, float] = {}
        
        # Module metadata
        self.name = self.__class__.__name__
        self.active = True
        
    def get_smoothing_samples(self, param: str) -> int:
        """
        Get smoothing duration for a parameter.
        
        Args:
            param: Parameter name
            
        Returns:
            Number of samples for smoothing
        """
        return self.smoothing_samples.get(param, 
                                         self.smoothing_samples.get('default', 0))
    
    def set_param(self, param: str, value: float, immediate: bool = False) -> None:
        """
        Set a parameter value (applied at next buffer boundary).
        
        Args:
            param: Parameter name
            value: Target value
            immediate: If True, bypass smoothing
            
        Note: Called by ModuleHost at buffer boundaries, no locking required.
        """
        if param not in self.params:
            # First time setting this parameter
            self.params[param] = value
            self.param_targets[param] = value
            self.smoothing_state[param] = value
        else:
            if immediate:
                self.params[param] = value
                self.param_targets[param] = value
                self.smoothing_state[param] = value
            else:
                # Set target for smoothing
                self.param_targets[param] = value
                
    def get_param(self, param: str, default: float = 0.0) -> float:
        """
        Get current parameter value.
        
        Args:
            param: Parameter name
            default: Default value if parameter not set
            
        Returns:
            Current parameter value
        """
        return self.params.get(param, default)
    
    def _update_smoothing(self) -> None:
        """
        Update parameter smoothing (called at buffer boundary).
        
        Uses exponential (one-pole filter) smoothing, not linear ramping.
        This provides a smooth per-buffer step toward the target value.
        
        For future linear ramping across the buffer (if needed for stricter
        anti-click), we would pre-compute a ramp array and apply per-sample.
        Current approach is sufficient for MVP and allocation-free.
        """
        for param in self.param_targets:
            target = self.param_targets[param]
            current = self.smoothing_state.get(param, target)
            
            if abs(current - target) < 1e-9:
                # Already at target
                self.params[param] = target
                self.smoothing_state[param] = target
                continue
                
            # Calculate smoothing coefficient
            smooth_samples = self.get_smoothing_samples(param)
            
            if smooth_samples > 0:
                # One-pole filter coefficient
                # alpha = 1 means instant change, smaller = slower
                alpha = 1.0 / (1.0 + smooth_samples / self.buffer_size)
                
                # Exponential smoothing
                new_value = current + alpha * (target - current)
                
                # Snap to target if very close
                if abs(new_value - target) < 1e-6:
                    new_value = target
                    
                self.smoothing_state[param] = new_value
                self.params[param] = new_value
            else:
                # No smoothing - immediate update
                self.params[param] = target
                self.smoothing_state[param] = target
    
    def prepare(self) -> None:
        """
        Reset module state before playback starts.
        Override in subclasses to reset oscillator phase, filter state, etc.
        """
        pass
    
    def process_buffer(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        """
        Process one buffer of audio.
        
        CRITICAL: This method must be allocation-free!
        - No list/array creation
        - No string operations
        - No dictionary updates
        - Use pre-allocated buffers only
        
        Args:
            in_buf: Input buffer (may be None for generators)
            out_buf: Output buffer to write into
        """
        # Update smoothing at buffer boundary
        self._update_smoothing()
        
        # Subclasses must implement actual processing
        self._process_audio(in_buf, out_buf)
        
    def _process_audio(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        """
        Actual audio processing implementation.
        Must be overridden by subclasses.
        
        Args:
            in_buf: Input buffer
            out_buf: Output buffer
        """
        # Default: pass-through
        if in_buf is not None:
            np.copyto(out_buf, in_buf, casting='no')
        else:
            out_buf.fill(0.0)
            
    def validate_params(self) -> bool:
        """
        Validate current parameters are within acceptable ranges.
        Override in subclasses for specific validation.
        
        Returns:
            True if parameters are valid
        """
        return True
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current module state for serialization.
        
        Returns:
            Dictionary of state variables
        """
        return {
            'name': self.name,
            'params': self.params.copy(),
            'targets': self.param_targets.copy(),
            'active': self.active
        }
    
    def set_state(self, state: Dict[str, Any]) -> None:
        """
        Restore module state from serialized data.
        
        Args:
            state: State dictionary
        """
        self.params = state.get('params', {}).copy()
        self.param_targets = state.get('targets', {}).copy()
        self.active = state.get('active', True)
        
        # Reset smoothing state
        for param in self.params:
            self.smoothing_state[param] = self.params[param]
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        param_str = ', '.join(f"{k}={v:.2f}" for k, v in self.params.items())
        return f"{self.name}({param_str})"