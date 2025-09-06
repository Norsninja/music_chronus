"""
Distortion Module - Various types of audio destruction
For dirty bass, aggressive leads, and general nastiness
"""

import numpy as np
from .base import BaseModule
from ..module_registry import register_module


@register_module('distortion')
class Distortion(BaseModule):
    """
    Multi-mode distortion processor
    
    Modes:
    0 - Soft clip (tube-like saturation)
    1 - Hard clip (aggressive digital)
    2 - Foldback (wavefolding)
    3 - Bitcrush (lo-fi digital)
    
    Parameters:
    - drive: Input gain (1.0-50.0)
    - mix: Dry/wet blend (0.0-1.0)
    - mode: Distortion type (0-3)
    - tone: Post-distortion tone control (0.0-1.0)
    """
    
    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)
        
        # Parameters
        self.params = {
            "drive": 1.0,    # No distortion at 1.0
            "mix": 1.0,      # Full wet
            "mode": 0,       # Soft clip
            "tone": 0.5,     # Neutral tone
        }
        self.param_targets = self.params.copy()
        
        # Smoothing (fast for distortion parameters)
        self.smoothing_samples.update({
            "drive": int(0.002 * sample_rate),  # 2ms
            "mix": int(0.005 * sample_rate),    # 5ms
            "tone": int(0.005 * sample_rate),   # 5ms
            "mode": 0,  # Instant switching
        })
        
        # Pre-allocate working buffers
        self.dry_buffer = np.zeros(buffer_size, dtype=np.float32)
        self.wet_buffer = np.zeros(buffer_size, dtype=np.float32)
        
        # Tone control (simple one-pole filter)
        self.tone_z1 = 0.0
        
        # Bitcrusher state
        self.bit_depth = 8  # bits
        self.sample_rate_reduction = 4  # factor
        self.bit_counter = 0
        self.held_sample = 0.0
    
    def process_buffer(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        """Process audio with selected distortion type"""
        
        # Update parameter smoothing at buffer boundary
        self._update_smoothing()
        
        # Get current parameters
        drive = self.params["drive"]
        mix = self.params["mix"]
        mode = int(self.params["mode"])
        tone = self.params["tone"]
        
        # Store dry signal
        np.copyto(self.dry_buffer, in_buf)
        
        # Apply drive (pre-gain)
        np.multiply(in_buf, drive, out=self.wet_buffer)
        
        # Apply selected distortion mode
        if mode == 0:  # Soft clip
            self._soft_clip(self.wet_buffer)
        elif mode == 1:  # Hard clip
            self._hard_clip(self.wet_buffer)
        elif mode == 2:  # Foldback
            self._foldback(self.wet_buffer)
        elif mode == 3:  # Bitcrush
            self._bitcrush(self.wet_buffer)
        
        # Apply tone control
        self._apply_tone(self.wet_buffer, tone)
        
        # Normalize output level (distortion can get loud!)
        np.multiply(self.wet_buffer, 0.7 / max(drive, 1.0), out=self.wet_buffer)
        
        # Mix dry and wet signals
        if mix >= 0.999:
            # Full wet
            np.copyto(out_buf, self.wet_buffer)
        elif mix <= 0.001:
            # Full dry
            np.copyto(out_buf, self.dry_buffer)
        else:
            # Blend
            np.multiply(self.dry_buffer, 1.0 - mix, out=out_buf)
            np.add(out_buf, self.wet_buffer * mix, out=out_buf)
    
    def _soft_clip(self, buffer: np.ndarray) -> None:
        """Soft clipping - smooth saturation like tube distortion"""
        # Hyperbolic tangent saturation
        np.tanh(buffer * 0.7, out=buffer)
    
    def _hard_clip(self, buffer: np.ndarray) -> None:
        """Hard clipping - aggressive digital distortion"""
        np.clip(buffer, -1.0, 1.0, out=buffer)
    
    def _foldback(self, buffer: np.ndarray) -> None:
        """Wavefolding - creates complex harmonics"""
        # Fold the signal back on itself when it exceeds threshold
        threshold = 0.7
        
        # Find samples that exceed threshold
        over_positive = buffer > threshold
        over_negative = buffer < -threshold
        
        # Fold them back
        buffer[over_positive] = threshold * 2 - buffer[over_positive]
        buffer[over_negative] = -threshold * 2 - buffer[over_negative]
        
        # Apply again for double folding on extreme values
        over_positive = buffer > threshold
        over_negative = buffer < -threshold
        buffer[over_positive] = threshold * 2 - buffer[over_positive]
        buffer[over_negative] = -threshold * 2 - buffer[over_negative]
        
        # Final clip to prevent runaway
        np.clip(buffer, -1.5, 1.5, out=buffer)
    
    def _bitcrush(self, buffer: np.ndarray) -> None:
        """Bit crushing - lo-fi digital degradation"""
        # Reduce bit depth
        bit_scale = 2 ** (self.bit_depth - 1)
        
        # Quantize to reduced bit depth
        np.round(buffer * bit_scale, out=buffer)
        np.divide(buffer, bit_scale, out=buffer)
        
        # Sample rate reduction (sample and hold)
        for i in range(len(buffer)):
            if self.bit_counter == 0:
                self.held_sample = buffer[i]
            buffer[i] = self.held_sample
            
            self.bit_counter += 1
            if self.bit_counter >= self.sample_rate_reduction:
                self.bit_counter = 0
    
    def _apply_tone(self, buffer: np.ndarray, tone: float) -> None:
        """Simple one-pole lowpass filter for tone control"""
        # Convert tone (0-1) to filter coefficient
        # 0 = very dark (heavy filtering)
        # 1 = very bright (minimal filtering)
        cutoff = 200.0 + tone * 10000.0  # 200Hz to 10.2kHz range
        
        # One-pole filter coefficient
        alpha = 1.0 - np.exp(-2.0 * np.pi * cutoff / self.sr)
        
        # Apply filter
        for i in range(len(buffer)):
            self.tone_z1 = buffer[i] * alpha + self.tone_z1 * (1.0 - alpha)
            buffer[i] = self.tone_z1
    
    def set_gate(self, gate: bool) -> None:
        """Reset bitcrusher on gate (for rhythmic effect)"""
        if gate:
            self.bit_counter = 0
            self.held_sample = 0.0