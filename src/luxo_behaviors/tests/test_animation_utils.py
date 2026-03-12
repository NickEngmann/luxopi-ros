#!/usr/bin/env python3
"""Tests for AnimationUtils class."""

import unittest
import sys
import math
import unittest.mock as mock

# Mock ROS2 imports to avoid dependency issues
sys.modules['rclpy'] = mock.MagicMock()
sys.modules['rclpy.node'] = mock.MagicMock()
sys.modules['std_msgs'] = mock.MagicMock()
sys.modules['std_msgs.msg'] = mock.MagicMock()
sys.modules['sensor_msgs'] = mock.MagicMock()
sys.modules['sensor_msgs.msg'] = mock.MagicMock()
sys.modules['luxo_interfaces'] = mock.MagicMock()
sys.modules['luxo_interfaces.msg'] = mock.MagicMock()
sys.modules['luxo_interfaces.srv'] = mock.MagicMock()
sys.modules['geometry_msgs'] = mock.MagicMock()
sys.modules['geometry_msgs.msg'] = mock.MagicMock()
sys.modules['nav_msgs'] = mock.MagicMock()
sys.modules['nav_msgs.msg'] = mock.MagicMock()

sys.path.insert(0, 'src/luxo_behaviors')

from luxo_behaviors.shared_utils import AnimationUtils


class TestAnimationUtils(unittest.TestCase):
    """Test cases for AnimationUtils class."""
    
    def test_interpolate_positions(self):
        """Test position interpolation."""
        start = [0.0, 0.0, 0.0, 0.0]
        end = [1.0, 1.0, 1.0, 1.0]
        
        # Test with 3 steps
        positions = AnimationUtils.interpolate_positions(start, end, steps=3)
        self.assertEqual(len(positions), 3)
        self.assertEqual(positions[0], start)
        self.assertEqual(positions[2], end)
        
        # Test with 2 steps (should return start and end)
        positions = AnimationUtils.interpolate_positions(start, end, steps=2)
        self.assertEqual(len(positions), 2)
        self.assertEqual(positions[0], start)
        self.assertEqual(positions[1], end)
        
        # Test with invalid steps
        positions = AnimationUtils.interpolate_positions(start, end, steps=1)
        self.assertEqual(len(positions), 2)
    
    def test_calculate_blend_factor(self):
        """Test blend factor calculation."""
        # Test when current equals target
        factor = AnimationUtils.calculate_blend_factor(0.5, 0.5)
        self.assertAlmostEqual(factor, 1.0)
        
        # Test when current is less than target
        factor = AnimationUtils.calculate_blend_factor(0.0, 1.0, blend_speed=0.1)
        self.assertAlmostEqual(factor, 0.1, places=5)
        
        # Test when current is greater than target
        factor = AnimationUtils.calculate_blend_factor(1.0, 0.0, blend_speed=0.1)
        self.assertAlmostEqual(factor, -0.1, places=5)
    
    def test_create_animation_sequence(self):
        """Test animation sequence creation."""
        # Test with empty poses
        sequence = AnimationUtils.create_animation_sequence([])
        self.assertEqual(sequence['poses'], [])
        self.assertEqual(sequence['durations'], [])
        self.assertEqual(sequence['total_duration'], 0.0)
        
        # Test with single pose
        poses = [[0.0, 0.0, 0.0, 0.0]]
        sequence = AnimationUtils.create_animation_sequence(poses)
        self.assertEqual(sequence['poses'], poses)
        self.assertEqual(sequence['durations'], [])
        self.assertEqual(sequence['total_duration'], 0.0)
        
        # Test with multiple poses
        poses = [
            [0.0, 0.0, 0.0, 0.0],
            [1.0, 1.0, 1.0, 1.0],
            [2.0, 2.0, 2.0, 2.0]
        ]
        sequence = AnimationUtils.create_animation_sequence(poses, transition_speed=1.0)
        self.assertEqual(len(sequence['poses']), 3)
        self.assertEqual(len(sequence['durations']), 2)
        self.assertGreater(sequence['total_duration'], 0.0)
    
    def test_calculate_animation_velocity(self):
        """Test animation velocity calculation."""
        start = [0.0, 0.0, 0.0, 0.0]
        end = [1.0, 2.0, 3.0, 4.0]
        duration = 1.0
        
        velocity = AnimationUtils.calculate_animation_velocity(start, end, duration)
        self.assertEqual(len(velocity), 4)
        self.assertEqual(velocity, [1.0, 2.0, 3.0, 4.0])
        
        # Test with duration of 2.0
        velocity = AnimationUtils.calculate_animation_velocity(start, end, 2.0)
        self.assertEqual(velocity, [0.5, 1.0, 1.5, 2.0])
        
        # Test with invalid duration
        velocity = AnimationUtils.calculate_animation_velocity(start, end, -1.0)
        self.assertEqual(velocity, [0.0, 0.0, 0.0, 0.0])
        
        # Test with mismatched lengths
        velocity = AnimationUtils.calculate_animation_velocity(start, [1.0, 2.0], 1.0)
        self.assertEqual(velocity, [0.0, 0.0, 0.0, 0.0])
    
    def test_smooth_animation_position(self):
        """Test animation position smoothing."""
        current = [0.0, 0.0, 0.0, 0.0]
        target = [1.0, 1.0, 1.0, 1.0]
        
        # Test with alpha = 0.1
        smoothed = AnimationUtils.smooth_animation_position(current, target, alpha=0.1)
        self.assertEqual(len(smoothed), 4)
        self.assertAlmostEqual(smoothed[0], 0.1, places=5)
        
        # Test with alpha = 0.5
        smoothed = AnimationUtils.smooth_animation_position(current, target, alpha=0.5)
        self.assertAlmostEqual(smoothed[0], 0.5, places=5)
        
        # Test with alpha = 1.0 (should return target)
        smoothed = AnimationUtils.smooth_animation_position(current, target, alpha=1.0)
        self.assertEqual(smoothed, target)
        
        # Test with invalid alpha
        smoothed = AnimationUtils.smooth_animation_position(current, target, alpha=0.0)
        self.assertEqual(smoothed, target)
        
        smoothed = AnimationUtils.smooth_animation_position(current, target, alpha=1.5)
        self.assertEqual(smoothed, target)
        
        # Test with mismatched lengths
        smoothed = AnimationUtils.smooth_animation_position(current, [1.0, 2.0], alpha=0.1)
        self.assertEqual(smoothed, [1.0, 2.0])


if __name__ == '__main__':
    unittest.main()
