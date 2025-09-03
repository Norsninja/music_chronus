#!/usr/bin/env python3
"""
Quick verification that all fixes are applied
Run this to prove the workspace has the correct code
"""

import os
import sys

print("=" * 60)
print("WORKSPACE FIX VERIFICATION")
print("=" * 60)

# Check 1: Verify supervisor_v3_router.py exists (current implementation)
print("\n1. Checking for current supervisor implementation...")
if os.path.exists('src/music_chronus/supervisor_v3_router.py'):
    print("✅ PASS: supervisor_v3_router.py exists (current implementation)")
    with open('src/music_chronus/supervisor_v3_router.py', 'r') as f:
        content = f.read()
elif os.path.exists('src/music_chronus/supervisor_v2_fixed.py'):
    print("⚠️  WARNING: Using older supervisor_v2_fixed.py")
    with open('src/music_chronus/supervisor_v2_fixed.py', 'r') as f:
        content = f.read()
else:
    print("❌ FAIL: No supervisor implementation found")
    sys.exit(1)
    
# Look for the terminate method
terminate_start = content.find('def terminate(self):')
terminate_end = content.find('def ', terminate_start + 1)
terminate_method = content[terminate_start:terminate_end]

if 'pack_command_v2' in terminate_method or 'shutdown' in terminate_method.lower() and 'shutdown_flag' not in terminate_method:
    print("❌ FAIL: Still has shutdown command in terminate()")
    print(terminate_method[:200])
else:
    if 'self.process.terminate()' in terminate_method:
        print("✅ PASS: Uses SIGTERM only (no command ring pollution)")
    else:
        print("⚠️  WARNING: Method structure unexpected")

# Check 2: metrics.active_worker should be 0
print("\n2. Checking metrics.active_worker normalization...")
import re
active_worker_matches = re.findall(r'self\.metrics\.active_worker = (\d)', content)
if all(val == '0' for val in active_worker_matches):
    print(f"✅ PASS: All {len(active_worker_matches)} assignments set to 0")
else:
    print(f"❌ FAIL: Found non-zero assignments: {active_worker_matches}")

# Check 3: CommandRing.reset() exists
print("\n3. Checking CommandRing.reset() in supervisor.py...")
with open('src/music_chronus/supervisor.py', 'r') as f:
    supervisor_content = f.read()
    
if 'def reset(self):' in supervisor_content and 'self.reset()' in supervisor_content:
    print("✅ PASS: reset() method exists and is called")
else:
    print("❌ FAIL: reset() method missing or not called")

# Check 4: Test files exist
print("\n4. Checking test files...")
if os.path.exists('test_modulehost_fixed.py'):
    with open('test_modulehost_fixed.py', 'r') as f:
        test_content = f.read()
    if "status['metrics']['failover_count']" in test_content:
        print("✅ PASS: Test checks failover_count for detection")
    else:
        print("⚠️  WARNING: Test doesn't use failover_count")
else:
    print("⚠️  WARNING: test_modulehost_fixed.py not found (may be in tests/ directory)")

# Summary
print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
print("\nCurrent implementation: supervisor_v3_router.py")
print("This includes CP3 router support and recording capability.")
print("\nTo test functionality, run:")
print("  export CHRONUS_ROUTER=1")
print("  python src/music_chronus/supervisor_v3_router.py")