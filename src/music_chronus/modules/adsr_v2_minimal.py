"""
ADSR v2 Minimal - Pure RC envelope, no defensive code
Following "Make It Work First" manifesto
"""

import numpy as np
from math import exp
from .base import BaseModule
from ..module_registry import register_module


@register_module('adsr_v2')
class ADSRv2(BaseModule):
    """
    Minimal RC-based ADSR envelope.
    Just the physics, nothing else.
    """
    
    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)
        
        # State - that's it!
        self.level = 0.0
        self.target = 0.0
        self.alpha = 0.0
        self.gate = False
        self.in_decay = False
        
        # Parameters (in milliseconds, matching codebase convention)
        self.params = {
            "attack": 10.0,    # 10ms
            "decay": 100.0,    # 100ms
            "sustain": 0.7,    # 0-1
            "release": 200.0,  # 200ms
        }
        self.param_targets = self.params.copy()  # Required by BaseModule
        
        # Configure smoothing (no smoothing for ADSR params)
        self.smoothing_samples.update({
            "attack": 0,
            "decay": 0,
            "sustain": 0,
            "release": 0,
            "default": 0,
        })
        
        # Pre-computed alphas (will calculate on param change)
        self.alpha_attack = 0.0
        self.alpha_decay = 0.0
        self.alpha_release = 0.0
        self._update_alphas()
        
    def _update_alphas(self):
        """Pre-compute RC alphas from time constants"""
        # RC formula: alpha = 1 - exp(-1/(tau * sr))
        # Convert milliseconds to seconds
        attack_sec = self.params["attack"] / 1000.0
        decay_sec = self.params["decay"] / 1000.0
        release_sec = self.params["release"] / 1000.0
        
        # Prevent division by zero
        attack_sec = max(0.0001, attack_sec)  # Min 0.1ms
        decay_sec = max(0.0001, decay_sec)
        release_sec = max(0.0001, release_sec)
        
        self.alpha_attack = 1.0 - exp(-1.0 / (attack_sec * self.sr))
        self.alpha_decay = 1.0 - exp(-1.0 / (decay_sec * self.sr))
        self.alpha_release = 1.0 - exp(-1.0 / (release_sec * self.sr))
    
    def set_gate(self, gate: bool):
        """Gate control - that's all we need"""
        self.gate = gate
        
    def _process_audio(self, in_buf: np.ndarray, out_buf: np.ndarray):
        """
        The entire ADSR - one RC equation doing everything
        """
        # Update alphas if params changed
        self._update_alphas()
        
        # Gate is controlled by set_gate() method, NOT params
        # This was the bug - we were overriding the gate every buffer!
        
        # Debug output if requested
        import os
        if os.environ.get('CHRONUS_DEBUG'):
            print(f"ADSR: gate={self.gate}, level={self.level:.3f}, alpha={self.alpha:.6f}")
        
        # Process each sample
        for i in range(self.buffer_size):
            # Gate logic - just set target and alpha
            if self.gate and not self.in_decay:
                # Going up
                self.target = 1.0
                self.alpha = self.alpha_attack
                
                # Hit the top? Start decay
                if self.level > 0.99:
                    self.target = self.params["sustain"]
                    self.alpha = self.alpha_decay
                    self.in_decay = True
                    
            elif not self.gate:
                # Gate off - release
                self.target = 0.0
                self.alpha = self.alpha_release
                self.in_decay = False
                
            elif self.in_decay and self.level <= self.params["sustain"]:
                # Sustaining
                self.target = self.params["sustain"]
                # Keep decay alpha for smooth transition
            
            # THE CORE - One line that does everything
            self.level += (self.target - self.level) * self.alpha
            
            # Apply envelope
            if in_buf is not None:
                out_buf[i] = in_buf[i] * self.level
            else:
                out_buf[i] = self.level  # Output envelope directly
    
    def prepare(self):
        """Reset for playback"""
        self.level = 0.0
        self.target = 0.0
        self.gate = False
        self.in_decay = False
        self._update_alphas()
    
    def validate_params(self) -> bool:
        """Validate and clamp parameters to safe ranges"""
        # Clamp times to safe ranges (min 0.1ms, max 10 seconds)
        for param in ["attack", "decay", "release"]:
            val = float(self.params.get(param, 10.0))
            val = max(0.1, min(10000.0, val))  # 0.1ms to 10s
            self.params[param] = val
        
        # Clamp sustain 0-1
        sus = float(self.params.get("sustain", 0.7))
        sus = max(0.0, min(1.0, sus))
        self.params["sustain"] = sus
        
        return True