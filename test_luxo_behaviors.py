#!/usr/bin/env python3
"""Tests for luxo_behaviors module."""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch, Mock

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Mock ROS2 imports before importing luxo_behaviors
sys.modules['rclpy'] = MagicMock()
sys.modules['rclpy.node'] = MagicMock()
sys.modules['rclpy.qos'] = MagicMock()
sys.modules['rclpy.executors'] = MagicMock()
sys.modules['std_msgs'] = MagicMock()
sys.modules['std_msgs.msg'] = MagicMock()
sys.modules['geometry_msgs'] = MagicMock()
sys.modules['geometry_msgs.msg'] = MagicMock()
sys.modules['diagnostic_msgs'] = MagicMock()
sys.modules['diagnostic_msgs.msg'] = MagicMock()
sys.modules['luxo_interfaces'] = MagicMock()
sys.modules['luxo_interfaces.msg'] = MagicMock()
sys.modules['luxo_interfaces.srv'] = MagicMock()

from luxo_behaviors.state_machine import LuxoState, StateTransition


class TestLuxoState:
    """Test cases for LuxoState enum."""
    
    def test_luxo_state_enum_values(self):
        """Test that all expected states exist."""
        states = [
            LuxoState.IDLE,
            LuxoState.ANIMATING,
            LuxoState.VOICE_FOLLOWING,
            LuxoState.COLLISION_AVOIDING,
            LuxoState.RETURNING_HOME,
            LuxoState.ESCAPE_MODE,
            LuxoState.USER_CONTROL,
            LuxoState.EMOTION_REACTING,
            LuxoState.PETTING,
            LuxoState.ERROR,
            LuxoState.INITIALIZING,
            LuxoState.SHUTDOWN
        ]
        assert len(states) == 12
    
    def test_luxo_state_names(self):
        """Test that state names are correct."""
        expected_names = [
            'IDLE', 'ANIMATING', 'VOICE_FOLLOWING', 'COLLISION_AVOIDING',
            'RETURNING_HOME', 'ESCAPE_MODE', 'USER_CONTROL', 'EMOTION_REACTING',
            'PETTING', 'ERROR', 'INITIALIZING', 'SHUTDOWN'
        ]
        actual_names = [state.name for state in LuxoState]
        assert set(actual_names) == set(expected_names)
    
    def test_luxo_state_values_are_unique(self):
        """Test that all state values are unique."""
        values = [state.value for state in LuxoState]
        assert len(values) == len(set(values)), "State values should be unique"
    
    def test_luxo_state_iteration(self):
        """Test that we can iterate over all states."""
        states_list = list(LuxoState)
        assert len(states_list) == 12


class TestStateTransition:
    """Test cases for StateTransition class."""
    
    def test_state_transition_creation(self):
        """Test creating a basic state transition."""
        def dummy_condition():
            return True
        
        def dummy_action():
            pass
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=dummy_condition,
            action=dummy_action
        )
        
        assert transition.from_state == LuxoState.IDLE
        assert transition.to_state == LuxoState.ANIMATING
        assert transition.condition == dummy_condition
        assert transition.action == dummy_action
    
    def test_state_transition_without_condition(self):
        """Test creating a state transition without a condition."""
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=None,
            action=None
        )
        
        assert transition.from_state == LuxoState.IDLE
        assert transition.to_state == LuxoState.ANIMATING
        assert transition.condition is None
        assert transition.action is None
    
    def test_state_transition_with_lambda_condition(self):
        """Test creating a state transition with a lambda condition."""
        condition = lambda: True
        action = lambda: None
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=condition,
            action=action
        )
        
        assert transition.condition() is True
    
    def test_state_transition_condition_evaluation(self):
        """Test that conditions are properly evaluated."""
        condition_called = []
        
        def counting_condition():
            condition_called.append(True)
            return True
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=counting_condition,
            action=None
        )
        
        # Evaluate the condition
        result = transition.condition()
        assert result is True
        assert len(condition_called) == 1
    
    def test_state_transition_with_multiple_states(self):
        """Test transitions between different states."""
        transitions = [
            StateTransition(LuxoState.IDLE, LuxoState.ANIMATING),
            StateTransition(LuxoState.ANIMATING, LuxoState.VOICE_FOLLOWING),
            StateTransition(LuxoState.VOICE_FOLLOWING, LuxoState.COLLISION_AVOIDING),
            StateTransition(LuxoState.COLLISION_AVOIDING, LuxoState.IDLE),
        ]
        
        assert len(transitions) == 4
        assert transitions[0].from_state == LuxoState.IDLE
        assert transitions[0].to_state == LuxoState.ANIMATING
        assert transitions[1].from_state == LuxoState.ANIMATING
        assert transitions[1].to_state == LuxoState.VOICE_FOLLOWING
    
    def test_state_transition_equality(self):
        """Test that transitions with same attributes are equal."""
        def dummy_condition():
            return True
        
        def dummy_action():
            pass
        
        transition1 = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=dummy_condition,
            action=dummy_action
        )
        
        transition2 = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=dummy_condition,
            action=dummy_action
        )
        
        # Test that attributes match
        assert transition1.from_state == transition2.from_state
        assert transition1.to_state == transition2.to_state
        assert transition1.condition == transition2.condition
        assert transition1.action == transition2.action


class TestStateTransitionLogic:
    """Test state transition logic."""
    
    def test_transition_condition_can_be_false(self):
        """Test that a condition can return False."""
        condition = lambda: False
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=condition,
            action=None
        )
        
        assert transition.condition() is False
    
    def test_transition_condition_with_parameters(self):
        """Test that conditions can accept parameters."""
        def condition_with_param(x):
            return x > 5
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=lambda: condition_with_param(10),
            action=None
        )
        
        assert transition.condition() is True
    
    def test_transition_action_can_be_executed(self):
        """Test that actions can be executed."""
        action_executed = []
        
        def counting_action():
            action_executed.append(True)
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=lambda: True,
            action=counting_action
        )
        
        # Execute the action
        transition.action()
        assert len(action_executed) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
