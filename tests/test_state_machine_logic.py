"""
Unit tests for the state machine logic in state_machine.py.

Tests the core state machine functionality without ROS dependencies.
"""

import pytest
from unittest.mock import MagicMock
import sys
import os

# Add the source directory to the Python path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
source_dir = os.path.join(repo_root, 'src', 'luxo_behaviors')
sys.path.insert(0, source_dir)

# Mock ROS2 imports since we're testing pure logic
sys.modules['rclpy'] = MagicMock()
sys.modules['rclpy.node'] = MagicMock()
sys.modules['rclpy.action'] = MagicMock()

# Import the state machine module
from luxo_behaviors.state_machine import LuxoState, StateTransition, StateMachine


class TestLuxoState:
    """Tests for the LuxoState enum."""
    
    def test_luxo_state_enum_values(self):
        """Verify all states are defined correctly."""
        states = list(LuxoState)
        assert len(states) > 0
        assert LuxoState.IDLE in states
        assert LuxoState.BEHAVIOR in states
        assert LuxoState.COLLISION in states
        assert LuxoState.PETTING in states
        assert LuxoState.VOICE in states
        assert LuxoState.CAMERA in states


class TestStateTransition:
    """Tests for the StateTransition class."""
    
    def test_transition_creation(self):
        """Test creating a basic state transition."""
        def dummy_condition():
            return True
        
        def dummy_action():
            pass
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=dummy_condition,
            action=dummy_action
        )
        
        assert transition.from_state == LuxoState.IDLE
        assert transition.to_state == LuxoState.BEHAVIOR
        assert transition.condition == dummy_condition
        assert transition.action == dummy_action
    
    def test_transition_with_none_condition(self):
        """Test transition with None condition (always allowed)."""
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=None,
            action=None
        )
        
        # None condition should be treated as always True
        assert transition.condition is None
    
    def test_transition_with_none_action(self):
        """Test transition with None action."""
        def dummy_condition():
            return True
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=dummy_condition,
            action=None
        )
        
        assert transition.action is None


