#!/usr/bin/env python3
"""
Quick test to verify pyo is installed and working
"""

try:
    from pyo import *
    print("✓ Pyo imported successfully!")
    
    # Try to create a server (won't start audio, just test creation)
    print("\nTesting server creation...")
    s = Server(sr=48000, nchnls=1, buffersize=256, duplex=0)
    print("✓ Server object created")
    
    # List available audio devices
    print("\nAvailable audio devices:")
    pa_list_devices()
    
    print("\n✓ Pyo is installed correctly and ready to use!")
    
except ImportError as e:
    print(f"✗ Failed to import pyo: {e}")
    print("\nTry installing with:")
    print("  pip install pyo")
    
except Exception as e:
    print(f"✗ Error during pyo test: {e}")
    print("\nPyo is installed but may have configuration issues")
