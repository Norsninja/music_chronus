#!/usr/bin/env python3
"""
Test that refactored structure works correctly
"""

import sys
import os

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that we can import from new structure"""
    print("Testing imports from new structure...")
    
    try:
        from music_chronus import AudioSupervisor, AudioEngine
        print("✅ Package-level imports work")
    except ImportError as e:
        print(f"❌ Package import failed: {e}")
        return False
    
    try:
        from music_chronus.supervisor import AudioSupervisor
        print("✅ Direct supervisor import works")
    except ImportError as e:
        print(f"❌ Supervisor import failed: {e}")
        return False
    
    try:
        from music_chronus.engine import AudioEngine
        print("✅ Direct engine import works")
    except ImportError as e:
        print(f"❌ Engine import failed: {e}")
        return False
    
    return True

def test_supervisor_instantiation():
    """Test that supervisor can be instantiated"""
    print("\nTesting supervisor instantiation...")
    
    try:
        from music_chronus import AudioSupervisor
        supervisor = AudioSupervisor()
        print(f"✅ Supervisor created: {supervisor.__class__.__name__}")
        return True
    except Exception as e:
        print(f"❌ Failed to create supervisor: {e}")
        return False

def test_engine_instantiation():
    """Test that engine can be instantiated"""
    print("\nTesting engine instantiation...")
    
    try:
        from music_chronus import AudioEngine
        engine = AudioEngine()
        print(f"✅ Engine created: {engine.__class__.__name__}")
        return True
    except Exception as e:
        print(f"❌ Failed to create engine: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("REFACTOR VALIDATION TEST")
    print("=" * 50)
    
    results = []
    results.append(test_imports())
    results.append(test_supervisor_instantiation())
    results.append(test_engine_instantiation())
    
    print("\n" + "=" * 50)
    if all(results):
        print("✅ ALL TESTS PASSED - Refactor successful")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - Do not proceed")
        sys.exit(1)