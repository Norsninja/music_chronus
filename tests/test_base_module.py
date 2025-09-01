#!/usr/bin/env python3
"""
Test suite for BaseModule
Verifies zero-allocation guarantees and parameter smoothing
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
import time
import gc
from music_chronus.modules.base import BaseModule


class TestModule(BaseModule):
    """Test implementation of BaseModule."""
    
    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)
        
        # Set up test parameters
        self.params = {
            'gain': 1.0,
            'offset': 0.0
        }
        self.param_targets = self.params.copy()
        
        # Custom smoothing times
        self.smoothing_samples = {
            'gain': int(0.010 * sample_rate),  # 10ms
            'offset': 0,  # No smoothing
            'default': int(0.005 * sample_rate)  # 5ms
        }
        
    def _process_audio(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        """Simple gain + offset processing."""
        if in_buf is not None:
            # Apply gain and offset
            gain = self.params['gain']
            offset = self.params['offset']
            
            # In-place operations only
            np.multiply(in_buf, gain, out=out_buf)
            out_buf += offset
        else:
            out_buf.fill(self.params['offset'])


def test_initialization():
    """Test module initialization."""
    print("Testing initialization...")
    
    module = TestModule(44100, 256)
    
    assert module.sr == 44100
    assert module.buffer_size == 256
    assert module.get_param('gain') == 1.0
    assert module.get_param('offset') == 0.0
    assert module.active == True
    
    print("✅ Initialization test passed")


def test_parameter_setting():
    """Test parameter setting with and without smoothing."""
    print("\nTesting parameter setting...")
    
    module = TestModule(44100, 256)
    
    # Test immediate setting
    module.set_param('gain', 0.5, immediate=True)
    assert module.params['gain'] == 0.5
    assert module.param_targets['gain'] == 0.5
    
    # Test smoothed setting
    module.set_param('gain', 0.8, immediate=False)
    assert module.param_targets['gain'] == 0.8
    # Current value shouldn't change yet
    assert module.params['gain'] == 0.5
    
    # Process a buffer to apply smoothing
    in_buf = np.ones(256, dtype=np.float32)
    out_buf = np.zeros(256, dtype=np.float32)
    module.process_buffer(in_buf, out_buf)
    
    # Value should have moved toward target
    assert 0.5 < module.params['gain'] < 0.8
    
    print("✅ Parameter setting test passed")


def test_smoothing():
    """Test parameter smoothing behavior."""
    print("\nTesting parameter smoothing...")
    
    module = TestModule(44100, 256)
    
    # Set gain with smoothing (10ms)
    module.set_param('gain', 0.0, immediate=True)
    module.set_param('gain', 1.0, immediate=False)
    
    # Process multiple buffers
    values = []
    in_buf = np.ones(256, dtype=np.float32)
    out_buf = np.zeros(256, dtype=np.float32)
    
    for _ in range(20):  # ~120ms worth
        module.process_buffer(in_buf, out_buf)
        values.append(module.params['gain'])
    
    # Should see gradual increase
    assert values[0] < values[5] < values[10]
    # Should reach target eventually
    assert abs(values[-1] - 1.0) < 0.01
    
    # Test instant parameter (offset has no smoothing)
    module.set_param('offset', 0.5, immediate=False)
    module.process_buffer(in_buf, out_buf)
    assert module.params['offset'] == 0.5  # Should be immediate
    
    print(f"✅ Smoothing test passed (final gain: {values[-1]:.4f})")


def test_zero_allocation():
    """Test that process_buffer creates no allocations."""
    print("\nTesting zero-allocation guarantee...")
    
    module = TestModule(44100, 256)
    in_buf = np.ones(256, dtype=np.float32)
    out_buf = np.zeros(256, dtype=np.float32)
    
    # Warm up
    for _ in range(10):
        module.process_buffer(in_buf, out_buf)
    
    # Force garbage collection
    gc.collect()
    
    # Measure allocations
    gc_stats_before = gc.get_stats()
    start_objects = len(gc.get_objects())
    
    # Process many buffers
    # Use pre-computed values to avoid random allocations
    test_values = [0.1, 0.5, 0.9, 0.3, 0.7]
    for i in range(1000):
        module.process_buffer(in_buf, out_buf)
        # Cycle through test values
        module.set_param('gain', test_values[i % len(test_values)])
    
    gc.collect()
    gc_stats_after = gc.get_stats()
    end_objects = len(gc.get_objects())
    
    # Check for allocation growth
    # Allow small variance for Python internals
    object_growth = end_objects - start_objects
    
    print(f"  Object growth: {object_growth} objects")
    print(f"  GC collections: {gc_stats_after[0]['collections'] - gc_stats_before[0]['collections']}")
    
    # Should have minimal object growth
    assert object_growth < 100, f"Too many allocations: {object_growth} new objects"
    
    print("✅ Zero-allocation test passed")


def test_state_persistence():
    """Test state save/restore."""
    print("\nTesting state persistence...")
    
    module = TestModule(44100, 256)
    
    # Set some parameters
    module.set_param('gain', 0.7, immediate=True)
    module.set_param('offset', -0.1, immediate=True)
    module.active = False
    
    # Get state
    state = module.get_state()
    
    # Create new module and restore
    module2 = TestModule(44100, 256)
    module2.set_state(state)
    
    assert module2.params['gain'] == 0.7
    assert module2.params['offset'] == -0.1
    assert module2.active == False
    
    print("✅ State persistence test passed")


def test_audio_processing():
    """Test actual audio processing."""
    print("\nTesting audio processing...")
    
    module = TestModule(44100, 256)
    
    # Test with gain and offset
    module.set_param('gain', 2.0, immediate=True)
    module.set_param('offset', 0.5, immediate=True)
    
    in_buf = np.ones(256, dtype=np.float32) * 0.25
    out_buf = np.zeros(256, dtype=np.float32)
    
    module.process_buffer(in_buf, out_buf)
    
    # Should be: 0.25 * 2.0 + 0.5 = 1.0
    expected = 0.25 * 2.0 + 0.5
    assert np.allclose(out_buf, expected)
    
    # Test with None input (generator mode)
    out_buf.fill(0)
    module.process_buffer(None, out_buf)
    
    # Should just be offset
    assert np.allclose(out_buf, 0.5)
    
    print("✅ Audio processing test passed")


def test_performance():
    """Benchmark processing performance."""
    print("\nTesting performance...")
    
    module = TestModule(44100, 256)
    in_buf = np.ones(256, dtype=np.float32)
    out_buf = np.zeros(256, dtype=np.float32)
    
    # Warm up
    for _ in range(100):
        module.process_buffer(in_buf, out_buf)
    
    # Benchmark
    iterations = 10000
    start = time.perf_counter()
    
    for _ in range(iterations):
        module.process_buffer(in_buf, out_buf)
    
    elapsed = time.perf_counter() - start
    
    # Calculate metrics
    buffers_per_second = iterations / elapsed
    realtime_factor = buffers_per_second * 256 / 44100
    us_per_buffer = (elapsed / iterations) * 1_000_000
    
    print(f"  Processed {iterations} buffers in {elapsed:.3f}s")
    print(f"  {buffers_per_second:.0f} buffers/sec")
    print(f"  {us_per_buffer:.1f} µs per buffer")
    print(f"  {realtime_factor:.1f}x realtime")
    
    # Should be much faster than realtime
    assert realtime_factor > 10, f"Too slow: only {realtime_factor:.1f}x realtime"
    
    print("✅ Performance test passed")


def run_all_tests():
    """Run all BaseModule tests."""
    print("=" * 60)
    print("BaseModule Test Suite")
    print("=" * 60)
    
    tests = [
        test_initialization,
        test_parameter_setting,
        test_smoothing,
        test_zero_allocation,
        test_state_persistence,
        test_audio_processing,
        test_performance
    ]
    
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} error: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    if failed == 0:
        print("✅ All tests passed!")
        return True
    else:
        print(f"❌ {failed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)