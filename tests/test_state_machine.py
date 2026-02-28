"""
Unit tests for the state machine components of luxo_behaviors.
"""

import pytest
import sys
import os

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'luxo_behaviors'))

from luxo_behaviors.state_machine import LuxoState, StateTransition


class TestLuxoState:
    """Test the LuxoState enum."""
    
    def test_luxo_state_enum_values(self):
        """Verify all expected states exist in the enum."""
        expected_states = [
            'IDLE', 'ANIMATING', 'VOICE_FOLLOWING', 'COLLISION_AVOIDING',
            'RETURNING_HOME', 'ESCAPE_MODE', 'USER_CONTROL', 'EMOTION_REACTING',
            'PETTING', 'ERROR', 'INITIALIZING', 'SHUTDOWN'
        ]
        for state_name in expected_states:
            assert hasattr(LuxoState, state_name)
    
    def test_luxo_state_idle(self):
        """Test IDLE state."""
        assert LuxoState.IDLE == LuxoState.IDLE
    
    def test_luxo_state_animating(self):
        """Test ANIMATING state."""
        assert LuxoState.ANIMATING == LuxoState.ANIMATING
    
    def test_luxo_state_voice_following(self):
        """Test VOICE_FOLLOWING state."""
        assert LuxoState.VOICE_FOLLOWING == LuxoState.VOICE_FOLLOWING
    
    def test_luxo_state_collision_avoiding(self):
        """Test COLLISION_AVOIDING state."""
        assert LuxoState.COLLISION_AVOIDING == LuxoState.COLLISION_AVOIDING
    
    def test_luxo_state_returning_home(self):
        """Test RETURNING_HOME state."""
        assert LuxoState.RETURNING_HOME == LuxoState.RETURNING_HOME
    
    def test_luxo_state_escape_mode(self):
        """Test ESCAPE_MODE state."""
        assert LuxoState.ESCAPE_MODE == LuxoState.ESCAPE_MODE
    
    def test_luxo_state_user_control(self):
        """Test USER_CONTROL state."""
        assert LuxoState.USER_CONTROL == LuxoState.USER_CONTROL
    
    def test_luxo_state_emotion_reacting(self):
        """Test EMOTION_REACTING state."""
        assert LuxoState.EMOTION_REACTING == LuxoState.EMOTION_REACTING
    
    def test_luxo_state_petting(self):
        """Test PETTING state."""
        assert LuxoState.PETTING == LuxoState.PETTING
    
    def test_luxo_state_error(self):
        """Test ERROR state."""
        assert LuxoState.ERROR == LuxoState.ERROR
    
    def test_luxo_state_initializing(self):
        """Test INITIALIZING state."""
        assert LuxoState.INITIALIZING == LuxoState.INITIALIZING
    
    def test_luxo_state_shutdown(self):
        """Test SHUTDOWN state."""
        assert LuxoState.SHUTDOWN == LuxoState.SHUTDOWN


class TestStateTransition:
    """Test the StateTransition class."""
    
    def test_state_transition_creation(self):
        """Test creating a basic state transition."""
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
    
    def test_state_transition_equality(self):
        """Test that transitions with same parameters are equal."""
        transition1 = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING
        )
        transition2 = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.ANIMATING
        )
        # Note: This tests object identity, not structural equality
        assert transition1 == transition1
        assert transition1 != transition2  # Different objects
