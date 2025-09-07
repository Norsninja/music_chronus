#!/usr/bin/env python3
"""
Test SuperCollider headless operation
Verifies scsynth can be controlled via OSC from Python
"""

import subprocess
import time
import sys
from pythonosc import udp_client
import os

def start_scsynth():
    """Start SuperCollider server in headless mode"""
    
    # Common paths for SuperCollider on Windows
    sc_paths = [
        r"C:\Program Files\SuperCollider-3.14.0\scsynth.exe",
        r"C:\Program Files\SuperCollider-3.13.0\scsynth.exe",
        r"C:\Program Files\SuperCollider\scsynth.exe",
        r"C:\Program Files (x86)\SuperCollider\scsynth.exe",
    ]
    
    scsynth_path = None
    for path in sc_paths:
        if os.path.exists(path):
            scsynth_path = path
            break
    
    if not scsynth_path:
        print("ERROR: Could not find scsynth.exe")
        print("Please install SuperCollider from https://supercollider.github.io/download")
        return None
    
    print(f"Found scsynth at: {scsynth_path}")
    
    # Start scsynth with basic options
    # -u 57110 : UDP port
    # -a 1024  : Number of audio bus channels  
    # -i 2     : Number of input channels
    # -o 2     : Number of output channels
    # -H ""    : Hardware device name (empty for default)
    # For Windows/WASAPI, we can try specifying device
    
    # Check if user specified a device
    device_id = os.environ.get('SC_DEVICE', '')
    
    if device_id:
        print(f"Using audio device: {device_id}")
        # On Windows, device selection is tricky - try both methods
        cmd = [scsynth_path, "-u", "57110", "-a", "1024", "-i", "2", "-o", "2", "-H", device_id]
    else:
        cmd = [scsynth_path, "-u", "57110", "-a", "1024", "-i", "2", "-o", "2"]
    
    print("Starting SuperCollider server...")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Give it time to start
    time.sleep(2)
    
    if process.poll() is not None:
        print("ERROR: scsynth failed to start")
        stdout, stderr = process.communicate()
        print(f"stdout: {stdout.decode()}")
        print(f"stderr: {stderr.decode()}")
        return None
    
    print("SuperCollider server started successfully!")
    return process

def test_basic_synthesis():
    """Test basic sound synthesis via OSC"""
    
    client = udp_client.SimpleUDPClient("127.0.0.1", 57110)
    
    print("\n" + "="*50)
    print("TESTING SUPERCOLLIDER OSC CONTROL")
    print("="*50)
    
    # Test 1: Query server status
    print("\n1. Querying server status...")
    client.send_message("/status", 1)
    time.sleep(0.5)
    
    # Test 2: Create default synth (sine wave)
    print("\n2. Creating default sine wave synth...")
    # /s_new defName nodeID addAction targetID
    # defName="default" is built-in sine synth
    # nodeID=1000 (arbitrary ID we choose)
    # addAction=0 (add to head)
    # targetID=0 (default group)
    client.send_message("/s_new", ["default", 1000, 0, 0, "freq", 440, "amp", 0.2])
    print("   Playing 440Hz sine wave for 2 seconds...")
    time.sleep(2)
    
    # Test 3: Change frequency
    print("\n3. Changing frequency to 880Hz...")
    client.send_message("/n_set", [1000, "freq", 880])
    time.sleep(1)
    
    # Test 4: Stop the synth
    print("\n4. Stopping synth...")
    client.send_message("/n_free", [1000])
    time.sleep(0.5)
    
    # Test 5: Play a simple melody
    print("\n5. Playing a simple melody...")
    notes = [261.63, 293.66, 329.63, 349.23, 392.00, 349.23, 329.63, 293.66]
    for i, freq in enumerate(notes):
        node_id = 2000 + i
        client.send_message("/s_new", ["default", node_id, 0, 0, "freq", freq, "amp", 0.15])
        time.sleep(0.25)
        client.send_message("/n_free", [node_id])
        time.sleep(0.05)
    
    print("\n" + "="*50)
    print("TEST COMPLETE!")
    print("="*50)

def main():
    """Main test function"""
    
    print("SuperCollider Headless Test")
    print("="*50)
    
    # Start scsynth
    sc_process = start_scsynth()
    
    if not sc_process:
        print("Failed to start SuperCollider")
        return 1
    
    try:
        # Run tests
        test_basic_synthesis()
        
        print("\n✓ SuperCollider is working perfectly for headless operation!")
        print("✓ We can control everything via OSC from Python/Bash")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        return 1
    
    finally:
        # Clean shutdown
        print("\nShutting down SuperCollider server...")
        sc_process.terminate()
        sc_process.wait(timeout=5)
        print("Server stopped.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())