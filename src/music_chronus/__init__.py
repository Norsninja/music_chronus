"""
Music Chronus - Real-time Modular Synthesizer
Phase 2 Complete: Slot-based Fault-Tolerant Synthesis with <50ms Failover
"""

__version__ = "0.3.0"
__author__ = "Chronus Nexus & Mike"

# Make key components available at package level
# Using supervisor_v2_slots_fixed as the production AudioSupervisor (slot-based architecture with zero-allocation)
from .supervisor_v2_slots_fixed import AudioSupervisor
from .engine import AudioEngine
from .module_host import ModuleHost

__all__ = ['AudioSupervisor', 'AudioEngine', 'ModuleHost']