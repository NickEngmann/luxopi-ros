#!/usr/bin/env python3
"""Tests for collision detection system."""

import pytest
import sys
import os
import time

# Add the package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'luxo_behaviors'))

# Mock ROS2 before importing collision detection components
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


class TestCollisionDetector:
    """Tests for the collision detector."""
    
    def test_detector_creation(self):
        """Test creating a collision detector."""
        from luxo_behaviors.collision_detection import CollisionDetector
        
        detector = CollisionDetector()
        assert detector is not None
        assert len(detector._obstacles) == 0
    
    def test_add_obstacle(self):
        """Test adding an obstacle."""
        from luxo_behaviors.collision_detection import CollisionDetector
        
        detector = CollisionDetector()
        
        obstacle = {
            'position': [0.5, 0.3, 0.2],
            'size': [0.1, 0.1, 0.1],
            'type': 'static'
        }
        
        detector.add_obstacle(obstacle)
        
        assert len(detector._obstacles) == 1
        assert detector._obstacles[0] == obstacle
    
    def test_add_multiple_obstacles(self):
        """Test adding multiple obstacles."""
        from luxo_behaviors.collision_detection import CollisionDetector
        
        detector = CollisionDetector()
        
        for i in range(5):
            obstacle = {
                'position': [float(i) * 0.1, 0.3, 0.2],
                'size': [0.1, 0.1, 0.1],
                'type': 'static'
            }
            detector.add_obstacle(obstacle)
        
        assert len(detector._obstacles) == 5
    
    def test_remove_obstacle(self):
        """Test removing an obstacle."""
        from luxo_behaviors.collision_detection import CollisionDetector
        
        detector = CollisionDetector()
        
        obstacle = {
            'position': [0.5, 0.3, 0.2],
            'size': [0.1, 0.1, 0.1],
            'type': 'static'
        }
        
        detector.add_obstacle(obstacle)
        assert len(detector._obstacles) == 1
        
        detector.remove_obstacle(obstacle)
        assert len(detector._obstacles) == 0
    
    def test_clear_obstacles(self):
        """Test clearing all obstacles."""
        from luxo_behaviors.collision_detection import CollisionDetector
        
        detector = CollisionDetector()
        
        for i in range(5):
            obstacle = {
                'position': [float(i) * 0.1, 0.3, 0.2],
                'size': [0.1, 0.1, 0.1],
                'type': 'static'
            }
            detector.add_obstacle(obstacle)
        
        detector.clear_obstacles()
        assert len(detector._obstacles) == 0
    
    def test_check_collision_with_obstacle(self):
        """Test checking for collision with obstacle."""
        from luxo_behaviors.collision_detection import CollisionDetector
        
        detector = CollisionDetector()
        
        obstacle = {
            'position': [0.5, 0.0, 0.0],
            'size': [0.2, 0.2, 0.2],
            'type': 'static'
        }
        
        detector.add_obstacle(obstacle)
        
        # Check if a position within the obstacle would collide
        robot_position = [0.5, 0.0, 0.0]
        robot_size = [0.1, 0.1, 0.1]
        
        collision = detector.check_collision(robot_position, robot_size)
        assert collision is True
    
    def test_check_no_collision(self):
        """Test checking for no collision."""
        from luxo_behaviors.collision_detection import CollisionDetector
        
        detector = CollisionDetector()
        
        obstacle = {
            'position': [1.0, 1.0, 1.0],
            'size': [0.2, 0.2, 0.2],
            'type': 'static'
        }
        
        detector.add_obstacle(obstacle)
        
        # Check if a distant position would not collide
        robot_position = [0.0, 0.0, 0.0]
        robot_size = [0.1, 0.1, 0.1]
        
        collision = detector.check_collision(robot_position, robot_size)
        assert collision is False
    
    def test_get_closest_obstacle(self):
        """Test getting the closest obstacle."""
        from luxo_behaviors.collision_detection import CollisionDetector
        
        detector = CollisionDetector()
        
        # Add obstacles at different distances
        detector.add_obstacle({
            'position': [0.1, 0.0, 0.0],
            'size': [0.1, 0.1, 0.1],
            'type': 'static'
        })
        detector.add_obstacle({
            'position': [1.0, 0.0, 0.0],
            'size': [0.1, 0.1, 0.1],
            'type': 'static'
        })
        
        closest = detector.get_closest_obstacle([0.0, 0.0, 0.0])
        assert closest is not None
        assert closest['position'][0] == 0.1  # Closest is at x=0.1
    
    def test_update_obstacle_position(self):
        """Test updating an obstacle's position."""
        from luxo_behaviors.collision_detection import CollisionDetector
        
        detector = CollisionDetector()
        
        obstacle = {
            'position': [0.5, 0.0, 0.0],
            'size': [0.1, 0.1, 0.1],
            'type': 'static'
        }
        
        detector.add_obstacle(obstacle)
        
        # Update position
        detector.update_obstacle(obstacle, {'position': [0.6, 0.0, 0.0]})
        
        assert detector._obstacles[0]['position'][0] == 0.6
    
    def test_get_all_obstacles(self):
        """Test getting all obstacles."""
        from luxo_behaviors.collision_detection import CollisionDetector
        
        detector = CollisionDetector()
        
        for i in range(3):
            obstacle = {
                'position': [float(i) * 0.1, 0.0, 0.0],
                'size': [0.1, 0.1, 0.1],
                'type': 'static'
            }
            detector.add_obstacle(obstacle)
        
        obstacles = detector.get_all_obstacles()
        assert len(obstacles) == 3


class TestCollisionAvoidanceNode:
    """Tests for the collision avoidance node."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        mock.MagicMock.reset_mock()
    
    def test_node_creation(self):
        """Test creating a collision avoidance node."""
        from luxo_behaviors.collision_avoidance_node import CollisionAvoidanceNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = CollisionAvoidanceNode()
            assert node is not None
    
    def test_process_sensor_data(self):
        """Test processing sensor data."""
        from luxo_behaviors.collision_avoidance_node import CollisionAvoidanceNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = CollisionAvoidanceNode()
            
            # Mock sensor data
            sensor_data = {
                'distance': 0.5,
                'angle': 45.0,
                'timestamp': time.time()
            }
            
            result = node.process_sensor_data(sensor_data)
            assert result is not None
    
    def test_generate_safe_path(self):
        """Test generating a safe path."""
        from luxo_behaviors.collision_avoidance_node import CollisionAvoidanceNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = CollisionAvoidanceNode()
            
            start_position = [0.0, 0.0, 0.0]
            target_position = [1.0, 1.0, 1.0]
            
            path = node.generate_safe_path(start_position, target_position)
            assert path is not None
    
    def test_handle_emergency_stop(self):
        """Test handling emergency stop."""
        from luxo_behaviors.collision_avoidance_node import CollisionAvoidanceNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = CollisionAvoidanceNode()
            
            node.handle_emergency_stop()
            # Should set emergency state
            assert node._emergency_stop is True
    
    def test_reset_emergency_stop(self):
        """Test resetting emergency stop."""
        from luxo_behaviors.collision_avoidance_node import CollisionAvoidanceNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = CollisionAvoidanceNode()
            
            node.handle_emergency_stop()
            assert node._emergency_stop is True
            
            node.reset_emergency_stop()
            assert node._emergency_stop is False
    
    def test_cleanup(self):
        """Test cleanup method."""
        from luxo_behaviors.collision_avoidance_node import CollisionAvoidanceNode
        
        with mock.patch('rclpy.node.Node.__init__'):
            node = CollisionAvoidanceNode()
            
            # This should not raise an exception
            node.cleanup()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
