"""
Music Chronus - Real-time Modular Synthesizer
Phase 2 Complete: Modular Synthesis with <10ms Failover
"""

__version__ = "0.2.0"
__author__ = "Chronus Nexus & Mike"

# Make key components available at package level
# Using supervisor_v2_fixed as the production AudioSupervisor
from .supervisor_v2_fixed import AudioSupervisor
from .engine import AudioEngine
from .module_host import ModuleHost

__all__ = ['AudioSupervisor', 'AudioEngine', 'ModuleHost']