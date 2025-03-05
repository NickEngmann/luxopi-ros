#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import JointState
import time

class AnimationCommand(Node):
    def __init__(self):
        super().__init__('animation_command')
        
        # Parameter to control if this node should publish joint states
        self.declare_parameter('publish_joint_states', True)
        self.should_publish = self.get_parameter('publish_joint_states').get_parameter_value().bool_value
        
        # Create subscription for animation commands
        self.command_subscription = self.create_subscription(
            String,
            '/roarm/animation_command',
            self.command_callback,
            10)
        
        # Create publisher for joint states
        self.joint_publisher = self.create_publisher(
            JointState, 
            '/joint_states', 
            10)
        
        # Current joint positions
        self.current_positions = [0.0, 0.0, 0.0, 0.0]
        
        # Define joint names based on the URDF
        self.joint_names = ['base_to_L1', 'L1_to_L2', 'L2_to_L3', 'L3_to_L4']
        
        # Timer for regular publishing
        self.timer = self.create_timer(0.05, self.publish_joint_states)
        
        # Animation state
        self.is_animating = False
        self.animation_steps = []
        self.current_step = 0
        self.step_durations = []
        self.animation_timer = None
        
        self.get_logger().info('Animation command interface initialized')
    
    def command_callback(self, msg):
        """Handle animation command messages."""
        command = msg.data.strip().lower()
        
        # Map of animation names to methods
        animations = {
            'curious': self.curious_look,
            'excited': self.excited_hop,
            'sad': self.sad_droop,
            'sweep': self.light_sweep,
            'stop': self.stop_animation
        }
        
        if command in animations:
            self.get_logger().info(f'Executing animation: {command}')
            animations[command]()
        else:
            self.get_logger().warn(f'Unknown animation command: {command}')
            self.get_logger().info(f'Available commands: {", ".join(animations.keys())}')
    
    def publish_joint_states(self):
        """Publish current joint states."""
        if not self.should_publish:
            return
        
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self.joint_names
        msg.position = self.current_positions
        self.joint_publisher.publish(msg)
    
    def move_to_position(self, positions, duration=1.0):
        """Move to a specific position over a duration."""
        start_positions = self.current_positions.copy()
        start_time = time.time()
        
        # Continuously update joint positions
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            progress = min(1.0, progress)  # Clamp to 1.0
            
            # Linear interpolation for each joint
            for i in range(len(self.current_positions)):
                self.current_positions[i] = start_positions[i] + progress * (positions[i] - start_positions[i])
            
            time.sleep(0.01)  # Small delay to prevent CPU overload
        
        # Ensure final position is exactly what was requested
        self.current_positions = positions.copy()
    
    # Copy all the remaining methods from arm_controller.py
    def start_animation(self, keyframes, durations):
        """Start an animation with keyframes and durations."""
        self.animation_steps = keyframes
        self.step_durations = durations
        self.current_step = 0
        self.is_animating = True
        
        # Start the animation
        self._process_next_step()

    def _next_step_callback(self):
        """Handle timer callback for the next animation step."""
        # Cancel this timer so it doesn't fire again
        if self.animation_timer:
            self.animation_timer.cancel()
            self.animation_timer = None
        
        # Process the next step
        self._process_next_step()
    
    def _process_next_step(self):
        """Process the next animation step."""
        if not self.is_animating or self.current_step >= len(self.animation_steps):
            self.is_animating = False
            return
        
        # Get the next position and duration
        next_position = self.animation_steps[self.current_step]
        duration = self.step_durations[self.current_step]
        
        # Move to the position
        self.get_logger().info(f'Animation step {self.current_step+1}/{len(self.animation_steps)}')
        self.move_to_position(next_position, duration)
        
        # Increment step and schedule next one
        self.current_step += 1
        if self.current_step < len(self.animation_steps):
            # Schedule the next step using a timer
            self.animation_timer = self.create_timer(
                duration, 
                self._next_step_callback)
        else:
            self.is_animating = False
            self.get_logger().info('Animation completed')
    
    def stop_animation(self):
        """Stop the current animation."""
        self.is_animating = False
        if self.animation_timer:
            self.animation_timer.cancel()
        self.get_logger().info('Animation stopped')

    # Include all animation methods
    def curious_look(self):
        """Make the arm look curiously at something (like Luxo Jr)."""
        # Starting from current position
        start_pos = self.current_positions.copy()
        
        # Keyframe positions
        keyframes = [
            # Small head tilt, slight base rotation
            [0.2, start_pos[1], start_pos[2], 0.5],
            
            # Lean forward
            [0.2, 0.5, 1.2, 0.5],
            
            # Look more intently with further head tilt
            [0.3, 0.5, 1.2, 0.8],
            
            # Hold position
            [0.3, 0.5, 1.2, 0.8],
            
            # Return to a neutral position with head still slightly tilted
            [0.0, 0.3, 0.7, 0.3]
        ]
        
        # Duration for each keyframe (in seconds)
        durations = [0.8, 0.8, 0.6, 1.0, 1.2]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing curious look animation')
    
    def excited_hop(self):
        """Make the arm do an excited little hop like Luxo Jr."""
        # Keyframe positions
        keyframes = [
            # Crouch down (prepare to hop)
            [0.0, 0.8, 1.5, 0.0],
            
            # Quick extension upward (the hop)
            [0.0, 0.2, 0.8, 0.7],
            
            # Slight bounce on landing
            [0.0, 0.4, 0.9, 0.5],
            
            # Return to neutral but with "head" up
            [0.0, 0.3, 0.7, 0.4]
        ]
        
        # Faster durations for more energetic movement
        durations = [0.6, 0.3, 0.4, 0.7]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing excited hop animation')
    
    def sad_droop(self):
        """Make the arm droop down sadly."""
        # Keyframe positions
        keyframes = [
            # Start looking down slightly
            [0.0, 0.3, 0.7, -0.3],
            
            # Begin to droop
            [-0.2, 0.5, 0.9, -0.5],
            
            # Full droop with head down
            [-0.2, 0.7, 1.2, -1.0],
            
            # Hold the sad position
            [-0.2, 0.7, 1.2, -1.0],
            
            # Slowly return to neutral
            [0.0, 0.3, 0.7, 0.0]
        ]
        
        # Slower durations for a sad mood
        durations = [1.0, 1.2, 1.0, 1.5, 2.0]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing sad droop animation')
    
    def light_sweep(self):
        """Make the arm sweep across like a desk lamp looking for something."""
        # Set a neutral position for the arm
        neutral_arm = [0.0, 0.4, 0.9, 0.3]
        
        # Keyframe positions - only changing the base rotation and head tilt
        keyframes = [
            # Start position (left side)
            [-1.0, neutral_arm[1], neutral_arm[2], neutral_arm[3]],
            
            # Mid-left with head up slightly
            [-0.6, neutral_arm[1], neutral_arm[2], 0.5],
            
            # Center position with head normal
            [0.0, neutral_arm[1], neutral_arm[2], 0.3],
            
            # Mid-right with head up slightly
            [0.6, neutral_arm[1], neutral_arm[2], 0.5],
            
            # Far right position
            [1.0, neutral_arm[1], neutral_arm[2], 0.3],
            
            # Return to center
            [0.0, neutral_arm[1], neutral_arm[2], 0.0]
        ]
        
        # Durations for a smooth scanning movement
        durations = [0.8, 0.6, 0.6, 0.6, 0.8, 1.0]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing light sweep animation')

def main(args=None):
    rclpy.init(args=args)
    command_interface = AnimationCommand()
    
    # Keep the node running
    rclpy.spin(command_interface)
    
    command_interface.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()