"""
Simple LFO module for Music Chronus
Follows established module patterns with schema integration
Provides modulation sources for filter and amplitude control
"""

from pyo import *

class SimpleLFOModule:
    """
    Low-frequency oscillator for modulation
    Provides sine wave LFO with rate and depth controls
    """
    
    def __init__(self, module_id="lfo1", server=None):
        """
        Initialize LFO module following DistortionModule pattern
        
        Args:
            module_id: Identifier for this module (e.g., "lfo1", "lfo2")
            server: Pyo server instance (uses default if None)
        """
        self.module_id = module_id
        self.server = server  # Not needed but kept for consistency
        
        # Parameter smoothing time (20ms for zipper-free control)
        self.smooth_time = 0.02
        
        # Rate control (0.01-10 Hz)
        self.rate_sig = Sig(0.25)  # Default 0.25Hz for wobble
        self.rate = SigTo(self.rate_sig, time=self.smooth_time)
        
        # Depth control (0-1, modulation amount)
        self.depth_sig = Sig(0.7)  # Default 70% depth
        self.depth = SigTo(self.depth_sig, time=self.smooth_time)
        
        # LFO oscillator - using Sine for smooth modulation
        # TODO: Add waveform selection in v2 (requires multiple oscillators)
        self.lfo_osc = Sine(freq=self.rate, mul=1)
        
        # Convert bipolar (-1 to +1) to unipolar (0 to 1)
        self.unipolar = (self.lfo_osc + 1) * 0.5
        
        # Apply depth control
        self.with_depth = self.unipolar * self.depth
        
        # Final output ready for scaling
        self.output = self.with_depth
        
    def set_rate(self, rate):
        """Set LFO rate in Hz
        
        0.01-0.5: Slow sweeps
        0.5-2.0: Wobble bass
        2.0-8.0: Tremolo
        8.0-10.0: Fast modulation
        """
        rate = max(0.01, min(10.0, float(rate)))
        self.rate_sig.value = rate
    
    def set_depth(self, depth):
        """Set modulation depth (0-1)
        
        0: No modulation
        0.5: Moderate modulation
        1: Full modulation range
        """
        depth = max(0.0, min(1.0, float(depth)))
        self.depth_sig.value = depth
    
    def get_scaled_for_filter(self, hz_range=800):
        """Get LFO output scaled for filter frequency modulation
        
        Args:
            hz_range: Maximum Hz deviation from center (default ±800Hz)
        
        Returns:
            PyoObject outputting -hz_range to +hz_range
        """
        return Scale(
            self.output,
            inmin=0, inmax=1,
            outmin=-hz_range, outmax=hz_range
        )
    
    def get_scaled_for_amp(self, min_amp=0.2):
        """Get LFO output scaled for amplitude modulation
        
        Args:
            min_amp: Minimum amplitude (default 0.2, never fully off)
        
        Returns:
            PyoObject outputting min_amp to 1.0
        """
        return Scale(
            self.output,
            inmin=0, inmax=1,
            outmin=min_amp, outmax=1.0
        )
    
    def get_status(self):
        """Get current module status for pattern save/load"""
        return {
            'module_id': self.module_id,
            'rate': self.rate_sig.value,
            'depth': self.depth_sig.value
        }
    
    def get_schema(self):
        """Get parameter schema for registry integration"""
        return {
            "name": f"LFO ({self.module_id})",
            "type": "lfo",
            "params": {
                "rate": {
                    "type": "float",
                    "min": 0.01,
                    "max": 10.0,
                    "default": 0.25,
                    "smoothing_ms": 20,
                    "unit": "Hz",
                    "notes": "0.01-0.5: slow, 0.5-2: wobble, 2-8: tremolo"
                },
                "depth": {
                    "type": "float",
                    "min": 0,
                    "max": 1,
                    "default": 0.7,
                    "smoothing_ms": 20,
                    "notes": "Modulation amount: 0=none, 1=full"
                }
            },
            "notes": "Simple sine LFO for modulation"
        }
    
    def get_output(self):
        """Get raw LFO output signal (0-1 range with depth applied)"""
        return self.output