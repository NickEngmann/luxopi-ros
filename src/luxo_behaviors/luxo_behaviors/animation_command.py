#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import JointState
import time
import random
import math

class EnhancedAnimationCommand(Node):
    def __init__(self):
        super().__init__('animation_command')
        
        # Parameter to control if this node should publish joint states
        self.declare_parameter('publish_joint_states', True)
        self.should_publish = self.get_parameter('publish_joint_states').get_parameter_value().bool_value
        
        # Parameter to control which joint names to use (for hardware compatibility)
        self.declare_parameter('use_hardware_joint_names', False)
        self.use_hardware_joint_names = self.get_parameter('use_hardware_joint_names').get_parameter_value().bool_value
        
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
        self.current_positions = [0.0, 0.0, 0.0, 0.0, 3.14]  # Added gripper value
        
        # Define joint names based on the configuration
        if self.use_hardware_joint_names:
            # Hardware interface expected joint names
            self.joint_names = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
            self.get_logger().info('Using hardware joint names for RoArm compatibility')
        else:
            # URDF-based joint names
            self.joint_names = ['base_to_L1', 'L1_to_L2', 'L2_to_L3', 'L3_to_L4', 'hand']
        
        # Timer for regular publishing
        self.timer = self.create_timer(0.05, self.publish_joint_states)
        
        # Animation state
        self.is_animating = False
        self.animation_steps = []
        self.current_step = 0
        self.step_durations = []
        self.animation_timer = None
        
        # Default animation speed multiplier (1.0 = normal)
        self.speed_multiplier = 1.0
        
        # Random noise amplitude
        self.noise_amplitude = 0.05  # Small noise for subtle variability
        
        self.get_logger().info('Enhanced animation command interface initialized')
    
    def command_callback(self, msg):
        """Handle animation command messages."""
        command_parts = msg.data.strip().lower().split()
        base_command = command_parts[0]
        
        # Extract speed parameter if present
        speed = 1.0  # Default speed
        if len(command_parts) > 1:
            try:
                speed_param = float(command_parts[1])
                if 0.1 <= speed_param <= 2.0:  # Clamp speed to reasonable range
                    speed = speed_param
                    self.get_logger().info(f'Using speed multiplier: {speed}')
            except ValueError:
                self.get_logger().warn(f'Invalid speed parameter: {command_parts[1]}, using default speed')
        
        self.speed_multiplier = speed
        
        # Map of animation names to methods
        animations = {
            'curious': self.curious_look,
            'excited': self.excited_hop,
            'sad': self.sad_droop,
            'sweep': self.light_sweep,
            'playful': self.playful_bounce,
            'startled': self.startled_jump,
            'grab': self.grab_release,
            'think': self.thinking_animation,       # New animation
            'wave': self.waving_animation,          # New animation
            'dance': self.dancing_animation,        # New animation
            'stretch': self.stretching_animation,   # New animation
            'nod': self.nodding_animation,          # New animation
            'shake': self.head_shake_animation,     # New animation
            'write': self.writing_animation,        # New animation
            'random': self.random_animation,        # Plays a random animation
            'stop': self.stop_animation
        }
        
        if base_command in animations:
            self.get_logger().info(f'Executing animation: {base_command} with speed {speed}')
            animations[base_command]()
        else:
            self.get_logger().warn(f'Unknown animation command: {base_command}')
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
    
    def add_noise_to_position(self, positions):
        """Add subtle random noise to make animations less mechanical."""
        noisy_positions = []
        for pos in positions:
            noise = random.uniform(-self.noise_amplitude, self.noise_amplitude)
            noisy_positions.append(pos + noise)
        return noisy_positions
    
    def ease_in_out(self, t):
        """Cubic easing function for smoother motion."""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2
    
    def move_to_position(self, positions, duration=1.0, easing=True):
        """Move to a specific position over a duration with optional easing."""
        start_positions = self.current_positions.copy()
        start_time = time.time()
        
        # Apply speed multiplier to duration
        adjusted_duration = duration / self.speed_multiplier
        
        # Continuously update joint positions
        while time.time() - start_time < adjusted_duration:
            progress = (time.time() - start_time) / adjusted_duration
            progress = min(1.0, progress)  # Clamp to 1.0
            
            # Apply easing if requested
            if easing:
                eased_progress = self.ease_in_out(progress)
            else:
                eased_progress = progress
            
            # Linear interpolation for each joint
            for i in range(len(self.current_positions)):
                self.current_positions[i] = start_positions[i] + eased_progress * (positions[i] - start_positions[i])
            
            time.sleep(0.01)  # Small delay to prevent CPU overload
        
        # Add subtle noise to final position to make it less robotic
        self.current_positions = self.add_noise_to_position(positions)
    
    def start_animation(self, keyframes, durations):
        """Start an animation with keyframes and durations."""
        # Add subtle variations to keyframes for more natural movement
        varied_keyframes = []
        for keyframe in keyframes:
            varied_keyframe = self.add_noise_to_position(keyframe)
            varied_keyframes.append(varied_keyframe)
        
        self.animation_steps = varied_keyframes
        
        # Apply speed multiplier to durations
        adjusted_durations = [d / self.speed_multiplier for d in durations]
        self.step_durations = adjusted_durations
        
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
        
        # Determine if we should use easing for this step
        # Use easing for most steps, but occasionally skip for more dynamic motion
        use_easing = random.random() > 0.2
        
        # Move to the position
        self.get_logger().info(f'Animation step {self.current_step+1}/{len(self.animation_steps)}')
        self.move_to_position(next_position, duration, easing=use_easing)
        
        # Increment step and schedule next one
        self.current_step += 1
        if self.current_step < len(self.animation_steps):
            # Add slight random variation to timing for more natural movement
            time_variation = random.uniform(0.9, 1.1)
            # Schedule the next step using a timer
            self.animation_timer = self.create_timer(
                duration * time_variation, 
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

    # Enhanced animation methods implementing Disney animation principles
    def curious_look(self):
        """Make the arm look curiously at something with Disney animation principles."""
        # Starting from current position but with slight randomization
        start_pos = self.current_positions.copy()
        
        # Get current gripper position or use default closed position
        gripper_pos = start_pos[4] if len(start_pos) > 4 else 3.14
        
        # Calculate relative positions from current state
        base_center = start_pos[0]
        
        # Keyframe positions with enhanced Disney animation principles
        keyframes = [
            # Anticipation: slight backward movement before main action
            [base_center, start_pos[1]+0.1, start_pos[2]-0.15, start_pos[3]-0.1, gripper_pos],
            
            # Quick "notice something" movement with overshoot (exaggeration)
            [base_center-0.25, start_pos[1], start_pos[2]-0.2, -0.3, gripper_pos],
            
            # Secondary action: slight adjustment while focusing
            [base_center-0.2, 0.4, 0.9, 0.4, gripper_pos * 0.9],  # Slightly open gripper
            
            # Squash and stretch: lean in to investigate (overlapping action)
            [base_center-0.15, 0.7, 1.4, 0.6, gripper_pos * 0.8],
            
            # Follow through: quick surprised reaction with head movement
            [base_center-0.1, 0.4, 1.0, 0.9, gripper_pos * 0.7],
            
            # Arcs: move in curved path to other side (using arcs in motion)
            [base_center+0.3, 0.5, 1.1, 0.3, gripper_pos * 0.75],
            
            # More intense inspection - tilt other way (solid drawing - clear poses)
            [base_center+0.4, 0.6, 1.3, -0.3, gripper_pos * 0.8],
            
            # Slow in, slow out: final examination (timing)
            [base_center+0.2, 0.5, 1.2, 0.7, gripper_pos * 0.9],
            
            # Staging: clear final pose showing interest
            [base_center, 0.4, 0.8, 0.5, gripper_pos]
        ]
        
        # Duration for each keyframe (in seconds) - varied timing for interest
        durations = [0.3, 0.25, 0.4, 0.5, 0.2, 0.6, 0.7, 0.6, 0.8]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced curious look animation')

    def excited_hop(self):
        """Make the arm do an excited bouncy hop with Disney principles."""
        # Starting position
        base_pos = self.current_positions[0]
        
        # Get current gripper position or use default closed position
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney animation principles
        keyframes = [
            # Anticipation: crouch down before the jump
            [base_pos, 0.6, 1.1, 0.2, gripper_pos * 0.7],  # Open gripper a bit for excitement
            
            # Exaggerate squash - deeper crouch with slight angle
            [base_pos+0.1, 0.9, 1.7, -0.3, gripper_pos * 0.6],
            
            # Quick stretch - jumping up (snappy timing)
            [base_pos, 0.05, 0.5, 0.9, gripper_pos * 0.5],  # Open gripper more
            
            # Follow through - slight overshoot at top
            [base_pos-0.1, 0.0, 0.4, 1.1, gripper_pos * 0.4],
            
            # Secondary action - wiggle at apex
            [base_pos+0.2, 0.05, 0.45, 1.0, gripper_pos * 0.5],
            
            # Start coming down with anticipation
            [base_pos, 0.2, 0.6, 0.8, gripper_pos * 0.6],
            
            # Squash on impact - exaggerate landing
            [base_pos-0.1, 0.8, 1.3, 0.2, gripper_pos * 0.7],
            
            # Follow through - bounce up with overlapping action
            [base_pos+0.15, 0.3, 0.8, 0.6, gripper_pos * 0.8],
            
            # Secondary bounce with diminishing energy
            [base_pos-0.05, 0.5, 1.0, 0.4, gripper_pos * 0.9],
            
            # Settle with continued motion - slow in
            [base_pos, 0.3, 0.7, 0.5, gripper_pos]
        ]
        
        # Varied durations for more dynamic movement - quick up, slower down
        durations = [0.4, 0.3, 0.15, 0.1, 0.1, 0.2, 0.12, 0.25, 0.2, 0.4]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced excited hop animation')

    def sad_droop(self):
        """Make the arm droop down sadly with Disney principles."""
        # Get current position values
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney animation principles
        keyframes = [
            # Anticipation - slight upward movement
            [base_pos, 0.15, 0.5, 0.2, gripper_pos],
            
            # Staging - clear pose showing emotion beginning
            [base_pos-0.05, 0.25, 0.65, 0.0, gripper_pos],
            
            # Slow in - start of the droop movement
            [base_pos-0.1, 0.4, 0.8, -0.3, gripper_pos * 1.1],  # Close gripper tighter
            
            # Secondary action - slight shake (hesitation)
            [base_pos-0.15, 0.45, 0.85, -0.35, gripper_pos * 1.15],
            
            # Attempt to look up (showing character resistance)
            [base_pos-0.1, 0.35, 0.75, -0.2, gripper_pos * 1.1],
            
            # Deeper droop - giving up (exaggeration)
            [base_pos-0.2, 0.6, 1.1, -0.7, gripper_pos * 1.2],  # Even tighter grip
            
            # Squash - complete slump (solid drawing)
            [base_pos-0.25, 0.9, 1.4, -1.0, gripper_pos * 1.3],
            
            # Small movement - sigh (follow through)
            [base_pos-0.2, 0.85, 1.35, -0.95, gripper_pos * 1.25],
            
            # Another small movement (appeal - showing emotion)
            [base_pos-0.25, 0.8, 1.3, -1.05, gripper_pos * 1.3],
            
            # Very slight movement (secondary action)
            [base_pos-0.2, 0.75, 1.25, -1.0, gripper_pos * 1.25],
            
            # Long pause in sad position (timing)
            [base_pos-0.15, 0.7, 1.2, -0.9, gripper_pos * 1.2],
            
            # Very slow recovery starts (slow out)
            [base_pos-0.1, 0.6, 1.0, -0.7, gripper_pos * 1.15],
            
            # Final return to neutral with lingering effect
            [base_pos, 0.4, 0.8, -0.3, gripper_pos]
        ]
        
        # Slower, heavier durations for sadness
        durations = [0.4, 0.5, 0.6, 0.3, 0.7, 0.8, 1.0, 0.4, 0.5, 0.7, 1.5, 1.2, 1.0]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced sad droop animation')

    def light_sweep(self):
        """Make the arm sweep like searching with Disney principles."""
        # Current base position
        base_pos = self.current_positions[0]
        
        # Get current gripper position or use default closed position
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Neutral position parameters
        shoulder_neutral = 0.35
        elbow_neutral = 0.85
        wrist_up = 0.5
        wrist_down = -0.2
        
        # Keyframe positions with Disney animation principles
        keyframes = [
            # Anticipation - alert starting position
            [base_pos, shoulder_neutral, elbow_neutral, wrist_up, gripper_pos * 0.9],  # Slightly open
            
            # Quick turn to left - snappy timing
            [base_pos-0.9, shoulder_neutral, elbow_neutral, wrist_up * 0.7, gripper_pos * 0.85],
            
            # Exaggerated peek left - overlapping action in wrist
            [base_pos-1.2, shoulder_neutral+0.1, elbow_neutral+0.1, wrist_down, gripper_pos * 0.8],
            
            # Follow through - slight bounce back
            [base_pos-1.1, shoulder_neutral-0.05, elbow_neutral-0.05, wrist_down * 0.5, gripper_pos * 0.85],
            
            # Secondary action - quick look up while still on left
            [base_pos-1.0, shoulder_neutral-0.1, elbow_neutral-0.2, wrist_up * 1.4, gripper_pos * 0.8],
            
            # Arcing movement to mid-left
            [base_pos-0.6, shoulder_neutral, elbow_neutral, wrist_up * 0.9, gripper_pos * 0.85],
            
            # Quick glance down on mid-left (staging)
            [base_pos-0.5, shoulder_neutral+0.15, elbow_neutral+0.15, wrist_down, gripper_pos * 0.9],
            
            # Fast transition to center (snappy timing)
            [base_pos, shoulder_neutral-0.05, elbow_neutral-0.05, wrist_up, gripper_pos * 0.85],
            
            # Anticipation for right movement
            [base_pos+0.2, shoulder_neutral+0.05, elbow_neutral+0.05, wrist_up * 0.8, gripper_pos * 0.8],
            
            # Quick swing to mid-right (exaggeration)
            [base_pos+0.6, shoulder_neutral, elbow_neutral, wrist_up * 0.7, gripper_pos * 0.75],
            
            # Peer down mid-right with emphasis
            [base_pos+0.5, shoulder_neutral+0.15, elbow_neutral+0.15, wrist_down * 1.2, gripper_pos * 0.8],
            
            # Secondary action - double-take up
            [base_pos+0.6, shoulder_neutral-0.1, elbow_neutral-0.2, wrist_up * 1.5, gripper_pos * 0.7],
            
            # Exaggerated swing to far right (arcs)
            [base_pos+1.2, shoulder_neutral, elbow_neutral, wrist_up * 0.9, gripper_pos * 0.75],
            
            # Final check down right (solid drawing)
            [base_pos+1.1, shoulder_neutral+0.2, elbow_neutral+0.2, wrist_down, gripper_pos * 0.8],
            
            # "Found something!" reaction (appeal)
            [base_pos+0.9, shoulder_neutral-0.1, elbow_neutral-0.2, wrist_up * 1.6, gripper_pos * 0.5],  # Open wide
            
            # Secondary motion - excitement wiggle
            [base_pos+0.8, shoulder_neutral-0.15, elbow_neutral-0.25, wrist_up * 1.7, gripper_pos * 0.45],
            
            # Return to center with follow-through
            [base_pos+0.3, shoulder_neutral, elbow_neutral, wrist_up * 1.3, gripper_pos * 0.6],
            
            # Final position showing excitement
            [base_pos, shoulder_neutral-0.05, elbow_neutral-0.1, wrist_up * 1.1, gripper_pos * 0.7]
        ]
        
        # Varied durations for more lifelike searching
        durations = [0.4, 0.3, 0.5, 0.2, 0.3, 0.4, 0.5, 0.3, 0.2, 0.3, 0.5, 0.25, 0.4, 0.5, 0.2, 0.15, 0.4, 0.5]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced light sweep animation')

    def playful_bounce(self):
        """Make the arm perform a playful, energetic bounce with Disney principles."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney animation principles
        keyframes = [
            # Anticipation - slight wiggle in place
            [base_pos, 0.35, 0.8, 0.4, gripper_pos * 0.9],  # Slightly open gripper
            
            # More anticipation - opposite wiggle (build energy)
            [base_pos+0.25, 0.3, 0.75, 0.45, gripper_pos * 0.85],
            
            # Even more anticipation - swing other way
            [base_pos-0.25, 0.3, 0.75, 0.5, gripper_pos * 0.8],
            
            # Squash - deep crouch (exaggeration)
            [base_pos, 0.7, 1.4, 0.3, gripper_pos * 0.75],
            
            # Stretch - big bounce up (snappy timing)
            [base_pos, 0.05, 0.4, 0.9, gripper_pos * 0.5],  # Open gripper more
            
            # Follow through - slight overshoot at apex
            [base_pos+0.1, 0.0, 0.35, 1.0, gripper_pos * 0.45],
            
            # Secondary action - wiggle at apex
            [base_pos-0.1, 0.0, 0.35, 1.0, gripper_pos * 0.4],
            
            # Arcs - begin to fall in curved motion
            [base_pos+0.05, 0.15, 0.5, 0.8, gripper_pos * 0.45],
            
            # Squash - land with impact (exaggeration)
            [base_pos+0.15, 0.65, 1.2, 0.25, gripper_pos * 0.6],
            
            # Follow through - slight compression after landing
            [base_pos+0.2, 0.7, 1.25, 0.2, gripper_pos * 0.65],
            
            # Stretch - small bounce 1 (diminishing energy)
            [base_pos+0.3, 0.25, 0.65, 0.6, gripper_pos * 0.7],
            
            # Squash - land and crouch right
            [base_pos+0.4, 0.6, 1.15, 0.3, gripper_pos * 0.75],
            
            # Stretch - small bounce 2 with rotation (arcs)
            [base_pos-0.3, 0.2, 0.6, 0.65, gripper_pos * 0.8],
            
            # Squash - land and crouch left
            [base_pos-0.4, 0.55, 1.1, 0.25, gripper_pos * 0.85],
            
            # Stretch - final small hop to center
            [base_pos, 0.15, 0.55, 0.75, gripper_pos * 0.9],
            
            # Follow through - slight overshoot at landing
            [base_pos+0.05, 0.35, 0.75, 0.45, gripper_pos * 0.95],
            
            # Settle with continued motion - slow in
            [base_pos, 0.3, 0.7, 0.5, gripper_pos]
        ]
        
        # Energetic timing with snappy movements and pauses for emphasis
        durations = [0.3, 0.15, 0.15, 0.4, 0.15, 0.1, 0.1, 0.2, 0.1, 0.1, 0.25, 0.15, 0.25, 0.15, 0.25, 0.15, 0.4]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced playful bounce animation')

  
    def startled_jump(self):
        """Make the arm perform a startled jump with Disney principles."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney principles
        keyframes = [
            # Calm starting position
            [base_pos, 0.3, 0.7, 0.0, gripper_pos],
            
            # Freeze momentarily (anticipation) - actually just slightly tense up
            [base_pos, 0.32, 0.72, -0.05, gripper_pos * 1.1],  # Close gripper tighter
            
            # Extreme surprise reaction (exaggeration)
            [base_pos-0.4, 0.05, 0.3, 1.2, gripper_pos * 0.5],  # Open gripper in shock
            
            # Hold stretched position briefly (timing)
            [base_pos-0.45, 0.0, 0.25, 1.3, gripper_pos * 0.45],
            
            # Follow through - slight overshoot backward
            [base_pos-0.55, 0.1, 0.4, 1.1, gripper_pos * 0.5],
            
            # Secondary action - slight shake
            [base_pos-0.5, 0.15, 0.45, 1.0, gripper_pos * 0.55],
            
            # Cautious position, angled away (staging)
            [base_pos-0.45, 0.5, 1.0, 0.7, gripper_pos * 0.6],
            
            # Hesitant peek forward (appeal - showing character)
            [base_pos-0.3, 0.45, 0.95, 0.5, gripper_pos * 0.65],
            
            # Small nervous movement back (secondary action)
            [base_pos-0.35, 0.5, 1.0, 0.6, gripper_pos * 0.7],
            
            # Another hesitant peek (overlapping action)
            [base_pos-0.25, 0.4, 0.9, 0.4, gripper_pos * 0.75],
            
            # Quick nervous glance around (timing)
            [base_pos+0.1, 0.35, 0.85, 0.5, gripper_pos * 0.8],
            
            # Back to cautious position (arc motion)
            [base_pos-0.15, 0.4, 0.9, 0.45, gripper_pos * 0.85],
            
            # Slightly more confident lean forward (slow out)
            [base_pos-0.05, 0.35, 0.8, 0.35, gripper_pos * 0.9],
            
            # Final return to neutral but slightly alert (solid drawing)
            [base_pos, 0.3, 0.7, 0.25, gripper_pos * 0.95]
        ]
        
        # Varied durations for snappy startled movement followed by cautious recovery
        durations = [0.3, 0.2, 0.15, 0.2, 0.2, 0.15, 0.5, 0.6, 0.4, 0.6, 0.3, 0.5, 0.7, 0.6]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced startled jump animation')

    def grab_release(self):
        """Make the arm grab and release with the gripper using Disney principles."""
        # Starting position
        base_pos = self.current_positions[0]
        shoulder_pos = self.current_positions[1]
        elbow_pos = self.current_positions[2]
        wrist_pos = self.current_positions[3]
        
        # Keyframe positions with Disney principles
        keyframes = [
            # Anticipation - prepare to grab
            [base_pos-0.1, shoulder_pos-0.1, elbow_pos-0.1, wrist_pos+0.1, 1.57],  # Open gripper
            
            # Secondary action - slight hesitation
            [base_pos-0.05, shoulder_pos-0.05, elbow_pos-0.05, wrist_pos+0.05, 1.57],
            
            # Move down with slight arc (arcs principle)
            [base_pos, shoulder_pos+0.15, elbow_pos+0.15, wrist_pos-0.15, 1.57],
            
            # Slight adjustment (overlapping action)
            [base_pos, shoulder_pos+0.2, elbow_pos+0.2, wrist_pos-0.2, 1.57],
            
            # Close gripper with anticipation
            [base_pos, shoulder_pos+0.22, elbow_pos+0.22, wrist_pos-0.22, 2.8],  # Not fully closed yet
            
            # Complete closing (exaggeration)
            [base_pos, shoulder_pos+0.2, elbow_pos+0.2, wrist_pos-0.2, 3.14],
            
            # Slight upward movement (follow through)
            [base_pos, shoulder_pos+0.15, elbow_pos+0.15, wrist_pos-0.15, 3.14],
            
            # Move back up with slight arc
            [base_pos, shoulder_pos+0.05, elbow_pos+0.05, wrist_pos-0.05, 3.14],
            
            # Complete upward movement
            [base_pos, shoulder_pos, elbow_pos, wrist_pos, 3.14],
            
            # Move to different position with arcs
            [base_pos+0.2, shoulder_pos, elbow_pos+0.05, wrist_pos+0.1, 3.14],
            
            # Continue to new position
            [base_pos+0.3, shoulder_pos, elbow_pos, wrist_pos+0.2, 3.14],
            
            # Start moving down
            [base_pos+0.3, shoulder_pos+0.1, elbow_pos+0.1, wrist_pos+0.1, 3.14],
            
            # Complete moving down
            [base_pos+0.3, shoulder_pos+0.2, elbow_pos+0.2, wrist_pos, 3.14],
            
            # Prepare to release (anticipation)
            [base_pos+0.3, shoulder_pos+0.2, elbow_pos+0.2, wrist_pos-0.05, 3.0],
            
            # Release gripper
            [base_pos+0.3, shoulder_pos+0.2, elbow_pos+0.2, wrist_pos, 1.57],
            
            # Small bounce after release (follow through)
            [base_pos+0.3, shoulder_pos+0.18, elbow_pos+0.18, wrist_pos+0.05, 1.57],
            
            # Move back up with arc
            [base_pos+0.3, shoulder_pos+0.1, elbow_pos+0.1, wrist_pos+0.1, 1.57],
            
            # Complete moving up
            [base_pos+0.3, shoulder_pos, elbow_pos, wrist_pos+0.2, 1.57],
            
            # Start returning to original position
            [base_pos+0.15, shoulder_pos, elbow_pos, wrist_pos+0.1, 1.57],
            
            # Complete return with slight overshoot
            [base_pos-0.05, shoulder_pos, elbow_pos, wrist_pos, 1.57],
            
            # Settle to original position
            [base_pos, shoulder_pos, elbow_pos, wrist_pos, 1.57]
        ]
        
        # Varied durations for natural grabbing motion with snappy moments
        durations = [0.3, 0.2, 0.4, 0.2, 0.2, 0.3, 0.15, 0.3, 0.5, 0.4, 0.3, 0.3, 0.4, 0.2, 0.2, 0.15, 0.3, 0.5, 0.4, 0.2, 0.3]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced grab and release animation')

    def thinking_animation(self):
        """Make the arm appear to be thinking like a person pondering a question."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney animation principles
        keyframes = [
            # Initial pose - upright, alert
            [base_pos, 0.3, 0.7, 0.3, gripper_pos * 0.9],  # Slightly open gripper
            
            # Tilt "head" slightly (staging, establishing character)
            [base_pos+0.1, 0.25, 0.65, 0.5, gripper_pos * 0.85],
            
            # Secondary action - slight rotation
            [base_pos+0.15, 0.25, 0.65, 0.55, gripper_pos * 0.8],
            
            # Main thinking pose - "hand on chin" equivalent
            [base_pos+0.2, 0.35, 0.75, 0.2, gripper_pos * 0.7],
            
            # Slight downward tilt (staging)
            [base_pos+0.2, 0.4, 0.8, 0.0, gripper_pos * 0.65],
            
            # Hold in thought (timing)
            [base_pos+0.2, 0.42, 0.82, -0.05, gripper_pos * 0.65],
            
            # Small "hmm" movement (appeal)
            [base_pos+0.25, 0.4, 0.8, 0.0, gripper_pos * 0.6],
            
            # Look up slightly (as if having an idea)
            [base_pos+0.2, 0.3, 0.7, 0.3, gripper_pos * 0.6],
            
            # "Eureka" movement (exaggeration)
            [base_pos+0.1, 0.2, 0.6, 0.7, gripper_pos * 0.5],  # Open gripper more
            
            # Excited response to idea (secondary action)
            [base_pos, 0.15, 0.55, 0.8, gripper_pos * 0.45],
            
            # Quick confirmation nod (follow through)
            [base_pos, 0.25, 0.65, 0.5, gripper_pos * 0.5],
            
            # Final satisfied position
            [base_pos, 0.3, 0.7, 0.4, gripper_pos * 0.7]
        ]
        
        # Varied durations for natural thinking pattern with longer pauses
        durations = [0.5, 0.6, 0.4, 0.7, 0.6, 1.2, 0.5, 0.8, 0.4, 0.3, 0.4, 0.6]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing thinking animation')

    def waving_animation(self):
        """Make the arm wave hello/goodbye with Disney principles."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney principles
        keyframes = [
            # Anticipation - prepare to wave
            [base_pos, 0.3, 0.7, 0.2, gripper_pos * 0.7],  # Open gripper a bit
            
            # Raise arm (staging)
            [base_pos, 0.15, 0.5, 0.8, gripper_pos * 0.6],
            
            # Secondary action - slight adjustment
            [base_pos, 0.12, 0.45, 0.9, gripper_pos * 0.55],
            
            # Wave right (arc motion)
            [base_pos+0.2, 0.1, 0.4, 1.0, gripper_pos * 0.5],
            
            # Wave left with exaggeration
            [base_pos-0.25, 0.1, 0.4, 1.0, gripper_pos * 0.5],
            
            # Wave right (follow through)
            [base_pos+0.23, 0.12, 0.42, 0.95, gripper_pos * 0.5],
            
            # Wave left (overlapping action)
            [base_pos-0.22, 0.12, 0.42, 0.95, gripper_pos * 0.5],
            
            # Wave right (decreasing energy)
            [base_pos+0.18, 0.14, 0.44, 0.9, gripper_pos * 0.55],
            
            # Wave left (decreasing energy)
            [base_pos-0.15, 0.14, 0.44, 0.9, gripper_pos * 0.55],
            
            # Final small wave right
            [base_pos+0.1, 0.16, 0.46, 0.85, gripper_pos * 0.6],
            
            # Start lowering arm (slow out)
            [base_pos, 0.2, 0.5, 0.7, gripper_pos * 0.7],
            
            # Continue lowering with follow through
            [base_pos, 0.25, 0.6, 0.5, gripper_pos * 0.8],
            
            # Final position (appeal)
            [base_pos, 0.3, 0.7, 0.3, gripper_pos * 0.9]
        ]
        
        # Varied durations for waving - quick at first, then slower
        durations = [0.4, 0.5, 0.3, 0.25, 0.25, 0.25, 0.25, 0.3, 0.3, 0.3, 0.5, 0.6, 0.4]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing waving animation')

    def dancing_animation(self):
        """Make the arm perform a rhythmic dance with Disney principles."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney principles
        keyframes = [
            # Starting pose - upright, ready
            [base_pos, 0.3, 0.7, 0.3, gripper_pos * 0.8],  # Slightly open gripper
            
            # Anticipation - slight bounce down
            [base_pos, 0.4, 0.8, 0.2, gripper_pos * 0.75],
            
            # Dance move 1 - bounce up right (exaggeration)
            [base_pos+0.3, 0.15, 0.5, 0.6, gripper_pos * 0.7],
            
            # Follow through - slight overshoot
            [base_pos+0.35, 0.1, 0.45, 0.65, gripper_pos * 0.65],
            
            # Dance move 2 - bounce down right (squash)
            [base_pos+0.3, 0.5, 0.9, 0.1, gripper_pos * 0.7],
            
            # Dance move 3 - bounce up left (stretch, arcs)
            [base_pos-0.3, 0.15, 0.5, 0.6, gripper_pos * 0.65],
            
            # Follow through - slight overshoot
            [base_pos-0.35, 0.1, 0.45, 0.65, gripper_pos * 0.6],
            
            # Dance move 4 - bounce down left (squash)
            [base_pos-0.3, 0.5, 0.9, 0.1, gripper_pos * 0.65],
            
            # Dance move 5 - twist middle (secondary action)
            [base_pos, 0.3, 0.7, 0.7, gripper_pos * 0.5],  # Open gripper more
            
            # Follow through - slight twist
            [base_pos+0.1, 0.25, 0.65, 0.75, gripper_pos * 0.45],
            
            # Dance move 6 - spin right (exaggeration, arcs)
            [base_pos+0.5, 0.2, 0.6, 0.5, gripper_pos * 0.5],
            
            # Dance move 7 - spin left (exaggeration, arcs)
            [base_pos-0.5, 0.2, 0.6, 0.5, gripper_pos * 0.5],
            
            # Dance move 8 - dip down (solid drawing, staging)
            [base_pos, 0.6, 1.0, 0.0, gripper_pos * 0.6],
            
            # Dance move 9 - pop up (stretch)
            [base_pos, 0.1, 0.4, 0.9, gripper_pos * 0.5],
            
            # Dance finale - pose with style (appeal)
            [base_pos+0.2, 0.2, 0.5, 0.7, gripper_pos * 0.5],
            
            # Hold finale pose
            [base_pos+0.2, 0.2, 0.5, 0.7, gripper_pos * 0.5],
            
            # Return to neutral with style (slow in)
            [base_pos, 0.3, 0.7, 0.3, gripper_pos * 0.7]
        ]
        
        # Rhythmic durations with musical feel
        durations = [0.4, 0.3, 0.4, 0.2, 0.4, 0.4, 0.2, 0.4, 0.4, 0.2, 0.5, 0.5, 0.4, 0.3, 0.2, 0.6, 0.7]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing dancing animation')

    def stretching_animation(self):
        """Make the arm perform a satisfying stretch with Disney principles."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney principles
        keyframes = [
            # Starting position - slightly hunched
            [base_pos, 0.4, 0.9, 0.1, gripper_pos * 1.1],  # Closed gripper
            
            # Initial small stretch up (anticipation)
            [base_pos, 0.35, 0.85, 0.2, gripper_pos * 1.05],
            
            # Slight contraction (more anticipation)
            [base_pos, 0.45, 0.95, 0.0, gripper_pos * 1.1],
            
            # Begin big stretch (stretch principle)
            [base_pos, 0.25, 0.6, 0.4, gripper_pos * 0.9],  # Start opening gripper
            
            # Continue stretch upward with tilt (exaggeration)
            [base_pos+0.2, 0.15, 0.4, 0.7, gripper_pos * 0.7],
            
            # Maximum stretch with twist (solid drawing, appeal)
            [base_pos+0.3, 0.05, 0.3, 1.0, gripper_pos * 0.5],  # Widely open gripper
            
            # Hold stretch at apex (timing)
            [base_pos+0.3, 0.05, 0.3, 1.0, gripper_pos * 0.5],
            
            # Stretch to other side (secondary action, arcs)
            [base_pos-0.3, 0.05, 0.3, 1.0, gripper_pos * 0.5],
            
            # Hold other side stretch
            [base_pos-0.3, 0.05, 0.3, 1.0, gripper_pos * 0.5],
            
            # Start relaxing (slow out)
            [base_pos-0.2, 0.15, 0.4, 0.8, gripper_pos * 0.6],
            
            # Continue relaxing (follow through)
            [base_pos, 0.25, 0.6, 0.5, gripper_pos * 0.7],
            
            # Small bounce in relaxation (overlapping action)
            [base_pos, 0.3, 0.7, 0.4, gripper_pos * 0.8],
            
            # Final settled position with satisfaction
            [base_pos, 0.35, 0.8, 0.3, gripper_pos * 0.9]
        ]
        
        # Durations for stretching - slow extend, hold, then relax
        durations = [0.4, 0.3, 0.5, 0.6, 0.7, 0.8, 1.0, 0.8, 1.0, 0.7, 0.6, 0.4, 0.5]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing stretching animation')

    def nodding_animation(self):
        """Make the arm nod yes with Disney principles."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney principles
        keyframes = [
            # Starting pose - neutral, upright
            [base_pos, 0.3, 0.7, 0.3, gripper_pos],
            
            # First nod down - anticipation
            [base_pos, 0.35, 0.8, 0.0, gripper_pos],
            
            # First nod up - with slight overshoot (exaggeration)
            [base_pos, 0.25, 0.6, 0.5, gripper_pos],
            
            # Second nod down - stronger (squash)
            [base_pos, 0.4, 0.85, -0.1, gripper_pos],
            
            # Second nod up - not as high (follow through, diminishing energy)
            [base_pos, 0.27, 0.65, 0.4, gripper_pos],
            
            # Third nod down - smaller (overlapping action)
            [base_pos, 0.35, 0.75, 0.1, gripper_pos],
            
            # Third nod up - smaller (follow through)
            [base_pos, 0.28, 0.68, 0.35, gripper_pos],
            
            # Final tiny nod down - smallest (appeal)
            [base_pos, 0.32, 0.72, 0.25, gripper_pos],
            
            # Return to neutral with slight satisfaction (solid drawing)
            [base_pos, 0.3, 0.7, 0.3, gripper_pos]
        ]
        
        # Durations for nodding - quick down, slower up
        durations = [0.3, 0.4, 0.3, 0.4, 0.25, 0.35, 0.2, 0.25, 0.4]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing nodding animation')

    def head_shake_animation(self):
        """Make the arm shake 'no' with Disney principles."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney principles
        keyframes = [
            # Starting pose - neutral, upright
            [base_pos, 0.3, 0.7, 0.3, gripper_pos],
            
            # Initial anticipation - slight rotation opposite first shake
            [base_pos-0.1, 0.3, 0.7, 0.3, gripper_pos * 1.05],  # Slight gripper close
            
            # First shake right - exaggeration
            [base_pos+0.3, 0.3, 0.7, 0.35, gripper_pos * 1.1],
            
            # First shake left - overshoot (follow through)
            [base_pos-0.35, 0.3, 0.7, 0.35, gripper_pos * 1.1],
            
            # Second shake right - not as far (diminishing energy)
            [base_pos+0.25, 0.3, 0.7, 0.32, gripper_pos * 1.05],
            
            # Second shake left - not as far (timing)
            [base_pos-0.3, 0.3, 0.7, 0.32, gripper_pos * 1.05],
            
            # Third shake right - smaller (overlapping action)
            [base_pos+0.2, 0.3, 0.7, 0.3, gripper_pos * 1.02],
            
            # Third shake left - smaller (solid drawing)
            [base_pos-0.2, 0.3, 0.7, 0.3, gripper_pos * 1.02],
            
            # Final tiny shake right - smallest (appeal)
            [base_pos+0.1, 0.3, 0.7, 0.3, gripper_pos * 1.01],
            
            # Final tiny shake left - smallest
            [base_pos-0.1, 0.3, 0.7, 0.3, gripper_pos * 1.01],
            
            # Return to neutral with slight attitude (staging)
            [base_pos, 0.32, 0.72, 0.28, gripper_pos]
        ]
        
        # Durations for head shaking - snappy side to side
        durations = [0.3, 0.2, 0.25, 0.25, 0.25, 0.25, 0.2, 0.2, 0.15, 0.15, 0.4]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing head shake animation')

    def writing_animation(self):
        """Make the arm appear to write something with Disney principles."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Set up neutral positions for writing
        shoulder_neutral = 0.5  # Lower arm position for writing
        elbow_neutral = 1.0
        wrist_neutral = 0.0
        
        # Keyframe positions with Disney principles
        keyframes = [
            # Initial pose - prepare to write (staging)
            [base_pos, 0.3, 0.7, 0.3, gripper_pos * 0.75],  # Slightly open gripper as if holding a pen
            
            # Move down to writing surface (anticipation)
            [base_pos, shoulder_neutral+0.05, elbow_neutral+0.05, wrist_neutral, gripper_pos * 0.75],
            
            # Position to start writing (solid drawing)
            [base_pos-0.2, shoulder_neutral, elbow_neutral, wrist_neutral, gripper_pos * 0.75],
            
            # First stroke right (arcs, appeal)
            [base_pos+0.2, shoulder_neutral, elbow_neutral, wrist_neutral-0.05, gripper_pos * 0.75],
            
            # Lift slightly for next letter (secondary action)
            [base_pos+0.2, shoulder_neutral-0.05, elbow_neutral-0.05, wrist_neutral+0.1, gripper_pos * 0.75],
            
            # Move back left (overlapping action)
            [base_pos, shoulder_neutral, elbow_neutral, wrist_neutral, gripper_pos * 0.75],
            
            # Second stroke - curved motion (arcs)
            [base_pos+0.1, shoulder_neutral+0.05, elbow_neutral+0.05, wrist_neutral-0.1, gripper_pos * 0.75],
            
            # Continue curved motion
            [base_pos+0.15, shoulder_neutral+0.07, elbow_neutral+0.07, wrist_neutral-0.15, gripper_pos * 0.75],
            
            # Complete curved motion
            [base_pos+0.05, shoulder_neutral+0.08, elbow_neutral+0.08, wrist_neutral-0.2, gripper_pos * 0.75],
            
            # Move to next letter position (follow through)
            [base_pos-0.1, shoulder_neutral-0.05, elbow_neutral-0.05, wrist_neutral+0.1, gripper_pos * 0.75],
            
            # Down stroke (exaggeration)
            [base_pos-0.1, shoulder_neutral+0.1, elbow_neutral+0.1, wrist_neutral-0.2, gripper_pos * 0.75],
            
            # Cross stroke (timing)
            [base_pos+0.1, shoulder_neutral+0.08, elbow_neutral+0.08, wrist_neutral-0.15, gripper_pos * 0.75],
            
            # Final dot motion (appeal)
            [base_pos+0.15, shoulder_neutral+0.05, elbow_neutral+0.05, wrist_neutral-0.1, gripper_pos * 0.75],
            
            # Tap for dot (squash)
            [base_pos+0.15, shoulder_neutral+0.12, elbow_neutral+0.12, wrist_neutral-0.25, gripper_pos * 0.75],
            
            # Lift up after writing (stretch)
            [base_pos+0.1, shoulder_neutral-0.1, elbow_neutral-0.1, wrist_neutral+0.3, gripper_pos * 0.75],
            
            # Look at work - tilt (secondary action)
            [base_pos, 0.25, 0.6, 0.4, gripper_pos * 0.75],
            
            # Return to neutral with satisfaction
            [base_pos, 0.3, 0.7, 0.3, gripper_pos * 0.8]
        ]
        
        # Varied durations for writing with appropriate pauses
        durations = [0.5, 0.6, 0.4, 0.7, 0.3, 0.5, 0.4, 0.3, 0.4, 0.3, 0.5, 0.4, 0.3, 0.2, 0.5, 0.8, 0.6]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing writing animation')

    def random_animation(self):
        """Play a random animation from the available set."""
        # List of all animations except 'random' and 'stop'
        animations = [
            self.curious_look,
            self.excited_hop,
            self.sad_droop,
            self.light_sweep,
            self.playful_bounce,
            self.startled_jump,
            self.grab_release,
            self.thinking_animation,
            self.waving_animation,
            self.dancing_animation,
            self.stretching_animation,
            self.nodding_animation,
            self.head_shake_animation,
            self.writing_animation
        ]
        
        # Pick a random animation
        chosen_animation = random.choice(animations)
        
        # Execute it
        self.get_logger().info(f'Executing random animation: {chosen_animation.__name__}')
        chosen_animation()


def main(args=None):
    rclpy.init(args=args)
    command_interface = EnhancedAnimationCommand()
    
    # Keep the node running
    rclpy.spin(command_interface)
    
    command_interface.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
