#!/usr/bin/env python3
"""
Run script for AudioSupervisor v3 with router support
This handles proper module imports and environment setup

Usage:
    python run_supervisor_router.py
    
Or with router enabled:
    CHRONUS_ROUTER=1 python run_supervisor_router.py
"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run supervisor
from music_chronus.supervisor_v3_router import AudioSupervisorV3

def main():
    """Main entry point"""
    # Check router mode
    router_enabled = os.environ.get('CHRONUS_ROUTER', '0') == '1'
    
    print("=" * 60)
    print("Audio Supervisor v3 - Modular Synthesizer")
    print("=" * 60)
    
    if router_enabled:
        print("🎛️  ROUTER MODE ENABLED")
        print("Available commands:")
        print("  /patch/create <id> <type>  - Create module")
        print("  /patch/connect <src> <dst> - Connect modules")
        print("  /patch/commit             - Apply patch")
        print("  /patch/abort              - Cancel patch")
    else:
        print("📻 LINEAR CHAIN MODE (default)")
        print("Set CHRONUS_ROUTER=1 to enable router mode")
    
    print("\nTraditional commands always available:")
    print("  /mod/<module>/<param> <value> - Set parameter")
    print("  /gate/<module> <0|1>          - Gate control")
    print("\n" + "=" * 60)
    
    # Create and run supervisor
    try:
        supervisor = AudioSupervisorV3()
        supervisor.run()
    except KeyboardInterrupt:
        print("\n\nShutdown requested...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()