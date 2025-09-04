"""
Unit tests for sequencer pattern parsing and manipulation.
No timing or audio - pure data transformation tests.
"""

import unittest
from dataclasses import dataclass
from typing import List, Optional, Dict


def parse_pattern(pattern: str) -> tuple[List[bool], List[int]]:
    """
    Parse pattern string into gates and velocities.
    'x' = gate with velocity 64
    'X' = gate with velocity 127 (accent)
    '.' = no gate
    
    Returns: (gates, velocities)
    """
    gates = []
    velocities = []
    
    for char in pattern:
        if char == 'X':
            gates.append(True)
            velocities.append(127)
        elif char == 'x':
            gates.append(True)
            velocities.append(64)
        elif char == '.':
            gates.append(False)
            velocities.append(0)
        else:
            # Ignore other characters (spaces, etc)
            continue
    
    return gates, velocities


def parse_param_lane(values_str: str, steps: int) -> List[float]:
    """
    Parse CSV string or space-separated values into parameter lane.
    Truncate or pad with 0.0 to match steps.
    """
    if not values_str:
        return [0.0] * steps
    
    # Handle both CSV and space-separated
    if ',' in values_str:
        parts = values_str.split(',')
    else:
        parts = values_str.split()
    
    # Convert to floats
    values = []
    for part in parts:
        part = part.strip()
        if part:
            try:
                values.append(float(part))
            except ValueError:
                values.append(0.0)
    
    # Truncate or pad to match steps
    if len(values) > steps:
        return values[:steps]
    else:
        return values + [0.0] * (steps - len(values))


def rotate_pattern(gates: List[bool], rotation: int) -> List[bool]:
    """Rotate pattern by N steps (positive = right, negative = left)."""
    if not gates:
        return gates
    rotation = rotation % len(gates)
    return gates[-rotation:] + gates[:-rotation]


def euclidean_pattern(pulses: int, steps: int) -> List[bool]:
    """
    Generate Euclidean rhythm using Bjorklund's algorithm.
    Distributes 'pulses' as evenly as possible across 'steps'.
    """
    if pulses >= steps:
        return [True] * steps
    if pulses <= 0:
        return [False] * steps
    
    # Bjorklund's algorithm
    pattern = [[True]] * pulses + [[False]] * (steps - pulses)
    
    while len(pattern) > 1:
        # Find split point
        split = min(len(pattern) // 2, len(pattern) - len(pattern) // 2)
        if split == 0:
            break
            
        # Combine pairs
        new_pattern = []
        for i in range(split):
            new_pattern.append(pattern[i] + pattern[-(i+1)])
        
        # Add remaining
        if len(pattern) % 2 == 1:
            new_pattern.append(pattern[len(pattern) // 2])
            
        pattern = new_pattern
    
    # Flatten result
    result = []
    for group in pattern:
        result.extend(group)
    return result


class TestPatternParsing(unittest.TestCase):
    """Test pattern string parsing."""
    
    def test_basic_pattern(self):
        """Parse basic kick pattern."""
        gates, velocities = parse_pattern("x...x...x...x...")
        self.assertEqual(gates, [True] + [False]*3 + [True] + [False]*3 + 
                               [True] + [False]*3 + [True] + [False]*3)
        self.assertEqual(velocities[0], 64)
        self.assertEqual(velocities[1], 0)
    
    def test_accent_pattern(self):
        """Parse pattern with accents."""
        gates, velocities = parse_pattern("X..x..X.")
        self.assertEqual(gates, [True, False, False, True, False, False, True, False])
        self.assertEqual(velocities, [127, 0, 0, 64, 0, 0, 127, 0])
    
    def test_empty_pattern(self):
        """Parse empty/rest pattern."""
        gates, velocities = parse_pattern("........")
        self.assertEqual(gates, [False] * 8)
        self.assertEqual(velocities, [0] * 8)
    
    def test_ignore_spaces(self):
        """Spaces should be ignored in patterns."""
        gates, velocities = parse_pattern("x... x... x... x...")
        # Spaces ignored, so we get 16 steps
        self.assertEqual(len(gates), 16)
        self.assertEqual(gates[0], True)
        self.assertEqual(gates[4], True)


class TestParamLanes(unittest.TestCase):
    """Test parameter lane parsing."""
    
    def test_csv_parsing(self):
        """Parse CSV parameter values."""
        values = parse_param_lane("60,62,64,65", 8)
        self.assertEqual(values, [60.0, 62.0, 64.0, 65.0, 0.0, 0.0, 0.0, 0.0])
    
    def test_space_separated(self):
        """Parse space-separated values."""
        values = parse_param_lane("440 220 330", 4)
        self.assertEqual(values, [440.0, 220.0, 330.0, 0.0])
    
    def test_truncate_long(self):
        """Truncate values if longer than steps."""
        values = parse_param_lane("1,2,3,4,5,6", 4)
        self.assertEqual(values, [1.0, 2.0, 3.0, 4.0])
    
    def test_empty_lane(self):
        """Empty string gives zeros."""
        values = parse_param_lane("", 4)
        self.assertEqual(values, [0.0, 0.0, 0.0, 0.0])
    
    def test_invalid_values(self):
        """Invalid values become 0.0."""
        values = parse_param_lane("60,bad,64", 4)
        self.assertEqual(values, [60.0, 0.0, 64.0, 0.0])


class TestPatternManipulation(unittest.TestCase):
    """Test pattern transformations."""
    
    def test_rotate_right(self):
        """Rotate pattern to the right."""
        pattern = [True, False, False, True]
        rotated = rotate_pattern(pattern, 1)
        self.assertEqual(rotated, [True, True, False, False])
    
    def test_rotate_left(self):
        """Rotate pattern to the left."""
        pattern = [True, False, False, True]
        rotated = rotate_pattern(pattern, -1)
        self.assertEqual(rotated, [False, False, True, True])
    
    def test_rotate_full_cycle(self):
        """Rotating by pattern length returns original."""
        pattern = [True, False, True, False]
        rotated = rotate_pattern(pattern, 4)
        self.assertEqual(rotated, pattern)
    
    def test_euclidean_5_16(self):
        """Generate Euclidean rhythm E(5,16)."""
        pattern = euclidean_pattern(5, 16)
        self.assertEqual(sum(pattern), 5)  # Exactly 5 pulses
        self.assertEqual(len(pattern), 16)  # 16 steps total
        # E(5,16) should be reasonably distributed
        # Check that no two pulses are too close
        last_pulse = -1
        min_gap = 16
        for i, pulse in enumerate(pattern):
            if pulse:
                if last_pulse >= 0:
                    gap = i - last_pulse
                    min_gap = min(min_gap, gap)
                last_pulse = i
        self.assertGreaterEqual(min_gap, 2)  # At least 2 steps between pulses
    
    def test_euclidean_edge_cases(self):
        """Test Euclidean edge cases."""
        # All pulses
        self.assertEqual(euclidean_pattern(4, 4), [True] * 4)
        # No pulses
        self.assertEqual(euclidean_pattern(0, 4), [False] * 4)
        # More pulses than steps
        self.assertEqual(euclidean_pattern(5, 4), [True] * 4)


if __name__ == '__main__':
    unittest.main()