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
        self.declare_parameter('position_request_interval', 5.0)  # Increased to 5s

        # Initialization parameters
        self.declare_parameter('use_hardware_position_on_init', True)
        self.declare_parameter('init_position_timeout', 10.0)
        self.declare_parameter('initialization_duration', 3.0)
        
        # Movement source integration
        self.declare_parameter('enable_movement_source_integration', True)
        
        # Debug mode
        self.declare_parameter('debug_serial_communication', True)
        
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
        
        self.get_logger().info("Hardware interface initialization complete")
    
    def _load_parameters(self):
        """Load all parameters."""
        self.serial_port = self.get_parameter('serial_port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.enable_torque_on_start = self.get_parameter('enable_torque').value
        self.read_throttle = self.get_parameter('read_throttle').value
        self.use_hardware_joint_names = self.get_parameter('use_hardware_joint_names').value
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
        self.position_request_interval = self.get_parameter('position_request_interval').value
        
        # Initialization parameters
        self.use_hardware_position_on_init = self.get_parameter('use_hardware_position_on_init').value
        self.init_position_timeout = self.get_parameter('init_position_timeout').value
        self.initialization_duration = self.get_parameter('initialization_duration').value
        self.enable_movement_source_integration = self.get_parameter('enable_movement_source_integration').value
        
        # Debug parameters
        self.debug_serial_communication = self.get_parameter('debug_serial_communication').value
    
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
        """Handle hardware connection failure with retry"""
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
            
        else:
            self.get_logger().error("Hardware connection failed")
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
                
            
        except Exception as e:
            self.get_logger().error(f"Error during connection retry: {e}")
            self._handle_connection_failure()
    
    
    def _initialize_hardware(self):
        """Initialize hardware with better error handling and diagnostics."""
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
                'spd': 0,
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
        
    
    def _connection_health_check(self):
        """Periodically check connection health and attempt recovery if needed."""
        try:
            if self.serial_manager:
                if not self.serial_manager.is_connected():
                    self.get_logger().warn("Connection lost - attempting recovery")
                    self.connection_active = False
                    self._handle_connection_failure()
                            
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
            if time_in_init < self.initialization_duration:
                return
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
        if not self.dynamic_adaptation_active:
            self.enable_dynamic_adaptation_mode()
    
    def _on_exit_user_control(self):
        """Called when exiting USER_CONTROL state."""
        self.get_logger().info("Exiting USER_CONTROL state (DEMA disabled)")
        if self.dynamic_adaptation_active:
            self.disable_dynamic_adaptation_mode()
    
    def _on_enter_error(self):
        """Called when entering ERROR state."""
        self.get_logger().error("Entering ERROR state")
        try:
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
        
        if self.state_machine.is_in_state(LuxoState.INITIALIZING):
            self.get_logger().debug("Skipping command during initialization")
            return
        
        try:
            positions = msg.position
            
            self.get_logger().debug(f"Safety coordinator command received: {[round(p, 2) for p in positions[:5]]}")
            
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
                
                if self.dynamic_adaptation_active:
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
                
                try:
                    # FIXED: Add delays similar to old version
                    
                    # Use only the working format from old version
                    cmd_format = {
                        'T': 102,
                        'base': joint_positions[0],
                        'shoulder': joint_positions[1],
                        'elbow': joint_positions[2],
                        'wrist': joint_positions[3],
                        'roll': joint_positions[4],
                        'hand': 0.0,
                        'spd': 0,
                        'acc': 10.0
                    }
                    
                    cmd_str = json.dumps(cmd_format)
                    
                    if self.serial_manager.send_command(cmd_str, source):
                        success = True
                        self.get_logger().debug(f"Sent hardware command from {source}")
                        time.sleep(0.1)
                    else:
                        self.get_logger().error(f"Failed to send command")                        
                except Exception as e:
                    self.get_logger().error(f"Error sending hardware command: {e}")
                    success = False
                
                if success:
                    self.commanded_joints = joint_positions.copy()
                    self.is_commanded_movement = True
                    self.last_commanded_movement_time = self.get_clock().now()
                    
                    if self.enable_movement_source_integration:
                        self.publish_movement_source("behavior")
                    
                    return True
                else:
                    self.get_logger().error(f"Failed to send joint command from {source}")
                    return False
                    
        except Exception as e:
            self.get_logger().error(f"Error in send_safe_joint_command from {source}: {e}")
            return False
    
    
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
            if self.connection_active:
                feedback_status = "receiving" if self.position_feedback_received else "NO FEEDBACK"
                msg.data = f"HW: Connected ({self.serial_port}), DEMA: {'Active' if self.dynamic_adaptation_active else 'Inactive'}, Pos: {feedback_status}"
            else:
                msg.data = f"Hardware Interface: Disconnected, Retrying... ({self.connection_retry_count}/{self.max_connection_retries})"
            self.hardware_status_publisher.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing hardware status: {e}")
    
    def request_hardware_position(self):
        """Request the current position from the hardware with multiple formats."""
            
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
                
                # Update last feedback time and set feedback received flag
                self.last_position_feedback_time = self.get_clock().now()
                self.position_feedback_received = True
                self.total_feedback_received += 1
                
                # Critical for DEMA: If in dynamic adaptation mode and position changed significantly
                # but we didn't issue the command ourselves, then this is user movement
                if (self.dynamic_adaptation_active and is_significant and 
                    not getattr(self, 'is_commanded_movement', False)):
                    self.get_logger().info("Detected user manual movement while DEMA is active")
                    # User is physically moving the arm, keep DEMA enabled to allow this
                    # Update the DEMA last active time to prevent timeout
                    # Don't disable DEMA for user movements
                
                # Reset the commanded movement flag
                self.is_commanded_movement = False
                
                # Also update target if we're in physical teaching mode (DEMA)
                if self.dynamic_adaptation_active:
                    # In DEMA mode, update both target and current to match physical position
                    self.target_joints = positions.copy()
                
        except Exception as e:
            self.get_logger().error(f"Error in position feedback callback: {e}")
            import traceback
            self.get_logger().error(traceback.format_exc())

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

    # Hardware control methods
    def enable_torque(self):
        """Enable torque on the arm using the serial manager."""
            
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
        return self.serial_manager.disable_torque() if self.serial_manager else False
    
    def initialize_arm(self):
        """Initialize the arm position using the serial manager."""
        return self.serial_manager.initialize_arm() if self.serial_manager else False
    
    def enable_dynamic_adaptation_mode(self):
        """Enable the dynamic external force adaptation mode."""
            
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
            'diagnostic_timer'
        ]
        
        for timer_name in timers_to_cancel:
            if hasattr(self, timer_name):
                timer = getattr(self, timer_name)
                if timer:
                    timer.cancel()
        
        if hasattr(self, 'state_machine'):
            self.state_machine.transition_to(LuxoState.SHUTDOWN, force=True)
        
        if self.dynamic_adaptation_active:
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