#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from builtin_interfaces.msg import Time
from nav_msgs.msg import Odometry


class DiagnosticNode(Node):
    def __init__(self):
        super().__init__('diagnostic_checker')
        self.get_logger().info('Diagnostic checker started')
        
        # Subscribe to behavior tree state
        self.bt_sub = self.create_subscription(
            String, 
            '/behavior_tree_log',
            self.bt_callback,
            10)
            
        # Subscribe to odometry to check if robot is moving
        self.odom_sub = self.create_subscription(
            Odometry,
            '/luxo/odom',
            self.odom_callback,
            10)
        
        # Check parameters
        self.demo_param = self.declare_parameter('run_demo', False).value
        self.get_logger().info(f'run_demo parameter is set to: {self.demo_param}')
        
        # Create a timer to periodically check system status
        self.timer = self.create_timer(5.0, self.check_status)
        self.last_odom_time = None
        self.movement_detected = False
        
    def bt_callback(self, msg):
        self.get_logger().info(f'Behavior Tree state: {msg.data}')
        
    def odom_callback(self, msg):
        current_time = msg.header.stamp
        
        # Check if we're getting odometry updates
        if self.last_odom_time is None:
            self.last_odom_time = current_time
            return
            
        # Check if there's any movement (velocity)
        if abs(msg.twist.twist.linear.x) > 0.001 or abs(msg.twist.twist.angular.z) > 0.001:
            self.movement_detected = True
            
    def check_status(self):
        self.get_logger().info('=== Diagnostic Status ===')
        self.get_logger().info(f'Movement detected: {self.movement_detected}')
        self.get_logger().info(f'Run demo parameter: {self.demo_param}')
        

def main():
    rclpy.init()
    node = DiagnosticNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
