#!/usr/bin/env python3
"""Tests for shared_utils.py module."""

import unittest
import sys
import os

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

import numpy as np
from shared_utils import (
    PositionUtils, StateUtils, SafetyLimits, AnimationTracker,
    IdleAnimationConfig, CollisionMath, MovementValidator
)


class TestPositionUtils(unittest.TestCase):
    """Test cases for PositionUtils class."""
    
    def test_normalize_angle_positive(self):
        """Test angle normalization for positive angles."""
        # Test angles greater than pi
        angle = np.pi * 1.5
        normalized = PositionUtils.normalize_angle(angle)
        self.assertLess(normalized, np.pi)
        self.assertGreaterEqual(normalized, -np.pi)
    
    def test_normalize_angle_negative(self):
        """Test angle normalization for negative angles."""
        # Test angles less than -pi
        angle = -np.pi * 1.5
        normalized = PositionUtils.normalize_angle(angle)
        self.assertLess(normalized, np.pi)
        self.assertGreaterEqual(normalized, -np.pi)
    
    def test_normalize_angle_already_normalized(self):
        """Test that already normalized angles remain unchanged."""
        angle = np.pi / 2
        normalized = PositionUtils.normalize_angle(angle)
        self.assertAlmostEqual(normalized, np.pi / 2)
    
    def test_normalize_angle_zero(self):
        """Test that zero angle remains zero."""
        angle = 0.0
        normalized = PositionUtils.normalize_angle(angle)
        self.assertEqual(normalized, 0.0)
    
    def test_calculate_position_distance(self):
        """Test position distance calculation."""
        pos1 = [0.0, 0.0, 0.0]
        pos2 = [1.0, 0.0, 0.0]
        distance = PositionUtils.calculate_position_distance(pos1, pos2)
        self.assertAlmostEqual(distance, 1.0)
    
    def test_calculate_position_distance_same_position(self):
        """Test distance between same positions is zero."""
        pos1 = [1.0, 2.0, 3.0]
        pos2 = [1.0, 2.0, 3.0]
        distance = PositionUtils.calculate_position_distance(pos1, pos2)
        self.assertAlmostEqual(distance, 0.0)
    
    def test_calculate_position_distance_different_lengths(self):
        """Test distance calculation with different length positions."""
        pos1 = [0.0, 0.0]
        pos2 = [0.0, 0.0, 0.0]
        distance = PositionUtils.calculate_position_distance(pos1, pos2)
        self.assertEqual(distance, float('inf'))
    
    def test_at_position_within_tolerance(self):
        """Test position comparison within tolerance."""
        pos1 = [0.0, 0.0, 0.0]
        pos2 = [0.01, 0.01, 0.01]
        result = PositionUtils.at_position(pos1, pos2, tolerance=0.1)
        self.assertTrue(result)
    
    def test_at_position_outside_tolerance(self):
        """Test position comparison outside tolerance."""
        pos1 = [0.0, 0.0, 0.0]
        pos2 = [0.2, 0.0, 0.0]
        result = PositionUtils.at_position(pos1, pos2, tolerance=0.1)
        self.assertFalse(result)
    
    def test_at_home_position_ignore_base(self):
        """Test home position check ignoring base joint."""
        current_pos = [0.5, 0.5, 1.3, 1.4, -1.5]
        home_pos = [0.0, 0.5, 1.3, 1.4, -1.5]  # Different base
        result = PositionUtils.at_home_position(current_pos, home_pos, tolerance=0.1, ignore_base=True)
        self.assertTrue(result)
    
    def test_at_home_position_include_base(self):
        """Test home position check including base joint."""
        current_pos = [0.5, 0.5, 1.3, 1.4, -1.5]
        home_pos = [0.0, 0.5, 1.3, 1.4, -1.5]  # Different base
        result = PositionUtils.at_home_position(current_pos, home_pos, tolerance=0.1, ignore_base=False)
        self.assertFalse(result)
    
    def test_add_position_noise(self):
        """Test adding noise to positions."""
        position = [0.0, 0.0, 0.0]
        noisy = PositionUtils.add_position_noise(position, noise_range=0.1)
        # Check that noise was added (values should be different)
        self.assertNotEqual(noisy, position)
        # Check that noise is within range
        for i, (original, noisy_val) in enumerate(zip(position, noisy)):
            self.assertLessEqual(abs(noisy_val - original), 0.1)
    
    def test_add_position_noise_exclude_indices(self):
        """Test adding noise with excluded indices."""
        position = [0.0, 0.0, 0.0]
        noisy = PositionUtils.add_position_noise(position, noise_range=0.1, exclude_indices=[0])
        # First element should remain unchanged
        self.assertEqual(noisy[0], position[0])
        # Other elements should have noise
        self.assertNotEqual(noisy[1], position[1])
        self.assertNotEqual(noisy[2], position[2])
    
    def test_clip_to_limits(self):
        """Test clipping positions to limits."""
        position = [-1.0, 0.0, 2.0]
        min_limits = [0.0, 0.0, 0.0]
        max_limits = [1.0, 1.0, 1.0]
        clipped = PositionUtils.clip_to_limits(position, min_limits, max_limits)
        self.assertEqual(clipped[0], 0.0)  # Clipped to min
        self.assertEqual(clipped[1], 0.0)  # Within limits
        self.assertEqual(clipped[2], 1.0)  # Clipped to max
    
    def test_interpolate_positions(self):
        """Test position interpolation."""
        start = [0.0, 0.0, 0.0]
        end = [1.0, 1.0, 1.0]
        interpolated = PositionUtils.interpolate_positions(start, end, 0.5)
        expected = [0.5, 0.5, 0.5]
        for i, (actual, exp) in enumerate(zip(interpolated, expected)):
            self.assertAlmostEqual(actual, exp, msg=f"Index {i} mismatch")
    
    def test_interpolate_positions_different_lengths(self):
        """Test interpolation with different length positions."""
        start = [0.0, 0.0]
        end = [1.0, 1.0, 1.0]
        interpolated = PositionUtils.interpolate_positions(start, end, 0.5)
        self.assertEqual(interpolated, start)  # Should return start if lengths differ
    
    def test_get_position_velocity(self):
        """Test velocity calculation."""
        pos1 = [0.0, 0.0, 0.0]
        pos2 = [1.0, 1.0, 1.0]
        time_delta = 1.0
        velocity = PositionUtils.get_position_velocity(pos1, pos2, time_delta)
        expected = [1.0, 1.0, 1.0]
        for i, (actual, exp) in enumerate(zip(velocity, expected)):
            self.assertAlmostEqual(actual, exp, msg=f"Index {i} mismatch")
    
    def test_get_position_velocity_zero_time_delta(self):
        """Test velocity calculation with zero time delta."""
        pos1 = [0.0, 0.0, 0.0]
        pos2 = [1.0, 1.0, 1.0]
        velocity = PositionUtils.get_position_velocity(pos1, pos2, 0.0)
        expected = [0.0, 0.0, 0.0]
        self.assertEqual(velocity, expected)


