#!/usr/bin/env python3
"""
Unit tests for CollisionMath and MovementValidator classes in shared_utils.py.
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

from luxo_behaviors.shared_utils import CollisionMath, MovementValidator, SafetyLimits


class TestCollisionMath:
    """Tests for CollisionMath class."""
    
    def test_calculate_severity_safe(self):
        """Test safe severity calculation."""
        severity = CollisionMath.calculate_severity(20.0)
        assert severity == 'safe'
    
    def test_calculate_severity_warning(self):
        """Test warning severity calculation."""
        severity = CollisionMath.calculate_severity(10.0)
        assert severity == 'warning'
    
    def test_calculate_severity_danger(self):
        """Test danger severity calculation."""
        severity = CollisionMath.calculate_severity(5.0)
        assert severity == 'danger'
    
    def test_calculate_severity_at_warning_threshold(self):
        """Test severity at warning threshold (15.0)."""
        severity = CollisionMath.calculate_severity(15.0)
        assert severity == 'warning'
    
    def test_calculate_severity_at_danger_threshold(self):
        """Test severity at danger threshold (7.0)."""
        severity = CollisionMath.calculate_severity(7.0)
        assert severity == 'warning'
    
    def test_calculate_avoidance_magnitude_normal(self):
        """Test normal avoidance magnitude."""
        magnitude = CollisionMath.calculate_avoidance_magnitude('warning', 3)
        assert 0.72 <= magnitude <= 0.88  # 0.8 * 0.9 to 0.8 * 1.1
    
    def test_calculate_avoidance_magnitude_high_consecutive(self):
        """Test high consecutive count magnitude."""
        magnitude = CollisionMath.calculate_avoidance_magnitude('warning', 10)
        assert 2.25 <= magnitude <= 2.75  # 2.5 * 0.9 to 2.5 * 1.1
    
    def test_calculate_avoidance_magnitude_medium_consecutive(self):
        """Test medium consecutive count magnitude."""
        magnitude = CollisionMath.calculate_avoidance_magnitude('warning', 6)
        assert 1.8 <= magnitude <= 2.2  # 2.0 * 0.9 to 2.0 * 1.1
    
    def test_calculate_avoidance_magnitude_emergency(self):
        """Test emergency magnitude."""
        magnitude = CollisionMath.calculate_avoidance_magnitude('warning', 3, emergency=True)
        assert 1.35 <= magnitude <= 1.65  # 1.5 * 0.9 to 1.5 * 1.1
    
    def test_calculate_acceleration_danger(self):
        """Test acceleration for danger severity."""
        accel = CollisionMath.calculate_acceleration('danger', 3)
        assert accel == 17.5
    
    def test_calculate_acceleration_warning(self):
        """Test acceleration for warning severity."""
        accel = CollisionMath.calculate_acceleration('warning', 3)
        assert accel == 12.5
    
    def test_calculate_acceleration_persistent_collision(self):
        """Test increased acceleration for persistent collisions."""
        accel = CollisionMath.calculate_acceleration('warning', 10)
        assert accel == 17.5  # 12.5 + (10-5)*1.0 = 17.5
    
    def test_calculate_acceleration_base(self):
        """Test acceleration with custom base value."""
        accel = CollisionMath.calculate_acceleration('warning', 3, base_acceleration=20.0)
        assert accel == 20.0
    
    def test_calculate_escape_rotation_left(self):
        """Test escape rotation for left direction."""
        rotation = CollisionMath.calculate_escape_rotation('left')
        assert rotation == 0.6  # 0.3 * 2.0
    
    def test_calculate_escape_rotation_left_custom(self):
        """Test escape rotation with custom parameters."""
        rotation = CollisionMath.calculate_escape_rotation('left', base_rotation=0.5, escape_multiplier=3.0)
        assert rotation == 1.5  # 0.5 * 3.0
    
    def test_calculate_escape_rotation_right(self):
        """Test escape rotation for right direction."""
        rotation = CollisionMath.calculate_escape_rotation('right')
        assert rotation == -0.6  # -0.3 * 2.0
    
    def test_calculate_escape_rotation_front(self):
        """Test escape rotation for front direction (random)."""
        rotation = CollisionMath.calculate_escape_rotation('front')
        assert rotation in [0.6, -0.6]
    
    def test_check_path_blocked_no_danger(self):
        """Test path not blocked when no danger collisions."""
        collision_status = {
            'front': {'active': True, 'severity': 'warning'},
            'left': {'active': False, 'severity': 'safe'},
            'right': {'active': True, 'severity': 'warning'}
        }
        is_blocked, blocked_dirs = CollisionMath.check_path_blocked(collision_status)
        assert is_blocked is False
        assert len(blocked_dirs) == 0
    
    def test_check_path_blocked_two_danger(self):
        """Test path blocked when 2+ danger collisions."""
        collision_status = {
            'front': {'active': True, 'severity': 'danger'},
            'left': {'active': True, 'severity': 'danger'},
            'right': {'active': False, 'severity': 'safe'}
        }
        is_blocked, blocked_dirs = CollisionMath.check_path_blocked(collision_status)
        assert is_blocked is True
        assert 'front' in blocked_dirs
        assert 'left' in blocked_dirs
    
    def test_check_path_blocked_one_danger(self):
        """Test path not blocked when only 1 danger collision."""
        collision_status = {
            'front': {'active': True, 'severity': 'danger'},
            'left': {'active': False, 'severity': 'safe'},
            'right': {'active': False, 'severity': 'safe'}
        }
        is_blocked, blocked_dirs = CollisionMath.check_path_blocked(collision_status)
        assert is_blocked is False
    
    def test_calculate_safe_direction_left_blocked(self):
        """Test safe direction when left is blocked."""
        current_base = 0.0
        safe = CollisionMath.calculate_safe_direction(['left'], current_base)
        assert safe > current_base  # Should rotate right (positive)
    
    def test_calculate_safe_direction_right_blocked(self):
        """Test safe direction when right is blocked."""
        current_base = 0.0
        safe = CollisionMath.calculate_safe_direction(['right'], current_base)
        assert safe < current_base  # Should rotate left (negative)
    
    def test_calculate_safe_direction_both_blocked(self):
        """Test safe direction when both sides blocked."""
        current_base = 0.0
        safe = CollisionMath.calculate_safe_direction(['left', 'right'], current_base)
        assert abs(safe - math.pi) < 0.001  # Should rotate 180 degrees
    
    def test_calculate_safe_direction_front_only(self):
        """Test safe direction when only front is blocked."""
        current_base = 0.0
        safe = CollisionMath.calculate_safe_direction(['front'], current_base)
        # Should try to rotate either left or right
        assert abs(safe) < math.pi


class TestMovementValidator:
    """Tests for MovementValidator class."""
    
    def test_validate_position_clamps_base(self):
        """Test that base angle is clamped to limits."""
        limits = SafetyLimits()
        pos = [3.5, 0.0, 0.0, 0.0, 0.0]  # base > max
        validated = MovementValidator.validate_position(pos, limits)
        assert validated[0] == limits.max_base_angle
    
    def test_validate_position_clamps_base_negative(self):
        """Test that negative base angle is clamped."""
        limits = SafetyLimits()
        pos = [-3.5, 0.0, 0.0, 0.0, 0.0]  # base < min
        validated = MovementValidator.validate_position(pos, limits)
        assert validated[0] == limits.min_base_angle
    
    def test_validate_position_clamps_joints(self):
        """Test that joint positions are clamped to limits."""
        limits = SafetyLimits()
        pos = [0.0, 2.0, 0.0, 0.0, 0.0]  # shoulder > max
        validated = MovementValidator.validate_position(pos, limits)
        assert validated[1] == limits.joint_limits['shoulder']['max']
    
    def test_validate_position_no_clamping_needed(self):
        """Test position that doesn't need clamping."""
        limits = SafetyLimits()
        pos = [0.0, 0.5, 0.5, 0.5, 0.5]
        validated = MovementValidator.validate_position(pos, limits)
        assert validated == pos
    
    def test_check_movement_safety_safe(self):
        """Test movement is safe when no collisions."""
        current = [0.0, 0.0, 0.0, 0.0, 0.0]
        target = [0.1, 0.1, 0.1, 0.1, 0.1]
        collision_status = {}
        
        safe, message = MovementValidator.check_movement_safety(current, target, collision_status)
        assert safe is True
        assert message == "Movement safe"
    
    def test_check_movement_safety_front_collision(self):
        """Test movement blocked by front collision."""
        current = [0.0, 0.5, 0.0, 0.0, 0.0]
        target = [0.0, 0.3, 0.0, 0.0, 0.0]  # Moving shoulder forward
        collision_status = {
            'front': {'active': True, 'severity': 'danger'}
        }
        
        safe, message = MovementValidator.check_movement_safety(current, target, collision_status)
        assert safe is False
        assert 'front' in message
    
    def test_check_movement_safety_left_collision(self):
        """Test movement blocked by left collision."""
        current = [0.5, 0.0, 0.0, 0.0, 0.0]
        target = [0.3, 0.0, 0.0, 0.0, 0.0]  # Rotating left
        collision_status = {
            'left': {'active': True, 'severity': 'danger'}
        }
        
        safe, message = MovementValidator.check_movement_safety(current, target, collision_status)
        assert safe is False
        assert 'left' in message
    
    def test_check_movement_safety_right_collision(self):
        """Test movement blocked by right collision."""
        current = [-0.5, 0.0, 0.0, 0.0, 0.0]
        target = [-0.3, 0.0, 0.0, 0.0, 0.0]  # Rotating right
        collision_status = {
            'right': {'active': True, 'severity': 'danger'}
        }
        
        safe, message = MovementValidator.check_movement_safety(current, target, collision_status)
        assert safe is False
        assert 'right' in message
    
    def test_check_movement_safety_warning_not_blocked(self):
        """Test that warning severity doesn't block movement."""
        current = [0.0, 0.5, 0.0, 0.0, 0.0]
        target = [0.0, 0.3, 0.0, 0.0, 0.0]
        collision_status = {
            'front': {'active': True, 'severity': 'warning'}
        }
        
        safe, message = MovementValidator.check_movement_safety(current, target, collision_status)
        assert safe is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
