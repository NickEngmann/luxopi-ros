#!/usr/bin/env python3
#hardware_interface.py
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, String, Float32
import json
import threading
import time
from luxo_behaviors.serial_manager import SerialManager
from luxo_behaviors.collision_avoidance import CollisionAvoidance

class RoArmHardwareInterface(Node):
    def __init__(self):
        super().__init__('roarm_hardware_interface')
        
        # Declare parameters
        self.declare_parameter('serial_port', '/dev/ttyAMA0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('enable_torque', True)
        self.declare_parameter('read_throttle', 0.1)
        
        # Collision avoidance parameters
        self.declare_parameter('enable_collision_avoidance', True)
        self.declare_parameter('soft_limit_distance', 12.0)  # cm
        self.declare_parameter('hard_limit_distance', 8.0)   # cm
        self.declare_parameter('max_deceleration', 2.0)  # rad/s²
        self.declare_parameter('collision_recovery_timeout', 3.0)  # seconds
        
        # Additional parameters for proactive avoidance
        self.declare_parameter('avoidance_playfulness', 0.3)  # 0.0-1.0 random factor
        self.declare_parameter('side_avoidance_magnitude', 0.5)  # Rotation magnitude for side avoidance
        self.declare_parameter('consecutive_collision_threshold', 3)  # How many repeated collisions trigger stronger response
        self.declare_parameter('escape_threshold', 10)  # How many consecutive collisions trigger escape mode
        self.declare_parameter('max_retreat_angle', 0.8)  # Maximum shoulder/elbow retreat angle
        self.declare_parameter('escape_mode_duration', 10.0)  # How long to avoid an area after escaping (seconds)
        self.declare_parameter('max_escape_attempts', 5)  # Maximum attempts before forced rest position
        
        # Add parameter for rest position
        self.declare_parameter('enable_rest_position', True)  # Enable/disable the rest position behavior
        self.declare_parameter('base_rest_position', [0.0, -2.0, 2.0, 1.0, 0.0])  # Base rest position
        self.declare_parameter('rest_variation_range', 0.15)  # Range for position variation        
        self.declare_parameter('use_hardware_joint_names', False)
        
        # Add parameters for dynamic adaptation/external force control
        self.declare_parameter('enable_dynamic_adaptation', False)  # Default to disabled
        self.declare_parameter('dynamic_adaptation_base_limit', 1)  # Default torque limits
        self.declare_parameter('dynamic_adaptation_shoulder_limit', 1)
        self.declare_parameter('dynamic_adaptation_elbow_limit', 1)
        self.declare_parameter('dynamic_adaptation_wrist_limit', 1)
        self.declare_parameter('dynamic_adaptation_roll_limit', 1)
        self.declare_parameter('dynamic_adaptation_hand_limit', 1)
        self.declare_parameter('dynamic_adaptation_resume_delay', 3.0)  # Changed from 10.0 to 3.0 seconds
        
        # Add a new parameter for the DEMA movement source integration
        self.declare_parameter('enable_movement_source_integration', True)
        
        # Add parameter for initialization method
        self.declare_parameter('use_hardware_position_on_init', True)  # Whether to read actual position from hardware
        self.declare_parameter('init_position_timeout', 10.0)  # Timeout for getting initial position
        
        # Get parameters
        self.serial_port = self.get_parameter('serial_port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.enable_torque_on_start = self.get_parameter('enable_torque').value
        self.read_throttle = self.get_parameter('read_throttle').value
        self.enable_collision_avoidance = self.get_parameter('enable_collision_avoidance').value
        
        # Get parameters for rest position
        self.enable_rest_position = self.get_parameter('enable_rest_position').value
        self.base_rest_position = self.get_parameter('base_rest_position').value
        self.rest_variation_range = self.get_parameter('rest_variation_range').value
        
        self.use_hardware_joint_names = self.get_parameter('use_hardware_joint_names').value
        
        # Get dynamic adaptation parameters
        self.enable_dynamic_adaptation = self.get_parameter('enable_dynamic_adaptation').value
        self.dynamic_adaptation_base_limit = self.get_parameter('dynamic_adaptation_base_limit').value
        self.dynamic_adaptation_shoulder_limit = self.get_parameter('dynamic_adaptation_shoulder_limit').value
        self.dynamic_adaptation_elbow_limit = self.get_parameter('dynamic_adaptation_elbow_limit').value
        self.dynamic_adaptation_wrist_limit = self.get_parameter('dynamic_adaptation_wrist_limit').value
        self.dynamic_adaptation_roll_limit = self.get_parameter('dynamic_adaptation_roll_limit').value
        self.dynamic_adaptation_hand_limit = self.get_parameter('dynamic_adaptation_hand_limit').value
        self.dynamic_adaptation_resume_delay = self.get_parameter('dynamic_adaptation_resume_delay').value
        
        # Get initialization parameters
        self.use_hardware_position_on_init = self.get_parameter('use_hardware_position_on_init').value
        self.init_position_timeout = self.get_parameter('init_position_timeout').value
        
        # Connection control
        self.connection_active = False
        self.connection_lock = threading.Lock()
        
        # Add timer health tracking variables using ROS time
        self.safety_timer_active = False
        self.last_safety_timer_id = 0
        self.safety_timer_creation_time = self.get_clock().now()
        self.safety_timer_call_count = 0
        self.safety_timer_last_exception = None
        self.safety_timer_lock = threading.Lock()
        
        # Initialize the SerialManager
        self.serial_manager = SerialManager(
            self, 
            self.serial_port, 
            self.baud_rate, 
            self.read_throttle
        )
        
        # Connect to the serial port
        self.connection_active = self.serial_manager.connect()

        # Joint state tracking with fallback default values
        # These will be initialized from hardware before publishing begins
        self.current_joints = [0.0, 0.0, 0.0, 0.0, 0.0]  # base, shoulder, elbow, wrist, hand
        self.target_joints = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.joint_velocities = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.last_command_time = self.get_clock().now()  # ROS time
        
        # Flag to track whether we have valid joint positions from hardware
        self.position_initialized = False
        
        # Add tracking variables for dynamic adaptation using ROS time
        self.dynamic_adaptation_active = False
        self.dynamic_adaptation_last_disable_time = self.get_clock().now()
        self.dynamic_adaptation_pending_resume = False
        self.dynamic_adaptation_lock = threading.Lock()
        self.dynamic_adaptation_timeout = 10.0  # Keep enabled for 10 seconds
        self.last_movement_source = "unknown"  # Track movement source for DEMA control
        self.initial_adaptation_setup = True  # Flag to track initial setup vs toggle
        
        # Enable movement source integration
        self.enable_movement_source_integration = self.get_parameter('enable_movement_source_integration').value
        if self.enable_movement_source_integration:
            self.movement_source_publisher = self.create_publisher(
                String,
                '/roarm/movement_source',
                10
            )
        
        if self.connection_active:
            # Initialize the collision avoidance system
            self.collision_avoidance = CollisionAvoidance(
                self,  # Pass this node to the collision system
                self.send_safe_joint_command,  # Callback to send joint commands
                self.publish_actual_joint_states  # Callback to publish joint states
            )
            if self.enable_torque_on_start:
                self.get_logger().info("Torque enabled on startup")
                self.enable_torque()
            else:
                self.get_logger().info("Torque disabled on startup")
            time.sleep(0.5)  # Hardware initialization delay - keep as time.sleep
            
            # Configure dynamic adaptation for startup
            # Always start with dynamic adaptation disabled regardless of parameter
            self.disable_dynamic_adaptation_mode()
            self.get_logger().info("Dynamic adaptation disabled for initialization")
                
            # Store the parameter value for later re-enabling
            self.dema_should_be_enabled = self.enable_dynamic_adaptation
            
            # Changed subscription to joint_states_target
            self.subscription = self.create_subscription(
                JointState,
                'joint_states_target',
                self.joint_states_callback,
                10)
            
            # Add publisher for actual joint states after collision avoidance
            self.get_logger().info("Creating publisher for actual joint states on /joint_states")
            self.joint_states_publisher = self.create_publisher(
                JointState,
                '/joint_states',
                10)
                
            # Add a direct publishing timer to ensure we're sending messages regularly
            self.direct_pub_timer = self.create_timer(0.1, self.publish_current_joint_states)
            
            # Publisher for collision status that animations can monitor
            self.collision_status_publisher = self.create_publisher(
                String,
                '/collision_status_for_animation',
                10
            )
            
            # Timer to publish collision status regularly
            self.collision_status_timer = self.create_timer(0.1, self.publish_collision_status)
            
            # Create subscriptions to collision topics
            self.front_collision_sub = self.create_subscription(
                Bool, 
                '/head_collision_warning',
                self.front_collision_callback, 
                10)
                
            self.left_collision_sub = self.create_subscription(
                Bool, 
                '/left_collision_warning',
                self.left_collision_callback, 
                10)
                
            self.right_collision_sub = self.create_subscription(
                Bool, 
                '/right_collision_warning',
                self.right_collision_callback, 
                10)
                
            # Subscribe to distance measurements for more precise control
            self.front_proximity_sub = self.create_subscription(
                Float32, 
                '/proximity',
                self.front_proximity_callback, 
                10)
                
            self.left_distance_sub = self.create_subscription(
                Float32, 
                '/left_distance',
                self.left_distance_callback, 
                10)
                
            self.right_distance_sub = self.create_subscription(
                Float32, 
                '/right_distance',
                self.right_distance_callback, 
                10)
                
            # Subscribe to severity messages for detailed response
            self.front_severity_sub = self.create_subscription(
                String, 
                '/front_collision_severity',
                self.front_severity_callback, 
                10)
                
            self.left_severity_sub = self.create_subscription(
                String, 
                '/left_severity',
                self.left_severity_callback, 
                10)
                
            self.right_severity_sub = self.create_subscription(
                String, 
                '/right_severity',
                self.right_severity_callback, 
                10)
            
            # Initialize timer tracking variables with ROS time
            self.safety_timer_creation_time = self.get_clock().now()
            self.safety_timer_active = True
            self.safety_timer_call_count = 0
            
            # Create the safety timer using our improved method
            self.recreate_safety_timer()
            self.last_safety_check_time = self.get_clock().now()
            
            # Add a health check timer to ensure safety_timer is still running
            self.timer_health_check = self.create_timer(5.0, self.safety_timer_watchdog)
            
            # Add subscription for light control
            self.light_control_sub = self.create_subscription(
                Bool,
                '/roarm/light',
                self.light_control_callback,
                10
            )
            
            # Add timer to turn on the light after X seconds
            self.light_timer = self.create_timer(60.0, self.delayed_light_on)
            self.get_logger().info("Light will automatically turn on in 60 seconds")
            
            self.get_logger().info("RoArm hardware interface initialized")
            
            if self.enable_collision_avoidance:
                self.get_logger().info("Collision avoidance enabled")
            else:
                self.get_logger().warn("Collision avoidance disabled - robot will not react to obstacles")
            
            if self.enable_dynamic_adaptation:
                self.get_logger().info("Dynamic adaptation/external force control enabled")
            
            # Create subscription for dynamic adaptation toggle topic
            self.dynamic_adaptation_sub = self.create_subscription(
                Bool,
                '/dynamic_adaptation_toggle',
                self.dynamic_adaptation_toggle_callback,
                10
            )
            
            # Add subscription for position feedback
            self.position_feedback_sub = self.create_subscription(
                String,
                '/position_feedback',
                self.position_feedback_callback,
                10
            )
            
            # Initialize ROS time tracking for various features
            self.last_publish_time = self.get_clock().now()
            self.last_watchdog_check_time = self.get_clock().now()
            self.last_dema_pending_log = self.get_clock().now()
            self.last_adaptation_toggle_time = self.get_clock().now()
            
            # Track command significance
            self.significant_publish = False
            self.significant_command = False
            
            # Initialize recent command times tracking
            self.recent_command_times = []
            
            # Timer for DEMA re-enable checking
            self.dema_reenable_timer = None
            
        else:
            self.get_logger().error("Failed to initialize hardware interface")
    
    def publish_collision_status(self):
        """Publish current collision status for animation system."""
        if hasattr(self, 'collision_avoidance'):
            status_msg = String()
            status_msg.data = self.collision_avoidance.get_animation_collision_status()
            self.collision_status_publisher.publish(status_msg)
            
    def safety_timer_watchdog(self):
        """Check if the safety timer is still functioning properly"""
        try:
            current_time = self.get_clock().now()
            
            # Use a separate timestamp for watchdog checks
            if not hasattr(self, 'last_watchdog_check_time'):
                self.last_watchdog_check_time = current_time
                return  # Skip the first execution to establish baseline
                
            # Update the watchdog timestamp after the check
            self.last_watchdog_check_time = current_time
            
        except Exception as e:
            self.get_logger().error(f"Error in timer health check: {e}")
    
    def recreate_safety_timer(self):
        """Recreate the safety timer with better tracking"""
        try:
            # Generate a unique ID for this timer instance
            timer_id = self.get_clock().now().nanoseconds
            
            with self.safety_timer_lock:
                self.safety_timer_active = True
                self.last_safety_timer_id = timer_id
                self.safety_timer_creation_time = self.get_clock().now()
                self.safety_timer_call_count = 0
                
            # Create a new timer with a wrapper function that includes error handling
            self.safety_timer = self.create_timer(
                0.05,
                lambda: self.safety_timer_wrapper(timer_id)
            )
            
            self.get_logger().info(f"Created new safety monitoring timer (ID: {timer_id})")
            return True
            
        except Exception as e:
            self.get_logger().error(f"Failed to recreate safety timer: {e}")
            return False
    
    def safety_timer_wrapper(self, timer_id):
        """Wrapper for safety_monitor_callback with error handling and validation"""
        try:
            # Check if this is the current timer
            with self.safety_timer_lock:
                if timer_id != self.last_safety_timer_id:
                    # This callback is from an old timer - skip execution
                    return
                
                self.safety_timer_call_count += 1
                self.safety_timer_active = True
            
            # Call the actual safety monitor function
            self.safety_monitor_callback()
            
        except Exception as e:
            # Record the exception but keep the timer alive
            self.get_logger().error(f"Error in safety timer (ID {timer_id}): {e}")
            
            with self.safety_timer_lock:
                self.safety_timer_last_exception = str(e)
                
            import traceback
            self.get_logger().error(f"Stack trace: {traceback.format_exc()}")

    # Collision detection callbacks - delegate to collision_avoidance system
    def right_collision_callback(self, msg):
        self.collision_avoidance.handle_collision('right', msg.data)

    def left_collision_callback(self, msg):
        self.collision_avoidance.handle_collision('left', msg.data)

    def front_collision_callback(self, msg):
        self.collision_avoidance.handle_collision('front', msg.data)
    
    def front_proximity_callback(self, msg):
        self.collision_avoidance.update_distance('front', msg.data, is_proximity=True)

    def left_distance_callback(self, msg):
        self.collision_avoidance.update_distance('left', msg.data)
    
    def right_distance_callback(self, msg):
        self.collision_avoidance.update_distance('right', msg.data)
    
    def front_severity_callback(self, msg):
        self.collision_avoidance.update_severity('front', msg.data)
    
    def left_severity_callback(self, msg):
        self.collision_avoidance.update_severity('left', msg.data)
    
    def right_severity_callback(self, msg):
        self.collision_avoidance.update_severity('right', msg.data)

    def safety_monitor_callback(self):
        """Periodic callback to monitor safety and adjust motion if needed"""
        # Update the last check time at the beginning to track timer operation
        self.last_safety_check_time = self.get_clock().now()
        
        # Check if dynamic adaptation needs to be restored based on movement completion
        if self.enable_dynamic_adaptation and not self.dynamic_adaptation_active and self.dynamic_adaptation_pending_resume:
            current_time = self.get_clock().now()
            
            # Only check for re-enabling if we have a pending resume request
            if self.dynamic_adaptation_pending_resume:
                # Check if there's been no significant movement for a while
                time_since_command = (current_time - self.last_command_time).nanoseconds / 1e9
                
                # Only re-enable DEMA if the arm has been still for a while (3 seconds)
                # This indicates the movement that required DEMA off has completed
                if time_since_command > 3.0:
                    self.get_logger().info(f"Movement appears complete (no commands for {time_since_command:.2f}s) - re-enabling DEMA")
                    # Cancel any pending re-enable timer first
                    if self.dema_reenable_timer:
                        self.dema_reenable_timer.cancel()
                        self.dema_reenable_timer = None
                    # Re-enable DEMA
                    success = self.enable_dynamic_adaptation_mode()
                    if success:
                        self.get_logger().info("Successfully re-enabled dynamic adaptation mode")
                        self.dynamic_adaptation_pending_resume = False
                    else:
                        self.get_logger().error("Failed to re-enable dynamic adaptation mode, will retry later")
                        # Don't adjust the timer - we'll retry on the next callback
                else:
                    # Log this less frequently to avoid spamming the logs
                    time_since_log = (current_time - self.last_dema_pending_log).nanoseconds / 1e9
                    if time_since_log > 2.0:
                        self.get_logger().debug(f"DEMA re-enable pending: waiting for arm to be still (time since command: {time_since_command:.2f}s)")
                        self.last_dema_pending_log = current_time
        
        # Delegate collision avoidance monitoring to the collision_avoidance system
        try:
            # Update current joints in collision avoidance before safety check
            self.collision_avoidance.update_current_joints(self.current_joints)
            
            # Check activity time
            now = self.get_clock().now()
            time_since_publish = (now - self.last_publish_time).nanoseconds / 1e9
            
            # If we've published recently, update last activity time in collision avoidance,
            # but only if last_publish was due to a significant change
            if time_since_publish < 0.5 and getattr(self, 'significant_publish', False):
                self.collision_avoidance.last_activity_time = now
                self.get_logger().debug("Activity timestamp updated due to recent publish")
                
            # If we've received commands recently, also update activity time,
            # but only apply this based on the significant change flag
            time_since_command = (now - self.last_command_time).nanoseconds / 1e9
            
            if time_since_command < 1.0 and getattr(self, 'significant_command', False):
                self.collision_avoidance.last_activity_time = now
                self.get_logger().debug("Activity timestamp updated due to recent command")
            
            # Check if we're returning to home - this check should be prioritized
            if self.collision_avoidance.returning_to_home:
                # Ensure dynamic adaptation is disabled during return to home
                if self.enable_dynamic_adaptation and self.dynamic_adaptation_active:
                    self.get_logger().info("Disabling DEMA during return to home movement")
                    self.disable_dynamic_adaptation_mode()
                    # Set a flag to re-enable after the movement completes
                    self.dynamic_adaptation_pending_resume = True
                
                # Ensure the home position override is enforced
                if self.collision_avoidance.target_override_active and self.collision_avoidance.target_override_joints is not None:
                    self.send_safe_joint_command(
                        self.collision_avoidance.target_override_joints,
                        "Enforcing home position"
                    )
            
            # Run the regular safety monitor callback
            self.collision_avoidance.safety_monitor_callback()
        except Exception as e:
            self.get_logger().error(f"Error in collision avoidance callback: {e}")
            
            # Record the exception for watchdog tracking
            with self.safety_timer_lock:
                self.safety_timer_last_exception = str(e)
                
            # Add stack trace for better debugging
            import traceback
            self.get_logger().error(f"Stack trace: {traceback.format_exc()}")
            
            # This error could potentially make the timer stop working
            # Let's check if we need to restart it
            current_time = self.get_clock().now()
            time_since_creation = (current_time - self.safety_timer_creation_time).nanoseconds / 1e9
            if time_since_creation > 1.0:  # If timer is older than 1 second
                self.get_logger().warn("Safety timer exception might have corrupted timer - recreating")
                self.recreate_safety_timer()
        
        finally:
            # Always log completion to help track when callbacks are running
            self.get_logger().debug(f"Completed safety_monitor_callback")

    def estimate_joint_velocities(self):
        """Estimate current joint velocities based on recent commands"""
        current_time = self.get_clock().now()
        dt = (current_time - self.last_command_time).nanoseconds / 1e9
        
        if dt > 0 and dt < 1.0:  # Only calculate velocity for recent movements
            # Calculate approximate velocities
            self.joint_velocities = [(self.target_joints[i] - self.current_joints[i]) / dt 
                                     for i in range(len(self.current_joints))]
        else:
            self.joint_velocities = [0.0] * len(self.current_joints)
        
        # Update tracking variables - store as ROS Time for velocity calculations
        self.last_command_time = current_time
        self.current_joints = self.target_joints.copy()
        
        # Update the collision avoidance system with current velocities
        self.collision_avoidance.update_joint_velocities(self.joint_velocities)
    
    def is_connected(self):
        """Check if the serial connection is active"""
        return self.serial_manager.is_connected()
    
    def send_command(self, cmd_str, description=""):
        """Send a command to the robot arm using the serial manager."""
        return self.serial_manager.send_command(cmd_str, description)
    
    def enable_torque(self):
        """Enable torque on the arm using the serial manager."""
        return self.serial_manager.enable_torque()
    
    def disable_torque(self):
        """Disable torque on the arm using the serial manager."""
        return self.serial_manager.disable_torque()
    
    def initialize_arm(self):
        """Initialize the arm position using the serial manager."""
        return self.serial_manager.initialize_arm()

    def joint_states_callback(self, msg):
        """Handle joint states and send to hardware with collision avoidance."""
        if not self.is_connected():
            return
        
        try:
            # Update last movement time with ROS time
            self.last_command_time = self.get_clock().now()
            
            # Skip processing if collision avoidance system is returning to home position
            if self.collision_avoidance.returning_to_home:
                self.get_logger().info("Skipping joint_states_target - currently returning to home position")
                return
            
            # Track recent command times to help collision avoidance detect animations
            if not hasattr(self, 'recent_command_times'):
                self.recent_command_times = []
            
            # Store as float seconds for easier calculation
            current_seconds = self.get_clock().now().nanoseconds / 1e9
            self.recent_command_times.append(current_seconds)
            if len(self.recent_command_times) > 5:  # Keep last 5 command times
                self.recent_command_times.pop(0)
            
            # Explicitly update the collision avoidance system's recent command times
            self.collision_avoidance.recent_command_times = self.recent_command_times.copy()
            
            # Extract joint positions (in radians)
            names = msg.name
            positions = msg.position
            
            # Check for movement source in the velocity field (we use this as a hack to pass metadata)
            movement_source = "unknown"
            animation_name = None
            if len(msg.velocity) > 0:
                # The movement source is encoded as a special value in the first velocity slot
                encoded_source = int(msg.velocity[0])
                self.get_logger().debug(f"Received encoded movement source: {encoded_source}")
                if encoded_source == 1:
                    movement_source = "animation"
                    # Animation name is no longer passed via effort field
                    # Just notify collision avoidance that an animation is active
                    self.collision_avoidance.set_active_animation("unknown_animation")
                elif encoded_source == 2:
                    movement_source = "collision"
                elif encoded_source == 3:
                    movement_source = "user"
                elif encoded_source == 0:
                    movement_source = "idle"
                    # Clear any active animation tracking
                    self.collision_avoidance.clear_active_animation()
                
                # Store the last movement source
                previous_source = getattr(self, 'last_movement_source', None)
                self.last_movement_source = movement_source
                
                # Only log when the source changes to reduce log spam
                if previous_source != movement_source:
                    self.get_logger().info(f"Movement source changed: {previous_source or 'initial'} -> {movement_source}")
                    # If changing to animation or collision, disable DEMA
                    if movement_source in ["animation", "collision"]:
                        self.get_logger().info(f"Movement source is {movement_source} - disabling DEMA")
                        self.disable_dynamic_adaptation_mode()
                        # Set flag to re-enable after movement completes
                        self.dynamic_adaptation_pending_resume = True
                        self.dynamic_adaptation_last_disable_time = self.get_clock().now()
                            
                    # If changing to user mode, always enable DEMA
                    elif movement_source == "user" and self.enable_dynamic_adaptation :
                        self.get_logger().info(f"Movement source is user - enabling DEMA")
                        self.enable_dynamic_adaptation_mode()
                        self.dynamic_adaptation_pending_resume = False
                            
                    # If changing to idle and DEMA was pending resume, re-enable it
                    elif movement_source == "idle" and self.enable_dynamic_adaptation:
                        self.get_logger().info(f"Movement source is idle")
                        if self.dynamic_adaptation_pending_resume:
                            success = self.enable_dynamic_adaptation_mode()
                            if success:
                                self.dynamic_adaptation_pending_resume = False
                                self.get_logger().info("Successfully re-enabled DEMA")
                            else:
                                self.get_logger().error("Failed to re-enable DEMA")
            
            # Find indices for our joints (RoArm naming convention)
            indices = {}
            for i, name in enumerate(names):
                if name in self.get_joint_mappings().keys():
                    indices[self.get_joint_mappings()[name]] = i
            
            # Make sure we have at least the main joints
            required_joints = ['base', 'shoulder', 'elbow', 'hand']
            if not all(joint in indices for joint in required_joints):
                missing = [j for j in required_joints if j not in indices]
                self.get_logger().warn(f"Missing required joints: {missing}")
                return
            
            # Create target joint positions
            target_positions = [
                positions[indices['base']],
                positions[indices['shoulder']],
                positions[indices['elbow']],
                positions[indices['wrist']] if 'wrist' in indices else 0.0,
                positions[indices['hand']] if 'hand' in indices else 0.0
            ]
            
            # Check if this is a significant movement using our method
            previous_joints = getattr(self, 'target_joints', None)
            is_significant = self.is_significant_movement(previous_joints, target_positions, threshold=0.05)
            
            # Store the flag for use in other methods
            self.significant_command = is_significant
            
            # Store for velocity estimation
            self.target_joints = target_positions.copy()
            
            # Only update activity time if significant change
            if is_significant:
                self.collision_avoidance.last_activity_time = self.get_clock().now()
                self.get_logger().debug(f"Activity timestamp updated due to significant joint position change")
            
            # Update the collision avoidance system with new target
            self.collision_avoidance.update_target_joints(target_positions)
            
            # Log the incoming command
            self.get_logger().debug(f"Received joint_states_target: {[round(p, 2) for p in target_positions]}")
            
            # If movement source is animation, validate with collision system
            if movement_source == "animation" and self.enable_collision_avoidance:
                # Get animation name if available
                animation_name = self.collision_avoidance.current_animation_name
                
                # Validate the target positions
                is_safe, adjusted_positions, severity = self.collision_avoidance.validate_animation_keyframe(
                    target_positions, 
                    animation_name
                )
                
                if not is_safe:
                    self.get_logger().debug(f"Animation keyframe adjusted due to {severity} collision risk")
                    target_positions = adjusted_positions
                    
                    # Check if we should notify about preemption
                    if severity == "danger" and self.collision_avoidance.animation_preempted:
                        self.get_logger().warn(f"Animation interrupted due to {severity} collision")
            
            # Calculate the safe target position using collision avoidance
            safe_positions = self.collision_avoidance.get_effective_target_position(target_positions)
            
            # Apply collision avoidance and send command
            self.send_safe_joint_command(safe_positions, "Joint control")
            
            # Explicitly publish to joint_states to ensure our topic is active
            self.publish_actual_joint_states(self.current_joints)
            
        except Exception as e:
            self.get_logger().error(f"Error in joint_states_callback: {e}")
            # Add stack trace for better debugging
            import traceback
            self.get_logger().error(traceback.format_exc())

    def send_safe_joint_command(self, positions, description=""):
        """Send a joint command with safety checks applied"""
        if not self.is_connected():
            return False
            
        # Apply safety limits based on collision status
        if self.enable_collision_avoidance:
            safe_positions = self.collision_avoidance.apply_safety_limits(positions)
        else:
            safe_positions = positions
            
        try:
            # Only disable DEMA if it's active and the command is something other than regular joint control
            if self.enable_dynamic_adaptation and self.dynamic_adaptation_active and description != "Joint control":
                self.get_logger().info(f"Temporarily disabling DEMA for command: {description}")
                self.disable_dynamic_adaptation_mode()
                # Set a flag to re-enable after movement completes
                self.dynamic_adaptation_pending_resume = True
                self.dynamic_adaptation_last_disable_time = self.get_clock().now()
                
                # Schedule a ROS timer to check for re-enabling DEMA after 3 seconds
                if self.dema_reenable_timer is None or not self.dema_reenable_timer.is_ready():
                    self.dema_reenable_timer = self.create_timer(
                        3.0, 
                        self.check_dema_reenable
                    )
                    self.get_logger().info("Scheduled DEMA re-enable check in 3.0 seconds")
            
            # Use T:102 command for joint control in radians
            # From API: {"T":102,"base":0,"shoulder":0,"elbow":1.57,"hand":0.0,"spd":0,"acc":10}
            joint_cmd = {
                'T': 102,
                'base': safe_positions[0],
                'shoulder': safe_positions[1],
                'elbow': safe_positions[2],
                'roll': -1.5,
                'hand': 0.0,  # Gripper
                'spd': 0,  # Max speed
                'acc': 10  # Gentle acceleration
            }
            
            # Add wrist joint if present
            if len(safe_positions) > 3:
                joint_cmd['wrist'] = safe_positions[3]
            
            # Update current joints first with the safe positions
            self.current_joints = list(safe_positions)
            
            # Update the collision avoidance system with the current joint state
            self.collision_avoidance.update_current_joints(self.current_joints)
            
            # Publish the actual safe positions for visualization and monitoring
            self.publish_actual_joint_states(safe_positions)
            
            # Add more info for debugging
            self.get_logger().debug(f"Sending command to hardware: {description}")
            
            # Send command as JSON
            cmd_str = json.dumps(joint_cmd)
            result = self.send_command(cmd_str, description)
            
            return result
            
        except Exception as e:
            self.get_logger().error(f"Error sending safe joint commands: {e}")
            return False

    def check_dema_reenable(self):
        """Check if DEMA can be re-enabled after settling into a position"""
        try:
            if not self.enable_dynamic_adaptation:
                self.get_logger().warn("Dynamic adaptation is disabled - skipping re-enable check")
                return
            current_time = self.get_clock().now()
            time_since_disable = (current_time - self.dynamic_adaptation_last_disable_time).nanoseconds / 1e9
            
            # Use debug level for frequent checks, info only for significant events
            self.get_logger().debug(f"Checking if robot has settled to re-enable DEMA (disabled for {time_since_disable:.1f}s)")
            
            # Only proceed if DEMA is currently disabled but should be enabled
            if not self.dynamic_adaptation_active and self.dynamic_adaptation_pending_resume:
                # Check if we've been in position for at least 1 second
                # We'll use two approaches to determine if we're settled:
                # 1. Check time since last command
                # 2. Check if we're close to our target position
                
                # Calculate time since last command
                time_since_command = (current_time - self.last_command_time).nanoseconds / 1e9
                
                # Check if target and current positions are close (settled)
                is_settled = True
                if hasattr(self, 'target_joints') and hasattr(self, 'current_joints'):
                    for i in range(min(len(self.target_joints), len(self.current_joints))):
                        if abs(self.target_joints[i] - self.current_joints[i]) > 0.05:
                            is_settled = False
                            break
                
                # Re-enable DEMA if we've settled for at least 1 second
                if time_since_command >= 1.0 and is_settled:
                    self.get_logger().info("Robot appears to have settled into position - re-enabling DEMA")
                    success = self.enable_dynamic_adaptation_mode()
                    if success:
                        self.dynamic_adaptation_pending_resume = False
                        self.get_logger().info("Successfully re-enabled DEMA after settling")
                    else:
                        self.get_logger().error("Failed to re-enable DEMA, scheduling another check")
                        # Cancel any existing timer before creating a new one
                        if self.dema_reenable_timer:
                            self.dema_reenable_timer.cancel()
                        # Schedule another check after 0.5 seconds
                        self.dema_reenable_timer = self.create_timer(
                            0.5, 
                            self.check_dema_reenable
                        )
                else:
                    self.get_logger().debug(f"Robot not settled yet (time since command: {time_since_command:.1f}s, is_settled: {is_settled})")
                    # Cancel any existing timer before creating a new one
                    if self.dema_reenable_timer:
                        self.dema_reenable_timer.cancel()
                    # Schedule another check after 0.5 seconds
                    self.dema_reenable_timer = self.create_timer(
                        0.5, 
                        self.check_dema_reenable
                    )
                    
            # Cancel the timer if we're done
            if self.dema_reenable_timer and (not self.dynamic_adaptation_pending_resume or self.dynamic_adaptation_active):
                self.dema_reenable_timer.cancel()
                self.dema_reenable_timer = None
                
        except Exception as e:
            self.get_logger().error(f"Error in DEMA re-enable check: {e}")
            import traceback
            self.get_logger().error(traceback.format_exc())
            # Cancel timer on error to prevent spam
            if self.dema_reenable_timer:
                self.dema_reenable_timer.cancel()
                self.dema_reenable_timer = None

    def publish_current_joint_states(self):
        """Publish the current joint states periodically to ensure topic is active."""
        try:
            if hasattr(self, 'current_joints') and len(self.current_joints) > 0:
                # Record the publish time with ROS time
                self.last_publish_time = self.get_clock().now()
                
                # Always publish the joint states (important for ROS control)
                self.publish_actual_joint_states(self.current_joints)
                
                # Update current joints in collision avoidance
                self.collision_avoidance.update_current_joints(self.current_joints)
                
                # Check if we've reached home position when returning to home
                if (self.collision_avoidance.returning_to_home and 
                    self.collision_avoidance.target_override_active and 
                    self.collision_avoidance.target_override_joints is not None):
                    
                    # Check if we're close to home position
                    if all(abs(a - b) < 0.1 for a, b in zip(
                        self.current_joints, 
                        self.collision_avoidance.target_override_joints)):
                        
                        self.get_logger().info("Successfully reached home position")
                        self.collision_avoidance.returning_to_home = False
                        self.collision_avoidance.persistent_head_collision_active = False
                        
                        # Reset the activity timer to prevent immediately triggering idle timeout
                        self.collision_avoidance.last_activity_time = self.get_clock().now()
        except Exception as e:
            self.get_logger().error(f"Error in direct publish timer: {e}")

    def publish_actual_joint_states(self, positions):
        """Publish the actual joint positions after collision avoidance."""
        try:
            if not getattr(self, 'current_joints', []):
                self.get_logger().warn("Cannot publish joint states: current_joints not initialized or empty")
                return                
            # Add state tracking to avoid repeated identical messages
            if not hasattr(self, '_last_published_positions'):
                self._last_published_positions = None    
            
            # Create a joint state message with the actual positions
            msg = JointState()
            msg.header.stamp = self.get_clock().now().to_msg()
            
            # Use the appropriate joint names based on configuration
            if hasattr(self, 'use_hardware_joint_names') and self.use_hardware_joint_names:
                # Hardware interface expected joint names
                msg.name = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
            else:
                # URDF-based joint names
                msg.name = ['base_to_L1', 'L1_to_L2', 'L2_to_L3', 'L3_to_L4', 'hand']
            
            # Set the actual positions - ensure we have a Python list, not just an array reference
            msg.position = list(positions)
            
            # Check if positions are the same as previously published
            if (self._last_published_positions is not None and 
                len(self._last_published_positions) == len(positions) and
                all(abs(a - b) < 0.001 for a, b in zip(positions, self._last_published_positions))):
                # Skip logging the same position again
                pass
            else:
                # Add debug logging
                self.get_logger().debug(f"Publishing to /joint_states: {[round(p, 2) for p in positions]}")
            
            # Remember this position for next comparison
            self._last_published_positions = list(positions)
            
            # Update the last publish time with ROS time
            self.last_publish_time = self.get_clock().now()

            # Publish the message
            self.joint_states_publisher.publish(msg)
            
        except Exception as e:
            self.get_logger().error(f"Error publishing actual joint states: {e}")
            # Add stack trace for better debugging
            import traceback
            self.get_logger().error(traceback.format_exc())
    
    def get_joint_mappings(self):
        """Return mappings between ROS joint names and RoArm joint names."""
        return {
            'base': 'base',
            'shoulder': 'shoulder',
            'elbow': 'elbow',
            'wrist': 'wrist',
            'roll': 'roll',
            'hand': 'hand',
            # Add alternative mappings from your system if needed
            'base_to_L1': 'base',
            'L1_to_L2': 'shoulder',
            'L2_to_L3': 'elbow',
            'L3_to_L4': 'wrist',
            'L4_to_L5': 'roll'
        }
    
    def is_significant_movement(self, old_positions, new_positions, threshold=0.05):
        """
        Determine if a joint movement is significant enough to disable dynamic adaptation.
        
        Args:
            old_positions: Previous joint positions
            new_positions: New joint positions
            threshold: Minimum difference to consider significant (radians)
            
        Returns:
            bool: True if movement is significant
        """
        if not old_positions or not new_positions or len(old_positions) != len(new_positions):
            return True  # Consider any first movement or size mismatch as significant
            
        # Check each joint for significant changes
        for i, (old_pos, new_pos) in enumerate(zip(old_positions, new_positions)):
            if abs(old_pos - new_pos) > threshold:
                return True
                
        return False
    
    def destroy_node(self):
        """Clean up when node is destroyed."""
        self.get_logger().info("Shutting down hardware interface")
        
        # Cancel any active timers
        if hasattr(self, 'dema_reenable_timer') and self.dema_reenable_timer:
            self.dema_reenable_timer.cancel()
        
        # Disable dynamic adaptation mode if active
        if self.dynamic_adaptation_active:
            self.disable_dynamic_adaptation_mode()
        
        # Disable torque before closing
        if self.is_connected():
            self.disable_torque()
        
        # Close the serial connection
        if hasattr(self, 'serial_manager'):
            self.serial_manager.close()
            
        super().destroy_node()
    
    # Add methods to control dynamic adaptation
    def enable_dynamic_adaptation_mode(self):
        """Enable the dynamic external force adaptation mode"""
        try:
            with self.dynamic_adaptation_lock:
                
                # Log the parameters we're using for better debugging
                self.get_logger().info(f"DEMA parameters: base:{self.dynamic_adaptation_base_limit}, " +
                                     f"shoulder:{self.dynamic_adaptation_shoulder_limit}, " +
                                     f"elbow:{self.dynamic_adaptation_elbow_limit}, " +
                                     f"wrist:{self.dynamic_adaptation_wrist_limit}")
                
                # Critical fix: Make sure we're passing non-zero values to ensure DEMA works properly
                base_limit = max(1, self.dynamic_adaptation_base_limit)
                shoulder_limit = max(1, self.dynamic_adaptation_shoulder_limit)
                elbow_limit = max(1, self.dynamic_adaptation_elbow_limit)
                wrist_limit = max(1, self.dynamic_adaptation_wrist_limit)
                roll_limit = max(1, self.dynamic_adaptation_roll_limit)
                hand_limit = max(1, self.dynamic_adaptation_hand_limit)
                
                # Use SerialManager's built-in method with our configured limits
                success = self.serial_manager.set_dynamic_adaptation(
                    mode=1,
                    base=base_limit,
                    shoulder=shoulder_limit,
                    elbow=elbow_limit,
                    wrist=wrist_limit,
                    roll=roll_limit,
                    hand=hand_limit
                )
                
                if success:
                    self.dynamic_adaptation_active = True
                    self.get_logger().info("Dynamic adaptation mode enabled")
                else:
                    self.get_logger().error("Failed to enable dynamic adaptation mode")
                return success
        except Exception as e:
            self.get_logger().error(f"Error enabling dynamic adaptation mode: {e}")
            return False

    def disable_dynamic_adaptation_mode(self):
        """Disable the dynamic external force adaptation mode"""
        try:
            with self.dynamic_adaptation_lock:
                
                # Use SerialManager's built-in method to disable
                success = self.serial_manager.set_dynamic_adaptation(mode=0)
                
                if success:
                    self.dynamic_adaptation_active = False
                    self.dynamic_adaptation_last_disable_time = self.get_clock().now()
                    self.get_logger().info("Dynamic adaptation mode disabled")
                else:
                    self.get_logger().error("Failed to disable dynamic adaptation mode")
                return success
        except Exception as e:
            self.get_logger().error(f"Error disabling dynamic adaptation mode: {e}")
            return False

    def dynamic_adaptation_toggle_callback(self, msg):
        """Handle incoming toggle commands for dynamic adaptation"""
        try:
            # Add extra check to prevent rapid toggles
            current_time = self.get_clock().now()
            time_since_toggle = (current_time - self.last_adaptation_toggle_time).nanoseconds / 1e9
            
            if time_since_toggle < 2.0:
                self.get_logger().warn("Ignoring rapid dynamic adaptation toggle - wait at least 2 seconds between toggles")
                return
                
            self.last_adaptation_toggle_time = current_time
            
            if msg.data:  # Enable dynamic adaptation
                self.get_logger().info("Enabling dynamic adaptation mode via toggle")
                # Now enable dynamic adaptation mode
                success = self.enable_dynamic_adaptation_mode()
                if success:
                    self.get_logger().info("Dynamic adaptation successfully enabled via toggle")
                else:
                    self.get_logger().error("Failed to enable dynamic adaptation")
            else:  # Disable dynamic adaptation
                self.get_logger().info("Disabling dynamic adaptation mode via toggle")
                success = self.disable_dynamic_adaptation_mode()
                if success:
                    self.get_logger().info("Dynamic adaptation successfully disabled via toggle")
                else:
                    self.get_logger().error("Failed to disable dynamic adaptation")
        except Exception as e:
            self.get_logger().error(f"Error in dynamic adaptation toggle callback: {e}")
            # Try to restore state if error occurs
            try:
                self.disable_dynamic_adaptation_mode()
            except:
                pass

    def light_control_callback(self, msg):
        """Handle incoming light control commands"""
        try:
            if not self.is_connected():
                self.get_logger().warn("Cannot control light: Serial connection is not active")
                return
                
            # Set brightness value based on the boolean message
            brightness = 255 if msg.data else 0
            
            # Use SerialManager's built-in method to control the light
            success = self.serial_manager.control_light(brightness)
            
            if success:
                state = "ON" if msg.data else "OFF"
                self.get_logger().info(f"Light turned {state}")
            else:
                self.get_logger().error("Failed to control light")
        except Exception as e:
            self.get_logger().error(f"Error in light control callback: {e}")

    def delayed_light_on(self):
        """Turn on the light after startup delay"""
        try:
            self.get_logger().info("Auto-enabling light after startup delay")
            # Use SerialManager's built-in method to control the light
            success = self.serial_manager.control_light(255)  # Full brightness
            
            if success:
                self.get_logger().info("Light turned ON automatically")
            else:
                self.get_logger().error("Failed to turn on light automatically")
                
            # Cancel the timer so it doesn't fire again
            self.light_timer.cancel()
            
        except Exception as e:
            self.get_logger().error(f"Error in delayed light control: {e}")

    def position_feedback_callback(self, msg):
        """Process joint position feedback from hardware and update position tracking"""
        try:
            # Parse the position data from feedback message
            if isinstance(msg, String):
                feedback_data = json.loads(msg.data)
            else:
                feedback_data = json.loads(msg)
                
            # Check if this is a position feedback message
            if 'type' in feedback_data and feedback_data['type'] == 'position':
                # Extract the current positions
                positions = [
                    feedback_data.get('base', 0.0),
                    feedback_data.get('shoulder', 0.0),
                    feedback_data.get('elbow', 0.0),
                    feedback_data.get('wrist', 0.0),
                    feedback_data.get('hand', 0.0)
                ]
                
                # Check if positions are valid (not all zeros)
                if all(p == 0.0 for p in positions):
                    self.get_logger().debug("Ignoring invalid all-zero position feedback")
                    return
                
                # Check if this is a significant change from last reported position
                previous_joints = getattr(self, 'current_joints', None)
                is_significant = self.is_significant_movement(previous_joints, positions, threshold=0.05)
                
                # Update the current joints
                self.current_joints = positions
                
                # Update collision avoidance system with current position
                self.collision_avoidance.update_current_joints(positions)
                
                # Critical for DEMA: If in dynamic adaptation mode and position changed significantly
                # but we didn't issue the command ourselves, then this is user movement
                if (self.dynamic_adaptation_active and is_significant and 
                    not getattr(self, 'is_commanded_movement', False)):
                    self.get_logger().info("Detected user manual movement while DEMA is active")
                    # User is physically moving the arm, keep DEMA enabled to allow this
                    # Update the DEMA last active time to prevent timeout
                    self.dynamic_adaptation_last_disable_time = self.get_clock().now()
                    # Don't disable DEMA for user movements
                
                # Reset the commanded movement flag
                self.is_commanded_movement = False
                
                # Publish the updated joint states
                self.publish_actual_joint_states(positions)
                
                # Also update collision avoidance target if we're in physical teaching mode (DEMA)
                if self.dynamic_adaptation_active:
                    # In DEMA mode, update both target and current to match physical position
                    self.collision_avoidance.update_target_joints(positions)
                    self.target_joints = positions.copy()
                
        except Exception as e:
            self.get_logger().error(f"Error in position feedback callback: {e}")
            import traceback
            self.get_logger().error(traceback.format_exc())

def main(args=None):
    rclpy.init(args=args)
    
    # Create and run the node
    hardware_interface = RoArmHardwareInterface()
    
    if hardware_interface.serial_manager.is_connected():
        rclpy.spin(hardware_interface)
    
    # Clean up is handled in destroy_node
    hardware_interface.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()