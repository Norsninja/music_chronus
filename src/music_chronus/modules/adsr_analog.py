"""
ADSR_Analog - Analog-modeled envelope generator with RC circuit behavior
Follows all codebase patterns while implementing click-free exponential segments
"""

import numpy as np
from math import exp
from .base import BaseModule
from ..module_registry import register_module


@register_module('adsr_analog')
class ADSRAnalog(BaseModule):
    """
    Analog-modeled ADSR envelope using RC circuit simulation.
    Provides natural, click-free transitions via exponential segments.
    
    Params (in milliseconds):
    - attack: Attack time (default 10ms)
    - decay: Decay time (default 100ms)  
    - sustain: Sustain level 0-1 (default 0.7)
    - release: Release time (default 200ms)
    
    Control:
    - set_gate(True/False): Trigger or release envelope
    """
    
    # Stage tracking for clarity
    IDLE = 0
    ATTACK = 1
    DECAY = 2
    SUSTAIN = 3
    RELEASE = 4

    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)

        # Parameters in milliseconds (codebase standard)
        self.params = {
            "attack": 10.0,
            "decay": 100.0,
            "sustain": 0.7,
            "release": 200.0,
        }
        self.param_targets = self.params.copy()

        # No smoothing - ADSR provides its own smoothing
        self.smoothing_samples.update({
            "attack": 0,
            "decay": 0,
            "sustain": 0,
            "release": 0,
            "default": 0,
        })

        # Core state
        self._level = 0.0
        self._target = 0.0
        self._alpha = 0.0
        self._stage = self.IDLE
        
        # Gate buffering (apply at boundaries)
        self._gate = False
        self._next_gate = False
        self._gate_changed = False
        
        # Cached alphas
        self._alpha_attack = 0.0
        self._alpha_decay = 0.0
        self._alpha_release = 0.0
        
        # Constants
        self._epsilon = 0.001
        self._denormal = 1e-6
        
        self._update_coefficients()

    def set_gate(self, gate: bool) -> None:
        """Queue gate change for next buffer boundary."""
        self._next_gate = gate
        self._gate_changed = True

    def prepare(self) -> None:
        """Reset state for playback."""
        self._level = 0.0
        self._target = 0.0
        self._alpha = 0.0
        self._stage = self.IDLE
        self._gate = False
        self._next_gate = False
        self._gate_changed = False
        self._update_coefficients()

    def validate_params(self) -> bool:
        """Ensure parameters are in safe ranges."""
        # Enforce minimums for click-free operation
        self.params["attack"] = max(3.0, min(10000.0, float(self.params["attack"])))
        self.params["decay"] = max(3.0, min(10000.0, float(self.params["decay"])))
        self.params["release"] = max(10.0, min(10000.0, float(self.params["release"])))
        self.params["sustain"] = max(0.0, min(1.0, float(self.params["sustain"])))
        return True

    def _update_coefficients(self) -> None:
        """Calculate RC coefficients from millisecond parameters."""
        # Convert to seconds
        attack_s = self.params["attack"] / 1000.0
        decay_s = self.params["decay"] / 1000.0
        release_s = self.params["release"] / 1000.0
        
        # RC formula: alpha = 1 - exp(-1/(tau * sr))
        self._alpha_attack = 1.0 - exp(-1.0 / (max(0.0001, attack_s) * self.sr))
        self._alpha_decay = 1.0 - exp(-1.0 / (max(0.0001, decay_s) * self.sr))
        self._alpha_release = 1.0 - exp(-1.0 / (max(0.0001, release_s) * self.sr))

    def _process_audio(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        """
        Process audio with RC envelope model.
        """
        # Update parameters if changed
        self.validate_params()
        self._update_coefficients()
        
        # Handle gate changes at buffer boundary
        if self._gate_changed:
            prev_gate = self._gate
            self._gate = self._next_gate
            self._gate_changed = False
            
            if self._gate and not prev_gate:
                # Gate ON - attack from current level (legato)
                self._stage = self.ATTACK
                self._target = 1.0
                self._alpha = self._alpha_attack
                
            elif not self._gate and prev_gate:
                # Gate OFF - release from current level
                if self._stage != self.IDLE:
                    self._stage = self.RELEASE
                    self._target = 0.0
                    self._alpha = self._alpha_release
        
        # Process samples with RC model
        for i in range(self.buffer_size):
            # Core RC equation - exponential approach to target
            self._level += (self._target - self._level) * self._alpha
            
            # Handle stage transitions
            if self._stage == self.ATTACK and self._level >= (1.0 - self._epsilon):
                # Start decay
                self._stage = self.DECAY
                self._target = self.params["sustain"]
                self._alpha = self._alpha_decay
                
            elif self._stage == self.DECAY and self._level <= (self.params["sustain"] + self._epsilon):
                # Enter sustain
                self._stage = self.SUSTAIN
                self._alpha = 0.0001  # Minimal drift
                
            elif self._stage == self.RELEASE and self._level <= self._denormal:
                # Return to idle
                self._level = 0.0
                self._stage = self.IDLE
                self._alpha = 0.0
            
            # Clamp and denormal prevention
            if abs(self._level) < self._denormal:
                self._level = 0.0
            self._level = np.clip(self._level, 0.0, 1.0)
            
            # Apply envelope
            if in_buf is not None:
                out_buf[i] = in_buf[i] * self._level
            else:
                out_buf[i] = self._level
    
    def get_state(self) -> dict:
        """Return current state for debugging."""
        state = super().get_state()
        state.update({
            "stage": ["idle", "attack", "decay", "sustain", "release"][self._stage],
            "level": f"{self._level:.3f}",
            "gate": self._gate,
        })
        return state