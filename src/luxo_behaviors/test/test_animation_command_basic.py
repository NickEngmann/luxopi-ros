import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

# Mock ROS2 imports
sys.modules['rclpy'] = Mock()
sys.modules['rclpy.node'] = Mock()
sys.modules['rclpy.action'] = Mock()
sys.modules['rclpy.callback_groups'] = Mock()
sys.modules['rclpy.executors'] = Mock()
sys.modules['rclpy.duration'] = Mock()
sys.modules['rclpy.time'] = Mock()
sys.modules['rclpy.constants'] = Mock()
sys.modules['std_msgs'] = Mock()
sys.modules['std_msgs.msg'] = Mock()
sys.modules['std_msgs.msg.String'] = Mock()
sys.modules['luxo_interfaces'] = Mock()
sys.modules['luxo_interfaces.action'] = Mock()
sys.modules['luxo_interfaces.action.PlayAnima'] = Mock()
sys.modules['luxo_interfaces.action.PlayAnima.Goal'] = Mock()
sys.modules['luxo_interfaces.action.PlayAnima.Result'] = Mock()
sys.modules['luxo_interfaces.action.PlayAnima.Feedback'] = Mock()
sys.modules['luxo_interfaces.msg'] = Mock()
sys.modules['luxo_interfaces.msg.JointState'] = Mock()
sys.modules['luxo_interfaces.msg.JointCommand'] = Mock()
sys.modules['luxo_interfaces.msg.BehaviorState'] = Mock()

class TestAnimationCommandBasic:
    """Basic test cases for AnimationCommand class."""
    
    def test_animation_command_init(self):
        """Test AnimationCommand initialization."""
        from animation_command import AnimationCommand
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        mock_node.create_action_server = Mock()
        
        command = AnimationCommand(node=mock_node)
        
        assert command.node == mock_node
    
    def test_animation_command_default_values(self):
        """Test AnimationCommand with default values."""
        from animation_command import AnimationCommand
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        mock_node.create_action_server = Mock()
        
        command = AnimationCommand(node=mock_node)
        
        assert command._current_animation is None
        assert command._current_joint_angles is None
        assert command._current_speed is None
    
    def test_animation_command_play_animation(self):
        """Test play_animation method."""
        from animation_command import AnimationCommand
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        mock_node.create_action_server = Mock()
        
        command = AnimationCommand(node=mock_node)
        
        # Mock the publish_joint_angles method
        command.publish_joint_angles = Mock()
        
        # Test with valid animation
        command.play_animation('wave')
        assert command._current_animation == 'wave'
        command.publish_joint_angles.assert_called_once()
    
    def test_animation_command_stop_animation(self):
        """Test stop_animation method."""
        from animation_command import AnimationCommand
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        mock_node.create_action_server = Mock()
        
        command = AnimationCommand(node=mock_node)
        
        # Set a current animation
        command._current_animation = 'wave'
        
        # Mock the publish_joint_angles method
        command.publish_joint_angles = Mock()
        
        # Stop the animation
        command.stop_animation()
        assert command._current_animation is None
    
    def test_animation_command_set_speed(self):
        """Test set_speed method."""
        from animation_command import AnimationCommand
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        mock_node.create_action_server = Mock()
        
        command = AnimationCommand(node=mock_node)
        
        command.set_speed(0.5)
        assert command._current_speed == 0.5
    
    def test_animation_command_publish_joint_angles(self):
        """Test publish_joint_angles method."""
        from animation_command import AnimationCommand
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_publisher = Mock()
        mock_node.create_publisher = Mock(return_value=mock_publisher)
        mock_node.create_action_server = Mock()
        
        command = AnimationCommand(node=mock_node)
        
        # Mock joint angles
        joint_angles = [0.0, 45.0, 90.0, 135.0, 180.0, 0.0]
        
        command.publish_joint_angles(joint_angles)
        assert command._current_joint_angles == joint_angles
    
    def test_animation_command_publish_joint_angles_empty(self):
        """Test publish_joint_angles with empty list."""
        from animation_command import AnimationCommand
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_publisher = Mock()
        mock_node.create_publisher = Mock(return_value=mock_publisher)
        mock_node.create_action_server = Mock()
        
        command = AnimationCommand(node=mock_node)
        
        # Mock empty joint angles
        joint_angles = []
        
        command.publish_joint_angles(joint_angles)
        assert command._current_joint_angles == joint_angles
    
    def test_animation_command_publish_joint_angles_invalid(self):
        """Test publish_joint_angles with invalid angles."""
        from animation_command import AnimationCommand
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_publisher = Mock()
        mock_node.create_publisher = Mock(return_value=mock_publisher)
        mock_node.create_action_server = Mock()
        
        command = AnimationCommand(node=mock_node)
        
        # Mock invalid joint angles (out of range)
        joint_angles = [0.0, 45.0, 90.0, 135.0, 180.0, 200.0]  # 200 is out of range
        
        command.publish_joint_angles(joint_angles)
        assert command._current_joint_angles == joint_angles
    
    def test_animation_command_get_current_animation(self):
        """Test get_current_animation method."""
        from animation_command import AnimationCommand
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        mock_node.create_action_server = Mock()
        
        command = AnimationCommand(node=mock_node)
        
        # Set a current animation
        command._current_animation = 'wave'
        
        current = command.get_current_animation()
        assert current == 'wave'
    
    def test_animation_command_get_current_joint_angles(self):
        """Test get_current_joint_angles method."""
        from animation_command import AnimationCommand
        
        mock_node = Mock()
        mock_node.get_logger = Mock(return_value=Mock())
        mock_node.get_clock = Mock(return_value=Mock())
        mock_node.get_clock().now = Mock(return_value=Mock())
        mock_node.create_publisher = Mock()
        mock_node.create_action_server = Mock()
        
        command = AnimationCommand(node=mock_node)
        
        # Set current joint angles
        joint_angles = [0.0, 45.0, 90.0, 135.0, 180.0, 0.0]
        command._current_joint_angles = joint_angles
        
        current = command.get_current_joint_angles()
        assert current == joint_angles
