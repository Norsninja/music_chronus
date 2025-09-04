"""
Unit tests for sequencer timing calculations.
Deterministic tests only - no actual time.sleep or threading.
"""

import unittest
from dataclasses import dataclass
from typing import List, Optional


# Constants matching our audio engine
SAMPLE_RATE = 44100
BUFFER_SIZE = 512
BUFFER_PERIOD = BUFFER_SIZE / SAMPLE_RATE  # ~0.0116 seconds


@dataclass
class SequencerTiming:
    """Timing calculations for sequencer."""
    bpm: float
    division: int  # 4 = quarter note, 16 = sixteenth note
    gate_length: float = 0.5  # Fraction of step duration
    
    @property
    def step_duration_sec(self) -> float:
        """Duration of one step in seconds."""
        # Division: 4 = quarter note, 8 = eighth, 16 = sixteenth
        # At 120 BPM: quarter = 0.5s, eighth = 0.25s, sixteenth = 0.125s
        beat_duration = 60.0 / self.bpm  # Duration of one beat (quarter note)
        return beat_duration / (self.division / 4)
    
    @property
    def buffers_per_step(self) -> int:
        """Number of audio buffers per sequencer step."""
        return round(self.step_duration_sec / BUFFER_PERIOD)
    
    @property 
    def gate_buffers(self) -> int:
        """Number of buffers the gate stays on."""
        return round(self.gate_length * self.buffers_per_step)
    
    def step_to_buffer(self, step: int) -> int:
        """Convert step index to buffer index."""
        return step * self.buffers_per_step
    
    def buffer_to_step(self, buffer: int) -> tuple[int, int]:
        """
        Convert buffer index to step and remaining buffers.
        Returns: (step_index, buffers_until_next_step)
        """
        step = buffer // self.buffers_per_step
        remaining = self.buffers_per_step - (buffer % self.buffers_per_step)
        return step, remaining


