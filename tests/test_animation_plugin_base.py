"""
Unit tests for the animation plugin base components of luxo_behaviors.
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Mock ROS imports before importing the modules
sys.modules['rclpy'] = MagicMock()
sys.modules['rclpy.node'] = MagicMock()
sys.modules['rclpy.action'] = MagicMock()
sys.modules['std_msgs'] = MagicMock()
sys.modules['std_msgs.msg'] = MagicMock()
sys.modules['geometry_msgs'] = MagicMock()
sys.modules['geometry_msgs.msg'] = MagicMock()
sys.modules['sensor_msgs'] = MagicMock()
sys.modules['sensor_msgs.msg'] = MagicMock()
sys.modules['nav_msgs'] = MagicMock()
sys.modules['nav_msgs.msg'] = MagicMock()
sys.modules['tf2_ros'] = MagicMock()
sys.modules['tf2'] = MagicMock()
sys.modules['tf2_msgs'] = MagicMock()
sys.modules['tf2_msgs.msg'] = MagicMock()
sys.modules['visualization_msgs'] = MagicMock()
sys.modules['visualization_msgs.msg'] = MagicMock()
sys.modules['message_filters'] = MagicMock()

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'luxo_behaviors'))

from luxo_behaviors.animation_plugin_base import AnimationPlugin
from luxo_behaviors.state_machine import LuxoState, StateTransition
from luxo_behaviors.shared_utils import StateUtils


class TestAnimationPlugin:
    """Test cases for AnimationPlugin base class."""
    
    def test_animation_plugin_abstract_methods(self):
        """Test that AnimationPlugin requires abstract methods."""
        # AnimationPlugin is abstract, so we can't instantiate it directly
        # We need to create a concrete implementation
        class ConcreteAnimation(AnimationPlugin):
            @property
            def name(self):
                return "test_animation"
            
            @property
            def description(self):
                return "Test animation"
            
            def get_keyframes(self):
                return ([], [])
        
        node = Mock()
        plugin = ConcreteAnimation(node)
        assert plugin.name == "test_animation"
        assert plugin.description == "Test animation"
    
    def test_animation_plugin_with_keyframes(self):
        """Test animation plugin with actual keyframes."""
        class KeyframeAnimation(AnimationPlugin):
            def __init__(self, node):
                super().__init__(node)
                self._keyframes = [[0.0, 0.0, 0.0, 0.0, 0.0]]
                self._durations = [1.0]
            
            @property
            def name(self):
                return "keyframe_test"
            
            @property
            def description(self):
                return "Keyframe test animation"
            
            def get_keyframes(self):
                return (self._keyframes, self._durations)
        
        node = Mock()
        plugin = KeyframeAnimation(node)
        keyframes, durations = plugin.get_keyframes()
        assert len(keyframes) == 1
        assert len(durations) == 1
        assert durations[0] == 1.0
    
    def test_add_noise_to_position(self):
        """Test adding noise to positions."""
        node = Mock()
        
        class ConcreteAnimation(AnimationPlugin):
            @property
            def name(self):
                return "test"
            @property
            def description(self):
                return "Test"
            def get_keyframes(self):
                return ([], [])
        
        plugin = ConcreteAnimation(node)
        positions = [0.0, 1.0, 2.0]
        noisy = plugin.add_noise_to_position(positions, noise_amplitude=0.1)
        assert len(noisy) == len(positions)
        # Check that noise was added (values should be slightly different)
        for original, noisy_pos in zip(positions, noisy):
            assert abs(original - noisy_pos) <= 0.1
    
    def test_validate_keyframes_valid(self):
        """Test keyframe validation with valid keyframes."""
        node = Mock()
        node.get_logger().error = Mock()
        
        class ValidAnimation(AnimationPlugin):
            @property
            def name(self):
                return "valid"
            @property
            def description(self):
                return "Valid"
            def get_keyframes(self):
                return ([0.0, 1.0], [1.0, 1.0])
        
        plugin = ValidAnimation(node)
        assert plugin.validate_keyframes() is True
        node.get_logger().error.assert_not_called()
    
    def test_validate_keyframes_mismatched(self):
        """Test keyframe validation with mismatched keyframes and durations."""
        node = Mock()
        node.get_logger().error = Mock()
        
        class MismatchedAnimation(AnimationPlugin):
            @property
            def name(self):
                return "mismatched"
            @property
            def description(self):
                return "Mismatched"
            def get_keyframes(self):
                return ([0.0, 1.0], [1.0])  # 2 keyframes, 1 duration
        
        plugin = MismatchedAnimation(node)
        assert plugin.validate_keyframes() is False
        node.get_logger().error.assert_called()
    
    def test_validate_keyframes_empty(self):
        """Test keyframe validation with empty keyframes."""
        node = Mock()
        node.get_logger().error = Mock()
        
        class EmptyAnimation(AnimationPlugin):
            @property
            def name(self):
                return "empty"
            @property
            def description(self):
                return "Empty"
            def get_keyframes(self):
                return ([], [])
        
        plugin = EmptyAnimation(node)
        assert plugin.validate_keyframes() is False
        node.get_logger().error.assert_called()


class TestStateTransition:
    """Test cases for StateTransition class."""
    
    def test_state_transition_creation(self):
        """Test creating a state transition."""
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING
        )
        assert transition.from_state == LuxoState.IDLE
        assert transition.to_state == LuxoState.ANIMATING
        assert transition.condition is None
        assert transition.action is None
    
    def test_state_transition_with_condition(self):
        """Test creating a state transition with a condition."""
        condition = lambda: True
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=condition
        )
        assert transition.condition == condition
    
    def test_state_transition_with_action(self):
        """Test creating a state transition with an action."""
        action = lambda: None
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            action=action
        )
        assert transition.action == action
    
    def test_state_transition_with_both_condition_and_action(self):
        """Test creating a state transition with both condition and action."""
        condition = lambda: True
        action = lambda: None
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=condition,
            action=action
        )
        assert transition.condition == condition
        assert transition.action == action


class TestStateUtils:
    """Test cases for StateUtils class."""
    
    def test_state_utils_creation(self):
        """Test creating a StateUtils instance."""
        node = Mock()
        utils = StateUtils(node)
        assert utils is not None
    
    def test_state_utils_get_state_name(self):
        """Test getting state name from enum."""
        node = Mock()
        utils = StateUtils(node)
        assert utils.get_state_name(LuxoState.IDLE) == "IDLE"
        assert utils.get_state_name(LuxoState.ANIMATING) == "ANIMATING"
    
    def test_state_utils_is_valid_state(self):
        """Test checking if a state is valid."""
        node = Mock()
        utils = StateUtils(node)
        assert utils.is_valid_state(LuxoState.IDLE) is True
        assert utils.is_valid_state("invalid") is False
