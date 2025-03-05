#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import time

class DemoMode(Node):
    def __init__(self):
        super().__init__('demo_mode')
        
        # Create publisher for animation commands
        self.animation_publisher = self.create_publisher(
            String,
            '/roarm/animation_command',
            10)
        
        # Demo sequence timer
        self.timer = self.create_timer(10.0, self.demo_callback)  # Run demo sequence every 10 seconds
        
        # Demo state
        self.demo_state = 0
        self.animations = ['curious', 'excited', 'sad', 'sweep']
        
        self.get_logger().info('Demo mode initialized')
    
    def demo_callback(self):
        """Cycle through different animation sequences."""
        # Get the current animation
        animation = self.animations[self.demo_state]
        
        # Publish the animation command
        msg = String()
        msg.data = animation
        self.animation_publisher.publish(msg)
        self.get_logger().info(f'Demo: triggering {animation} animation')
        
        # Cycle to next state
        self.demo_state = (self.demo_state + 1) % len(self.animations)

def main(args=None):
    rclpy.init(args=args)
    demo_node = DemoMode()
    
    # Keep the node running
    rclpy.spin(demo_node)
    
    demo_node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()