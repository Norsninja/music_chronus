"""
LFO (Low Frequency Oscillator) Module
Zero-allocation modulation source for parameter control
"""

import numpy as np
from typing import Optional
from .base import BaseModule


class LFO(BaseModule):
    """
    Low Frequency Oscillator for modulation
    
    Parameters:
    - freq: LFO frequency (0.01-20 Hz)
    - depth: Modulation depth (0.0-1.0)
    - shape: Waveform (0=sine, 1=triangle, 2=square, 3=saw)
    - offset: DC offset (-1.0 to 1.0)
    """
    
    # Waveform shapes
    SHAPE_SINE = 0
    SHAPE_TRIANGLE = 1
    SHAPE_SQUARE = 2
    SHAPE_SAW = 3
    
    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)
        
        # LFO state
        self.phase = 0.0  # Current phase [0, 1)
        self.phase_increment = 0.0
        
        # Parameters with defaults
        self.frequency = 1.0  # Hz
        self.depth = 1.0  # Full depth
        self.shape = self.SHAPE_SINE
        self.offset = 0.0
        
        # Parameter targets for smoothing
        self.target_frequency = 1.0
        self.target_depth = 1.0
        self.target_offset = 0.0
        
        # Smoothing rates (faster than audio rate since LFO)
        self.freq_smooth = 0.99
        self.depth_smooth = 0.95
        self.offset_smooth = 0.95
        
        # Pre-allocate working buffer
        self.work_buffer = np.zeros(buffer_size, dtype=np.float32)
        
        # Update phase increment
        self._update_phase_increment()
    
    def _update_phase_increment(self):
        """Update phase increment based on frequency"""
        # Clamp frequency to valid range
        freq = np.clip(self.frequency, 0.01, 20.0)
        self.phase_increment = freq / self.sample_rate
    
    def set_param(self, name: str, value: float, immediate: bool = False) -> None:
        """Set LFO parameter"""
        if name == "freq":
            self.target_frequency = np.clip(value, 0.01, 20.0)
            if immediate:
                self.frequency = self.target_frequency
                self._update_phase_increment()
        
        elif name == "depth":
            self.target_depth = np.clip(value, 0.0, 1.0)
            if immediate:
                self.depth = self.target_depth
        
        elif name == "shape":
            # Shape is discrete, always immediate
            self.shape = int(np.clip(value, 0, 3))
        
        elif name == "offset":
            self.target_offset = np.clip(value, -1.0, 1.0)
            if immediate:
                self.offset = self.target_offset
        
        elif name == "reset":
            # Reset phase to 0
            self.phase = 0.0
    
    def get_param(self, name: str) -> Optional[float]:
        """Get LFO parameter value"""
        if name == "freq":
            return self.frequency
        elif name == "depth":
            return self.depth
        elif name == "shape":
            return self.shape
        elif name == "offset":
            return self.offset
        elif name == "phase":
            return self.phase
        return None
    
    def process(self, input_buffer: np.ndarray) -> np.ndarray:
        """
        Generate LFO signal
        Note: LFO typically doesn't process input, it generates control signal
        Output range: -1.0 to 1.0 (scaled by depth and offset)
        """
        output = self.output_buffer
        
        # Process each sample
        for i in range(self.buffer_size):
            # Smooth parameters
            if self.frequency != self.target_frequency:
                self.frequency += (self.target_frequency - self.frequency) * (1.0 - self.freq_smooth)
                self._update_phase_increment()
            
            if self.depth != self.target_depth:
                self.depth += (self.target_depth - self.depth) * (1.0 - self.depth_smooth)
            
            if self.offset != self.target_offset:
                self.offset += (self.target_offset - self.offset) * (1.0 - self.offset_smooth)
            
            # Generate waveform based on shape
            if self.shape == self.SHAPE_SINE:
                # Sine wave
                sample = np.sin(2.0 * np.pi * self.phase)
            
            elif self.shape == self.SHAPE_TRIANGLE:
                # Triangle wave
                if self.phase < 0.25:
                    sample = 4.0 * self.phase
                elif self.phase < 0.75:
                    sample = 2.0 - 4.0 * self.phase
                else:
                    sample = 4.0 * self.phase - 4.0
            
            elif self.shape == self.SHAPE_SQUARE:
                # Square wave
                sample = 1.0 if self.phase < 0.5 else -1.0
            
            elif self.shape == self.SHAPE_SAW:
                # Sawtooth wave
                sample = 2.0 * self.phase - 1.0
            
            else:
                sample = 0.0
            
            # Apply depth and offset
            output[i] = sample * self.depth + self.offset
            
            # Advance phase
            self.phase += self.phase_increment
            if self.phase >= 1.0:
                self.phase -= 1.0
        
        return output
    
    def reset(self) -> None:
        """Reset LFO to initial state"""
        self.phase = 0.0
        self.frequency = 1.0
        self.depth = 1.0
        self.shape = self.SHAPE_SINE
        self.offset = 0.0
        self.target_frequency = 1.0
        self.target_depth = 1.0
        self.target_offset = 0.0
        self._update_phase_increment()
        self.output_buffer.fill(0)
    
    def get_modulation_value(self) -> float:
        """
        Get current LFO value for external modulation
        Useful for modulating other parameters
        """
        if self.shape == self.SHAPE_SINE:
            value = np.sin(2.0 * np.pi * self.phase)
        elif self.shape == self.SHAPE_TRIANGLE:
            if self.phase < 0.25:
                value = 4.0 * self.phase
            elif self.phase < 0.75:
                value = 2.0 - 4.0 * self.phase
            else:
                value = 4.0 * self.phase - 4.0
        elif self.shape == self.SHAPE_SQUARE:
            value = 1.0 if self.phase < 0.5 else -1.0
        elif self.shape == self.SHAPE_SAW:
            value = 2.0 * self.phase - 1.0
        else:
            value = 0.0
        
        return value * self.depth + self.offset