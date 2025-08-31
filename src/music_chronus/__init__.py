"""
Music Chronus - Real-time Modular Synthesizer
Phase 1 Complete: Audio Engine with Fault-Tolerant Supervision
"""

__version__ = "0.1.0"
__author__ = "Chronus Nexus & Mike"

# Make key components available at package level
from .supervisor import AudioSupervisor
from .engine import AudioEngine

__all__ = ['AudioSupervisor', 'AudioEngine']