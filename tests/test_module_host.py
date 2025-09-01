#!/usr/bin/env python3
"""
Test suite for ModuleHost
Verifies chain processing and command handling
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
import time
from music_chronus.module_host import (
    ModuleHost, pack_command_v2, unpack_command_v2,
    CMD_OP_SET, CMD_OP_GATE, CMD_TYPE_FLOAT, CMD_TYPE_BOOL
)
from music_chronus.modules.base import BaseModule


class GainModule(BaseModule):
    """Simple gain module for testing."""
    
    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)
        self.params = {'gain': 1.0}
        self.param_targets = self.params.copy()
        
    def _process_audio(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        if in_buf is not None:
            np.multiply(in_buf, self.params['gain'], out=out_buf)
        else:
            out_buf.fill(0.0)


class OffsetModule(BaseModule):
    """Simple offset module for testing."""
    
    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)
        self.params = {'offset': 0.0}
        self.param_targets = self.params.copy()
        
    def _process_audio(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        if in_buf is not None:
            np.copyto(out_buf, in_buf, casting='no')
            out_buf += self.params['offset']
        else:
            out_buf.fill(self.params['offset'])


def test_command_packing():
    """Test Command Protocol v2 packing/unpacking."""
    print("Testing command packing...")
    
    # Test float parameter
    cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'sine', 'freq', 440.0)
    assert len(cmd) == 64
    
    op, dtype, module_id, param, value = unpack_command_v2(cmd)
    assert op == CMD_OP_SET
    assert dtype == CMD_TYPE_FLOAT
    assert module_id == 'sine'
    assert param == 'freq'
    assert abs(value - 440.0) < 0.001
    
    # Test bool parameter
    cmd = pack_command_v2(CMD_OP_GATE, CMD_TYPE_BOOL, 'adsr', 'gate', True)
    op, dtype, module_id, param, value = unpack_command_v2(cmd)
    assert op == CMD_OP_GATE
    assert dtype == CMD_TYPE_BOOL
    assert value == True
    
    # Test ASCII validation
    try:
        pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'invalid!', 'param', 1.0)
        assert False, "Should have rejected invalid module_id"
    except ValueError:
        pass
    
    print("✅ Command packing test passed")


def test_module_management():
    """Test adding/removing modules."""
    print("\nTesting module management...")
    
    host = ModuleHost(44100, 256)
    
    # Add modules
    gain = GainModule(44100, 256)
    offset = OffsetModule(44100, 256)
    
    assert host.add_module('gain', gain) == True
    assert host.add_module('offset', offset) == True
    
    # Can't add duplicate
    assert host.add_module('gain', gain) == False
    
    # Get module
    assert host.get_module('gain') == gain
    assert host.get_module('nonexistent') == None
    
    # Remove module
    assert host.remove_module('gain') == True
    assert host.remove_module('gain') == False  # Already removed
    
    # Check stats
    stats = host.get_stats()
    assert stats['modules'] == 1  # Only offset left
    assert 'offset' in stats['module_ids']
    
    print("✅ Module management test passed")


def test_chain_processing():
    """Test audio processing through chain."""
    print("\nTesting chain processing...")
    
    host = ModuleHost(44100, 256)
    
    # Build chain: gain → offset
    gain = GainModule(44100, 256)
    offset = OffsetModule(44100, 256)
    
    host.add_module('gain', gain)
    host.add_module('offset', offset)
    
    # Set parameters directly
    gain.set_param('gain', 2.0, immediate=True)
    offset.set_param('offset', 0.5, immediate=True)
    
    # Process
    input_buf = np.ones(256, dtype=np.float32) * 0.25
    output = host.process_chain(input_buf)
    
    # Should be: 0.25 * 2.0 + 0.5 = 1.0
    expected = 1.0
    assert np.allclose(output, expected)
    
    # Test without input (generator mode)
    output = host.process_chain(None)
    # Should be: 0 * 2.0 + 0.5 = 0.5
    assert np.allclose(output, 0.5)
    
    print("✅ Chain processing test passed")


def test_command_processing():
    """Test command queue and processing."""
    print("\nTesting command processing...")
    
    host = ModuleHost(44100, 256)
    
    # Add module
    gain = GainModule(44100, 256)
    host.add_module('gain', gain)
    
    # Queue commands
    cmd1 = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'gain', 'gain', 0.5)
    cmd2 = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 'gain', 'gain', 0.8)
    
    host.queue_command(cmd1)
    host.queue_command(cmd2)
    
    assert len(host.pending_commands) == 2
    
    # Process chain (should apply commands)
    input_buf = np.ones(256, dtype=np.float32)
    output = host.process_chain(input_buf)
    
    # Commands should be processed
    assert len(host.pending_commands) == 0
    assert host.commands_processed == 2
    
    # Last command should have set gain to 0.8
    # (might be smoothing toward it)
    assert gain.param_targets['gain'] == 0.8
    
    print("✅ Command processing test passed")


def test_zero_allocation():
    """Test that chain processing is allocation-free."""
    print("\nTesting zero-allocation...")
    
    import gc
    
    host = ModuleHost(44100, 256)
    
    # Add modules
    host.add_module('gain1', GainModule(44100, 256))
    host.add_module('offset', OffsetModule(44100, 256))
    host.add_module('gain2', GainModule(44100, 256))
    
    input_buf = np.ones(256, dtype=np.float32)
    
    # Warm up
    for _ in range(100):
        host.process_chain(input_buf)
    
    # Measure allocations
    gc.collect()
    start_objects = len(gc.get_objects())
    
    # Process many buffers with commands
    for i in range(1000):
        # Add command every 10 buffers
        if i % 10 == 0:
            cmd = pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, 
                                 'gain1', 'gain', 0.5 + (i % 5) * 0.1)
            host.queue_command(cmd)
        
        host.process_chain(input_buf)
    
    gc.collect()
    end_objects = len(gc.get_objects())
    
    object_growth = end_objects - start_objects
    print(f"  Object growth: {object_growth} objects")
    
    # Should have minimal growth
    assert object_growth < 200, f"Too many allocations: {object_growth}"
    
    print("✅ Zero-allocation test passed")


def test_performance():
    """Benchmark chain processing."""
    print("\nTesting performance...")
    
    host = ModuleHost(44100, 256)
    
    # Build 3-module chain
    host.add_module('gain1', GainModule(44100, 256))
    host.add_module('offset', OffsetModule(44100, 256))
    host.add_module('gain2', GainModule(44100, 256))
    
    input_buf = np.ones(256, dtype=np.float32)
    
    # Warm up
    for _ in range(100):
        host.process_chain(input_buf)
    
    # Benchmark
    iterations = 10000
    start = time.perf_counter()
    
    for _ in range(iterations):
        host.process_chain(input_buf)
    
    elapsed = time.perf_counter() - start
    
    # Calculate metrics
    buffers_per_second = iterations / elapsed
    realtime_factor = buffers_per_second * 256 / 44100
    us_per_buffer = (elapsed / iterations) * 1_000_000
    
    print(f"  3-module chain: {us_per_buffer:.1f} µs/buffer")
    print(f"  {realtime_factor:.1f}x realtime")
    
    # Should be much faster than realtime
    assert realtime_factor > 10, f"Too slow: {realtime_factor:.1f}x"
    
    print("✅ Performance test passed")


def run_all_tests():
    """Run all ModuleHost tests."""
    print("=" * 60)
    print("ModuleHost Test Suite")
    print("=" * 60)
    
    tests = [
        test_command_packing,
        test_module_management,
        test_chain_processing,
        test_command_processing,
        test_zero_allocation,
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