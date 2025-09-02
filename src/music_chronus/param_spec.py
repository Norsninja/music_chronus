"""
Parameter Specification System for Module Framework
Phase 3: Dynamic routing and parameter metadata

Provides type-safe parameter definitions with ranges, units, and smoothing.
"""

from typing import Union, Tuple, Optional, Any
from enum import Enum
import numpy as np


class ParamType(Enum):
    """Supported parameter types"""
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    ENUM = "enum"  # For discrete choices


class SmoothingMode(Enum):
    """Parameter smoothing algorithms"""
    NONE = "none"               # Immediate change
    LINEAR = "linear"           # Linear interpolation
    EXPONENTIAL = "exponential" # One-pole lowpass filter
    LOGARITHMIC = "logarithmic" # Log-scale smoothing (for frequency)


class ParamSpec:
    """
    Specification for a module parameter.
    
    Defines type, range, units, default value, and smoothing behavior.
    Used by modules to declare their parameters for the framework.
    """
    
    def __init__(
        self,
        name: str,
        param_type: ParamType,
        default: Union[float, int, bool],
        range: Optional[Tuple[float, float]] = None,
        units: str = "",
        smoothing_mode: SmoothingMode = SmoothingMode.LINEAR,
        smoothing_time_ms: float = 5.0,
        description: str = "",
        enum_values: Optional[list] = None
    ):
        """
        Initialize a parameter specification.
        
        Args:
            name: Parameter identifier (e.g., "frequency", "cutoff")
            param_type: Type of parameter (FLOAT, INT, BOOL, ENUM)
            default: Default value
            range: (min, max) tuple for numeric types
            units: Unit string ("Hz", "dB", "ms", "%")
            smoothing_mode: How to smooth parameter changes
            smoothing_time_ms: Smoothing duration in milliseconds
            description: Human-readable description
            enum_values: List of valid values for ENUM type
        """
        self.name = name
        self.param_type = param_type
        self.default = default
        self.range = range
        self.units = units
        self.smoothing_mode = smoothing_mode
        self.smoothing_time_ms = smoothing_time_ms
        self.description = description
        self.enum_values = enum_values
        
        # Validate specification
        self._validate()
        
        # Calculate smoothing coefficient (will be set by module based on sample rate)
        self._smoothing_coeff = None
    
    def _validate(self):
        """Validate parameter specification consistency"""
        # Type checking
        if self.param_type == ParamType.FLOAT:
            if not isinstance(self.default, (float, int)):
                raise ValueError(f"Float param {self.name} needs numeric default")
            if self.range and len(self.range) != 2:
                raise ValueError(f"Range must be (min, max) tuple")
                
        elif self.param_type == ParamType.INT:
            if not isinstance(self.default, int):
                raise ValueError(f"Int param {self.name} needs integer default")
            if self.range and len(self.range) != 2:
                raise ValueError(f"Range must be (min, max) tuple")
                
        elif self.param_type == ParamType.BOOL:
            if not isinstance(self.default, bool):
                raise ValueError(f"Bool param {self.name} needs boolean default")
                
        elif self.param_type == ParamType.ENUM:
            if not self.enum_values:
                raise ValueError(f"Enum param {self.name} needs enum_values list")
            if self.default not in self.enum_values:
                raise ValueError(f"Default {self.default} not in enum_values")
    
    def clamp_value(self, value: Any) -> Any:
        """
        Clamp value to valid range (RT-safe, no branches in hot path).
        
        Args:
            value: Input value
            
        Returns:
            Clamped value within valid range
        """
        if self.param_type in [ParamType.FLOAT, ParamType.INT]:
            if self.range:
                # Branchless clamping using numpy
                return np.clip(value, self.range[0], self.range[1])
        elif self.param_type == ParamType.ENUM:
            if value not in self.enum_values:
                return self.default
        return value
    
    def calculate_smoothing_coeff(self, sample_rate: int) -> float:
        """
        Calculate smoothing coefficient for given sample rate.
        
        Args:
            sample_rate: System sample rate in Hz
            
        Returns:
            Smoothing coefficient for one-pole filter
        """
        if self.smoothing_mode == SmoothingMode.NONE:
            return 0.0
        
        # Convert time to samples
        smoothing_samples = (self.smoothing_time_ms / 1000.0) * sample_rate
        
        if self.smoothing_mode == SmoothingMode.LINEAR:
            # Linear interpolation step size
            return 1.0 / max(1.0, smoothing_samples)
            
        elif self.smoothing_mode in [SmoothingMode.EXPONENTIAL, SmoothingMode.LOGARITHMIC]:
            # One-pole lowpass coefficient
            # coeff = exp(-1 / tau) where tau is time constant in samples
            return np.exp(-1.0 / max(1.0, smoothing_samples))
        
        return 0.99  # Safe default
    
    def to_dict(self) -> dict:
        """
        Convert specification to dictionary for serialization.
        
        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "type": self.param_type.value,
            "default": self.default,
            "range": self.range,
            "units": self.units,
            "smoothing_mode": self.smoothing_mode.value,
            "smoothing_time_ms": self.smoothing_time_ms,
            "description": self.description,
            "enum_values": self.enum_values
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ParamSpec':
        """
        Create ParamSpec from dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ParamSpec instance
        """
        return cls(
            name=data["name"],
            param_type=ParamType(data["type"]),
            default=data["default"],
            range=data.get("range"),
            units=data.get("units", ""),
            smoothing_mode=SmoothingMode(data.get("smoothing_mode", "linear")),
            smoothing_time_ms=data.get("smoothing_time_ms", 5.0),
            description=data.get("description", ""),
            enum_values=data.get("enum_values")
        )


# Common parameter specifications (presets for convenience)
class CommonParams:
    """Commonly used parameter specifications"""
    
    @staticmethod
    def frequency(default: float = 440.0) -> ParamSpec:
        """Standard frequency parameter (20Hz - 20kHz)"""
        return ParamSpec(
            name="frequency",
            param_type=ParamType.FLOAT,
            default=default,
            range=(20.0, 20000.0),
            units="Hz",
            smoothing_mode=SmoothingMode.EXPONENTIAL,
            smoothing_time_ms=5.0,
            description="Frequency in Hertz"
        )
    
    @staticmethod
    def gain(default: float = 0.5) -> ParamSpec:
        """Standard gain parameter (0-1)"""
        return ParamSpec(
            name="gain",
            param_type=ParamType.FLOAT,
            default=default,
            range=(0.0, 1.0),
            units="",
            smoothing_mode=SmoothingMode.LINEAR,
            smoothing_time_ms=5.0,
            description="Gain (0-1)"
        )
    
    @staticmethod
    def cutoff_frequency(default: float = 1000.0) -> ParamSpec:
        """Filter cutoff frequency"""
        return ParamSpec(
            name="cutoff",
            param_type=ParamType.FLOAT,
            default=default,
            range=(20.0, 20000.0),
            units="Hz",
            smoothing_mode=SmoothingMode.LOGARITHMIC,
            smoothing_time_ms=10.0,
            description="Filter cutoff frequency"
        )
    
    @staticmethod
    def resonance(default: float = 1.0) -> ParamSpec:
        """Filter resonance/Q parameter"""
        return ParamSpec(
            name="resonance",
            param_type=ParamType.FLOAT,
            default=default,
            range=(0.5, 25.0),
            units="",
            smoothing_mode=SmoothingMode.LINEAR,
            smoothing_time_ms=5.0,
            description="Filter resonance (Q factor)"
        )
    
    @staticmethod
    def attack_time(default: float = 10.0) -> ParamSpec:
        """ADSR attack time"""
        return ParamSpec(
            name="attack",
            param_type=ParamType.FLOAT,
            default=default,
            range=(0.1, 5000.0),
            units="ms",
            smoothing_mode=SmoothingMode.NONE,  # No smoothing for envelope times
            smoothing_time_ms=0.0,
            description="Attack time in milliseconds"
        )
    
    @staticmethod
    def waveform() -> ParamSpec:
        """Oscillator waveform selection"""
        return ParamSpec(
            name="waveform",
            param_type=ParamType.ENUM,
            default="sine",
            enum_values=["sine", "saw", "square", "triangle", "noise"],
            smoothing_mode=SmoothingMode.NONE,
            description="Oscillator waveform"
        )
    
    @staticmethod
    def gate() -> ParamSpec:
        """Gate on/off parameter"""
        return ParamSpec(
            name="gate",
            param_type=ParamType.BOOL,
            default=False,
            smoothing_mode=SmoothingMode.NONE,
            description="Gate signal (on/off)"
        )