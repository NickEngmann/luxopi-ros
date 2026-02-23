import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

from state_machine import LuxoState, StateTransition

class TestLuxoState:
    """Test cases for LuxoState enum."""
    
    def test_luxo_state_enum_values(self):
        """Test that all expected states exist in the enum."""
        expected_states = [
            'IDLE', 'ANIMATING', 'VOICE_FOLLOWING', 'COLLISION_AVOIDING',
            'RETURNING_HOME', 'ESCAPE_MODE', 'USER_CONTROL', 'EMOTION_REACTING',
            'PETTING', 'ERROR', 'INITIALIZING', 'SHUTDOWN'
        ]
        for state_name in expected_states:
            assert hasattr(LuxoState, state_name)
    
    def test_luxo_state_idle(self):
        """Test IDLE state exists and has correct type."""
        assert LuxoState.IDLE == LuxoState.IDLE
        assert isinstance(LuxoState.IDLE, LuxoState)
    
    def test_luxo_state_animating(self):
        """Test ANIMATING state exists and has correct type."""
        assert LuxoState.ANIMATING == LuxoState.ANIMATING
        assert isinstance(LuxoState.ANIMATING, LuxoState)

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
        """Test creating a state transition without condition."""
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING
        )
        
        assert transition.from_state == LuxoState.IDLE
        assert transition.to_state == LuxoState.ANIMATING
        assert transition.condition is None
        assert transition.action is None
    
    def test_state_transition_with_condition_only(self):
        """Test creating a state transition with only condition."""
        def dummy_condition():
            return True
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=dummy_condition
        )
        
        assert transition.condition == dummy_condition
        assert transition.action is None
    
    def test_state_transition_with_action_only(self):
        """Test creating a state transition with only action."""
        def dummy_action():
            pass
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            action=dummy_action
        )
        
        assert transition.condition is None
        assert transition.action == dummy_action
    
    def test_state_transition_condition_evaluation(self):
        """Test that condition function is properly stored and can be called."""
        condition_called = {'value': False}
        
        def test_condition():
            condition_called['value'] = True
            return True
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            condition=test_condition
        )
        
        # Verify condition can be called
        result = transition.condition()
        assert result is True
        assert condition_called['value'] is True
    
    def test_state_transition_action_execution(self):
        """Test that action function is properly stored and can be called."""
        action_called = {'value': False}
        
        def test_action():
            action_called['value'] = True
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING,
            action=test_action
        )
        
        # Verify action can be called
        transition.action()
        assert action_called['value'] is True
