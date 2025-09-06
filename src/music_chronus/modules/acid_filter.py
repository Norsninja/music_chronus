"""
Acid Filter (TB-303 Style) - Diode Ladder Filter with Resonance
Based on Karlsen Fast Ladder III algorithm and TB-303 analysis
"""

import numpy as np
from .base import BaseModule
from ..module_registry import register_module


@register_module('acid_filter')
class AcidFilter(BaseModule):
    """
    TB-303 style resonant lowpass filter
    
    Based on research:
    - Actually a 4-pole (24dB) diode ladder, not 18dB as myth suggests
    - Has HPF in resonance feedback path (unique 303 characteristic)
    - Resonance decreases at low cutoff frequencies (303 behavior)
    - Soft clipping for analog character
    
    Parameters:
    - cutoff: Filter cutoff frequency (20-20000 Hz)
    - resonance: Resonance amount (0-0.95, >0.9 self-oscillates)
    - env_amount: Envelope modulation depth (-1 to 1)
    - accent: Boosts both resonance and envelope (0-1)
    - decay: Envelope decay time in milliseconds
    - drive: Input saturation (1-5 for analog warmth)
    """
    
    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)
        
        # Parameters
        self.params = {
            "cutoff": 500.0,      # Hz
            "resonance": 0.0,     # 0-0.95
            "env_amount": 0.0,    # -1 to 1
            "accent": 0.0,        # 0-1 (accent boost)
            "decay": 200.0,       # ms
            "drive": 1.0,         # Input saturation
        }
        self.param_targets = self.params.copy()
        
        # Smoothing (fast for filter parameters)
        self.smoothing_samples.update({
            "cutoff": int(0.005 * sample_rate),     # 5ms
            "resonance": int(0.002 * sample_rate),  # 2ms
            "env_amount": int(0.005 * sample_rate), # 5ms
            "accent": 0,  # Instant
            "decay": 0,   # Instant
            "drive": int(0.002 * sample_rate),      # 2ms
        })
        
        # Filter state (4-pole ladder)
        self.pole1 = 0.0
        self.pole2 = 0.0
        self.pole3 = 0.0
        self.pole4 = 0.0
        
        # Resonance HPF state (303 characteristic)
        self.reso_hp = 0.0
        self.reso_hp_cutoff = 50.0 / sample_rate  # 50Hz HPF
        
        # Envelope state
        self.env_state = 0.0
        self.env_stage = 'idle'  # idle, decay
        self.env_trigger_pending = False
        
        # Pre-compute constants
        self.two_pi = 2.0 * np.pi
        self.sr_inv = 1.0 / sample_rate
        
        # Oversampling buffers (2x for better analog character)
        self.oversample_buffer = np.zeros(buffer_size * 2, dtype=np.float32)
        
    def process_buffer(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        """Process audio through 303-style filter"""
        
        # Update parameter smoothing
        self._update_smoothing()
        
        # Get current parameters
        cutoff = self.params["cutoff"]
        resonance = self.params["resonance"]
        env_amount = self.params["env_amount"]
        accent = self.params["accent"]
        decay_ms = self.params["decay"]
        drive = self.params["drive"]
        
        # Apply accent (303 style - boosts both resonance and envelope)
        if accent > 0:
            resonance = min(0.95, resonance + accent * 0.3)
            env_mod = env_amount * (1.0 + accent * 0.5)
        else:
            env_mod = env_amount
        
        # Calculate envelope decay coefficient
        decay_samples = decay_ms * 0.001 * self.sr
        decay_coeff = np.exp(-1.0 / max(decay_samples, 1.0))
        
        # Process each sample (could optimize with vectorization later)
        for i in range(len(in_buf)):
            # Update envelope
            if self.env_trigger_pending:
                self.env_state = 1.0
                self.env_stage = 'decay'
                self.env_trigger_pending = False
            elif self.env_stage == 'decay':
                self.env_state *= decay_coeff
                if self.env_state < 0.001:
                    self.env_state = 0.0
                    self.env_stage = 'idle'
            
            # Calculate modulated cutoff
            env_mod_hz = env_mod * 5000.0 * self.env_state  # ±5kHz envelope sweep
            modulated_cutoff = np.clip(cutoff + env_mod_hz, 20.0, 20000.0)
            
            # Convert cutoff to filter coefficient (normalized frequency)
            # Karlsen formula: 2*pi*cutoff/samplerate
            # But limit to 0.8 for stability
            cutoff_norm = min(0.8, self.two_pi * modulated_cutoff * self.sr_inv)
            
            # Input with drive (soft saturation)
            input_sample = in_buf[i] * drive
            if drive > 1.0:
                # Soft clip for analog warmth
                input_sample = np.tanh(input_sample * 0.7) * 1.2
            
            # Calculate resonance with 303-style behavior
            # Reduce resonance at low frequencies (HPF in feedback)
            freq_compensation = min(1.0, modulated_cutoff / 200.0)
            reso_amount = resonance * freq_compensation * 4.0  # 0-4 range like Karlsen
            
            # Get resonance feedback (from 4th pole)
            reso_feedback = self.pole4 * reso_amount
            
            # Apply HPF to resonance (303 characteristic)
            self.reso_hp += (reso_feedback - self.reso_hp) * self.reso_hp_cutoff
            reso_feedback = reso_feedback - self.reso_hp
            
            # Limit resonance to prevent blowup
            if reso_feedback > 1.0:
                reso_feedback = 1.0
            elif reso_feedback < -1.0:
                reso_feedback = -1.0
            
            # Apply resonance to input
            filtered = input_sample - reso_feedback
            
            # Soft clipping (303 diode characteristic)
            filtered_clipped = filtered
            if filtered > 1.0:
                filtered_clipped = 1.0
            elif filtered < -1.0:
                filtered_clipped = -1.0
            
            # Dynamic restoration (Karlsen technique)
            filtered = filtered + ((filtered_clipped - filtered) * 0.984)
            
            # 4-pole ladder filter
            self.pole1 += (-self.pole1 + filtered) * cutoff_norm
            self.pole2 += (-self.pole2 + self.pole1) * cutoff_norm
            self.pole3 += (-self.pole3 + self.pole2) * cutoff_norm
            self.pole4 += (-self.pole4 + self.pole3) * cutoff_norm
            
            # Output (with slight gain compensation)
            out_buf[i] = self.pole4 * 0.9
    
    def set_gate(self, gate: bool) -> None:
        """Trigger filter envelope (for acid sweeps)"""
        if gate:
            self.env_trigger_pending = True
    
    def set_accent(self, accent: bool) -> None:
        """Set accent on/off (303 style)"""
        self.set_param('accent', 1.0 if accent else 0.0, immediate=True)
    
    def reset(self) -> None:
        """Reset filter state (prevent clicks when starting)"""
        self.pole1 = 0.0
        self.pole2 = 0.0
        self.pole3 = 0.0
        self.pole4 = 0.0
        self.reso_hp = 0.0
        self.env_state = 0.0
        self.env_stage = 'idle'