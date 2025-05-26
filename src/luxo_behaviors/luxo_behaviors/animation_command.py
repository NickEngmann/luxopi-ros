#!/usr/bin/env python3
#animation_command.py
import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import String
from sensor_msgs.msg import JointState
from luxo_interfaces.action import PlayAnimation
import time
import json
import threading
import importlib
import inspect
import pkgutil
from typing import Dict, List, Optional

# Import the base plugin class
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class AnimationCommandActionServer(Node):
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
        
        # Joint limits configuration
        self.joint_limits = {
            'L1_to_L2': {'min': -1.57, 'max': 2.05},
            # Add other joint limits here if needed
        }
        
        self.declare_parameter('enforce_joint_limits', True)
        self.enforce_joint_limits = self.get_parameter('enforce_joint_limits').value
        
        # Hardware position feedback parameter
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
        
        # Create subscription for animation commands (backward compatibility)
        self.command_subscription = self.create_subscription(
            String,
            '/roarm/animation_command',
            self.command_callback,
            10)
        
        # Create publisher for joint states
        joint_topic = '/joint_states_target' if self.publish_target else '/joint_states'
        self.joint_publisher = self.create_publisher(
            JointState, 
            joint_topic,
            10)
        
        self.get_logger().info(f'Publishing joint states to: {joint_topic}')

        # Current joint positions
        self.current_positions = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.target_positions = self.current_positions.copy()
        
        self.collision_avoidance = None

        # Define joint names
        if self.use_hardware_joint_names:
            self.joint_names = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
            self.get_logger().info('Using hardware joint names for RoArm compatibility')
        else:
            self.joint_names = ['base_to_L1', 'L1_to_L2', 'L2_to_L3', 'L3_to_L4', 'hand']
        
        # Timer for regular publishing
        self.timer = self.create_timer(0.25, self.publish_joint_states_target)
        
        # Animation state
        self.is_animating = False
        self.animation_steps = []
        self.current_step = 0
        self.step_durations = []
        self.animation_timer = None
        self.speed_multiplier = 1.0
        
        # Action server state
        self._goal_handle = None
        self._goal_lock = threading.Lock()
        self._cancel_requested = False
        
        # Movement source tracking
        self.movement_source = "idle"
        self.last_movement_source_change = self.get_clock().now()
        
        # DEMA control integration
        self.declare_parameter('enable_dema_integration', True)
        self.enable_dema_integration = True
        
        # Create publisher for movement type
        if self.enable_dema_integration:
            self.movement_source_publisher = self.create_publisher(
                String,
                '/roarm/movement_source',
                10
            )
            self.get_logger().info("Publishing movement source information for DEMA coordination")
        
        # Subscribe to collision status
        self.collision_status = "safe"
        self.collision_status_sub = self.create_subscription(
            String,
            '/collision_status_for_animation',
            self.collision_status_callback,
            10
        )
        
        # Track if animation was preempted by collision
        self.collision_preempted = False
        
        # Load animation plugins
        self.animation_plugins = self._load_animation_plugins()
        self.get_logger().info(f'Loaded {len(self.animation_plugins)} animation plugins')
        
        # Create action server
        self._action_server = ActionServer(
            self,
            PlayAnimation,
            'play_animation',
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            handle_accepted_callback=self.handle_accepted_callback,
            cancel_callback=self.cancel_callback,
            callback_group=ReentrantCallbackGroup()
        )
        
        # Initialize ROS time tracking
        self._init_time_tracking()
        
        # Maximum attempts to get hardware position
        self.max_position_attempts = 10
        self.position_request_interval = 0.5
        
        self.get_logger().info('Animation command action server initialized')
        self.get_logger().info(f'Available animations: {", ".join(self.animation_plugins.keys())}')
        self.get_logger().info(f'Publishing to topic: {joint_topic}')
        self.get_logger().info(f'Publish enabled: {self.should_publish}')
        self.get_logger().info(f'Hardware joint names: {self.use_hardware_joint_names}')
        self.get_logger().info(f'Joint names: {self.joint_names}')
        
        # Initialize hardware position if enabled
        if self.use_hardware_position_feedback:
            self.request_hardware_position()
    
    def set_collision_avoidance(self, collision_avoidance):
        """Set the collision avoidance reference from hardware interface."""
        self.collision_avoidance = collision_avoidance
        self.get_logger().info("Collision avoidance reference set in animation command")
    
    def _init_time_tracking(self):
        """Initialize all ROS time tracking variables."""
        now = self.get_clock().now()
        self._last_debug_time = now
        self._last_position_log_time = now
        self._last_movement_source_log_time = now
        self._last_source_log = now
        self.last_animation_end_time = now
        self.last_valid_positions = [0.0] * 5
        self.idle_reset_timer = None
    
    def collision_status_callback(self, msg):
        """Update collision status from collision avoidance system."""
        self.collision_status = msg.data
        
        # Check if this is a danger status while we have an active goal
        if "danger" in self.collision_status and self._goal_handle and self._goal_handle.is_active:
            # Check if interruption is allowed
            goal = self._goal_handle.request
            if goal.allow_interruption:
                self.get_logger().warn(f"Collision danger detected during animation: {self.collision_status}")
                self.collision_preempted = True
    
    def _load_animation_plugins(self) -> Dict[str, AnimationPlugin]:
        """Dynamically load all animation plugins."""
        plugins = {}
        
        # Try to import animation plugin modules
        plugin_modules = [
            'luxo_behaviors.animation_plugins.emotion_animations',
            'luxo_behaviors.animation_plugins.action_animations',
            'luxo_behaviors.animation_plugins.response_animations'
        ]
        
        for module_name in plugin_modules:
            try:
                module = importlib.import_module(module_name)
                
                # Find all classes that inherit from AnimationPlugin
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, AnimationPlugin) and obj != AnimationPlugin:
                        # Create instance of the plugin
                        plugin_instance = obj(self)
                        
                        # Validate the plugin
                        if plugin_instance.validate_keyframes():
                            plugins[plugin_instance.name] = plugin_instance
                            self.get_logger().debug(f"Loaded animation plugin: {plugin_instance.name}")
                        else:
                            self.get_logger().error(f"Failed to validate animation plugin: {name}")
                            
            except ImportError as e:
                self.get_logger().warn(f"Could not import plugin module {module_name}: {e}")
            except Exception as e:
                self.get_logger().error(f"Error loading plugins from {module_name}: {e}")
        
        return plugins
    
    def goal_callback(self, goal_request):
        """Decide whether to accept or reject a goal request."""
        self.get_logger().info(f'Received animation goal request: {goal_request.animation_name}')
        
        # Check if animation exists
        if goal_request.animation_name not in self.animation_plugins:
            self.get_logger().warn(f'Unknown animation: {goal_request.animation_name}')
            return GoalResponse.REJECT
        
        # Accept the goal
        return GoalResponse.ACCEPT
    
    def handle_accepted_callback(self, goal_handle):
        """Start executing an accepted goal."""
        with self._goal_lock:
            # Cancel any existing goal
            if self._goal_handle is not None and self._goal_handle.is_active:
                self.get_logger().info('Cancelling previous animation goal')
                self._goal_handle.canceled()
            
            self._goal_handle = goal_handle
            self._cancel_requested = False
        
        # Execute the goal immediately
        goal_handle.execute()
    
    def cancel_callback(self, goal_handle):
        """Accept or reject a cancel request."""
        self.get_logger().info('Received cancel request')
        with self._goal_lock:
            self._cancel_requested = True
        return CancelResponse.ACCEPT
    
    def execute_callback(self, goal_handle):
        """Execute the animation goal (called by action server)."""
        # Now we execute in the callback thread
        result = self._execute_animation(goal_handle)
        return result
    
    def _execute_animation(self, goal_handle):
        """Execute animation in the action server thread."""
        start_time = time.time()
        collision_interruptions = 0
        final_state = "completed"
        
        # Reset collision preemption flag
        self.collision_preempted = False
        
        try:
            goal = goal_handle.request
            animation_name = goal.animation_name
            speed_multiplier = goal.speed_multiplier if 0.1 <= goal.speed_multiplier <= 2.0 else 1.0
            
            self.get_logger().info(
                f'Executing animation: {animation_name} with speed {speed_multiplier}'
            )
            
            # Get the animation plugin
            plugin = self.animation_plugins[animation_name]
            
            # Get hardware position if requested
            if goal.use_hardware_feedback and self.use_hardware_position_feedback:
                self.request_hardware_position()
            
            # Get keyframes and durations
            keyframes, durations = plugin.get_keyframes()
            keyframe_names = plugin.get_keyframe_names()
            
            # Prepare keyframes for current position
            if self.hardware_position_received:
                keyframes = plugin.prepare_for_current_position(
                    self.current_positions, keyframes
                )
            
            # Apply speed multiplier
            self.speed_multiplier = speed_multiplier  # Set the instance variable
            adjusted_durations = [d / speed_multiplier for d in durations]
            
            # Set movement source
            self.movement_source = "animation"
            self.last_movement_source_change = self.get_clock().now()
            self.is_animating = True  # Set animation flag
            
            # Execute animation with progress feedback
            total_duration = sum(adjusted_durations)
            
            for i, (keyframe, duration) in enumerate(zip(keyframes, adjusted_durations)):
                # Check for cancel
                if self._cancel_requested:
                    final_state = "preempted"
                    break
                
                # Check if we've been preempted by collision
                if self.collision_preempted and goal.allow_interruption:
                    final_state = "preempted"
                    self.get_logger().warn("Animation preempted by collision system")
                    break
                
                # Add noise to keyframe
                noisy_keyframe = plugin.add_noise_to_position(keyframe)
                
                # Use actual collision status
                collision_status = self.collision_status
                
                # Calculate progress
                elapsed_time = time.time() - start_time
                progress = min(1.0, elapsed_time / total_duration)
                time_remaining = max(0.0, total_duration - elapsed_time)
                
                # Publish feedback
                feedback = PlayAnimation.Feedback()
                feedback.progress = progress
                feedback.current_keyframe = i
                feedback.total_keyframes = len(keyframes)
                feedback.current_step_name = keyframe_names[i] if keyframe_names else f"Step {i+1}"
                feedback.collision_status = collision_status
                feedback.current_joints = list(self.current_positions)
                feedback.time_remaining = time_remaining
                
                goal_handle.publish_feedback(feedback)
                
                # Log keyframe execution
                self.get_logger().info(
                    f"Executing keyframe {i+1}/{len(keyframes)}: "
                    f"{feedback.current_step_name} -> {[round(p, 2) for p in noisy_keyframe]}"
                )
                
                # Move to position
                self.move_to_position(noisy_keyframe, duration, easing=True, animation_name=animation_name)
                
                # If collision interrupted, increment counter
                if collision_status != "safe":
                    collision_interruptions += 1
            
            # Animation complete
            self.is_animating = False
            actual_duration = time.time() - start_time
            
            # Schedule return to home position after 1 second if animation completed successfully
            if final_state == "completed":
                    # Fallback: schedule idle state after delay
                    self.get_logger().info("Scheduling idle state after animation")
                    if hasattr(self, 'idle_reset_timer') and self.idle_reset_timer:
                        self.idle_reset_timer.cancel()
                    self.idle_reset_timer = self.create_timer(
                        0.5,
                        lambda: self._reset_to_idle_once()
                    )
            
            # Create result
            result = PlayAnimation.Result()
            result.success = final_state == "completed"
            result.message = f"Animation {animation_name} {final_state}"
            result.actual_duration = actual_duration
            result.collision_interruptions = collision_interruptions
            result.final_state = final_state
            result.final_positions = list(self.current_positions)
            
            if final_state == "completed":
                goal_handle.succeed()
            elif final_state == "preempted":
                goal_handle.canceled()
            else:
                goal_handle.abort()
            
            return result
                    
        except Exception as e:
            self.get_logger().error(f"Error executing animation: {e}")
            result = PlayAnimation.Result()
            result.success = False
            result.message = f"Animation failed: {str(e)}"
            result.actual_duration = time.time() - start_time
            result.collision_interruptions = collision_interruptions
            result.final_state = "aborted"
            result.final_positions = list(self.current_positions)
            goal_handle.abort()
            return result

    
    def command_callback(self, msg):
        """Handle animation command messages (backward compatibility)."""
        command_parts = msg.data.strip().lower().split()
        base_command = command_parts[0]
        
        # Extract speed parameter if present
        speed = 1.0
        if len(command_parts) > 1:
            try:
                speed = float(command_parts[1])
                speed = max(0.1, min(2.0, speed))
            except ValueError:
                pass
        
        # Check if animation exists
        if base_command not in self.animation_plugins:
            self.get_logger().warn(f'Unknown animation command: {base_command}')
            self.get_logger().info(f'Available: {", ".join(self.animation_plugins.keys())}')
            return
        
        # Execute via simple method (not action)
        self.execute_animation_simple(base_command, speed)
    
    def execute_animation_simple(self, animation_name, speed=1.0):
        """Execute animation without action server (for topic compatibility)."""
        # Prevent running if action-based animation is active
        with self._goal_lock:
            if self._goal_handle and self._goal_handle.is_active:
                self.get_logger().warn("Cannot run topic-based animation while action is active")
                return
        
        self.get_logger().info(f'Executing animation: {animation_name} with speed {speed}')
        
        # Set movement source
        self.movement_source = "animation"
        self.last_movement_source_change = self.get_clock().now()
        
        # Get plugin and execute
        plugin = self.animation_plugins[animation_name]
        keyframes, durations = plugin.get_keyframes()
        
        # Prepare for current position if hardware feedback available
        if self.use_hardware_position_feedback and self.hardware_position_received:
            keyframes = plugin.prepare_for_current_position(
                self.current_positions, keyframes
            )
        
        # Start animation
        self.speed_multiplier = speed
        self.start_animation(keyframes, durations, animation_name)
        
        # Schedule return to home after animation completes
        total_duration = sum([d / speed for d in durations])
        
        # Cancel any existing idle reset timer
        if hasattr(self, 'idle_reset_timer') and self.idle_reset_timer:
            self.idle_reset_timer.cancel()
        
        # Schedule home position 1 second after animation ends
        home_delay = total_duration + 1.0
        self.idle_reset_timer = self.create_timer(
            home_delay,
            lambda: self._schedule_home_or_idle()
        )
    
    def _schedule_home_position(self):
        """Schedule return to home position after animation."""
        try:
            # Cancel the timer
            if hasattr(self, 'idle_reset_timer') and self.idle_reset_timer:
                self.idle_reset_timer.cancel()
                self.idle_reset_timer = None
            
            # Use collision avoidance to schedule home if available
            if self.collision_avoidance:
                self.collision_avoidance.schedule_home_after_animation(delay=0.1)
            else:
                # Just set to idle state
                self.get_logger().info("Setting movement source to idle (collision avoidance not available)")
                self.movement_source = "idle"
                self.publish_movement_source()
        except Exception as e:
            self.get_logger().error(f"Error scheduling home position: {e}")
    
    def _schedule_home_or_idle(self):
        """Schedule home position if collision avoidance available, otherwise just go idle."""
        try:
            if hasattr(self, 'idle_reset_timer') and self.idle_reset_timer:
                self.idle_reset_timer.cancel()
                self.idle_reset_timer = None
            
            # Just set to idle state since we don't have collision avoidance
            self.movement_source = "idle"
            self.publish_movement_source()
            self.get_logger().info("Animation complete - movement source set to idle")
        except Exception as e:
            self.get_logger().error(f"Error in schedule home or idle: {e}")
    
    def position_feedback_callback(self, msg):
        """Handle position feedback from the hardware."""
        try:
            position_list = json.loads(msg.data)
            
            if isinstance(position_list, list) and len(position_list) >= 5:
                # Filter positions
                if self.current_positions is None:
                    self.current_positions = position_list.copy()
                else:
                    tolerance = 0.03
                    filtered_positions = position_list.copy()
                    
                    for i in range(min(len(position_list), len(self.current_positions))):
                        diff = abs(float(position_list[i]) - float(self.current_positions[i]))
                        if diff < tolerance:
                            filtered_positions[i] = self.current_positions[i]
                    
                    self.current_positions = filtered_positions
                
                if not self.is_animating:
                    self.target_positions = self.current_positions.copy()
                
                self.hardware_position_received = True
                
        except Exception as e:
            self.get_logger().error(f"Error parsing position feedback: {e}")
    
    def request_hardware_position(self):
        """Request and wait for hardware position before proceeding."""
        if not self.use_hardware_position_feedback:
            return True
        
        self.get_logger().info("Waiting for initial hardware position...")
        
        attempts = 0
        self.hardware_position_received = False
        
        while attempts < self.max_position_attempts and not self.hardware_position_received:
            time.sleep(self.position_request_interval)
            attempts += 1
        
        if self.hardware_position_received:
            self.get_logger().info("Hardware position received")
            return True
        else:
            self.get_logger().warn("Failed to get hardware position, using defaults")
            return False
    
    def publish_joint_states_target(self):
        """Publish target joint states."""
        if not self.should_publish:
            self.get_logger().debug("Publishing disabled by parameter")
            return
        
        # Check movement source status
        current_time = self.get_clock().now()
        
        if not self.is_animating and self.movement_source == "animation":
            if not hasattr(self, 'last_animation_end_time'):
                self.last_animation_end_time = current_time
            
            time_since_animation_end = (current_time - self.last_animation_end_time).nanoseconds / 1e9
            if time_since_animation_end > 3.0:
                self.movement_source = "idle"
                self.publish_movement_source()
        
        if self.is_animating:
            self.last_animation_end_time = current_time
        
        # Create joint state message
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self.joint_names
        
        try:
            validated_positions = [float(pos) for pos in self.target_positions]
            
            if self.enforce_joint_limits:
                validated_positions = self.apply_joint_limits(msg.name, validated_positions)
            
            msg.position = validated_positions
            
            # Encode movement source in velocity field
            source_code = 0  # idle
            if self.movement_source == "animation":
                source_code = 1
            elif self.movement_source == "collision":
                source_code = 2
            elif self.movement_source == "user":
                source_code = 3
            
            msg.velocity = [float(source_code)]
            
            self.joint_publisher.publish(msg)
            
            # Add debug logging
            if self.is_animating:
                self.get_logger().debug(f"Published joint states during animation: {[round(p, 2) for p in validated_positions]}")
            
        except Exception as e:
            self.get_logger().error(f"Error publishing joint states: {e}")
    
    def apply_joint_limits(self, joint_names, joint_positions):
        """Apply joint limits to positions."""
        limited_positions = list(joint_positions)
        
        for i, name in enumerate(joint_names):
            if name in self.joint_limits:
                limits = self.joint_limits[name]
                original_value = joint_positions[i]
                
                if original_value < limits['min']:
                    limited_positions[i] = limits['min']
                elif original_value > limits['max']:
                    limited_positions[i] = limits['max']
        
        return limited_positions
    
    def ease_in_out(self, t):
        """Cubic easing function for smoother motion."""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2
    
    def move_to_position(self, positions, duration=1.0, easing=True, animation_name=None):
        """Move to a specific position over a duration with optional easing."""
        start_positions = self.target_positions.copy()
        start_time = self.get_clock().now()
        
        adjusted_duration = duration / self.speed_multiplier
        
        # Store current animation name for tracking
        if animation_name:
            self.current_animation_name = animation_name
        
        elapsed_time = 0.0
        while elapsed_time < adjusted_duration:
            current_time = self.get_clock().now()
            elapsed_time = (current_time - start_time).nanoseconds / 1e9
            progress = min(1.0, elapsed_time / adjusted_duration)
            
            if easing:
                eased_progress = self.ease_in_out(progress)
            else:
                eased_progress = progress
            
            for i in range(len(self.target_positions)):
                self.target_positions[i] = start_positions[i] + eased_progress * (positions[i] - start_positions[i])
            
            # IMPORTANT: Explicitly publish the joint states during movement
            self.publish_joint_states_target()
            
            time.sleep(0.01)
        
        self.target_positions = list(positions)
        
        # Final publish at target position
        self.publish_joint_states_target()
        
        return True
    
    def start_animation(self, keyframes, durations, animation_name=None):
        """Start an animation with keyframes and durations."""
        self.animation_steps = keyframes
        self.step_durations = [d / self.speed_multiplier for d in durations]
        self.current_step = 0
        self.is_animating = True
        self.current_animation_name = animation_name
        
        self._process_next_step()
    
    def _process_next_step(self):
        """Process the next animation step."""
        if not self.is_animating or self.current_step >= len(self.animation_steps):
            if self.is_animating:
                self.is_animating = False
                self.current_animation_name = None
                self.get_logger().info('Legacy animation completed')
            return
        
        next_position = self.animation_steps[self.current_step]
        duration = self.step_durations[self.current_step]
        
        self.move_to_position(next_position, duration, easing=True, animation_name=self.current_animation_name)
        
        self.current_step += 1
        if self.current_step < len(self.animation_steps):
            # Cancel any existing timer
            if hasattr(self, 'animation_timer') and self.animation_timer:
                self.animation_timer.cancel()
            self.animation_timer = self.create_timer(duration, self._next_step_callback)
        else:
            self.is_animating = False
            self.current_animation_name = None
            self.get_logger().info('Legacy animation completed')
    
    def _next_step_callback(self):
        """Handle timer callback for the next animation step."""
        # Cancel this timer immediately to prevent repeated calls
        if hasattr(self, 'animation_timer') and self.animation_timer:
            self.animation_timer.cancel()
            self.animation_timer = None
        
        # Process the next step
        self._process_next_step()
    
    def _reset_to_idle(self):
        """Reset movement source to idle."""
        if self.movement_source != "idle":
            self.movement_source = "idle"
            self.get_logger().info('Movement source reset to idle')
            self.publish_movement_source()
        
        if self.idle_reset_timer:
            self.idle_reset_timer.cancel()
            self.idle_reset_timer = None
    
    def _reset_to_idle_once(self):
        """Reset to idle and cancel the timer (for one-shot timers)."""
        self._reset_to_idle()
    
    def publish_movement_source(self):
        """Publish the current movement source."""
        if not self.enable_dema_integration:
            self.get_logger().debug("DEMA integration disabled, not publishing movement source")
            return
        
        try:
            msg = String()
            msg.data = self.movement_source
            self.movement_source_publisher.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing movement source: {e}")


def main(args=None):
    rclpy.init(args=args)
    
    # Use MultiThreadedExecutor for action server
    executor = MultiThreadedExecutor()
    animation_server = AnimationCommandActionServer()
    
    executor.add_node(animation_server)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        animation_server.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()