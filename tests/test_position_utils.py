#!/usr/bin/env python3
"""
Unit tests for PositionUtils class in shared_utils.py.
"""

import sys
import math
from unittest.mock import MagicMock
import pytest

# Mock external dependencies
sys.modules['rclpy'] = MagicMock()
sys.modules['rclpy.node'] = MagicMock()
sys.modules['sensor_msgs'] = MagicMock()
sys.modules['sensor_msgs.msg'] = MagicMock()
sys.modules['std_msgs'] = MagicMock()
sys.modules['std_msgs.msg'] = MagicMock()

from luxo_behaviors.shared_utils import PositionUtils


class TestPositionUtils:
    """Tests for PositionUtils class."""
    
    def test_normalize_angle_positive(self):
        """Test normalizing positive angles."""
        result = PositionUtils.normalize_angle(1.57)  # pi/2
        assert abs(result - 1.57) < 0.001
        
        result = PositionUtils.normalize_angle(3.14)  # pi
        assert abs(result - 3.14) < 0.001
    
    def test_normalize_angle_wraps_pi(self):
        """Test that angles > pi wrap to [-pi, pi]."""
        result = PositionUtils.normalize_angle(4.0)  # > pi
        assert -math.pi <= result <= math.pi
        
        result = PositionUtils.normalize_angle(7.0)  # > 2*pi
        assert -math.pi <= result <= math.pi
    
    def test_normalize_angle_negative(self):
        """Test normalizing negative angles."""
        result = PositionUtils.normalize_angle(-1.57)  # -pi/2
        assert abs(result - (-1.57)) < 0.001
        
        result = PositionUtils.normalize_angle(-4.0)  # < -pi
        assert -math.pi <= result <= math.pi
    
    def test_calculate_position_distance_same(self):
        """Test distance between identical positions is 0."""
        pos1 = [0.0, 0.0, 0.0, 0.0, 0.0]
        pos2 = [0.0, 0.0, 0.0, 0.0, 0.0]
        distance = PositionUtils.calculate_position_distance(pos1, pos2)
        assert distance == 0.0
    
    def test_calculate_position_distance_different(self):
        """Test distance calculation for different positions."""
        pos1 = [0.0, 0.0, 0.0, 0.0, 0.0]
        pos2 = [1.0, 0.0, 0.0, 0.0, 0.0]
        distance = PositionUtils.calculate_position_distance(pos1, pos2)
        assert abs(distance - 1.0) < 0.001
    
    def test_calculate_position_distance_empty(self):
        """Test that empty positions return infinity."""
        assert PositionUtils.calculate_position_distance([], [1.0]) == float('inf')
        assert PositionUtils.calculate_position_distance([1.0], []) == float('inf')
    
    def test_calculate_position_distance_length_mismatch(self):
        """Test that length mismatch returns infinity."""
        pos1 = [0.0, 0.0]
        pos2 = [0.0, 0.0, 0.0]
        assert PositionUtils.calculate_position_distance(pos1, pos2) == float('inf')
    
    def test_at_position_same(self):
        """Test that identical positions are at same position."""
        pos1 = [0.1, 0.2, 0.3, 0.4, 0.5]
        pos2 = [0.1, 0.2, 0.3, 0.4, 0.5]
        assert PositionUtils.at_position(pos1, pos2) is True
    
    def test_at_position_within_tolerance(self):
        """Test positions within tolerance are considered same."""
        pos1 = [0.0, 0.0, 0.0, 0.0, 0.0]
        pos2 = [0.04, 0.04, 0.04, 0.04, 0.04]  # within 0.05 tolerance
        assert PositionUtils.at_position(pos1, pos2) is True
    
    def test_at_position_outside_tolerance(self):
        """Test positions outside tolerance are different."""
        pos1 = [0.0, 0.0, 0.0, 0.0, 0.0]
        pos2 = [0.06, 0.06, 0.06, 0.06, 0.06]  # outside 0.05 tolerance
        assert PositionUtils.at_position(pos1, pos2) is False
    
    def test_at_position_length_mismatch(self):
        """Test that length mismatch returns False."""
        pos1 = [0.0, 0.0]
        pos2 = [0.0, 0.0, 0.0]
        assert PositionUtils.at_position(pos1, pos2) is False
    
    def test_at_home_position_ignore_base(self):
        """Test home position check ignoring base joint."""
        current = [3.14, 0.1, 0.2, 0.3, 0.4]  # base different
        home = [0.0, 0.1, 0.2, 0.3, 0.4]
        assert PositionUtils.at_home_position(current, home, 0.05, ignore_base=True) is True
    
    def test_at_home_position_include_base(self):
        """Test home position check including base joint."""
        current = [3.14, 0.1, 0.2, 0.3, 0.4]  # base different
        home = [0.0, 0.1, 0.2, 0.3, 0.4]
        assert PositionUtils.at_home_position(current, home, 0.05, ignore_base=False) is False
    
    def test_add_position_noise(self):
        """Test adding noise to positions."""
        pos = [0.0, 0.0, 0.0, 0.0, 0.0]
        noisy = PositionUtils.add_position_noise(pos, noise_range=0.1)
        
        # Check that noise was added (not all values should be exactly 0)
        has_noise = any(abs(v) > 0.001 for v in noisy)
        assert has_noise is True
    
    def test_add_position_noise_excludes_indices(self):
        """Test that excluded indices don't get noise."""
        pos = [0.0, 0.0, 0.0, 0.0, 0.0]
        noisy = PositionUtils.add_position_noise(pos, noise_range=0.1, exclude_indices=[0, 2])
        
        # First and third positions should be unchanged
        assert noisy[0] == 0.0
        assert noisy[2] == 0.0
    
    def test_clip_to_limits(self):
        """Test clipping positions to limits."""
        pos = [1.0, 2.0, 3.0, 4.0, 5.0]
        min_limits = [0.0, 0.0, 0.0, 0.0, 0.0]
        max_limits = [2.0, 2.0, 2.0, 2.0, 2.0]
        
        clipped = PositionUtils.clip_to_limits(pos, min_limits, max_limits)
        
        assert clipped[0] == 1.0  # within limits
        assert clipped[1] == 2.0  # at max
        assert clipped[2] == 2.0  # clipped to max
        assert clipped[3] == 2.0  # clipped to max
        assert clipped[4] == 2.0  # clipped to max
    
    def test_interpolate_positions(self):
        """Test linear interpolation between positions."""
        start = [0.0, 0.0, 0.0, 0.0, 0.0]
        end = [1.0, 1.0, 1.0, 1.0, 1.0]
        
        # Interpolate at 0.5 (middle)
        result = PositionUtils.interpolate_positions(start, end, 0.5)
        
        for val in result:
            assert abs(val - 0.5) < 0.001
    
    def test_interpolate_positions_length_mismatch(self):
        """Test that length mismatch returns start position."""
        start = [0.0, 0.0]
        end = [1.0, 1.0, 1.0]
        result = PositionUtils.interpolate_positions(start, end, 0.5)
        assert result == start
    
    def test_get_position_velocity(self):
        """Test velocity calculation."""
        pos1 = [0.0, 0.0, 0.0, 0.0, 0.0]
        pos2 = [1.0, 1.0, 1.0, 1.0, 1.0]
        time_delta = 1.0
        
        velocity = PositionUtils.get_position_velocity(pos1, pos2, time_delta)
        
        for val in velocity:
            assert abs(val - 1.0) < 0.001
    
    def test_get_position_velocity_zero_time(self):
        """Test that zero time delta returns zero velocity."""
        pos1 = [0.0, 0.0]
        pos2 = [1.0, 1.0]
        velocity = PositionUtils.get_position_velocity(pos1, pos2, 0.0)
        
        assert velocity == [0.0, 0.0]
    
    def test_get_position_velocity_negative_time(self):
        """Test that negative time delta returns zero velocity."""
        pos1 = [0.0, 0.0]
        pos2 = [1.0, 1.0]
        velocity = PositionUtils.get_position_velocity(pos1, pos2, -1.0)
        
        assert velocity == [0.0, 0.0]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
