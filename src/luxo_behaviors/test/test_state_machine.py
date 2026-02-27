#!/usr/bin/env python3
"""Tests for state_machine.py module."""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

from state_machine import LuxoState, StateTransition


class TestLuxoState(unittest.TestCase):
    """Test cases for LuxoState enum."""
    
    def test_state_enum_values(self):
        """Test that all expected states exist."""
        expected_states = [
            'IDLE', 'ANIMATING', 'VOICE_FOLLOWING', 'COLLISION_AVOIDING',
            'RETURNING_HOME', 'ESCAPE_MODE', 'USER_CONTROL', 'EMOTION_REACTING',
            'PETTING', 'ERROR', 'INITIALIZING', 'SHUTDOWN'
        ]
        for state_name in expected_states:
            with self.subTest(state=state_name):
                self.assertTrue(hasattr(LuxoState, state_name))
    
    def test_state_enum_members(self):
        """Test that all states are accessible as enum members."""
        self.assertEqual(LuxoState.IDLE.name, 'IDLE')
        self.assertEqual(LuxoState.ANIMATING.name, 'ANIMATING')
        self.assertEqual(LuxoState.PETTING.name, 'PETTING')


class TestStateTransition(unittest.TestCase):
    """Test cases for StateTransition class."""
    
    def test_init_with_all_parameters(self):
        """Test StateTransition initialization with all parameters."""
        from_state = LuxoState.IDLE
        to_state = LuxoState.ANIMATING
        condition = lambda: True
        action = lambda: None
        
        transition = StateTransition(from_state, to_state, condition, action)
        
        self.assertEqual(transition.from_state, from_state)
        self.assertEqual(transition.to_state, to_state)
        self.assertEqual(transition.condition, condition)
        self.assertEqual(transition.action, action)
    
    def test_init_with_no_condition(self):
        """Test StateTransition initialization without condition."""
        from_state = LuxoState.IDLE
        to_state = LuxoState.ANIMATING
        
        transition = StateTransition(from_state, to_state)
        
        self.assertEqual(transition.from_state, from_state)
        self.assertEqual(transition.to_state, to_state)
        self.assertIsNone(transition.condition)
        self.assertIsNone(transition.action)
    
    def test_init_with_no_action(self):
        """Test StateTransition initialization without action."""
        from_state = LuxoState.IDLE
        to_state = LuxoState.ANIMATING
        condition = lambda: True
        
        transition = StateTransition(from_state, to_state, condition)
        
        self.assertEqual(transition.from_state, from_state)
        self.assertEqual(transition.to_state, to_state)
        self.assertEqual(transition.condition, condition)
        self.assertIsNone(transition.action)
    
    def test_condition_evaluation(self):
        """Test that condition function is properly stored and can be called."""
        condition_result = False
        
        def condition_func():
            nonlocal condition_result
            return condition_result
        
        transition = StateTransition(LuxoState.IDLE, LuxoState.ANIMATING, condition_func)
        
        # Initially condition should return False
        self.assertFalse(transition.condition())
        
        # Change the condition result
        condition_result = True
        self.assertTrue(transition.condition())
    
    def test_action_execution(self):
        """Test that action function is properly stored and can be called."""
        action_called = False
        
        def action_func():
            nonlocal action_called
            action_called = True
        
        transition = StateTransition(LuxoState.IDLE, LuxoState.ANIMATING, action=action_func)
        
        # Action should not be called initially
        self.assertFalse(action_called)
        
        # Call the action
        transition.action()
        self.assertTrue(action_called)


if __name__ == '__main__':
    unittest.main()
