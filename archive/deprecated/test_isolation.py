#!/usr/bin/env python3
"""
Isolation test script for debugging engine sound issue
Follows Senior Dev's recommended test sequence
"""

import os
import sys
import time
import subprocess
import signal

def run_test(name, env_vars, duration=5):
    """Run a test configuration"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"Config: {env_vars}")
    print(f"{'='*60}")
    
    # Set environment
    env = os.environ.copy()
    env['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'
    env['CHRONUS_VERBOSE'] = '1'
    env.update(env_vars)
    
    # Start supervisor
    proc = subprocess.Popen(
        [sys.executable, '-m', 'src.music_chronus.supervisor_v3_debug'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print(f"Started supervisor (PID: {proc.pid})")
    time.sleep(1)  # Let it initialize
    
    # Send test commands
    print("Sending test sequence...")
    osc_commands = [
        "python utils/osc_control.py gate 1",
        "python utils/osc_control.py freq 440",
        "python utils/osc_control.py gain 0.5"
    ]
    
    for cmd in osc_commands:
        subprocess.run(cmd, shell=True, capture_output=True)
        time.sleep(0.1)
    
    print(f"Playing for {duration} seconds...")
    
    # Capture output for duration
    start_time = time.time()
    lines = []
    while time.time() - start_time < duration:
        try:
            line = proc.stdout.readline()
            if line:
                print(line.rstrip())
                lines.append(line)
        except:
            break
    
    # Stop
    print("Stopping supervisor...")
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=2)
    
    # Analyze output
    print("\n--- Analysis ---")
    rms_values = []
    for line in lines:
        if "RMS=" in line:
            try:
                rms = float(line.split("RMS=")[1].split()[0])
                rms_values.append(rms)
            except:
                pass
    
    if rms_values:
        avg_rms = sum(rms_values) / len(rms_values)
        print(f"Average RMS: {avg_rms:.6f}")
        print(f"Non-zero buffers: {sum(1 for r in rms_values if r > 1e-6)}/{len(rms_values)}")
    
    return lines


def main():
    """Run isolation test sequence"""
    print("="*60)
    print("AUDIO ENGINE ISOLATION TESTS")
    print("Following Senior Dev's diagnostic protocol")
    print("="*60)
    
    # Make sure we're in the right directory
    os.chdir('/home/norsninja/music_chronus')
    
    # Activate venv
    activate_cmd = "source venv/bin/activate"
    
    tests = [
        ("1. Primary only + Pure sine (no modules)", {
            'PRIMARY_ONLY': '1',
            'NO_MODULES': '1',
            'NO_MONITOR': '1',
            'DEBUG_LEVEL': '1'
        }),
        
        ("2. Primary only + Sine module only", {
            'PRIMARY_ONLY': '1',
            'NO_MODULES': '0',
            'NO_MONITOR': '1',
            'DEBUG_LEVEL': '1'
        }),
        
        ("3. Primary only + Full chain", {
            'PRIMARY_ONLY': '1',
            'NO_MODULES': '0',
            'NO_MONITOR': '1',
            'DEBUG_LEVEL': '1'
        }),
        
        ("4. Dual workers + No monitor", {
            'PRIMARY_ONLY': '0',
            'NO_MODULES': '0',
            'NO_MONITOR': '1',
            'DEBUG_LEVEL': '1'
        }),
        
        ("5. Full system (dual + monitor)", {
            'PRIMARY_ONLY': '0',
            'NO_MODULES': '0',
            'NO_MONITOR': '0',
            'DEBUG_LEVEL': '1'
        })
    ]
    
    results = {}
    
    for test_name, env_vars in tests:
        input(f"\nPress Enter to run: {test_name}")
        try:
            lines = run_test(test_name, env_vars, duration=3)
            
            # Ask user about audio quality
            quality = input("How did it sound? (clean/engine/silent): ").strip().lower()
            results[test_name] = quality
            
        except Exception as e:
            print(f"Test failed: {e}")
            results[test_name] = "error"
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test_name, result in results.items():
        print(f"{test_name}: {result}")
    
    # Diagnosis
    print("\n" + "="*60)
    print("DIAGNOSIS")
    print("="*60)
    
    if results.get("1. Primary only + Pure sine (no modules)") == "clean":
        print("✓ Audio path is clean")
        
        if results.get("2. Primary only + Sine module only") == "engine":
            print("✗ Issue is in SimpleSine module")
        elif results.get("3. Primary only + Full chain") == "engine":
            print("✗ Issue is in ADSR or Filter module")
        elif results.get("4. Dual workers + No monitor") == "engine":
            print("✗ Issue is dual-worker interference")
        elif results.get("5. Full system (dual + monitor)") == "engine":
            print("✗ Issue is in monitor/failover logic")
    else:
        print("✗ Core audio path has issues")


if __name__ == '__main__':
    main()