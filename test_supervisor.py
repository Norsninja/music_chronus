#!/usr/bin/env python3
"""
Phase 1C: Supervisor Test Suite
Tests lockstep rendering, failover timing, and resource hygiene
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import signal
import psutil
import numpy as np
from pythonosc import udp_client
from music_chronus import AudioSupervisor


class SupervisorTester:
    """Test harness for Audio Supervisor"""
    
    def __init__(self):
        self.supervisor = AudioSupervisor()
        self.osc_client = udp_client.SimpleUDPClient('127.0.0.1', 5005)
        self.test_results = {}
        
    def smoke_test(self):
        """Basic functionality test"""
        print("\n=== SMOKE TEST ===")
        print("Starting supervisor...")
        
        if not self.supervisor.start():
            print("❌ Failed to start supervisor")
            return False
        
        time.sleep(1)  # Let workers settle
        
        # Check both workers are running
        status = self.supervisor.get_status()
        if status['primary_pid'] and status['standby_pid']:
            print(f"✅ Both workers running: Primary={status['primary_pid']}, Standby={status['standby_pid']}")
        else:
            print("❌ Workers not running properly")
            return False
        
        # Check heartbeats incrementing
        hb1 = [status['primary_heartbeat'], status['standby_heartbeat']]
        time.sleep(0.5)
        status = self.supervisor.get_status()
        hb2 = [status['primary_heartbeat'], status['standby_heartbeat']]
        
        if hb2[0] > hb1[0] and hb2[1] > hb1[1]:
            print(f"✅ Heartbeats incrementing: Primary {hb1[0]}→{hb2[0]}, Standby {hb1[1]}→{hb2[1]}")
        else:
            print("❌ Heartbeats not incrementing")
            return False
        
        # Test OSC control
        print("Testing OSC control...")
        self.osc_client.send_message('/engine/freq', 880.0)
        time.sleep(0.1)
        self.osc_client.send_message('/engine/gain', 0.3)
        time.sleep(0.1)
        
        status = self.supervisor.get_status()
        if status['commands_sent'] >= 4:  # 2 commands × 2 workers
            print(f"✅ OSC commands processed: {status['commands_sent']} sent")
        else:
            print(f"⚠️  Commands sent: {status['commands_sent']}")
        
        print("✅ Smoke test passed")
        return True
    
    def lockstep_test(self):
        """Verify both workers render identically"""
        print("\n=== LOCKSTEP TEST ===")
        
        # Sample from both rings
        print("Sampling audio from both rings...")
        
        # Force read from both rings
        primary_samples = []
        standby_samples = []
        
        for _ in range(10):
            # Read from primary
            audio = self.supervisor.primary_audio_ring.read_latest()
            if audio is not None:
                primary_samples.append(audio[:10])  # First 10 samples
            
            # Read from standby
            audio = self.supervisor.standby_audio_ring.read_latest()
            if audio is not None:
                standby_samples.append(audio[:10])
            
            time.sleep(0.01)
        
        if len(primary_samples) > 0 and len(standby_samples) > 0:
            # Compare samples (should be nearly identical)
            primary_hash = np.mean([np.sum(s) for s in primary_samples])
            standby_hash = np.mean([np.sum(s) for s in standby_samples])
            
            diff = abs(primary_hash - standby_hash)
            if diff < 0.01:  # Allow tiny floating point differences
                print(f"✅ Lockstep verified: difference={diff:.6f}")
                return True
            else:
                print(f"❌ Lockstep failed: difference={diff:.6f}")
                return False
        else:
            print("⚠️  Could not sample both rings")
            return False
    
    def failover_test_clean_exit(self):
        """Test failover on clean worker exit"""
        print("\n=== FAILOVER TEST: CLEAN EXIT ===")
        
        initial_status = self.supervisor.get_status()
        primary_pid = initial_status['primary_pid']
        
        print(f"Terminating primary worker (PID {primary_pid})...")
        start_time = time.monotonic_ns()
        
        # Clean termination
        try:
            os.kill(primary_pid, signal.SIGTERM)
        except:
            pass
        
        # Wait for failover
        time.sleep(0.02)  # 20ms max wait
        
        status = self.supervisor.get_status()
        
        # Check failover occurred
        if status['active_worker'] == 'standby' or status['primary_pid'] != primary_pid:
            detection_time = (time.monotonic_ns() - start_time) / 1_000_000
            print(f"✅ Failover completed in {detection_time:.2f}ms")
            
            if detection_time < 10:
                print(f"✅ Met <10ms target")
            else:
                print(f"⚠️  Exceeded 10ms target")
            
            self.test_results['clean_exit_ms'] = detection_time
            return True
        else:
            print("❌ Failover did not occur")
            return False
    
    def failover_test_sigkill(self):
        """Test failover on SIGKILL"""
        print("\n=== FAILOVER TEST: SIGKILL ===")
        
        # Wait for standby to respawn
        timeout = time.time() + 2
        while not self.supervisor.metrics.spare_ready and time.time() < timeout:
            time.sleep(0.1)
        
        initial_status = self.supervisor.get_status()
        primary_pid = initial_status['primary_pid']
        
        print(f"Killing primary worker (PID {primary_pid})...")
        start_time = time.monotonic_ns()
        
        # Hard kill
        try:
            os.kill(primary_pid, signal.SIGKILL)
        except:
            pass
        
        # Wait for failover
        time.sleep(0.02)  # 20ms max wait
        
        status = self.supervisor.get_status()
        
        # Check failover occurred
        if status['primary_pid'] != primary_pid:
            detection_time = (time.monotonic_ns() - start_time) / 1_000_000
            print(f"✅ Failover completed in {detection_time:.2f}ms")
            
            if detection_time < 10:
                print(f"✅ Met <10ms target")
            else:
                print(f"⚠️  Exceeded 10ms target")
            
            self.test_results['sigkill_ms'] = detection_time
            return True
        else:
            print("❌ Failover did not occur")
            return False
    
    def failover_test_hang(self):
        """Test failover on worker hang (heartbeat timeout)"""
        print("\n=== FAILOVER TEST: HANG ===")
        
        # Wait for standby
        timeout = time.time() + 2
        while not self.supervisor.metrics.spare_ready and time.time() < timeout:
            time.sleep(0.1)
        
        initial_status = self.supervisor.get_status()
        primary_pid = initial_status['primary_pid']
        
        print(f"Simulating hang in primary worker (PID {primary_pid})...")
        start_time = time.monotonic_ns()
        
        # Send SIGSTOP to freeze the process
        try:
            os.kill(primary_pid, signal.SIGSTOP)
        except:
            pass
        
        # Wait for heartbeat timeout (should be ~15ms)
        time.sleep(0.025)  # 25ms max wait
        
        status = self.supervisor.get_status()
        
        # Check failover occurred
        if status['primary_pid'] != primary_pid:
            detection_time = (time.monotonic_ns() - start_time) / 1_000_000
            print(f"✅ Failover completed in {detection_time:.2f}ms")
            
            if detection_time < 20:  # Slightly higher threshold for heartbeat
                print(f"✅ Met heartbeat timeout target")
            else:
                print(f"⚠️  Exceeded timeout target")
            
            self.test_results['hang_ms'] = detection_time
            
            # Clean up frozen process
            try:
                os.kill(primary_pid, signal.SIGKILL)
            except:
                pass
            
            return True
        else:
            print("❌ Failover did not occur")
            # Unfreeze the process
            try:
                os.kill(primary_pid, signal.SIGCONT)
            except:
                pass
            return False
    
    def standby_crash_test(self):
        """Test standby crash while idle"""
        print("\n=== STANDBY CRASH TEST ===")
        
        # Wait for standby
        timeout = time.time() + 2
        while not self.supervisor.metrics.spare_ready and time.time() < timeout:
            time.sleep(0.1)
        
        initial_status = self.supervisor.get_status()
        standby_pid = initial_status['standby_pid']
        
        print(f"Killing standby worker (PID {standby_pid})...")
        rebuild_start = time.monotonic_ns()
        
        try:
            os.kill(standby_pid, signal.SIGKILL)
        except:
            pass
        
        # Wait for respawn
        timeout = time.time() + 1
        while time.time() < timeout:
            status = self.supervisor.get_status()
            if status['standby_pid'] and status['standby_pid'] != standby_pid:
                rebuild_time = (time.monotonic_ns() - rebuild_start) / 1_000_000
                print(f"✅ Standby respawned in {rebuild_time:.2f}ms")
                
                if rebuild_time < 500:
                    print(f"✅ Met <500ms rebuild target")
                else:
                    print(f"⚠️  Exceeded rebuild target")
                
                self.test_results['rebuild_ms'] = rebuild_time
                return True
            time.sleep(0.01)
        
        print("❌ Standby did not respawn")
        return False
    
    def resource_hygiene_test(self, cycles=50):
        """Test for resource leaks over multiple kill/restart cycles"""
        print(f"\n=== RESOURCE HYGIENE TEST ({cycles} cycles) ===")
        
        # Get initial resource counts
        process = psutil.Process()
        initial_fds = process.num_fds()
        initial_threads = process.num_threads()
        
        print(f"Initial resources: FDs={initial_fds}, Threads={initial_threads}")
        
        # Run kill/restart cycles
        for i in range(cycles):
            status = self.supervisor.get_status()
            worker_pid = status['primary_pid'] if i % 2 == 0 else status['standby_pid']
            
            if worker_pid:
                try:
                    os.kill(worker_pid, signal.SIGKILL)
                except:
                    pass
            
            # Wait for recovery
            time.sleep(0.1)
            
            if i % 5 == 0:
                print(f"  Cycle {i+1}/{cycles}...")
        
        # Check final resources
        time.sleep(0.5)  # Let things settle
        final_fds = process.num_fds()
        final_threads = process.num_threads()
        
        print(f"Final resources: FDs={final_fds}, Threads={final_threads}")
        
        fd_leak = final_fds - initial_fds
        thread_leak = final_threads - initial_threads
        
        if fd_leak <= 2 and thread_leak <= 1:  # Allow minor variance
            print(f"✅ No significant leaks: FD delta={fd_leak}, Thread delta={thread_leak}")
            return True
        else:
            print(f"❌ Resource leaks detected: FD delta={fd_leak}, Thread delta={thread_leak}")
            return False
    
    def performance_summary(self):
        """Print performance summary"""
        print("\n=== PERFORMANCE SUMMARY ===")
        
        metrics = self.supervisor.metrics
        status = self.supervisor.get_status()
        
        print(f"Total crashes: {metrics.crash_count}")
        print(f"Total failovers: {metrics.failovers}")
        print(f"Replacements spawned: {metrics.replacements}")
        print(f"Commands sent: {metrics.commands_sent}")
        
        if metrics.failover_times_ns:
            p50 = metrics.get_percentile(metrics.failover_times_ns, 50)
            p95 = metrics.get_percentile(metrics.failover_times_ns, 95)
            p99 = metrics.get_percentile(metrics.failover_times_ns, 99)
            print(f"Failover times: p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")
        
        if metrics.rebuild_times_ns:
            p50 = metrics.get_percentile(metrics.rebuild_times_ns, 50)
            p95 = metrics.get_percentile(metrics.rebuild_times_ns, 95)
            print(f"Rebuild times: p50={p50:.2f}ms, p95={p95:.2f}ms")
        
        print(f"Ring underruns: Primary={status['primary_ring_underruns']}, Standby={status['standby_ring_underruns']}")
        
        # Check against targets
        print("\n=== TARGET COMPLIANCE ===")
        if 'sigkill_ms' in self.test_results and self.test_results['sigkill_ms'] < 10:
            print("✅ Detection p95 <10ms")
        else:
            print("❌ Detection p95 >10ms")
        
        if metrics.failover_times_ns and metrics.get_percentile(metrics.failover_times_ns, 95) < 10:
            print("✅ Switch p95 <10ms")
        else:
            print("❌ Switch p95 >10ms")
        
        if 'rebuild_ms' in self.test_results and self.test_results['rebuild_ms'] < 500:
            print("✅ Rebuild <500ms")
        else:
            print("❌ Rebuild >500ms")
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 60)
        print("PHASE 1C SUPERVISOR TEST SUITE")
        print("=" * 60)
        
        results = []
        
        # Run tests
        results.append(("Smoke Test", self.smoke_test()))
        results.append(("Lockstep Test", self.lockstep_test()))
        results.append(("Clean Exit Failover", self.failover_test_clean_exit()))
        results.append(("SIGKILL Failover", self.failover_test_sigkill()))
        results.append(("Hang Detection", self.failover_test_hang()))
        results.append(("Standby Crash", self.standby_crash_test()))
        results.append(("Resource Hygiene", self.resource_hygiene_test()))
        
        # Summary
        self.performance_summary()
        
        print("\n=== TEST RESULTS ===")
        passed = 0
        for name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{name}: {status}")
            if result:
                passed += 1
        
        print(f"\nTotal: {passed}/{len(results)} tests passed")
        
        # Cleanup
        print("\nStopping supervisor...")
        self.supervisor.stop()
        
        return passed == len(results)


if __name__ == "__main__":
    # Check if we're in venv
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("ERROR: Not in virtual environment!")
        print("Run: source venv/bin/activate")
        sys.exit(1)
    
    tester = SupervisorTester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)