#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import JointState
import time
import random
import json

class EnhancedAnimationCommand(Node):
    def __init__(self):
        super().__init__('animation_command')
        
        # Parameter to control if this node should publish joint states
        self.declare_parameter('publish_joint_states_target', True)
        self.should_publish = self.get_parameter('publish_joint_states_target').get_parameter_value().bool_value
        
        # Parameter to control which joint names to use (for hardware compatibility)
        self.declare_parameter('use_hardware_joint_names', False)
        self.use_hardware_joint_names = self.get_parameter('use_hardware_joint_names').get_parameter_value().bool_value
        
        # Parameter to control which topic to publish to (hardware vs simulation)
        self.declare_parameter('publish_target_topic', False)
        self.publish_target = self.get_parameter('publish_target_topic').get_parameter_value().bool_value
        
        # Add joint limits configuration
        self.joint_limits = {
            'L1_to_L2': {'min': -1.57, 'max': 0.75},  # Limit L1_to_L2 to max +0.75
            # Add other joint limits here if needed
        }
        
        self.declare_parameter('enforce_joint_limits', True)
        self.enforce_joint_limits = self.get_parameter('enforce_joint_limits').value
        
        # Add parameter to control if we should use hardware position feedback
        self.declare_parameter('use_hardware_position_feedback', False)
        self.use_hardware_position_feedback = self.get_parameter('use_hardware_position_feedback').get_parameter_value().bool_value
        
        # Hardware position feedback
        self.hardware_position_received = False
        
        # Create subscription for hardware position feedback
        if self.use_hardware_position_feedback:
            self.position_subscription = self.create_subscription(
                String, 
                'roarm/position',
                self.position_feedback_callback,
                10)
            self.get_logger().info('Subscribed to roarm/position for hardware feedback')
        
        # Create subscription for animation commands
        self.command_subscription = self.create_subscription(
            String,
            '/roarm/animation_command',
            self.command_callback,
            10)
        
        # Create publisher for joint states (topic depends on hardware vs simulation)
        joint_topic = '/joint_states_target' if self.publish_target else '/joint_states'
        self.joint_publisher = self.create_publisher(
            JointState, 
            joint_topic,
            10)
        
        self.get_logger().info(f'Publishing joint states to: {joint_topic}')

        # Current joint positions (will be updated from hardware if available)
        self.current_positions = [0.0, 0.0, 0.0, 0.0, 3.14]  # Added gripper value
        
        # Target positions to publish (separate from current hardware positions)
        self.target_positions = self.current_positions.copy()
        
        # Define joint names based on the configuration
        if self.use_hardware_joint_names:
            # Hardware interface expected joint names
            self.joint_names = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
            self.get_logger().info('Using hardware joint names for RoArm compatibility')
        else:
            # URDF-based joint names
            self.joint_names = ['base_to_L1', 'L1_to_L2', 'L2_to_L3', 'L3_to_L4', 'hand']
        
        # Timer for regular publishing
        self.timer = self.create_timer(0.25, self.publish_joint_states_target)
        
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
        
        # Maximum attempts to get hardware position before timing out
        self.max_position_attempts = 10
        self.position_request_interval = 0.5  # seconds
        
        self.get_logger().info('Enhanced animation command interface initialized')
        
        # Initialize hardware position if enabled
        if self.use_hardware_position_feedback:
            self.request_hardware_position()

    def position_feedback_callback(self, msg):
        """Handle position feedback from the hardware."""
        try:
            # Parse the list from the message
            position_list = json.loads(msg.data)
            
            # Check if this is a valid position list with at least 5 elements
            if isinstance(position_list, list) and len(position_list) >= 5:
                # Add occasional debug logging to understand what's happening
                should_log = not hasattr(self, '_last_debug_time') or \
                            time.time() - self._last_debug_time > 5.0
                
                if should_log:
                    self._last_debug_time = time.time()
                    
                # First time receiving position or no current positions yet
                if self.current_positions is None:
                    # First reading, use as is
                    self.current_positions = position_list.copy()
                    if should_log:
                        self.get_logger().info(f"Initial position reading: {position_list}")
                else:
                    # Calculate differences between new position and current saved positions
                    diff_report = []
                    has_significant_change = False
                    tolerance = 0.03  # radians
                    
                    # Create filtered position list starting with raw values
                    filtered_position_list = position_list.copy()
                    
                    for i in range(min(len(position_list), len(self.current_positions))):
                        # Calculate difference between current raw reading and current saved position
                        diff = abs(float(position_list[i]) - float(self.current_positions[i]))
                        
                        if should_log:
                            diff_report.append(f"{i}: {diff:.4f}")
                        
                        # Check if difference exceeds tolerance
                        if diff >= tolerance:
                            has_significant_change = True
                        else:
                            # Only for positions within tolerance, keep current value
                            filtered_position_list[i] = self.current_positions[i]
                    
                    if should_log:
                        self.get_logger().debug(f"Position differences: {', '.join(diff_report)}")
                        self.get_logger().debug(f"Raw: {position_list}")
                        self.get_logger().debug(f"Filtered: {filtered_position_list}")
                        self.get_logger().debug(f"Current positions: {self.current_positions}")
                        self.get_logger().debug(f"Has significant change: {has_significant_change}")
                    
                    # Update current positions with filtered values
                    self.current_positions = filtered_position_list
                # Only update target positions when not animating to avoid disrupting animations
                if not self.is_animating:
                    self.target_positions = self.current_positions.copy()
                
                # Mark that we've received hardware position
                self.hardware_position_received = True
                
                # Log occasionally to prevent flooding
                if not hasattr(self, '_last_position_log_time') or \
                    time.time() - self._last_position_log_time > 5.0:
                        self.get_logger().debug(f"Hardware position updated: " +
                                            f"base={self.current_positions[0]:.2f}, " +
                                            f"shoulder={self.current_positions[1]:.2f}, " +
                                            f"elbow={self.current_positions[2]:.2f}, " +
                                            f"wrist={self.current_positions[3]:.2f}, " +
                                            f"hand={self.current_positions[4]:.2f}")
                        self._last_position_log_time = time.time()
        
        except (json.JSONDecodeError, ValueError) as e:
            self.get_logger().error(f"Error parsing position feedback: {e}")
        except Exception as e:
            self.get_logger().error(f"Error in position feedback callback: {e}")
    
    def request_hardware_position(self):
        """Request and wait for hardware position before proceeding."""
        if not self.use_hardware_position_feedback:
            return True  # Not using hardware feedback
            
        self.get_logger().info("Waiting for initial hardware position...")
        
        attempts = 0
        self.hardware_position_received = False
        
        # Wait for position feedback with timeout
        while attempts < self.max_position_attempts and not self.hardware_position_received:
            time.sleep(self.position_request_interval)
            attempts += 1
            self.get_logger().debug(f"Waiting for position feedback ({attempts}/{self.max_position_attempts})")
            
        if self.hardware_position_received:
            self.get_logger().info("Hardware position received, ready for animations")
            return True
        else:
            self.get_logger().warn("Failed to get hardware position after timeout, using default positions")
            return False
    
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
        
        # If using hardware, ensure we have the latest position before starting animation
        if self.use_hardware_position_feedback and not self.hardware_position_received:
            self.get_logger().info("Getting hardware position before starting animation...")
            self.request_hardware_position()

        # Map of animation names to methods
        animations = {
            'excited': self.excited_hop,
            'playful': self.playful_bounce,
            'dance': self.dancing_animation, 
            'sad': self.sad_droop,
            'think': self.thinking_animation, 
            'idle': self.idle_state,
            'curious': self.curious_look,
            'stretch': self.stretching_animation,   
            'nod': self.nodding_animation,          
            'shake': self.head_shake_animation,
            'startled': self.startled_jump,          
            'stop': self.stop_animation
        }
        
        if base_command in animations:
            self.get_logger().info(f'Executing animation: {base_command} with speed {speed}')
            animations[base_command]()
        else:
            self.get_logger().warn(f'Unknown animation command: {base_command}')
            self.get_logger().info(f'Available commands: {", ".join(animations.keys())}')
    
    def publish_joint_states_target(self):
        """Publish target joint states."""
        if not self.should_publish:
            return
        
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self.joint_names
        
        # Ensure all position values are valid floats
        try:
            # Make a copy and ensure all elements are floats
            validated_positions = [float(pos) for pos in self.target_positions]
            
            # Apply joint limits before publishing
            if self.enforce_joint_limits:
                validated_positions = self.apply_joint_limits(msg.name, validated_positions)
            
            # Assign the validated positions to the message
            msg.position = validated_positions
            
            self.joint_publisher.publish(msg)
        except (ValueError, TypeError) as e:
            self.get_logger().error(f"Invalid position value in target_positions: {self.target_positions}")
            self.get_logger().error(f"Error details: {e}")
            
            # Attempt to recover by using the last known good positions or zeros
            if hasattr(self, 'last_valid_positions') and self.last_valid_positions:
                self.get_logger().warn("Using last valid positions as fallback")
                msg.position = self.last_valid_positions
                self.joint_publisher.publish(msg)
            else:
                self.get_logger().warn("No valid positions available, using zeros")
                msg.position = [0.0] * len(msg.name)
                self.joint_publisher.publish(msg)
        else:
            # If successful, store these as the last valid positions
            self.last_valid_positions = validated_positions.copy()
    
    def apply_joint_limits(self, joint_names, joint_positions):
        """Apply joint limits to the given positions and return the corrected values."""
        limited_positions = list(joint_positions)  # Create a copy to modify
        
        for i, name in enumerate(joint_names):
            if name in self.joint_limits:
                limits = self.joint_limits[name]
                original_value = joint_positions[i]
                
                # Apply min limit
                if original_value < limits['min']:
                    limited_positions[i] = limits['min']
                    self.get_logger().debug(f"Limited {name} from {original_value:.3f} to min {limits['min']:.3f}")
                
                # Apply max limit
                elif original_value > limits['max']:
                    limited_positions[i] = limits['max']
                    self.get_logger().warn(f"Limited {name} from {original_value:.3f} to max {limits['max']:.3f}")
                    
        return limited_positions
    
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
        start_positions = self.target_positions.copy()  # Start from current target positions
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
            for i in range(len(self.target_positions)):
                self.target_positions[i] = start_positions[i] + eased_progress * (positions[i] - start_positions[i])
            
            time.sleep(0.01)  # Small delay to prevent CPU overload
        
        # Add subtle noise to final position to make it less robotic
        self.target_positions = self.add_noise_to_position(positions)
        
        # Return success status
        return True

    def start_animation(self, keyframes, durations):
        """Start an animation with keyframes and durations."""
        # If we have hardware feedback, make sure we start from current position
        if self.use_hardware_position_feedback and self.hardware_position_received:
            # Adjust the first keyframe to be relative to the current position
            # This helps animations blend from whatever position the arm is actually in
            if len(keyframes) > 0:
                self.get_logger().debug("Adjusting animation to start from current hardware position")
                
                # Create a modified first keyframe that's a blend between 
                # the intended first keyframe and the current position
                first_keyframe = keyframes[0].copy()
                
                # Use current hardware position but keep the intended relative movements
                # This preserves the "character" of the animation while respecting actual position
                for i in range(min(len(first_keyframe), len(self.current_positions))):
                    # Get the difference between original starting point and the intended position
                    intended_offset = first_keyframe[i] - self.target_positions[i]
                    # Scale down the offset to create a smoother transition
                    scaled_offset = intended_offset * 0.5
                    # Apply this scaled offset to the current position
                    first_keyframe[i] = self.current_positions[i] + scaled_offset
                
                # Replace the first keyframe with our adjusted version
                keyframes[0] = first_keyframe
                
                # Also update target positions to match current positions before starting animation
                self.target_positions = self.current_positions.copy()
        
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
        
        # Check if destination is significantly different from current position
        # This helps detect if collisions or escape maneuvers have moved us far from expected
        if self.current_step > 0 and hasattr(self, 'previous_position'):
            # Get our current position
            curr_pos = self.current_positions
            expected_pos = self.previous_position
            
            # Calculate difference 
            diff_magnitude = sum([(curr - expected)**2 for curr, expected in zip(curr_pos, expected_pos)])
            if diff_magnitude > 1.0:  # Significant deviation
                self.get_logger().warn(f"Detected significant position deviation (mag={diff_magnitude:.2f}) - " +
                                      f"current: {[round(p, 2) for p in curr_pos]}, " +
                                      f"expected: {[round(p, 2) for p in expected_pos]}")
                
                # Adjust timing to be a bit slower after deviation to allow for smoother recovery
                duration = duration * 1.5
                self.get_logger().info(f"Increasing move duration to {duration:.2f}s for smoother recovery")
        
        # Try to move to the position
        self.move_to_position(next_position, duration, easing=use_easing)
        
        # Remember this target position for next comparison
        self.previous_position = next_position
        
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
            # Initial excited wiggle (anticipation)
            [base_pos+0.2, 0.35, 0.7, 0.3, gripper_pos * 0.8],  # Open gripper for excitement
            
            # Opposite wiggle (building energy)
            [base_pos-0.2, 0.32, 0.68, 0.35, gripper_pos * 0.7], 
            
            # Final anticipation - crouch down deeply before jump
            [base_pos, 0.7, 1.3, 0.0, gripper_pos * 0.6],
            
            # Exaggerate squash - compress even more with slight angle
            [base_pos+0.1, 1.0, 1.8, -0.3, gripper_pos * 0.5],
            
            # Begin compact fold (extreme squash)
            [base_pos, -1.0, 1.0, 0.0, gripper_pos * 0.5],
            
            # Maximum compression - compact fold for powerful jump
            [base_pos, -2.0, 2.0, 2.0, gripper_pos * 0.45],  
            
            # Explosive release - extremely quick stretch upward
            [base_pos, 0.0, 0.3, 1.0, gripper_pos * 0.4],
            
            # Maximum extension at apex (extreme stretch)
            [base_pos, -0.3, 0.1, 1.4, gripper_pos * 0.3],  # Wide open gripper
            
            # Follow through - dramatic overshoot at top
            [base_pos-0.2, -0.4, 0.0, 1.6, gripper_pos * 0.25],
            
            # Secondary action - excited wiggle at apex
            [base_pos+0.3, -0.35, 0.05, 1.5, gripper_pos * 0.3],
            
            # Second wiggle (overlapping action)
            [base_pos-0.25, -0.35, 0.05, 1.5, gripper_pos * 0.35],
            
            # Start descent with anticipation
            [base_pos, -0.1, 0.3, 1.2, gripper_pos * 0.4],
            
            # Continue descent with arcing motion
            [base_pos+0.2, 0.2, 0.6, 0.8, gripper_pos * 0.5],
            
            # Dramatic squash on impact - exaggerate landing
            [base_pos+0.1, 0.75, 1.7, 0.0, gripper_pos * 0.6],
            
            # Compression at landing - absorb energy
            [base_pos, 0.75, 1.8, -0.2, gripper_pos * 0.65],
            
            # Secondary bounce preparation - small anticipation
            [base_pos-0.1, 0.75, 1.5, 0.1, gripper_pos * 0.7],
            
            # Secondary smaller bounce - reduced height
            [base_pos-0.05, 0.2, 0.6, 0.8, gripper_pos * 0.75],
            
            # Small apex on second bounce
            [base_pos+0.1, 0.15, 0.5, 0.9, gripper_pos * 0.7],
            
            # Second landing - less dramatic
            [base_pos+0.15, 0.6, 1.2, 0.3, gripper_pos * 0.8],
            
            # Mini-fold for final bounce
            [base_pos, 0.5, 1.0, 0.4, gripper_pos * 0.85],
            
            # Final tiny hop
            [base_pos-0.05, 0.3, 0.8, 0.6, gripper_pos * 0.9],
            
            # Settle with continued motion - follow through
            [base_pos+0.05, 0.35, 0.75, 0.5, gripper_pos * 0.95],
            
            # Final satisfied position - slight anticipation for next action
            [base_pos, 0.3, 0.7, 0.5, gripper_pos * 0.9]
        ]
        
        # Varied durations for more dynamic movement
        # Extremely quick for explosive moments, longer for anticipation and recovery
        durations = [
            0.2,  # Initial wiggle
            0.2,  # Opposite wiggle
            0.3,  # Crouch down
            0.25, # Deeper crouch
            0.2,  # Begin compact fold
            0.3,  # Maximum compression
            0.1,  # Explosive release (extremely quick!)
            0.08, # Maximum extension
            0.08, # Overshoot at top
            0.1,  # Excited wiggle
            0.1,  # Second wiggle
            0.15, # Start descent
            0.15, # Continue descent
            0.1,  # Impact landing
            0.15, # Compression
            0.2,  # Secondary bounce preparation
            0.15, # Secondary bounce up
            0.1,  # Small apex
            0.15, # Second landing
            0.12, # Final tiny bounce prep
            0.1,  # Final tiny hop
            0.2,  # Settling
            0.3   # Final position
        ]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced dynamic excited hop animation')

    def idle_state(self):
        """Make the arm return to its idle state with slight variation, then look around briefly."""
        # Starting from current position
        base_pos = self.current_positions[0]
        shoulder_pos = self.current_positions[1]
        elbow_pos = self.current_positions[2]
        wrist_pos = self.current_positions[3]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Add subtle variations to idle state target
        target_base = base_pos + random.uniform(-0.1, 0.1)
        target_shoulder = shoulder_pos + random.uniform(-0.15, 0.15)
        target_elbow = elbow_pos + random.uniform(-0.1, 0.1)
        target_wrist = wrist_pos + random.uniform(-0.2, 0.2)
        target_gripper = gripper_pos + random.uniform(-0.1, 0.1)
        
        # Random amounts to look left and right (different values)
        look_right_amount = random.uniform(0.2, 0.4)
        look_left_amount = random.uniform(0.2, 0.5)  # Potentially more to the left
        
        # Keyframe positions - first go to idle position, then look around
        keyframes = [
            # First transition to the idle position with variation
            [target_base, target_shoulder, target_elbow, target_wrist, target_gripper],
            
            # Brief pause in idle position
            [target_base, target_shoulder, target_elbow, target_wrist, target_gripper],
            
            # Look right with random amount
            [target_base + look_right_amount, target_shoulder, target_elbow, target_wrist, target_gripper],
            
            # Look back to center
            [target_base, target_shoulder, target_elbow, target_wrist, target_gripper],
            
            # Look left with different random amount
            [target_base - look_left_amount, target_shoulder, target_elbow, target_wrist, target_gripper],
            
            # Return to idle position with slight variation
            [target_base + random.uniform(-0.05, 0.05), target_shoulder, target_elbow, target_wrist, target_gripper]
        ]
    
        # Duration for each keyframe (in seconds) - longer for initial positioning, quicker for looking around
        durations = [1.0, 0.7, 0.5, 0.4, 0.5, 0.6]
    
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing idle animation: using current position as base with slight variations')

    def sad_droop(self):
        """Make the arm droop down sadly with Disney principles."""
        # Get current position values
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney animation principles
        keyframes = [
            # Anticipation - slight upward movement showing initial energy
            [base_pos, 0.15, 0.5, 0.2, gripper_pos],
            
            # Staging - brief moment of realization 
            [base_pos-0.05, 0.25, 0.65, 0.0, gripper_pos],
            
            # Slow in - start of the droop movement
            [base_pos-0.1, 0.4, 0.8, -0.3, gripper_pos * 1.1],  # Close gripper tighter
            
            # Secondary action - slight shake (hesitation)
            [base_pos-0.15, 0.45, 0.85, -0.35, gripper_pos * 1.15],
            
            # Attempt to look up (showing character resistance)
            [base_pos-0.1, 0.35, 0.75, -0.2, gripper_pos * 1.1],
            
            # Begin folding - giving up (exaggeration and emotional staging)
            [base_pos-0.2, 0.6, 1.1, -0.7, gripper_pos * 1.2],  # Even tighter grip
            
            # Heavy droop - more dramatic folding
            [base_pos-0.25, 0.9, 1.6, -0.9, gripper_pos * 1.25],
            
            # Full slump - extreme folding position (staging the emotion)
            [base_pos-0.3, -1.0, 1.5, -0.8, gripper_pos * 1.3],
            
            # Even more compression - collapsing with weight of sadness
            [base_pos-0.35, -1.5, 1.8, 0.0, gripper_pos * 1.35],
            
            # Maximum sad position - full compact fold (extreme squash)
            [base_pos-0.4, -2.0, 2.0, 1.0, gripper_pos * 1.4],
            
            # Small movement - deep sigh (follow through)
            [base_pos-0.35, -1.9, 1.9, 1.1, gripper_pos * 1.35],
            
            # Another small movement (appeal - showing emotion)
            [base_pos-0.4, -2.0, 2.0, 1.0, gripper_pos * 1.4],
            
            # Very slight movement (secondary action - slight trembling)
            [base_pos-0.38, -1.95, 1.95, 0.95, gripper_pos * 1.38],
            
            # Long pause in sad position (timing - dwelling in emotion)
            [base_pos-0.4, -2.0, 2.0, 1.0, gripper_pos * 1.4],
            
            # Very slow recovery starts (slow out - reluctant to move)
            [base_pos-0.35, -1.5, 1.7, 0.5, gripper_pos * 1.3],
            
            # Continue slow recovery - still low energy
            [base_pos-0.3, -1.0, 1.5, 0.0, gripper_pos * 1.25],
            
            # Still drooping but less extreme
            [base_pos-0.2, -0.5, 1.2, -0.5, gripper_pos * 1.2],
            
            # Final return to neutral with lingering effect (emotional follow-through)
            [base_pos-0.1, 0.2, 0.9, -0.5, gripper_pos * 1.15],
            
            # Settling into resigned position
            [base_pos, 0.4, 0.8, -0.3, gripper_pos]
        ]
        
        # Slower, heavier durations for sadness - long pauses and slow movements
        durations = [
            0.4,  # Initial moment
            0.5,  # Realization
            0.6,  # Start drooping
            0.3,  # Hesitation
            0.7,  # Resistance attempt
            0.8,  # Giving up 
            0.9,  # Heavy droop
            1.0,  # Full slump
            1.0,  # More compression
            1.2,  # Maximum sad position
            0.6,  # Deep sigh
            0.5,  # Small movement
            0.7,  # Trembling
            2.0,  # Long emotional pause
            1.5,  # Very slow recovery starts
            1.3,  # Continue recovery
            1.2,  # Still drooping
            1.0,  # Final return movement
            1.0   # Settling
        ]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced emotional sad droop animation')


    def playful_bounce(self):
        """Make the arm perform a playful, energetic bounce with Disney principles."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney animation principles
        keyframes = [
            # Initial pose - slight anticipation wiggle
            [base_pos, 0.35, 0.8, 0.4, gripper_pos * 0.9],  # Slightly open gripper
            
            # More anticipation - opposite wiggle (build energy)
            [base_pos+0.25, 0.3, 0.75, 0.45, gripper_pos * 0.85],
            
            # Even more anticipation - swing other way
            [base_pos-0.25, 0.3, 0.75, 0.5, gripper_pos * 0.8],
            
            # Deeper anticipation - start folding back (extreme squash)
            [base_pos, -1.0, 1.0, 0.0, gripper_pos * 0.7],
            
            # Maximum compression - compact fold (extreme squash)
            [base_pos, -2.0, 2.0, 2.0, gripper_pos * 0.6],  # Using your sitting position 3
            
            # Hold compact state briefly (timing - building anticipation)
            [base_pos, -2.0, 2.0, 1.8, gripper_pos * 0.55],
            
            # Explosive release - big bounce up (extreme stretch)
            [base_pos, 0.0, 0.2, 1.2, gripper_pos * 0.4],  # Open gripper more
            
            # Maximum extension at apex (exaggeration)
            [base_pos, -0.2, 0.1, 1.5, gripper_pos * 0.35],
            
            # Follow through - slight overshoot at apex
            [base_pos+0.2, -0.1, 0.1, 1.6, gripper_pos * 0.3],
            
            # Secondary action - joyful wiggle at apex
            [base_pos-0.2, -0.1, 0.1, 1.5, gripper_pos * 0.3],
            
            # Begin to fall in curved motion (arcs)
            [base_pos+0.1, 0.2, 0.4, 0.9, gripper_pos * 0.4],
            
            # Squash - land with dramatic impact
            [base_pos+0.2, 0.8, 1.5, 0.1, gripper_pos * 0.5],
            
            # Follow through - compression after landing
            [base_pos+0.3, 0.9, 1.6, 0.0, gripper_pos * 0.55],
            
            # Prepare for second bounce - fold back again
            [base_pos+0.2, -1.0, 1.0, 0.5, gripper_pos * 0.6],
            
            # Second compact fold - not as extreme
            [base_pos+0.1, -1.8, 1.8, 1.5, gripper_pos * 0.65],
            
            # Second bounce - smaller height (diminishing energy)
            [base_pos-0.3, 0.1, 0.4, 0.9, gripper_pos * 0.7],
            
            # Secondary action at second apex
            [base_pos-0.4, 0.05, 0.35, 1.0, gripper_pos * 0.65],
            
            # Second landing with less impact
            [base_pos-0.5, 0.7, 1.3, 0.2, gripper_pos * 0.75],
            
            # Mini-fold for final bounce
            [base_pos-0.3, -0.5, 1.0, 1.0, gripper_pos * 0.8],
            
            # Final small hop toward center
            [base_pos, 0.15, 0.5, 0.8, gripper_pos * 0.85],
            
            # Follow through - slight overshoot at landing
            [base_pos+0.05, 0.4, 0.85, 0.45, gripper_pos * 0.9],
            
            # Settle with continued motion - slow in
            [base_pos, 0.3, 0.7, 0.5, gripper_pos * 0.95],
            
            # Final satisfied position
            [base_pos, 0.35, 0.75, 0.4, gripper_pos]
        ]
        
        # Energetic timing with dynamic variations
        # Quick compression, explosive stretch, slower recovery
        durations = [
            0.3,  # Initial wiggle
            0.15, # Opposite wiggle
            0.15, # Another wiggle
            0.3,  # Start folding
            0.25, # Complete fold
            0.2,  # Hold fold (anticipation)
            0.1,  # Explosive release (very quick!)
            0.1,  # Maximum extension
            0.08, # Overshoot
            0.08, # Wiggle at apex
            0.25, # Begin falling
            0.1,  # Impact land
            0.15, # Compression
            0.2,  # Second fold start
            0.2,  # Second compact
            0.15, # Second bounce
            0.12, # Second apex
            0.15, # Second land
            0.2,  # Mini-fold
            0.15, # Final hop
            0.15, # Overshoot
            0.3,  # Settle
            0.4   # Final position
        ]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced dynamic playful bounce animation')

  
    def startled_jump(self):
        """Make the arm perform a startled jump with Disney principles."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney principles
        keyframes = [
            # Calm, unsuspecting starting position
            [base_pos, 0.3, 0.7, 0.0, gripper_pos],
            
            # Tiny freeze with subtle tension (anticipation)
            [base_pos, 0.32, 0.72, -0.05, gripper_pos * 1.1],  # Tighten gripper
            
            # Ultra-quick compression (extreme squash before jump)
            [base_pos, -1.0, 1.0, 0.0, gripper_pos * 1.15],  # Even tighter grip in panic
            
            # Explosive panic reaction (extreme stretch, exaggeration)
            [base_pos-0.4, -0.3, 0.1, 1.6, gripper_pos * 0.4],  # Gripper flies open in shock
            
            # Maximum extension with overshoot (follow-through)
            [base_pos-0.6, -0.4, 0.0, 1.8, gripper_pos * 0.3],  # Maximum shock expression
            
            # Secondary action - violent shake at apex
            [base_pos-0.5, -0.35, 0.05, 1.7, gripper_pos * 0.35],
            
            # Quick opposing shake (overlapping action)
            [base_pos-0.7, -0.35, 0.05, 1.7, gripper_pos * 0.4],
            
            # Initial settling but still alert (slow out)
            [base_pos-0.55, -0.15, 0.3, 1.3, gripper_pos * 0.45],
            
            # Begin cautious stance (staging)
            [base_pos-0.45, 0.5, 1.0, 0.7, gripper_pos * 0.5],
            
            # Nervous bounce back (secondary action)
            [base_pos-0.6, 0.4, 0.9, 0.8, gripper_pos * 0.55],
            
            # Hesitant peek forward (appeal - showing character)
            [base_pos-0.3, 0.45, 0.95, 0.5, gripper_pos * 0.6],
            
            # Quick startled recoil (timing)
            [base_pos-0.5, 0.5, 1.0, 0.7, gripper_pos * 0.55],
            
            # Another hesitant peek, braver this time (overlapping action)
            [base_pos-0.2, 0.4, 0.9, 0.4, gripper_pos * 0.65],
            
            # Quick nervous glance right (timing, exaggeration)
            [base_pos+0.3, 0.35, 0.85, 0.5, gripper_pos * 0.6],
            
            # Rapid glance left (arcs, secondary action)
            [base_pos-0.4, 0.35, 0.85, 0.5, gripper_pos * 0.65],
            
            # Glance back right, less extreme (diminishing energy)
            [base_pos+0.2, 0.35, 0.85, 0.5, gripper_pos * 0.7],
            
            # Back to cautious center position (arc motion)
            [base_pos-0.1, 0.4, 0.9, 0.45, gripper_pos * 0.75],
            
            # Beginning to relax but still alert (slow in)
            [base_pos-0.05, 0.35, 0.8, 0.35, gripper_pos * 0.8],
            
            # Calming down but with lingering vigilance
            [base_pos, 0.3, 0.7, 0.25, gripper_pos * 0.9]
        ]
        
        # Varied durations for dynamic startled movement
        durations = [
            0.3,  # Calm starting position
            0.2,  # Subtle tension
            0.1,  # Ultra-quick compression (very fast!)
            0.08, # Explosive reaction (extremely fast!)
            0.1,  # Maximum extension
            0.08, # Shake at apex
            0.08, # Opposing shake
            0.15, # Initial settling
            0.2,  # Cautious stance
            0.15, # Nervous bounce
            0.25, # Hesitant peek
            0.15, # Startled recoil
            0.3,  # Another peek
            0.15, # Nervous glance right
            0.15, # Rapid glance left
            0.2,  # Less extreme glance
            0.25, # Back to center
            0.4,  # Beginning to relax
            0.5   # Final vigilant pose
        ]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced dynamic startled jump animation')

    def thinking_animation(self):
        """Make the arm appear to be thinking like a person pondering a question."""
        # Get current positions
        base_pos = self.current_positions[0]
        gripper_pos = self.current_positions[4] if len(self.current_positions) > 4 else 3.14
        
        # Keyframe positions with Disney animation principles
        keyframes = [
            # Initial pose - upright, alert
            [base_pos, 0.3, 0.7, 0.3, gripper_pos * 0.9],  # Slightly open gripper
            
            # Anticipation - slight pause, "processing" the question
            [base_pos+0.05, 0.28, 0.68, 0.35, gripper_pos * 0.85],
            
            # Tilt "head" slightly (staging, establishing character)
            [base_pos+0.1, 0.25, 0.65, 0.5, gripper_pos * 0.8],
            
            # Secondary action - slight rotation showing contemplation
            [base_pos+0.2, 0.25, 0.65, 0.55, gripper_pos * 0.75],
            
            # Main thinking pose - "hand on chin" equivalent
            [base_pos+0.2, 0.35, 0.75, 0.2, gripper_pos * 0.7],
            
            # Deeper thought - fold back partially (using compact position)
            [base_pos+0.15, -0.5, 0.8, 0.4, gripper_pos * 0.65],
            
            # Slight downward tilt while folded (staging)
            [base_pos+0.2, -0.6, 0.9, 0.3, gripper_pos * 0.65],
            
            # Hold in deep thought (timing)
            [base_pos+0.2, -0.7, 1.0, 0.2, gripper_pos * 0.65],
            
            # Small "hmm" movement (appeal)
            [base_pos+0.25, -0.65, 0.95, 0.25, gripper_pos * 0.6],
            
            # Another contemplative pose - shifting position
            [base_pos-0.15, -0.5, 0.8, 0.3, gripper_pos * 0.6],
            
            # Look up slightly (as if having an idea forming)
            [base_pos-0.1, -0.3, 0.7, 0.5, gripper_pos * 0.6],
            
            # Unfold more as idea develops (arc motion)
            [base_pos, 0.1, 0.5, 0.7, gripper_pos * 0.55],
            
            # "Eureka" movement - dramatic unfolding (exaggeration)
            [base_pos+0.1, 0.0, 0.3, 1.1, gripper_pos * 0.5],  # Open gripper more
            
            # Excited response to idea - full extension (stretch)
            [base_pos, -0.2, 0.2, 1.3, gripper_pos * 0.45],
            
            # Bouncy movement showing excitement (secondary action)
            [base_pos+0.2, -0.15, 0.15, 1.4, gripper_pos * 0.4],
            
            # Quick confirmation nod (follow through)
            [base_pos, 0.1, 0.3, 1.0, gripper_pos * 0.5],
            
            # Satisfied bounce (appeal)
            [base_pos-0.1, 0.2, 0.5, 0.7, gripper_pos * 0.6],
            
            # Final satisfied position with slight lean
            [base_pos, 0.3, 0.7, 0.4, gripper_pos * 0.7]
        ]
        
        # Varied durations for natural thinking pattern with longer pauses
        durations = [
            0.5,  # Initial pose
            0.6,  # Anticipation pause
            0.4,  # Head tilt
            0.5,  # Rotation
            0.7,  # Hand on chin pose
            0.8,  # Fold back
            0.5,  # Downward tilt
            1.2,  # Hold in thought (long pause)
            0.4,  # "Hmm" movement
            0.7,  # Shift position
            0.6,  # Look up
            0.5,  # Unfold more
            0.4,  # Eureka moment
            0.3,  # Excited response
            0.3,  # Bouncy movement
            0.4,  # Confirmation nod
            0.5,  # Satisfied bounce
            0.6   # Final position
        ]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced thinking animation')

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
        
        # Keyframe positions with Disney animation principles
        keyframes = [
            # Starting position - compressed, tired looking pose
            [base_pos, 0.6, 1.2, -0.2, gripper_pos * 1.2],  # Very closed gripper (tension)
            
            # Initial tiny stretch movement (anticipation)
            [base_pos+0.1, 0.55, 1.15, -0.1, gripper_pos * 1.15],
            
            # Slight contraction - building tension (more anticipation)
            [base_pos+0.05, 0.65, 1.25, -0.3, gripper_pos * 1.2],
            
            # First small stretch attempt - not quite there yet
            [base_pos, 0.4, 1.0, 0.1, gripper_pos * 1.1],
            
            # Bigger contraction - really preparing (extreme anticipation)
            [base_pos, -0.5, 1.0, 0.0, gripper_pos * 1.2],  # Folded back position
            
            # Compact fold for maximum tension (extreme squash)
            [base_pos, -1.5, 1.8, 1.0, gripper_pos * 1.25],  # Using folded position
            
            # Begin big stretch upward (initial stretch)
            [base_pos, 0.2, 0.5, 0.6, gripper_pos * 0.9],  # Start opening gripper
            
            # Continue stretch upward with tilt (exaggeration)
            [base_pos+0.3, 0.0, 0.3, 1.0, gripper_pos * 0.7],
            
            # Maximum stretch with twist right (extreme stretch)
            [base_pos+0.5, -0.2, 0.2, 1.4, gripper_pos * 0.5],  # Widely open gripper
            
            # Hold stretch at apex with slight wobble (timing, appeal)
            [base_pos+0.45, -0.25, 0.15, 1.45, gripper_pos * 0.45],
            
            # Stretch to left side with arcing motion (arcs)
            [base_pos-0.5, -0.2, 0.2, 1.4, gripper_pos * 0.5],  # Maintain stretch
            
            # Hold left stretch with slight adjustment (secondary action)
            [base_pos-0.45, -0.25, 0.15, 1.45, gripper_pos * 0.45],
            
            # Second phase - bend down stretch (solid drawing)
            [base_pos, 0.7, 1.4, -0.5, gripper_pos * 0.6],  # Different direction stretch
            
            # Maximum down stretch (exaggeration)
            [base_pos, 0.9, 1.7, -0.8, gripper_pos * 0.55],
            
            # Hold down stretch with slight shake (appeal)
            [base_pos+0.1, 0.85, 1.65, -0.75, gripper_pos * 0.6],
            
            # Start relaxing with a sigh (slow out)
            [base_pos-0.1, 0.7, 1.5, -0.5, gripper_pos * 0.65],
            
            # Twist stretch - rotate base fully (secondary action)
            [base_pos+0.8, 0.5, 1.2, -0.2, gripper_pos * 0.7],
            
            # Counter twist - opposite direction (follow through)
            [base_pos-0.8, 0.5, 1.2, -0.2, gripper_pos * 0.7],
            
            # Final folded stretch position (squash and stretch)
            [base_pos, -1.0, 1.5, 1.0, gripper_pos * 0.8],  # One more good stretch
            
            # Begin final relaxing (follow through)
            [base_pos, 0.1, 0.6, 0.7, gripper_pos * 0.85],
            
            # Continue relaxing with satisfaction (arc motion)
            [base_pos, 0.2, 0.7, 0.5, gripper_pos * 0.9],
            
            # Small bounce in relaxation (overlapping action)
            [base_pos, 0.3, 0.75, 0.35, gripper_pos * 0.95],
            
            # Final settled position with satisfaction and slight wiggle
            [base_pos+0.1, 0.35, 0.8, 0.3, gripper_pos]
        ]
        
        # Varied durations for a more satisfying stretch experience
        durations = [
            0.5,  # Tired starting position
            0.3,  # Initial tiny stretch
            0.4,  # Building tension
            0.5,  # First small attempt
            0.6,  # Bigger contraction
            0.7,  # Maximum compact tension
            0.5,  # Begin big stretch
            0.6,  # Continue stretch
            0.7,  # Maximum stretch right
            1.2,  # Hold and savor stretch (long hold)
            0.8,  # Stretch to left
            1.0,  # Hold left stretch
            0.6,  # Bend down stretch
            0.7,  # Maximum down
            0.8,  # Hold with shake
            0.6,  # Start relaxing
            0.4,  # Twist stretch
            0.4,  # Counter twist
            0.8,  # Final folded stretch
            0.5,  # Begin final relaxing
            0.6,  # Continue relaxing
            0.4,  # Bounce in relaxation
            0.7   # Final settled position
        ]
        
        # Start the animation
        self.start_animation(keyframes, durations)
        self.get_logger().info('Executing enhanced satisfying stretch animation')

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


def main(args=None):
    rclpy.init(args=args)
    command_interface = EnhancedAnimationCommand()
    
    # Keep the node running
    rclpy.spin(command_interface)
    
    command_interface.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
