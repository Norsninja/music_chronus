"""
ADSR RC (Clickless) — Production-aligned envelope

- Per-sample RC update for continuity: level += (target - level) * alpha
- Parameters in milliseconds (attack/decay/release)
- Gate controlled via set_gate(); no param polling in hot path
- Zero allocations in process_buffer(); aligns with BaseModule patterns
"""

import numpy as np
from math import exp
from .base import BaseModule
from ..module_registry import register_module


@register_module('adsr_rc')
class ADSR_RC(BaseModule):
    """
    Minimal, clickless ADSR envelope modeled as an RC system.
    Default mode: legato (continue from current level on gate-on).
    """

    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)

        # State
        self._level = 0.0
        self._gate = False
        self._in_decay = False

        # Parameters (ms)
        self.params = {
            'attack': 10.0,     # ms
            'decay': 100.0,     # ms
            'sustain': 0.7,     # 0..1
            'release': 200.0,   # ms
        }
        self.param_targets = self.params.copy()

        # No external smoothing for ADSR time params; ADSR is the smoothing
        self.smoothing_samples.update({
            'attack': 0,
            'decay': 0,
            'sustain': 0,
            'release': 0,
            'default': 0,
        })

        # Cached alphas (recomputed on param change)
        self._alpha_attack = 0.0
        self._alpha_decay = 0.0
        self._alpha_release = 0.0
        self._update_alphas()

        self._epsilon = 1e-6

    def validate_params(self) -> bool:
        # Clamp times: 0.1ms .. 10s; sustain in [0,1]
        for p in ('attack', 'decay', 'release'):
            v = float(self.params.get(p, 10.0))
            if v < 0.1:
                v = 0.1
            elif v > 10000.0:
                v = 10000.0
            self.params[p] = v
        s = float(self.params.get('sustain', 0.7))
        if s < 0.0:
            s = 0.0
        elif s > 1.0:
            s = 1.0
        self.params['sustain'] = s
        return True

    def _update_alphas(self) -> None:
        # alpha = 1 - exp(-1 / (tau_seconds * sr))
        sr = float(self.sr)
        atk_s = max(self.params['attack'] / 1000.0, 1e-6)
        dec_s = max(self.params['decay'] / 1000.0, 1e-6)
        rel_s = max(self.params['release'] / 1000.0, 1e-6)
        self._alpha_attack = 1.0 - exp(-1.0 / (atk_s * sr))
        self._alpha_decay = 1.0 - exp(-1.0 / (dec_s * sr))
        self._alpha_release = 1.0 - exp(-1.0 / (rel_s * sr))

    def set_gate(self, gate: bool) -> None:
        self._gate = bool(gate)

    def prepare(self) -> None:
        self._level = 0.0
        self._gate = False
        self._in_decay = False
        self._update_alphas()

    def _process_audio(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        # Refresh constraints and alphas once per buffer
        self.validate_params()
        self._update_alphas()

        sustain = float(self.params['sustain'])

        for i in range(self.buffer_size):
            # Choose target and alpha based on gate and phase
            if self._gate:
                if not self._in_decay:
                    target = 1.0
                    alpha = self._alpha_attack
                    if self._level >= 0.999:
                        self._in_decay = True
                else:
                    target = sustain
                    alpha = self._alpha_decay
            else:
                target = 0.0
                alpha = self._alpha_release
                self._in_decay = False

            # RC update
            self._level += (target - self._level) * alpha

            # Clamp and denormal guard
            if self._level < self._epsilon:
                self._level = 0.0
            elif self._level > 1.0:
                self._level = 1.0

            # Apply envelope
            if in_buf is not None:
                out_buf[i] = in_buf[i] * self._level
            else:
                out_buf[i] = self._level

