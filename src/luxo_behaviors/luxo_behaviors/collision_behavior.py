#!/usr/bin/env python3
#collision_behavior.py
"""
Collision behavior module for Luxo robot.
Handles collision detection, avoidance, and escape behaviors.
"""

import random
import time
import threading
from typing import Dict, List, Tuple, Optional
from luxo_behaviors.state_machine import LuxoState
from luxo_behaviors.shared_utils import (
    CollisionMath, MovementValidator, TimeUtils
)
import numpy as np


class CollisionBehavior:
    """Mixin class for collision avoidance behavior functionality."""
    
    def setup_collision_behavior(self):
        """Initialize collision behavior attributes and parameters."""
        # Collision avoidance parameters - check before declaring
        if not self.node.has_parameter('enable_collision_avoidance'):
            self.node.declare_parameter('enable_collision_avoidance', True)
        if not self.node.has_parameter('soft_limit_distance'):
            self.node.declare_parameter('soft_limit_distance', 15.0)
        if not self.node.has_parameter('hard_limit_distance'):
            self.node.declare_parameter('hard_limit_distance', 10.0)
        if not self.node.has_parameter('max_deceleration'):
            self.node.declare_parameter('max_deceleration', 5.0)
        if not self.node.has_parameter('collision_recovery_timeout'):
            self.node.declare_parameter('collision_recovery_timeout', 2.0)
        if not self.node.has_parameter('avoidance_playfulness'):
            self.node.declare_parameter('avoidance_playfulness', 0.5)
        if not self.node.has_parameter('side_avoidance_magnitude'):
            self.node.declare_parameter('side_avoidance_magnitude', 0.3)
        if not self.node.has_parameter('consecutive_collision_threshold'):
            self.node.declare_parameter('consecutive_collision_threshold', 3)
        if not self.node.has_parameter('escape_threshold'):
            self.node.declare_parameter('escape_threshold', 10)
        if not self.node.has_parameter('max_retreat_angle'):
            self.node.declare_parameter('max_retreat_angle', 0.5)
        if not self.node.has_parameter('escape_mode_duration'):
            self.node.declare_parameter('escape_mode_duration', 5.0)
        if not self.node.has_parameter('max_escape_attempts'):
            self.node.declare_parameter('max_escape_attempts', 3)
        
        # Load parameters
        self.enable_collision_avoidance = self.node.get_parameter('enable_collision_avoidance').value
        self.soft_limit_distance = self.node.get_parameter('soft_limit_distance').value
        self.hard_limit_distance = self.node.get_parameter('hard_limit_distance').value
        self.max_deceleration = self.node.get_parameter('max_deceleration').value
        self.collision_recovery_timeout = self.node.get_parameter('collision_recovery_timeout').value
        self.avoidance_playfulness = self.node.get_parameter('avoidance_playfulness').value
        self.side_avoidance_magnitude = self.node.get_parameter('side_avoidance_magnitude').value
        self.consecutive_collision_threshold = self.node.get_parameter('consecutive_collision_threshold').value
        self.escape_threshold = self.node.get_parameter('escape_threshold').value
        self.max_retreat_angle = self.node.get_parameter('max_retreat_angle').value
        self.escape_mode_duration = self.node.get_parameter('escape_mode_duration').value
        self.max_escape_attempts = self.node.get_parameter('max_escape_attempts').value
        
        # Initialize collision tracking
        self.collision_status = self.collision_tracker.status
        self.collision_lock = threading.Lock()
        self.last_collision_time = self.node.get_clock().now()
        self.last_avoidance_direction = None
        
        # Adjustment tracking
        self.adjustment_history = {
            'front': {
                'last_time': self.node.get_clock().now(), 
                'last_position': None, 
                'adjustment_made': False
            },
            'left': {
                'last_time': self.node.get_clock().now(), 
                'last_position': None, 
                'adjustment_made': False
            },
            'right': {
                'last_time': self.node.get_clock().now(), 
                'last_position': None, 
                'adjustment_made': False
            }
        }
        self.adjustment_cooldown = 0.2  # Reduced from 1.0 for faster response
        self.adjustment_position_threshold = 0.1
        
        # Escape mode variables
        self.escape_mode_start_time = self.node.get_clock().now()
        self.unsafe_zones = []  # List of positions to avoid
        self.last_escape_direction = None
        self.retreat_level = 0
        self.escape_attempts = 0
        
        # Persistent head collision tracking
        self.persistent_head_collision_start = self.node.get_clock().now()
        self.persistent_head_collision_active = False
        self.persistent_head_collision_last_log = self.node.get_clock().now()
        
        # Collision timeout configuration
        self.short_collision_timeout = 1.25  # Original timeout for quick response
        self.extended_collision_timeout = 8.0  # Extended timeout for persistent collisions
        self.max_collision_timeout = 15.0  # Maximum time before force reset
        
        # Last failed adjustment tracking
        self.last_failed_adjustment_time = self.node.get_clock().now()
        
        self.node.get_logger().info("Collision behavior initialized")
    
    def handle_collision(self, direction: str, is_active: bool):
        """Unified collision handling for all directions."""
        try:
            with self.collision_lock:
                # If we're returning to home, still track collisions but don't react
                was_active = self.collision_status[direction]['active']
                current_time = self.node.get_clock().now()
                
                # Track persistent head collision even when returning home
                if direction == 'front':
                    if is_active and self.collision_status[direction]['severity'] == 'danger':
                        if not self.persistent_head_collision_active:
                            self.persistent_head_collision_start = current_time
                            self.persistent_head_collision_active = True
                            self.node.get_logger().info("Started tracking persistent head collision")
                        else:
                            time_since_log = (current_time - self.persistent_head_collision_last_log).nanoseconds / 1e9
                            if time_since_log > 2.0:
                                duration = (current_time - self.persistent_head_collision_start).nanoseconds / 1e9
                                self.node.get_logger().info(f"Persistent head collision ongoing for {duration:.1f}s")
                                self.persistent_head_collision_last_log = current_time
                    else:
                        if self.persistent_head_collision_active:
                            self.node.get_logger().info("Persistent head collision cleared")
                            self.persistent_head_collision_active = False
                
                # If we're already returning to home, just track state but don't react
                if self._is_in_state(LuxoState.RETURNING_HOME):
                    self.collision_status[direction]['active'] = is_active
                    return
                
                # Fast path: No change in status
                if was_active == is_active and not (is_active and self.collision_status[direction]['consecutive_count'] > 3):
                    return
                
                # If newly active, start fresh
                if not was_active and is_active:
                    self.node.get_logger().debug(f"{direction.capitalize()} collision warning activated")
                    self.collision_status[direction]['active'] = True
                    self.collision_status[direction]['consecutive_count'] = 1
                    
                    # Transition to COLLISION_AVOIDING state
                    self._transition_to_state(LuxoState.COLLISION_AVOIDING)
                    
                    # Fast reaction for immediate danger
                    if self.collision_status[direction]['severity'] == 'danger':
                        self.collision_lock.release()
                        try:
                            self.perform_collision_avoidance(direction, self.collision_status[direction]['distance'], emergency=True)
                        finally:
                            self.collision_lock.acquire()
                    return
                
                # If collision was cleared
                if was_active and not is_active:
                    self.node.get_logger().info(f"{direction.capitalize()} collision warning cleared")
                    self.collision_status[direction]['active'] = False
                    self.collision_status[direction]['consecutive_count'] = 0
                    self.adjustment_history[direction]['adjustment_made'] = False
                    
                    # Check if all collisions are cleared
                    if not any(status['active'] for status in self.collision_status.values()):
                        if self._is_in_state(LuxoState.COLLISION_AVOIDING):
                            self._transition_to_state(LuxoState.IDLE)
                    return
                
                # Update the active state
                self.collision_status[direction]['active'] = is_active
                
                if is_active:  # If collision is still active
                    adjustment_made = self.adjustment_history[direction]['adjustment_made']
                    time_since_adjustment = (current_time - self.adjustment_history[direction]['last_time']).nanoseconds / 1e9
                    
                    if not adjustment_made or time_since_adjustment > self.adjustment_cooldown:
                        self.collision_status[direction]['consecutive_count'] += 1
                        
                        if self.collision_status[direction]['consecutive_count'] % 5 == 0:
                            self.node.get_logger().warn(
                                f"Persistent {direction} collision! Count: {self.collision_status[direction]['consecutive_count']}"
                            )
                        
                        # Check if we need to trigger escape mode
                        if self.collision_status[direction]['consecutive_count'] > self.escape_threshold:
                            self.node.get_logger().warn(
                                f"Persistent collision detected ({self.collision_status[direction]['consecutive_count']}), attempting to escape"
                            )
                            if not self._is_in_state(LuxoState.ESCAPE_MODE):
                                self.collision_lock.release()
                                try:
                                    self._activate_escape_mode(direction)
                                finally:
                                    self.collision_lock.acquire()
                            elif self.escape_attempts >= self.max_escape_attempts:
                                self.node.get_logger().warn("Multiple escape attempts failed, returning to rest position")
                                self.collision_lock.release()
                                try:
                                    self.go_to_rest_position("Escape failure rest position")
                                finally:
                                    self.collision_lock.acquire()
                                self.escape_attempts = 0
                    else:
                        if self.collision_status[direction]['consecutive_count'] > 3 and time_since_adjustment > (self.adjustment_cooldown / 2.0):
                            self.node.get_logger().debug(
                                f"{direction.capitalize()} collision still active after adjustment, "
                                f"waiting {self.adjustment_cooldown - time_since_adjustment:.1f}s before responding again"
                            )
                        
                        # Cap the count to prevent rapid escalation
                        if self.collision_status[direction]['consecutive_count'] > 5:
                            self.collision_status[direction]['consecutive_count'] = 5
                else:
                    if was_active:
                        self.node.get_logger().info(f"{direction.capitalize()} collision warning cleared")
                    self.collision_status[direction]['consecutive_count'] = 0
                    self.adjustment_history[direction]['adjustment_made'] = False
                    
        except Exception as e:
            self.node.get_logger().error(f"Error in handle_collision for {direction}: {e}")
            if self.collision_lock._is_owned():
                self.collision_lock.release()
    
    def update_distance(self, direction: str, value: float, is_proximity: bool = False):
        """Update distance information with fast reaction for dangerous values."""
        with self.collision_lock:
            # Special handling for proximity sensor
            if is_proximity:
                proximity = max(1, min(255, value))
                distance = max(1.0, 30.0 * (1.0 - proximity / 255.0))
            else:
                distance = value
            
            # Store the distance
            old_distance = self.collision_status[direction]['distance']
            self.collision_status[direction]['distance'] = distance
            
            # Calculate severity
            severity = CollisionMath.calculate_severity(
                distance, 
                danger_threshold=self.hard_limit_distance,
                warning_threshold=self.soft_limit_distance
            )
            self.collision_status[direction]['severity'] = severity
            
            # Fast reaction path
            current_time = self.node.get_clock().now()
            distance_getting_smaller = old_distance == float('inf') or distance < old_distance
            time_since_collision = TimeUtils.get_elapsed_time(self.node, self.last_collision_time)
            
            if (distance <= self.hard_limit_distance and 
                distance_getting_smaller and
                time_since_collision > 0.25 and
                not self.adjustment_history[direction]['adjustment_made']):
                
                self.last_collision_time = current_time
                self.collision_status[direction]['active'] = True
                
                # Transition to COLLISION_AVOIDING state
                self._transition_to_state(LuxoState.COLLISION_AVOIDING)
                
                # Release lock before potentially long operation
                self.collision_lock.release()
                try:
                    self.node.get_logger().warn(f"EMERGENCY: {direction} distance {distance:.2f}cm below hard limit")
                    self.perform_collision_avoidance(direction, distance, emergency=True)
                finally:
                    self.collision_lock.acquire()
    
    def update_severity(self, direction: str, severity: str):
        """Update severity information with immediate reaction for danger."""
        with self.collision_lock:
            old_severity = self.collision_status[direction]['severity']
            self.collision_status[direction]['severity'] = severity
            
            # Update persistent head collision tracking
            if direction == 'front':
                current_time = self.node.get_clock().now()
                if severity == 'danger':
                    if not self.persistent_head_collision_active:
                        self.persistent_head_collision_start = current_time
                        self.persistent_head_collision_active = True
                        self.persistent_head_collision_last_log = current_time
                        self.node.get_logger().info("Started tracking persistent head collision due to danger severity")
                else:
                    if self.persistent_head_collision_active:
                        self.node.get_logger().info("Persistent head collision cleared (severity changed)")
                        self.persistent_head_collision_active = False
            
            # Fast reaction path
            if severity == 'danger' and old_severity != 'danger':
                current_time = self.node.get_clock().now()
                time_since_collision = TimeUtils.get_elapsed_time(self.node, self.last_collision_time)
                if time_since_collision > 0.25:
                    self.last_collision_time = current_time
                    self.collision_status[direction]['active'] = True
                    
                    # Transition to COLLISION_AVOIDING state
                    self._transition_to_state(LuxoState.COLLISION_AVOIDING)
                    
                    # Release lock before potentially long operation
                    self.collision_lock.release()
                    try:
                        self.node.get_logger().warn(f"EMERGENCY: {direction} severity changed to 'danger'")
                        self.perform_collision_avoidance(direction, self.collision_status[direction]['distance'], emergency=True)
                    finally:
                        self.collision_lock.acquire()
    
    def perform_collision_avoidance(self, direction: str, distance: float, emergency: bool = False):
        """Perform collision avoidance with rotation limit awareness and dynamic acceleration."""
        # Update activity time
        current_time = self.node.get_clock().now()
        self.last_activity_time = current_time
        
        if emergency and self.should_preempt_animation("danger"):
            with self.animation_lock:
                self.animation_preempted = True
                self.animation_preemption_time = current_time
                self.node.get_logger().warn(
                    f"Animation '{self.current_animation_name}' should be preempted due to {direction} collision"
                )
        
        self.node.get_logger().debug(f"Activity timestamp updated due to collision avoidance action")
        
        # Report collision movement source
        self._publish_movement_source("collision")
        
        try:
            # Start with current position
            new_position = self.current_joints.copy()
            
            # Get collision metrics
            consecutive_count = self.collision_status[direction]['consecutive_count']
            severity = self.collision_status[direction]['severity']
            
            # Calculate acceleration and magnitude
            acceleration = CollisionMath.calculate_acceleration(
                severity, consecutive_count, base_acceleration=12.5
            )
            
            magnitude = CollisionMath.calculate_avoidance_magnitude(
                severity, consecutive_count, emergency
            )
            
            self.node.get_logger().info(
                f"Using acceleration {acceleration} and magnitude {magnitude:.2f} for {direction} collision"
            )
            
            # Check base limits
            current_base = new_position[0]
            near_min_limit = self.safety_limits.is_near_base_limit(current_base) == 'min'
            near_max_limit = self.safety_limits.is_near_base_limit(current_base) == 'max'
            at_min_limit = self.safety_limits.is_at_base_limit(current_base) == 'min'
            at_max_limit = self.safety_limits.is_at_base_limit(current_base) == 'max'
            
            if direction == 'front':
                # Pull back shoulder and elbow
                new_position[1] -= 0.6 * magnitude
                new_position[2] += 0.4 * magnitude
                
                # Calculate escape rotation
                if consecutive_count > 5:
                    if at_max_limit and self.enable_base_wraparound:
                        rotation = -(abs(current_base - self.base_min_limit) * 0.8)
                        self.node.get_logger().warn(f"Front collision at max limit - attempting wraparound")
                    elif at_min_limit and self.enable_base_wraparound:
                        rotation = (abs(current_base - self.base_max_limit) * 0.8)
                        self.node.get_logger().warn(f"Front collision at min limit - attempting wraparound")
                    else:
                        rotation = CollisionMath.calculate_escape_rotation(direction, 0.5, magnitude)
                else:
                    rotation = CollisionMath.calculate_escape_rotation(direction, 0.3, magnitude)
                    if near_max_limit:
                        rotation = -abs(rotation)
                    elif near_min_limit:
                        rotation = abs(rotation)
                
                new_position[0] += rotation
                
            elif direction == 'left':
                rotation = CollisionMath.calculate_escape_rotation(direction, 0.4, magnitude)
                if at_min_limit and self.enable_base_wraparound:
                    new_position[0] = self.base_max_limit - 0.2
                    self.node.get_logger().info("Left collision at min limit - wraparound to max side")
                elif at_min_limit:
                    new_position[0] += abs(rotation) * 1.5
                    self.node.get_logger().info("Left collision at min limit - rotating RIGHT instead")
                else:
                    new_position[0] += rotation
                new_position[1] += 0.1 * magnitude
                
            elif direction == 'right':
                rotation = CollisionMath.calculate_escape_rotation(direction, 0.4, magnitude)
                if at_max_limit and self.enable_base_wraparound:
                    new_position[0] = self.base_min_limit + 0.2
                    self.node.get_logger().info("Right collision at max limit - wraparound to min side")
                elif at_max_limit:
                    new_position[0] += rotation * 1.5
                    self.node.get_logger().info("Right collision at max limit - rotating LEFT instead")
                else:
                    new_position[0] += rotation
                new_position[1] += 0.1 * magnitude
            
            # Clamp and validate
            new_position[0] = self.safety_limits.clamp_base_angle(new_position[0])
            new_position = MovementValidator.validate_position(new_position, self.safety_limits)
            
            # Add acceleration
            new_position_with_acceleration = new_position.copy() + [acceleration]
            
            # Send command
            self.send_safe_joint_command(
                new_position_with_acceleration, 
                f"Collision avoidance (count: {consecutive_count}, accel: {acceleration})"
            )
            
            # Create persistent override
            self.target_override_active = True
            self.target_override_time = current_time
            self.target_override_joints = new_position.copy()
            self.target_override_reason = f"Collision avoidance for {direction} at {distance:.1f}cm (accel: {acceleration})"
            self.target_joints = new_position.copy()
            
            # If emergency and multiple attempts failed
            if emergency and consecutive_count > self.escape_threshold:
                self.node.get_logger().warn(f"Multiple path adjustments failed, will return to rest position")
                self.go_to_rest_position("Emergency rest return")
                
                # Reset collision counts
                with self.collision_lock:
                    for dir in self.collision_status:
                        self.collision_status[dir]['consecutive_count'] = 0
            
            self.node.get_logger().warn(f"Collision avoidance COMPLETED for {direction} at {distance:.1f}cm with acceleration {acceleration}")
            
        except Exception as e:
            self.node.get_logger().error(f"Error in collision avoidance: {e}")
    
    def apply_safety_limits(self, positions: List[float]) -> List[float]:
        """Apply safety limits to joint positions based on collision status."""
        # Skip collision-based limits when returning home
        if self._is_in_state(LuxoState.RETURNING_HOME):
            return positions
        
        # Validate position
        validated_positions = MovementValidator.validate_position(positions, self.safety_limits)
        safe_positions = validated_positions.copy()
        
        # Check for front collisions
        if self.collision_status['front']['active']:
            severity = self.collision_status['front']['severity']
            distance = self.collision_status['front']['distance']
            
            if severity == 'danger' or distance <= self.hard_limit_distance:
                safe_positions[1] = max(safe_positions[1], self.current_joints[1])
                safe_positions[2] = max(safe_positions[2], self.current_joints[2])
                
            elif severity == 'warning' or distance <= self.soft_limit_distance:
                limit_factor = min(1.0, (distance - self.hard_limit_distance) / 
                                (self.soft_limit_distance - self.hard_limit_distance))
                
                if safe_positions[1] < self.current_joints[1]:
                    delta = self.current_joints[1] - safe_positions[1]
                    safe_positions[1] = self.current_joints[1] - (delta * limit_factor)
                    
                if safe_positions[2] < self.current_joints[2]:
                    delta = self.current_joints[2] - safe_positions[2]
                    safe_positions[2] = self.current_joints[2] - (delta * limit_factor)
        
        # Check for left collisions
        if self.collision_status['left']['active']:
            severity = self.collision_status['left']['severity']
            distance = self.collision_status['left']['distance']
            
            if (severity == 'danger' or distance <= self.hard_limit_distance) and safe_positions[0] > self.current_joints[0]:
                safe_positions[0] = self.current_joints[0]
            elif (severity == 'warning' or distance <= self.soft_limit_distance) and safe_positions[0] > self.current_joints[0]:
                limit_factor = min(1.0, (distance - self.hard_limit_distance) / 
                                (self.soft_limit_distance - self.hard_limit_distance))
                delta = safe_positions[0] - self.current_joints[0]
                safe_positions[0] = self.current_joints[0] + (delta * limit_factor)

        # Check for right collisions
        if self.collision_status['right']['active']:
            severity = self.collision_status['right']['severity']
            distance = self.collision_status['right']['distance']
            
            if (severity == 'danger' or distance <= self.hard_limit_distance) and safe_positions[0] < self.current_joints[0]:
                safe_positions[0] = self.current_joints[0]
            elif (severity == 'warning' or distance <= self.soft_limit_distance) and safe_positions[0] < self.current_joints[0]:
                limit_factor = min(1.0, (distance - self.hard_limit_distance) / 
                                (self.soft_limit_distance - self.hard_limit_distance))
                delta = self.current_joints[0] - safe_positions[0]
                safe_positions[0] = self.current_joints[0] - (delta * limit_factor)
        
        return safe_positions
    
    def adjust_path_for_collision(self, front_status: dict, left_status: dict, right_status: dict):
        """Adjust the current motion path to avoid obstacles."""
        # Skip when returning home
        if self._is_in_state(LuxoState.RETURNING_HOME):
            return

        # Update activity time
        current_time = self.node.get_clock().now()
        self.last_activity_time = current_time
        self.node.get_logger().debug(f"Activity timestamp updated due to collision path adjustment")

        # Check if we're in voice following mode - be less aggressive with collision overrides
        is_voice_following = self._is_in_state(LuxoState.VOICE_FOLLOWING)

        # Calculate adjustment factors
        front_factor = self.calculate_adjustment_factor(front_status)
        left_factor = self.calculate_adjustment_factor(left_status)
        right_factor = self.calculate_adjustment_factor(right_status)

        # During voice following, require higher thresholds and consecutive detections
        if is_voice_following:
            # Only override for true danger (not warnings) during voice following
            min_consecutive_for_override = 3  # Require 3 consecutive detections

            # Check consecutive counts
            front_consecutive_ok = front_status['consecutive_count'] >= min_consecutive_for_override
            left_consecutive_ok = left_status['consecutive_count'] >= min_consecutive_for_override
            right_consecutive_ok = right_status['consecutive_count'] >= min_consecutive_for_override

            # Only allow override if: (danger level AND consecutive) OR (very close to hard limit)
            if front_factor < 1.0 and not front_consecutive_ok:
                front_factor = 0.0
                self.node.get_logger().debug(f"🎤 Voice following: Suppressing front collision (consecutive: {front_status['consecutive_count']}/{min_consecutive_for_override})")

            if left_factor < 1.0 and not left_consecutive_ok:
                left_factor = 0.0
                self.node.get_logger().debug(f"🎤 Voice following: Suppressing left collision (consecutive: {left_status['consecutive_count']}/{min_consecutive_for_override})")

            if right_factor < 1.0 and not right_consecutive_ok:
                right_factor = 0.0
                self.node.get_logger().debug(f"🎤 Voice following: Suppressing right collision (consecutive: {right_status['consecutive_count']}/{min_consecutive_for_override})")

        # Early return if no adjustments needed
        if front_factor < 0.1 and left_factor < 0.1 and right_factor < 0.1:
            return
        
        # Create adjusted targets
        adjusted_targets = self.target_joints.copy()
        base_adjustment = 0.0
        adjustment_msgs = []
        
        # Handle right collision
        right_cooldown_active = (
            (current_time - self.adjustment_history['right']['last_time']).nanoseconds / 1e9 < self.adjustment_cooldown and
            self.adjustment_history['right']['adjustment_made']
        )
        
        if right_factor > 0.1 and not right_cooldown_active:
            right_multiplier = min(3.0, 1.0 + right_status['consecutive_count'] * 0.1)
            right_adjustment = right_factor * 0.7 * right_multiplier
            base_adjustment += right_adjustment
            
            adjustment_msgs.append(f"right(rotate right: {right_adjustment:.2f})")
            self.node.get_logger().info(
                f"Right collision adjusting base: {right_adjustment:.2f} "
                f"(factor: {right_factor:.2f}, count: {right_status['consecutive_count']})"
            )
            
            self.adjustment_history['right']['last_time'] = current_time
            self.adjustment_history['right']['last_position'] = self.current_joints.copy()
            self.adjustment_history['right']['adjustment_made'] = True

            # During voice following, skip immediate collision responses unless truly critical
            # This prevents constant wraparound spam that blocks voice tracking
            should_send_immediate = right_status['distance'] <= self.hard_limit_distance
            if is_voice_following and should_send_immediate:
                # During voice following, only send immediate response for very close collisions
                if right_status['distance'] <= (self.hard_limit_distance * 0.7):  # 70% of hard limit
                    temp_position = self.current_joints.copy()
                    temp_position[0] += right_adjustment
                    self.send_safe_joint_command(temp_position, "Immediate right collision response")
                else:
                    self.node.get_logger().debug(f"🎤 Voice following: Skipping immediate right response (distance: {right_status['distance']:.1f}cm)")
            elif should_send_immediate and not is_voice_following:
                temp_position = self.current_joints.copy()
                temp_position[0] += right_adjustment
                self.send_safe_joint_command(temp_position, "Immediate right collision response")
        elif right_factor > 0.1 and right_cooldown_active:
            time_since_adjustment = (current_time - self.adjustment_history['right']['last_time']).nanoseconds / 1e9
            self.node.get_logger().debug(f"Skipping right adjustment - on cooldown ({time_since_adjustment:.1f}s)")
            
            if time_since_adjustment > (self.adjustment_cooldown * 0.75):
                with self.collision_lock:
                    if self.collision_status['right']['consecutive_count'] > 3:
                        self.collision_status['right']['consecutive_count'] = 3
                        self.node.get_logger().info("Adjusting right collision count to prevent escalation")
        
        # Handle left collision (similar pattern)
        left_cooldown_active = (
            (current_time - self.adjustment_history['left']['last_time']).nanoseconds / 1e9 < self.adjustment_cooldown and
            self.adjustment_history['left']['adjustment_made']
        )
        
        if left_factor > 0.1 and not left_cooldown_active:
            left_multiplier = min(3.0, 1.0 + left_status['consecutive_count'] * 0.1)
            left_adjustment = -left_factor * 0.7 * left_multiplier
            base_adjustment += left_adjustment
            
            adjustment_msgs.append(f"left(rotate left: {left_adjustment:.2f})")
            self.node.get_logger().info(
                f"Left collision adjusting base: {left_adjustment:.2f} "
                f"(factor: {left_factor:.2f}, count: {left_status['consecutive_count']})"
            )
            
            self.adjustment_history['left']['last_time'] = current_time
            self.adjustment_history['left']['last_position'] = self.current_joints.copy()
            self.adjustment_history['left']['adjustment_made'] = True

            # During voice following, skip immediate collision responses unless truly critical
            # This prevents constant wraparound spam that blocks voice tracking
            should_send_immediate = left_status['distance'] <= self.hard_limit_distance
            if is_voice_following and should_send_immediate:
                # During voice following, only send immediate response for very close collisions
                if left_status['distance'] <= (self.hard_limit_distance * 0.7):  # 70% of hard limit
                    temp_position = self.current_joints.copy()
                    temp_position[0] += left_adjustment
                    self.send_safe_joint_command(temp_position, "Immediate left collision response")
                else:
                    self.node.get_logger().debug(f"🎤 Voice following: Skipping immediate left response (distance: {left_status['distance']:.1f}cm)")
            elif should_send_immediate and not is_voice_following:
                temp_position = self.current_joints.copy()
                temp_position[0] += left_adjustment
                self.send_safe_joint_command(temp_position, "Immediate left collision response")
        elif left_factor > 0.1 and left_cooldown_active:
            time_since_adjustment = (current_time - self.adjustment_history['left']['last_time']).nanoseconds / 1e9
            self.node.get_logger().debug(f"Skipping left adjustment - on cooldown ({time_since_adjustment:.1f}s)")
            
            if time_since_adjustment > (self.adjustment_cooldown * 0.75):
                with self.collision_lock:
                    if self.collision_status['left']['consecutive_count'] > 3:
                        self.collision_status['left']['consecutive_count'] = 3
                        self.node.get_logger().info("Adjusting left collision count to prevent escalation")
        
        # Apply base adjustment
        if abs(base_adjustment) > 0.01:
            adjusted_targets[0] += base_adjustment
        
        # Handle front collision
        front_cooldown_active = (
            (current_time - self.adjustment_history['front']['last_time']).nanoseconds / 1e9 < self.adjustment_cooldown and
            self.adjustment_history['front']['adjustment_made']
        )
        
        if front_factor > 0.1 and not front_cooldown_active:
            persistence_multiplier = min(3.0, 1.0 + front_status['consecutive_count'] * 0.05)
            
            shoulder_adjustment = front_factor * 0.4 * persistence_multiplier
            elbow_adjustment = front_factor * 0.3 * persistence_multiplier
            adjusted_targets[1] -= shoulder_adjustment
            adjusted_targets[2] -= elbow_adjustment
            adjusted_targets[3] -= (shoulder_adjustment + elbow_adjustment) * 0
            
            adjustment_msgs.append(f"front(retreat: {shoulder_adjustment:.2f})")
            
            self.adjustment_history['front']['last_time'] = current_time
            self.adjustment_history['front']['last_position'] = self.current_joints.copy()
            self.adjustment_history['front']['adjustment_made'] = True
        elif front_factor > 0.1 and front_cooldown_active:
            time_since_adjustment = (current_time - self.adjustment_history['front']['last_time']).nanoseconds / 1e9
            self.node.get_logger().debug(f"Skipping front adjustment - on cooldown ({time_since_adjustment:.1f}s)")
            
            if time_since_adjustment > (self.adjustment_cooldown * 0.75):
                with self.collision_lock:
                    if self.collision_status['front']['consecutive_count'] > 3:
                        self.collision_status['front']['consecutive_count'] = 3
                        self.node.get_logger().info("Adjusting front collision count to prevent escalation")
        
        # If no adjustments to make, return
        if not adjustment_msgs:
            return
        
        self.node.get_logger().debug(f"Dynamic collision avoidance: {', '.join(adjustment_msgs)}")
        
        # Check if already at adjusted position
        if self._at_position(adjusted_targets, self.current_joints, 0.1):
            self.node.get_logger().info("Already at adjusted position - skipping adjustment")
            
            time_since_failed = (current_time - self.last_failed_adjustment_time).nanoseconds / 1e9
            
            if time_since_failed > 2.0:
                # Find most persistent collision
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
        
        # Reset failed adjustment timer
        self.last_failed_adjustment_time = current_time
        
        # Send adjusted target
        self.send_safe_joint_command(adjusted_targets, "Collision avoidance adjustment")
        
        # Set target override
        self.target_override_active = True
        self.target_override_time = current_time
        self.target_override_joints = adjusted_targets.copy()
        self.target_override_reason = f"Path adjustment: {', '.join(adjustment_msgs)}"
        
        self.node.get_logger().info(f"Created target override: {self.target_override_reason}")
        self.node.get_logger().debug(f"ADJUSTMENT SENT: {[round(p, 2) for p in adjusted_targets]}")
        
        # Update last movement time
        self.last_movement_time = current_time
    
    def calculate_adjustment_factor(self, status: dict) -> float:
        """Calculate adjustment factor (0.0-1.0) based on collision status."""
        # Calculate severity if not set
        if 'severity' not in status or not status['severity']:
            severity = CollisionMath.calculate_severity(
                status['distance'],
                danger_threshold=self.hard_limit_distance,
                warning_threshold=self.soft_limit_distance
            )
        else:
            severity = status['severity']
        
        # Strong factor for danger
        if severity == 'danger':
            return 1.0
        
        # Check activity and distance
        if status['active'] or severity == 'warning':
            if status['distance'] <= self.hard_limit_distance:
                return 1.0
            elif status['distance'] <= self.soft_limit_distance:
                range_fraction = (self.soft_limit_distance - status['distance']) / \
                                (self.soft_limit_distance - self.hard_limit_distance)
                return max(0.1, min(1.0, range_fraction))
        
        return 0.0
    
    def check_persistent_collision(self, current_time) -> Optional[str]:
        """
        Check for persistent collisions that need special handling.
        Returns the action to take ('escape', 'home', or None).
        """
        # Check persistent head collision duration
        if self.persistent_head_collision_active:
            head_collision_duration = (current_time - self.persistent_head_collision_start).nanoseconds / 1e9
            
            # Log periodically
            time_since_log = (current_time - self.persistent_head_collision_last_log).nanoseconds / 1e9
            if time_since_log > 1.0:
                self.node.get_logger().info(f"Persistent head collision duration: {head_collision_duration:.1f}s")
                self.persistent_head_collision_last_log = current_time
            
            # Determine action based on duration
            if head_collision_duration > self.extended_collision_timeout:
                return 'home'
            elif head_collision_duration > self.short_collision_timeout:
                if not self._is_in_state(LuxoState.ESCAPE_MODE):
                    return 'escape'
        
        # Check for any persistent collisions
        with self.collision_lock:
            any_persistent = any(status['consecutive_count'] > 5 for status in self.collision_status.values())
            
            if any_persistent:
                # Log persistent collision counts
                front_count = self.collision_status['front']['consecutive_count']
                left_count = self.collision_status['left']['consecutive_count']
                right_count = self.collision_status['right']['consecutive_count']
                
                self.node.get_logger().warn(
                    f"Persistent collision detected - counts: Front={front_count}, "
                    f"Left={left_count}, Right={right_count}"
                )
                
                # Force avoidance for persistent collisions
                for direction, status in self.collision_status.items():
                    if status['consecutive_count'] > 5 and status['severity'] == 'danger':
                        self.node.get_logger().warn(f"Forcing avoidance for persistent {direction} collision")
                        self.perform_collision_avoidance(direction, status['distance'], emergency=True)
                        break
        
        return None
    
    def check_escape_mode_status(self, current_time) -> bool:
        """
        Check and update escape mode status.
        Returns True if escape mode is active.
        """
        if not self._is_in_state(LuxoState.ESCAPE_MODE):
            return False
        
        # Check escape duration
        escape_duration = (current_time - self.escape_mode_start_time).nanoseconds / 1e9
        if escape_duration > self.escape_mode_duration:
            # Transition back to IDLE
            self._transition_to_state(LuxoState.IDLE)
            self.node.get_logger().info("Escape mode deactivated - normal operation resuming")
            
            # Force publish current position
            self.publish_actual_joint_states(self.current_joints)
            return False
        
        # Check if still in collision
        with self.collision_lock:
            persistent_collision = False
            
            if not self.is_animating():
                # Check for persistent collision in escape direction
                if self.last_escape_direction:
                    status = self.collision_status.get(self.last_escape_direction, {})
                    if (status.get('active', False) and 
                        status.get('consecutive_count', 0) > self.consecutive_collision_threshold):
                        persistent_collision = True
            
            if persistent_collision:
                # Try another escape
                self.escape_attempts += 1
                
                if self.escape_attempts >= self.max_escape_attempts:
                    self.node.get_logger().warn(
                        f"Escape attempts exceeded ({self.escape_attempts}/{self.max_escape_attempts}), "
                        f"returning to rest"
                    )
                    self.go_to_rest_position("Escape failure rest position")
                    self._transition_to_state(LuxoState.IDLE)
                    self.escape_attempts = 0
                    return False
                else:
                    # Try another escape
                    if self.is_animating():
                        self._execute_animation_safe_escape(self.last_escape_direction)
                    else:
                        self._execute_escape_maneuver(self.last_escape_direction)
        
        return True
    
    def _is_position_in_unsafe_zone(self, position: List[float]) -> bool:
        """Check if a position is in any of the recorded unsafe zones."""
        for unsafe_pos, radius in self.unsafe_zones:
            distance = self.position_utils.calculate_position_distance(position, unsafe_pos)
            if distance < radius:
                return True
        return False
    
    def _activate_escape_mode(self, direction: str):
        """Activate escape mode to avoid persistent collisions."""
        # Transition to ESCAPE_MODE state
        self._transition_to_state(LuxoState.ESCAPE_MODE)
        
        self.escape_mode_start_time = self.node.get_clock().now()
        self.last_escape_direction = direction
        self.escape_attempts = 0
        
        self.node.get_logger().warn(f"Activating escape mode for {direction} collision")
        
        # Record current position as unsafe
        unsafe_radius = 0.4
        self.unsafe_zones.append((self.current_joints.copy(), unsafe_radius))
        
        # Execute escape maneuver
        if self.is_animating():
            self._execute_animation_safe_escape(direction)
        else:
            self._execute_escape_maneuver(direction)
    
    def _execute_escape_maneuver(self, direction: str):
        """Execute an escape maneuver for a specific direction."""
        new_position = self.current_joints.copy()
        
        # Calculate escape parameters
        escape_magnitude = min(2.0, 1.0 + (self.escape_attempts * 0.3))
        
        # Check base limits
        current_base = new_position[0]
        at_min_limit = self.safety_limits.is_at_base_limit(current_base) == 'min'
        at_max_limit = self.safety_limits.is_at_base_limit(current_base) == 'max'
        
        if direction == 'front':
            # Pull back dramatically
            new_position[1] -= 0.6 * escape_magnitude
            new_position[2] += 0.4 * escape_magnitude
            
            # Handle rotation with wraparound
            if at_max_limit and self.enable_base_wraparound:
                new_position[0] = self.base_min_limit + 0.5
                self.node.get_logger().warn("Escape: wraparound from max to min limit")
            elif at_min_limit and self.enable_base_wraparound:
                new_position[0] = self.base_max_limit - 0.5
                self.node.get_logger().warn("Escape: wraparound from min to max limit")
            else:
                rotation = CollisionMath.calculate_escape_rotation(direction, 0.8, escape_magnitude)
                if self.escape_attempts % 2 == 0:
                    new_position[0] += abs(rotation)
                else:
                    new_position[0] -= abs(rotation)
                    
        elif direction == 'left':
            # Escape RIGHT
            if at_min_limit and self.enable_base_wraparound:
                new_position[0] = self.base_max_limit - 0.3
                self.node.get_logger().warn("Left escape: wraparound to max limit")
            else:
                rotation = CollisionMath.calculate_escape_rotation(direction, 0.8, escape_magnitude)
                new_position[0] += rotation
            new_position[1] += 0.3 * escape_magnitude
            
        elif direction == 'right':
            # Escape LEFT
            if at_max_limit and self.enable_base_wraparound:
                new_position[0] = self.base_min_limit + 0.3
                self.node.get_logger().warn("Right escape: wraparound to min side")
            else:
                rotation = CollisionMath.calculate_escape_rotation(direction, 0.8, escape_magnitude)
                new_position[0] += rotation
            new_position[1] += 0.3 * escape_magnitude
        
        # Clamp and validate
        new_position[0] = self.safety_limits.clamp_base_angle(new_position[0])
        new_position = MovementValidator.validate_position(new_position, self.safety_limits)
        
        # Send command
        self.send_safe_joint_command(
            new_position, 
            f"Escape maneuver ({direction}, attempt {self.escape_attempts})"
        )
        
        # Update tracking
        self.target_override_active = True
        self.target_override_time = self.node.get_clock().now()
        self.target_override_joints = new_position.copy()
        self.target_override_reason = f"Escape from {direction} collision (attempt {self.escape_attempts})"
    
    def _execute_animation_safe_escape(self, direction: str):
        """Execute a gentler escape suitable during animations."""
        new_position = self.current_joints.copy()
        
        # Smaller adjustments during animation
        escape_magnitude = min(1.2, 0.8 + (self.escape_attempts * 0.1))
        
        if direction == 'front':
            new_position[1] -= 0.5 * escape_magnitude
            new_position[2] += 0.3 * escape_magnitude
            
            rotation = CollisionMath.calculate_escape_rotation(direction, 0.3, escape_magnitude)
            if self.escape_attempts % 2 == 0:
                new_position[0] += abs(rotation)
            else:
                new_position[0] -= abs(rotation)
                
        elif direction == 'left':
            rotation = CollisionMath.calculate_escape_rotation(direction, 0.4, escape_magnitude)
            new_position[0] += rotation
            
        elif direction == 'right':
            rotation = CollisionMath.calculate_escape_rotation(direction, 0.4, escape_magnitude)
            new_position[0] += rotation
        
        # Validate
        new_position = MovementValidator.validate_position(new_position, self.safety_limits)
        
        # Send command
        self.send_safe_joint_command(new_position, f"Animation-safe escape ({direction})")
        
        # Shorter escape duration during animations
        self.escape_mode_duration = min(self.escape_mode_duration, 3.0)