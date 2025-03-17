#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import time
import math

class PositionTestNode(Node):
    def __init__(self):
        super().__init__('position_test')
        
        # Create publisher for joint states
        self.joint_publisher = self.create_publisher(
            JointState, 
            '/joint_states_target',  # Changed from '/joint_states' to '/joint_states_target'
            10)
        
        # Joint names - updated to match RoArm conventions
        self.joint_names = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
        
        # Define test positions (in radians) - more gentle for real hardware
        # Based on the RoArm's range limits from the API documentation
        self.test_positions = [
            [0.0, 0.0, 0.0, 0.0, 3.14],              # Home position with closed gripper
            [0.0, -2.0, 1.0, 0.0, 3.14],             # Sitting position 1 - arm folded back
            [0.0, -2.0, 2.0, 0.0, 3.14],             # Sitting position 2 - more extreme fold
            [0.0, -2.0, 2.0, 2.0, 3.14],             # Sitting position 3 - compact fold
            [0.5, 0.0, 0.0, 0.0, 3.14],              # default with base rotation
            [0.0, 0.5, 0.0, 0.0, 3.14],              # default with shoulder movement
            [0.0, 0.0, 0.5, 0.0, 3.14],              # default with elbow movement
            [0.0, 0.0, 0.0, 0.5, 3.14],              # default with wrist movement
            [0.0, 0.0, 0.0, 0.0, 1.57],              # Open gripper
            [0.3, -0.8, 1.3, 0.5, 1.57],             # Sitting position with open gripper
            [0.0, 0.0, 0.0, 0.0, 3.14]               # Back to home with closed gripper
        ]
        
        # Position index
        self.position_index = 0
        self.current_target = self.test_positions[0]
        self.current_position = self.test_positions[0].copy()
        
        # Timing parameters
        self.move_duration = 4.0  # seconds to reach target
        self.hold_duration = 3.0  # seconds to hold position
        self.start_time = self.get_clock().now()
        self.state = "holding"  # "moving" or "holding"
        
        # Timer for publishing at 20Hz
        self.publish_timer = self.create_timer(0.05, self.update_position)
        
        self.get_logger().info("Position test node started - gentle movements")
        self.get_logger().info(f"Will test {len(self.test_positions)} positions with {self.move_duration}s movements and {self.hold_duration}s holds")
    
    def update_position(self):
        """Update and publish position with smooth transitions."""
        now = self.get_clock().now()
        elapsed = (now - self.start_time).nanoseconds / 1e9
        
        if self.state == "holding":
            # Check if hold time is over
            if elapsed >= self.hold_duration:
                # Move to next position
                self.position_index = (self.position_index + 1) % len(self.test_positions)
                self.start_position = self.current_position.copy()
                self.current_target = self.test_positions[self.position_index]
                self.start_time = now
                self.state = "moving"
                self.get_logger().info(f"Moving to position {self.position_index+1}/{len(self.test_positions)}: {self.current_target}")
        
        elif self.state == "moving":
            # Update position based on elapsed time
            progress = min(1.0, elapsed / self.move_duration)
            
            # Use smooth easing function
            t = progress
            # Cubic easing: t³
            smooth_progress = t * t * t
            
            # Interpolate between start and target positions
            for i in range(len(self.current_position)):
                self.current_position[i] = self.start_position[i] + smooth_progress * (self.current_target[i] - self.start_position[i])
            
            # Check if movement is complete
            if progress >= 1.0:
                self.current_position = self.current_target.copy()
                self.start_time = now
                self.state = "holding"
                self.get_logger().info(f"Holding position {self.position_index+1}")
        
        # Create and publish message
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self.joint_names
        msg.position = self.current_position
        self.joint_publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = PositionTestNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()