class TestSequencerTiming(unittest.TestCase):
    """Test timing calculations."""
    
    def test_step_duration_120bpm_quarter(self):
        """120 BPM, quarter notes (division=4)."""
        timing = SequencerTiming(bpm=120, division=4)
        # At 120 BPM, quarter note = 0.5 seconds
        self.assertAlmostEqual(timing.step_duration_sec, 0.5, places=3)
    
    def test_step_duration_120bpm_sixteenth(self):
        """120 BPM, sixteenth notes (division=16)."""
        timing = SequencerTiming(bpm=120, division=16)
        # At 120 BPM, sixteenth note = 0.125 seconds
        self.assertAlmostEqual(timing.step_duration_sec, 0.125, places=3)
    
    def test_buffers_per_step_120bpm_quarter(self):
        """Calculate buffers for quarter notes at 120 BPM."""
        timing = SequencerTiming(bpm=120, division=4)
        # 0.5 sec / 0.0116 sec = ~43 buffers
        self.assertEqual(timing.buffers_per_step, 43)
    
    def test_buffers_per_step_120bpm_eighth(self):
        """Calculate buffers for eighth notes at 120 BPM."""
        timing = SequencerTiming(bpm=120, division=8)
        # 0.25 sec / 0.0116 sec = ~22 buffers
        self.assertEqual(timing.buffers_per_step, 22)
    
    def test_buffers_per_step_140bpm_sixteenth(self):
        """Calculate buffers for sixteenth notes at 140 BPM."""
        timing = SequencerTiming(bpm=140, division=16)
        # (60/140)/4 sec / 0.0116 sec = ~9 buffers
        self.assertEqual(timing.buffers_per_step, 9)
    
    def test_gate_length_calculation(self):
        """Test gate length as fraction of step."""
        timing = SequencerTiming(bpm=120, division=4, gate_length=0.25)
        # 25% of 43 buffers = ~11 buffers
        self.assertEqual(timing.gate_buffers, 11)
        
        timing.gate_length = 0.5
        # 50% of 43 buffers = ~22 buffers
        self.assertEqual(timing.gate_buffers, 22)
        
        timing.gate_length = 1.0
        # 100% of 43 buffers = 43 buffers
        self.assertEqual(timing.gate_buffers, 43)
    
    def test_step_to_buffer_mapping(self):
        """Map step indices to buffer indices."""
        timing = SequencerTiming(bpm=120, division=4)
        
        # Kick pattern x...x...x...x... at steps 0,4,8,12
        self.assertEqual(timing.step_to_buffer(0), 0)
        self.assertEqual(timing.step_to_buffer(4), 172)  # 4 * 43
        self.assertEqual(timing.step_to_buffer(8), 344)  # 8 * 43
        self.assertEqual(timing.step_to_buffer(12), 516) # 12 * 43
    
    def test_buffer_to_step_mapping(self):
        """Map buffer indices back to steps."""
        timing = SequencerTiming(bpm=120, division=4)
        
        # Buffer 0 = step 0, 43 buffers remaining
        step, remaining = timing.buffer_to_step(0)
        self.assertEqual(step, 0)
        self.assertEqual(remaining, 43)
        
        # Buffer 42 = step 0, 1 buffer remaining
        step, remaining = timing.buffer_to_step(42)
        self.assertEqual(step, 0)
        self.assertEqual(remaining, 1)
        
        # Buffer 43 = step 1, 43 buffers remaining
        step, remaining = timing.buffer_to_step(43)
        self.assertEqual(step, 1)
        self.assertEqual(remaining, 43)
        
        # Buffer 172 = step 4
        step, remaining = timing.buffer_to_step(172)
        self.assertEqual(step, 4)
        self.assertEqual(remaining, 43)
    
    def test_tempo_change_recalculation(self):
        """Tempo changes should update timing."""
        timing = SequencerTiming(bpm=120, division=4)
        original_buffers = timing.buffers_per_step
        
        # Change tempo
        timing.bpm = 140
        new_buffers = timing.buffers_per_step
        
        # Faster tempo = fewer buffers per step
        self.assertLess(new_buffers, original_buffers)
        # 140 BPM quarter = ~37 buffers
        self.assertEqual(new_buffers, 37)
    
    def test_rounding_consistency(self):
        """Verify rounding is consistent."""
        # Test various BPMs to ensure rounding works
        test_cases = [
            (60, 4, 86),   # Very slow
            (90, 4, 57),   # Slow
            (120, 4, 43),  # Medium
            (140, 4, 37),  # Fast
            (160, 4, 32),  # Faster
            (180, 4, 29),  # Very fast
        ]
        
        for bpm, div, expected in test_cases:
            timing = SequencerTiming(bpm=bpm, division=div)
            self.assertEqual(timing.buffers_per_step, expected,
                           f"Failed for {bpm} BPM")


class TestStepScheduler(unittest.TestCase):
    """Test step scheduling logic."""
    
    def test_pattern_cycle(self):
        """Test cycling through a pattern."""
        steps = 16
        current_step = 0
        
        # Simulate advancing through pattern
        for _ in range(20):  # More than one cycle
            next_step = (current_step + 1) % steps
            self.assertLess(next_step, steps)
            self.assertGreaterEqual(next_step, 0)
            current_step = next_step
    
    def test_gate_on_off_scheduling(self):
        """Test gate on/off event scheduling."""
        timing = SequencerTiming(bpm=120, division=4, gate_length=0.5)
        pattern = [True, False, False, False] * 4  # x...x...x...x...
        
        events = []
        current_buffer = 0
        
        for step in range(16):
            if pattern[step]:
                # Gate on at step boundary
                on_buffer = timing.step_to_buffer(step)
                events.append(('gate_on', on_buffer))
                
                # Gate off after gate_length
                off_buffer = on_buffer + timing.gate_buffers
                events.append(('gate_off', off_buffer))
        
        # Should have 4 on and 4 off events
        on_events = [e for e in events if e[0] == 'gate_on']
        off_events = [e for e in events if e[0] == 'gate_off']
        self.assertEqual(len(on_events), 4)
        self.assertEqual(len(off_events), 4)
        
        # Check timing
        self.assertEqual(on_events[0][1], 0)    # First on at buffer 0
        self.assertEqual(on_events[1][1], 172)  # Second on at buffer 172
        self.assertEqual(off_events[0][1], 22)  # First off at buffer 22 (50% of 43)


if __name__ == '__main__':
    unittest.main()