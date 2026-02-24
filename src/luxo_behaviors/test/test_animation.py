#!/usr/bin/env python3
"""Tests for the animation system."""

import pytest
import sys
import os
import time

# Add the package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

# Mock ROS2 before importing animation components
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


class TestAnimation:
    """Tests for the Animation class."""
    
    def test_animation_creation(self):
        """Test creating a basic animation."""
        from luxo_behaviors.animation import Animation
        
        anim = Animation('test_animation')
        assert anim.name == 'test_animation'
        assert len(anim.frames) == 0
        assert anim.loop is False
        assert anim.speed == 1.0
    
    def test_add_frame(self):
        """Test adding frames to an animation."""
        from luxo_behaviors.animation import Animation
        
        anim = Animation('test')
        
        # Add a frame
        frame_data = {'joint1': 0.5, 'joint2': 0.3}
        anim.add_frame(frame_data, duration=0.5)
        
        assert len(anim.frames) == 1
        assert anim.frames[0]['data'] == frame_data
        assert anim.frames[0]['duration'] == 0.5
    
    def test_add_multiple_frames(self):
        """Test adding multiple frames."""
        from luxo_behaviors.animation import Animation
        
        anim = Animation('test')
        
        for i in range(5):
            frame_data = {f'joint{i}': float(i) / 10.0}
            anim.add_frame(frame_data, duration=0.1)
        
        assert len(anim.frames) == 5
    
    def test_set_loop(self):
        """Test setting loop mode."""
        from luxo_behaviors.animation import Animation
        
        anim = Animation('test')
        anim.set_loop(True)
        
        assert anim.loop is True
        
        anim.set_loop(False)
        assert anim.loop is False
    
    def test_set_speed(self):
        """Test setting animation speed."""
        from luxo_behaviors.animation import Animation
        
        anim = Animation('test')
        anim.set_speed(2.0)
        
        assert anim.speed == 2.0
        
        anim.set_speed(0.5)
        assert anim.speed == 0.5
    
    def test_get_frame_at_index(self):
        """Test getting a frame by index."""
        from luxo_behaviors.animation import Animation
        
        anim = Animation('test')
        frame_data = {'joint1': 0.5}
        anim.add_frame(frame_data, duration=0.5)
        
        retrieved = anim.get_frame(0)
        assert retrieved['data'] == frame_data
        assert retrieved['duration'] == 0.5
    
    def test_get_frame_out_of_range(self):
        """Test getting a frame out of range."""
        from luxo_behaviors.animation import Animation
        
        anim = Animation('test')
        
        with pytest.raises(IndexError):
            anim.get_frame(0)
    
    def test_get_total_duration(self):
        """Test calculating total animation duration."""
        from luxo_behaviors.animation import Animation
        
        anim = Animation('test')
        anim.add_frame({'joint1': 0.5}, duration=0.5)
        anim.add_frame({'joint1': 0.6}, duration=0.3)
        anim.add_frame({'joint1': 0.7}, duration=0.2)
        
        total = anim.get_total_duration()
        assert total == 1.0
    
    def test_get_total_duration_with_speed(self):
        """Test calculating total duration with speed factor."""
        from luxo_behaviors.animation import Animation
        
        anim = Animation('test')
        anim.add_frame({'joint1': 0.5}, duration=1.0)
        anim.add_frame({'joint1': 0.6}, duration=1.0)
        
        anim.set_speed(2.0)
        total = anim.get_total_duration()
        
        # With speed 2.0, duration should be halved
        assert total == 1.0
    
    def test_clear_frames(self):
        """Test clearing all frames."""
        from luxo_behaviors.animation import Animation
        
        anim = Animation('test')
        anim.add_frame({'joint1': 0.5}, duration=0.5)
        anim.add_frame({'joint1': 0.6}, duration=0.3)
        
        anim.clear_frames()
        assert len(anim.frames) == 0


class TestAnimationPlayer:
    """Tests for the AnimationPlayer class."""
    
    def test_player_creation(self):
        """Test creating an animation player."""
        from luxo_behaviors.animation import AnimationPlayer
        
        player = AnimationPlayer()
        assert player._animations == {}
        assert player._current_animation is None
        assert player._is_playing is False
    
    def test_register_animation(self):
        """Test registering an animation."""
        from luxo_behaviors.animation import Animation, AnimationPlayer
        
        player = AnimationPlayer()
        anim = Animation('test')
        
        player.register_animation(anim)
        
        assert 'test' in player._animations
        assert player._animations['test'] is anim
    
    def test_register_multiple_animations(self):
        """Test registering multiple animations."""
        from luxo_behaviors.animation import Animation, AnimationPlayer
        
        player = AnimationPlayer()
        
        anim1 = Animation('anim1')
        anim2 = Animation('anim2')
        anim3 = Animation('anim3')
        
        player.register_animation(anim1)
        player.register_animation(anim2)
        player.register_animation(anim3)
        
        assert len(player._animations) == 3
    
    def test_play_animation(self):
        """Test playing an animation."""
        from luxo_behaviors.animation import Animation, AnimationPlayer
        
        player = AnimationPlayer()
        anim = Animation('test')
        player.register_animation(anim)
        
        result = player.play('test')
        assert result is True
        assert player._current_animation == anim
        assert player._is_playing is True
    
    def test_play_nonexistent_animation(self):
        """Test playing a non-existent animation."""
        from luxo_behaviors.animation import AnimationPlayer
        
        player = AnimationPlayer()
        
        result = player.play('nonexistent')
        assert result is False
        assert player._is_playing is False
    
    def test_stop_animation(self):
        """Test stopping an animation."""
        from luxo_behaviors.animation import Animation, AnimationPlayer
        
        player = AnimationPlayer()
        anim = Animation('test')
        player.register_animation(anim)
        player.play('test')
        
        player.stop()
        
        assert player._is_playing is False
        assert player._current_animation is None
    
    def test_pause_and_resume(self):
        """Test pausing and resuming an animation."""
        from luxo_behaviors.animation import Animation, AnimationPlayer
        
        player = AnimationPlayer()
        anim = Animation('test')
        player.register_animation(anim)
        player.play('test')
        
        player.pause()
        assert player._is_paused is True
        
        player.resume()
        assert player._is_paused is False
    
    def test_get_current_animation(self):
        """Test getting the current animation."""
        from luxo_behaviors.animation import Animation, AnimationPlayer
        
        player = AnimationPlayer()
        anim = Animation('test')
        player.register_animation(anim)
        player.play('test')
        
        current = player.get_current_animation()
        assert current is anim
    
    def test_get_current_animation_none(self):
        """Test getting current animation when none is playing."""
        from luxo_behaviors.animation import AnimationPlayer
        
        player = AnimationPlayer()
        
        current = player.get_current_animation()
        assert current is None


class TestAnimationActionClient:
    """Tests for the animation action client."""
    
    def test_action_client_creation(self):
        """Test creating an animation action client."""
        from luxo_behaviors.animation_action_client import AnimationActionClient
        
        with mock.patch('rclpy.node.Node.__init__'):
            client = AnimationActionClient()
            assert client._action_client is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
