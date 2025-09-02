"""
ADSR - Linear envelope generator module (Phase 2)
- Processor: applies envelope to in_buf, writes to out_buf
- Zero allocations in process_buffer()
- Sample-accurate state machine
- Gate control with retrigger support
"""

import numpy as np
from .base import BaseModule
from ..module_registry import register_module


@register_module('adsr')
class ADSR(BaseModule):
    """
    Linear ADSR envelope generator with sample-accurate timing.
    
    Params (in milliseconds):
    - attack: Attack time (default 10ms)
    - decay: Decay time (default 100ms)
    - sustain: Sustain level 0-1 (default 0.7)
    - release: Release time (default 200ms)
    
    Control:
    - set_gate(True/False): Trigger or release envelope
    """
    
    # Envelope stages
    IDLE = 0
    ATTACK = 1
    DECAY = 2
    SUSTAIN = 3
    RELEASE = 4

    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)

        # Parameters (times in milliseconds)
        self.params = {
            "attack": 10.0,
            "decay": 100.0,
            "sustain": 0.7,
            "release": 200.0,
        }
        self.param_targets = self.params.copy()

        # Smoothing config - no smoothing for ADSR params (they ARE the smoothing)
        self.smoothing_samples.update({
            "attack": 0,
            "decay": 0,
            "sustain": 0,
            "release": 0,
            "default": 0,
        })

        # State variables
        self._stage = self.IDLE
        self._level = 0.0  # Current envelope level (0-1)
        self._gate = False
        self._next_gate = False  # For buffer-boundary gate changes
        self._gate_changed = False
        
        # Pre-computed increments (updated at buffer boundaries)
        self._attack_inc = 0.0
        self._decay_inc = 0.0
        self._release_inc = 0.0
        
        # Conversion factor
        self._ms_to_samples = sample_rate / 1000.0
        
        # Denormal prevention threshold
        self._denormal_threshold = 1e-6

    def set_gate(self, gate: bool) -> None:
        """
        Trigger or release envelope (applied at next buffer boundary).
        
        Args:
            gate: True to trigger, False to release
        """
        import os
        if os.environ.get('CHRONUS_VERBOSE'):
            pass  # Debug: gate={gate}, current_stage={self._stage}, current_gate={self._gate}
        self._next_gate = gate
        self._gate_changed = True

    def prepare(self) -> None:
        """Reset envelope state before playback."""
        self._stage = self.IDLE
        self._level = 0.0
        self._gate = False
        self._next_gate = False
        self._gate_changed = False
        self._update_increments()

    def validate_params(self) -> bool:
        """Clamp params to safe ranges."""
        # Minimum 0.1ms, maximum 10 seconds
        for param in ["attack", "decay", "release"]:
            val = float(self.params.get(param, 10.0))
            val = max(0.1, min(10000.0, val))
            self.params[param] = val
        
        # Sustain level 0-1
        sus = float(self.params.get("sustain", 0.7))
        sus = max(0.0, min(1.0, sus))
        self.params["sustain"] = sus
        
        return True

    def _update_increments(self) -> None:
        """Pre-compute per-sample increments for current parameters."""
        # Convert times to samples
        attack_samples = max(1.0, self.params["attack"] * self._ms_to_samples)
        decay_samples = max(1.0, self.params["decay"] * self._ms_to_samples)
        release_samples = max(1.0, self.params["release"] * self._ms_to_samples)
        
        # Linear increments per sample
        self._attack_inc = 1.0 / attack_samples
        self._decay_inc = (1.0 - self.params["sustain"]) / decay_samples
        
        # Release from current level, not from sustain
        # This will be updated when entering release stage
        self._release_inc = 1.0 / release_samples

    def _process_audio(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        """
        Apply envelope to input buffer sample-by-sample.
        Zero allocations - processes in-place.
        """
        # Validate and update increments if parameters changed
        self.validate_params()
        self._update_increments()
        
        # Apply gate change at buffer boundary
        if self._gate_changed:
            import os
            old_gate = self._gate
            self._gate = self._next_gate
            self._gate_changed = False
            
            if os.environ.get('CHRONUS_VERBOSE'):
                pass  # Debug: Processing gate change: {old_gate} -> {self._gate}, stage={self._stage}
            
            if self._gate:
                # Gate on - start attack (allow retrigger)
                self._stage = self.ATTACK
                if os.environ.get('CHRONUS_VERBOSE'):
                    pass  # Debug: Gate ON: Starting ATTACK
            elif self._stage != self.IDLE and self._stage != self.RELEASE:
                # Gate off - enter release unless already idle/releasing
                self._stage = self.RELEASE
                # Calculate release increment from current level
                if self._level > self._denormal_threshold:
                    release_samples = max(1.0, self.params["release"] * self._ms_to_samples)
                    self._release_inc = self._level / release_samples
                if os.environ.get('CHRONUS_VERBOSE'):
                    pass  # Debug: Gate OFF: Entering RELEASE from stage {old_gate}
            elif os.environ.get('CHRONUS_VERBOSE'):
                pass  # Debug: Gate OFF but already in {['IDLE','ATTACK','DECAY','SUSTAIN','RELEASE'][self._stage]}
        
        # Process each sample with state machine
        # Sample-by-sample required for accurate timing
        for i in range(self.buffer_size):
            # State machine for envelope stages
            if self._stage == self.ATTACK:
                self._level += self._attack_inc
                if self._level >= 1.0:
                    self._level = 1.0
                    self._stage = self.DECAY
                    
            elif self._stage == self.DECAY:
                self._level -= self._decay_inc
                sustain_level = self.params["sustain"]
                if self._level <= sustain_level:
                    self._level = sustain_level
                    self._stage = self.SUSTAIN
                    
            elif self._stage == self.SUSTAIN:
                self._level = self.params["sustain"]
                
            elif self._stage == self.RELEASE:
                self._level -= self._release_inc
                if self._level <= self._denormal_threshold:
                    self._level = 0.0
                    self._stage = self.IDLE
                    
            else:  # IDLE
                self._level = 0.0
            
            # Apply envelope to sample (in-place multiplication)
            if in_buf is not None:
                out_buf[i] = in_buf[i] * self._level
            else:
                out_buf[i] = self._level  # Output envelope directly if no input
                
    def get_state(self) -> dict:
        """Get current module state for debugging."""
        state = super().get_state()
        state.update({
            "stage": ["idle", "attack", "decay", "sustain", "release"][self._stage],
            "level": self._level,
            "gate": self._gate,
        })
        return state