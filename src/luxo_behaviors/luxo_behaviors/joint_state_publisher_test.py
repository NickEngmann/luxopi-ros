#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import time

class JointStatePublisherTest(Node):
    def __init__(self):
        super().__init__('joint_state_publisher_test')
        
        # Create publisher for both topics to test
        self.joint_publisher = self.create_publisher(
            JointState, 
            '/joint_states_target', 
            10)
            
        self.direct_publisher = self.create_publisher(
            JointState,
            '/joint_states',
            10)
        
        self.joint_names = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
        self.position = [0.0, 0.0, 0.0, 0.0, 3.14]
        
        # Create timer for publishing test messages
        self.create_timer(1.0, self.publish_test_messages)
        
        self.get_logger().info("Joint state publisher test node initialized")
        self.get_logger().info("Publishing test messages to /joint_states_target and /joint_states")
        
    def publish_test_messages(self):
        # Create message
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self.joint_names
        msg.position = self.position
        
        # Publish to joint_states_target
        self.joint_publisher.publish(msg)
        self.get_logger().info(f"Published to /joint_states_target: {self.position}")
        
        # Small modification to position for direct publish
        direct_pos = [p + 0.1 for p in self.position]
        
        # Create direct message
        direct_msg = JointState()
        direct_msg.header.stamp = self.get_clock().now().to_msg()
        direct_msg.name = self.joint_names
        direct_msg.position = direct_pos
        
        # Publish directly to joint_states
        self.direct_publisher.publish(direct_msg)
        self.get_logger().info(f"Published directly to /joint_states: {direct_pos}")
        
        # Alternate between two positions
        if self.position[0] == 0.0:
            self.position = [0.5, 0.2, 0.3, 0.1, 1.57]
        else:
            self.position = [0.0, 0.0, 0.0, 0.0, 3.14]

def main(args=None):
    rclpy.init(args=args)
    node = JointStatePublisherTest()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
