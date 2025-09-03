"""
SimpleSine - Allocation-free sine oscillator module (Phase 2)
- Generator: ignores in_buf, writes to out_buf
- Zero allocations in process_buffer()
- Boundary-only parameter updates (via BaseModule smoothing hook)
- Phase continuity across buffers; periodic wrap to avoid drift
"""

import numpy as np
from .base import BaseModule
from ..module_registry import register_module


@register_module('simple_sine')
class SimpleSine(BaseModule):
    """
    Phase accumulator sine oscillator with zero allocations.
    
    Params (targets applied at buffer boundaries):
    - freq (Hz, float): oscillator frequency (default 440.0), clamped to (0.1 .. Nyquist - 10)
    - gain (0..1, float): output gain (default 0.5)
    """

    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)

        # Parameters (float64 for precision in state)
        self.params = {
            "freq": 440.0,
            "gain": 0.5,
        }
        self.param_targets = self.params.copy()

        # Smoothing config (in samples)
        # Keep gain click-free; no smoothing for freq by default (glide can be added later)
        self.smoothing_samples.update(
            {
                "gain": int(0.005 * sample_rate),  # ~5ms
                "freq": 0,
                "default": int(0.005 * sample_rate),
            }
        )

        # Precomputed constants/state
        self._two_pi = 2.0 * np.pi
        self._two_pi_over_sr = self._two_pi / float(sample_rate)
        self._phase = 0.0  # float64 phase accumulator

        # Pre-allocated phase index (used to compute per-sample phase offsets)
        # Note: We write phases and samples directly into out_buf to avoid temp arrays.
        self._phase_index = np.arange(buffer_size, dtype=np.float32)

        # Wrap threshold: wrap every 2π to keep precision
        self._wrap_threshold = self._two_pi

    def prepare(self) -> None:
        """Reset oscillator state before playback."""
        self._phase = 0.0

    def validate_params(self) -> bool:
        """Clamp params to safe ranges."""
        nyquist = 0.5 * float(self.sr)
        # Clamp frequency: (0.1 .. Nyquist - 10)
        f = float(self.params.get("freq", 440.0))
        f = max(0.1, min(nyquist - 10.0, f))
        self.params["freq"] = f

        # Clamp gain: [0..1]
        g = float(self.params.get("gain", 0.5))
        g = 0.0 if g < 0.0 else (1.0 if g > 1.0 else g)
        self.params["gain"] = g
        return True

    def _process_audio(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        """
        Zero-allocation oscillator:
        - Compute phase for each sample into out_buf (reuse as working buffer)
        - Take sine in-place into out_buf
        - Apply gain in-place
        """
        # Ensure parameters are within safe ranges
        self.validate_params()

        # Compute phase increment at buffer boundary
        freq = float(self.params["freq"])
        phase_inc = self._two_pi_over_sr * freq

        # Build per-sample phases directly into out_buf to avoid temporary arrays:
        # out_buf[:] = phase_index * phase_inc + current_phase
        # Cast phase_inc to float32 to avoid hidden temp array allocation
        phase_inc_f32 = np.float32(phase_inc)
        np.multiply(self._phase_index, phase_inc_f32, out=out_buf)  # out_buf = index * inc
        out_buf += np.float32(self._phase)                          # out_buf = out_buf + phase

        # Sine in-place
        np.sin(out_buf, out=out_buf)

        # Apply gain
        gain = float(self.params["gain"])
        if gain != 1.0:
            out_buf *= gain

        # Advance phase by one buffer
        self._phase += phase_inc * self.buffer_size

        # Wrap to keep precision
        if self._phase > self._wrap_threshold:
            self._phase = self._phase % self._two_pi