class TestSafetyLimits(unittest.TestCase):
    """Test cases for SafetyLimits class."""
    
    def test_init_default_limits(self):
        """Test SafetyLimits initialization with default values."""
        limits = SafetyLimits()
        self.assertIsNotNone(limits)
    
    def test_init_custom_limits(self):
        """Test SafetyLimits initialization with custom values."""
        limits = SafetyLimits(
            base_min=np.deg2rad(-180.0),
            base_max=np.deg2rad(180.0),
            soft_margin=np.deg2rad(10.0)
        )
        self.assertIsNotNone(limits)
    
    def test_clamp_base_angle_within_limits(self):
        """Test clamping base angle within limits."""
        limits = SafetyLimits(
            base_min=np.deg2rad(-90.0),
            base_max=np.deg2rad(90.0),
            soft_margin=np.deg2rad(10.0)
        )
        angle = np.deg2rad(45.0)
        clamped = limits.clamp_base_angle(angle)
        self.assertAlmostEqual(clamped, angle)
    
    def test_clamp_base_angle_below_min(self):
        """Test clamping base angle below minimum."""
        limits = SafetyLimits(
            base_min=np.deg2rad(-90.0),
            base_max=np.deg2rad(90.0),
            soft_margin=np.deg2rad(10.0)
        )
        angle = np.deg2rad(-120.0)
        clamped = limits.clamp_base_angle(angle)
        self.assertGreaterEqual(clamped, limits.base_min_limit)
    
    def test_clamp_base_angle_above_max(self):
        """Test clamping base angle above maximum."""
        limits = SafetyLimits(
            base_min=np.deg2rad(-90.0),
            base_max=np.deg2rad(90.0),
            soft_margin=np.deg2rad(10.0)
        )
        angle = np.deg2rad(120.0)
        clamped = limits.clamp_base_angle(angle)
        self.assertLessEqual(clamped, limits.base_max_limit)


