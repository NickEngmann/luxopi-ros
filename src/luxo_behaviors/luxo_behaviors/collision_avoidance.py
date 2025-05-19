#!/usr/bin/env python3

import random
import time
import math
import threading
from sensor_msgs.msg import JointState
from std_msgs.msg import String

class CollisionAvoidance:
    """Class to handle collision avoidance logic for the RoArm hardware interface."""
    
    def __init__(self, node, send_safe_joint_command_callback, publish_actual_joint_states_callback):
        """
        Initialize the CollisionAvoidance system.
        
        Args:
            node: The ROS node that owns this system (for logging and parameters)
            send_safe_joint_command_callback: Callback to send commands to hardware
            publish_actual_joint_states_callback: Callback to publish joint states
        """
        self.node = node
        self.send_safe_joint_command = send_safe_joint_command_callback
        self.publish_actual_joint_states = publish_actual_joint_states_callback
        
        # Load parameters from the node
        self.enable_collision_avoidance = node.get_parameter('enable_collision_avoidance').value
        self.soft_limit_distance = node.get_parameter('soft_limit_distance').value
        self.hard_limit_distance = node.get_parameter('hard_limit_distance').value
        self.max_deceleration = node.get_parameter('max_deceleration').value
        self.collision_recovery_timeout = node.get_parameter('collision_recovery_timeout').value
        self.avoidance_playfulness = node.get_parameter('avoidance_playfulness').value
        self.side_avoidance_magnitude = node.get_parameter('side_avoidance_magnitude').value
        self.consecutive_collision_threshold = node.get_parameter('consecutive_collision_threshold').value
        self.escape_threshold = node.get_parameter('escape_threshold').value
        self.max_retreat_angle = node.get_parameter('max_retreat_angle').value
        self.escape_mode_duration = node.get_parameter('escape_mode_duration').value
        self.max_escape_attempts = node.get_parameter('max_escape_attempts').value
        
        # Rest position parameters
        self.enable_rest_position = node.get_parameter('enable_rest_position').value
        self.base_rest_position = node.get_parameter('base_rest_position').value
        self.rest_variation_range = node.get_parameter('rest_variation_range').value
        
        # Collision tracking
        self.collision_status = {
            'front': {'active': False, 'distance': float('inf'), 'severity': 'safe', 'consecutive_count': 0},
            'left': {'active': False, 'distance': float('inf'), 'severity': 'safe', 'consecutive_count': 0},
            'right': {'active': False, 'distance': float('inf'), 'severity': 'safe', 'consecutive_count': 0}
        }
        self.collision_lock = threading.Lock()
        self.last_collision_time = 0.0
        self.last_avoidance_direction = None  # Track which direction last triggered avoidance
        
        # Adjustment tracking
        self.adjustment_history = {
            'front': {'last_time': 0.0, 'last_position': None, 'adjustment_made': False},
            'left': {'last_time': 0.0, 'last_position': None, 'adjustment_made': False},
            'right': {'last_time': 0.0, 'last_position': None, 'adjustment_made': False}
        }
        self.adjustment_cooldown = 1.0 
        self.adjustment_position_threshold = 0.1  # Difference threshold to consider a new position
        
        # Escape mode variables
        self.escape_mode_active = False
        self.escape_mode_start_time = 0.0
        self.unsafe_zones = []  # List of positions to avoid
        self.last_escape_direction = None  # Track last escape direction
        self.retreat_level = 0  # Tracks how far we've retreated
        self.escape_attempts = 0  # Count escape attempts
        
        # Target override tracking
        self.target_override_active = False  # Flag to indicate override is active
        self.target_override_time = 0.0  # When the override was activated
        self.target_override_joints = None  # The safe position we've moved to
        self.target_override_reason = ""  # Why the override exists
        self.target_override_timeout = 10.0  # Time before reconsidering original target
        self.last_original_target_change_time = 0.0  # Last time original target changed
        
        # Rest position tracking
        self.last_rest_position = None  # Track the last used rest position
        self.is_returning_to_rest = False  # Flag to track when we're returning to rest
        
        # External shared state
        self.current_joints = [0.0, 0.0, 0.0, 0.0, 0.0]  # Current joint positions
        self.target_joints = [0.0, 0.0, 0.0, 0.0, 0.0]   # Target joint positions
        self.joint_velocities = [0.0, 0.0, 0.0, 0.0, 0.0] # Current joint velocities
        
        # Additional tracking variables
        self.last_failed_adjustment_time = time.time()
        self.last_proactive_check = 0.0
        
        # Two-stage home position sequence
        self.home_position_1 = [0.5, 0.5, 1.3, 1.4, 0.0]  # Initial home position
        self.home_position_2 = [0.5, -0.85, 1.3, 1.4, 0.0]  # Final home position
        self.home_position_tolerance = 0.2  # Tolerance to determine if we're at a position (increased from 0.15 for faster transitions)
        self.home_position_stage = 1  # Track which stage of the home sequence we're in
        self.home_position_stage_change_time = 0.0  # When we switched home position stages
        self.home_position_stage_timeout = 2  # Time to wait at home_position_1 before moving to home_position_2
        
        # Animation state tracking
        self.last_movement_time = time.time()
        self.recent_command_times = []
        
        # Add tracking for persistent front (head) collision
        self.persistent_head_collision_start = 0.0
        self.persistent_head_collision_active = False
        self.persistent_head_collision_last_log = 0.0  # For log throttling
        
        # Add tracking for idle time
        self.last_activity_time = time.time()
        self.idle_timeout = 4.0  # seconds - used for both idle detection and home position timeout
        self.idle_check_active = True  # Flag to enable/disable idle detection
        self.idle_check_last_log = 0.0  # For log throttling
        
        # Add flags for special operations
        self.returning_to_home = False
        self.returning_to_home_start_time = 0.0  # When we started returning to home
    
    def update_current_joints(self, joints):
        """Update the current joint positions."""
        self.current_joints = joints.copy()
    
    def update_target_joints(self, joints):
        """Update the target joint positions."""
        # Check if position has changed enough to update activity time
        current_time = time.time()
        significant_change = False
        
        # Check if any joint has changed by more than 0.2 radians
        if hasattr(self, 'target_joints') and len(self.target_joints) == len(joints):
            for i, (old_pos, new_pos) in enumerate(zip(self.target_joints, joints)):
                if abs(old_pos - new_pos) > 0.2:
                    significant_change = True
                    break
        else:
            # First update or array size mismatch, consider it significant
            significant_change = True
        
        # Update the target joints regardless
        self.target_joints = joints.copy()
        
        # Only update activity time if significant change or first update
        if significant_change:
            self.last_activity_time = current_time
            self.node.get_logger().debug(f"Activity timestamp updated due to significant joint position change")
            
        # Check if this is a new target that's different from our original target
        if not self._at_position(joints, self.target_joints, 0.05):
            self.last_original_target_change_time = current_time
            
            # Clear target override if the desired target has changed
            if self.target_override_active:
                self.node.get_logger().info(f"New target received - clearing safety override")
                self.target_override_active = False
                self.target_override_joints = None
    
    def update_joint_velocities(self, velocities):
        """Update the current joint velocities."""
        self.joint_velocities = velocities.copy()
    
    def handle_collision(self, direction, is_active):
        """Unified collision handling for all directions."""
        try:
            with self.collision_lock:
                # If we're returning to home, still track collisions but don't react
                # This ensures we keep tracking persistent head collisions
                was_active = self.collision_status[direction]['active']
                current_time = time.time()
                
                # Track persistent head collision even when returning home
                if direction == 'front':
                    if is_active and self.collision_status[direction]['severity'] == 'danger':
                        # Start timing persistent head collision if not already tracking
                        if not self.persistent_head_collision_active:
                            self.persistent_head_collision_start = current_time
                            self.persistent_head_collision_active = True
                            self.node.get_logger().info("Started tracking persistent head collision")
                        # Throttle logs for persistent collisions
                        elif current_time - self.persistent_head_collision_last_log > 2.0:
                            duration = current_time - self.persistent_head_collision_start
                            self.node.get_logger().info(f"Persistent head collision ongoing for {duration:.1f}s")
                            self.persistent_head_collision_last_log = current_time
                    else:
                        # Reset persistent head collision tracking
                        if self.persistent_head_collision_active:
                            self.node.get_logger().info("Persistent head collision cleared")
                            self.persistent_head_collision_active = False
                
                # If we're already returning to home, just track state but don't react to collisions
                # This prevents collision reactions from interrupting the return to home
                if self.returning_to_home:
                    self.collision_status[direction]['active'] = is_active
                    return
                
                # Fast path: No change in status - return quickly to reduce processing overhead
                if was_active == is_active and not (is_active and self.collision_status[direction]['consecutive_count'] > 3):
                    # Only skip if not a persistent collision requiring attention
                    return
                
                # If newly active, start fresh
                if not was_active and is_active:
                    self.node.get_logger().info(f"{direction.capitalize()} collision warning activated")
                    self.collision_status[direction]['active'] = True
                    self.collision_status[direction]['consecutive_count'] = 1
                    
                    # Fast reaction for immediate danger
                    if self.collision_status[direction]['severity'] == 'danger':
                        # Release lock before calling perform_collision_avoidance to prevent deadlock
                        self.collision_lock.release()
                        try:
                            # Immediate action for danger - don't wait for safety timer
                            self.perform_collision_avoidance(direction, self.collision_status[direction]['distance'], emergency=True)
                        finally:
                            # Re-acquire lock for remaining processing
                            self.collision_lock.acquire()
                    return
                    
                # If collision was cleared - log and reset
                if was_active and not is_active:
                    self.node.get_logger().info(f"{direction.capitalize()} collision warning cleared")
                    self.collision_status[direction]['active'] = False
                    self.collision_status[direction]['consecutive_count'] = 0
                    # Reset adjustment tracking to allow new adjustments
                    self.adjustment_history[direction]['adjustment_made'] = False
                    return
                    
                # Update the active state
                self.collision_status[direction]['active'] = is_active
                
                if is_active:  # If collision is still active
                    # Check if an adjustment was recently made before increasing count
                    adjustment_made = self.adjustment_history[direction]['adjustment_made']
                    time_since_adjustment = current_time - self.adjustment_history[direction]['last_time']
                    
                    # Only increment counter if:
                    # 1. No adjustment has been made yet, or
                    # 2. It's been more than the cooldown period since last adjustment
                    if not adjustment_made or time_since_adjustment > self.adjustment_cooldown:
                        # If this is a new collision or continuing collision, increment the counter
                        self.collision_status[direction]['consecutive_count'] += 1
                        
                        # Log every few counts to avoid excessive logging
                        if self.collision_status[direction]['consecutive_count'] % 5 == 0:
                            self.node.get_logger().warn(f"Persistent {direction} collision! Count: {self.collision_status[direction]['consecutive_count']}")
                        
                        # Check if we need to trigger escape mode
                        if self.collision_status[direction]['consecutive_count'] > self.escape_threshold:
                            self.node.get_logger().warn(f"Persistent collision detected ({self.collision_status[direction]['consecutive_count']}), attempting to escape")
                            if not self.escape_mode_active:
                                # Release lock before calling _activate_escape_mode to prevent deadlock
                                self.collision_lock.release()
                                try:
                                    self._activate_escape_mode(direction)
                                finally:
                                    # Re-acquire lock for remaining processing
                                    self.collision_lock.acquire()
                            elif self.escape_attempts >= self.max_escape_attempts:
                                self.node.get_logger().warn("Multiple escape attempts failed, returning to rest position")
                                # Release lock before calling go_to_rest_position to prevent deadlock
                                self.collision_lock.release()
                                try:
                                    self.go_to_rest_position("Escape failure rest position")
                                finally:
                                    # Re-acquire lock for remaining processing
                                    self.collision_lock.acquire()
                                self.escape_mode_active = False
                                self.escape_attempts = 0
                    else:
                        # If we're on cooldown and still detecting the collision,
                        # log at a lower level to avoid flooding
                        if self.collision_status[direction]['consecutive_count'] > 3 and time_since_adjustment > (self.adjustment_cooldown / 2.0):
                            self.node.get_logger().debug(f"{direction.capitalize()} collision still active after adjustment, waiting {self.adjustment_cooldown - time_since_adjustment:.1f}s before responding again")
                            
                        # If adjustment was made and we're in cooldown period, prevent the count from growing too large
                        if self.collision_status[direction]['consecutive_count'] > 5:
                            # Capping at 5 prevents rapid escalation to escape mode
                            self.collision_status[direction]['consecutive_count'] = 5
                else:  # If collision is cleared but was previously active
                    if was_active:
                        self.node.get_logger().info(f"{direction.capitalize()} collision warning cleared")
                    self.collision_status[direction]['consecutive_count'] = 0
                    # Reset adjustment tracking
                    self.adjustment_history[direction]['adjustment_made'] = False
                    
        except Exception as e:
            self.node.get_logger().error(f"Error in {direction}_collision_callback: {e}")
            # Ensure we don't leave the lock acquired if an exception occurs
            if self.collision_lock._is_owned():
                self.collision_lock.release()
    
    def update_distance(self, direction, value, is_proximity=False):
        """Update distance information with fast reaction for dangerous values."""
        with self.collision_lock:
            # Special handling for proximity sensor
            if is_proximity:
                # Convert proximity to approximate distance in cm (higher value = closer object)
                proximity = max(1, min(255, value))
                distance = max(1.0, 30.0 * (1.0 - proximity / 255.0))
            else:
                distance = value
                
            # Store the distance
            old_distance = self.collision_status[direction]['distance']
            self.collision_status[direction]['distance'] = distance
            
            # Fast reaction path: If distance is critically low and we haven't reacted recently
            current_time = time.time()
            
            # Enhanced trigger conditions: react when distance DECREASES below threshold
            # This ensures we react when approaching, not when moving away
            distance_getting_smaller = old_distance == float('inf') or distance < old_distance
            if (distance <= self.hard_limit_distance and 
                distance_getting_smaller and
                (current_time - self.last_collision_time) > 0.25 and  # Prevent rapid reactions
                not self.adjustment_history[direction]['adjustment_made']):
                
                self.last_collision_time = current_time
                self.collision_status[direction]['active'] = True
                
                # Release lock before potentially long operation
                self.collision_lock.release()
                try:
                    # Immediate emergency avoidance without waiting for timer
                    self.node.get_logger().warn(f"EMERGENCY: {direction} distance {distance:.2f}cm below hard limit")
                    # Force reaction by setting active and triggering emergency avoidance
                    self.perform_collision_avoidance(direction, distance, emergency=True)
                finally:
                    # Re-acquire lock after operation
                    self.collision_lock.acquire()
    
    def update_severity(self, direction, severity):
        """Update severity information with immediate reaction for danger."""
        with self.collision_lock:
            old_severity = self.collision_status[direction]['severity']
            self.collision_status[direction]['severity'] = severity
            
            # Update persistent head collision tracking for front direction
            if direction == 'front':
                current_time = time.time()
                if severity == 'danger':
                    if not self.persistent_head_collision_active:
                        self.persistent_head_collision_start = current_time
                        self.persistent_head_collision_active = True
                        self.persistent_head_collision_last_log = current_time
                        self.node.get_logger().info("Started tracking persistent head collision due to danger severity")
                else:
                    # Reset persistent head collision tracking if previously active
                    if self.persistent_head_collision_active:
                        self.node.get_logger().info("Persistent head collision cleared (severity changed)")
                        self.persistent_head_collision_active = False
            
            # Fast reaction path: If severity changed to danger, react immediately
            if severity == 'danger' and old_severity != 'danger':
                current_time = time.time()
                if (current_time - self.last_collision_time) > 0.25:  # Prevent too rapid reactions
                    # Update for tracking
                    self.last_collision_time = current_time
                    self.collision_status[direction]['active'] = True
                    
                    # Release lock before potentially long operation
                    self.collision_lock.release()
                    try:
                        self.node.get_logger().warn(f"EMERGENCY: {direction} severity changed to 'danger'")
                        # Immediate emergency avoidance without waiting for timer
                        self.perform_collision_avoidance(direction, self.collision_status[direction]['distance'], emergency=True)
                    finally:
                        # Re-acquire lock after operation
                        self.collision_lock.acquire()
    
    def safety_monitor_callback(self):
        """Periodic callback to monitor safety and adjust motion if needed."""
        if not self.enable_collision_avoidance:
            self.node.get_logger().debug(f"Collision avoidance disabled - skipping safety check")
            return
            
        try:
            # Get current time for this check cycle
            current_time = time.time()
            
            # Check if we're currently trying to go home and handle timeouts
            if self.returning_to_home:
                time_since_home_attempt = current_time - self.returning_to_home_start_time
                if time_since_home_attempt > self.idle_timeout:
                    self.node.get_logger().warn(f"Home position return timeout after {time_since_home_attempt:.1f}s - giving up")
                    self.returning_to_home = False
                    # Reset other state variables for clean slate
                    self.persistent_head_collision_active = False
                    self.target_override_active = False
                return  # Skip other checks when returning to home
            
            # Check persistent head collision duration
            if self.persistent_head_collision_active:
                head_collision_duration = current_time - self.persistent_head_collision_start
                # Log the duration periodically
                if current_time - self.persistent_head_collision_last_log > 1.0:
                    self.node.get_logger().info(f"Persistent head collision duration: {head_collision_duration:.1f}s")
                    self.persistent_head_collision_last_log = current_time
                
                if head_collision_duration > 1.25:
                    self.node.get_logger().warn(f"Persistent head collision for {head_collision_duration:.1f}s - resetting to home position")
                    # Force go to home by setting flag and calling method
                    self.returning_to_home = True
                    self.returning_to_home_start_time = current_time
                    self.go_to_home_position("Persistent head collision reset")
                    return  # Skip remaining checks as we're already taking action
            
            # Check idle timeout (only if we're not already handling a collision)
            if self.idle_check_active and not any(status['active'] for status in self.collision_status.values()):
                time_since_activity = current_time - self.last_activity_time
                
                # Check if we're already at or very close to home positions
                already_at_home2 = self._at_position(self.current_joints, self.home_position_2, self.home_position_tolerance)
                already_at_home1 = self._at_position(self.current_joints, self.home_position_1, self.home_position_tolerance * 1.2)
                
                # Use different timeout values based on position
                if already_at_home1 or already_at_home2:
                    # If already near a home position, use shorter timeout
                    effective_timeout = self.home_position_stage_timeout
                    position_status = "near home position"
                else:
                    # Regular timeout for positions away from home
                    effective_timeout = self.idle_timeout
                    position_status = "away from home position"
                
                # Log the idle time periodically to help debugging
                if time_since_activity > 1.5 and current_time - self.idle_check_last_log > 2.0:
                    self.node.get_logger().debug(f"Device idle for {time_since_activity:.1f}s (timeout: {effective_timeout}s, {position_status})")
                    self.idle_check_last_log = current_time
                
                if time_since_activity > effective_timeout and not already_at_home2:
                    self.node.get_logger().info(f"Device idle for {time_since_activity:.1f}s ({position_status}) - returning to home position")
                    # Force go to home by setting flag and calling method
                    self.returning_to_home = True
                    self.returning_to_home_start_time = current_time
                    self.go_to_home_position("Idle timeout reset")
                    return  # Skip remaining checks as we're already taking action
                elif time_since_activity > effective_timeout and already_at_home2:
                    # We're already at home, so just reset the activity timer to prevent continuous triggering
                    self.node.get_logger().debug("Device idle, but already at final home position - resetting activity timer")
                    self.last_activity_time = current_time
            
            # Fast path: Check if there are any active collisions or we're in escape mode
            with self.collision_lock:
                any_collision_active = any(status['active'] for status in self.collision_status.values())
                any_persistent_collision = any(status['consecutive_count'] > 5 for status in self.collision_status.values())
                escape_mode_active = self.escape_mode_active
                
                # If nothing needs attention, return early to reduce overhead
                if not any_collision_active and not any_persistent_collision and not escape_mode_active:
                    return
                
                # Get current collision status (do this early so we have latest data)
                front_status = self.collision_status['front'].copy()
                left_status = self.collision_status['left'].copy()
                right_status = self.collision_status['right'].copy()
            
            # Add logging for persistent collisions - this helps track what's happening
            if any_persistent_collision:
                self.node.get_logger().warn(f"Persistent collision detected - counts: Front={front_status['consecutive_count']}, Left={left_status['consecutive_count']}, Right={right_status['consecutive_count']}")
                
                # Force avoidance action for persistent collisions regardless of throttling
                # This is important - even if we recently did an avoidance, we need to try again
                if front_status['consecutive_count'] > 5 and front_status['severity'] == 'danger':
                    self.node.get_logger().warn(f"Forcing avoidance for persistent front collision")
                    self.perform_collision_avoidance('front', front_status['distance'], emergency=True)
                elif left_status['consecutive_count'] > 5 and left_status['severity'] == 'danger':
                    self.node.get_logger().warn(f"Forcing avoidance for persistent left collision")
                    self.perform_collision_avoidance('left', left_status['distance'], emergency=True)
                elif right_status['consecutive_count'] > 5 and right_status['severity'] == 'danger':
                    self.node.get_logger().warn(f"Forcing avoidance for persistent right collision")
                    self.perform_collision_avoidance('right', right_status['distance'], emergency=True)

            # Check if escape mode is active and should be updated or deactivated
            if escape_mode_active:
                # Check if escape mode has been active too long
                if current_time - self.escape_mode_start_time > self.escape_mode_duration:
                    self.escape_mode_active = False
                    self.node.get_logger().info("Escape mode deactivated - normal operation resuming")
                    
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
                                self.node.get_logger().warn(f"Escape attempts exceeded ({self.escape_attempts}/{self.max_escape_attempts}), returning to rest")
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
                self.node.get_logger().info(f"Attempting path adjustment for active collisions: Front={front_status['active']}, Left={left_status['active']}, Right={right_status['active']}")
                # Calculate a safe adjustment vector based on collision directions
                self.adjust_path_for_collision(front_status, left_status, right_status)
        
        except Exception as e:
            self.node.get_logger().error(f"Error in safety monitor: {e}")
            
            # Add stack trace for better debugging
            import traceback
            self.node.get_logger().error(f"Stack trace: {traceback.format_exc()}")
    
    def perform_collision_avoidance(self, direction, distance, emergency=False):
        """Perform collision avoidance with more significant adjustments for emergency cases."""
        # Update activity time when performing collision avoidance
        current_time = time.time()
        self.last_activity_time = current_time
        self.node.get_logger().debug(f"Activity timestamp updated due to collision avoidance action")
        
        # Report collision movement source for DEMA coordination
        if hasattr(self.node, 'enable_movement_source_integration') and self.node.enable_movement_source_integration:
            try:
                movement_source_msg = String()
                movement_source_msg.data = "collision"
                if hasattr(self.node, 'movement_source_publisher'):
                    self.node.movement_source_publisher.publish(movement_source_msg)
                    self.node.get_logger().debug("Published collision movement source for DEMA")
            except Exception as e:
                self.node.get_logger().error(f"Error publishing collision movement source: {e}")
        
        try:
            # Start with current position
            new_position = self.current_joints.copy()
            
            # Get the consecutive count for this direction
            consecutive_count = self.collision_status[direction]['consecutive_count']
            
            # Determine adjustment magnitude based on consecutive count
            # The more persistent the collision, the stronger the response
            if consecutive_count > 8:
                # Very persistent collision - make a dramatic move
                magnitude = 2.5  # Much stronger than normal emergency
                self.node.get_logger().warn(f"DRAMATIC avoidance for persistent {direction} collision (count: {consecutive_count})")
            elif consecutive_count > 5:
                # Persistent collision - stronger than emergency
                magnitude = 2.0
                self.node.get_logger().warn(f"Strong avoidance for persistent {direction} collision (count: {consecutive_count})")
            elif emergency:
                magnitude = 1.5
            else:
                magnitude = 0.8
            
            # Add some variation to avoid getting stuck in repeating patterns
            variation = random.uniform(0.9, 1.1)
            magnitude *= variation
            
            if direction == 'front':
                # Pull back shoulder and elbow
                new_position[1] -= 0.6 * magnitude  # Shoulder back
                new_position[2] += 0.4 * magnitude  # Elbow fold
                
                # Add a random rotation to help escape
                # For persistent collisions, make rotation more decisive
                if consecutive_count > 5:
                    # Choose a consistent rotation direction rather than random
                    rotation = 0.5 * magnitude if consecutive_count % 2 == 0 else -0.5 * magnitude
                else:
                    rotation = random.uniform(-0.7, 0.7) * magnitude
                    
                new_position[0] += rotation
                
            elif direction == 'left':
                # REVERSED: Rotate to the LEFT (negative adjustment)
                new_position[0] -= 0.4 * magnitude
                new_position[1] += 0.1 * magnitude  # Slight shoulder back
                
            elif direction == 'right':
                # REVERSED: Rotate to the RIGHT (positive adjustment)
                new_position[0] += 0.4 * magnitude
                new_position[1] += 0.1 * magnitude  # Slight shoulder back
            
            # Send command with high priority
            self.send_safe_joint_command(new_position, f"Collision avoidance (count: {consecutive_count})")
            
            # Set this as our target override position
            self.target_override_active = True
            self.target_override_time = time.time()
            self.target_override_joints = new_position.copy()
            self.target_override_reason = f"Collision avoidance for {direction} at {distance:.1f}cm"
            self.node.get_logger().info(f"Created target override: {self.target_override_reason}")
            
            # If emergency and avoidance doesn't work after multiple attempts,
            # schedule a return to rest position
            if emergency and consecutive_count > self.escape_threshold:
                self.node.get_logger().warn(f"Multiple path adjustments failed, will return to rest position")
                self.go_to_rest_position("Emergency rest return")
                
                # Reset collision counts after going to rest
                with self.collision_lock:
                    for direction in self.collision_status:
                        self.collision_status[direction]['consecutive_count'] = 0
            
            self.node.get_logger().warn(f"Collision avoidance COMPLETED for {direction} at {distance:.1f}cm")
            
        except Exception as e:
            self.node.get_logger().error(f"Error in collision avoidance: {e}")
    
    def _at_position(self, position1, position2=None, tolerance=0.05):
        """Check if two positions are the same within tolerance."""
        if position2 is None:
            position2 = self.current_joints
        
        # Calculate differences between positions
        differences = [abs(pos1 - pos2) for pos1, pos2 in zip(position1, position2)]
        
        # Add debugging to help diagnose position comparison issues
        if hasattr(self, 'returning_to_home') and self.returning_to_home:
            # Explicitly identify which position is target and which is current
            target_pos = position1  # First parameter should be the target position
            current_pos = position2  # Second parameter should be the current position
            
            # For debugging stage transitions, clearly label which positions we're comparing
            if self.home_position_stage == 1:
                stage_target = "home_position_1"
                compare_target = self.home_position_1
            else:
                stage_target = "home_position_2"
                compare_target = self.home_position_2
                
            self.node.get_logger().info(f"Position comparison: differences={[round(d, 4) for d in differences]}, tolerance={tolerance}")
            self.node.get_logger().info(f"Target ({stage_target})={[round(p, 4) for p in target_pos]}, Current={[round(p, 4) for p in current_pos]}")
            
            # If any difference is too large for the current stage, handle it
            if max(differences) > 0.4 and self.home_position_stage == 2:
                self.node.get_logger().warn(f"Significant difference detected - resetting home position stage to 1")
                self.home_position_stage = 1
                return False
            
            # Add additional validation - verify we're actually comparing against the correct target
            correct_target_diffs = [abs(c - t) for c, t in zip(current_pos, compare_target)]
            if stage_target == "home_position_1" and max(correct_target_diffs) > self.home_position_tolerance * 1.5:
                self.node.get_logger().warn(f"Robot not close to {stage_target}: actual diffs={[round(d, 4) for d in correct_target_diffs]}")
                return False
            elif stage_target == "home_position_2" and max(correct_target_diffs) > self.home_position_tolerance * 1.5:
                self.node.get_logger().warn(f"Robot not close to {stage_target}: actual diffs={[round(d, 4) for d in correct_target_diffs]}")
                return False
                
            # If we're in stage 1 and the robot thinks it's at position 1, double-check with actual data
            if self.home_position_stage == 1 and max(differences) <= tolerance:
                hp1_diffs = [abs(c - t) for c, t in zip(current_pos, self.home_position_1)]
                if max(hp1_diffs) > self.home_position_tolerance:
                    self.node.get_logger().warn(f"False positive detection of home_position_1: actual diffs={[round(d, 4) for d in hp1_diffs]}")
                    return False
                else:
                    self.node.get_logger().info(f"DETECTED: Robot has reached home_position_1 within tolerance {self.home_position_tolerance}")
            
            # Same validation for stage 2
            if self.home_position_stage == 2 and max(differences) <= tolerance:
                hp2_diffs = [abs(c - t) for c, t in zip(current_pos, self.home_position_2)]
                if max(hp2_diffs) > self.home_position_tolerance:
                    self.node.get_logger().warn(f"False positive detection of home_position_2: actual diffs={[round(d, 4) for d in hp2_diffs]}")
                    return False
                else:
                    self.node.get_logger().info(f"DETECTED: Robot has reached home_position_2 within tolerance {self.home_position_tolerance}")
        
        # The actual position comparison
        for i, (pos1, pos2) in enumerate(zip(position1, position2)):
            if abs(pos1 - pos2) > tolerance:
                return False
        return True
    
    def get_effective_target_position(self, original_target):
        """Determine which target position to use based on overrides and safety."""
        current_time = time.time()
        
        # When returning to home, always return the home position override
        if self.returning_to_home and self.target_override_active and self.target_override_joints is not None:
            # Log that we're enforcing home position override (throttled)
            if not hasattr(self, 'last_home_override_log') or current_time - self.last_home_override_log > 1.0:
                self.node.get_logger().info(f"Enforcing home position override (stage {self.home_position_stage})")
                self.last_home_override_log = current_time
            
            # If we're in stage 2, check if any difference is too large and revert to stage 1 if needed
            if self.home_position_stage == 2:
                # Calculate differences between current position and target home_position_2
                differences = [abs(curr - target) for curr, target in zip(self.current_joints, self.home_position_2)]
                
                # Check if any difference exceeds 2x the tolerance
                double_tolerance = self.home_position_tolerance * 2.0
                large_differences = [i for i, diff in enumerate(differences) if diff > double_tolerance]
                
                if large_differences:
                    # At least one joint position is too far from home_position_2
                    indices_str = ", ".join([str(i) for i in large_differences])
                    self.node.get_logger().warn(f"Joint(s) at indices {indices_str} exceed 2x tolerance ({double_tolerance:.2f}) - reverting to stage 1")
                    
                    # Revert to stage 1
                    self.home_position_stage = 1
                    
                    # Add slight random variation to home_position_1
                    noise_range = 0.05
                    home_with_variation = [
                        pos + random.uniform(-noise_range, noise_range) 
                        for pos in self.home_position_1
                    ]
                    
                    # Update the target override with home_position_1
                    self.target_override_joints = home_with_variation
                    self.target_override_time = current_time
                    self.target_override_reason = "Reverting to home position stage 1"
                    
                    # Send command to move to home_position_1
                    self.send_safe_joint_command(home_with_variation, "Reverting to home position stage 1")
                    
                    # Log the current differences for debugging
                    self.node.get_logger().info(f"Current differences from home_position_2: {[round(d, 4) for d in differences]}")
                elif self._at_position(self.current_joints, self.home_position_2, self.home_position_tolerance):
                    # We've successfully reached the final home position
                    self.node.get_logger().debug("Successfully reached final home position (stage 2)")
                    # Clear returning to home flag once we've fully reached home
                    self.returning_to_home = False
                
            # Check if we're in the first stage of the home sequence
            elif self.home_position_stage == 1:
                # Check if we've reached home_position_1 (within tolerance)
                if self._at_position(self.current_joints, self.home_position_1, self.home_position_tolerance):
                    # Check if we've been at position 1 long enough before moving to position 2
                    current_time = time.time()
                    
                    # Initialize the stage change time if it's not set yet
                    if self.home_position_stage_change_time == 0.0:
                        self.home_position_stage_change_time = current_time
                        self.node.get_logger().info(f"Started timing home position stage 1 - will wait {self.home_position_stage_timeout}s")
                    
                    time_at_position_1 = current_time - self.home_position_stage_change_time
                    
                    # Check if we've waited long enough at position 1
                    if time_at_position_1 >= self.home_position_stage_timeout:
                        self.node.get_logger().info(f"Reached home_position_1 and waited {time_at_position_1:.1f}s - transitioning to home_position_2")
                        
                        # Switch to stage 2
                        self.home_position_stage = 2
                        self.home_position_stage_change_time = current_time
                        
                        # Add slight random variation to home_position_2
                        noise_range = 0.05
                        home_with_variation = [
                            pos + random.uniform(-noise_range, noise_range) 
                            for pos in self.home_position_2
                        ]
                        
                        # Update the target override with home_position_2
                        self.target_override_joints = home_with_variation
                        self.target_override_time = current_time
                        self.target_override_reason = "Home position sequence stage 2"
                        
                        # Send command to move to home_position_2
                        self.send_safe_joint_command(home_with_variation, "Home position stage 2")
                    elif current_time - self.idle_check_last_log > 1.0:
                        # Periodically log the waiting progress
                        self.node.get_logger().debug(f"At home_position_1, waiting {self.home_position_stage_timeout - time_at_position_1:.1f}s before transitioning to stage 2")
                        self.idle_check_last_log = current_time
                else:
                    # Reset stage change time if we're not at position 1
                    if self.home_position_stage_change_time != 0.0:
                        self.node.get_logger().debug("Lost home_position_1 - resetting stage timer")
                        self.home_position_stage_change_time = 0.0
            
            # Always return the override position when in home movement sequence
            return self.target_override_joints
        
        # Regular override handling
        if not self.target_override_active or self.target_override_joints is None:
            return original_target
        
        # Check if original target has changed significantly
        if self._at_position(original_target, self.target_joints, 0.05) == False:
            self.node.get_logger().info("Original target changed - clearing override")
            self.target_override_active = False
            return original_target
            
        # Check if collision has been clear for a while
        any_collision_active = any(self.collision_status[direction]['active'] for direction in self.collision_status)
        override_duration = current_time - self.target_override_time
        
        if not any_collision_active and override_duration > self.target_override_timeout:
            self.node.get_logger().warn(f"Collisions clear for {override_duration:.1f}s - gradually returning to original target")
            
            # Gradually blend between override and original target
            blend_factor = min(1.0, (override_duration - self.target_override_timeout) / 2.0)
            blended_target = [
                self.target_override_joints[i] * (1.0 - blend_factor) + original_target[i] * blend_factor
                for i in range(len(original_target))
            ]
            
            # If we're very close to original target, clear the override completely
            if blend_factor > 0.9:
                self.node.get_logger().warn("Override expired - returning to original target")
                self.target_override_active = False
                return original_target
                
            return blended_target
            
        # If override is still active and needed, use it
        return self.target_override_joints
    
    def apply_safety_limits(self, positions):
        """Apply safety limits to joint positions based on collision status."""
        # If returning to home position, don't apply collision-based safety limits
        if self.returning_to_home:
            return positions
            
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
    
    def adjust_path_for_collision(self, front_status, left_status, right_status):
        """Adjust the current motion path to avoid obstacles."""
        # Skip if we're returning to home - don't adjust the home positioning
        if self.returning_to_home:
            return
            
        # Update activity time when adjusting path
        current_time = time.time()
        self.last_activity_time = current_time
        self.node.get_logger().debug(f"Activity timestamp updated due to collision path adjustment")
        
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
        
        # REVERSED: Handle right collision - rotate RIGHT (positive adjustment)
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
            self.node.get_logger().info(f"Right collision adjusting base: {right_adjustment:.2f} (factor: {right_factor:.2f}, count: {right_status['consecutive_count']})")
            
            # Mark that we've made an adjustment for right collision
            self.adjustment_history['right']['last_time'] = current_time
            self.adjustment_history['right']['last_position'] = self.current_joints.copy()
            self.adjustment_history['right']['adjustment_made'] = True
            
            # Force immediate action for right collisions by directly sending a command
            if right_status['distance'] <= self.hard_limit_distance:
                temp_position = self.current_joints.copy()
                temp_position[0] += right_adjustment  # Apply immediate adjustment
                self.send_safe_joint_command(temp_position, "Immediate right collision response")
                
        elif right_factor > 0.1 and right_cooldown_active:
            self.node.get_logger().info(f"Skipping right adjustment - on cooldown ({current_time - self.adjustment_history['right']['last_time']:.1f}s)")
            
            # If we've been in cooldown for a while and still have collisions, reset
            if current_time - self.adjustment_history['right']['last_time'] > (self.adjustment_cooldown * 0.75):
                # Artificially decrease the consecutive count to prevent escalation
                with self.collision_lock:
                    # Don't reset completely, but prevent unlimited growth
                    if self.collision_status['right']['consecutive_count'] > 3:
                        self.collision_status['right']['consecutive_count'] = 3
                        self.node.get_logger().info("Adjusting right collision count to prevent escalation")
        
        # Check for cooldown period on left adjustments
        left_cooldown_active = (
            current_time - self.adjustment_history['left']['last_time'] < self.adjustment_cooldown and
            self.adjustment_history['left']['adjustment_made']
        )
        
        # REVERSED: Handle left collision - rotate LEFT (negative adjustment)
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
            self.node.get_logger().info(f"Left collision adjusting base: {left_adjustment:.2f} (factor: {left_factor:.2f}, count: {left_status['consecutive_count']})")
            
            # Mark that we've made an adjustment for left collision
            self.adjustment_history['left']['last_time'] = current_time
            self.adjustment_history['left']['last_position'] = self.current_joints.copy()
            self.adjustment_history['left']['adjustment_made'] = True
            
            # Force immediate action for left collisions by directly sending a command
            if left_status['distance'] <= self.hard_limit_distance:
                temp_position = self.current_joints.copy()
                temp_position[0] += left_adjustment  # Apply immediate adjustment
                self.send_safe_joint_command(temp_position, "Immediate left collision response")
                
        elif left_factor > 0.1 and left_cooldown_active:
            self.node.get_logger().info(f"Skipping left adjustment - on cooldown ({current_time - self.adjustment_history['left']['last_time']:.1f}s)")
            
            # If we've been in cooldown for a while and still have collisions, reset
            if current_time - self.adjustment_history['left']['last_time'] > (self.adjustment_cooldown * 0.75):
                # Artificially decrease the consecutive count to prevent escalation
                with self.collision_lock:
                    # Don't reset completely, but prevent unlimited growth
                    if self.collision_status['left']['consecutive_count'] > 3:
                        self.collision_status['left']['consecutive_count'] = 3
                        self.node.get_logger().info("Adjusting left collision count to prevent escalation")
        
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
            elbow_adjustment = front_factor * 0.3 * persistence_multiplier
            adjusted_targets[1] -= shoulder_adjustment
            adjusted_targets[2] -= elbow_adjustment
            
            # Adjust wrist to maintain end effector orientation
            adjusted_targets[3] -= (shoulder_adjustment + elbow_adjustment) * 0
            
            front_adjustment_msg = f"front(retreat: {shoulder_adjustment:.2f})"
            
            # Mark that we've made an adjustment for front collision
            self.adjustment_history['front']['last_time'] = current_time
            self.adjustment_history['front']['last_position'] = self.current_joints.copy()
            self.adjustment_history['front']['adjustment_made'] = True
        elif front_factor > 0.1 and front_cooldown_active:
            self.node.get_logger().info(f"Skipping front adjustment - on cooldown ({current_time - self.adjustment_history['front']['last_time']:.1f}s)")
            
            # If we've been in cooldown for a while and still have collisions, reset
            if current_time - self.adjustment_history['front']['last_time'] > (self.adjustment_cooldown * 0.75):
                # Artificially decrease the consecutive count to prevent escalation
                with self.collision_lock:
                    # Don't reset completely, but prevent unlimited growth
                    if self.collision_status['front']['consecutive_count'] > 3:
                        self.collision_status['front']['consecutive_count'] = 3
                        self.node.get_logger().info("Adjusting front collision count to prevent escalation")
        
        # Better logging that includes all adjustments
        adjustment_msgs = []
        if front_adjustment_msg: adjustment_msgs.append(front_adjustment_msg)
        if left_adjustment_msg: adjustment_msgs.append(left_adjustment_msg)
        if right_adjustment_msg: adjustment_msgs.append(right_adjustment_msg)
        
        # If no adjustments to make (due to cooldowns), return early
        if not adjustment_msgs:
            return
        
        self.node.get_logger().debug(f"Dynamic collision avoidance: {', '.join(adjustment_msgs)}")
        
        # Check if we're already close to the adjusted position
        # to avoid sending redundant commands that don't change position
        if self._at_position(adjusted_targets, self.current_joints, 0.1):
            self.node.get_logger().info("Already at adjusted position - skipping adjustment")
            
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
                    
                self.node.get_logger().warn(f"Adjustments ineffective - activating escape mode for {direction}")
                self._activate_escape_mode(direction)
                self.last_failed_adjustment_time = current_time
            
            return
            
        # Reset the failed adjustment timer since we're sending a new command
        self.last_failed_adjustment_time = current_time
        
        # Send the adjusted target positions to the arm
        self.send_safe_joint_command(adjusted_targets, "Collision avoidance adjustment")
        
        # Set this as our target override position
        self.target_override_active = True
        self.target_override_time = time.time()
        self.target_override_joints = adjusted_targets.copy()
        
        # Create a descriptive reason for the override
        reasons = []
        if front_adjustment_msg: reasons.append(front_adjustment_msg)
        if left_adjustment_msg: reasons.append(left_adjustment_msg)
        if right_adjustment_msg: reasons.append(right_adjustment_msg)
        self.target_override_reason = f"Path adjustment: {', '.join(reasons)}"
        self.node.get_logger().info(f"Created target override: {self.target_override_reason}")
        
        self.node.get_logger().debug(f"ADJUSTMENT SENT: {[round(p, 2) for p in adjusted_targets]}")
        # Update last movement time when we make an adjustment
        self.last_movement_time = time.time()
    
    def calculate_adjustment_factor(self, status):
        """Calculate adjustment factor (0.0-1.0) based on collision status."""
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
    
    def _generate_rest_position(self):
        """Generate a rest position with some random variation."""
        # Start with the base rest position
        rest_position = self.base_rest_position.copy()
        
        # Add random variation to each joint
        for i in range(len(rest_position)):
            # Apply smaller variation to the hand/gripper (last position)
            variation_scale = float(0.0) if i == 4 else float(0.0)
            variation = random.uniform(-self.rest_variation_range, self.rest_variation_range) * variation_scale
            rest_position[i] += variation
            
        self.last_rest_position = rest_position
        return rest_position
    
    def go_to_rest_position(self, description="Rest position"):
        """Move to a rest position with random variation."""
        if not self.enable_rest_position:
            return False
            
        try:
            self.is_returning_to_rest = True
            
            # Generate a rest position with variation
            rest_position = self._generate_rest_position()
            
            self.node.get_logger().info(f"Moving to rest position: {[round(p, 2) for p in rest_position]}")
            
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
            self.node.get_logger().error(f"Error moving to rest position: {e}")
            self.is_returning_to_rest = False
            return False
    
    def go_to_home_position(self, description="Home position reset"):
        """Move to home position using a two-stage sequence.
        
        First moves to home_position_1, and once it's within tolerance of that position,
        transitions to home_position_2. If already close to home_position_2, skips
        directly to that position.

        Preserves the current base rotation (joint 0) regardless of what's in the home positions.
        """
        try:
            # Publish a "collision" movement source to disable DEMA during home movement
            self._publish_movement_source("collision")
            
            # Force disable any other modes that might interfere
            self.escape_mode_active = False
            self.target_override_active = False  # Clear any previous override
            
            current_time = time.time()
            current_base_position = self.current_joints[0]
            
            # Create modified home positions that preserve the current base rotation
            mod_home_position_1 = self.home_position_1.copy()
            mod_home_position_1[0] = current_base_position
            
            mod_home_position_2 = self.home_position_2.copy()
            mod_home_position_2[0] = current_base_position
            
            # IMPROVED: Check if we're already at or near home_position_2 - use a more relaxed tolerance
            # Skip checking joint 0 (base) when determining if we're at home
            hp2_diffs = [abs(curr - target) if i > 0 else 0.0 
            for i, (curr, target) in enumerate(zip(self.current_joints, mod_home_position_2))]
            already_at_home2 = max(hp2_diffs) <= 0.2
            
            if already_at_home2:
                self.home_position_stage = 2
                self.node.get_logger().debug(f"Already at final home position (diffs: {[round(d, 2) for d in hp2_diffs]})")
                # return True
            else:
                # Also check if we're close to home_position_1, ignoring base position
                hp1_diffs = [abs(curr - target) if i > 0 else 0.0 
                for i, (curr, target) in enumerate(zip(self.current_joints, mod_home_position_1))]
                already_at_home1 = max(hp1_diffs) <= self.home_position_tolerance
                
                if already_at_home1:
                    self.home_position_stage = 2  # Start at stage 1 but we'll quickly transition to stage 2
                    self.node.get_logger().info(f"Already at initial home position (diffs: {[round(d, 2) for d in hp1_diffs]}) - starting at stage 1")
                else:
                    self.home_position_stage = 1
                    self.node.get_logger().info(f"Starting home position sequence at stage 1")
            
            # Add slight random variation to home position
            noise_range = 0.05
            if self.home_position_stage == 1:
                home_with_variation = [
                current_base_position if i == 0 else pos + random.uniform(-noise_range, noise_range) 
                    for i, pos in enumerate(mod_home_position_1)
                ]
            else:
                home_with_variation = [
                current_base_position if i == 0 else                     pos + random.uniform(-noise_range, noise_range) 
                    for i, pos in enumerate(mod_home_position_2)
                ]
            
            self.node.get_logger().debug(f"Moving to home position stage {self.home_position_stage} with variation: {[round(p, 2) for p in home_with_variation]}")
            
            # Create a high-priority override to enforce this target
            self.target_override_active = True
            self.target_override_time = current_time
            self.target_override_joints = home_with_variation
            self.target_override_reason = description
            self.target_override_timeout = 10.0  # Keep this override active for at least 10 seconds
            
            # Reset the last activity time to prevent immediate idle detection after going home
            self.last_activity_time = current_time
            
            # Move to the home position - override unsafe zones in this case
            success = self.send_safe_joint_command(
                home_with_variation, 
                description 
            )
            
            # Reset collision counters and escape status
            if success:
                # The arm is moving to home, but we'll keep the returning_to_home flag set
                # until we detect we've reached home or timeout
                self.escape_attempts = 0
                # Don't reset persistent_head_collision_active here since we want to 
                # keep tracking it until we reach home or the collision naturally clears
                with self.collision_lock:
                    for direction in self.collision_status:
                        self.collision_status[direction]['consecutive_count'] = 0
            else:
                self.node.get_logger().error("Failed to send home position command")
                self.returning_to_home = False  # Clear flag if command failed
            
            # Reset idle timer
            self.last_activity_time = current_time
            
            return success
        except Exception as e:
            self.node.get_logger().error(f"Error moving to home position: {e}")
            self.returning_to_home = False  # Clear flag on error
            return False
    
    def move_to_safe_position(self, position, description="Proactive avoidance movement", override_checks=False):
        """Move to a position with collision checking."""
        try:
            # Check if position is in any recorded unsafe zone (skip if overriding)
            if not override_checks and self._is_position_in_unsafe_zone(position):
                self.node.get_logger().warn("Avoiding known unsafe position - finding alternative")
                
                # Try to find a slightly different position
                for _ in range(5):  # Try a few variations
                    # Add random perturbations to avoid unsafe zone
                    perturbed_pos = [p + random.uniform(-0.3, 0.3) for p in position]
                    
                    # Check if this position is safe
                    if not self._is_position_in_unsafe_zone(perturbed_pos):
                        position = perturbed_pos
                        self.node.get_logger().info("Found safer alternative position")
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
            self.node.get_logger().error(f"Error in move_to_safe_position: {e}")
            return False
    
    def _is_position_in_unsafe_zone(self, position):
        """Check if a position is in any of the recorded unsafe zones."""
        for unsafe_pos, radius in self.unsafe_zones:
            # Calculate Euclidean distance in joint space
            sum_squared = sum((p1 - p2) ** 2 for p1, p2 in zip(position, unsafe_pos))
            distance = math.sqrt(sum_squared)
            
            if distance < radius:
                return True
                
        return False
    
    def _activate_escape_mode(self, direction):
        """Activate escape mode to avoid persistent collisions in a direction."""
        self.escape_mode_active = True
        self.escape_mode_start_time = time.time()
        self.last_escape_direction = direction
        self.escape_attempts = 0
        
        self.node.get_logger().warn(f"Activating escape mode for {direction} collision")
        
        # Record current position as unsafe
        unsafe_radius = 0.4  # Joint space radius to consider unsafe
        self.unsafe_zones.append((self.current_joints.copy(), unsafe_radius))
        
        # Execute appropriate escape maneuver
        if self.is_animating():
            self._execute_animation_safe_escape(direction)
        else:
            self._execute_escape_maneuver(direction)
    
    def _execute_escape_maneuver(self, direction):
        """Execute an escape maneuver for a specific direction."""
        new_position = self.current_joints.copy()
        
        # Make the escape movement more dramatic than regular avoidance
        escape_magnitude = min(2.0, 1.0 + (self.escape_attempts * 0.3))
        
        if direction == 'front':
            # Pull back arm dramatically
            new_position[1] -= 0.6 * escape_magnitude  # Shoulder back
            new_position[2] += 0.4 * escape_magnitude  # Elbow fold
            
            # Add rotation to move out of the way
            # Use consistent rotation based on attempt # to avoid oscillation
            if self.escape_attempts % 2 == 0:
                new_position[0] += 0.8 * escape_magnitude  # Rotate right
            else:
                new_position[0] -= 0.8 * escape_magnitude  # Rotate left
                
        elif direction == 'left':
            # REVERSED: Escape to the RIGHT (positive rotation)
            new_position[0] += 0.8 * escape_magnitude
            new_position[1] += 0.3 * escape_magnitude  # Pull back
            
        elif direction == 'right':
            # REVERSED: Escape to the LEFT (negative rotation)
            new_position[0] -= 0.8 * escape_magnitude
            new_position[1] += 0.3 * escape_magnitude  # Pull back
        
        # Send the escape command with high priority
        self.send_safe_joint_command(new_position, f"Escape maneuver ({direction}, attempt {self.escape_attempts})")
        
        # Update tracking variables
        self.target_override_active = True
        self.target_override_time = time.time()
        self.target_override_joints = new_position.copy()
        self.target_override_reason = f"Escape from {direction} collision (attempt {self.escape_attempts})"
    
    def _execute_animation_safe_escape(self, direction):
        """Execute a gentler escape suitable during animations."""
        new_position = self.current_joints.copy()
        
        # Use smaller adjustments during animation to avoid disruption
        escape_magnitude = min(1.2, 0.8 + (self.escape_attempts * 0.1))
        
        if direction == 'front':
            # Pull back arm slightly
            new_position[1] -= 0.5 * escape_magnitude  # Shoulder back
            new_position[2] += 0.3 * escape_magnitude  # Elbow fold
            
            # Small rotation
            if self.escape_attempts % 2 == 0:
                new_position[0] += 0.3 * escape_magnitude
            else:
                new_position[0] -= 0.3 * escape_magnitude
                
        elif direction == 'left':
            # REVERSED: Smaller rotation to RIGHT
            new_position[0] += 0.4 * escape_magnitude
            
        elif direction == 'right':
            # REVERSED: Smaller rotation to LEFT
            new_position[0] -= 0.4 * escape_magnitude
        
        # Send command with note about animation-aware escape
        self.send_safe_joint_command(new_position, f"Animation-safe escape ({direction})")
        
        # Set shorter escape duration during animations
        self.escape_mode_duration = min(self.escape_mode_duration, 3.0)
    
    def is_animating(self):
        """Determine if the robot is currently executing an animation."""
        # Check if we've had any joint command in the last second that might be part of an animation
        time_since_last_command = time.time() - self.last_movement_time
        
        # If we've moved very recently, consider it an animation in progress
        if time_since_last_command < 0.5:
            return True
            
        # Also check if we're in the middle of a dramatic movement (high velocity)
        max_velocity = max([abs(v) for v in self.joint_velocities]) if self.joint_velocities else 0
        if max_velocity > 0.5:  # Significant movement in progress
            return True
            
        # Check if recent movements form a pattern consistent with animation
        # This helps detect ongoing animations even if current velocity is low
        if len(self.recent_command_times) >= 3:
            # Check for regular timing pattern in recent commands (animation typically has regular timing)
            intervals = [self.recent_command_times[i+1] - self.recent_command_times[i] 
                        for i in range(len(self.recent_command_times)-1)]
            if intervals and max(intervals) - min(intervals) < 0.2:  # Regular timing pattern
                return True
        
        return False
    
    def _publish_movement_source(self, source):
        """Publish movement source information for DEMA coordination."""
        try:
            # Check if node has movement source publisher
            if hasattr(self.node, 'enable_movement_source_integration') and self.node.enable_movement_source_integration:
                self.node.get_logger().info(f"Publishing movement source: {source} from collision avoidance")
                
                # Try with joint_states style encoding for hardware interface
                if hasattr(self.node, 'joint_states_publisher'):
                    msg = JointState()
                    msg.header.stamp = self.node.get_clock().now().to_msg()
                    msg.name = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
                    msg.position = self.current_joints.copy()
                    
                    # Encode movement source in velocity field
                    source_code = 0  # Default to idle
                    if source == "animation":
                        source_code = 1
                    elif source == "collision":
                        source_code = 2
                    elif source == "user":
                        source_code = 3
                    
                    msg.velocity = [float(source_code)]
                    self.node.joint_states_publisher.publish(msg)
                
                # Also try with the String message approach for compatibility
                if hasattr(self.node, 'movement_source_publisher'):
                    str_msg = String()
                    str_msg.data = source
                    self.node.movement_source_publisher.publish(str_msg)
        except Exception as e:
            self.node.get_logger().error(f"Error publishing movement source: {e}")
            import traceback
            self.node.get_logger().error(f"Stack trace: {traceback.format_exc()}")