class TestStateMachine:
    """Tests for the StateMachine class."""
    
    def test_initialization(self):
        """Test state machine initialization."""
        sm = StateMachine(LuxoState.IDLE)
        
        assert sm.current_state == LuxoState.IDLE
        assert len(sm.transitions) == 0
    
    def test_add_transition(self):
        """Test adding a transition to the state machine."""
        sm = StateMachine(LuxoState.IDLE)
        
        def dummy_condition():
            return True
        
        def dummy_action():
            pass
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=dummy_condition,
            action=dummy_action
        )
        
        sm.add_transition(transition)
        
        assert len(sm.transitions) == 1
        assert sm.transitions[0] == transition
    
    def test_add_multiple_transitions(self):
        """Test adding multiple transitions."""
        sm = StateMachine(LuxoState.IDLE)
        
        def dummy_condition():
            return True
        
        def dummy_action():
            pass
        
        transition1 = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=dummy_condition,
            action=dummy_action
        )
        
        transition2 = StateTransition(
            from_state=LuxoState.BEHAVIOR,
            to_state=LuxoState.IDLE,
            condition=dummy_condition,
            action=dummy_action
        )
        
        sm.add_transition(transition1)
        sm.add_transition(transition2)
        
        assert len(sm.transitions) == 2
    
    def test_can_transition_with_matching_transition(self):
        """Test can_transition when a matching transition exists."""
        sm = StateMachine(LuxoState.IDLE)
        
        condition_called = {'called': False}
        
        def dummy_condition():
            condition_called['called'] = True
            return True
        
        def dummy_action():
            pass
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=dummy_condition,
            action=dummy_action
        )
        
        sm.add_transition(transition)
        
        result = sm.can_transition(LuxoState.IDLE, LuxoState.BEHAVIOR)
        
        assert result is True
        assert condition_called['called'] is True
    
    def test_can_transition_with_condition_false(self):
        """Test can_transition when condition returns False."""
        sm = StateMachine(LuxoState.IDLE)
        
        def false_condition():
            return False
        
        def dummy_action():
            pass
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=false_condition,
            action=dummy_action
        )
        
        sm.add_transition(transition)
        
        result = sm.can_transition(LuxoState.IDLE, LuxoState.BEHAVIOR)
        
        assert result is False
    
    def test_can_transition_with_no_matching_transition(self):
        """Test can_transition when no matching transition exists."""
        sm = StateMachine(LuxoState.IDLE)
        
        def dummy_condition():
            return True
        
        def dummy_action():
            pass
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=dummy_condition,
            action=dummy_action
        )
        
        sm.add_transition(transition)
        
        # Try to transition from a different state
        result = sm.can_transition(LuxoState.BEHAVIOR, LuxoState.IDLE)
        
        assert result is False
    
    def test_can_transition_with_none_condition(self):
        """Test can_transition when transition has None condition."""
        sm = StateMachine(LuxoState.IDLE)
        
        def dummy_action():
            pass
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=None,
            action=dummy_action
        )
        
        sm.add_transition(transition)
        
        result = sm.can_transition(LuxoState.IDLE, LuxoState.BEHAVIOR)
        
        assert result is True
    
    def test_perform_transition_with_action(self):
        """Test perform_transition with an action."""
        sm = StateMachine(LuxoState.IDLE)
        
        action_called = {'called': False}
        
        def dummy_action():
            action_called['called'] = True
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=lambda: True,
            action=dummy_action
        )
        
        sm.add_transition(transition)
        
        result = sm.perform_transition(LuxoState.BEHAVIOR)
        
        assert result is True
        assert sm.current_state == LuxoState.BEHAVIOR
        assert action_called['called'] is True
    
    def test_perform_transition_without_action(self):
        """Test perform_transition without an action."""
        sm = StateMachine(LuxoState.IDLE)
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=lambda: True,
            action=None
        )
        
        sm.add_transition(transition)
        
        result = sm.perform_transition(LuxoState.BEHAVIOR)
        
        assert result is True
        assert sm.current_state == LuxoState.BEHAVIOR
    
    def test_perform_transition_with_condition_false(self):
        """Test perform_transition when condition returns False."""
        sm = StateMachine(LuxoState.IDLE)
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=lambda: False,
            action=lambda: None
        )
        
        sm.add_transition(transition)
        
        result = sm.perform_transition(LuxoState.BEHAVIOR)
        
        assert result is False
        assert sm.current_state == LuxoState.IDLE  # State should not change
    
    def test_perform_transition_with_no_matching_transition(self):
        """Test perform_transition when no matching transition exists."""
        sm = StateMachine(LuxoState.IDLE)
        
        def dummy_condition():
            return True
        
        def dummy_action():
            pass
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=dummy_condition,
            action=dummy_action
        )
        
        sm.add_transition(transition)
        
        # Try to transition from a different state
        result = sm.perform_transition(LuxoState.IDLE)
        
        assert result is False
        assert sm.current_state == LuxoState.IDLE
    
    def test_perform_transition_with_none_condition(self):
        """Test perform_transition when transition has None condition."""
        sm = StateMachine(LuxoState.IDLE)
        
        transition = StateTransition(
            from_state=LuxoState.IDLE,
            to_state=LuxoState.BEHAVIOR,
            condition=None,
            action=lambda: None
        )
        
        sm.add_transition(transition)
        
        result = sm.perform_transition(LuxoState.BEHAVIOR)
        
        assert result is True
        assert sm.current_state == LuxoState.BEHAVIOR
    
    def test_change_state_directly(self):
        """Test changing state directly without transition."""
        sm = StateMachine(LuxoState.IDLE)
        
        sm.change_state(LuxoState.BEHAVIOR)
        
        assert sm.current_state == LuxoState.BEHAVIOR
    
    def test_get_current_state(self):
        """Test getting the current state."""
        sm = StateMachine(LuxoState.IDLE)
        
        assert sm.get_current_state() == LuxoState.IDLE
        
        sm.change_state(LuxoState.BEHAVIOR)
        
        assert sm.get_current_state() == LuxoState.BEHAVIOR
