#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, String, Float32
import json
import threading
import math
import time
import numpy as np
import random
from luxo_behaviors.serial_manager import SerialManager

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
        self.declare_parameter('proactive_threshold', 15.0)  # cm
        self.declare_parameter('avoidance_playfulness', 0.3)  # 0.0-1.0 random factor
        self.declare_parameter('side_avoidance_magnitude', 0.5)  # Rotation magnitude for side avoidance
        self.declare_parameter('consecutive_collision_threshold', 3)  # How many repeated collisions trigger stronger response
        self.declare_parameter('escape_threshold', 10)  # How many consecutive collisions trigger escape mode
        self.declare_parameter('max_retreat_angle', 0.8)  # Maximum shoulder/elbow retreat angle
        self.declare_parameter('escape_mode_duration', 10.0)  # How long to avoid an area after escaping (seconds)
        self.declare_parameter('max_escape_attempts', 5)  # Maximum attempts before forced rest position
        
        # Add parameter for rest position
        self.declare_parameter('enable_rest_position', True)  # Enable/disable the rest position behavior
        self.declare_parameter('base_rest_position', [0.0, -2.0, 2.0, 1.0, 3.14])  # Base rest position
        self.declare_parameter('rest_variation_range', 0.15)  # Range for position variation        
        self.declare_parameter('use_hardware_joint_names', False)
        
        # Get parameters
        self.serial_port = self.get_parameter('serial_port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.enable_torque_on_start = self.get_parameter('enable_torque').value
        self.read_throttle = self.get_parameter('read_throttle').value
        self.enable_collision_avoidance = self.get_parameter('enable_collision_avoidance').value
        self.soft_limit_distance = self.get_parameter('soft_limit_distance').value
        self.hard_limit_distance = self.get_parameter('hard_limit_distance').value
        self.max_deceleration = self.get_parameter('max_deceleration').value
        self.collision_recovery_timeout = self.get_parameter('collision_recovery_timeout').value
        
        self.proactive_threshold = self.get_parameter('proactive_threshold').value
        self.avoidance_playfulness = self.get_parameter('avoidance_playfulness').value
        self.side_avoidance_magnitude = self.get_parameter('side_avoidance_magnitude').value
        self.consecutive_collision_threshold = self.get_parameter('consecutive_collision_threshold').value
        self.escape_threshold = self.get_parameter('escape_threshold').value
        self.max_retreat_angle = self.get_parameter('max_retreat_angle').value
        self.escape_mode_duration = self.get_parameter('escape_mode_duration').value
        self.max_escape_attempts = self.get_parameter('max_escape_attempts').value
        
        # Get parameters for rest position
        self.enable_rest_position = self.get_parameter('enable_rest_position').value
        self.base_rest_position = self.get_parameter('base_rest_position').value
        self.rest_variation_range = self.get_parameter('rest_variation_range').value
        
        self.use_hardware_joint_names = self.get_parameter('use_hardware_joint_names').value
        
        # Connection control
        self.connection_active = False
        self.connection_lock = threading.Lock()
        
        # Add timer health tracking variables
        self.safety_timer_active = False
        self.last_safety_timer_id = 0
        self.safety_timer_creation_time = 0
        self.safety_timer_call_count = 0
        self.safety_timer_last_exception = None
        self.safety_timer_lock = threading.Lock()
        
        # Rest position tracking
        self.last_rest_position = None  # Track the last used rest position
        
        # Tracking for adjustment actions
        self.adjustment_history = {
            'front': {'last_time': 0.0, 'last_position': None, 'adjustment_made': False},
            'left': {'last_time': 0.0, 'last_position': None, 'adjustment_made': False},
            'right': {'last_time': 0.0, 'last_position': None, 'adjustment_made': False}
        }
        self.adjustment_cooldown = 2.0  # Time to wait before making the same adjustment again
        self.adjustment_position_threshold = 0.1  # Difference threshold to consider a new position
        
        # Collision tracking
        self.collision_status = {
            'front': {'active': False, 'distance': float('inf'), 'severity': 'safe', 'consecutive_count': 0},
            'left': {'active': False, 'distance': float('inf'), 'severity': 'safe', 'consecutive_count': 0},
            'right': {'active': False, 'distance': float('inf'), 'severity': 'safe', 'consecutive_count': 0}
        }
        self.collision_lock = threading.Lock()
        self.last_collision_time = 0.0
        self.last_avoidance_direction = None  # Track which direction last triggered avoidance
        
        # Idle state tracking
        self.last_movement_time = time.time()
        self.last_proactive_check = 0.0
        self.home_position = [0.0, 0.3, 0.7, 0.4, 3.14]  # Default safe home (not used for rest)
        self.is_returning_to_rest = False  # Flag to track when we're returning to rest
        
        # Escape mode variables
        self.escape_mode_active = False
        self.escape_mode_start_time = 0.0
        self.unsafe_zones = []  # List of positions to avoid
        self.last_escape_direction = None  # Track last escape direction
        self.retreat_level = 0  # Tracks how far we've retreated
        self.escape_attempts = 0  # Count escape attempts
        
        # Joint state tracking
        self.current_joints = [0.0, 0.0, 0.0, 0.0, 3.14]  # base, shoulder, elbow, wrist, hand
        self.target_joints = [0.0, 0.0, 0.0, 0.0, 3.14]
        self.joint_velocities = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.last_command_time = self.get_clock().now()
        
        # Initialize the SerialManager
        self.serial_manager = SerialManager(
            self, 
            self.serial_port, 
            self.baud_rate, 
            self.read_throttle
        )
        
        # Connect to the serial port
        self.connection_active = self.serial_manager.connect()
        
        if self.connection_active:
            # Initialize the arm if torque is enabled
            if self.enable_torque_on_start:
                self.serial_manager.enable_torque()
                time.sleep(0.5)
                self.serial_manager.initialize_arm()
            
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
                
            # Add a direct publishing timer to ensure we're sending messages regularly
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
            
            # Initialize timer tracking variables first
            self.safety_timer_creation_time = self.get_clock().now().nanoseconds / 1e9
            self.safety_timer_active = True
            self.safety_timer_call_count = 0
            
            # Create the safety timer using our improved method
            self.recreate_safety_timer()
            self.last_safety_check_time = self.get_clock().now().nanoseconds / 1e9
            
            # Add a health check timer to ensure safety_timer is still running
            self.timer_health_check = self.create_timer(5.0, self.safety_timer_watchdog)
            
            self.get_logger().info("RoArm hardware interface initialized")
            
            if self.enable_collision_avoidance:
                self.get_logger().info("Collision avoidance enabled")
            else:
                self.get_logger().warn("Collision avoidance disabled - robot will not react to obstacles")
        else:
            self.get_logger().error("Failed to initialize hardware interface")
            
    def safety_timer_watchdog(self):
        """Check if the safety timer is still functioning properly"""
        try:
            current_time = self.get_clock().now().nanoseconds / 1e9
            
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
            timer_id = time.time_ns()
            
            with self.safety_timer_lock:
                self.safety_timer_active = True
                self.last_safety_timer_id = timer_id
                self.safety_timer_creation_time = self.get_clock().now().nanoseconds / 1e9
                self.safety_timer_call_count = 0
                
            # Create a new timer with a wrapper function that includes error handling
            self.safety_timer = self.create_timer(
                0.1,
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

    # Enhanced right_collision_callback with improved state management
    def right_collision_callback(self, msg):
        try:
            with self.collision_lock:
                was_active = self.collision_status['right']['active']
                current_time = time.time()
                
                # If we were active before and have made an adjustment recently
                # we should carefully manage the transition to avoid repeated warnings
                if was_active and not msg.data:
                    # Collision cleared - log and reset
                    self.get_logger().info("Right collision warning cleared")
                    self.collision_status['right']['active'] = False
                    self.collision_status['right']['consecutive_count'] = 0
                    # Reset adjustment tracking to allow new adjustments
                    self.adjustment_history['right']['adjustment_made'] = False
                    return
                    
                # If newly active, start fresh
                if not was_active and msg.data:
                    self.get_logger().info("Right collision warning activated")
                    self.collision_status['right']['active'] = True
                    self.collision_status['right']['consecutive_count'] = 1
                    return
                    
                # Update the active state
                self.collision_status['right']['active'] = msg.data
                
                if msg.data:  # If collision is still active
                    # Check if an adjustment was recently made before increasing count
                    adjustment_made = self.adjustment_history['right']['adjustment_made']
                    time_since_adjustment = current_time - self.adjustment_history['right']['last_time']
                    
                    # Only increment counter if:
                    # 1. No adjustment has been made yet, or
                    # 2. It's been more than the cooldown period since last adjustment
                    if not adjustment_made or time_since_adjustment > self.adjustment_cooldown:
                        # If this is a new collision or continuing collision, increment the counter
                        self.collision_status['right']['consecutive_count'] += 1
                        
                        # Log every few counts to avoid excessive logging
                        if self.collision_status['right']['consecutive_count'] % 5 == 0:
                            self.get_logger().warn(f"Persistent right collision! Count: {self.collision_status['right']['consecutive_count']}")
                        
                        # Check if we need to trigger escape mode
                        if self.collision_status['right']['consecutive_count'] > self.escape_threshold:
                            self.get_logger().warn(f"Persistent collision detected ({self.collision_status['right']['consecutive_count']}), attempting to escape")
                            if not self.escape_mode_active:
                                self._activate_escape_mode('right')
                            elif self.escape_attempts >= self.max_escape_attempts:
                                self.get_logger().warn("Multiple escape attempts failed, returning to rest position")
                                self.go_to_rest_position("Escape failure rest position")
                                self.escape_mode_active = False
                                self.escape_attempts = 0
                    else:
                        # If we're on cooldown and still detecting the collision,
                        # log at a lower level to avoid flooding
                        if self.collision_status['right']['consecutive_count'] > 3 and time_since_adjustment > (self.adjustment_cooldown / 2.0):
                            self.get_logger().debug(f"Right collision still active after adjustment, waiting {self.adjustment_cooldown - time_since_adjustment:.1f}s before responding again")
                            
                        # If adjustment was made and we're in cooldown period, prevent the count from growing too large
                        if self.collision_status['right']['consecutive_count'] > 5:
                            # Capping at 5 prevents rapid escalation to escape mode
                            self.collision_status['right']['consecutive_count'] = 5
                else:  # If collision is cleared but was previously active
                    if was_active:
                        self.get_logger().info("Right collision warning cleared")
                    self.collision_status['right']['consecutive_count'] = 0
                    # Reset adjustment tracking
                    self.adjustment_history['right']['adjustment_made'] = False
                    
        except Exception as e:
            self.get_logger().error(f"Error in right_collision_callback: {e}")
            # Ensure we don't leave the lock acquired if an exception occurs
            if self.collision_lock._is_owned():
                self.collision_lock.release()

    # Enhanced left_collision_callback with similar improved logic
    def left_collision_callback(self, msg):
        try:
            with self.collision_lock:
                was_active = self.collision_status['left']['active']
                current_time = time.time()
                
                # If we were active before and have made an adjustment recently
                # we should carefully manage the transition to avoid repeated warnings
                if was_active and not msg.data:
                    # Collision cleared - log and reset
                    self.get_logger().info("Left collision warning cleared")
                    self.collision_status['left']['active'] = False
                    self.collision_status['left']['consecutive_count'] = 0
                    # Reset adjustment tracking to allow new adjustments
                    self.adjustment_history['left']['adjustment_made'] = False
                    return
                    
                # If newly active, start fresh
                if not was_active and msg.data:
                    self.get_logger().info("Left collision warning activated")
                    self.collision_status['left']['active'] = True
                    self.collision_status['left']['consecutive_count'] = 1
                    return
                    
                # Update the active state
                self.collision_status['left']['active'] = msg.data
                
                if msg.data:  # If collision is still active
                    # Check if an adjustment was recently made before increasing count
                    adjustment_made = self.adjustment_history['left']['adjustment_made']
                    time_since_adjustment = current_time - self.adjustment_history['left']['last_time']
                    
                    # Only increment counter if:
                    # 1. No adjustment has been made yet, or
                    # 2. It's been more than the cooldown period since last adjustment
                    if not adjustment_made or time_since_adjustment > self.adjustment_cooldown:
                        # If this is a new collision or continuing collision, increment the counter
                        self.collision_status['left']['consecutive_count'] += 1
                        
                        # Log every few counts to avoid excessive logging
                        if self.collision_status['left']['consecutive_count'] % 5 == 0:
                            self.get_logger().warn(f"Persistent left collision! Count: {self.collision_status['left']['consecutive_count']}")
                        
                        # Check if we need to trigger escape mode
                        if self.collision_status['left']['consecutive_count'] > self.escape_threshold:
                            self.get_logger().warn(f"Persistent collision detected ({self.collision_status['left']['consecutive_count']}), attempting to escape")
                            if not self.escape_mode_active:
                                self._activate_escape_mode('left')
                            elif self.escape_attempts >= self.max_escape_attempts:
                                self.get_logger().warn("Multiple escape attempts failed, returning to rest position")
                                self.go_to_rest_position("Escape failure rest position")
                                self.escape_mode_active = False
                                self.escape_attempts = 0
                    else:
                        # If we're on cooldown and still detecting the collision,
                        # log at a lower level to avoid flooding
                        if self.collision_status['left']['consecutive_count'] > 3 and time_since_adjustment > (self.adjustment_cooldown / 2.0):
                            self.get_logger().debug(f"Left collision still active after adjustment, waiting {self.adjustment_cooldown - time_since_adjustment:.1f}s before responding again")
                            
                        # If adjustment was made and we're in cooldown period, prevent the count from growing too large
                        if self.collision_status['left']['consecutive_count'] > 5:
                            # Capping at 5 prevents rapid escalation to escape mode
                            self.collision_status['left']['consecutive_count'] = 5
                else:  # If collision is cleared but was previously active
                    if was_active:
                        self.get_logger().info("Left collision warning cleared")
                    self.collision_status['left']['consecutive_count'] = 0
                    # Reset adjustment tracking
                    self.adjustment_history['left']['adjustment_made'] = False
                    
        except Exception as e:
            self.get_logger().error(f"Error in left_collision_callback: {e}")
            # Ensure we don't leave the lock acquired if an exception occurs
            if self.collision_lock._is_owned():
                self.collision_lock.release()

    # Enhanced front_collision_callback with similar improved logic
    def front_collision_callback(self, msg):
        try:
            with self.collision_lock:
                was_active = self.collision_status['front']['active']
                current_time = time.time()
                
                # If we were active before and have made an adjustment recently
                # we should carefully manage the transition to avoid repeated warnings
                if was_active and not msg.data:
                    # Collision cleared - log and reset
                    self.get_logger().info("Front collision warning cleared")
                    self.collision_status['front']['active'] = False
                    self.collision_status['front']['consecutive_count'] = 0
                    # Reset adjustment tracking to allow new adjustments
                    self.adjustment_history['front']['adjustment_made'] = False
                    return
                    
                # If newly active, start fresh
                if not was_active and msg.data:
                    self.get_logger().info("Front collision warning activated")
                    self.collision_status['front']['active'] = True
                    self.collision_status['front']['consecutive_count'] = 1
                    return
                    
                # Update the active state
                self.collision_status['front']['active'] = msg.data
                
                if msg.data:  # If collision is still active
                    # Check if an adjustment was recently made before increasing count
                    adjustment_made = self.adjustment_history['front']['adjustment_made']
                    time_since_adjustment = current_time - self.adjustment_history['front']['last_time']
                    
                    # Only increment counter if:
                    # 1. No adjustment has been made yet, or
                    # 2. It's been more than the cooldown period since last adjustment
                    if not adjustment_made or time_since_adjustment > self.adjustment_cooldown:
                        # If this is a new collision or continuing collision, increment the counter
                        self.collision_status['front']['consecutive_count'] += 1
                        
                        # Log every few counts to avoid excessive logging
                        if self.collision_status['front']['consecutive_count'] % 5 == 0:
                            self.get_logger().warn(f"Persistent front collision! Count: {self.collision_status['front']['consecutive_count']}")
                        
                        # Check if we need to trigger escape mode
                        if self.collision_status['front']['consecutive_count'] > self.escape_threshold:
                            self.get_logger().warn(f"Persistent collision detected ({self.collision_status['front']['consecutive_count']}), attempting to escape")
                            if not self.escape_mode_active:
                                self._activate_escape_mode('front')
                            elif self.escape_attempts >= self.max_escape_attempts:
                                self.get_logger().warn("Multiple escape attempts failed, returning to rest position")
                                self.go_to_rest_position("Escape failure rest position")
                                self.escape_mode_active = False
                                self.escape_attempts = 0
                    else:
                        # If we're on cooldown and still detecting the collision,
                        # log at a lower level to avoid flooding
                        if self.collision_status['front']['consecutive_count'] > 3 and time_since_adjustment > (self.adjustment_cooldown / 2.0):
                            self.get_logger().debug(f"Front collision still active after adjustment, waiting {self.adjustment_cooldown - time_since_adjustment:.1f}s before responding again")
                            
                        # If adjustment was made and we're in cooldown period, prevent the count from growing too large
                        if self.collision_status['front']['consecutive_count'] > 5:
                            # Capping at 5 prevents rapid escalation to escape mode
                            self.collision_status['front']['consecutive_count'] = 5
                else:  # If collision is cleared but was previously active
                    if was_active:
                        self.get_logger().info("Front collision warning cleared")
                    self.collision_status['front']['consecutive_count'] = 0
                    # Reset adjustment tracking
                    self.adjustment_history['front']['adjustment_made'] = False
                    
        except Exception as e:
            self.get_logger().error(f"Error in front_collision_callback: {e}")
            # Ensure we don't leave the lock acquired if an exception occurs
            if self.collision_lock._is_owned():
                self.collision_lock.release()

    def _activate_escape_mode(self, direction):
        """Activate escape mode for persistent collisions"""
        # Check if we're currently in an animation - if so, we should be more careful
        in_animation = self.is_animating()
        
        self.escape_mode_active = True
        self.escape_mode_start_time = time.time()
        self.last_escape_direction = direction
        self.escape_attempts += 1
        
        # Record current position as unsafe
        unsafe_pos = self.current_joints.copy()
        self._add_unsafe_zone(unsafe_pos)
        
        self.get_logger().warn(f"ESCAPE MODE ACTIVATED: Persistent {direction} collision detected! (Attempt #{self.escape_attempts})")
        
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
                new_position[0] -= rotation_angle
                new_position[1] += 0.1
                
                self.get_logger().warn(f"Executing animation-safe right rotation escape")
                
            elif direction == 'right':
                # Smaller left rotation
                rotation_angle = 0.4
                new_position[0] += rotation_angle
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
                
                new_position[0] -= rotation_angle  # Strong clockwise rotation (right)
                new_position[1] += 0.2  # Some shoulder pullback for added clearance
                
                self.get_logger().warn(f"Executing DRAMATIC right rotation escape - level {self.retreat_level}")
                
            elif direction == 'right':
                # For right collisions, make a dramatic left turn
                rotation_angle = min(0.8 + (self.retreat_level * 0.15), 1.5)  # Increasing rotation
                
                new_position[0] += rotation_angle  # Strong counter-clockwise rotation (left)
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
    
    def perform_collision_avoidance(self, direction, distance, emergency=False):
        """Perform collision avoidance with more significant adjustments for emergency cases"""
        try:
            # Calculate current velocities first to understand motion
            self.estimate_joint_velocities()
            
            # Start with current position
            new_position = self.current_joints.copy()
            
            # Get the consecutive count for this direction
            consecutive_count = self.collision_status[direction]['consecutive_count']
            
            # Determine adjustment magnitude based on consecutive count
            # The more persistent the collision, the stronger the response
            if consecutive_count > 8:
                # Very persistent collision - make a dramatic move
                magnitude = 2.5  # Much stronger than normal emergency
                self.get_logger().warn(f"DRAMATIC avoidance for persistent {direction} collision (count: {consecutive_count})")
            elif consecutive_count > 5:
                # Persistent collision - stronger than emergency
                magnitude = 2.0
                self.get_logger().warn(f"Strong avoidance for persistent {direction} collision (count: {consecutive_count})")
            elif emergency:
                magnitude = 1.5
            else:
                magnitude = 0.8
            
            # Add some variation to avoid getting stuck in repeating patterns
            variation = random.uniform(0.9, 1.1)
            magnitude *= variation
            
            if direction == 'front':
                # Pull back shoulder and elbow
                new_position[1] += 0.3 * magnitude  # Shoulder back
                new_position[2] += 0.4 * magnitude  # Elbow fold
                
                # Add a random rotation to help escape
                # For persistent collisions, make rotation more decisive
                if consecutive_count > 5:
                    # Choose a consistent rotation direction rather than random
                    rotation = 0.5 * magnitude if consecutive_count % 2 == 0 else -0.5 * magnitude
                else:
                    rotation = random.uniform(-0.3, 0.3) * magnitude
                    
                new_position[0] += rotation
                
            elif direction == 'left':
                # Rotate to the right
                new_position[0] += 0.4 * magnitude
                new_position[1] += 0.1 * magnitude  # Slight shoulder back
                
            elif direction == 'right':
                # Rotate to the left
                new_position[0] -= 0.4 * magnitude
                new_position[1] += 0.1 * magnitude  # Slight shoulder back
            
            # Send command with high priority
            self.send_safe_joint_command(new_position, f"Collision avoidance (count: {consecutive_count})")
            
            # If emergency and avoidance doesn't work after multiple attempts,
            # schedule a return to rest position
            if emergency and consecutive_count > self.escape_threshold:
                self.get_logger().warn(f"Multiple path adjustments failed, will return to rest position")
                self.go_to_rest_position("Emergency rest return")
                
                # Reset collision counts after going to rest
                with self.collision_lock:
                    for direction in self.collision_status:
                        self.collision_status[direction]['consecutive_count'] = 0
            
            self.get_logger().warn(f"Collision avoidance COMPLETED for {direction} at {distance:.1f}cm")
            
            # Verify safety timer is still working after collision avoidance
            # This is crucial as collision avoidance seems to be where the timer dies
            current_time = self.get_clock().now().nanoseconds / 1e9
            
            with self.safety_timer_lock:
                timer_elapsed = current_time - self.safety_timer_creation_time
                timer_active = self.safety_timer_active
            
            # If timer is more than 0.5s old, verify it's still working by checking last call time
            if timer_elapsed > 0.5 and abs(current_time - self.last_safety_check_time) > 0.3:
                self.get_logger().warn("Safety timer may have become inactive during collision avoidance - recreating")
                self.recreate_safety_timer()
                
        except Exception as e:
            self.get_logger().error(f"Error in collision avoidance: {e}")
            
            # This is a critical function, so check if timer needs recreation after error
            self.get_logger().warn("Checking safety timer after collision avoidance error")
            current_time = self.get_clock().now().nanoseconds / 1e9
            if abs(current_time - self.last_safety_check_time) > 0.3:
                self.recreate_safety_timer()

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

    def safety_monitor_callback(self):
        """Periodic callback to monitor safety and adjust motion if needed"""
        # Update the last check time at the beginning to track timer operation
        self.last_safety_check_time = self.get_clock().now().nanoseconds / 1e9
        
        if not self.enable_collision_avoidance:
            self.get_logger().debug(f"Collision avoidance disabled - skipping safety check")
            return
            
        try:
            # Get current time for this check cycle
            current_time = time.time()
            
            # Get current collision status (do this early so we have latest data)
            with self.collision_lock:
                front_status = self.collision_status['front'].copy()
                left_status = self.collision_status['left'].copy()
                right_status = self.collision_status['right'].copy()
            
            # Add logging for persistent collisions - this helps track what's happening
            if (front_status['consecutive_count'] > 5 or 
                left_status['consecutive_count'] > 5 or 
                right_status['consecutive_count'] > 5):
                self.get_logger().warn(f"Persistent collision detected - counts: Front={front_status['consecutive_count']}, Left={left_status['consecutive_count']}, Right={right_status['consecutive_count']}")
                
                # Force avoidance action for persistent collisions regardless of throttling
                # This is important - even if we recently did an avoidance, we need to try again
                if front_status['consecutive_count'] > 5 and front_status['severity'] == 'danger':
                    self.get_logger().warn(f"Forcing avoidance for persistent front collision")
                    self.perform_collision_avoidance('front', front_status['distance'], emergency=True)
                elif left_status['consecutive_count'] > 5 and left_status['severity'] == 'danger':
                    self.get_logger().warn(f"Forcing avoidance for persistent left collision")
                    self.perform_collision_avoidance('left', left_status['distance'], emergency=True)
                elif right_status['consecutive_count'] > 5 and right_status['severity'] == 'danger':
                    self.get_logger().warn(f"Forcing avoidance for persistent right collision")
                    self.perform_collision_avoidance('right', right_status['distance'], emergency=True)

            # Check if escape mode is active and should be updated or deactivated
            if self.escape_mode_active:
                # Check if escape mode has been active too long
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
                            # Still in collision - try another escape move
                            self.escape_attempts += 1
                            
                            if self.escape_attempts >= self.max_escape_attempts:
                                # Too many failed attempts, return to rest
                                self.get_logger().warn(f"Escape attempts exceeded ({self.escape_attempts}/{self.max_escape_attempts}), returning to rest")
                                self.go_to_rest_position("Escape failure rest position")
                                self.escape_mode_active = False
                                self.escape_attempts = 0
                            else:
                                # Try another escape attempt
                                if self.is_animating():
                                    # Use gentler escape for animations
                                    self._execute_animation_safe_escape(self.last_escape_direction)
                                else:
                                    self._execute_escape_maneuver(self.last_escape_direction)
                
            # Check if we should trigger regular avoidance for active collisions
            if front_status['active'] or left_status['active'] or right_status['active']:
                self.get_logger().info(f"Attempting path adjustment for active collisions: Front={front_status['active']}, Left={left_status['active']}, Right={right_status['active']}")
                # Calculate a safe adjustment vector based on collision directions
                self.adjust_path_for_collision(front_status, left_status, right_status)
        
        except Exception as e:
            self.get_logger().error(f"Error in safety monitor: {e}")
            
            # Record the exception for watchdog tracking
            with self.safety_timer_lock:
                self.safety_timer_last_exception = str(e)
                
            # Add stack trace for better debugging
            import traceback
            self.get_logger().error(f"Stack trace: {traceback.format_exc()}")
            
            # This error could potentially make the timer stop working
            # Let's check if we need to restart it
            current_time = self.get_clock().now().nanoseconds / 1e9
            creation_time = self.safety_timer_creation_time
            if current_time - creation_time > 1.0:  # If timer is older than 1 second
                self.get_logger().warn("Safety timer exception might have corrupted timer - recreating")
                self.recreate_safety_timer()
        
        finally:
            # Always log completion to help track when callbacks are running
            self.get_logger().debug(f"Completed safety_monitor_callback")
    
    def adjust_path_for_collision(self, front_status, left_status, right_status):
        """Adjust the current motion path to avoid obstacles"""
        # Get current time for cooldown checks
        current_time = time.time()
        
        # Calculate adjustment factors based on distance and severity
        front_factor = self.calculate_adjustment_factor(front_status)
        left_factor = self.calculate_adjustment_factor(left_status)
        right_factor = self.calculate_adjustment_factor(right_status)
        
        # If no significant adjustments needed, return early
        if front_factor < 0.1 and left_factor < 0.1 and right_factor < 0.1:
            return
            
        # Create an adjustment for the current target joints
        adjusted_targets = self.target_joints.copy()
        
        # Handle left and right collisions independently with their own adjustments
        base_adjustment = 0.0
        left_adjustment_msg = ""
        right_adjustment_msg = ""
        
        # Check for cooldown period on right adjustments
        right_cooldown_active = (
            current_time - self.adjustment_history['right']['last_time'] < self.adjustment_cooldown and
            self.adjustment_history['right']['adjustment_made']
        )
        
        # Handle right collision - rotate RIGHT (positive adjustment)
        if right_factor > 0.1 and not right_cooldown_active:
            # Calculate multiplier for repeat collisions to make adjustment stronger over time
            right_multiplier = 1.0
            if right_status['consecutive_count'] > 0:
                # This grows with consecutive detections - more persistent = stronger response
                right_multiplier = min(3.0, 1.0 + right_status['consecutive_count'] * 0.1)
            
            # Calculate rotation amount - positive for right collisions (rotate right)
            right_adjustment = right_factor * 0.4 * right_multiplier
            base_adjustment += right_adjustment
            
            right_adjustment_msg = f"right(rotate right: {right_adjustment:.2f})"
            self.get_logger().info(f"Right collision adjusting base: {right_adjustment:.2f} (factor: {right_factor:.2f}, count: {right_status['consecutive_count']})")
            
            # Mark that we've made an adjustment for right collision
            self.adjustment_history['right']['last_time'] = current_time
            self.adjustment_history['right']['last_position'] = self.current_joints.copy()
            self.adjustment_history['right']['adjustment_made'] = True
        elif right_factor > 0.1 and right_cooldown_active:
            self.get_logger().info(f"Skipping right adjustment - on cooldown ({current_time - self.adjustment_history['right']['last_time']:.1f}s)")
            
            # If we've been in cooldown for a while and still have collisions, reset
            if current_time - self.adjustment_history['right']['last_time'] > (self.adjustment_cooldown * 0.75):
                # Artificially decrease the consecutive count to prevent escalation
                with self.collision_lock:
                    # Don't reset completely, but prevent unlimited growth
                    if self.collision_status['right']['consecutive_count'] > 3:
                        self.collision_status['right']['consecutive_count'] = 3
                        self.get_logger().info("Adjusting right collision count to prevent escalation")
        
        # Check for cooldown period on left adjustments
        left_cooldown_active = (
            current_time - self.adjustment_history['left']['last_time'] < self.adjustment_cooldown and
            self.adjustment_history['left']['adjustment_made']
        )
        
        # Handle left collision - rotate RIGHT (positive adjustment)
        if left_factor > 0.1 and not left_cooldown_active:
            # Calculate multiplier for repeat collisions to make adjustment stronger over time
            left_multiplier = 1.0
            if left_status['consecutive_count'] > 0:
                # This grows with consecutive detections - more persistent = stronger response
                left_multiplier = min(3.0, 1.0 + left_status['consecutive_count'] * 0.1)
            
            # Calculate rotation amount - negative for left collisions (rotate left)
            left_adjustment = -left_factor * 0.4 * left_multiplier
            base_adjustment += left_adjustment
            
            left_adjustment_msg = f"left(rotate left: {left_adjustment:.2f})"
            self.get_logger().info(f"Left collision adjusting base: {left_adjustment:.2f} (factor: {left_factor:.2f}, count: {left_status['consecutive_count']})")
            
            # Mark that we've made an adjustment for left collision
            self.adjustment_history['left']['last_time'] = current_time
            self.adjustment_history['left']['last_position'] = self.current_joints.copy()
            self.adjustment_history['left']['adjustment_made'] = True
        elif left_factor > 0.1 and left_cooldown_active:
            self.get_logger().info(f"Skipping left adjustment - on cooldown ({current_time - self.adjustment_history['left']['last_time']:.1f}s)")
            
            # If we've been in cooldown for a while and still have collisions, reset
            if current_time - self.adjustment_history['left']['last_time'] > (self.adjustment_cooldown * 0.75):
                # Artificially decrease the consecutive count to prevent escalation
                with self.collision_lock:
                    # Don't reset completely, but prevent unlimited growth
                    if self.collision_status['left']['consecutive_count'] > 3:
                        self.collision_status['left']['consecutive_count'] = 3
                        self.get_logger().info("Adjusting left collision count to prevent escalation")
        
        # Apply base adjustment
        if abs(base_adjustment) > 0.01:  # Only adjust if non-zero
            adjusted_targets[0] += base_adjustment
        
        # Check for cooldown period on front adjustments
        front_cooldown_active = (
            current_time - self.adjustment_history['front']['last_time'] < self.adjustment_cooldown and
            self.adjustment_history['front']['adjustment_made']
        )
        
        # Front obstacles primarily affect the arm extension
        front_adjustment_msg = ""
        if front_factor > 0.1 and not front_cooldown_active:
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
            
            front_adjustment_msg = f"front(retreat: {shoulder_adjustment:.2f})"
            
            # Mark that we've made an adjustment for front collision
            self.adjustment_history['front']['last_time'] = current_time
            self.adjustment_history['front']['last_position'] = self.current_joints.copy()
            self.adjustment_history['front']['adjustment_made'] = True
        elif front_factor > 0.1 and front_cooldown_active:
            self.get_logger().info(f"Skipping front adjustment - on cooldown ({current_time - self.adjustment_history['front']['last_time']:.1f}s)")
            
            # If we've been in cooldown for a while and still have collisions, reset
            if current_time - self.adjustment_history['front']['last_time'] > (self.adjustment_cooldown * 0.75):
                # Artificially decrease the consecutive count to prevent escalation
                with self.collision_lock:
                    # Don't reset completely, but prevent unlimited growth
                    if self.collision_status['front']['consecutive_count'] > 3:
                        self.collision_status['front']['consecutive_count'] = 3
                        self.get_logger().info("Adjusting front collision count to prevent escalation")
        
        # Better logging that includes all adjustments
        adjustment_msgs = []
        if front_adjustment_msg: adjustment_msgs.append(front_adjustment_msg)
        if left_adjustment_msg: adjustment_msgs.append(left_adjustment_msg)
        if right_adjustment_msg: adjustment_msgs.append(right_adjustment_msg)
        
        # If no adjustments to make (due to cooldowns), return early
        if not adjustment_msgs:
            return
        
        self.get_logger().debug(f"Dynamic collision avoidance: {', '.join(adjustment_msgs)}")
        
        # Check if we're already close to the adjusted position
        # to avoid sending redundant commands that don't change position
        if self._at_position(adjusted_targets, 0.1):
            self.get_logger().info("Already at adjusted position - skipping adjustment")
            
            # If we've been at this position for a while and still have collisions,
            # we need a more dramatic response
            if not hasattr(self, 'last_failed_adjustment_time'):
                self.last_failed_adjustment_time = current_time
            
            # If we've been stuck for more than 2 seconds, try escape mode
            if current_time - self.last_failed_adjustment_time > 2.0:
                # Find the most persistent collision
                if right_status['consecutive_count'] > max(front_status['consecutive_count'], left_status['consecutive_count']):
                    direction = 'right'
                elif left_status['consecutive_count'] > front_status['consecutive_count']:
                    direction = 'left'
                else:
                    direction = 'front'
                    
                self.get_logger().warn(f"Adjustments ineffective - activating escape mode for {direction}")
                self._activate_escape_mode(direction)
                self.last_failed_adjustment_time = current_time
            
            return
            
        # Reset the failed adjustment timer since we're sending a new command
        self.last_failed_adjustment_time = current_time
        
        # Send the adjusted target positions to the arm
        self.send_safe_joint_command(adjusted_targets, "Collision avoidance adjustment")
        self.get_logger().debug(f"ADJUSTMENT SENT: {[round(p, 2) for p in adjusted_targets]}")
        # Update last movement time when we make an adjustment
        self.last_movement_time = time.time()

    def calculate_adjustment_factor(self, status):
        """Calculate adjustment factor (0.0-1.0) based on collision status"""
        # Always return a strong value for danger severity regardless of distance
        if status['severity'] == 'danger':
            return 1.0
        
        # For other cases, check activity and distance
        if status['active'] or status['severity'] == 'warning':
            if status['distance'] <= self.hard_limit_distance:
                # Hard limit - strong adjustment
                return 1.0
            elif status['distance'] <= self.soft_limit_distance:
                # Soft limit - graduated adjustment
                # Linear interpolation between 0.0 and 1.0
                range_fraction = (self.soft_limit_distance - status['distance']) / \
                                (self.soft_limit_distance - self.hard_limit_distance)
                # Ensure a minimum adjustment factor for active collisions
                return max(0.1, min(1.0, range_fraction))
        
        return 0.0
    
    def joint_states_callback(self, msg):
        """Handle joint states and send to hardware with collision avoidance."""
        if not self.is_connected():
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

            # Publish the message
            self.joint_states_publisher.publish(msg)
            
        except Exception as e:
            self.get_logger().error(f"Error publishing actual joint states: {e}")
            # Add stack trace for better debugging
            import traceback
            self.get_logger().error(traceback.format_exc())
    
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

        # Check for right collisions (primarily affects base rotation)
        if self.collision_status['right']['active']:
            severity = self.collision_status['right']['severity']
            distance = self.collision_status['right']['distance']
            
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
            'roll': 'roll',
            'hand': 'hand',
            # Add alternative mappings from your system if needed
            'base_to_L1': 'base',
            'L1_to_L2': 'shoulder',
            'L2_to_L3': 'elbow',
            'L3_to_L4': 'wrist',
            'L4_to_L5': 'roll'
        }
    
    def destroy_node(self):
        """Clean up when node is destroyed."""
        self.get_logger().info("Shutting down hardware interface")
        
        # Disable torque before closing
        if self.is_connected():
            self.disable_torque()
        
        # Close the serial connection
        if hasattr(self, 'serial_manager'):
            self.serial_manager.close()
            
        super().destroy_node()
    
    def _different_enough(self, pos1, pos2, threshold=0.2):
        """Check if two positions are different enough to be considered distinct"""
        # Calculate Euclidean distance in joint space
        sum_squared = sum((p1 - p2) ** 2 for p1, p2 in zip(pos1, pos2))
        return math.sqrt(sum_squared) > threshold
 
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
            
            return success
        except Exception as e:
            self.get_logger().error(f"Error in move_to_safe_position: {e}")
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
            
            # Move to the rest position - override unsafe zones in this case
            success = self.move_to_safe_position(
                rest_position, 
                description, 
                override_checks=True  # Override collision checks for rest position
            )
            
            # Reset collision counters and escape status when we return to rest
            if success:
                self.escape_mode_active = False
                self.escape_attempts = 0
                with self.collision_lock:
                    for direction in self.collision_status:
                        self.collision_status[direction]['consecutive_count'] = 0
            
            # Reset the returning flag after motion is complete
            self.is_returning_to_rest = False
            
            return success
        except Exception as e:
            self.get_logger().error(f"Error moving to rest position: {e}")
            self.is_returning_to_rest = False
            return False

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
                # Always publish the joint states (important for ROS control)
                self.publish_actual_joint_states(self.current_joints)
        except Exception as e:
            self.get_logger().error(f"Error in direct publish timer: {e}")

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