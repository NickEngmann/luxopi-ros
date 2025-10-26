#!/usr/bin/env python3
#hardware_interface.py
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, String, Float32
import json
import threading
import time
import random
import numpy as np
from luxo_behaviors.serial_manager import SerialManager
from luxo_behaviors.behavior_coordinator import BehaviorCoordinator
from luxo_behaviors.state_machine import LuxoState  # Import for state enum only
from luxo_behaviors.shared_utils import StateUtils, TimeUtils  # Import shared utilities
from luxo_interfaces.srv import RequestStateTransition

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
        self.declare_parameter('idle_timeout_min', 5.0)  # Minimum idle timeout
        self.declare_parameter('idle_timeout_max', 16.0)  # Maximum idle timeout
        
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
        
        # Base joint limit parameters (in degrees, converted to radians internally)
        # Increased by 30° each direction for better voice following range
        self.declare_parameter('base_min_limit_deg', -290.0)  # Minimum base rotation in degrees (was -260.0)
        self.declare_parameter('base_max_limit_deg', 190.0)   # Maximum base rotation in degrees (was 160.0)
        self.declare_parameter('base_limit_buffer_deg', 10.0) # Buffer zone before hard limit in degrees
        self.declare_parameter('enable_base_wraparound', True) # Enable wraparound for collision avoidance
        
        # Add parameters for dynamic adaptation/external force control
        self.declare_parameter('enable_dynamic_adaptation', False)  # Default to disabled
        self.declare_parameter('dynamic_adaptation_base_limit', 60)  # Default torque limits
        self.declare_parameter('dynamic_adaptation_shoulder_limit', 750)
        self.declare_parameter('dynamic_adaptation_elbow_limit', 50)
        self.declare_parameter('dynamic_adaptation_wrist_limit', 50)
        self.declare_parameter('dynamic_adaptation_roll_limit', 50)
        self.declare_parameter('dynamic_adaptation_hand_limit', 50)
        
        # Add a new parameter for the DEMA movement source integration
        self.declare_parameter('enable_movement_source_integration', True)
        
        # Add parameter for initialization method
        self.declare_parameter('use_hardware_position_on_init', True)  # Whether to read actual position from hardware
        self.declare_parameter('init_position_timeout', 10.0)  # Timeout for getting initial position

        # Motor resistance detection parameters
        self.declare_parameter('enable_motor_resistance_detection', True)
        self.declare_parameter('motor_resistance_threshold', 0.15)  # Radians difference to detect resistance
        self.declare_parameter('motor_resistance_time_threshold', 1.0)  # Time in seconds before triggering
        self.declare_parameter('motor_resistance_consecutive_threshold', 5)  # Consecutive detections needed
        
        # Add initialization duration parameter
        self.declare_parameter('initialization_duration', 20.0)  # How long to stay in INITIALIZING state
        
        # Idle animation parameters
        self.declare_parameter('enable_idle_animations', True)
        self.declare_parameter('idle_animation_min_interval', 10.0)
        self.declare_parameter('idle_animation_max_interval', 20.0)
        self.declare_parameter('idle_time_before_animation', 6.0)
        
        # Add idle head variation parameters
        self.declare_parameter('enable_idle_head_variation', True)
        self.declare_parameter('idle_head_variation_interval', 5.0)  # Time between subtle movements
        self.declare_parameter('idle_head_base_rotation_range', 0.3)  # Max base rotation in radians
        self.declare_parameter('idle_head_look_up_range', 1.1)  # How much to look up (shoulder adjustment) - increased 15%
        self.declare_parameter('idle_head_look_down_range', 0.1)  # How much to look down - decreased 20%
        self.declare_parameter('idle_head_variation_speed', 3.5)  # Acceleration for head movements (reduced from 8.0)

        # Voice following parameters
        self.declare_parameter('enable_voice_following', True)  # Enable voice direction following
        self.declare_parameter('voice_follow_speed', 0.3)  # Speed of voice following movements
        self.declare_parameter('voice_follow_deadzone', 15.0)  # Deadzone in degrees for voice following
        self.declare_parameter('voice_follow_smoothing', 0.3)  # Smoothing factor for voice direction
        self.enable_idle_head_variation = self.get_parameter('enable_idle_head_variation').value
        self.idle_head_variation_interval = self.get_parameter('idle_head_variation_interval').value
        self.idle_head_base_rotation_range = self.get_parameter('idle_head_base_rotation_range').value
        self.idle_head_look_up_range = self.get_parameter('idle_head_look_up_range').value
        self.idle_head_look_down_range = self.get_parameter('idle_head_look_down_range').value
        self.idle_head_variation_speed = self.get_parameter('idle_head_variation_speed').value

        # Get parameters
        self.serial_port = self.get_parameter('serial_port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.enable_torque_on_start = self.get_parameter('enable_torque').value
        self.read_throttle = self.get_parameter('read_throttle').value
        self.enable_collision_avoidance = self.get_parameter('enable_collision_avoidance').value
        
        # Get base joint limit parameters and convert to radians
        self.base_min_limit = np.deg2rad(self.get_parameter('base_min_limit_deg').value)
        self.base_max_limit = np.deg2rad(self.get_parameter('base_max_limit_deg').value) 
        self.base_limit_buffer = np.deg2rad(self.get_parameter('base_limit_buffer_deg').value)
        self.enable_base_wraparound = self.get_parameter('enable_base_wraparound').value
        
        # Calculate soft limit zones
        self.base_soft_min = self.base_min_limit + self.base_limit_buffer
        self.base_soft_max = self.base_max_limit - self.base_limit_buffer
        
        self.get_logger().info(f"Base joint limits: {np.rad2deg(self.base_min_limit):.1f}° to {np.rad2deg(self.base_max_limit):.1f}°")
        self.get_logger().info(f"Base soft limits: {np.rad2deg(self.base_soft_min):.1f}° to {np.rad2deg(self.base_soft_max):.1f}°")
        self.get_logger().info(f"Base wraparound enabled: {self.enable_base_wraparound}")
        
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
        
        # Get initialization parameters
        self.use_hardware_position_on_init = self.get_parameter('use_hardware_position_on_init').value
        self.init_position_timeout = self.get_parameter('init_position_timeout').value
        
        # Get initialization duration
        self.initialization_duration = self.get_parameter('initialization_duration').value
        
        # Initialize timing variables for state tracking
        self.initialization_start_time = self.get_clock().now()
        
        # Track current state (received from global state manager)
        self.current_state = LuxoState.INITIALIZING
        self.state_lock = threading.Lock()
        self.collision_interrupted_state = None  # Track what state collision interrupted

        # State manager communication - using StateUtils pattern
        # Note: StateUtils will create the client as needed
        
        # Subscribe to state updates
        self.state_subscription = self.create_subscription(
            String,
            '/luxo/current_state',
            self.state_update_callback,
            10
        )
        
        # Publisher for node heartbeat
        self.heartbeat_publisher = self.create_publisher(
            String,
            '/luxo/node_heartbeat',
            10
        )
        
        # Heartbeat timer
        self.heartbeat_timer = self.create_timer(1.0, self.send_heartbeat)

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
        
        time.sleep(3) # Allow time before we connect to the serialport

        # Initialize the SerialManager
        self.serial_manager = SerialManager(
            self, 
            self.serial_port, 
            self.baud_rate, 
            self.read_throttle
        )
        
        # Connect to the serial port
        self.connection_active = self.serial_manager.connect()
        time.sleep(2)  # Allow time for connection to stabilize
        
        # Joint state tracking with fallback default values
        # These will be initialized from hardware before publishing begins
        self.current_joints = [0.0, 0.0, 0.0, 0.0, 0.0, 10.0, 0.0]  # base, shoulder, elbow, wrist, roll, acceleration, antenna
        self.target_joints = [0.0, 0.0, 0.0, 0.0, 0.0, 10.0, 0.0]  # Include default acceleration and antenna in target
        self.joint_velocities = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.last_command_time = self.get_clock().now()  # ROS time
        
        # Flag to track whether we have valid joint positions from hardware
        self.position_initialized = False

        # Motor resistance detection tracking
        self.enable_motor_resistance = self.get_parameter('enable_motor_resistance_detection').value
        self.motor_resistance_threshold = self.get_parameter('motor_resistance_threshold').value
        self.motor_resistance_time_threshold = self.get_parameter('motor_resistance_time_threshold').value
        self.motor_resistance_consecutive_threshold = self.get_parameter('motor_resistance_consecutive_threshold').value
        self.motor_resistance_detections = [0] * 5  # Track per joint
        self.motor_resistance_start_time = [None] * 5  # When resistance started per joint
        self.last_resistance_direction = [0.0] * 5  # Direction of last resistance
        
        # Add tracking variables for dynamic adaptation using ROS time
        self.dynamic_adaptation_active = False
        self.dynamic_adaptation_last_disable_time = self.get_clock().now()
        self.dynamic_adaptation_pending_resume = False
        self.dynamic_adaptation_lock = threading.Lock()
        self.dynamic_adaptation_timeout = 10.0  # Keep enabled for 10 seconds
        self.last_movement_source = "unknown"  # Track movement source for DEMA control
        self.initial_adaptation_setup = True  # Flag to track initial setup vs toggle
        self.dema_reenable_timer = None  # Initialize the timer variable
        self.last_publish_time = self.get_clock().now()  # Initialize publish time
        
        # Enable movement source integration
        self.enable_movement_source_integration = self.get_parameter('enable_movement_source_integration').value
        if self.enable_movement_source_integration:
            self.movement_source_publisher = self.create_publisher(
                String,
                '/roarm/movement_source',
                10
            )

        # Stay mode position freezing
        self.stay_frozen_position = None  # Frozen position when in STAY mode
        
        if self.connection_active:
            # Initialize the collision avoidance system (no state machine passed)
            self.behavior_coordinator = BehaviorCoordinator(
                self,  # Pass this node to the collision system
                self.send_safe_joint_command,  # Callback to send joint commands
                self.publish_actual_joint_states,  # Callback to publish joint states
            )
            
            # Pass idle animation parameters to collision avoidance
            self.behavior_coordinator.idle_animations_enabled = self.get_parameter('enable_idle_animations').value
            self.behavior_coordinator.min_idle_time_before_animation = self.get_parameter('idle_time_before_animation').value
            self.behavior_coordinator.idle_animation_interval = random.uniform(
                self.get_parameter('idle_animation_min_interval').value,
                self.get_parameter('idle_animation_max_interval').value
            )
            
            # Pass idle head variation parameters to collision avoidance
            self.behavior_coordinator.idle_head_variation_enabled = self.enable_idle_head_variation
            self.behavior_coordinator.idle_head_variation_interval = self.idle_head_variation_interval
            self.behavior_coordinator.idle_head_base_rotation_range = self.idle_head_base_rotation_range
            self.behavior_coordinator.idle_head_look_up_range = self.idle_head_look_up_range
            self.behavior_coordinator.idle_head_look_down_range = self.idle_head_look_down_range
            self.behavior_coordinator.idle_head_variation_speed = self.idle_head_variation_speed
            
            # Import and create animation command server with collision avoidance
            try:
                from luxo_behaviors.animation_command import AnimationCommandActionServer
                self.animation_command_server = AnimationCommandActionServer()
                self.animation_command_server.set_collision_avoidance(self.behavior_coordinator)
                self.animation_command_server.set_node(self)  # Pass node instead of state machine
                self.get_logger().info("Animation command server integrated with hardware interface")
            except Exception as e:
                self.get_logger().warn(f"Could not integrate animation command server: {e}")

            if self.enable_torque_on_start:
                self.get_logger().info("Torque enabled on startup")
                self.enable_torque()
            else:
                self.get_logger().info("Torque disabled on startup")
            time.sleep(1)  # Hardware initialization delay - keep as time.sleep
            
            # Configure dynamic adaptation for startup
            # Always start with dynamic adaptation disabled regardless of parameter
            self.disable_dynamic_adaptation_mode()
            self.get_logger().info("Dynamic adaptation disabled for initialization")
            time.sleep(1)  # Hardware initialization delay - keep as time.sleep
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
            
            # Health monitoring for joint state publishing
            self._last_joint_publish_time = time.time()
            self._joint_publish_count = 0
            self._joint_publish_health_timer = self.create_timer(30.0, self.check_joint_publish_health)
            
            # Publisher for collision status that animations can monitor
            self.collision_status_publisher = self.create_publisher(
                String,
                '/collision_status_for_animation',
                10
            )

            # Publisher for motor resistance status
            self.motor_resistance_publisher = self.create_publisher(
                String,
                '/motor_resistance/status',
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
            
            # Add publisher for light status
            self.light_status_publisher = self.create_publisher(
                Bool,
                '/roarm/light_status',
                10
            )
            
            # Initialize light status
            self.current_light_status = False
            
            
        else:
            self.get_logger().error("Failed to initialize hardware interface")
            self.request_state_transition(LuxoState.ERROR, priority=100)

    def send_heartbeat(self):
        """Send heartbeat to state manager"""
        try:
            # Format: "node_name:state:priority"
            heartbeat_msg = String()
            with self.state_lock:
                heartbeat_msg.data = f"hardware_interface:{self.current_state.name}:50"
            self.heartbeat_publisher.publish(heartbeat_msg)
        except Exception as e:
            self.get_logger().error(f"Error sending heartbeat: {e}")

    def state_update_callback(self, msg):
        """Handle state updates from global state manager"""
        try:
            new_state = LuxoState[msg.data.upper()]
            with self.state_lock:
                if self.current_state != new_state:
                    old_state = self.current_state
                    self.current_state = new_state
                    self.get_logger().info(f"State updated: {old_state.name} -> {new_state.name}")
                    self._handle_state_change(old_state, new_state)
        except KeyError:
            self.get_logger().warn(f"Unknown state received: {msg.data}")
        except Exception as e:
            self.get_logger().error(f"Error in state update callback: {e}")

    def _handle_state_change(self, old_state: LuxoState, new_state: LuxoState):
        """Handle state transitions locally"""
        # Clear motor resistance tracking on state changes (except collision states)
        if (self.enable_motor_resistance and
            new_state not in [LuxoState.COLLISION_AVOIDING, LuxoState.ESCAPE_MODE]):
            self.motor_resistance_detections = [0] * 5
            self.motor_resistance_start_time = [None] * 5
            self.get_logger().debug("Cleared motor resistance tracking due to state change")

        # Handle state-specific actions
        if new_state == LuxoState.INITIALIZING:
            self._on_enter_initializing()
        elif new_state == LuxoState.IDLE:
            self._on_enter_idle()
        elif new_state == LuxoState.ANIMATING:
            self._on_enter_animating()
        elif new_state == LuxoState.COLLISION_AVOIDING:
            self._on_enter_collision_avoiding()
        elif new_state == LuxoState.RETURNING_HOME:
            self._on_enter_returning_home()
        elif new_state == LuxoState.ESCAPE_MODE:
            self._on_enter_escape_mode()
        elif new_state == LuxoState.USER_CONTROL:
            self._on_enter_user_control()
        elif new_state == LuxoState.VOICE_FOLLOWING:
            self._on_enter_voice_following()
        elif new_state == LuxoState.PETTING:
            self._on_enter_petting()
        elif new_state == LuxoState.STAY:
            self._on_enter_stay()
        elif new_state == LuxoState.ERROR:
            self._on_enter_error()
        elif new_state == LuxoState.SHUTDOWN:
            self._on_enter_shutdown()

        # Handle state exit actions
        if old_state == LuxoState.ANIMATING:
            self._on_exit_animating()
        elif old_state == LuxoState.RETURNING_HOME:
            self._on_exit_returning_home()
        elif old_state == LuxoState.VOICE_FOLLOWING:
            self._on_exit_voice_following()
        elif old_state == LuxoState.PETTING:
            self._on_exit_petting()
        elif old_state == LuxoState.USER_CONTROL:
            self._on_exit_user_control()
        elif old_state == LuxoState.STAY:
            self._on_exit_stay()
        elif old_state == LuxoState.COLLISION_AVOIDING:
            self._on_exit_collision_avoiding()

    def request_state_transition(self, requested_state: LuxoState, priority: int = 50, force: bool = False, completion: bool = False):
        """Request a state transition from the global state manager using StateUtils"""
        return StateUtils.request_state_transition(self, requested_state, priority, force, completion)

    def is_in_state(self, *states: LuxoState) -> bool:
        """Check if currently in any of the given states"""
        with self.state_lock:
            return self.current_state in states

    def get_current_state(self) -> LuxoState:
        """Get current state"""
        with self.state_lock:
            return self.current_state

    # State callback implementations
    def _on_enter_initializing(self):
        """Called when entering INITIALIZING state."""
        self.get_logger().debug("Entering INITIALIZING state")
        self.get_logger().debug("Collision avoidance disabled during initialization")
        self.initialization_start_time = self.get_clock().now()

    def _on_enter_idle(self):
        """Called when entering IDLE state."""
        self.get_logger().debug("Entering IDLE state")
        self.dynamic_adaptation_pending_resume = False
    
    def _on_enter_animating(self):
        """Called when entering ANIMATING state."""
        self.get_logger().debug("Entering ANIMATING state")
    
    def _on_exit_animating(self):
        """Called when exiting ANIMATING state."""
        self.get_logger().debug("Exiting ANIMATING state")
    
    def _on_enter_collision_avoiding(self):
        """Called when entering COLLISION_AVOIDING state."""
        self.get_logger().debug("Entering COLLISION_AVOIDING state")
    
    def _on_enter_returning_home(self):
        """Called when entering RETURNING_HOME state."""
        self.get_logger().debug("Entering RETURNING_HOME state")
    
    def _on_exit_returning_home(self):
        """Called when exiting RETURNING_HOME state."""
        self.get_logger().debug("Exiting RETURNING_HOME state")
        # Re-enable DEMA if it was pending
        if self.dynamic_adaptation_pending_resume and self.enable_dynamic_adaptation:
            self.enable_dynamic_adaptation_mode()
            self.dynamic_adaptation_pending_resume = False
    
    def _on_exit_collision_avoiding(self):
        """Called when exiting COLLISION_AVOIDING state."""
        self.get_logger().debug("Exiting COLLISION_AVOIDING state")
        # Check if we should return to interrupted state
        if hasattr(self, 'collision_interrupted_state') and self.collision_interrupted_state:
            interrupted = self.collision_interrupted_state
            self.collision_interrupted_state = None
            self.get_logger().info(f"Collision resolved - returning to {interrupted.name}")
            # Use completion transition to return to interrupted state
            self.request_state_transition(interrupted, priority=50, completion=True)
    
    def _on_enter_escape_mode(self):
        """Called when entering ESCAPE_MODE state."""
        self.get_logger().debug("Entering ESCAPE_MODE state")
    
    def _on_enter_user_control(self):
        """Called when entering USER_CONTROL state."""
        self.get_logger().info("Entering USER_CONTROL state")
        # Store the position we want to maintain
        self.user_control_position = self.current_joints.copy() if hasattr(self, 'current_joints') and self.current_joints else None
        # Start a timer to maintain position during USER_CONTROL
        if not hasattr(self, 'user_control_timer') or self.user_control_timer is None:
            self.user_control_timer = self.create_timer(0.1, self._maintain_user_control_position)
    
    def _on_exit_user_control(self):
        """Called when exiting USER_CONTROL state."""
        self.get_logger().info("Exiting USER_CONTROL state")
        # Stop the position maintenance timer
        if hasattr(self, 'user_control_timer') and self.user_control_timer is not None:
            self.user_control_timer.cancel()
            self.user_control_timer = None
    
    def _maintain_user_control_position(self):
        """Maintain robot position during USER_CONTROL state."""
        if self.is_in_state(LuxoState.USER_CONTROL) and hasattr(self, 'user_control_position') and self.user_control_position:
            # Send the stored position to maintain it
            self.send_safe_joint_command(self.user_control_position, "USER_CONTROL position maintenance")

    def _on_enter_voice_following(self):
        """Called when entering VOICE_FOLLOWING state."""
        self.get_logger().info("🎤 Entering VOICE_FOLLOWING state - voice commands now have priority")
        # Voice following state is now active - behavior_coordinator will handle continuous updates
        # No position maintenance timer needed here since behavior_coordinator manages voice targets

    def _on_exit_voice_following(self):
        """Called when exiting VOICE_FOLLOWING state."""
        self.get_logger().info("Exiting VOICE_FOLLOWING state")
        # Voice following cleanup is handled by behavior_coordinator

    def _on_enter_petting(self):
        """Called when entering PETTING state."""
        self.get_logger().info("💕 Entering PETTING state")

    def _on_exit_petting(self):
        """Called when exiting PETTING state."""
        self.get_logger().info("Exiting PETTING state")

    def _on_enter_stay(self):
        """Called when entering STAY state - freeze current position."""
        # Capture current position as frozen position
        self.stay_frozen_position = self.current_joints[:5].copy()  # Only first 5 joints
        self.get_logger().info(f"🧊 STAY mode activated - position frozen at: {[round(p, 2) for p in self.stay_frozen_position]}")

    def _on_exit_stay(self):
        """Called when exiting STAY state."""
        self.get_logger().info("Exiting STAY mode - resuming normal operation")
        self.stay_frozen_position = None

    def _on_enter_error(self):
        """Called when entering ERROR state."""
        self.get_logger().error("Entering ERROR state")
        # Try to disable torque for safety
        try:
            self.disable_torque()
        except:
            pass
    
    def _on_enter_shutdown(self):
        """
        Called when entering SHUTDOWN state.
        Performs graceful shutdown sequence:
        1. Move to sleep position (synchronously, waiting for completion)
        2. Turn off lights and pixel ring
        3. Enable DEMA mode
        4. Disable torque
        5. Signal shutdown complete
        """
        self.get_logger().info("🛑 Entering SHUTDOWN state - beginning graceful shutdown sequence")

        try:
            # Step 1: Move to sleep position
            self.get_logger().info("📍 Step 1/5: Moving to sleep position...")

            # Sleep position from sleep animation (final position)
            # [base, shoulder, elbow, wrist, hand]
            sleep_position = [0.0, -1.75, 1.95, 1.4, -2.7]

            movement_sent = False
            if hasattr(self, 'serial_manager') and self.serial_manager and self.serial_manager.is_connected():
                # Send the sleep position command directly
                try:
                    self.send_safe_joint_command(sleep_position, "Shutdown - moving to sleep position")
                    movement_sent = True
                    self.get_logger().info("✅ Sleep position command sent")

                    # Wait for movement to complete with visual feedback
                    self.get_logger().info("⏳ Waiting for robot to reach sleep position...")

                    # Wait in small increments so we can provide feedback
                    for i in range(8):  # 8 * 0.5s = 4 seconds total
                        time.sleep(0.5)
                        if i % 2 == 0:
                            self.get_logger().info(f"   Movement progress: {(i+1)*12.5:.0f}%")

                    self.get_logger().info("✅ Sleep position reached")

                except Exception as e:
                    self.get_logger().error(f"❌ Failed to send sleep position command: {e}")
                    movement_sent = False

            if not movement_sent:
                self.get_logger().warn("⚠️  Hardware not available - skipping movement to sleep position")

            # Step 2: Turn off lights and pixel ring
            self.get_logger().info("💡 Step 2/5: Turning off lights and pixel ring...")
            try:
                if not hasattr(self, 'light_control_publisher'):
                    self.light_control_publisher = self.create_publisher(Bool, '/luxo/light_control', 10)
                if not hasattr(self, 'pixel_ring_control_publisher'):
                    self.pixel_ring_control_publisher = self.create_publisher(Bool, '/voice/pixel_ring_control', 10)

                # Turn off lights
                light_msg = Bool()
                light_msg.data = False
                self.light_control_publisher.publish(light_msg)

                # Turn off pixel ring
                pixel_msg = Bool()
                pixel_msg.data = False
                self.pixel_ring_control_publisher.publish(pixel_msg)

                self.get_logger().info("✅ Lights and pixel ring turned off")
            except Exception as e:
                self.get_logger().warn(f"⚠️  Failed to turn off lights: {e}")

            # Brief pause for message delivery
            time.sleep(0.2)

            # Step 3: Enable DEMA mode (makes robot compliant/limp)
            self.get_logger().info("🔧 Step 3/5: Enabling DEMA mode (robot will become compliant)...")
            if hasattr(self, 'serial_manager') and self.serial_manager and self.serial_manager.is_connected():
                try:
                    if hasattr(self, 'enable_dynamic_adaptation_mode'):
                        success = self.enable_dynamic_adaptation_mode()
                        if success:
                            self.get_logger().info("✅ DEMA mode enabled - robot is now compliant")
                        else:
                            self.get_logger().warn("⚠️  Failed to enable DEMA mode")
                    else:
                        self.get_logger().warn("⚠️  DEMA not available")
                except Exception as e:
                    self.get_logger().warn(f"⚠️  Failed to enable DEMA: {e}")
            else:
                self.get_logger().warn("⚠️  Hardware not available - skipping DEMA enable")

            # Step 4: Disable torque
            self.get_logger().info("⚡ Step 4/5: Disabling motor torque...")
            if hasattr(self, 'serial_manager') and self.serial_manager and self.serial_manager.is_connected():
                try:
                    if hasattr(self, 'disable_torque'):
                        self.disable_torque()
                        self.get_logger().info("✅ Motor torque disabled")
                except Exception as e:
                    self.get_logger().warn(f"⚠️  Failed to disable torque: {e}")
            else:
                self.get_logger().warn("⚠️  Hardware not available - skipping torque disable")

            # Step 5: Mark shutdown complete
            self.get_logger().info("🏁 Step 5/5: Shutdown sequence complete")
            self._shutdown_complete = True

        except Exception as e:
            self.get_logger().error(f"❌ Error during shutdown sequence: {e}")
            import traceback
            self.get_logger().error(f"Traceback: {traceback.format_exc()}")
            self._shutdown_complete = True  # Mark complete even on error
    
    def publish_collision_status(self):
        """Publish current collision status for animation system."""
        if hasattr(self, 'behavior_coordinator'):
            status_msg = String()
            status_msg.data = self.behavior_coordinator.get_animation_collision_status()
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

    # Collision detection callbacks - delegate to behavior_coordinator system
    def right_collision_callback(self, msg):
        if self.is_in_state(LuxoState.INITIALIZING):
            self.get_logger().debug("Ignoring collision during initialization phase")
            return
        # Store what we interrupted if collision is detected
        if msg.data and not self.is_in_state(LuxoState.COLLISION_AVOIDING):
            self.collision_interrupted_state = self.get_current_state()
        self.behavior_coordinator.handle_collision('right', msg.data)

    def left_collision_callback(self, msg):
        if self.is_in_state(LuxoState.INITIALIZING):
            self.get_logger().debug("Ignoring collision during initialization phase")
            return
        # Store what we interrupted if collision is detected
        if msg.data and not self.is_in_state(LuxoState.COLLISION_AVOIDING):
            self.collision_interrupted_state = self.get_current_state()
        self.behavior_coordinator.handle_collision('left', msg.data)

    def front_collision_callback(self, msg):
        if self.is_in_state(LuxoState.INITIALIZING):
            self.get_logger().debug("Ignoring collision during initialization phase")
            return
        # Store what we interrupted if collision is detected
        if msg.data and not self.is_in_state(LuxoState.COLLISION_AVOIDING):
            self.collision_interrupted_state = self.get_current_state()
        self.behavior_coordinator.handle_collision('front', msg.data)

    def front_proximity_callback(self, msg):
        # Don't process proximity during initialization
        if self.is_in_state(LuxoState.INITIALIZING):
            return
        self.behavior_coordinator.update_distance('front', msg.data, is_proximity=True)

    def left_distance_callback(self, msg):
        # Don't process distance during initialization
        if self.is_in_state(LuxoState.INITIALIZING):
            return
        self.behavior_coordinator.update_distance('left', msg.data)
    
    def right_distance_callback(self, msg):
        # Don't process distance during initialization
        if self.is_in_state(LuxoState.INITIALIZING):
            return
        self.behavior_coordinator.update_distance('right', msg.data)
    
    def front_severity_callback(self, msg):
        # Don't process severity during initialization
        if self.is_in_state(LuxoState.INITIALIZING):
            return
        self.behavior_coordinator.update_severity('front', msg.data)
    
    def left_severity_callback(self, msg):
        # Don't process severity during initialization
        if self.is_in_state(LuxoState.INITIALIZING):
            return
        self.behavior_coordinator.update_severity('left', msg.data)
    
    def right_severity_callback(self, msg):
        # Don't process severity during initialization
        if self.is_in_state(LuxoState.INITIALIZING):
            return
        self.behavior_coordinator.update_severity('right', msg.data)

    def safety_monitor_callback(self):
        """Periodic callback to monitor safety and adjust motion if needed"""
        if self.is_in_state(LuxoState.INITIALIZING):
            self.get_logger().debug("Skipping safety monitoring during initialization")
            return
            
        # Update the last check time at the beginning to track timer operation
        self.last_safety_check_time = self.get_clock().now()
        
        # Delegate collision avoidance monitoring to the behavior_coordinator system
        try:
            # Update current joints in collision avoidance before safety check
            self.behavior_coordinator.update_current_joints(self.current_joints)
            
            # Check activity time
            now = self.get_clock().now()
            time_since_publish = (now - self.last_publish_time).nanoseconds / 1e9 if hasattr(self, 'last_publish_time') else float('inf')
            
            # If we've published recently, update last activity time in collision avoidance,
            # but only if last_publish was due to a significant change
            if time_since_publish < 0.5 and getattr(self, 'significant_publish', False):
                self.behavior_coordinator.last_activity_time = now
                self.get_logger().debug("Activity timestamp updated due to recent publish")
                
            # If we've received commands recently, also update activity time,
            # but only apply this based on the significant change flag
            time_since_command = (now - self.last_command_time).nanoseconds / 1e9
            
            if time_since_command < 1.0 and getattr(self, 'significant_command', False):
                self.behavior_coordinator.last_activity_time = now
                self.get_logger().debug("Activity timestamp updated due to recent command")
            
            # Check if we're returning to home - this check should be prioritized
            if self.is_in_state(LuxoState.RETURNING_HOME):
                # Ensure dynamic adaptation is disabled during return to home
                if self.enable_dynamic_adaptation and self.dynamic_adaptation_active:
                    self.get_logger().info("Disabling DEMA during return to home movement")
                    self.disable_dynamic_adaptation_mode()
                    # Set a flag to re-enable after the movement completes
                    self.dynamic_adaptation_pending_resume = True
                
                # Ensure the home position override is enforced
                if self.behavior_coordinator.target_override_active and self.behavior_coordinator.target_override_joints is not None:
                    self.send_safe_joint_command(
                        self.behavior_coordinator.target_override_joints,
                        "Enforcing home position"
                    )
            
            # Run the regular safety monitor callback
            self.behavior_coordinator.safety_monitor_callback()
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
        self.behavior_coordinator.update_joint_velocities(self.joint_velocities)
    
    def is_connected(self):
        """Check if the serial connection is active"""
        return self.serial_manager.is_connected()
    
    def send_command(self, cmd_str, description="", timeout=3.0):
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
        
        # Allow basic joint commands during initialization but skip collision avoidance
        if self.is_in_state(LuxoState.INITIALIZING):
            self.get_logger().debug("Processing joint command during initialization (collision avoidance disabled)")
            # Process the command but skip collision avoidance entirely
            try:
                # Extract joint positions (in radians)
                names = msg.name
                positions = msg.position
                
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
                
                # Check if we have acceleration value (6th position)
                if len(positions) > 5:
                    target_positions.append(positions[5])

                # Check if we have antenna value (7th position)
                if len(positions) > 6:
                    target_positions.append(positions[6])
                    self.get_logger().debug(f"Received antenna value during init: {positions[6]:.3f}")

                # Send command directly without collision avoidance during initialization
                self.send_safe_joint_command(target_positions, "Joint control (initialization)")
                
                return
                
            except Exception as e:
                self.get_logger().error(f"Error in joint_states_callback during initialization: {e}")
                return
        
        try:
            # Update last movement time with ROS time
            self.last_command_time = self.get_clock().now()
            
            # Check if we're in RETURNING_HOME state - add timeout check
            if self.is_in_state(LuxoState.RETURNING_HOME):
                # Check for stuck RETURNING_HOME state
                if hasattr(self.behavior_coordinator, 'returning_to_home_start_time'):
                    current_time = self.get_clock().now()
                    time_in_returning_home = (current_time - self.behavior_coordinator.returning_to_home_start_time).nanoseconds / 1e9
                    
                    # If stuck in RETURNING_HOME for more than 30 seconds, force clear
                    if time_in_returning_home > 30.0:
                        self.get_logger().warn(f"Stuck in RETURNING_HOME state for {time_in_returning_home:.1f}s - force clearing")
                        # Force clear collision avoidance flags
                        self.behavior_coordinator.target_override_active = False
                        self.behavior_coordinator.target_override_joints = None
                        self.behavior_coordinator.home_position_stage = 1
                        # Force transition to IDLE
                        self.request_state_transition(LuxoState.IDLE, priority=100, force=True)
                    else:
                        self.get_logger().debug("Skipping joint_states_target - currently returning to home position")
                        return
                else:
                    self.get_logger().debug("Skipping joint_states_target - currently returning to home position")
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
            self.behavior_coordinator.recent_command_times = self.recent_command_times.copy()
            
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
                    # Only request transition if not already in ANIMATING state
                    if not self.is_in_state(LuxoState.ANIMATING):
                        self.get_logger().info("Animation starting - requesting transition to ANIMATING state")
                        StateUtils.request_state_transition(self, LuxoState.ANIMATING, priority=50)
                    # Animation name is no longer passed via effort field
                    # Just notify collision avoidance that an animation is active
                    self.behavior_coordinator.set_active_animation("unknown_animation")
                    
                    # IMPORTANT: Clear any stuck flags when animation starts
                    if hasattr(self.behavior_coordinator, 'target_override_active'):
                        if self.behavior_coordinator.target_override_active:
                            self.get_logger().info("Clearing target override for animation start")
                            self.behavior_coordinator.target_override_active = False
                            self.behavior_coordinator.target_override_joints = None
                    
                elif encoded_source == 2:
                    movement_source = "collision"
                    # Only request transition if not already in COLLISION_AVOIDING state
                    if not self.is_in_state(LuxoState.COLLISION_AVOIDING):
                        self.get_logger().info("Collision detected - requesting transition to COLLISION_AVOIDING state")
                        StateUtils.request_state_transition(self, LuxoState.COLLISION_AVOIDING, priority=80)
                elif encoded_source == 3:
                    movement_source = "user"
                    # Only request transition if not already in USER_CONTROL state
                    if not self.is_in_state(LuxoState.USER_CONTROL):
                        self.get_logger().info("User control detected - requesting transition to USER_CONTROL state")
                        StateUtils.request_state_transition(self, LuxoState.USER_CONTROL, priority=70)
                elif encoded_source == 0:
                    movement_source = "idle"
                    # Clear any active animation tracking
                    self.behavior_coordinator.clear_active_animation()
                    
                    # Use completion transition when returning from states
                    if self.is_in_state(LuxoState.ANIMATING):
                        self.get_logger().info(f"Animation completed - requesting completion transition")
                        # Return to IDLE after animation
                        StateUtils.request_state_transition(self, LuxoState.IDLE, priority=30, completion=True)
                    elif self.is_in_state(LuxoState.COLLISION_AVOIDING):
                        # Check if we should return to interrupted state
                        if hasattr(self, 'collision_interrupted_state') and self.collision_interrupted_state:
                            self.get_logger().info(f"Collision resolved - returning to {self.collision_interrupted_state.name}")
                            StateUtils.request_state_transition(self, self.collision_interrupted_state, priority=50, completion=True)
                            self.collision_interrupted_state = None
                        else:
                            # Default to IDLE if no interrupted state
                            self.get_logger().info(f"Collision resolved - returning to IDLE")
                            StateUtils.request_state_transition(self, LuxoState.IDLE, priority=30, completion=True)

                
                # Store the last movement source
                previous_source = getattr(self, 'last_movement_source', None)
                self.last_movement_source = movement_source
                
                # Only log when the source changes to reduce log spam
                if previous_source != movement_source:
                    self.get_logger().info(f"Movement source changed: {previous_source or 'initial'} -> {movement_source}")
                    # If changing to animation or collision, disable DEMA
                    if movement_source in ["animation", "collision"]  and self.enable_dynamic_adaptation:
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
            
            # Check if we have acceleration value (6th position)
            acceleration = None
            if len(positions) > 5:
                acceleration = positions[5]
                # Add acceleration to target_positions
                target_positions.append(acceleration)
                self.get_logger().debug(f"Received acceleration value: {acceleration}")

            # Check if we have antenna value (7th position)
            antenna = None
            if len(positions) > 6:
                antenna = positions[6]
                # Add antenna to target_positions
                target_positions.append(antenna)
                self.get_logger().debug(f"Received antenna value: {antenna:.3f}")

            # Check if this is a significant movement using our method
            previous_joints = getattr(self, 'target_joints', None)
            is_significant = self.is_significant_movement(previous_joints, target_positions[:5], threshold=0.05)  # Only check joint positions, not acceleration
            
            # Store the flag for use in other methods
            self.significant_command = is_significant
            
            # Store for velocity estimation (include acceleration if present)
            self.target_joints = target_positions.copy()
            
            # Only update activity time if significant change
            if is_significant:
                self.behavior_coordinator.last_activity_time = self.get_clock().now()
                self.get_logger().debug(f"Activity timestamp updated due to significant joint position change")
            
            # Update the collision avoidance system with new target (only joint positions)
            self.behavior_coordinator.update_target_joints(target_positions[:5])
            
            # Log the incoming command
            accel_info = f", accel: {acceleration}" if acceleration is not None else ""
            self.get_logger().debug(f"Received joint_states_target: {[round(p, 2) for p in target_positions[:5]]}{accel_info}")
            
            # If movement source is animation, validate with collision system
            if movement_source == "animation" and self.enable_collision_avoidance:
                # Get animation name if available
                animation_name = self.behavior_coordinator.current_animation_name
                
                # Validate the target positions (only joint positions)
                is_safe, adjusted_positions, severity = self.behavior_coordinator.validate_animation_keyframe(
                    target_positions[:5], 
                    animation_name
                )
                
                if not is_safe:
                    self.get_logger().debug(f"Animation keyframe adjusted due to {severity} collision risk")
                    # Update only joint positions, keep acceleration
                    target_positions[:5] = adjusted_positions
                    
                    # Check if we should notify about preemption
                    if severity == "danger" and self.behavior_coordinator.animation_preempted:
                        self.get_logger().warn(f"Animation interrupted due to {severity} collision")
            
            # Calculate the safe target position using collision avoidance (only joint positions)
            safe_positions = self.behavior_coordinator.get_effective_target_position(target_positions[:5])
            
            # Add acceleration back if it was provided
            if acceleration is not None:
                safe_positions = list(safe_positions) + [acceleration]

            # Add antenna back if it was provided
            if antenna is not None:
                safe_positions = list(safe_positions) + [antenna]

            # Clear motor resistance tracking for commanded movements
            if self.enable_motor_resistance:
                # Only clear for joints that are actively being commanded to move
                for i in range(min(5, len(target_positions))):
                    if i < len(self.current_joints) and abs(target_positions[i] - self.current_joints[i]) > 0.05:
                        self.motor_resistance_detections[i] = 0
                        self.motor_resistance_start_time[i] = None

            # Apply collision avoidance and send command
            self.send_safe_joint_command(safe_positions, "Joint control")
            
            # Explicitly publish to joint_states to ensure our topic is active
            self.publish_actual_joint_states(self.current_joints)
            
        except Exception as e:
            self.get_logger().error(f"Error in joint_states_callback: {e}")
            # Add stack trace for better debugging
            import traceback
            self.get_logger().error(traceback.format_exc())

    def enforce_base_joint_limits(self, positions, context="general"):
        """
        Enforce base joint limits with wraparound support.
        
        Args:
            positions: List of joint positions [base, shoulder, elbow, wrist, hand, ...]
            context: Context for decision making ("collision", "animation", "general", "voice")
            
        Returns:
            Tuple of (safe_positions, wraparound_needed, limit_reached)
        """
        if len(positions) == 0:
            return positions, False, False
            
        safe_positions = positions.copy()
        base_position = safe_positions[0]
        wraparound_needed = False
        limit_reached = False
        
        # Check if we're at or beyond hard limits
        if base_position <= self.base_min_limit:
            limit_reached = True
            if context == "collision" and self.enable_base_wraparound:
                # For collision avoidance, try wraparound to the other side
                wraparound_target = self.base_max_limit - 0.2  # Start near max limit
                self.get_logger().warn(f"Base at min limit ({np.rad2deg(base_position):.1f}°) - wraparound to {np.rad2deg(wraparound_target):.1f}°")
                safe_positions[0] = wraparound_target
                wraparound_needed = True
            else:
                # Hard stop at minimum limit
                safe_positions[0] = self.base_min_limit + 0.01  # Small buffer
                self.get_logger().debug(f"Base position clamped to min limit: {np.rad2deg(safe_positions[0]):.1f}°")
                
        elif base_position >= self.base_max_limit:
            limit_reached = True
            if context == "collision" and self.enable_base_wraparound:
                # For collision avoidance, try wraparound to the other side
                wraparound_target = self.base_min_limit + 0.2  # Start near min limit
                self.get_logger().debug(f"Base at max limit ({np.rad2deg(base_position):.1f}°) - wraparound to {np.rad2deg(wraparound_target):.1f}°")
                safe_positions[0] = wraparound_target
                wraparound_needed = True
            else:
                # Hard stop at maximum limit
                safe_positions[0] = self.base_max_limit - 0.01  # Small buffer
                self.get_logger().debug(f"Base position clamped to max limit: {np.rad2deg(safe_positions[0]):.1f}°")
                
        # Check soft limits for warnings
        elif base_position <= self.base_soft_min:
            self.get_logger().debug(f"Base approaching min limit: {np.rad2deg(base_position):.1f}°")
            if context == "animation":
                # For animations, be more conservative and stay within soft limits
                safe_positions[0] = self.base_soft_min
                
        elif base_position >= self.base_soft_max:
            self.get_logger().debug(f"Base approaching max limit: {np.rad2deg(base_position):.1f}°")
            if context == "animation":
                # For animations, be more conservative and stay within soft limits
                safe_positions[0] = self.base_soft_max
        
        return safe_positions, wraparound_needed, limit_reached
    
    def is_base_near_limit(self, threshold_deg=20.0):
        """
        Check if base is near any limit.
        
        Args:
            threshold_deg: Threshold in degrees to consider "near"
            
        Returns:
            Tuple of (near_min, near_max, distance_to_closest_limit_deg)
        """
        if not hasattr(self, 'current_joints') or len(self.current_joints) == 0:
            return False, False, float('inf')
            
        current_base = self.current_joints[0]
        threshold_rad = np.deg2rad(threshold_deg)
        
        dist_to_min = current_base - self.base_min_limit
        dist_to_max = self.base_max_limit - current_base
        
        near_min = dist_to_min <= threshold_rad
        near_max = dist_to_max <= threshold_rad
        
        closest_dist_deg = np.rad2deg(min(dist_to_min, dist_to_max))
        
        return near_min, near_max, closest_dist_deg
    
    def calculate_wraparound_path(self, current_base, target_base):
        """
        Calculate if wraparound would be more efficient and safe.
        
        Returns:
            Tuple of (use_wraparound, intermediate_positions)
        """
        if not self.enable_base_wraparound:
            return False, []
            
        # Calculate direct path
        direct_distance = abs(target_base - current_base)
        
        # Calculate wraparound distances
        if current_base > 0:  # Near max limit
            wraparound_distance = (self.base_max_limit - current_base) + (target_base - self.base_min_limit)
        else:  # Near min limit  
            wraparound_distance = (current_base - self.base_min_limit) + (self.base_max_limit - target_base)
        
        # Use wraparound if it's significantly shorter and we're near a limit
        near_min, near_max, _ = self.is_base_near_limit(30.0)  # 30 degree threshold
        
        if (near_min or near_max) and wraparound_distance < direct_distance * 0.7:
            # Generate intermediate positions for smooth wraparound
            if current_base > 0:  # Wraparound via min limit
                intermediate = [
                    current_base + 0.3,  # Move slightly away from limit first
                    self.base_min_limit + 0.2,  # Jump to other side
                    target_base
                ]
            else:  # Wraparound via max limit
                intermediate = [
                    current_base - 0.3,  # Move slightly away from limit first
                    self.base_max_limit - 0.2,  # Jump to other side
                    target_base
                ]
            return True, intermediate
            
        return False, []

    def send_safe_joint_command(self, positions, description=""):
        """Send a joint command with safety checks applied"""
        if not self.is_connected():
            return False

        # STAY MODE GATE: If in STAY mode, ignore all incoming commands and resend frozen position
        if self.is_in_state(LuxoState.STAY) and self.stay_frozen_position is not None:
            self.get_logger().debug(f"STAY mode active - blocking command: '{description}' and resending frozen position")
            # Override positions with frozen position
            positions = self.stay_frozen_position.copy()
            # Add default values for acceleration and antenna if needed
            if len(positions) < 6:
                positions = positions + [10.0]  # Default acceleration
            if len(positions) < 7:
                positions = positions + [1.5]  # Default antenna position
            description = "STAY mode - position frozen"

        time.sleep(0.05)  # delay between commands

        # Apply base joint limits first
        context = "general"
        if "collision" in description.lower():
            context = "collision"
        elif "animation" in description.lower():
            context = "animation"
        elif "voice" in description.lower():
            context = "voice"
            
        safe_positions, wraparound_needed, limit_reached = self.enforce_base_joint_limits(positions, context)
        
        if limit_reached and not wraparound_needed:
            self.get_logger().debug(f"Base joint limit reached for: {description}")
            
        if wraparound_needed:
            self.get_logger().info(f"Executing base wraparound for: {description}")

        # Apply collision avoidance safety limits
        if self.enable_collision_avoidance:
            safe_positions = self.behavior_coordinator.apply_safety_limits(safe_positions)
        
        try:
            # Only disable DEMA if it's active and the command is something other than regular joint control
            if self.enable_dynamic_adaptation and self.dynamic_adaptation_active and description != "Joint control":
                self.get_logger().info(f"Temporarily disabling DEMA for command: {description}")
                self.disable_dynamic_adaptation_mode()
                # Set a flag to re-enable after movement completes
                self.dynamic_adaptation_pending_resume = True
                self.dynamic_adaptation_last_disable_time = self.get_clock().now()
                
                # Schedule a ROS timer to check for re-enabling DEMA after 3 seconds
                if not hasattr(self, 'dema_reenable_timer') or self.dema_reenable_timer is None:
                    self.dema_reenable_timer = self.create_timer(
                        3.0, 
                        self.check_dema_reenable
                    )
                    self.get_logger().info("Scheduled DEMA re-enable check in 3.0 seconds")
            
            # Determine roll value with boundary checking
            if len(safe_positions) > 4:
                roll_value = safe_positions[4]
                # Check if roll value is within safe boundaries (-2.5 to -0.5)
                if roll_value < -2.5 or roll_value > -0.5:
                    roll_value = -1.5  # Set to safe default if out of bounds
            else:
                roll_value = -1.5  # Default safe position

            if len(safe_positions) > 5:
                acc_val = safe_positions[5]
                # Check if acc_value is within safe boundaries (-2.5 to -0.5)
                if acc_val < 10 or acc_val > 22.5:
                    acc_val = 10  # Set to safe default if out of bounds
            else:
                acc_val = 10  # Default safe position

            # Determine hand/antenna value if provided (7th element)
            if len(safe_positions) > 6:
                hand_value = safe_positions[6]
                # Antenna safe range: 0.5 to 2.6 radians for realistic movement
                # This provides good visible movement without extremes
                if hand_value < 0.5:
                    hand_value = 0.5  # Minimum realistic position
                elif hand_value > 2.6:
                    hand_value = 2.6  # Maximum realistic position
            else:
                hand_value = 1.5  # Default neutral position for antenna (mid-range)

            joint_cmd = {
                'T': 102,
                'base': safe_positions[0],
                'shoulder': safe_positions[1],
                'elbow': safe_positions[2],
                'roll': roll_value,  # Use boundary-checked roll value
                'hand': hand_value,  # Gripper/antenna value from animations
                'spd': 0,  #  Speed
                'acc': acc_val  # Acceleration
            }
            
            # Add wrist joint if present
            if len(safe_positions) > 3:
                joint_cmd['wrist'] = safe_positions[3]
            
            # Update current joints first with the safe positions
            self.current_joints = list(safe_positions)
            
            # Update the collision avoidance system with the current joint state
            self.behavior_coordinator.update_current_joints(self.current_joints)
            
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
                # Cancel any existing timer since DEMA is disabled
                if self.dema_reenable_timer:
                    self.dema_reenable_timer.cancel()
                    self.dema_reenable_timer = None
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
                time_since_command = TimeUtils.get_time_since(self, self.last_command_time)
                
                # Check if target and current positions are close (settled)
                is_settled = True
                if hasattr(self, 'target_joints') and hasattr(self, 'current_joints'):
                    for i in range(min(len(self.target_joints), len(self.current_joints))):
                        if abs(self.target_joints[i] - self.current_joints[i]) > 0.05:
                            is_settled = False
                            break
                
                # Re-enable DEMA if we've settled for at least 1 second and we're in IDLE state
                if time_since_command >= 1.0 and is_settled and self.is_in_state(LuxoState.IDLE):
                    self.get_logger().info("Robot appears to have settled into position - re-enabling DEMA")
                    success = self.enable_dynamic_adaptation_mode()
                    if success:
                        self.dynamic_adaptation_pending_resume = False
                        self.get_logger().info("Successfully re-enabled DEMA after settling")
                        # Cancel timer since we're done
                        if self.dema_reenable_timer:
                            self.dema_reenable_timer.cancel()
                            self.dema_reenable_timer = None
                    else:
                        self.get_logger().error("Failed to re-enable DEMA, scheduling another check")
                        # Schedule another check after 0.5 seconds
                        if self.dema_reenable_timer:
                            self.dema_reenable_timer.cancel()
                        self.dema_reenable_timer = self.create_timer(
                            0.5, 
                            self.check_dema_reenable
                        )
                else:
                    self.get_logger().debug(f"Robot not settled yet (time since command: {time_since_command:.1f}s, is_settled: {is_settled}, state: {self.get_current_state().name})")
                    # Schedule another check after 0.5 seconds only if we don't have an active timer
                    if not self.dema_reenable_timer:
                        self.dema_reenable_timer = self.create_timer(
                            0.5, 
                            self.check_dema_reenable
                        )
            else:
                # Cancel the timer if we're done
                if self.dema_reenable_timer:
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
                
                # Health monitoring
                self._last_joint_publish_time = time.time()
                self._joint_publish_count += 1
                
                # Always publish the joint states (important for ROS control)
                self.publish_actual_joint_states(self.current_joints)
                
                # Update current joints in collision avoidance
                self.behavior_coordinator.update_current_joints(self.current_joints)
                
                # Check if we've reached home position when returning to home
                if (self.is_in_state(LuxoState.RETURNING_HOME) and 
                    self.behavior_coordinator.target_override_active and 
                    self.behavior_coordinator.target_override_joints is not None):
                    
                    # Check if we're close to home position
                    if all(abs(a - b) < 0.1 for a, b in zip(
                        self.current_joints, 
                        self.behavior_coordinator.target_override_joints)):
                        
                        # Add throttling for stage 1 logging
                        if self.behavior_coordinator.home_position_stage == 1:
                            # Force the collision avoidance system to check for stage transition
                            # by calling get_effective_target_position which contains the transition logic
                            _ = self.behavior_coordinator.get_effective_target_position(
                                self.behavior_coordinator.target_joints
                            )
                        elif self.behavior_coordinator.home_position_stage == 2:
                            self.get_logger().info("Successfully reached final home position (stage 2)")
                            # Transition back to IDLE state
                            self.request_state_transition(LuxoState.IDLE, priority=30)
                            self.behavior_coordinator.persistent_head_collision_active = False
                            
                            # Reset the activity timer to prevent immediately triggering idle timeout
                            self.behavior_coordinator.last_activity_time = self.get_clock().now()
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
                msg.name = ['base', 'shoulder', 'elbow', 'wrist', 'hand', 'antenna']
            else:
                # URDF-based joint names
                msg.name = ['base_to_L1', 'L1_to_L2', 'L2_to_L3', 'L3_to_L4', 'hand', 'antenna']

            # Set the actual positions - filter out acceleration (index 5) if present
            # positions should be [base, shoulder, elbow, wrist, roll, acceleration, antenna]
            # We want to publish [base, shoulder, elbow, wrist, roll, antenna]
            if len(positions) >= 7:
                # Skip acceleration at index 5
                msg.position = list(positions[:5]) + [positions[6]]  # Skip acceleration
                self.get_logger().debug(f"Publishing with antenna - Positions: {positions}, Published: {msg.position}")
            else:
                msg.position = list(positions)
                self.get_logger().debug(f"Publishing without antenna - Positions: {positions}")
            
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
            'antenna': 'antenna',  # Antenna is controlled by the hand/gripper servo
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
        
        # Request shutdown state using StateUtils
        StateUtils.request_state_transition(self, LuxoState.SHUTDOWN, priority=100, force=True)
        
        if hasattr(self, 'state_publish_timer'):
            self.state_publish_timer.cancel()

        if hasattr(self, 'light_status_timer'):
            self.light_status_timer.cancel()

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
                    # Transition to USER_CONTROL state if not already there
                    if not self.is_in_state(LuxoState.USER_CONTROL):
                        self.request_state_transition(LuxoState.USER_CONTROL, priority=50)
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
                # Don't disable if in sleep mode
                if hasattr(self, '_sleep_mode_active') and self._sleep_mode_active:
                    self.get_logger().info("Ignoring DEMA disable request - robot is in sleep mode")
                    return True
                # Use SerialManager's built-in method to disable
                success = self.serial_manager.set_dynamic_adaptation(mode=0)
                
                if success:
                    self.dynamic_adaptation_active = False
                    self.dynamic_adaptation_last_disable_time = self.get_clock().now()
                    # Transition out of USER_CONTROL state if we're in it
                    if self.is_in_state(LuxoState.USER_CONTROL):
                        self.request_state_transition(LuxoState.IDLE, priority=30)
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
            if not hasattr(self, 'last_adaptation_toggle_time'):
                self.last_adaptation_toggle_time = current_time
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


    def publish_light_status(self):
        """Publish the current light status."""
        try:
            if hasattr(self, 'light_status_publisher'):
                status_msg = Bool()
                status_msg.data = self.current_light_status
                self.light_status_publisher.publish(status_msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing light status: {e}")

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

                # Check for motor resistance (blocked movement)
                if self.enable_motor_resistance:
                    self.check_motor_resistance(positions)

                # Update collision avoidance system with current position
                self.behavior_coordinator.update_current_joints(positions)
                
                # Critical for DEMA: If in dynamic adaptation mode and position changed significantly
                # but we didn't issue the command ourselves, then this is user movement
                if (self.dynamic_adaptation_active and is_significant and 
                    not getattr(self, 'is_commanded_movement', False)):
                    self.get_logger().info("Detected user manual movement while DEMA is active")
                    # User is physically moving the arm, keep DEMA enabled to allow this
                    # Update the DEMA last active time to prevent timeout
                    self.dynamic_adaptation_last_disable_time = self.get_clock().now()
                    # Don't disable DEMA for user movements
                
                # Check if we've reached our target (movement complete)
                if hasattr(self, 'target_joints') and self.target_joints:
                    all_reached = all(
                        abs(positions[i] - self.target_joints[i]) < 0.05
                        for i in range(min(len(positions), 5))
                    )
                    if all_reached and self.enable_motor_resistance:
                        # Clear resistance tracking when target is reached
                        self.motor_resistance_detections = [0] * 5
                        self.motor_resistance_start_time = [None] * 5

                # Reset the commanded movement flag
                self.is_commanded_movement = False
                
                # Publish the updated joint states
                self.publish_actual_joint_states(positions)
                
        except Exception as e:
            self.get_logger().error(f"Error in position feedback callback: {e}")
            import traceback
            self.get_logger().error(traceback.format_exc())

    def check_motor_resistance(self, actual_positions):
        """Check if motors are experiencing resistance by comparing commanded vs actual positions."""
        if not hasattr(self, 'target_joints') or not self.target_joints:
            return

        current_time = self.get_clock().now()
        resistance_detected = False
        resistance_joints = []

        # Check each joint for resistance
        for i in range(min(len(actual_positions), len(self.target_joints[:5]))):
            target = self.target_joints[i]
            actual = actual_positions[i]
            diff = abs(target - actual)

            # Check if there's significant difference between commanded and actual
            if diff > self.motor_resistance_threshold:
                # Record the direction of resistance
                direction = 1.0 if target > actual else -1.0

                # Start tracking time if this is the first detection
                if self.motor_resistance_start_time[i] is None:
                    self.motor_resistance_start_time[i] = current_time
                    self.last_resistance_direction[i] = direction
                    self.get_logger().debug(f"Joint {i} resistance started: target={target:.2f}, actual={actual:.2f}, diff={diff:.2f}")

                # Check if resistance has persisted long enough
                elif (current_time - self.motor_resistance_start_time[i]).nanoseconds / 1e9 > self.motor_resistance_time_threshold:
                    # Check if we're still trying to move in the same direction
                    if direction == self.last_resistance_direction[i]:
                        self.motor_resistance_detections[i] += 1
                        resistance_detected = True
                        resistance_joints.append(i)

                        joint_names = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
                        self.get_logger().warn(
                            f"Motor resistance detected on {joint_names[i]}: "
                            f"target={target:.2f}, actual={actual:.2f}, "
                            f"detections={self.motor_resistance_detections[i]}"
                        )
            else:
                # Clear resistance tracking if joint is moving freely
                self.motor_resistance_start_time[i] = None
                self.motor_resistance_detections[i] = max(0, self.motor_resistance_detections[i] - 1)

        # Publish resistance status
        if self.enable_motor_resistance:
            status_msg = String()
            if resistance_detected:
                joint_names = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
                joints_str = ', '.join([joint_names[j] for j in resistance_joints])
                detections_str = ', '.join([str(self.motor_resistance_detections[j]) for j in resistance_joints])
                status_msg.data = f"RESISTANCE_DETECTED: joints=[{joints_str}], detections=[{detections_str}]"
            else:
                status_msg.data = "NO_RESISTANCE"
            self.motor_resistance_publisher.publish(status_msg)

        # Trigger collision-like response if resistance is detected
        if resistance_detected:
            self.handle_motor_resistance(resistance_joints)

    def handle_motor_resistance(self, resistance_joints):
        """Handle detected motor resistance by triggering appropriate safety responses."""
        # Calculate total resistance score
        total_detections = sum(self.motor_resistance_detections[j] for j in resistance_joints)

        # Determine severity based on persistence
        if total_detections >= self.motor_resistance_consecutive_threshold * 3:
            # Severe resistance - trigger escape mode
            self.get_logger().error("Severe motor resistance detected - triggering escape mode")

            # Request escape mode through state machine
            try:
                # Use StateUtils from shared_utils for proper state transition
                state_utils = StateUtils(self)
                state_utils.request_state_transition('ESCAPE_MODE', priority=90)
            except Exception as e:
                self.get_logger().error(f"Failed to request ESCAPE_MODE: {e}")
                # Fallback: Stop movement
                self.stop_current_movement()

        elif total_detections >= self.motor_resistance_consecutive_threshold:
            # Moderate resistance - back off
            self.get_logger().warn("Motor resistance persisting - backing off")

            # Calculate safe retreat position
            safe_positions = self.current_joints.copy()
            for joint in resistance_joints:
                # Move back in opposite direction of resistance
                retreat_amount = 0.1 * self.last_resistance_direction[joint] * -1
                safe_positions[joint] += retreat_amount

            # Apply safety limits
            if self.enable_collision_avoidance:
                safe_positions = self.behavior_coordinator.apply_safety_limits(safe_positions)

            # Send the retreat command
            self.send_safe_joint_command(safe_positions, "Motor resistance retreat")

            # Request collision avoidance state
            try:
                state_utils = StateUtils(self)
                state_utils.request_state_transition('COLLISION_AVOIDING', priority=80)
            except Exception as e:
                self.get_logger().warn(f"Failed to request COLLISION_AVOIDING: {e}")
        else:
            # Light resistance - just slow down
            self.get_logger().info("Light motor resistance detected - reducing speed")

            # Reduce movement speed
            if hasattr(self, 'serial_manager') and self.serial_manager.is_connected():
                # Send reduced speed command
                speed_cmd = {"T": 11, "cmd": 500}  # Slow speed
                self.serial_manager.write_data(json.dumps(speed_cmd))

    def stop_current_movement(self):
        """Emergency stop of current movement."""
        try:
            # Hold current position
            if hasattr(self, 'current_joints') and self.current_joints:
                self.send_safe_joint_command(self.current_joints, "Emergency stop")
                self.target_joints = self.current_joints.copy()

            # Clear resistance tracking
            self.motor_resistance_detections = [0] * 5
            self.motor_resistance_start_time = [None] * 5

        except Exception as e:
            self.get_logger().error(f"Error in emergency stop: {e}")

    def check_joint_publish_health(self):
        """Check if joint states are being published regularly"""
        current_time = time.time()
        
        # Check publish timer health
        publish_age = current_time - self._last_joint_publish_time
        if publish_age > 3.0:  # Should publish at 10Hz, so 3s is way too long
            self.get_logger().error(f"Joint state publishing appears stuck! Last publish {publish_age:.1f}s ago")
            self.get_logger().error(f"Joint publish count: {self._joint_publish_count}")
            
            # Try to recover by requesting state transition
            if self.is_in_state(LuxoState.IDLE, LuxoState.ANIMATING):
                self.get_logger().warning("Attempting recovery by requesting RETURNING_HOME state")
                try:
                    self.request_state_transition(LuxoState.RETURNING_HOME, 'hardware_interface', 70, False)
                except Exception as e:
                    self.get_logger().error(f"Recovery state transition failed: {e}")
        
        # Log health status periodically
        self.get_logger().info(f"Joint publish health check - Count: {self._joint_publish_count}, Age: {publish_age:.1f}s")


def main(args=None):
    import signal
    import sys

    rclpy.init(args=args)

    # Create and run the node
    hardware_interface = RoArmHardwareInterface()

    # Flag to track if shutdown was requested
    shutdown_requested = [False]  # Use list so we can modify in nested function

    def signal_handler(sig, frame):
        """Handle Ctrl+C and request graceful shutdown"""
        if not shutdown_requested[0]:
            shutdown_requested[0] = True
            hardware_interface.get_logger().info("⚠️  Shutdown signal received (Ctrl+C) - requesting SHUTDOWN state...")

            # Request transition to SHUTDOWN state (this will trigger _on_enter_shutdown)
            try:
                from luxo_behaviors.shared_utils import StateUtils
                StateUtils.request_state_transition(
                    hardware_interface,
                    LuxoState.SHUTDOWN,
                    priority=100,
                    force=True
                )
                hardware_interface.get_logger().info("✅ SHUTDOWN state requested - shutdown sequence running...")
            except Exception as e:
                hardware_interface.get_logger().error(f"Error requesting SHUTDOWN state: {e}")

        # Don't block - let the ROS executor continue to process the shutdown state
        # The _on_enter_shutdown() callback will handle the actual shutdown sequence
        # After it completes, we'll exit naturally

    # Register signal handlers for graceful shutdown
    original_sigint = signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    original_sigterm = signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

    if hardware_interface.serial_manager.is_connected():
        try:
            rclpy.spin(hardware_interface)
        except KeyboardInterrupt:
            # Shutdown was requested - check if shutdown sequence completed
            hardware_interface.get_logger().info("⚠️  Interrupt received - checking shutdown status...")

            # If we're in SHUTDOWN state and the sequence hasn't completed, wait for it
            if shutdown_requested[0]:
                hardware_interface.get_logger().info("⏳ Waiting for shutdown sequence to complete...")

                # Wait for up to 6 seconds for shutdown to complete
                import time
                for i in range(12):  # 12 * 0.5s = 6 seconds
                    if hasattr(hardware_interface, '_shutdown_complete') and hardware_interface._shutdown_complete:
                        hardware_interface.get_logger().info("✅ Shutdown sequence completed")
                        break
                    time.sleep(0.5)
                else:
                    hardware_interface.get_logger().warn("⚠️  Shutdown sequence timeout - proceeding with cleanup")

    # Clean up is handled in destroy_node
    hardware_interface.get_logger().info("🔄 Cleaning up hardware interface...")

    # Restore original signal handlers before cleanup
    signal.signal(signal.SIGINT, original_sigint)
    signal.signal(signal.SIGTERM, original_sigterm)

    hardware_interface.destroy_node()
    rclpy.shutdown()
    hardware_interface.get_logger().info("👋 Hardware interface shutdown complete")

if __name__ == '__main__':
    main()