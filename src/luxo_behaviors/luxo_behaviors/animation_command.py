#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import time

from luxo_behaviors.arm_controller import ArmController

class AnimationCommand(Node):
    def __init__(self):
        super().__init__('animation_command')
        
        # Create arm controller
        self.arm_controller = ArmController()
        
        # Create subscription for animation commands
        self.command_subscription = self.create_subscription(
            String,
            '/roarm/animation_command',
            self.command_callback,
            10)
        
        # Map of animation names to methods
        self.animations = {
            'curious': self.arm_controller.curious_look,
            'excited': self.arm_controller.excited_hop,
            'sad': self.arm_controller.sad_droop,
            'sweep': self.arm_controller.light_sweep,
            'stop': self.arm_controller.stop_animation
        }
        
        self.get_logger().info('Animation command interface initialized')
    
    def command_callback(self, msg):
        """Handle animation command messages."""
        command = msg.data.strip().lower()
        
        if command in self.animations:
            self.get_logger().info(f'Executing animation: {command}')
            self.animations[command]()
        else:
            self.get_logger().warn(f'Unknown animation command: {command}')
            self.get_logger().info(f'Available commands: {", ".join(self.animations.keys())}')

def main(args=None):
    rclpy.init(args=args)
    command_interface = AnimationCommand()
    
    # Keep the node running (this will also run the arm controller)
    rclpy.spin(command_interface)
    
    command_interface.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()