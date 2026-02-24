#!/usr/bin/env python3
"""Tests for the state machine components."""

import pytest
import sys
import os

# Add the package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

from luxo_behaviors.state_machine import LuxoState, StateTransition


class TestLuxoState:
    """Tests for the LuxoState enum."""
    
    def test_state_enum_exists(self):
        """Test that LuxoState enum is defined."""
        assert LuxoState is not None
    
    def test_all_states_defined(self):
        """Test that all expected states are defined."""
        expected_states = [
            'INITIALIZING', 'IDLE', 'ANIMATING', 'VOICE_FOLLOWING',
            'COLLISION_AVOIDING', 'RETURNING_HOME', 'ESCAPE_MODE',
            'USER_CONTROL', 'EMOTION_REACTING', 'PETTING', 'ERROR', 'SHUTDOWN'
        ]
        for state_name in expected_states:
            assert hasattr(LuxoState, state_name)
    
    def test_state_names(self):
        """Test that state names are correct."""
        assert LuxoState.IDLE.name == 'IDLE'
        assert LuxoState.ANIMATING.name == 'ANIMATING'
        assert LuxoState.ESCAPE_MODE.name == 'ESCAPE_MODE'


class TestStateTransition:
    """Tests for the StateTransition class."""
    
    def test_transition_creation(self):
        """Test creating a basic state transition."""
        from_state = LuxoState.IDLE
        to_state = LuxoState.ANIMATING
        
        transition = StateTransition(from_state, to_state)
        
        assert transition.from_state == from_state
        assert transition.to_state == to_state
        assert transition.condition is None
        assert transition.action is None
    
    def test_transition_with_condition(self):
        """Test creating a state transition with a condition."""
        from_state = LuxoState.IDLE
        to_state = LuxoState.ANIMATING
        
        def test_condition():
            return True
        
        transition = StateTransition(from_state, to_state, condition=test_condition)
        
        assert transition.condition is test_condition
        assert transition.condition() is True
    
    def test_transition_with_action(self):
        """Test creating a state transition with an action."""
        from_state = LuxoState.IDLE
        to_state = LuxoState.ANIMATING
        
        action_called = [False]
        
        def test_action():
            action_called[0] = True
        
        transition = StateTransition(from_state, to_state, action=test_action)
        
        assert transition.action is test_action
        transition.action()
        assert action_called[0] is True
    
    def test_transition_with_both_condition_and_action(self):
        """Test creating a state transition with both condition and action."""
        from_state = LuxoState.IDLE
        to_state = LuxoState.ANIMATING
        
        condition_result = [True]
        
        def test_condition():
            return condition_result[0]
        
        action_called = [False]
        
        def test_action():
            action_called[0] = True
        
        transition = StateTransition(from_state, to_state, condition=test_condition, action=test_action)
        
        assert transition.condition() is True
        transition.action()
        assert action_called[0] is True
        
        # Test with condition returning False
        condition_result[0] = False
        assert transition.condition() is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
