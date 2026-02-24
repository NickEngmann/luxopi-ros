#!/usr/bin/env python3
"""Tests for the state manager node."""

import pytest
import sys
import os
import threading
import time

# Add the package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

# Mock ROS2 before importing state_manager
import unittest.mock as mock

# Mock all ROS2 imports
sys.modules['rclpy'] = mock.MagicMock()
sys.modules['rclpy.node'] = mock.MagicMock()
sys.modules['rclpy.qos'] = mock.MagicMock()
sys.modules['rclpy.executors'] = mock.MagicMock()
sys.modules['std_msgs.msg'] = mock.MagicMock()
sys.modules['geometry_msgs.msg'] = mock.MagicMock()
sys.modules['diagnostic_msgs.msg'] = mock.MagicMock()
sys.modules['luxo_interfaces.msg'] = mock.MagicMock()
sys.modules['luxo_interfaces.srv'] = mock.MagicMock()

# Now we can import the state machine components
from luxo_behaviors.state_machine import LuxoState, StateTransition


class TestStateManagerNode:
    """Tests for the StateManagerNode class."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        # Reset mock before each test
        mock.MagicMock.reset_mock()
        
        # Import after mocking
        from luxo_behaviors.state_manager_node import StateManagerNode
        
        # Create a mock node
        with mock.patch('rclpy.node.Node.__init__'):
            with mock.patch.object(StateManagerNode, '_initialize_neopixel'):
                self.node = StateManagerNode()
                # Set required attributes
                self.node._last_update_time = time.time()
                self.node._last_publish_time = time.time()
                self.node._update_count = 0
                self.node._publish_count = 0
    
    def test_initial_state(self):
        """Test that the node starts in INITIALIZING state."""
        assert self.node._current_state == LuxoState.INITIALIZING
    
    def test_state_transitions(self):
        """Test basic state transitions."""
        # Test transition from INITIALIZING to IDLE
        result = self.node.transition_to(LuxoState.IDLE)
        assert result is True
        assert self.node._current_state == LuxoState.IDLE
    
    def test_invalid_state_transition(self):
        """Test that invalid transitions are rejected."""
        # First transition to IDLE
        self.node.transition_to(LuxoState.IDLE)
        
        # Try an invalid transition (IDLE -> INITIALIZING should be invalid)
        result = self.node.transition_to(LuxoState.INITIALIZING)
        assert result is False
    
    def test_state_priority_system(self):
        """Test the priority-based state request system."""
        # Test that higher priority states can override lower priority ones
        self.node._active_node_states['low_priority'] = (LuxoState.IDLE, 10, time.time())
        
        # Add a high priority request
        self.node._active_node_states['high_priority'] = (LuxoState.ESCAPE_MODE, 90, time.time())
        
        # Check that priorities are stored correctly
        assert self.node._active_node_states['low_priority'][1] == 10
        assert self.node._active_node_states['high_priority'][1] == 90
    
    def test_state_callbacks(self):
        """Test state enter/exit callbacks."""
        enter_called = [False]
        exit_called = [False]
        
        def on_enter(state):
            enter_called[0] = True
        
        def on_exit(state):
            exit_called[0] = True
        
        # Register callbacks
        self.node.register_on_enter_callback(LuxoState.IDLE, on_enter)
        self.node.register_on_exit_callback(LuxoState.IDLE, on_exit)
        
        # Transition to IDLE
        self.node.transition_to(LuxoState.IDLE)
        
        assert enter_called[0] is True
    
    def test_get_state_duration(self):
        """Test getting the duration of current state."""
        self.node.transition_to(LuxoState.IDLE)
        time.sleep(0.1)
        
        duration = self.node.get_state_duration()
        assert duration >= 0.1
    
    def test_is_in_state(self):
        """Test checking if node is in a particular state."""
        self.node.transition_to(LuxoState.IDLE)
        
        assert self.node.is_in_state(LuxoState.IDLE) is True
        assert self.node.is_in_state(LuxoState.ANIMATING) is False
    
    def test_is_in_multiple_states(self):
        """Test checking if node is in any of multiple states."""
        self.node.transition_to(LuxoState.IDLE)
        
        assert self.node.is_in_state(LuxoState.IDLE, LuxoState.ANIMATING) is True
        assert self.node.is_in_state(LuxoState.ANIMATING, LuxoState.ESCAPE_MODE) is False
    
    def test_get_state_history(self):
        """Test getting state history."""
        self.node.transition_to(LuxoState.IDLE)
        time.sleep(0.01)
        self.node.transition_to(LuxoState.ANIMATING)
        
        history = self.node.get_state_history()
        assert len(history) >= 1
        assert history[-1]['state'] == LuxoState.ANIMATING
    
    def test_cleanup(self):
        """Test cleanup method."""
        # This should not raise an exception
        self.node.cleanup()
    
    def test_check_health_with_stuck_update(self):
        """Test health check detects stuck update timer."""
        # Simulate a stuck update timer
        self.node._last_update_time = time.time() - 3.0  # 3 seconds ago
        
        # Should detect the issue and try to recover
        self.node.check_health()
    
    def test_check_health_with_stuck_publish(self):
        """Test health check detects stuck publish timer."""
        # Simulate a stuck publish timer
        self.node._last_publish_time = time.time() - 6.0  # 6 seconds ago
        
        # Should detect the issue
        self.node.check_health()


class TestPriorityBasedTransitions:
    """Tests for priority-based state transitions."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        mock.MagicMock.reset_mock()
        
        from luxo_behaviors.state_manager_node import StateManagerNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            with mock.patch.object(StateManagerNode, '_initialize_neopixel'):
                self.node = StateManagerNode()
                self.node._last_update_time = time.time()
                self.node._last_publish_time = time.time()
                self.node._update_count = 0
                self.node._publish_count = 0
    
    def test_high_priority_can_force_transition(self):
        """Test that high priority can force a state transition."""
        # Start in IDLE
        self.node.transition_to(LuxoState.IDLE)
        
        # Add a high priority request (escape mode)
        self.node._active_node_states['escape'] = (LuxoState.ESCAPE_MODE, 90, time.time())
        
        # Should be able to transition to escape mode
        result = self.node.transition_to(LuxoState.ESCAPE_MODE)
        assert result is True
        assert self.node._current_state == LuxoState.ESCAPE_MODE


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
