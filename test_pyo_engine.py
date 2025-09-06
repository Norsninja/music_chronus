#!/usr/bin/env python3
"""
Test script for pyo engine
Sends OSC commands to verify audio synthesis works without clicks
"""

import time
from pythonosc import udp_client

def main():
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("Testing Pyo Engine")
    print("=" * 50)
    
    # Wait for engine to be ready
    time.sleep(1)
    
    print("\n1. Testing basic sine tone (440Hz)")
    client.send_message("/gate/adsr1", 1.0)
    time.sleep(2)
    client.send_message("/gate/adsr1", 0.0)
    time.sleep(1)
    
    print("\n2. Testing frequency changes")
    client.send_message("/gate/adsr1", 1.0)
    for freq in [440, 550, 660, 880, 440]:
        print(f"   Frequency: {freq}Hz")
        client.send_message("/mod/sine1/freq", freq)
        time.sleep(0.5)
    client.send_message("/gate/adsr1", 0.0)
    time.sleep(1)
    
    print("\n3. Testing filter sweep")
    client.send_message("/gate/adsr1", 1.0)
    client.send_message("/mod/sine1/freq", 220)  # Lower frequency
    for cutoff in [200, 500, 1000, 2000, 5000, 1000]:
        print(f"   Filter cutoff: {cutoff}Hz")
        client.send_message("/mod/filter1/freq", cutoff)
        time.sleep(0.5)
    client.send_message("/gate/adsr1", 0.0)
    time.sleep(1)
    
    print("\n4. Testing ADSR parameters")
    # Fast attack/release
    client.send_message("/mod/adsr1/attack", 0.001)
    client.send_message("/mod/adsr1/release", 0.05)
    print("   Fast envelope")
    for _ in range(5):
        client.send_message("/gate/adsr1", 1.0)
        time.sleep(0.1)
        client.send_message("/gate/adsr1", 0.0)
        time.sleep(0.1)
    
    # Slow attack/release
    client.send_message("/mod/adsr1/attack", 0.5)
    client.send_message("/mod/adsr1/release", 1.0)
    print("   Slow envelope")
    client.send_message("/gate/adsr1", 1.0)
    time.sleep(1)
    client.send_message("/gate/adsr1", 0.0)
    time.sleep(2)
    
    print("\n5. Testing 10-second sustained tone (listen for clicks)")
    client.send_message("/mod/adsr1/attack", 0.01)
    client.send_message("/mod/adsr1/release", 0.5)
    client.send_message("/mod/sine1/freq", 440)
    client.send_message("/mod/filter1/freq", 2000)
    client.send_message("/gate/adsr1", 1.0)
    print("   Playing sustained tone...")
    time.sleep(10)
    client.send_message("/gate/adsr1", 0.0)
    time.sleep(1)
    
    print("\n6. Testing rapid parameter changes (stress test)")
    client.send_message("/gate/adsr1", 1.0)
    print("   Sending rapid frequency changes...")
    start_time = time.time()
    count = 0
    while time.time() - start_time < 5:
        freq = 220 + (count % 20) * 20
        client.send_message("/mod/sine1/freq", freq)
        count += 1
        time.sleep(0.01)  # 100 messages per second
    client.send_message("/gate/adsr1", 0.0)
    print(f"   Sent {count} messages in 5 seconds ({count/5:.1f} msg/sec)")
    
    print("\n" + "=" * 50)
    print("Test complete!")
    print("\nDid you hear:")
    print("- Clean tones without clicking?")
    print("- Smooth parameter changes?")
    print("- Stable audio during rapid updates?")
    print("\nIf yes, pyo is working correctly!")

if __name__ == "__main__":
    main()