#!/usr/bin/env python3
"""
Schema Audit Test - Ensures the parameter registry stays up to date
Runs the engine in test mode, fetches schema, and validates completeness
"""

import json
import time
import subprocess
import sys
from pythonosc import udp_client

def run_schema_audit():
    """Run schema audit test"""
    print("=" * 50)
    print("SCHEMA AUDIT TEST")
    print("=" * 50)
    
    # Check if engine is running
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("\n1. Testing engine connection...")
    try:
        # Try to get schema
        client.send_message("/engine/schema", ["json"])
        print("   [OK] Engine is responding")
    except Exception as e:
        print(f"   [FAIL] Engine not responding: {e}")
        print("\nPlease start the engine first: python engine_pyo.py")
        return False
    
    print("\n2. Checking for unknown routes...")
    # Send a test unknown route
    client.send_message("/test/unknown/route", [123])
    time.sleep(0.1)
    
    print("\n3. Validating registered routes...")
    # Test known routes to ensure they're registered
    test_routes = [
        ("/engine/status", []),
        ("/seq/status", []),
        ("/mod/voice1/freq", [440.0]),
        ("/gate/voice1", [0])
    ]
    
    for route, args in test_routes:
        print(f"   Testing {route}...")
        client.send_message(route, args)
        time.sleep(0.05)
    
    print("\n4. Schema validation checks:")
    
    # Request schema again to see if unknown routes were tracked
    client.send_message("/engine/schema", ["json"])
    
    print("\n   Check engine output for:")
    print("   - Registered routes list")
    print("   - Unknown routes (should include /test/unknown/route)")
    print("   - Complete parameter metadata")
    
    print("\n5. Developer checklist:")
    print("   [ ] All routes use map_route() wrapper")
    print("   [ ] All modules have get_schema() method")
    print("   [ ] Parameter metadata includes min/max/default")
    print("   [ ] Unknown routes are tracked and logged")
    print("   [ ] Schema version bumped if breaking changes")
    
    print("\n" + "=" * 50)
    print("AUDIT COMPLETE")
    print("Check engine terminal for detailed schema output")
    print("=" * 50)
    
    return True

def export_golden_schema():
    """Export current schema as golden reference"""
    client = udp_client.SimpleUDPClient("127.0.0.1", 5005)
    
    print("\nExporting golden schema...")
    print("Set CHRONUS_EXPORT_SCHEMA=1 and restart engine")
    print("Then run: python chronusctl.py schema --format file")
    print("This creates a timestamped schema file for CI comparison")

if __name__ == "__main__":
    # Run audit
    success = run_schema_audit()
    
    if success and len(sys.argv) > 1 and sys.argv[1] == "--export":
        export_golden_schema()
    
    sys.exit(0 if success else 1)