"""
BiquadFilter - Transposed Direct Form II filter module (Phase 2)
- Processor: filters in_buf, writes to out_buf
- Zero allocations in process_buffer()
- RBJ cookbook coefficients
- State continuity across buffers
"""

import numpy as np
from .base import BaseModule


class BiquadFilter(BaseModule):
    """
    Transposed Direct Form II (DF2T) biquad filter.
    
    Params:
    - mode: Filter type (0=lowpass, 1=highpass, 2=bandpass) (default 0)
    - cutoff: Cutoff frequency in Hz (default 1000.0)
    - q: Resonance/Q factor (default 0.707)
    
    Uses RBJ Audio Cookbook coefficients for standard filter responses.
    """
    
    # Filter modes
    MODE_LOWPASS = 0
    MODE_HIGHPASS = 1
    MODE_BANDPASS = 2

    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)

        # Parameters
        self.params = {
            "mode": 0,
            "cutoff": 1000.0,
            "q": 0.707,  # Butterworth response
        }
        self.param_targets = self.params.copy()

        # Smoothing config (smooth cutoff and Q to prevent artifacts)
        self.smoothing_samples.update({
            "mode": 0,  # No smoothing for mode switches
            "cutoff": int(0.010 * sample_rate),  # 10ms
            "q": int(0.010 * sample_rate),  # 10ms
            "default": int(0.010 * sample_rate),
        })

        # DF2T state variables (float64 for stability)
        self._z1 = 0.0
        self._z2 = 0.0
        
        # Filter coefficients
        self._b0 = 1.0
        self._b1 = 0.0
        self._b2 = 0.0
        self._a1 = 0.0
        self._a2 = 0.0
        
        # Cached values for coefficient calculation
        self._last_cutoff = -1.0
        self._last_q = -1.0
        self._last_mode = -1
        
        # Precomputed constants
        self._nyquist = sample_rate * 0.5
        self._two_pi_over_sr = 2.0 * np.pi / float(sample_rate)
        
        # Denormal prevention threshold (tighter per Senior Dev)
        self._denormal_threshold = 1e-20
        
        # Initialize coefficients
        self._update_coefficients()

    def prepare(self) -> None:
        """Reset filter state before playback."""
        self._z1 = 0.0
        self._z2 = 0.0
        self._update_coefficients()

    def validate_params(self) -> bool:
        """Clamp params to safe ranges."""
        # Mode: 0-2
        mode = int(self.params.get("mode", 0))
        mode = max(0, min(2, mode))
        self.params["mode"] = mode
        
        # Cutoff: 10Hz to Nyquist-10Hz
        cutoff = float(self.params.get("cutoff", 1000.0))
        cutoff = max(10.0, min(self._nyquist - 10.0, cutoff))
        self.params["cutoff"] = cutoff
        
        # Q: 0.1 to 20 (reasonable range)
        q = float(self.params.get("q", 0.707))
        q = max(0.1, min(20.0, q))
        self.params["q"] = q
        
        return True

    def _update_coefficients(self) -> None:
        """
        Calculate RBJ cookbook biquad coefficients.
        Only recalculates if parameters have changed.
        """
        mode = int(self.params["mode"])
        cutoff = float(self.params["cutoff"])
        q = float(self.params["q"])
        
        # Skip if nothing changed
        if (cutoff == self._last_cutoff and 
            q == self._last_q and 
            mode == self._last_mode):
            return
        
        self._last_cutoff = cutoff
        self._last_q = q
        self._last_mode = mode
        
        # Pre-warp frequency
        w0 = self._two_pi_over_sr * cutoff
        cos_w0 = np.cos(w0)
        sin_w0 = np.sin(w0)
        alpha = sin_w0 / (2.0 * q)
        
        # Calculate coefficients based on filter mode (RBJ cookbook)
        if mode == self.MODE_LOWPASS:
            # Low-pass
            b0 = (1.0 - cos_w0) / 2.0
            b1 = 1.0 - cos_w0
            b2 = (1.0 - cos_w0) / 2.0
            a0 = 1.0 + alpha
            a1 = -2.0 * cos_w0
            a2 = 1.0 - alpha
            
        elif mode == self.MODE_HIGHPASS:
            # High-pass
            b0 = (1.0 + cos_w0) / 2.0
            b1 = -(1.0 + cos_w0)
            b2 = (1.0 + cos_w0) / 2.0
            a0 = 1.0 + alpha
            a1 = -2.0 * cos_w0
            a2 = 1.0 - alpha
            
        else:  # MODE_BANDPASS
            # Band-pass (constant 0 dB peak gain)
            b0 = alpha
            b1 = 0.0
            b2 = -alpha
            a0 = 1.0 + alpha
            a1 = -2.0 * cos_w0
            a2 = 1.0 - alpha
        
        # Normalize coefficients (a0 = 1)
        inv_a0 = 1.0 / a0
        self._b0 = b0 * inv_a0
        self._b1 = b1 * inv_a0
        self._b2 = b2 * inv_a0
        self._a1 = a1 * inv_a0
        self._a2 = a2 * inv_a0

    def _process_audio(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        """
        Apply DF2T biquad filter sample-by-sample.
        Zero allocations - processes directly from in_buf to out_buf.
        
        Transposed Direct Form II structure:
        y[n] = b0*x[n] + z1[n-1]
        z1[n] = b1*x[n] - a1*y[n] + z2[n-1]
        z2[n] = b2*x[n] - a2*y[n]
        """
        # Validate parameters and update coefficients if needed
        self.validate_params()
        self._update_coefficients()
        
        # Process each sample (DF2T structure)
        # Sample-by-sample required for state continuity
        for i in range(self.buffer_size):
            # Input sample
            x = in_buf[i] if in_buf is not None else 0.0
            
            # Transposed Direct Form II
            y = self._b0 * x + self._z1
            self._z1 = self._b1 * x - self._a1 * y + self._z2
            self._z2 = self._b2 * x - self._a2 * y
            
            # Denormal prevention
            if abs(self._z1) < self._denormal_threshold:
                self._z1 = 0.0
            if abs(self._z2) < self._denormal_threshold:
                self._z2 = 0.0
            
            # Output sample
            out_buf[i] = y
    
    def get_state(self) -> dict:
        """Get current module state for debugging."""
        state = super().get_state()
        state.update({
            "filter_type": ["lowpass", "highpass", "bandpass"][int(self.params["mode"])],
            "coefficients": {
                "b0": self._b0,
                "b1": self._b1,
                "b2": self._b2,
                "a1": self._a1,
                "a2": self._a2,
            },
            "state_vars": {
                "z1": self._z1,
                "z2": self._z2,
            }
        })
        return state