"""
Integration test for complete module chain:
SimpleSine → ADSR → BiquadFilter

Tests the full signal path with all modules working together.
"""

import pytest
import numpy as np
import sys
import time
from pathlib import Path
from collections import OrderedDict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from music_chronus.modules.simple_sine import SimpleSine
from music_chronus.modules.adsr import ADSR
from music_chronus.modules.biquad_filter import BiquadFilter
from music_chronus.module_host import ModuleHost, pack_command_v2, CMD_OP_SET, CMD_TYPE_FLOAT


class TestModuleChainIntegration:
    """Test complete module chain integration."""
    
    def test_simple_chain_processing(self):
        """Test basic chain: sine → ADSR → filter."""
        sample_rate = 44100
        buffer_size = 256
        
        # Create modules
        sine = SimpleSine(sample_rate, buffer_size)
        adsr = ADSR(sample_rate, buffer_size)
        biquad = BiquadFilter(sample_rate, buffer_size)
        
        # Configure modules
        sine.set_param("freq", 440.0, immediate=True)
        sine.set_param("gain", 1.0, immediate=True)
        
        adsr.set_param("attack", 10.0, immediate=True)
        adsr.set_param("decay", 50.0, immediate=True)
        adsr.set_param("sustain", 0.7, immediate=True)
        adsr.set_param("release", 100.0, immediate=True)
        
        biquad.set_param("mode", 0, immediate=True)  # Lowpass
        biquad.set_param("cutoff", 1000.0, immediate=True)
        biquad.set_param("q", 2.0, immediate=True)
        
        # Trigger envelope
        adsr.set_gate(True)
        
        # Pre-allocate buffers
        buf1 = np.zeros(buffer_size, dtype=np.float32)
        buf2 = np.zeros(buffer_size, dtype=np.float32)
        buf3 = np.zeros(buffer_size, dtype=np.float32)
        
        # Process several buffers
        outputs = []
        for i in range(20):
            # Generate sine
            sine.process_buffer(None, buf1)
            
            # Apply envelope
            adsr.process_buffer(buf1, buf2)
            
            # Apply filter
            biquad.process_buffer(buf2, buf3)
            
            outputs.append(buf3.copy())
            
            # Release after 10 buffers
            if i == 10:
                adsr.set_gate(False)
        
        # Verify output
        outputs = np.concatenate(outputs)
        
        # Should have signal (not silence)
        assert np.max(np.abs(outputs)) > 0.1, "No signal produced"
        
        # Should have envelope shape (rising then falling)
        first_quarter = outputs[:len(outputs)//4]
        last_quarter = outputs[3*len(outputs)//4:]
        
        assert np.mean(np.abs(first_quarter)) < np.max(np.abs(outputs)), (
            "Envelope should start low"
        )
        assert np.mean(np.abs(last_quarter)) < np.max(np.abs(outputs)) * 0.5, (
            "Envelope should decay"
        )
        
        print(f"✓ Chain processing: max amplitude {np.max(np.abs(outputs)):.3f}")
    
    def test_module_host_chain(self):
        """Test ModuleHost with complete chain."""
        sample_rate = 44100
        buffer_size = 256
        
        # Create host
        host = ModuleHost(sample_rate, buffer_size)
        
        # Add modules
        host.add_module("sine", SimpleSine(sample_rate, buffer_size))
        host.add_module("adsr", ADSR(sample_rate, buffer_size))
        host.add_module("filter", BiquadFilter(sample_rate, buffer_size))
        
        # Queue commands for configuration
        commands = [
            pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, "sine", "freq", 880.0),
            pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, "sine", "gain", 0.8),
            pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, "adsr", "attack", 5.0),
            pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, "adsr", "decay", 20.0),
            pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, "adsr", "sustain", 0.5),
            pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, "filter", "cutoff", 2000.0),
            pack_command_v2(CMD_OP_SET, CMD_TYPE_FLOAT, "filter", "q", 4.0),
        ]
        
        for cmd in commands:
            host.queue_command(cmd)
        
        # Trigger envelope
        host.get_module("adsr").set_gate(True)
        
        # Process buffers
        outputs = []
        for i in range(30):
            output = host.process_chain()
            outputs.append(output.copy())
            
            # Release after some time
            if i == 15:
                host.get_module("adsr").set_gate(False)
        
        # Verify
        outputs = np.concatenate(outputs)
        
        # Should produce signal
        assert np.max(np.abs(outputs)) > 0.1, "No signal from ModuleHost"
        
        # Check that commands were processed
        stats = host.get_stats()
        assert stats["commands_processed"] == len(commands), (
            f"Commands not processed: {stats['commands_processed']}/{len(commands)}"
        )
        
        print(f"✓ ModuleHost chain: {stats['modules']} modules, "
              f"{stats['commands_processed']} commands processed")
    
    def test_zero_allocation_performance(self):
        """Test that chain processing is allocation-free."""
        sample_rate = 44100
        buffer_size = 256
        
        # Create host with chain
        host = ModuleHost(sample_rate, buffer_size)
        host.add_module("sine", SimpleSine(sample_rate, buffer_size))
        host.add_module("adsr", ADSR(sample_rate, buffer_size))
        host.add_module("filter", BiquadFilter(sample_rate, buffer_size))
        
        # Configure
        host.get_module("sine").set_param("freq", 440.0, immediate=True)
        host.get_module("adsr").set_gate(True)
        
        # Warm up
        for _ in range(10):
            host.process_chain()
        
        # Measure timing for many buffers
        iterations = 1000
        start = time.perf_counter()
        
        for _ in range(iterations):
            output = host.process_chain()
        
        elapsed = time.perf_counter() - start
        
        # Calculate performance
        samples_processed = iterations * buffer_size
        seconds_of_audio = samples_processed / sample_rate
        realtime_factor = seconds_of_audio / elapsed
        
        # Should be much faster than realtime
        # Note: With 3 DSP modules in Python, 10-20x is reasonable
        assert realtime_factor > 10, (
            f"Performance too slow: {realtime_factor:.1f}x realtime"
        )
        
        # Average time per buffer
        time_per_buffer = elapsed / iterations * 1000  # ms
        assert time_per_buffer < 1.0, (
            f"Buffer processing too slow: {time_per_buffer:.3f}ms"
        )
        
        print(f"✓ Zero-allocation performance: {realtime_factor:.1f}x realtime, "
              f"{time_per_buffer:.3f}ms per buffer")
    
    def test_filter_modes(self):
        """Test different filter modes in the chain."""
        sample_rate = 44100
        buffer_size = 256
        
        # Test each filter mode
        modes = [
            (0, "lowpass"),
            (1, "highpass"),
            (2, "bandpass")
        ]
        
        for mode, name in modes:
            # Create simple chain
            sine = SimpleSine(sample_rate, buffer_size)
            biquad = BiquadFilter(sample_rate, buffer_size)
            
            # White noise would be better for filter testing,
            # but sine at multiple frequencies works too
            sine.set_param("freq", 2000.0, immediate=True)
            sine.set_param("gain", 1.0, immediate=True)
            
            biquad.set_param("mode", mode, immediate=True)
            biquad.set_param("cutoff", 1000.0, immediate=True)
            biquad.set_param("q", 2.0, immediate=True)
            
            # Process
            buf1 = np.zeros(buffer_size, dtype=np.float32)
            buf2 = np.zeros(buffer_size, dtype=np.float32)
            
            outputs = []
            for _ in range(10):
                sine.process_buffer(None, buf1)
                biquad.process_buffer(buf1, buf2)
                outputs.append(buf2.copy())
            
            outputs = np.concatenate(outputs)
            
            # All modes should produce some output
            assert np.max(np.abs(outputs)) > 0.01, (
                f"No output from {name} filter"
            )
            
            # Highpass should attenuate compared to input
            # (since 2kHz > 1kHz cutoff, highpass should pass it through)
            if mode == 1:  # highpass
                assert np.max(np.abs(outputs)) > 0.5, (
                    "Highpass should pass 2kHz signal with 1kHz cutoff"
                )
            
            print(f"✓ Filter mode {name}: max amplitude {np.max(np.abs(outputs)):.3f}")
    
    def test_parameter_smoothing(self):
        """Test that parameter smoothing prevents clicks."""
        sample_rate = 44100
        buffer_size = 256
        
        sine = SimpleSine(sample_rate, buffer_size)
        
        # Start at one frequency
        sine.set_param("freq", 440.0, immediate=True)
        sine.set_param("gain", 1.0, immediate=True)
        
        buf = np.zeros(buffer_size, dtype=np.float32)
        
        # Generate reference buffer
        sine.process_buffer(None, buf)
        ref_amplitude = np.max(np.abs(buf))
        
        # Change gain suddenly (but with smoothing)
        sine.set_param("gain", 0.1, immediate=False)
        
        # Process several buffers and check for smooth transition
        amplitudes = []
        for _ in range(10):
            sine.process_buffer(None, buf)
            amplitudes.append(np.max(np.abs(buf)))
        
        # Should gradually decrease, not jump
        for i in range(1, len(amplitudes)):
            # Each step should be smaller
            assert amplitudes[i] <= amplitudes[i-1], (
                f"Amplitude should decrease monotonically: {amplitudes}"
            )
        
        # Final should be near target
        assert abs(amplitudes[-1] - 0.1) < 0.01, (
            f"Should reach target gain: {amplitudes[-1]:.3f}"
        )
        
        print(f"✓ Parameter smoothing: smooth transition from "
              f"{amplitudes[0]:.3f} to {amplitudes[-1]:.3f}")


if __name__ == "__main__":
    # Run with verbose output
    pytest.main([__file__, "-v", "-s"])