class TestAnimationTracker(unittest.TestCase):
    """Test cases for AnimationTracker class."""
    
    def test_init(self):
        """Test AnimationTracker initialization."""
        tracker = AnimationTracker()
        self.assertIsNotNone(tracker)
    
    def test_start_animation(self):
        """Test starting an animation."""
        tracker = AnimationTracker()
        tracker.start_animation("test_animation", 10)
        self.assertEqual(tracker.current_animation_name, "test_animation")
        self.assertEqual(tracker.current_animation_duration, 10)
    
    def test_is_animating(self):
        """Test checking if animation is in progress."""
        tracker = AnimationTracker()
        tracker.start_animation("test_animation", 10)
        self.assertTrue(tracker.is_animating())


class TestIdleAnimationConfig(unittest.TestCase):
    """Test cases for IdleAnimationConfig class."""
    
    def test_init(self):
        """Test IdleAnimationConfig initialization."""
        config = IdleAnimationConfig()
        self.assertIsNotNone(config)
    
    def test_get_random_animation(self):
        """Test getting a random animation."""
        config = IdleAnimationConfig()
        anim = config.get_random_animation()
        self.assertIn(anim, config.idle_animations)


class TestCollisionMath(unittest.TestCase):
    """Test cases for CollisionMath class."""
    
    def test_calculate_severity_danger(self):
        """Test severity calculation for danger distance."""
        severity = CollisionMath.calculate_severity(5.0)
        self.assertEqual(severity, 'danger')
    
    def test_calculate_severity_warning(self):
        """Test severity calculation for warning distance."""
        severity = CollisionMath.calculate_severity(10.0)
        self.assertEqual(severity, 'warning')
    
    def test_calculate_severity_safe(self):
        """Test severity calculation for safe distance."""
        severity = CollisionMath.calculate_severity(20.0)
        self.assertEqual(severity, 'safe')
    
    def test_calculate_avoidance_magnitude_normal(self):
        """Test avoidance magnitude calculation for normal case."""
        magnitude = CollisionMath.calculate_avoidance_magnitude('warning', 2)
        self.assertGreater(magnitude, 0)
    
    def test_calculate_avoidance_magnitude_emergency(self):
        """Test avoidance magnitude calculation for emergency."""
        magnitude = CollisionMath.calculate_avoidance_magnitude('danger', 1, emergency=True)
        self.assertGreater(magnitude, 1.0)
    
    def test_calculate_escape_rotation_left(self):
        """Test escape rotation for left collision."""
        rotation = CollisionMath.calculate_escape_rotation('left')
        self.assertGreater(rotation, 0)  # Should rotate right
    
    def test_calculate_escape_rotation_right(self):
        """Test escape rotation for right collision."""
        rotation = CollisionMath.calculate_escape_rotation('right')
        self.assertLess(rotation, 0)  # Should rotate left


class TestMovementValidator(unittest.TestCase):
    """Test cases for MovementValidator class."""
    
    def test_validate_position_within_limits(self):
        """Test position validation within limits."""
        limits = SafetyLimits(
            base_min=np.deg2rad(-90.0),
            base_max=np.deg2rad(90.0),
            soft_margin=np.deg2rad(10.0)
        )
        position = [0.0, 0.5, 1.0, 1.5, 2.0]
        validated = MovementValidator.validate_position(position, limits)
        self.assertEqual(validated[0], 0.0)  # Base within limits
    
    def test_validate_position_clamped(self):
        """Test position validation with clamping."""
        limits = SafetyLimits(
            base_min=np.deg2rad(-90.0),
            base_max=np.deg2rad(90.0),
            soft_margin=np.deg2rad(10.0)
        )
        position = [2.0, 0.5, 1.0, 1.5, 2.0]  # Base outside limits
        validated = MovementValidator.validate_position(position, limits)
        self.assertLessEqual(validated[0], limits.base_max_limit)
    
    def test_check_movement_safety(self):
        """Test movement safety check."""
        current = [0.0, 0.5, 1.0, 1.5, 2.0]
        target = [0.1, 0.6, 1.1, 1.6, 2.1]
        collision_status = {
            'front': {'active': False, 'severity': 'safe'},
            'left': {'active': False, 'severity': 'safe'},
            'right': {'active': False, 'severity': 'safe'}
        }
        safe, reason = MovementValidator.check_movement_safety(current, target, collision_status)
        self.assertTrue(safe)
        self.assertEqual(reason, "Movement safe")


if __name__ == '__main__':
    unittest.main()
