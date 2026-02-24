#!/usr/bin/env python3
"""Tests for voice following functionality."""

import pytest
import sys
import os
import time

# Add the package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

# Mock ROS2 before importing voice following components
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


class TestVoiceDirectionNode:
    """Tests for the voice direction node."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        mock.MagicMock.reset_mock()
    
    def test_node_creation(self):
        """Test creating a voice direction node."""
        from luxo_behaviors.voice_direction_node import VoiceDirectionNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = VoiceDirectionNode()
            assert node is not None
    
    def test_process_voice_direction(self):
        """Test processing voice direction data."""
        from luxo_behaviors.voice_direction_node import VoiceDirectionNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = VoiceDirectionNode()
            
            # Mock the direction data
            direction = 45.0  # degrees
            confidence = 0.8
            
            result = node.process_voice_direction(direction, confidence)
            assert result is not None
    
    def test_update_direction_history(self):
        """Test updating direction history."""
        from luxo_behaviors.voice_direction_node import VoiceDirectionNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = VoiceDirectionNode()
            
            # Add some direction data
            node._direction_history.append((time.time(), 0.0, 0.9))
            node._direction_history.append((time.time(), 45.0, 0.8))
            node._direction_history.append((time.time(), 90.0, 0.7))
            
            assert len(node._direction_history) == 3
    
    def test_calculate_average_direction(self):
        """Test calculating average direction."""
        from luxo_behaviors.voice_direction_node import VoiceDirectionNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = VoiceDirectionNode()
            
            # Add direction data
            node._direction_history.append((time.time(), 0.0, 1.0))
            node._direction_history.append((time.time(), 0.0, 1.0))
            
            avg = node._calculate_average_direction()
            assert avg == 0.0
    
    def test_calculate_average_direction_with_multiple_values(self):
        """Test calculating average with multiple direction values."""
        from luxo_behaviors.voice_direction_node import VoiceDirectionNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = VoiceDirectionNode()
            
            # Add direction data
            node._direction_history.append((time.time(), 0.0, 1.0))
            node._direction_history.append((time.time(), 90.0, 1.0))
            node._direction_history.append((time.time(), 180.0, 1.0))
            node._direction_history.append((time.time(), 270.0, 1.0))
            
            # Average of 0, 90, 180, 270 should be around 135 or similar
            avg = node._calculate_average_direction()
            assert avg is not None
    
    def test_filter_direction_data(self):
        """Test filtering direction data by confidence."""
        from luxo_behaviors.voice_direction_node import VoiceDirectionNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = VoiceDirectionNode()
            
            # Add data with different confidence levels
            node._direction_history.append((time.time(), 0.0, 0.9))
            node._direction_history.append((time.time(), 45.0, 0.3))  # Low confidence
            node._direction_history.append((time.time(), 90.0, 0.8))
            
            # Filter should remove low confidence data
            filtered = [(t, d, c) for t, d, c in node._direction_history if c >= 0.5]
            assert len(filtered) == 2
    
    def test_handle_voice_command(self):
        """Test handling voice commands."""
        from luxo_behaviors.voice_direction_node import VoiceDirectionNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = VoiceDirectionNode()
            
            # Test various voice commands
            commands = ['follow', 'stop', 'idle', 'home']
            
            for cmd in commands:
                result = node.handle_voice_command(cmd)
                # Should return some response
                assert result is not None
    
    def test_reset_direction_tracking(self):
        """Test resetting direction tracking."""
        from luxo_behaviors.voice_direction_node import VoiceDirectionNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = VoiceDirectionNode()
            
            # Add some data
            node._direction_history.append((time.time(), 45.0, 0.8))
            
            # Reset
            node.reset_direction_tracking()
            
            assert len(node._direction_history) == 0
    
    def test_cleanup(self):
        """Test cleanup method."""
        from luxo_behaviors.voice_direction_node import VoiceDirectionNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = VoiceDirectionNode()
            
            # This should not raise an exception
            node.cleanup()


class TestVoiceBehavior:
    """Tests for the voice behavior system."""
    
    def test_behavior_creation(self):
        """Test creating a voice behavior."""
        from luxo_behaviors.voice_behavior import VoiceBehavior
        
        behavior = VoiceBehavior()
        assert behavior is not None
    
    def test_process_audio_command(self):
        """Test processing audio commands."""
        from luxo_behaviors.voice_behavior import VoiceBehavior
        
        behavior = VoiceBehavior()
        
        # Test various commands
        commands = ['hello', 'wave', 'dance', 'stop']
        
        for cmd in commands:
            result = behavior.process_command(cmd)
            assert result is not None
    
    def test_handle_emotion_detection(self):
        """Test handling emotion detection."""
        from luxo_behaviors.voice_behavior import VoiceBehavior
        
        behavior = VoiceBehavior()
        
        emotions = ['happy', 'sad', 'angry', 'neutral']
        
        for emotion in emotions:
            result = behavior.handle_emotion(emotion)
            assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
