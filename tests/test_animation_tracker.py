#!/usr/bin/env python3
"""
Unit tests for AnimationProgressTracker, IdleAnimationConfig, StateUtils, and SafetyLimits classes.
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

from luxo_behaviors.shared_utils import (
    AnimationProgressTracker,
    IdleAnimationConfig,
    StateUtils,
    SafetyLimits
)


class TestAnimationProgressTracker:
    """Tests for AnimationProgressTracker class."""
    
    def test_initial_state(self):
        """Test initial animation tracker state."""
        tracker = AnimationProgressTracker()
        assert tracker.animation_progress == 0.0
        assert tracker.animation_preempted is False
        assert tracker.current_animation_name is None
    
    def test_update_progress_clamps_below(self):
        """Test that progress is clamped to [0.0, 1.0]."""
        tracker = AnimationProgressTracker()
        tracker.update_progress(-0.5)  # Below minimum
        assert tracker.animation_progress == 0.0
    
    def test_update_progress_clamps_above(self):
        """Test that progress is clamped to [0.0, 1.0]."""
        tracker = AnimationProgressTracker()
        tracker.update_progress(1.5)  # Above maximum
        assert tracker.animation_progress == 1.0
    
    def test_update_progress_normal(self):
        """Test normal progress update."""
        tracker = AnimationProgressTracker()
        tracker.update_progress(0.75)
        assert tracker.animation_progress == 0.75
    
    def test_update_progress_zero(self):
        """Test progress update to zero."""
        tracker = AnimationProgressTracker()
        tracker.update_progress(0.0)
        assert tracker.animation_progress == 0.0
    
    def test_update_progress_one(self):
        """Test progress update to one."""
        tracker = AnimationProgressTracker()
        tracker.update_progress(1.0)
        assert tracker.animation_progress == 1.0
    
    def test_should_preempt_no_animation(self):
        """Test preempt check when no animation running."""
        tracker = AnimationProgressTracker()
        assert tracker.should_preempt() is False
    
    def test_should_preempt_no_interruption(self):
        """Test preempt check when interruption not allowed."""
        tracker = AnimationProgressTracker()
        tracker.current_animation_name = 'test_animation'
        tracker.animation_allow_interruption = False
        assert tracker.should_preempt() is False
    
    def test_should_preempt_warning(self):
        """Test preempt check with warning severity."""
        tracker = AnimationProgressTracker()
        tracker.current_animation_name = 'test_animation'
        tracker.animation_allow_interruption = True
        assert tracker.should_preempt('warning') is False
    
    def test_should_preempt_danger(self):
        """Test preempt check with danger severity."""
        tracker = AnimationProgressTracker()
        tracker.current_animation_name = 'test_animation'
        tracker.animation_allow_interruption = True
        assert tracker.should_preempt('danger') is True
    
    def test_should_preempt_safe(self):
        """Test preempt check with safe severity."""
        tracker = AnimationProgressTracker()
        tracker.current_animation_name = 'test_animation'
        tracker.animation_allow_interruption = True
        assert tracker.should_preempt('safe') is False
    
    def test_should_preempt_empty_string(self):
        """Test preempt check with empty string severity."""
        tracker = AnimationProgressTracker()
        tracker.current_animation_name = 'test_animation'
        tracker.animation_allow_interruption = True
        assert tracker.should_preempt('') is False


class TestIdleAnimationConfig:
    """Tests for IdleAnimationConfig class."""
    
    def test_default_animations(self):
        """Test default animation lists are populated."""
        config = IdleAnimationConfig()
        assert len(config.idle_animations) > 0
        assert len(config.petting_animations) > 0
        assert len(config.sleeping_animations) > 0
    
    def test_get_random_idle_animation(self):
        """Test getting random idle animation."""
        config = IdleAnimationConfig()
        animation = config.get_random_idle_animation()
        assert animation in config.idle_animations
    
    def test_get_random_idle_animation_excludes(self):
        """Test excluding animation from selection."""
        config = IdleAnimationConfig()
        exclude = config.idle_animations[0]
        animation = config.get_random_idle_animation(exclude=exclude)
        assert animation != exclude
        assert animation in config.idle_animations
    
    def test_get_random_idle_animation_excludes_all(self):
        """Test excluding all animations returns None."""
        config = IdleAnimationConfig()
        exclude = config.idle_animations.copy()
        animation = config.get_random_idle_animation(exclude=exclude)
        assert animation is None
    
    def test_get_random_interval(self):
        """Test getting random interval."""
        config = IdleAnimationConfig()
        interval = config.get_random_interval()
        assert config.idle_animation_interval_min <= interval <= config.idle_animation_interval_max
    
    def test_get_random_interval_bounds(self):
        """Test interval bounds are correct."""
        config = IdleAnimationConfig()
        assert config.idle_animation_interval_min == 2.0
        assert config.idle_animation_interval_max == 5.0
    
    def test_get_random_sleep_interval(self):
        """Test getting random sleep interval."""
        config = IdleAnimationConfig()
        interval = config.get_random_sleep_interval()
        assert config.sleep_animation_interval_min <= interval <= config.sleep_animation_interval_max


class TestStateUtils:
    """Tests for StateUtils class."""
    
    def test_is_in_state_with_attribute(self):
        """Test is_in_state with current_state attribute."""
        mock_node = MagicMock()
        mock_node.current_state = 'IDLE'
        mock_node.state_lock = None
        
        result = StateUtils.is_in_state(mock_node, 'IDLE', 'MOVING')
        assert result is True
    
    def test_is_in_state_with_method(self):
        """Test is_in_state with get_current_state method."""
        mock_node = MagicMock()
        mock_node.current_state = None
        mock_node.get_current_state.return_value = 'IDLE'
        
        result = StateUtils.is_in_state(mock_node, 'IDLE', 'MOVING')
        assert result is True
    
    def test_is_in_state_no_state(self):
        """Test is_in_state when no state available."""
        mock_node = MagicMock()
        mock_node.current_state = None
        mock_node.get_current_state = None
        
        result = StateUtils.is_in_state(mock_node, 'IDLE')
        assert result is False
    
    def test_is_in_state_different_states(self):
        """Test is_in_state with different states."""
        mock_node = MagicMock()
        mock_node.current_state = 'IDLE'
        mock_node.state_lock = None
        
        result = StateUtils.is_in_state(mock_node, 'MOVING', 'IDLE')
        assert result is False
    
    def test_get_current_state_with_attribute(self):
        """Test get_current_state with current_state attribute."""
        mock_node = MagicMock()
        mock_node.current_state = 'IDLE'
        mock_node.state_lock = None
        
        result = StateUtils.get_current_state(mock_node)
        assert result == 'IDLE'
    
    def test_get_current_state_with_method(self):
        """Test get_current_state with get_current_state method."""
        mock_node = MagicMock()
        mock_node.current_state = None
        mock_node.get_current_state.return_value = 'MOVING'
        
        result = StateUtils.get_current_state(mock_node)
        assert result == 'MOVING'
    
    def test_get_current_state_no_state(self):
        """Test get_current_state when no state available."""
        mock_node = MagicMock()
        mock_node.current_state = None
        mock_node.get_current_state = None
        
        result = StateUtils.get_current_state(mock_node)
        assert result is None
    
    def test_get_current_state_with_lock(self):
        """Test get_current_state with state lock."""
        mock_node = MagicMock()
        mock_node.current_state = 'IDLE'
        mock_node.state_lock = MagicMock()
        mock_node.state_lock.__enter__ = MagicMock(return_value=None)
        mock_node.state_lock.__exit__ = MagicMock(return_value=None)
        
        result = StateUtils.get_current_state(mock_node)
        assert result == 'IDLE'


class TestSafetyLimits:
    """Tests for SafetyLimits class."""
    
    def test_default_base_limits(self):
        """Test default base angle limits."""
        limits = SafetyLimits()
        assert limits.min_base_angle == -math.pi
        assert limits.max_base_angle == math.pi
    
    def test_default_joint_limits(self):
        """Test default joint limits."""
        limits = SafetyLimits()
        assert 'shoulder' in limits.joint_limits
        assert 'elbow' in limits.joint_limits
        assert 'wrist' in limits.joint_limits
        assert 'hand' in limits.joint_limits
    
    def test_joint_limits_structure(self):
        """Test joint limits have min and max."""
        limits = SafetyLimits()
        for joint_name in limits.joint_limits:
            assert 'min' in limits.joint_limits[joint_name]
            assert 'max' in limits.joint_limits[joint_name]
    
    def test_collision_thresholds(self):
        """Test collision thresholds."""
        limits = SafetyLimits()
        assert limits.warning_distance == 15.0
        assert limits.danger_distance == 7.0
    
    def test_animation_limits(self):
        """Test animation limits."""
        limits = SafetyLimits()
        assert limits.animation_preempt_distance == 10.0
        assert limits.animation_preempt_severity == 'danger'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
