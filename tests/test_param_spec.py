"""
Unit tests for Parameter Specification System
Phase 3: Module Framework
"""

import unittest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from music_chronus.param_spec import ParamSpec, ParamType, SmoothingMode, CommonParams


class TestParamSpec(unittest.TestCase):
    """Test ParamSpec class functionality"""
    
    def test_float_param_creation(self):
        """Test creating a float parameter"""
        param = ParamSpec(
            name="frequency",
            param_type=ParamType.FLOAT,
            default=440.0,
            range=(20.0, 20000.0),
            units="Hz"
        )
        
        self.assertEqual(param.name, "frequency")
        self.assertEqual(param.param_type, ParamType.FLOAT)
        self.assertEqual(param.default, 440.0)
        self.assertEqual(param.range, (20.0, 20000.0))
        self.assertEqual(param.units, "Hz")
    
    def test_value_clamping(self):
        """Test that values are clamped to valid range"""
        param = ParamSpec(
            name="gain",
            param_type=ParamType.FLOAT,
            default=0.5,
            range=(0.0, 1.0)
        )
        
        # Test clamping
        self.assertEqual(param.clamp_value(-0.5), 0.0)
        self.assertEqual(param.clamp_value(0.5), 0.5)
        self.assertEqual(param.clamp_value(1.5), 1.0)
    
    def test_enum_param(self):
        """Test enum parameter type"""
        param = ParamSpec(
            name="waveform",
            param_type=ParamType.ENUM,
            default="sine",
            enum_values=["sine", "saw", "square"]
        )
        
        self.assertEqual(param.default, "sine")
        self.assertIn("sine", param.enum_values)
        
        # Invalid enum value should return default
        self.assertEqual(param.clamp_value("invalid"), "sine")
        self.assertEqual(param.clamp_value("saw"), "saw")
    
    def test_smoothing_coefficient_calculation(self):
        """Test smoothing coefficient calculation"""
        param = ParamSpec(
            name="cutoff",
            param_type=ParamType.FLOAT,
            default=1000.0,
            smoothing_mode=SmoothingMode.EXPONENTIAL,
            smoothing_time_ms=10.0
        )
        
        # Calculate coefficient for 44100 Hz sample rate
        coeff = param.calculate_smoothing_coeff(44100)
        
        # Should be between 0 and 1
        self.assertGreater(coeff, 0.0)
        self.assertLess(coeff, 1.0)
        
        # Longer smoothing time should give coefficient closer to 1
        param2 = ParamSpec(
            name="cutoff2",
            param_type=ParamType.FLOAT,
            default=1000.0,
            smoothing_mode=SmoothingMode.EXPONENTIAL,
            smoothing_time_ms=100.0
        )
        coeff2 = param2.calculate_smoothing_coeff(44100)
        
        self.assertGreater(coeff2, coeff)
    
    def test_no_smoothing(self):
        """Test NONE smoothing mode"""
        param = ParamSpec(
            name="gate",
            param_type=ParamType.BOOL,
            default=False,
            smoothing_mode=SmoothingMode.NONE
        )
        
        coeff = param.calculate_smoothing_coeff(44100)
        self.assertEqual(coeff, 0.0)
    
    def test_serialization(self):
        """Test to_dict and from_dict"""
        param = CommonParams.frequency(880.0)
        
        # Serialize
        data = param.to_dict()
        self.assertEqual(data["name"], "frequency")
        self.assertEqual(data["default"], 880.0)
        self.assertEqual(data["units"], "Hz")
        
        # Deserialize
        param2 = ParamSpec.from_dict(data)
        self.assertEqual(param2.name, param.name)
        self.assertEqual(param2.default, param.default)
        self.assertEqual(param2.range, param.range)
    
    def test_common_params(self):
        """Test CommonParams helper functions"""
        freq = CommonParams.frequency()
        self.assertEqual(freq.units, "Hz")
        self.assertEqual(freq.range, (20.0, 20000.0))
        
        gain = CommonParams.gain()
        self.assertEqual(gain.range, (0.0, 1.0))
        
        cutoff = CommonParams.cutoff_frequency()
        self.assertEqual(cutoff.smoothing_mode, SmoothingMode.LOGARITHMIC)
        
        gate = CommonParams.gate()
        self.assertEqual(gate.param_type, ParamType.BOOL)
    
    def test_validation(self):
        """Test parameter validation"""
        # Invalid: float param with non-numeric default
        with self.assertRaises(ValueError):
            ParamSpec(
                name="bad",
                param_type=ParamType.FLOAT,
                default="not_a_number"
            )
        
        # Invalid: enum without values
        with self.assertRaises(ValueError):
            ParamSpec(
                name="bad_enum",
                param_type=ParamType.ENUM,
                default="value"
            )


if __name__ == '__main__':
    unittest.main()