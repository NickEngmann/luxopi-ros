#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, String, Float32
import json
import serial
import threading
import math
import time
import os
import subprocess
import numpy as np
import random

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
        self.declare_parameter('soft_limit_distance', 10.0)  # cm
        self.declare_parameter('hard_limit_distance', 5.0)   # cm
        self.declare_parameter('emergency_stop_distance', 3.0)  # cm
        self.declare_parameter('max_deceleration', 2.0)  # rad/s²
        self.declare_parameter('collision_recovery_timeout', 3.0)  # seconds
        
        # Additional parameters for proactive avoidance
        self.declare_parameter('enable_proactive_avoidance', True)
        self.declare_parameter('proactive_threshold', 15.0)  # cm
        self.declare_parameter('idle_check_interval', 2.0)  # seconds
        self.declare_parameter('avoidance_playfulness', 0.3)  # 0.0-1.0 random factor
        self.declare_parameter('max_idle_time', 30.0)  # seconds before returning to home
        self.declare_parameter('side_avoidance_magnitude', 0.5)  # Rotation magnitude for side avoidance
        self.declare_parameter('consecutive_collision_threshold', 3)  # How many repeated collisions trigger stronger response
        self.declare_parameter('escape_threshold', 20)  # How many consecutive collisions trigger escape mode
        self.declare_parameter('max_retreat_angle', 0.8)  # Maximum shoulder/elbow retreat angle
        self.declare_parameter('escape_mode_duration', 10.0)  # How long to avoid an area after escaping (seconds)
        
        # Add parameter for rest position
        self.declare_parameter('enable_rest_position', True)  # Enable/disable the rest position behavior
        self.declare_parameter('base_rest_position', [0.0, -2.0, 2.0, 1.0, 3.14])  # Base rest position
        self.declare_parameter('rest_variation_range', 0.15)  # Range for position variation
        
        # Make sure to define use_hardware_joint_names parameter
        self.declare_parameter('use_hardware_joint_names', False)
        
        # Get parameters
        self.serial_port = self.get_parameter('serial_port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.enable_torque_on_start = self.get_parameter('enable_torque').value
        self.read_throttle = self.get_parameter('read_throttle').value
        self.enable_collision_avoidance = self.get_parameter('enable_collision_avoidance').value
        self.soft_limit_distance = self.get_parameter('soft_limit_distance').value
        self.hard_limit_distance = self.get_parameter('hard_limit_distance').value
        self.emergency_stop_distance = self.get_parameter('emergency_stop_distance').value
        self.max_deceleration = self.get_parameter('max_deceleration').value
        self.collision_recovery_timeout = self.get_parameter('collision_recovery_timeout').value
        
        self.enable_proactive_avoidance = self.get_parameter('enable_proactive_avoidance').value
        self.proactive_threshold = self.get_parameter('proactive_threshold').value
        self.idle_check_interval = self.get_parameter('idle_check_interval').value
        self.avoidance_playfulness = self.get_parameter('avoidance_playfulness').value
        self.max_idle_time = self.get_parameter('max_idle_time').value
        self.side_avoidance_magnitude = self.get_parameter('side_avoidance_magnitude').value
        self.consecutive_collision_threshold = self.get_parameter('consecutive_collision_threshold').value
        self.escape_threshold = self.get_parameter('escape_threshold').value
        self.max_retreat_angle = self.get_parameter('max_retreat_angle').value
        self.escape_mode_duration = self.get_parameter('escape_mode_duration').value
        
        # Get parameters for rest position (renamed from initial_folding parameters)
        self.enable_rest_position = self.get_parameter('enable_rest_position').value
        self.base_rest_position = self.get_parameter('base_rest_position').value
        self.rest_variation_range = self.get_parameter('rest_variation_range').value
        self.idle_timeout = self.get_parameter('idle_timeout').value
        
        # Make sure to get the parameter value
        self.use_hardware_joint_names = self.get_parameter('use_hardware_joint_names').value
        
        # Connection control
        self.connection_active = False
        self.connection_lock = threading.Lock()
        self.stop_thread = False
        
        # Rest position tracking
        self.rest_position_timer_triggered = False
        self.rest_position_done = False
        self.last_rest_position = None  # Track the last used rest position
        
        # Collision tracking
        self.collision_status = {
            'front': {'active': False, 'distance': float('inf'), 'severity': 'safe', 'consecutive_count': 0},
            'left': {'active': False, 'distance': float('inf'), 'severity': 'safe', 'consecutive_count': 0},
            'right': {'active': False, 'distance': float('inf'), 'severity': 'safe', 'consecutive_count': 0}
        }
        self.collision_lock = threading.Lock()
        self.emergency_stop_active = False
        self.last_emergency_stop_time = 0.0
        self.last_avoidance_direction = None  # Track which direction last triggered avoidance
        
        # Idle state tracking
        self.last_movement_time = time.time()
        self.idle_avoidance_active = False
        self.safe_position_memory = []  # Remember previously safe positions
        self.last_proactive_check = 0.0
        self.home_position = [0.0, 0.3, 0.7, 0.4, 3.14]  # Default safe home (not used for rest)
        self.is_returning_to_rest = False  # Flag to track when we're returning to rest
        
        # Escape mode variables
        self.escape_mode_active = False
        self.escape_mode_start_time = 0.0
        self.unsafe_zones = []  # List of positions to avoid
        self.last_escape_direction = None  # Track last escape direction
        self.retreat_level = 0  # Tracks how far we've retreated
        
        # Joint state tracking
        self.current_joints = [0.0, 0.0, 0.0, 0.0, 3.14]  # base, shoulder, elbow, wrist, hand
        self.target_joints = [0.0, 0.0, 0.0, 0.0, 3.14]
        self.joint_velocities = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.last_command_time = self.get_clock().now()
        
        # Serial port setup
        self.connect_serial()
        
        if self.connection_active:
            # Changed subscription to joint_states_target
            self.subscription = self.create_subscription(
                JointState,
                'joint_states_target',  # Changed from 'joint_states' to 'joint_states_target'
                self.joint_states_callback,
                10)
            
            # Add publisher for actual joint states after collision avoidance
            self.get_logger().info("Creating publisher for actual joint states on /joint_states")
            self.joint_states_publisher = self.create_publisher(
                JointState,
                '/joint_states',
                10)
                
            # Add publisher for joint_states_target for sending idle state commands
            self.joint_states_target_publisher = self.create_publisher(
                JointState,
                '/joint_states_target',
                10)
                
            # Add a direct publishing timer to ensure we're sending messages regularly
            # This guarantees joint state publishing even if no target commands are received
            self.direct_pub_timer = self.create_timer(0.1, self.publish_current_joint_states)
            
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
                
            # Subscribe to detailed collision info
            self.collision_details_sub = self.create_subscription(
                String, 
                '/collision_details',
                self.collision_details_callback, 
                10)
            
            # Create a timer for safety monitoring and motion adjustment
            self.safety_timer = self.create_timer(0.05, self.safety_monitor_callback)
            
            # Add a timer for proactive avoidance when idle
            self.idle_timer = self.create_timer(self.idle_check_interval, self.idle_safety_check)
            self.get_logger().info("RoArm hardware interface initialized")
            
            if self.enable_collision_avoidance:
                self.get_logger().info("Collision avoidance enabled")
                if self.enable_proactive_avoidance:
                    self.get_logger().info("Proactive avoidance enabled - arm will actively avoid obstacles when idle")
                else:
                    self.get_logger().info("Proactive avoidance disabled - arm will only avoid obstacles during movement")
            else:
                self.get_logger().warn("Collision avoidance disabled - robot will not react to obstacles")
        else:
            self.get_logger().error("Failed to initialize hardware interface")
    
    def front_collision_callback(self, msg):
        with self.collision_lock:
            was_active = self.collision_status['front']['active']
            self.collision_status['front']['active'] = msg.data
            if msg.data and not was_active:
                self.get_logger().warn("Front collision warning activated")
                self.collision_status['front']['consecutive_count'] = 0
                # Force an immediate check for avoidance when we first detect a collision
                if self.enable_proactive_avoidance and not self.is_animating():
                    self.last_proactive_check = 0.0  # Force immediate check
            elif msg.data and was_active:
                # Increment consecutive detection counter
                self.collision_status['front']['consecutive_count'] += 1
                if self.collision_status['front']['consecutive_count'] % self.consecutive_collision_threshold == 0:
                    self.get_logger().warn(f"Persistent front collision! Count: {self.collision_status['front']['consecutive_count']}")
                    # Force more frequent checks for persistent collisions
                    if self.enable_proactive_avoidance and not self.is_animating():
                        self.last_proactive_check = 0.0  # Force immediate check
                        
                # Check if we need to trigger escape mode
                if self.collision_status['front']['consecutive_count'] > self.escape_threshold:
                    self.get_logger().warn(f"Persistent collision detected ({self.collision_status['front']['consecutive_count']}), returning to idle state")
                    self.return_to_idle_state("Persistent collision idle return")
                    if not self.escape_mode_active:
                        self._activate_escape_mode('front')
            elif was_active and not msg.data:
                self.get_logger().info("Front collision warning cleared")
                self.collision_status['front']['consecutive_count'] = 0
    
    def left_collision_callback(self, msg):
        with self.collision_lock:
            was_active = self.collision_status['left']['active']
            self.collision_status['left']['active'] = msg.data
            if msg.data and not was_active:
                self.get_logger().warn("Left collision warning activated")
                self.collision_status['left']['consecutive_count'] = 0
            elif msg.data and was_active:
                # Increment consecutive detection counter
                self.collision_status['left']['consecutive_count'] += 1
                if self.collision_status['left']['consecutive_count'] % self.consecutive_collision_threshold == 0:
                    self.get_logger().warn(f"Persistent left collision! Count: {self.collision_status['left']['consecutive_count']}")
                
                # Check if we need to trigger escape mode
                if self.collision_status['left']['consecutive_count'] > self.escape_threshold:
                    if not self.escape_mode_active:
                        self._activate_escape_mode('left')
            elif was_active and not msg.data:
                self.get_logger().info("Left collision warning cleared")
                self.collision_status['left']['consecutive_count'] = 0
    
    def right_collision_callback(self, msg):
        with self.collision_lock:
            was_active = self.collision_status['right']['active']
            self.collision_status['right']['active'] = msg.data
            if msg.data and not was_active:
                self.get_logger().warn("Right collision warning activated")
                self.collision_status['right']['consecutive_count'] = 0
            elif msg.data and was_active:
                # Increment consecutive detection counter
                self.collision_status['right']['consecutive_count'] += 1
                if self.collision_status['right']['consecutive_count'] % self.consecutive_collision_threshold == 0:
                    self.get_logger().warn(f"Persistent right collision! Count: {self.collision_status['right']['consecutive_count']}")
                
                # Check if we need to trigger escape mode
                if self.collision_status['right']['consecutive_count'] > self.escape_threshold:
                    if not self.escape_mode_active:
                        self._activate_escape_mode('right')
            elif was_active and not msg.data:
                self.get_logger().info("Right collision warning cleared")
                self.collision_status['right']['consecutive_count'] = 0
    
    def _activate_escape_mode(self, direction):
        """Activate escape mode for persistent collisions"""
        # Check if we're currently in an animation - if so, we should be more careful
        in_animation = self.is_animating()
        
        self.escape_mode_active = True
        self.escape_mode_start_time = time.time()
        self.last_escape_direction = direction
        self.retreat_level = 0  # Start fresh retreat sequence
        
        # Record current position as unsafe
        unsafe_pos = self.current_joints.copy()
        self._add_unsafe_zone(unsafe_pos)
        
        self.get_logger().warn(f"ESCAPE MODE ACTIVATED: Persistent {direction} collision detected!")
        
        # If in animation, use a gentler escape that won't completely interrupt
        if in_animation:
            self.get_logger().info("Animation in progress - using gentler escape maneuver")
            self._execute_animation_safe_escape(direction)
        else:
            # Normal dramatic escape for non-animation situations
            self._execute_escape_maneuver(direction)
            
        # Set a short timeout for animation cases to allow resuming animation
        if in_animation:
            self.escape_mode_duration = 3.0  # Short timeout
        else:
            self.escape_mode_duration = 10.0  # Normal timeout
    
    def _execute_animation_safe_escape(self, direction):
        """Execute a gentler escape maneuver that won't completely disrupt animations"""
        try:
            # Start with current position
            new_position = self.current_joints.copy()
            
            # Smaller adjustments than the normal escape maneuver
            if direction == 'front':
                # Smaller rotation and retreat
                rotation_angle = 0.3 if random.random() > 0.5 else -0.3
                shoulder_retreat = 0.2
                elbow_retreat = 0.3
                
                new_position[0] += rotation_angle
                new_position[1] += shoulder_retreat
                new_position[2] += elbow_retreat
                new_position[3] -= (shoulder_retreat + elbow_retreat) * 0.3
                
                self.get_logger().warn(f"Executing animation-safe front escape")
                
            elif direction == 'left':
                # Smaller right rotation
                rotation_angle = 0.4
                new_position[0] += rotation_angle
                new_position[1] += 0.1
                
                self.get_logger().warn(f"Executing animation-safe right rotation escape")
                
            elif direction == 'right':
                # Smaller left rotation
                rotation_angle = 0.4
                new_position[0] -= rotation_angle
                new_position[1] += 0.1
                
                self.get_logger().warn(f"Executing animation-safe left rotation escape")
            
            # Move to the new position with high priority
            self.move_to_safe_position(new_position, "Animation-safe escape", True)
            
        except Exception as e:
            self.get_logger().error(f"Error in animation-safe escape maneuver: {e}")
            self.escape_mode_active = False
    
    def _add_unsafe_zone(self, position, radius=0.3):
        """Add a position to the list of unsafe zones to avoid"""
        # Store the position and a radius around it to avoid
        self.unsafe_zones.append((position, radius))
        
        # Limit the size of unsafe zones list
        if len(self.unsafe_zones) > 5:
            self.unsafe_zones.pop(0)
    
    def _execute_escape_maneuver(self, direction):
        """Execute a decisive escape maneuver to break free from persistent collisions"""
        try:
            # Start with current position
            new_position = self.current_joints.copy()
            
            # Based on the robot's joint limits from animation_command.py
            # We know we can move:
            # base: full rotation range (-1.57 to 1.57 or more)
            # shoulder: can go down to -2.0 (folded back) or up to ~0.9
            # elbow: can go from near 0 up to around 2.0
            # wrist: roughly -0.8 to 1.6
            
            if direction == 'front':
                # For front collisions, make a dramatic retreat
                # Mix of pulling back and rotation
                rotation_angle = 0.8 if random.random() > 0.5 else -0.8  # Random direction but large
                
                # Use increasing retreat levels that get more extreme
                shoulder_retreat = min(0.4 + (self.retreat_level * 0.15), self.max_retreat_angle)
                elbow_retreat = min(0.6 + (self.retreat_level * 0.2), self.max_retreat_angle)
                
                # Dramatic backward fold - much larger than normal avoidance
                new_position[0] += rotation_angle  # Significant rotation
                new_position[1] += shoulder_retreat  # Significant shoulder pullback  
                new_position[2] += elbow_retreat  # Significant elbow fold
                
                # Adjust wrist to maintain end effector orientation
                new_position[3] -= (shoulder_retreat + elbow_retreat) * 0.5
                
                self.get_logger().warn(f"Executing DRAMATIC front escape - level {self.retreat_level}")
                
            elif direction == 'left':
                # For left collisions, make a dramatic right turn
                rotation_angle = min(0.8 + (self.retreat_level * 0.15), 1.5)  # Increasing rotation
                
                new_position[0] += rotation_angle  # Strong clockwise rotation (right)
                new_position[1] += 0.2  # Some shoulder pullback for added clearance
                
                self.get_logger().warn(f"Executing DRAMATIC right rotation escape - level {self.retreat_level}")
                
            elif direction == 'right':
                # For right collisions, make a dramatic left turn
                rotation_angle = min(0.8 + (self.retreat_level * 0.15), 1.5)  # Increasing rotation
                
                new_position[0] -= rotation_angle  # Strong counter-clockwise rotation (left)
                new_position[1] += 0.2  # Some shoulder pullback for added clearance
                
                self.get_logger().warn(f"Executing DRAMATIC left rotation escape - level {self.retreat_level}")
            
            # Increment retreat level for next time if this doesn't work
            self.retreat_level += 1
            
            # Move to the new position with high priority
            self.move_to_safe_position(new_position, "Emergency escape", True)
            
        except Exception as e:
            self.get_logger().error(f"Error in escape maneuver: {e}")
            self.escape_mode_active = False
    
    # Distance callbacks for more precise control
    def front_proximity_callback(self, msg):
        with self.collision_lock:
            # Convert proximity to approximate distance in cm (higher value = closer object)
            # This is a rough approximation since APDS9960 doesn't provide actual distance
            # Max proximity is typically around 255
            proximity = max(1, min(255, msg.data))
            distance = max(1.0, 30.0 * (1.0 - proximity / 255.0))
            self.collision_status['front']['distance'] = distance
    
    def left_distance_callback(self, msg):
        with self.collision_lock:
            self.collision_status['left']['distance'] = msg.data
    
    def right_distance_callback(self, msg):
        with self.collision_lock:
            self.collision_status['right']['distance'] = msg.data
    
    # Severity callbacks
    def front_severity_callback(self, msg):
        with self.collision_lock:
            self.collision_status['front']['severity'] = msg.data
    
    def left_severity_callback(self, msg):
        with self.collision_lock:
            self.collision_status['left']['severity'] = msg.data
    
    def right_severity_callback(self, msg):
        with self.collision_lock:
            self.collision_status['right']['severity'] = msg.data
    
    def collision_details_callback(self, msg):
        """Process detailed collision information"""
        try:
            # Expected format: "direction:distance:severity"
            parts = msg.data.split(':')
            if len(parts) == 3:
                direction, distance_str, severity = parts
                distance = float(distance_str)
                
                with self.collision_lock:
                    if direction in self.collision_status:
                        self.collision_status[direction]['distance'] = distance
                        self.collision_status[direction]['severity'] = severity
                        
                        # Check for emergency stop condition
                        if distance <= self.emergency_stop_distance and severity == "danger":
                            self.trigger_emergency_stop(direction, distance)
        except Exception as e:
            self.get_logger().error(f"Error processing collision details: {e}")
    
    def trigger_emergency_stop(self, direction, distance):
        """Initiate emergency stop procedure"""
        now = time.time()
        
        # Don't retrigger emergency stop if we're already handling one
        # or if we've had one very recently (to prevent oscillation)
        if self.emergency_stop_active or (now - self.last_emergency_stop_time < self.collision_recovery_timeout):
            return
            
        self.emergency_stop_active = True
        self.last_emergency_stop_time = now
        self.get_logger().error(f"EMERGENCY STOP triggered! {direction} collision at {distance:.1f}cm")
        
        # Update last movement time
        self.last_movement_time = now
        
        # Stop all joint movement with controlled deceleration
        self.execute_emergency_stop()
        
        # Clear the safe position memory since the environment has changed
        self.safe_position_memory = []
    
    def execute_emergency_stop(self):
        """Execute a controlled emergency stop with smooth deceleration"""
        # Calculate current velocities first
        self.estimate_joint_velocities()
        
        # Calculate deceleration time based on current velocities
        max_vel = max(abs(v) for v in self.joint_velocities)
        if max_vel < 0.01:  # Almost stationary
            self.emergency_stop_active = False
            return
            
        decel_time = max_vel / self.max_deceleration
        steps = max(10, int(decel_time / 0.05))  # Minimum 10 steps
        
        self.get_logger().warn(f"Executing controlled stop over {decel_time:.2f}s ({steps} steps)")
        
        # Start from current position
        current_pos = self.current_joints.copy()
        
        # Gradually reduce velocities to zero
        for i in range(1, steps + 1):
            decel_factor = 1.0 - (i / steps)
            
            # Calculate new velocities and positions
            new_velocities = [v * decel_factor for v in self.joint_velocities]
            new_positions = [current_pos[j] + new_velocities[j] * (decel_time / steps) 
                            for j in range(len(current_pos))]
            
            # Send command to joints
            self.send_safe_joint_command(new_positions, "Emergency stop deceleration")
            
            # Short sleep for smoother motion
            time.sleep(decel_time / steps)
        
        # Final stop command with zero velocity
        self.send_safe_joint_command(new_positions, "Emergency stop complete")
        self.emergency_stop_active = False
        
        self.get_logger().warn("Emergency stop completed - robot has stopped")
    
    def estimate_joint_velocities(self):
        """Estimate current joint velocities based on recent commands"""
        current_time = self.get_clock().now()
        dt = (current_time - self.last_command_time).nanoseconds / 1e9
        
        if dt > 0:
            # Calculate approximate velocities
            self.joint_velocities = [(self.target_joints[i] - self.current_joints[i]) / dt 
                                     for i in range(len(self.current_joints))]
        
        # Update tracking variables
        self.last_command_time = current_time
        self.current_joints = self.target_joints.copy()
    
    def check_fix_permissions(self):
        """Check and fix permissions on the serial port if needed"""
        try:
            self.get_logger().info(f"Checking permissions on {self.serial_port}")
            
            # Check if we have read/write access
            if not os.access(self.serial_port, os.R_OK | os.W_OK):
                self.get_logger().warn(f"Insufficient permissions on {self.serial_port}, attempting to fix")
                
                try:
                    # Try to fix permissions using sudo chmod
                    cmd = ['sudo', 'chmod', '777', self.serial_port]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        self.get_logger().info("Successfully updated port permissions")
                        return True
                    else:
                        self.get_logger().error(f"Failed to update permissions: {result.stderr}")
                        return False
                        
                except subprocess.SubprocessError as e:
                    self.get_logger().error(f"Failed to run chmod command: {e}")
                    return False
            
            return True  # Permissions are already OK
            
        except Exception as e:
            self.get_logger().error(f"Error checking/fixing permissions: {e}")
            return False
    
    def connect_serial(self):
        """Establish connection to the serial port"""
        # Check permissions first
        if not self.check_fix_permissions():
            self.get_logger().warn("Continuing without fixing permissions, may fail")
        
        try:
            self.ser = serial.Serial(self.serial_port, baudrate=self.baud_rate, dsrdtr=None, timeout=1)
            self.ser.setRTS(False)
            self.ser.setDTR(False)
            self.get_logger().info(f"Serial port {self.serial_port} connected successfully at {self.baud_rate} baud")
            
            # Update connection status
            with self.connection_lock:
                self.connection_active = True
            
            # Start a thread to read responses from the arm
            self.read_thread = threading.Thread(target=self.read_serial)
            self.read_thread.daemon = True
            self.read_thread.start()
            
            # Initialize the arm by enabling torque if configured
            if self.enable_torque_on_start:
                self.enable_torque()
                time.sleep(0.5)
                self.initialize_arm()
            
            return True
            
        except serial.SerialException as e:
            self.get_logger().error(f"Failed to open serial port: {e}")
            with self.connection_lock:
                self.connection_active = False
            return False
    
    def enable_torque(self):
        """Enable torque on the arm."""
        # Send torque lock command (T:210, cmd:1)
        torque_cmd = json.dumps({'T': 210, 'cmd': 1})
        success = self.send_command(torque_cmd, "Enabling torque lock")
        if success:
            self.get_logger().info("Torque lock enabled")
        else:
            self.get_logger().error("Failed to enable torque")
        return success
    
    def disable_torque(self):
        """Disable torque on the arm."""
        # Send torque unlock command (T:210, cmd:0)
        torque_cmd = json.dumps({'T': 210, 'cmd': 0})
        success = self.send_command(torque_cmd, "Disabling torque lock")
        if success:
            self.get_logger().info("Torque lock disabled")
        else:
            self.get_logger().error("Failed to disable torque")
        return success
    
    def initialize_arm(self):
        """Initialize the arm by moving to home position."""
        # Send initialization command (T:100)
        init_cmd = json.dumps({'T': 100})
        success = self.send_command(init_cmd, "Initializing arm position")
        if success:
            self.get_logger().info("Arm initialized to home position")
        else:
            self.get_logger().error("Failed to initialize arm position")
        return success
    
    def send_command(self, cmd_str, description=""):
        """Send a command to the robot arm."""
        if not self.is_connected():
            self.get_logger().error("Cannot send command: Serial connection is not active")
            return False
        
        try:
            # Add description to logs
            if description:
                self.get_logger().debug(f"Sending {description}: {cmd_str}")
            
            # Ensure command ends with newline
            if not cmd_str.endswith('\n'):
                cmd_str += '\n'
            
            # Write command to serial port
            self.ser.write(cmd_str.encode())
            self.ser.flush()
            
            # Allow time to process
            time.sleep(0.1)
            
            return True
        except Exception as e:
            self.get_logger().error(f"Serial write error: {e}")
            with self.connection_lock:
                self.connection_active = False
            return False
    
    def is_connected(self):
        """Thread-safe method to check connection status"""
        with self.connection_lock:
            return self.connection_active and hasattr(self, 'ser') and self.ser and self.ser.is_open
    
    def read_serial(self):
        """Read serial data in a separate thread."""
        while not self.stop_thread:
            if self.is_connected():
                try:
                    # Apply throttling to reduce CPU usage
                    time.sleep(self.read_throttle)
                    
                    if self.ser.in_waiting > 0:
                        data = self.ser.readline().decode('utf-8').strip()
                        if data:
                            # Try to parse as JSON for better logging
                            try:
                                json_data = json.loads(data)
                                self.get_logger().debug(f"Received: {json.dumps(json_data)}")
                            except json.JSONDecodeError:
                                # Not JSON, just log as text
                                self.get_logger().debug(f"Received: {data}")
                except Exception as e:
                    self.get_logger().error(f"Error reading from serial: {e}")
            else:
                # Exit thread if connection is lost
                break
    
    def safety_monitor_callback(self):
        """Periodic callback to monitor safety and adjust motion if needed"""
        if not self.enable_collision_avoidance:
            return
            
        # Skip if emergency stop is active
        if self.emergency_stop_active:
            return
            
        try:
            # Check if escape mode is active and should be updated or deactivated
            current_time = time.time()
            if self.escape_mode_active:
                if current_time - self.escape_mode_start_time > self.escape_mode_duration:
                    self.escape_mode_active = False
                    self.get_logger().info("Escape mode deactivated - normal operation resuming")
                    
                    # Force publish current position to ensure animation can continue
                    self.publish_actual_joint_states(self.current_joints)
                else:
                    # Check if we're still seeing the same collision that triggered escape mode
                    with self.collision_lock:
                        # Make this check less aggressive during animations
                        if self.is_animating():
                            # During animation, we're less reactive to avoid interruptions
                            persistent_collision = False
                        else:
                            persistent_collision = (
                                (self.last_escape_direction == 'front' and 
                                 self.collision_status['front']['active'] and 
                                 self.collision_status['front']['consecutive_count'] > self.consecutive_collision_threshold) or
                                (self.last_escape_direction == 'left' and 
                                 self.collision_status['left']['active'] and 
                                 self.collision_status['left']['consecutive_count'] > self.consecutive_collision_threshold) or
                                (self.last_escape_direction == 'right' and 
                                 self.collision_status['right']['active'] and 
                                 self.collision_status['right']['consecutive_count'] > self.consecutive_collision_threshold)
                            )
                            
                        if persistent_collision:
                            # Still in collision - try another escape move, but check if in animation first
                            if self.is_animating():
                                # Use gentler escape for animations
                                self._execute_animation_safe_escape(self.last_escape_direction)
                            else:
                                self._execute_escape_maneuver(self.last_escape_direction)
            
            # Check if we need to recover from a recent emergency stop
            if current_time - self.last_emergency_stop_time < self.collision_recovery_timeout:
                # We're in recovery period - only allow very slow, deliberate movements
                return
                
            # Get current collision status
            with self.collision_lock:
                front_status = self.collision_status['front'].copy()
                left_status = self.collision_status['left'].copy()
                right_status = self.collision_status['right'].copy()
            
            # Check if any emergency conditions exist
            if ((front_status['severity'] == 'danger' and front_status['distance'] <= self.emergency_stop_distance) or
                (left_status['severity'] == 'danger' and left_status['distance'] <= self.emergency_stop_distance) or
                (right_status['severity'] == 'danger' and right_status['distance'] <= self.emergency_stop_distance)):
                
                # Determine which direction has the closest obstacle
                if front_status['distance'] <= min(left_status['distance'], right_status['distance']):
                    self.trigger_emergency_stop('front', front_status['distance'])
                elif left_status['distance'] <= right_status['distance']:
                    self.trigger_emergency_stop('left', left_status['distance'])
                else:
                    self.trigger_emergency_stop('right', right_status['distance'])
                return
                
            # If we're actively moving (e.g. from animation commands), check for dynamic adjustment
            time_since_last_movement = time.time() - self.last_movement_time
            if time_since_last_movement < 0.5:  # We've moved recently
                # If we already have an active collision, we might need to adjust the path
                if front_status['active'] or left_status['active'] or right_status['active']:
                    # Calculate a safe adjustment vector based on collision directions
                    self.adjust_path_for_collision(front_status, left_status, right_status)
        
        except Exception as e:
            self.get_logger().error(f"Error in safety monitor: {e}")
    
    def adjust_path_for_collision(self, front_status, left_status, right_status):
        """Adjust the current motion path to avoid obstacles"""
        # Calculate adjustment factors based on distance and severity
        front_factor = self.calculate_adjustment_factor(front_status)
        left_factor = self.calculate_adjustment_factor(left_status)
        right_factor = self.calculate_adjustment_factor(right_status)
        
        # If no significant adjustments needed, return early
        if front_factor < 0.1 and left_factor < 0.1 and right_factor < 0.1:
            return
            
        # Create an adjustment for the current target joints
        adjusted_targets = self.target_joints.copy()
        
        # Adjust base rotation based on left/right obstacles with increasing strength
        # For frontal collisions, add more dramatic backward movement
        
        # Stronger base adjustment for persistent collisions
        base_factor_multiplier = 1.0
        if left_status['consecutive_count'] > self.consecutive_collision_threshold:
            base_factor_multiplier = min(3.0, 1.0 + left_status['consecutive_count'] * 0.05)
        if right_status['consecutive_count'] > self.consecutive_collision_threshold:
            base_factor_multiplier = max(base_factor_multiplier, 
                                         min(3.0, 1.0 + right_status['consecutive_count'] * 0.05))
        
        # Calculate base adjustment with enhanced response
        base_adjustment = (right_factor - left_factor) * 0.3 * base_factor_multiplier
        adjusted_targets[0] += base_adjustment
        
        # Front obstacles primarily affect the arm extension
        if front_factor > 0.1:
            # Enhanced response for persistent front collisions
            persistence_multiplier = 1.0
            if front_status['consecutive_count'] > self.consecutive_collision_threshold:
                persistence_multiplier = min(3.0, 1.0 + front_status['consecutive_count'] * 0.05)
                
            # Enhanced shoulder and elbow adjustments (pull back more strongly)
            shoulder_adjustment = front_factor * 0.4 * persistence_multiplier
            elbow_adjustment = front_factor * 0.5 * persistence_multiplier
            adjusted_targets[1] += shoulder_adjustment
            adjusted_targets[2] += elbow_adjustment
            
            # Adjust wrist to maintain end effector orientation
            adjusted_targets[3] -= (shoulder_adjustment + elbow_adjustment) * 0.5
        
        # Send the adjusted target positions to the arm
        if front_factor > 0.5 or left_factor > 0.5 or right_factor > 0.5:
            self.get_logger().info(f"Dynamic collision avoidance: adjusting path (front factor: {front_factor:.2f}, persistence: {front_status['consecutive_count']})")
            
        self.send_safe_joint_command(adjusted_targets, "Collision avoidance adjustment")
        
        # Update last movement time when we make an adjustment
        self.last_movement_time = time.time()
    
    def calculate_adjustment_factor(self, status):
        """Calculate adjustment factor (0.0-1.0) based on collision status"""
        if not status['active'] or status['severity'] == 'safe':
            return 0.0
            
        # Calculate factor based on distance
        if status['distance'] <= self.hard_limit_distance:
            # Hard limit - strong adjustment
            return 1.0
        elif status['distance'] <= self.soft_limit_distance:
            # Soft limit - graduated adjustment
            # Linear interpolation between 0.0 and 1.0
            range_fraction = (self.soft_limit_distance - status['distance']) / \
                             (self.soft_limit_distance - self.hard_limit_distance)
            return max(0.0, min(1.0, range_fraction))
        else:
            return 0.0
    
    def joint_states_callback(self, msg):
        """Handle joint states and send to hardware with collision avoidance."""
        if not self.is_connected() or self.emergency_stop_active:
            return
        
        try:
            # Update last movement time
            current_time = time.time()
            self.last_movement_time = current_time
            
            # Track recent command times to help detect animations
            if not hasattr(self, 'recent_command_times'):
                self.recent_command_times = []
            
            self.recent_command_times.append(current_time)
            if len(self.recent_command_times) > 5:  # Keep last 5 command times
                self.recent_command_times.pop(0)
            
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
                positions[indices['hand']] if 'hand' in indices else 3.14  # Default closed gripper if not specified
            ]
            
            # Store for velocity estimation
            self.target_joints = target_positions.copy()
            
            # Log the incoming command
            self.get_logger().debug(f"Received joint_states_target: {[round(p, 2) for p in target_positions]}")
            
            # Check if we're in escape mode during animation
            if self.escape_mode_active and self.is_animating():
                self.get_logger().info("Animation continuing during escape mode - shortening escape duration")
                # Shorten the escape duration to allow animation to continue
                remaining_time = self.escape_mode_start_time + self.escape_mode_duration - current_time
                if remaining_time > 1.0:  # If more than 1 second left
                    self.escape_mode_duration = current_time - self.escape_mode_start_time + 1.0  # Shorten to 1 more second
            
            # Apply collision avoidance and send command
            self.send_safe_joint_command(target_positions, "Joint control")
            
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
            
        if self.emergency_stop_active:
            self.get_logger().warn("Emergency stop active - ignoring command")
            return False
            
        # Apply safety limits based on collision status
        if self.enable_collision_avoidance:
            with self.collision_lock:
                safe_positions = self.apply_safety_limits(positions)
        else:
            safe_positions = positions
            
        try:
            # Use T:102 command for joint control in radians
            # From API: {"T":102,"base":0,"shoulder":0,"elbow":1.57,"hand":3.14,"spd":0,"acc":10}
            joint_cmd = {
                'T': 102,
                'base': safe_positions[0],
                'shoulder': safe_positions[1],
                'elbow': safe_positions[2],
                'roll': -1.5,
                'hand': safe_positions[4],  # Gripper
                'spd': 0,  # Max speed
                'acc': 10  # Gentle acceleration
            }
            
            # Add wrist joint if present
            if len(safe_positions) > 3:
                joint_cmd['wrist'] = safe_positions[3]
            
            # Update current joints first with the safe positions
            self.current_joints = list(safe_positions)
            
            # Publish the actual safe positions for visualization and monitoring
            self.publish_actual_joint_states(safe_positions)
            
            # Add more info for debugging
            self.get_logger().debug(f"Sending command to hardware: {description}")
            
            # Send command as JSON
            cmd_str = json.dumps(joint_cmd)
            return self.send_command(cmd_str, description)
            
        except Exception as e:
            self.get_logger().error(f"Error sending safe joint commands: {e}")
            return False

    def publish_actual_joint_states(self, positions):
        """Publish the actual joint positions after collision avoidance."""
        try:
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
            
            # Add debug logging
            self.get_logger().debug(f"Publishing to /joint_states: {[round(p, 2) for p in positions]}")
            
            # Publish the message
            self.joint_states_publisher.publish(msg)
            
            # Test if message was published (this adds a bit of overhead but helps debugging)
            # Remove this once confirmed working
            test_msg = self.joint_states_publisher.get_subscription_count()
            if test_msg == 0:
                self.get_logger().debug("No subscribers to /joint_states - message might not be received")
            
        except Exception as e:
            self.get_logger().error(f"Error publishing actual joint states: {e}")
            # Add stack trace for better debugging
            import traceback
            self.get_logger().error(traceback.format_exc())

    def test_joint_states_publisher(self):
        """Test function to verify the joint_states publisher is working."""
        if hasattr(self, 'current_joints') and len(self.current_joints) > 0:
            self.get_logger().info("Publishing test message to /joint_states")
            self.publish_actual_joint_states(self.current_joints)

    def apply_safety_limits(self, positions):
        """Apply safety limits to joint positions based on collision status"""
        # Get a copy of the target positions
        safe_positions = positions.copy()
        
        # Check for front collisions (primarily affects shoulder, elbow, wrist)
        if self.collision_status['front']['active']:
            severity = self.collision_status['front']['severity']
            distance = self.collision_status['front']['distance']
            
            if severity == 'danger' or distance <= self.hard_limit_distance:
                # Apply hard limits - significant restriction on forward movement
                safe_positions[1] = max(safe_positions[1], self.current_joints[1])  # Don't decrease shoulder angle
                safe_positions[2] = max(safe_positions[2], self.current_joints[2])  # Don't decrease elbow angle
                
            elif severity == 'warning' or distance <= self.soft_limit_distance:
                # Apply soft limits - partial restriction
                # Calculate how much we're allowing change (0.0 = none, 1.0 = full)
                limit_factor = min(1.0, (distance - self.hard_limit_distance) / 
                                  (self.soft_limit_distance - self.hard_limit_distance))
                
                # Apply graduated limits
                if safe_positions[1] < self.current_joints[1]:  # If moving shoulder forward
                    delta = self.current_joints[1] - safe_positions[1]
                    safe_positions[1] = self.current_joints[1] - (delta * limit_factor)
                    
                if safe_positions[2] < self.current_joints[2]:  # If extending elbow
                    delta = self.current_joints[2] - safe_positions[2]
                    safe_positions[2] = self.current_joints[2] - (delta * limit_factor)
        
        # Check for left collisions (primarily affects base rotation)
        if self.collision_status['left']['active']:
            severity = self.collision_status['left']['severity']
            distance = self.collision_status['left']['distance']
            
            # Limits on counter-clockwise rotation (negative direction)
            if (severity == 'danger' or distance <= self.hard_limit_distance) and safe_positions[0] < self.current_joints[0]:
                # Hard limit - prevent further rotation left
                safe_positions[0] = self.current_joints[0]
            elif (severity == 'warning' or distance <= self.soft_limit_distance) and safe_positions[0] < self.current_joints[0]:
                # Soft limit - partial restriction
                limit_factor = min(1.0, (distance - self.hard_limit_distance) / 
                                  (self.soft_limit_distance - self.hard_limit_distance))
                delta = self.current_joints[0] - safe_positions[0]
                safe_positions[0] = self.current_joints[0] - (delta * limit_factor)
        
        # Check for right collisions (primarily affects base rotation)
        if self.collision_status['right']['active']:
            severity = self.collision_status['right']['severity']
            distance = self.collision_status['right']['distance']
            
            # Limits on clockwise rotation (positive direction)
            if (severity == 'danger' or distance <= self.hard_limit_distance) and safe_positions[0] > self.current_joints[0]:
                # Hard limit - prevent further rotation right
                safe_positions[0] = self.current_joints[0]
            elif (severity == 'warning' or distance <= self.soft_limit_distance) and safe_positions[0] > self.current_joints[0]:
                # Soft limit - partial restriction
                limit_factor = min(1.0, (distance - self.hard_limit_distance) / 
                                  (self.soft_limit_distance - self.hard_limit_distance))
                delta = safe_positions[0] - self.current_joints[0]
                safe_positions[0] = self.current_joints[0] + (delta * limit_factor)
        
        # Add additional check for escape mode
        if self.escape_mode_active:
            # In escape mode, we relax some limits to allow more dramatic movements
            # We'll only apply hard limits here, no soft limits
            pass  # Continue with existing logic, but with modified thresholds
        
        return safe_positions
    
    def get_joint_mappings(self):
        """Return mappings between ROS joint names and RoArm joint names."""
        return {
            'base': 'base',
            'shoulder': 'shoulder',
            'elbow': 'elbow',
            'wrist': 'wrist',
            'hand': 'hand',
            # Add alternative mappings from your system if needed
            'base_to_L1': 'base',
            'L1_to_L2': 'shoulder',
            'L2_to_L3': 'elbow',
            'L3_to_L4': 'wrist'
        }
    
    def destroy_node(self):
        """Clean up when node is destroyed."""
        self.get_logger().info("Shutting down hardware interface")
        self.stop_thread = True
        
        # Disable torque before closing
        if self.is_connected():
            self.disable_torque()
        
        if self.read_thread:
            self.read_thread.join(timeout=1.0)
            
        if hasattr(self, 'ser') and self.ser and self.ser.is_open:
            self.ser.close()
            
        super().destroy_node()
    
    def record_safe_position(self):
        """Record the current position as safe if no collisions are detected"""
        # Only record if we're not in a collision state
        with self.collision_lock:
            if (not self.collision_status['front']['active'] and 
                not self.collision_status['left']['active'] and 
                not self.collision_status['right']['active']):
                
                # Create a copy of the current joints
                safe_pos = self.current_joints.copy()
                
                # Limit the size of the memory
                if len(self.safe_position_memory) > 5:
                    self.safe_position_memory.pop(0)  # Remove oldest
                    
                # Add to memory if it's different enough from existing positions
                if not self.safe_position_memory or self._different_enough(safe_pos, self.safe_position_memory[-1]):
                    self.safe_position_memory.append(safe_pos)
                    self.get_logger().debug(f"Recorded new safe position: {[round(p, 2) for p in safe_pos]}")
    
    def _different_enough(self, pos1, pos2, threshold=0.2):
        """Check if two positions are different enough to be considered distinct"""
        # Calculate Euclidean distance in joint space
        sum_squared = sum((p1 - p2) ** 2 for p1, p2 in zip(pos1, pos2))
        return math.sqrt(sum_squared) > threshold
        
    def idle_safety_check(self):
        """Check for obstacles when the arm is idle and move proactively if needed"""
        if not self.enable_proactive_avoidance:
            return
            
        current_time = time.time()
        
        # Check if escape mode is active
        if self.escape_mode_active:
            # Nothing else to do here - the safety monitor callback will handle escape mode
            return
            
        # Update our record of safe positions occasionally
        if current_time - self.last_movement_time > 1.0:  # If we've been still for 1 second
            self.record_safe_position()
        
        # Check if we've been idle for a while
        idle_time = current_time - self.last_movement_time
        
        # Return to rest position if we've been idle for the timeout period
        # and we're not already in the process of returning to rest
        if idle_time > self.idle_timeout and not self.is_returning_to_rest:
            self.get_logger().info(f"Been idle for {idle_time:.1f}s, returning to rest position")
            self.go_to_rest_position("Idle timeout rest position")
            return
        
        # Skip the rest if we're already in an avoidance maneuver
        if self.idle_avoidance_active or self.emergency_stop_active:
            return
            
        # Make idle collision checks more responsive - check more frequently
        # Reduced from 1.0 to 0.5 seconds for faster response
        if current_time - self.last_proactive_check < 0.5:
            return
            
        self.last_proactive_check = current_time
            
        # Check for obstacles that need proactive avoidance
        with self.collision_lock:
            most_critical_direction = None
            lowest_distance = float('inf')
            highest_consecutive_count = 0
            
            # Check all directions and choose the most critical one
            for direction in ['front', 'left', 'right']:
                status = self.collision_status[direction]
                
                # Lower the threshold for idle response - more sensitive when idle
                # Original was self.proactive_threshold
                idle_threshold = self.proactive_threshold * 1.2  # 20% more sensitive when idle
                
                # Check if this direction has a collision and is within threshold
                if status['active'] or status['distance'] < idle_threshold:
                    
                    # Calculate criticality score based on distance and consecutive count
                    # Lower distance or higher consecutive count means higher priority
                    criticality_score = status['consecutive_count'] * 2  # Weight consecutive detections heavily
                    
                    if status['severity'] == 'danger':
                        criticality_score += 10  # Add high priority for danger situations
                    elif status['severity'] == 'warning':
                        criticality_score += 5   # Add medium priority for warnings
                    
                    # Convert distance to a comparable score (closer = higher score)
                    distance_factor = 1.0 - (status['distance'] / idle_threshold)
                    criticality_score += distance_factor * 5
                    
                    # If this is more critical than previous, select it
                    if (most_critical_direction is None or 
                        criticality_score > highest_consecutive_count or
                        (criticality_score == highest_consecutive_count and status['distance'] < lowest_distance)):
                        
                        most_critical_direction = direction
                        lowest_distance = status['distance']
                        highest_consecutive_count = criticality_score
            
            # If we found a critical direction, respond to it
            if most_critical_direction:
                self._begin_proactive_avoidance(
                    most_critical_direction, 
                    self.collision_status[most_critical_direction]['distance'],
                    self.collision_status[most_critical_direction]['consecutive_count']
                )
                # Also log the severity for better debugging
                self.get_logger().info(f"Proactive avoidance triggered by {most_critical_direction} " +
                    f"({self.collision_status[most_critical_direction]['severity']}) at " +
                    f"{self.collision_status[most_critical_direction]['distance']:.2f}cm")
    
    def _begin_proactive_avoidance(self, direction, distance, consecutive_count=0):
        """Start a proactive avoidance movement when idle and object detected"""
        # Avoid triggering too frequently
        current_time = time.time()
        
        # Don't start a new avoidance if we just did one
        if current_time - self.last_movement_time < 1.5:
            return
            
        self.idle_avoidance_active = True
        self.last_avoidance_direction = direction
        
        # Log the avoidance action
        self.get_logger().info(f"Starting proactive avoidance for {direction} obstacle at {distance:.1f}cm (consecutive: {consecutive_count})")
        
        # Calculate an avoidance movement based on the direction
        self._execute_avoidance_movement(direction, distance, consecutive_count)
    
    def _execute_avoidance_movement(self, direction, distance, consecutive_count=0):
        """Execute a specific avoidance movement based on obstacle direction and distance"""
        try:
            # Start with current position
            new_position = self.current_joints.copy()
            
            # Determine scale of movement based on proximity (closer = bigger movements)
            # Map distance from proactive_threshold to emergency_stop_distance into 0.1-1.0 range
            avoidance_scale = 1.0 - (distance - self.emergency_stop_distance) / (self.proactive_threshold - self.emergency_stop_distance)
            avoidance_scale = max(0.1, min(1.0, avoidance_scale))  # Clamp to 0.1-1.0
            
            # Enhance response for warnings - respond more seriously to warnings
            if consecutive_count > 0:
                # Scale up based on consecutive detections to make more decisive moves
                persistence_factor = min(3.0, 1.0 + (consecutive_count / 5.0))
                avoidance_scale *= persistence_factor
            
            # Handle very close objects with extra urgency
            if distance < self.hard_limit_distance * 1.5:  # If object is quite close
                avoidance_scale = min(1.5, avoidance_scale * 1.3)  # Increase avoidance intensity by 30%
                self.get_logger().warn(f"Enhanced avoidance for close object at {distance:.2f}cm")
            
            # Add playfulness - small random variations
            playful_factor = random.uniform(0.7, 1.0) if random.random() < self.avoidance_playfulness else 1.0
            
            # Check if we have any safe positions in memory to return to
            use_safe_memory = consecutive_count < 5 and self.safe_position_memory
            if use_safe_memory:
                # Pick a random safe position with preference for more recent ones
                index_weights = [i+1 for i in range(len(self.safe_position_memory))]
                chosen_index = random.choices(range(len(self.safe_position_memory)), 
                                             weights=index_weights, k=1)[0]
                safe_pos = self.safe_position_memory[chosen_index]
                
                # Modify the safe position slightly for playfulness
                new_position = [p + random.uniform(-0.05, 0.05) * self.avoidance_playfulness 
                               for p in safe_pos]
                
                self.get_logger().info(f"Moving to previously safe position with playful adjustments")
                self.move_to_safe_position(new_position)
                return
            
            # If no safe positions or persistent collision, calculate a decisive evasion
            if direction == 'front':
                # Front obstacles - pull back and maybe rotate slightly
                # More aggressive retreat for persistent collisions
                shoulder_adjustment = 0.2 * avoidance_scale * playful_factor * (1 + consecutive_count * 0.1)
                elbow_adjustment = 0.4 * avoidance_scale * playful_factor * (1 + consecutive_count * 0.1)
                
                # Pull back more aggressively for persistent collisions
                new_position[1] += shoulder_adjustment  # Increase shoulder angle (pull back)
                new_position[2] += elbow_adjustment     # Increase elbow angle (fold arm)
                
                # For persistent collisions, make more dramatic movements
                if consecutive_count > self.consecutive_collision_threshold:
                    # Try rotating away more decisively to break the cycle
                    rotation_dir = 1 if random.random() > 0.5 else -1  # Random direction
                    new_position[0] += rotation_dir * 0.4 * avoidance_scale
                    
                    # Pull back even more dramatically
                    new_position[1] += 0.3 * avoidance_scale
                    
                    self.get_logger().warn("Persistent front collision: executing dramatic evasion")
                else:
                    # Add a slight random rotation for more natural movement
                    new_position[0] += random.uniform(-0.25, 0.25) * self.avoidance_playfulness
                
            elif direction == 'left':
                # Left obstacles - rotate right decisively
                rotation = self.side_avoidance_magnitude * 1.2 * avoidance_scale * playful_factor
                
                # Increase rotation magnitude for persistent collisions
                if consecutive_count > self.consecutive_collision_threshold:
                    rotation *= 1.8
                    self.get_logger().warn("Persistent left collision: executing dramatic rotation")
                
                new_position[0] += rotation  # Rotate clockwise (to the right)
                
                # Pull back slightly too for more clearance
                if consecutive_count > 0 or random.random() < 0.7:  # More likely to pull back
                    new_position[1] += 0.15 * avoidance_scale
                    
            elif direction == 'right':
                # Right obstacles - rotate left decisively
                rotation = self.side_avoidance_magnitude * 1.2 * avoidance_scale * playful_factor
                
                # Increase rotation magnitude for persistent collisions
                if consecutive_count > self.consecutive_collision_threshold:
                    rotation *= 1.8
                    self.get_logger().warn("Persistent right collision: executing dramatic rotation")
                
                new_position[0] -= rotation  # Rotate counter-clockwise (to the left)
                
                # Pull back slightly too for more clearance
                if consecutive_count > 0 or random.random() < 0.7:  # More likely to pull back
                    new_position[1] += 0.15 * avoidance_scale
            
            # Move to the new position
            self.move_to_safe_position(new_position)
            
        except Exception as e:
            self.get_logger().error(f"Error in avoidance movement: {e}")
            self.idle_avoidance_active = False
    
    def _is_position_in_unsafe_zone(self, position):
        """Check if a position is in any of the recorded unsafe zones"""
        for unsafe_pos, radius in self.unsafe_zones:
            # Calculate Euclidean distance in joint space
            sum_squared = sum((p1 - p2) ** 2 for p1, p2 in zip(position, unsafe_pos))
            distance = math.sqrt(sum_squared)
            
            if distance < radius:
                return True
                
        return False
    
    def _at_position(self, position, tolerance=0.05):
        """Check if the arm is already at a specific position within tolerance"""
        if len(position) != len(self.current_joints):
            return False
            
        for i, (curr, target) in enumerate(zip(self.current_joints, position)):
            if abs(curr - target) > tolerance:
                return False
        return True
    
    def move_to_safe_position(self, position, description="Proactive avoidance movement", override_checks=False):
        """Move to a position with collision checking"""
        try:
            # Check if position is in any recorded unsafe zone (skip if overriding)
            if not override_checks and self._is_position_in_unsafe_zone(position):
                self.get_logger().warn("Avoiding known unsafe position - finding alternative")
                
                # Try to find a slightly different position
                for _ in range(5):  # Try a few variations
                    # Add random perturbations to avoid unsafe zone
                    perturbed_pos = [p + random.uniform(-0.3, 0.3) for p in position]
                    
                    # Check if this position is safe
                    if not self._is_position_in_unsafe_zone(perturbed_pos):
                        position = perturbed_pos
                        self.get_logger().info("Found safer alternative position")
                        break
            
            # Apply safety limits to the target position
            with self.collision_lock:
                safe_position = self.apply_safety_limits(position)
            
            # Update tracking variables
            self.target_joints = safe_position.copy()
            self.last_movement_time = time.time()
            
            # Send the command
            success = self.send_safe_joint_command(safe_position, description)
            
            # Short delay to let the movement start
            time.sleep(0.1)
            
            # Reset the avoidance flag regardless of success
            self.idle_avoidance_active = False
            
            return success
        except Exception as e:
            self.get_logger().error(f"Error in move_to_safe_position: {e}")
            self.idle_avoidance_active = False
            return False
    
    def _generate_rest_position(self):
        """Generate a rest position with some random variation"""
        # Start with the base rest position
        rest_position = self.base_rest_position.copy()
        
        # Add random variation to each joint
        for i in range(len(rest_position)):
            # Apply smaller variation to the hand/gripper (last position)
            variation_scale = 0.2 if i == 4 else 1.0
            variation = random.uniform(-self.rest_variation_range, self.rest_variation_range) * variation_scale
            rest_position[i] += variation
            
        self.last_rest_position = rest_position
        return rest_position
    
    def go_to_rest_position(self, description="Rest position"):
        """Move to a rest position with random variation"""
        if not self.enable_rest_position or not self.is_connected():
            return False
            
        try:
            self.is_returning_to_rest = True
            
            # Generate a rest position with variation
            rest_position = self._generate_rest_position()
            
            self.get_logger().info(f"Moving to rest position: {[round(p, 2) for p in rest_position]}")
            
            # Move to the rest position
            success = self.move_to_safe_position(
                rest_position, 
                description, 
                override_checks=True  # Override collision checks for rest position
            )
            
            # Reset the returning flag after motion is complete
            self.is_returning_to_rest = False
            
            return success
        except Exception as e:
            self.get_logger().error(f"Error moving to rest position: {e}")
            self.is_returning_to_rest = False
            return False
    
    def rest_position_callback(self):
        """Move the arm to the rest position after startup"""
        # Skip if already triggered (our custom one-shot implementation)
        if self.rest_position_timer_triggered:
            return

        # Mark as triggered so it only runs once
        self.rest_position_timer_triggered = True
        
        # Cancel the timer so it doesn't consume resources
        self.rest_position_timer.cancel()
            
        if not self.is_connected():
            self.get_logger().error("Cannot perform initial rest positioning: not connected")
            return
            
        if self.rest_position_done:
            return  # Prevent duplicate execution
            
        try:
            self.get_logger().info("Moving to initial rest position")
            
            # Use the go_to_rest_position method for consistency
            success = self.go_to_rest_position("Initial rest position")
            
            if success:
                self.get_logger().info("Successfully moved to initial rest position")
            else:
                self.get_logger().warn("Failed to move to initial rest position")
                
            # Mark as done regardless of outcome to prevent retry
            self.rest_position_done = True
            
        except Exception as e:
            self.get_logger().error(f"Error during initial rest positioning: {e}")
            self.rest_position_done = True  # Mark as done to prevent retry

    def is_animating(self):
        """Determine if the robot is currently executing an animation.
        This helps us decide whether to override with avoidance movements."""
        # Check if we've had any joint command in the last second that might be part of an animation
        time_since_last_command = time.time() - self.last_movement_time
        
        # If we've moved very recently, consider it an animation in progress
        if time_since_last_command < 0.5:
            return True
            
        # Also check if we're in the middle of a dramatic movement (high velocity)
        max_velocity = max([abs(v) for v in self.joint_velocities]) if hasattr(self, 'joint_velocities') and self.joint_velocities else 0
        if max_velocity > 0.5:  # Significant movement in progress
            return True
            
        # Check if recent movements form a pattern consistent with animation
        # This helps detect ongoing animations even if current velocity is low
        if hasattr(self, 'recent_command_times') and len(self.recent_command_times) >= 3:
            # Check for regular timing pattern in recent commands (animation typically has regular timing)
            intervals = [self.recent_command_times[i+1] - self.recent_command_times[i] 
                        for i in range(len(self.recent_command_times)-1)]
            if intervals and max(intervals) - min(intervals) < 0.2:  # Regular timing pattern
                return True
        
        return False

    def publish_current_joint_states(self):
        """Publish the current joint states periodically to ensure topic is active."""
        try:
            if hasattr(self, 'current_joints') and len(self.current_joints) > 0:
                self.get_logger().debug("Publishing current joint states to /joint_states")
                self.publish_actual_joint_states(self.current_joints)
                
                # Log less frequently to avoid console spam
                if int(time.time()) % 10 == 0:  # Log every 10 seconds
                    self.get_logger().info(f"Publishing to /joint_states: {[round(p, 2) for p in self.current_joints]}")
        except Exception as e:
            self.get_logger().error(f"Error in direct publish timer: {e}")

def main(args=None):
    rclpy.init(args=args)
    
    # Create and run the node
    hardware_interface = RoArmHardwareInterface()
    
    if hardware_interface.is_connected():
        rclpy.spin(hardware_interface)
    
    # Clean up is handled in destroy_node
    hardware_interface.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()