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
            'playful': self.playful_bounce,
            'startled': self.startled_jump,
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
        
        # Keyframe positions with enhanced dynamics
        keyframes = [
            # Quick "notice something" movement (anticipation)
            [0.0, start_pos[1]+0.1, start_pos[2]-0.1, -0.2],
            
            # Hesitant approach - slight tilt (personality)
            [0.2, 0.4, 0.9, 0.3],
            
            # Lean in to investigate (overlapping action)
            [0.3, 0.6, 1.3, 0.5],
            
            # Quick surprised reaction (snappy timing)
            [0.3, 0.4, 1.1, 0.9],
            
            # More intense inspection - tilt head other way (contrast)
            [0.3, 0.5, 1.2, -0.3],
            
            # Final examination with head tilt (follow-through)
            [0.2, 0.5, 1.2, 0.7],
            
            # Return with slight lingering interest (easy-in)
            [0.0, 0.3, 0.7, 0.2]
        ]
        
        # Duration for each keyframe (in seconds) - varied timing
        durations = [0.4, 0.7, 0.6, 0.3, 0.5, 0.8, 1.0]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing curious look animation')
    
    def excited_hop(self):
        """Make the arm do an excited little hop like Luxo Jr."""
        # Keyframe positions
        keyframes = [
            # Initial anticipation - slight lean back
            [0.0, 0.4, 0.8, 0.3],
            
            # Deep crouch down (prepare to hop - anticipation)
            [0.0, 0.9, 1.6, -0.2],
            
            # Quick extension upward (the hop)
            [0.0, 0.1, 0.6, 0.8],
            
            # Hold at apex briefly (emphasis)
            [0.0, 0.1, 0.6, 0.9],
            
            # Start coming down
            [0.0, 0.3, 0.8, 0.6],
            
            # Land with impact (squash)
            [0.0, 0.7, 1.2, 0.3],
            
            # Bounce up slightly (follow-through)
            [0.0, 0.4, 0.9, 0.5],
            
            # Smaller secondary bounce (overlapping action)
            [0.0, 0.5, 1.0, 0.4],
            
            # Settle to excited "standing" pose
            [0.0, 0.3, 0.7, 0.5]
        ]
        
        # Varied durations for more dynamic movement
        durations = [0.5, 0.6, 0.2, 0.1, 0.2, 0.15, 0.3, 0.2, 0.5]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing excited hop animation')
    
    def sad_droop(self):
        """Make the arm droop down sadly."""
        # Keyframe positions
        keyframes = [
            # Initial reaction - slight recoil (anticipation)
            [0.0, 0.2, 0.6, 0.1],
            
            # Start looking down with hesitation
            [0.0, 0.3, 0.7, -0.2],
            
            # First droop with slight shake (emotion)
            [-0.1, 0.5, 0.9, -0.4],
            
            # Attempt to look up (personality)
            [-0.1, 0.4, 0.8, -0.1],
            
            # Give up - deeper droop (contrast in motion)
            [-0.2, 0.6, 1.1, -0.7],
            
            # Final dramatic slump (emphasis)
            [-0.2, 0.8, 1.3, -1.2],
            
            # Small defeated movement (subtle secondary action)
            [-0.2, 0.75, 1.25, -1.1],
            
            # Hold the sad position
            [-0.2, 0.7, 1.2, -1.0],
            
            # Very slow return halfway
            [-0.1, 0.5, 0.9, -0.5],
            
            # Final return to neutral with lingering droop
            [0.0, 0.3, 0.7, -0.1]
        ]
        
        # Slower, heavier durations for sadness
        durations = [0.5, 0.8, 0.7, 0.9, 0.8, 1.0, 0.5, 1.5, 1.8, 1.5]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing sad droop animation')
    
    def light_sweep(self):
        """Make the arm sweep across like a desk lamp looking for something."""
        # Set a neutral position for the arm
        neutral_arm = [0.0, 0.4, 0.9, 0.3]
        
        # Keyframe positions with more character
        keyframes = [
            # Alert starting position
            [0.0, 0.3, 0.8, 0.5],
            
            # Quick turn to left side (anticipation)
            [-0.8, 0.3, 0.8, 0.3],
            
            # Extend further left with curiosity
            [-1.1, 0.35, 0.85, 0.6],
            
            # Peer downward on left side
            [-1.0, 0.5, 1.0, -0.2],
            
            # Up quickly (searching)
            [-0.9, 0.3, 0.7, 0.7],
            
            # Move to mid-left and pause
            [-0.5, 0.35, 0.8, 0.4],
            
            # Glance down mid-left
            [-0.5, 0.45, 0.95, -0.1],
            
            # Quick center check
            [0.0, 0.4, 0.9, 0.5],
            
            # Skip to mid-right (urgency)
            [0.5, 0.35, 0.8, 0.4],
            
            # Peer down mid-right
            [0.5, 0.45, 0.95, -0.1],
            
            # Quick look up (double-take)
            [0.6, 0.3, 0.7, 0.7],
            
            # Swing to far right
            [1.1, 0.35, 0.85, 0.6],
            
            # Final check down right
            [1.0, 0.5, 1.0, -0.2],
            
            # Found something! (emphasis)
            [0.8, 0.3, 0.7, 0.8],
            
            # Return to center with excitement
            [0.0, 0.3, 0.7, 0.5]
        ]
        
        # Varied durations for more dynamic searching
        durations = [0.5, 0.4, 0.3, 0.6, 0.3, 0.5, 0.6, 0.4, 0.4, 0.6, 0.3, 0.5, 0.6, 0.3, 0.8]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing light sweep animation')

    def playful_bounce(self):
        """Make the arm perform a playful, energetic bounce sequence."""
        # Keyframe positions
        keyframes = [
            # Start posture - slightly alert
            [0.0, 0.3, 0.7, 0.3],
            
            # Quick wiggle right (anticipation)
            [0.3, 0.35, 0.75, 0.4],
            
            # Quick wiggle left (anticipation)
            [-0.3, 0.35, 0.75, 0.4],
            
            # Crouch down (preparing)
            [0.0, 0.7, 1.3, 0.2],
            
            # Big bounce up
            [0.0, 0.1, 0.5, 0.8],
            
            # Land with impact
            [0.0, 0.6, 1.1, 0.3],
            
            # Small bounce 1
            [0.2, 0.3, 0.7, 0.5],
            
            # Land and crouch right
            [0.3, 0.6, 1.1, 0.3],
            
            # Small bounce 2
            [-0.2, 0.3, 0.7, 0.6],
            
            # Land and crouch left
            [-0.3, 0.6, 1.1, 0.3],
            
            # Final small hop to center
            [0.0, 0.2, 0.6, 0.7],
            
            # Return to calm but happy pose
            [0.0, 0.3, 0.7, 0.4]
        ]
        
        # Energetic timing with pauses for emphasis
        durations = [0.4, 0.2, 0.2, 0.5, 0.2, 0.15, 0.3, 0.2, 0.3, 0.2, 0.3, 0.5]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing playful bounce animation')

    def startled_jump(self):
        """Make the arm perform a startled jump and cautious recovery."""
        # Keyframe positions
        keyframes = [
            # Calm starting position
            [0.0, 0.3, 0.7, 0.0],
            
            # Freeze momentarily (anticipation)
            [0.0, 0.3, 0.7, 0.0],
            
            # Dramatic jump back and up (exaggeration)
            [-0.3, 0.1, 0.4, 1.0],
            
            # Hold at apex briefly
            [-0.3, 0.1, 0.4, 1.0],
            
            # Quick recoil further back
            [-0.5, 0.2, 0.6, 0.8],
            
            # Cautious posture, angled away
            [-0.4, 0.5, 1.0, 0.6],
            
            # Hesitant peek forward
            [-0.2, 0.4, 0.9, 0.4],
            
            # Small nervous movement back
            [-0.3, 0.45, 0.95, 0.5],
            
            # Slightly more confident lean forward
            [-0.1, 0.4, 0.85, 0.3],
            
            # Final return to neutral but slightly alert
            [0.0, 0.3, 0.7, 0.2]
        ]
        
        # Varied timing - fast for startle, slow for caution
        durations = [0.3, 0.2, 0.15, 0.2, 0.2, 0.6, 0.8, 0.4, 0.7, 1.0]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing startled jump animation')

def main(args=None):
    rclpy.init(args=args)
    command_interface = AnimationCommand()
    
    # Keep the node running
    rclpy.spin(command_interface)
    
    command_interface.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()