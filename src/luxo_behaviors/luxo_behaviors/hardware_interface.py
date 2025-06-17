#!/usr/bin/env python3
"""
Hardware Interface for Behavior System Only
Enhanced version with better debugging, command format fixes, and sensor integration.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, String, Float32
import json
import threading
import time
import random
import numpy as np
import math
from typing import List, Optional, Dict, Any

# Hardware components
from luxo_behaviors.serial_manager import SerialManager
from luxo_behaviors.state_machine import LuxoStateMachine, LuxoState

# Import shared utilities
from luxo_behaviors.shared_utilities import (
    LuxoConstants, 
    SafetyUtils,
    AngleUtils, 
    PositionUtils, 
    ROSUtils,
    MathUtils
)


class RoArmHardwareInterface(Node):
    """
    Hardware interface for the RoArm robot - behavior system only.
    Enhanced version with better debugging and fixes.
    """
    
    def __init__(self):
        super().__init__('hardware_interface_main')
        
        # Declare parameters
        self.declare_parameter('serial_port', '/dev/ttyAMA0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('enable_torque', True)
        self.declare_parameter('read_throttle', 0.1)
        self.declare_parameter('enable_fallback_mode', True)
        self.declare_parameter('connection_retry_interval', 5.0)
        self.declare_parameter('max_connection_retries', 10)
        
        # Hardware joint names parameter
        self.declare_parameter('use_hardware_joint_names', True)
        
        # Dynamic adaptation parameters
        self.declare_parameter('enable_dynamic_adaptation', False)
        self.declare_parameter('dynamic_adaptation_base_limit', 15)
        self.declare_parameter('dynamic_adaptation_shoulder_limit', 15)
        self.declare_parameter('dynamic_adaptation_elbow_limit', 15)
        self.declare_parameter('dynamic_adaptation_wrist_limit', 15)
        self.declare_parameter('dynamic_adaptation_roll_limit', 15)
        self.declare_parameter('dynamic_adaptation_hand_limit', 15)
        self.declare_parameter('dynamic_adaptation_resume_delay', 3.0)
        
        # Position feedback parameters
        self.declare_parameter('position_feedback_timeout', 5.0)
        self.declare_parameter('use_commanded_position_fallback', True)
        self.declare_parameter('position_request_interval', 2.0)  # Increased to 2s
        
        # Initialization parameters
        self.declare_parameter('use_hardware_position_on_init', True)
        self.declare_parameter('init_position_timeout', 10.0)
        self.declare_parameter('initialization_duration', 3.0)
        
        # Movement source integration
        self.declare_parameter('enable_movement_source_integration', True)
        
        # Debug mode
        self.declare_parameter('debug_serial_communication', True)
        self.declare_parameter('simulate_sensor_data', True)  # For testing when sensors fail
        
        # Load parameters
        self._load_parameters()
        
        # Initialize timing variables
        self.initialization_start_time = self.get_clock().now()
        
        # Initialize the state machine
        self.state_machine = LuxoStateMachine(self, LuxoState.INITIALIZING)
        
        # State tracking
        self.last_command_time = self.get_clock().now()
        self.last_publish_time = self.get_clock().now()
        self.last_position_feedback_time = self.get_clock().now()
        self.last_position_request_time = self.get_clock().now()
        self.position_feedback_received = False
        
        # Initialize with proper default positions
        home_position = [0.5, 0.5, 1.3, 1.4, -1.5]
        self.target_joints = home_position.copy()
        self.current_joints = home_position.copy()
        self.commanded_joints = home_position.copy()
        self.joint_velocities = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.command_lock = threading.Lock()
        
        # Connection management
        self.connection_active = False
        self.connection_lock = threading.Lock()
        self.fallback_mode_active = False
        self.connection_retry_count = 0
        self.connection_retry_timer = None
        
        # Dynamic adaptation state
        self.dynamic_adaptation_active = False
        self.dynamic_adaptation_lock = threading.Lock()
        self.dynamic_adaptation_pending_resume = False
        self.last_adaptation_toggle_time = self.get_clock().now()
        self.dema_reenable_timer = None
        self.is_commanded_movement = False
        self.last_commanded_movement_time = self.get_clock().now()
        
        # Light control state
        self.current_light_status = False
        
        # Diagnostics
        self.total_commands_sent = 0
        self.total_feedback_received = 0
        self.last_diagnostic_time = self.get_clock().now()
        self.last_raw_feedback = ""
        
        self.get_logger().info("Hardware Interface Mode: Behavior System Only (Enhanced)")
        
        # Initialize serial manager with proper connection sequence
        self.serial_manager = None
        self._attempt_hardware_connection()
        
        # Create publishers
        self._create_publishers()
        
        # Create subscribers
        self._create_subscribers()
        
        # Setup state machine callbacks
        self._setup_state_callbacks()
        
        # Create timers
        self._create_timers()
        
        # If simulating sensor data, create sensor simulators
        if self.simulate_sensor_data:
            self._setup_sensor_simulation()
        
        self.get_logger().info("Hardware interface initialization complete")
    
    def _load_parameters(self):
        """Load all parameters."""
        self.serial_port = self.get_parameter('serial_port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.enable_torque_on_start = self.get_parameter('enable_torque').value
        self.read_throttle = self.get_parameter('read_throttle').value
        self.use_hardware_joint_names = self.get_parameter('use_hardware_joint_names').value
        self.enable_fallback_mode = self.get_parameter('enable_fallback_mode').value
        self.connection_retry_interval = self.get_parameter('connection_retry_interval').value
        self.max_connection_retries = self.get_parameter('max_connection_retries').value
        
        # Dynamic adaptation parameters
        self.enable_dynamic_adaptation = self.get_parameter('enable_dynamic_adaptation').value
        self.dynamic_adaptation_base_limit = self.get_parameter('dynamic_adaptation_base_limit').value
        self.dynamic_adaptation_shoulder_limit = self.get_parameter('dynamic_adaptation_shoulder_limit').value
        self.dynamic_adaptation_elbow_limit = self.get_parameter('dynamic_adaptation_elbow_limit').value
        self.dynamic_adaptation_wrist_limit = self.get_parameter('dynamic_adaptation_wrist_limit').value
        self.dynamic_adaptation_roll_limit = self.get_parameter('dynamic_adaptation_roll_limit').value
        self.dynamic_adaptation_hand_limit = self.get_parameter('dynamic_adaptation_hand_limit').value
        self.dynamic_adaptation_resume_delay = self.get_parameter('dynamic_adaptation_resume_delay').value
        
        # Position feedback parameters
        self.position_feedback_timeout = self.get_parameter('position_feedback_timeout').value
        self.use_commanded_position_fallback = self.get_parameter('use_commanded_position_fallback').value
        self.position_request_interval = self.get_parameter('position_request_interval').value
        
        # Initialization parameters
        self.use_hardware_position_on_init = self.get_parameter('use_hardware_position_on_init').value
        self.init_position_timeout = self.get_parameter('init_position_timeout').value
        self.initialization_duration = self.get_parameter('initialization_duration').value
        self.enable_movement_source_integration = self.get_parameter('enable_movement_source_integration').value
        
        # Debug parameters
        self.debug_serial_communication = self.get_parameter('debug_serial_communication').value
        self.simulate_sensor_data = self.get_parameter('simulate_sensor_data').value
    
    def _setup_sensor_simulation(self):
        """Setup sensor simulation for testing when real sensors fail."""
        self.get_logger().warn("SENSOR SIMULATION MODE ACTIVE - Using simulated sensor data")
        
        # Simulated sensor values
        self.simulated_proximity = 50
        self.simulated_left_distance = 20.0
        self.simulated_right_distance = 25.0
        self.simulated_petting = False
        self.last_petting_change = self.get_clock().now()
        
        # Create sensor simulation timer
        self.sensor_sim_timer = self.create_timer(0.1, self._simulate_sensor_data)
    
    def _simulate_sensor_data(self):
        """Simulate sensor data for testing."""
        try:
            current_time = self.get_clock().now()
            
            # Simulate proximity sensor (varies with sine wave)
            base_proximity = 50
            variation = 20 * math.sin(time.time() * 0.5)
            self.simulated_proximity = int(base_proximity + variation)
            
            # Publish simulated proximity
            prox_msg = Float32()
            prox_msg.data = float(self.simulated_proximity)
            self.simulated_proximity_pub.publish(prox_msg)
            
            # Simulate distance sensors
            self.simulated_left_distance = 15.0 + 10.0 * math.sin(time.time() * 0.3)
            self.simulated_right_distance = 20.0 + 8.0 * math.cos(time.time() * 0.4)
            
            # Publish simulated distances
            left_msg = Float32()
            left_msg.data = self.simulated_left_distance
            self.simulated_left_distance_pub.publish(left_msg)
            
            right_msg = Float32()
            right_msg.data = self.simulated_right_distance
            self.simulated_right_distance_pub.publish(right_msg)
            
            # Simulate petting (random events)
            time_since_petting_change = ROSUtils.time_since(self.last_petting_change, current_time)
            if time_since_petting_change > 5.0 and random.random() < 0.1:  # 10% chance every 5s
                self.simulated_petting = not self.simulated_petting
                self.last_petting_change = current_time
                
                # Publish petting event
                petting_msg = String()
                if self.simulated_petting:
                    pressure = random.randint(10, 50)
                    petting_msg.data = f"petting_started:{pressure}"
                else:
                    petting_msg.data = "petting_stopped:0"
                
                self.simulated_petting_pub.publish(petting_msg)
                self.get_logger().info(f"Simulated petting event: {petting_msg.data}")
                
        except Exception as e:
            self.get_logger().error(f"Error in sensor simulation: {e}")
    
    def _attempt_hardware_connection(self):
        """Attempt to connect to hardware using the original working pattern."""
        try:
            with self.connection_lock:
                self.get_logger().info(f"Attempting to connect to hardware on {self.serial_port}")
                
                self.serial_manager = SerialManager(
                    self, 
                    self.serial_port, 
                    self.baud_rate, 
                    self.read_throttle
                )
                
                self.connection_active = self.serial_manager.connect()
                
                if self.connection_active:
                    time.sleep(2)
                    
                    self.connection_active = self.serial_manager.is_connected()
                    
                    if self.connection_active:
                        self.get_logger().info(f"Successfully connected to RoArm on {self.serial_port}")
                        self.connection_retry_count = 0
                        self.fallback_mode_active = False
                        
                        self._initialize_hardware()
                        return True
                    else:
                        self.get_logger().warn("Connection lost during stabilization")
                        
                self.get_logger().error(f"Failed to connect to RoArm on {self.serial_port}")
                
                self._handle_connection_failure()
                return False
                
        except Exception as e:
            self.get_logger().error(f"Exception during hardware connection: {e}")
            self._handle_connection_failure()
            return False
    
    def _handle_connection_failure(self):
        """Handle hardware connection failure with retry or fallback."""
        self.connection_retry_count += 1
        
        if self.connection_retry_count <= self.max_connection_retries:
            self.get_logger().warn(
                f"Connection attempt {self.connection_retry_count}/{self.max_connection_retries} failed. "
                f"Retrying in {self.connection_retry_interval} seconds..."
            )
            
            if self.connection_retry_timer:
                self.connection_retry_timer.cancel()
            self.connection_retry_timer = self.create_timer(
                self.connection_retry_interval,
                self._retry_hardware_connection
            )
            
        elif self.enable_fallback_mode:
            self.get_logger().warn(
                f"Max connection retries ({self.max_connection_retries}) exceeded. "
                "Entering fallback mode - simulating hardware responses"
            )
            self._enter_fallback_mode()
            
        else:
            self.get_logger().error("Hardware connection failed and fallback mode disabled")
            self.state_machine.transition_to(LuxoState.ERROR)
    
    def _retry_hardware_connection(self):
        """Retry hardware connection."""
        try:
            if self.connection_retry_timer:
                self.connection_retry_timer.cancel()
                self.connection_retry_timer = None
            
            self.get_logger().info(f"Retrying hardware connection (attempt {self.connection_retry_count + 1})...")
            
            if self.serial_manager:
                try:
                    self.serial_manager.close()
                except:
                    pass
                self.serial_manager = None
            
            if self._attempt_hardware_connection():
                self.get_logger().info("Hardware connection successful on retry!")
                
                if self.fallback_mode_active:
                    self._exit_fallback_mode()
            
        except Exception as e:
            self.get_logger().error(f"Error during connection retry: {e}")
            self._handle_connection_failure()
    
    def _enter_fallback_mode(self):
        """Enter fallback mode with simulated hardware."""
        self.fallback_mode_active = True
        self.connection_active = True
        
        home_position = [0.5, 0.5, 1.3, 1.4, -1.5]
        self.current_joints = home_position.copy()
        self.target_joints = home_position.copy()
        self.commanded_joints = home_position.copy()
        
        self.get_logger().info(f"Fallback mode activated - initialized at position: {[round(p, 2) for p in home_position]}")
        
        if not hasattr(self, 'fallback_motion_timer'):
            self.fallback_motion_timer = self.create_timer(0.02, self._simulate_fallback_motion)
        
        self.state_machine.transition_to(LuxoState.IDLE)
    
    def _exit_fallback_mode(self):
        """Exit fallback mode and return to hardware control."""
        self.fallback_mode_active = False
        
        if hasattr(self, 'fallback_motion_timer'):
            self.fallback_motion_timer.cancel()
            delattr(self, 'fallback_motion_timer')
        
        self.get_logger().info("Exited fallback mode - hardware control restored")
        
        self._initialize_hardware()
    
    def _initialize_hardware(self):
        """Initialize hardware with better error handling and diagnostics."""
        if self.fallback_mode_active:
            return
            
        try:
            home_position = [0.5, 0.5, 1.3, 1.4, -1.5]
            self.current_joints = home_position.copy()
            self.target_joints = home_position.copy()
            self.commanded_joints = home_position.copy()
            
            self.get_logger().info(f"Hardware initialized with default position: {[round(p, 2) for p in home_position]}")
            
            # Try different initialization sequences
            if self.enable_torque_on_start:
                self.get_logger().info("Enabling torque...")
                
                # Try multiple torque enable commands
                torque_commands = [
                    '{"T":700}',  # Standard torque enable
                    '{"cmd":"torque_on"}',  # Alternative format
                    '{"T":1,"cmd":"enable"}',  # Another alternative
                ]
                
                for cmd in torque_commands:
                    if self.serial_manager.send_command(cmd, "Torque enable"):
                        self.get_logger().info(f"Torque enabled with command: {cmd}")
                        break
                    time.sleep(0.5)
            else:
                self.get_logger().info("Torque disabled on startup")
                
            time.sleep(1)
            
            # Send initialization position
            self.get_logger().info("Sending initial position...")
            init_position_cmd = {
                'T': 102,
                'base': home_position[0],
                'shoulder': home_position[1], 
                'elbow': home_position[2],
                'wrist': home_position[3],
                'roll': home_position[4],
                'hand': 0.0,
                'spd': 50,
                'acc': 10
            }
            
            if self.serial_manager.send_command(json.dumps(init_position_cmd), "Initial position"):
                self.get_logger().info("Initial position sent successfully")
            
            time.sleep(1)
            
            self.disable_dynamic_adaptation_mode()
            self.get_logger().info("Dynamic adaptation disabled for initialization")
            time.sleep(1)
            
            self.dema_should_be_enabled = self.enable_dynamic_adaptation
            
            if self.use_hardware_position_on_init:
                self.request_hardware_position()
                
        except Exception as e:
            self.get_logger().error(f"Error during hardware initialization: {e}")
    
    def _create_publishers(self):
        """Create ROS publishers."""
        self.joint_states_publisher = self.create_publisher(
            JointState,
            '/joint_states',
            10
        )
        
        self.state_publisher = self.create_publisher(
            String,
            '/luxo/current_state',
            10
        )
        
        self.light_status_publisher = self.create_publisher(
            Bool,
            '/luxo/light_status',
            10
        )
        
        if self.enable_movement_source_integration:
            self.movement_source_publisher = self.create_publisher(
                String,
                '/roarm/movement_source',
                10
            )
            
        self.hardware_status_publisher = self.create_publisher(
            String,
            '/hardware/status',
            10
        )
        
        self.diagnostic_publisher = self.create_publisher(
            String,
            '/hardware/diagnostics',
            10
        )
        
        # Create simulated sensor publishers if enabled
        if self.simulate_sensor_data:
            self.simulated_proximity_pub = self.create_publisher(
                Float32,
                '/proximity/front',
                10
            )
            
            self.simulated_left_distance_pub = self.create_publisher(
                Float32,
                '/distance/left',
                10
            )
            
            self.simulated_right_distance_pub = self.create_publisher(
                Float32,
                '/distance/right',
                10
            )
            
            self.simulated_petting_pub = self.create_publisher(
                String,
                '/collision/petting_events',
                10
            )
            
            self.get_logger().info("Created simulated sensor publishers")
    
    def _create_subscribers(self):
        """Create ROS subscribers."""
        self.safety_coordinator_subscription = self.create_subscription(
            JointState,
            '/roarm/joint_command',
            self.safety_coordinator_callback,
            10
        )
        
        self.position_subscription = self.create_subscription(
            String, 
            'roarm/position',
            self.position_feedback_callback,
            10
        )
        
        self.position_alt_subscription = self.create_subscription(
            String, 
            '/roarm/position',
            self.position_feedback_callback,
            10
        )
        
        # Subscribe to raw serial data for debugging
        self.serial_raw_subscription = self.create_subscription(
            String,
            'roarm/serial_raw',
            self.serial_raw_callback,
            10
        )
        
        self.dynamic_adaptation_toggle_sub = self.create_subscription(
            Bool,
            '/luxo/toggle_dynamic_adaptation',
            self.dynamic_adaptation_toggle_callback,
            10
        )
        
        self.light_control_sub = self.create_subscription(
            Bool,
            '/luxo/light_control',
            self.light_control_callback,
            10
        )
        
        self.get_logger().info("Subscribed to /roarm/joint_command for SafetyCoordinator commands")
    
    def _create_timers(self):
        """Create periodic timers."""
        self.joint_states_timer = self.create_timer(0.05, self.publish_current_joint_states)  # 20Hz
        self.state_timer = self.create_timer(0.5, self._update_state_machine)
        self.state_publish_timer = self.create_timer(0.5, self.publish_current_state)
        self.light_status_timer = self.create_timer(1.0, self.publish_light_status)
        self.hardware_status_timer = self.create_timer(1.0, self.publish_hardware_status)
        self.health_check_timer = self.create_timer(10.0, self._connection_health_check)
        
        self.position_request_timer = self.create_timer(
            self.position_request_interval, 
            self._periodic_position_request
        )
        
        self.diagnostic_timer = self.create_timer(5.0, self._publish_diagnostics)
    
    def _periodic_position_request(self):
        """Periodically request position from hardware."""
        if not self.fallback_mode_active and self.connection_active:
            current_time = self.get_clock().now()
            time_since_feedback = ROSUtils.time_since(self.last_position_feedback_time, current_time)
            
            if time_since_feedback > self.position_request_interval:
                self.request_hardware_position()
    
    def _publish_diagnostics(self):
        """Publish diagnostic information."""
        try:
            current_time = self.get_clock().now()
            time_since_start = ROSUtils.time_since(self.initialization_start_time, current_time)
            
            feedback_rate = 0.0
            if self.total_commands_sent > 0:
                feedback_rate = (self.total_feedback_received / self.total_commands_sent) * 100
            
            diagnostics = {
                'uptime': round(time_since_start, 1),
                'commands_sent': self.total_commands_sent,
                'feedback_received': self.total_feedback_received,
                'feedback_rate': round(feedback_rate, 1),
                'position_feedback': self.position_feedback_received,
                'fallback_mode': self.fallback_mode_active,
                'dema_active': self.dynamic_adaptation_active,
                'state': self.state_machine.current_state.name,
                'last_raw_feedback': self.last_raw_feedback[:100] if self.last_raw_feedback else "none",
                'simulating_sensors': self.simulate_sensor_data
            }
            
            msg = String()
            msg.data = json.dumps(diagnostics)
            self.diagnostic_publisher.publish(msg)
            
            if self.total_commands_sent > 10 and feedback_rate < 50:
                self.get_logger().warn(f"Low position feedback rate: {feedback_rate:.1f}%")
                
        except Exception as e:
            self.get_logger().error(f"Error publishing diagnostics: {e}")
    
    def _connection_health_check(self):
        """Periodically check connection health and attempt recovery if needed."""
        try:
            if not self.fallback_mode_active and self.serial_manager:
                if not self.serial_manager.is_connected():
                    self.get_logger().warn("Connection lost - attempting recovery")
                    self.connection_active = False
                    self._handle_connection_failure()
                else:
                    current_time = self.get_clock().now()
                    time_since_feedback = ROSUtils.time_since(self.last_position_feedback_time, current_time)
                    
                    if time_since_feedback > self.position_feedback_timeout:
                        self.get_logger().warn(f"No position feedback for {time_since_feedback:.1f}s")
                        if self.use_commanded_position_fallback:
                            self.get_logger().info("Using commanded position fallback")
                            
        except Exception as e:
            self.get_logger().error(f"Error in connection health check: {e}")
    
    def _setup_state_callbacks(self):
        """Set up callbacks for state transitions."""
        self.state_machine.register_on_enter(LuxoState.INITIALIZING, self._on_enter_initializing)
        self.state_machine.register_on_enter(LuxoState.IDLE, self._on_enter_idle)
        self.state_machine.register_on_enter(LuxoState.USER_CONTROL, self._on_enter_user_control)
        self.state_machine.register_on_exit(LuxoState.USER_CONTROL, self._on_exit_user_control)
        self.state_machine.register_on_enter(LuxoState.ERROR, self._on_enter_error)
        self.state_machine.register_on_enter(LuxoState.SHUTDOWN, self._on_enter_shutdown)
    
    def _update_state_machine(self):
        """Periodically update the state machine."""
        if self.state_machine.is_in_state(LuxoState.INITIALIZING):
            current_time = self.get_clock().now()
            time_in_init = ROSUtils.time_since(self.initialization_start_time, current_time)
            
            if self.fallback_mode_active:
                self.get_logger().info("Fallback mode active - transitioning to IDLE immediately")
                self.state_machine.transition_to(LuxoState.IDLE)
            elif time_in_init >= self.initialization_duration:
                self.get_logger().info(f"Initialization period complete ({time_in_init:.1f}s) - transitioning to IDLE")
                self.state_machine.transition_to(LuxoState.IDLE)
        
        self.state_machine.update()
    
    def _on_enter_initializing(self):
        """Called when entering INITIALIZING state."""
        self.get_logger().info(f"Entering INITIALIZING state - will remain for {self.initialization_duration} seconds")
        self.initialization_start_time = self.get_clock().now()
    
    def _on_enter_idle(self):
        """Called when entering IDLE state."""
        self.get_logger().info("Entering IDLE state")
        self.dynamic_adaptation_pending_resume = False
    
    def _on_enter_user_control(self):
        """Called when entering USER_CONTROL state."""
        self.get_logger().info("Entering USER_CONTROL state (DEMA enabled)")
        if not self.dynamic_adaptation_active and not self.fallback_mode_active:
            self.enable_dynamic_adaptation_mode()
    
    def _on_exit_user_control(self):
        """Called when exiting USER_CONTROL state."""
        self.get_logger().info("Exiting USER_CONTROL state (DEMA disabled)")
        if self.dynamic_adaptation_active and not self.fallback_mode_active:
            self.disable_dynamic_adaptation_mode()
    
    def _on_enter_error(self):
        """Called when entering ERROR state."""
        self.get_logger().error("Entering ERROR state")
        try:
            if not self.fallback_mode_active:
                self.disable_torque()
        except Exception:
            pass
    
    def _on_enter_shutdown(self):
        """Called when entering SHUTDOWN state."""
        self.get_logger().info("Entering SHUTDOWN state")
    
    def is_connected(self):
        """Check if we're connected to the hardware."""
        return self.connection_active
    
    def safety_coordinator_callback(self, msg: JointState):
        """Handle joint commands from the safety coordinator."""
        if not self.is_connected():
            self.get_logger().warn("Ignoring command - not connected")
            return
        
        if self.state_machine.is_in_state(LuxoState.INITIALIZING) and not self.fallback_mode_active:
            self.get_logger().debug("Skipping command during initialization")
            return
        
        try:
            positions = msg.position
            
            self.get_logger().info(f"Safety coordinator command received: {[round(p, 2) for p in positions[:5]]}")
            
            if len(positions) >= 5:
                target_positions = list(positions[:5])
                
                if len(positions) > 5:
                    acceleration = positions[5]
                    target_positions.append(acceleration)
                    self.get_logger().debug(f"Using acceleration from position[5]: {acceleration}")
                else:
                    target_positions.append(10.0)
                    self.get_logger().debug("Using default acceleration: 10.0")
                
                self.send_safe_joint_command(target_positions, "SafetyCoordinator")
                
            else:
                self.get_logger().warn(f"Insufficient joint positions in command: {len(positions)}")
                
        except Exception as e:
            self.get_logger().error(f"Error in safety_coordinator_callback: {e}")
            import traceback
            self.get_logger().error(traceback.format_exc())
    
    def send_safe_joint_command(self, positions: List[float], source: str = "Unknown"):
        """Send a joint command to the hardware with improved formatting."""
        try:
            with self.command_lock:
                if not self.is_connected():
                    self.get_logger().warn(f"Cannot send command from {source} - not connected")
                    return False
                
                if self.dynamic_adaptation_active and not self.fallback_mode_active:
                    self.get_logger().info(f"Skipping command from {source} - DEMA active")
                    return False
                
                if len(positions) > 5:
                    acceleration = positions[5]
                    joint_positions = positions[:5]
                else:
                    acceleration = 10.0
                    joint_positions = positions[:5]
                
                if len(joint_positions) < 5:
                    joint_positions.extend([0.0] * (5 - len(joint_positions)))
                
                success = False
                
                if self.fallback_mode_active:
                    self.target_joints = joint_positions.copy()
                    self.commanded_joints = joint_positions.copy()
                    success = True
                    self.get_logger().info(f"Fallback mode: Updated target to {[round(p, 2) for p in joint_positions]}")
                else:
                    try:
                        # Convert radians to degrees for hardware
                        joint_positions_deg = [math.degrees(p) for p in joint_positions]
                        
                        # Try multiple command formats
                        command_formats = [
                            # Format 1: Standard with T=102
                            {
                                'T': 102,
                                'base': joint_positions_deg[0],
                                'shoulder': joint_positions_deg[1],
                                'elbow': joint_positions_deg[2],
                                'wrist': joint_positions_deg[3],
                                'roll': joint_positions_deg[4],
                                'hand': 0.0,
                                'spd': 50,  # Speed percentage
                                'acc': int(acceleration * 10)  # Scale acceleration
                            },
                            # Format 2: Alternative with different fields
                            {
                                'cmd': 'move',
                                'joints': joint_positions_deg,
                                'speed': 50,
                                'accel': acceleration
                            },
                            # Format 3: Simplified format
                            {
                                'T': 1,
                                'pos': joint_positions_deg,
                                'acc': acceleration
                            }
                        ]
                        
                        for i, cmd_format in enumerate(command_formats):
                            cmd_str = json.dumps(cmd_format)
                            
                            if self.debug_serial_communication:
                                self.get_logger().debug(f"Trying command format {i+1}: {cmd_str}")
                            
                            if self.serial_manager.send_command(cmd_str, source):
                                success = True
                                self.get_logger().info(f"Sent hardware command from {source} (format {i+1}): {[round(p, 2) for p in joint_positions]}")
                                break
                            
                            time.sleep(0.1)  # Small delay between attempts
                        
                        if success:
                            self.total_commands_sent += 1
                        else:
                            self.get_logger().error(f"Failed to send command with any format")
                        
                    except Exception as e:
                        self.get_logger().error(f"Error sending hardware command: {e}")
                        success = False
                
                if success:
                    if not self.fallback_mode_active:
                        self.target_joints = joint_positions.copy()
                    self.commanded_joints = joint_positions.copy()
                    self.is_commanded_movement = True
                    self.last_commanded_movement_time = self.get_clock().now()
                    
                    if self.use_commanded_position_fallback and not self.fallback_mode_active:
                        current_time = self.get_clock().now()
                        time_since_feedback = ROSUtils.time_since(self.last_position_feedback_time, current_time)
                        
                        if time_since_feedback > 1.0:
                            self.current_joints = self.commanded_joints.copy()
                            self.get_logger().debug("Using commanded position as current (no feedback)")
                    
                    if self.enable_movement_source_integration:
                        self.publish_movement_source("behavior")
                    
                    return True
                else:
                    if not self.fallback_mode_active:
                        self.get_logger().error(f"Failed to send joint command from {source}")
                    return False
                    
        except Exception as e:
            self.get_logger().error(f"Error in send_safe_joint_command from {source}: {e}")
            return False
    
    def _simulate_fallback_motion(self):
        """Simulate smooth motion toward target positions in fallback mode."""
        if not self.fallback_mode_active:
            return
            
        try:
            with self.command_lock:
                target = self.target_joints.copy()
                current = self.current_joints.copy()
            
            movement_speed = 2.0
            dt = 0.02
            max_step = movement_speed * dt
            
            new_positions = []
            
            for i, (curr, targ) in enumerate(zip(current, target)):
                diff = targ - curr
                
                if abs(diff) > max_step:
                    step = max_step if diff > 0 else -max_step
                else:
                    step = diff
                
                new_pos = curr + step
                
                noise = np.random.normal(0, 0.001)
                new_pos += noise
                
                new_positions.append(new_pos)
            
            with self.command_lock:
                self.current_joints = new_positions
                
        except Exception as e:
            self.get_logger().error(f"Error in fallback motion simulation: {e}")
    
    def publish_movement_source(self, source: str):
        """Publish movement source for DEMA coordination."""
        try:
            if hasattr(self, 'movement_source_publisher'):
                msg = String()
                msg.data = source
                self.movement_source_publisher.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing movement source: {e}")
    
    def publish_current_joint_states(self):
        """Publish current joint states to /joint_states for other nodes."""
        try:
            if not self.current_joints or len(self.current_joints) < 5:
                return
                
            msg = JointState()
            msg.header.stamp = self.get_clock().now().to_msg()
            
            msg.name = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
            
            with self.command_lock:
                positions_with_accel = list(self.current_joints[:5]) + [10.0]
                msg.position = positions_with_accel
            
            self.joint_states_publisher.publish(msg)
            
            self.last_publish_time = self.get_clock().now()
            
        except Exception as e:
            self.get_logger().error(f"Error publishing joint states: {e}")
    
    def publish_current_state(self):
        """Publish the current state machine state."""
        try:
            if self.state_machine:
                state_msg = String()
                state_msg.data = self.state_machine.current_state.name
                self.state_publisher.publish(state_msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing state: {e}")
    
    def publish_light_status(self):
        """Publish current light status."""
        try:
            msg = Bool()
            msg.data = self.current_light_status
            self.light_status_publisher.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing light status: {e}")
    
    def publish_hardware_status(self):
        """Publish hardware status information."""
        try:
            msg = String()
            if self.fallback_mode_active:
                msg.data = f"Hardware Interface: FALLBACK MODE (simulated) - Retries: {self.connection_retry_count}/{self.max_connection_retries}"
            elif self.connection_active:
                feedback_status = "receiving" if self.position_feedback_received else "NO FEEDBACK"
                msg.data = f"HW: Connected ({self.serial_port}), DEMA: {'Active' if self.dynamic_adaptation_active else 'Inactive'}, Pos: {feedback_status}, Sim sensors: {self.simulate_sensor_data}"
            else:
                msg.data = f"Hardware Interface: Disconnected, Retrying... ({self.connection_retry_count}/{self.max_connection_retries})"
            self.hardware_status_publisher.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing hardware status: {e}")
    
    def request_hardware_position(self):
        """Request the current position from the hardware with multiple formats."""
        if self.fallback_mode_active:
            return
            
        try:
            if self.is_connected() and self.serial_manager:
                # Try different position request commands
                commands = [
                    '{"T": 103}',
                    '{"T": 104}',
                    '{"cmd": "get_position"}',
                    '{"cmd": "read_pos"}',
                    '{"T": 2}',  # Alternative read command
                ]
                
                for cmd in commands:
                    if self.debug_serial_communication:
                        self.get_logger().debug(f"Trying position request: {cmd}")
                        
                    success = self.serial_manager.send_command(cmd, "Position request")
                    if success:
                        self.get_logger().info(f"Requested hardware position with command: {cmd}")
                        self.last_position_request_time = self.get_clock().now()
                        break
                    
                    time.sleep(0.1)
                else:
                    self.get_logger().warn("Failed to request hardware position with any command format")
                    
        except Exception as e:
            self.get_logger().error(f"Error requesting hardware position: {e}")
    
    def serial_raw_callback(self, msg: String):
        """Handle raw serial data for debugging."""
        try:
            self.last_raw_feedback = msg.data
            
            if self.debug_serial_communication:
                self.get_logger().debug(f"Raw serial data: {msg.data[:100]}")
                
            # Try to parse as position data
            self.position_feedback_callback(msg)
            
        except Exception as e:
            self.get_logger().debug(f"Error processing raw serial data: {e}")
    
    def position_feedback_callback(self, msg: String):
        """Handle position feedback from the hardware with improved parsing."""
        if self.fallback_mode_active:
            return
            
        try:
            if self.debug_serial_communication:
                self.get_logger().debug(f"Received position feedback: {msg.data[:200]}")
            
            # Update raw feedback for diagnostics
            self.last_raw_feedback = msg.data
            
            # Try to parse different formats
            position_data = None
            positions = None
            
            # First try JSON parsing
            try:
                position_data = json.loads(msg.data)
            except json.JSONDecodeError:
                # Try to extract JSON from mixed data
                import re
                json_match = re.search(r'\{[^}]+\}', msg.data)
                if json_match:
                    try:
                        position_data = json.loads(json_match.group())
                    except:
                        pass
                
                # Try parsing as comma-separated values
                if not position_data:
                    try:
                        values = [float(x) for x in msg.data.split(',') if x.strip()]
                        if len(values) >= 5:
                            positions = values[:5]
                    except:
                        pass
            
            if position_data:
                # Look for positions in different fields
                if 'positions' in position_data:
                    positions = position_data['positions']
                elif 'position' in position_data:
                    positions = position_data['position']
                elif 'joints' in position_data:
                    positions = position_data['joints']
                elif 'pos' in position_data:
                    positions = position_data['pos']
                elif all(key in position_data for key in ['base', 'shoulder', 'elbow', 'wrist', 'roll']):
                    positions = [
                        position_data['base'],
                        position_data['shoulder'],
                        position_data['elbow'],
                        position_data['wrist'],
                        position_data['roll']
                    ]
                elif 'T' in position_data and position_data['T'] == 103:
                    # Response to position request
                    for key in ['data', 'value', 'result']:
                        if key in position_data:
                            if isinstance(position_data[key], list) and len(position_data[key]) >= 5:
                                positions = position_data[key][:5]
                                break
            
            if positions and len(positions) >= 5:
                # Convert to floats
                positions = [float(p) for p in positions]
                
                # Check if values are in degrees (typical range -180 to 180 or 0 to 360)
                likely_degrees = any(abs(p) > 6.28 for p in positions[:3])
                
                if likely_degrees:
                    joint_positions_rad = [math.radians(pos) for pos in positions[:5]]
                else:
                    joint_positions_rad = positions[:5]
                
                # Validate positions are reasonable
                valid = True
                for i, pos in enumerate(joint_positions_rad):
                    if not math.isfinite(pos) or abs(pos) > 10:  # 10 radians is very large
                        valid = False
                        break
                
                if valid:
                    with self.command_lock:
                        self.current_joints = joint_positions_rad
                        self.position_feedback_received = True
                        self.last_position_feedback_time = self.get_clock().now()
                        self.total_feedback_received += 1
                    
                    self.get_logger().info(f"Position feedback updated: {[round(p, 2) for p in joint_positions_rad]}")
                    
                    current_time = self.get_clock().now()
                    time_since_command = ROSUtils.time_since(self.last_commanded_movement_time, current_time)
                    
                    if self.is_commanded_movement and time_since_command < 2.0:
                        pass
                    else:
                        pass
                    
                    self.is_commanded_movement = False
                    
                    if self.dynamic_adaptation_active:
                        self.target_joints = joint_positions_rad.copy()
                else:
                    self.get_logger().warn(f"Invalid position values detected")
            else:
                if self.debug_serial_communication:
                    self.get_logger().warn(f"Could not extract valid position data from: {msg.data[:100]}")
                
        except Exception as e:
            self.get_logger().error(f"Error in position feedback callback: {e}")
            if self.debug_serial_communication:
                import traceback
                self.get_logger().error(traceback.format_exc())
    
    # Hardware control methods
    def enable_torque(self):
        """Enable torque on the arm using the serial manager."""
        if self.fallback_mode_active:
            self.get_logger().info("Simulated torque enabled")
            return True
            
        # Try multiple torque enable commands
        commands = [
            '{"T":700}',
            '{"cmd":"torque_on"}',
            '{"T":1,"enable":true}',
        ]
        
        for cmd in commands:
            if self.serial_manager and self.serial_manager.send_command(cmd, "Torque enable"):
                self.get_logger().info(f"Torque enabled with command: {cmd}")
                return True
            time.sleep(0.5)
            
        self.get_logger().error("Failed to enable torque with any command")
        return False
    
    def disable_torque(self):
        """Disable torque on the arm using the serial manager."""
        if self.fallback_mode_active:
            self.get_logger().info("Simulated torque disabled")
            return True
        return self.serial_manager.disable_torque() if self.serial_manager else False
    
    def initialize_arm(self):
        """Initialize the arm position using the serial manager."""
        if self.fallback_mode_active:
            self.get_logger().info("Simulated arm initialization")
            return True
        return self.serial_manager.initialize_arm() if self.serial_manager else False
    
    def enable_dynamic_adaptation_mode(self):
        """Enable the dynamic external force adaptation mode."""
        if self.fallback_mode_active:
            self.get_logger().info("Dynamic adaptation not available in fallback mode")
            return False
            
        try:
            with self.dynamic_adaptation_lock:
                self.get_logger().info(f"DEMA parameters: base:{self.dynamic_adaptation_base_limit}, " +
                                     f"shoulder:{self.dynamic_adaptation_shoulder_limit}, " +
                                     f"elbow:{self.dynamic_adaptation_elbow_limit}")
                
                base_limit = max(1, self.dynamic_adaptation_base_limit)
                shoulder_limit = max(1, self.dynamic_adaptation_shoulder_limit)
                elbow_limit = max(1, self.dynamic_adaptation_elbow_limit)
                wrist_limit = max(1, self.dynamic_adaptation_wrist_limit)
                roll_limit = max(1, self.dynamic_adaptation_roll_limit)
                hand_limit = max(1, self.dynamic_adaptation_hand_limit)
                
                success = self.serial_manager.set_dynamic_adaptation(
                    mode=1,
                    base=base_limit,
                    shoulder=shoulder_limit,
                    elbow=elbow_limit,
                    wrist=wrist_limit,
                    roll=roll_limit,
                    hand=hand_limit
                ) if self.serial_manager else False
                
                if success:
                    self.dynamic_adaptation_active = True
                    self.get_logger().info("Dynamic adaptation mode successfully enabled")
                    
                    self.state_machine.transition_to(LuxoState.USER_CONTROL)
                    
                    if self.enable_movement_source_integration:
                        self.publish_movement_source("user")
                    
                    return True
                else:
                    self.get_logger().error("Failed to enable dynamic adaptation mode")
                    return False
                    
        except Exception as e:
            self.get_logger().error(f"Error enabling dynamic adaptation mode: {e}")
            return False
    
    def disable_dynamic_adaptation_mode(self):
        """Disable the dynamic external force adaptation mode."""
        if self.fallback_mode_active:
            return True
            
        try:
            with self.dynamic_adaptation_lock:
                if not self.dynamic_adaptation_active:
                    return True
                
                success = self.serial_manager.set_dynamic_adaptation(mode=0) if self.serial_manager else True
                
                if success:
                    self.dynamic_adaptation_active = False
                    self.get_logger().info("Dynamic adaptation mode successfully disabled")
                    
                    if self.state_machine.is_in_state(LuxoState.USER_CONTROL):
                        self.state_machine.transition_to(LuxoState.IDLE)
                    
                    return True
                else:
                    self.get_logger().error("Failed to disable dynamic adaptation mode")
                    return False
        except Exception as e:
            self.get_logger().error(f"Error disabling dynamic adaptation mode: {e}")
            return False
    
    def dynamic_adaptation_toggle_callback(self, msg: Bool):
        """Handle incoming toggle commands for dynamic adaptation."""
        if self.fallback_mode_active:
            self.get_logger().info("Dynamic adaptation toggle ignored in fallback mode")
            return
            
        try:
            current_time = self.get_clock().now()
            time_since_toggle = ROSUtils.time_since(self.last_adaptation_toggle_time, current_time)
            
            if time_since_toggle < 2.0:
                self.get_logger().warn("Ignoring rapid dynamic adaptation toggle")
                return
                
            self.last_adaptation_toggle_time = current_time
            
            if msg.data:
                self.get_logger().info("Enabling dynamic adaptation mode via toggle")
                success = self.enable_dynamic_adaptation_mode()
                if success:
                    self.get_logger().info("Dynamic adaptation successfully enabled")
                else:
                    self.get_logger().error("Failed to enable dynamic adaptation")
            else:
                self.get_logger().info("Disabling dynamic adaptation mode via toggle")
                success = self.disable_dynamic_adaptation_mode()
                if success:
                    self.get_logger().info("Dynamic adaptation successfully disabled")
                else:
                    self.get_logger().error("Failed to disable dynamic adaptation")
        except Exception as e:
            self.get_logger().error(f"Error in dynamic adaptation toggle callback: {e}")
            try:
                self.disable_dynamic_adaptation_mode()
            except:
                pass
    
    def light_control_callback(self, msg: Bool):
        """Handle incoming light control commands."""
        try:
            if self.fallback_mode_active:
                self.current_light_status = msg.data
                self.get_logger().info(f"Simulated light {'ON' if msg.data else 'OFF'}")
            else:
                brightness = 255 if msg.data else 0
                success = self.serial_manager.control_light(brightness) if self.serial_manager else False
                if success:
                    self.current_light_status = msg.data
                    self.get_logger().info(f"Light {'ON' if msg.data else 'OFF'}")
                else:
                    self.get_logger().error("Failed to control light")
        except Exception as e:
            self.get_logger().error(f"Error in light control callback: {e}")
    
    def destroy_node(self):
        """Clean shutdown of the hardware interface."""
        self.get_logger().info("Shutting down hardware interface")
        
        timers_to_cancel = [
            'state_publish_timer', 'light_status_timer', 'joint_states_timer', 
            'state_timer', 'hardware_status_timer', 'health_check_timer',
            'connection_retry_timer', 'dema_reenable_timer', 'position_request_timer',
            'diagnostic_timer', 'sensor_sim_timer'
        ]
        
        for timer_name in timers_to_cancel:
            if hasattr(self, timer_name):
                timer = getattr(self, timer_name)
                if timer:
                    timer.cancel()
        
        if hasattr(self, 'fallback_motion_timer'):
            self.fallback_motion_timer.cancel()
        
        if hasattr(self, 'state_machine'):
            self.state_machine.transition_to(LuxoState.SHUTDOWN, force=True)
        
        if self.dynamic_adaptation_active and not self.fallback_mode_active:
            self.disable_dynamic_adaptation_mode()
        
        if self.is_connected():
            self.disable_torque()
        
        if hasattr(self, 'serial_manager') and self.serial_manager:
            self.serial_manager.close()
            
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    
    try:
        hardware_interface = RoArmHardwareInterface()
        rclpy.spin(hardware_interface)
    except Exception as e:
        print(f"Error starting hardware interface: {e}")
    finally:
        if 'hardware_interface' in locals():
            hardware_interface.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()