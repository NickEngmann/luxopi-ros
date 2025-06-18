#!/usr/bin/env python3
"""
Shared utilities module for ROS2 Luxo behavior nodes.
Contains common functions, constants, and helpers used across multiple behavior nodes.
"""

import math
import random
import numpy as np
from typing import List, Tuple, Optional, Union
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from rclpy.time import Time
from rclpy.node import Node


class LuxoConstants:
    """Constants used across Luxo behavior nodes."""
    
    # Joint limits (radians)
    BASE_MIN_LIMIT = np.deg2rad(-260.0)
    BASE_MAX_LIMIT = np.deg2rad(135.0)
    BASE_SOFT_MIN_OFFSET = np.deg2rad(10.0)
    BASE_SOFT_MAX_OFFSET = np.deg2rad(10.0)
    
    # Home position sequences
    HOME_POSITION_1 = [0.5, 0.5, 1.3, 1.4, -1.5]  # Initial home position
    HOME_POSITION_2 = [0.5, -0.85, 1.3, 1.4, -1.5]  # Final home position
    HOME_POSITION_TOLERANCE = 0.2
    HOME_POSITION_STAGE_TIMEOUT = 0.5  # seconds
    
    # Rest position configuration
    BASE_REST_POSITION = [0.0, -0.55, 1.2, 1.4, -1.5]
    REST_VARIATION_RANGE = 0.1
    
    # Idle behavior constants
    IDLE_BASE_POSITION = [0.0, -0.55, 1.2, 1.4, -1.5]
    IDLE_HEAD_BASE_ROTATION_RANGE = 0.3
    IDLE_HEAD_LOOK_UP_RANGE = 0.4
    IDLE_HEAD_LOOK_DOWN_RANGE = 0.1
    IDLE_HEAD_VARIATION_SPEED = 14.0
    
    # Voice following constants
    VOICE_NEUTRAL_POSITION = [-0.55, 1.2, 1.4, -2.0, 10.0]  # Baseline position (excluding base)
    VOICE_DIRECTION_TOLERANCE = 5.0  # degrees
    VOICE_ON_TARGET_THRESHOLD = 3.0  # seconds
    VOICE_VARIATION_INTERVAL = 2.0  # seconds
    VOICE_TIMEOUT = 2.0  # seconds
    
    # Collision avoidance constants
    DEFAULT_SOFT_LIMIT_DISTANCE = 15.0  # cm
    DEFAULT_HARD_LIMIT_DISTANCE = 8.0   # cm
    MAX_DECELERATION = 22.5
    ADJUSTMENT_COOLDOWN = 1.0  # seconds
    ADJUSTMENT_POSITION_THRESHOLD = 0.1
    CONSECUTIVE_COLLISION_THRESHOLD = 5
    ESCAPE_THRESHOLD = 8
    MAX_ESCAPE_ATTEMPTS = 3
    ESCAPE_MODE_DURATION = 5.0  # seconds
    
    # Timing constants
    SHORT_COLLISION_TIMEOUT = 1.25   # seconds
    EXTENDED_COLLISION_TIMEOUT = 8.0  # seconds
    MAX_COLLISION_TIMEOUT = 15.0     # seconds
    TARGET_OVERRIDE_TIMEOUT = 10.0   # seconds
    
    # Animation constants
    IDLE_ANIMATIONS = [
        'gentle_sway', 'curious_exploration', 'breathing', 
        'attentive_listening', 'playful_bob', 'scanning_watch',
        'settling_adjust', 'dreamy_drift', 'neck_stretch',
        'yawning_stretch', 'shoulder_shimmy', 'look_around_casual'
    ]
    
    PETTING_ANIMATIONS = ['folded_wiggle']
    
    # Petting behavior constants
    PETTING_MESSAGE_TIMEOUT = 5.0  # seconds
    PETTING_ANIMATION_COOLDOWN = 8.0  # seconds


class AngleUtils:
    """Utilities for angle calculations and wraparound logic."""
    
    @staticmethod
    def normalize_angle(angle: float) -> float:
        """
        Normalize angle to [-pi, pi] range.
        
        Args:
            angle: Angle in radians
            
        Returns:
            Normalized angle in [-pi, pi]
        """
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle
    
    @staticmethod
    def should_wrap_around(current_angle: float, target_angle: float) -> bool:
        """
        Check if wrapping around would be more efficient for base rotation.
        
        Args:
            current_angle: Current base angle in radians
            target_angle: Target base angle in radians
            
        Returns:
            True if wrap-around path is more efficient
        """
        direct_path = abs(AngleUtils.normalize_angle(target_angle - current_angle))
        wrap_path = 2 * np.pi - direct_path
        
        # If wrap path is significantly shorter (30% shorter)
        return wrap_path < direct_path * 0.7
    
    @staticmethod
    def calculate_wraparound_target(target_angle: float, 
                                   base_min_limit: float = LuxoConstants.BASE_MIN_LIMIT,
                                   base_max_limit: float = LuxoConstants.BASE_MAX_LIMIT) -> Tuple[float, bool]:
        """
        Calculate wraparound target angle if needed.
        
        Args:
            target_angle: Desired target angle
            base_min_limit: Minimum base rotation limit
            base_max_limit: Maximum base rotation limit
            
        Returns:
            Tuple of (adjusted_angle, was_wrapped)
        """
        normalized_target = AngleUtils.normalize_angle(target_angle)
        
        if normalized_target > base_max_limit:
            # Try wraparound to negative side
            wraparound_target = normalized_target - 2 * np.pi
            if wraparound_target >= base_min_limit:
                return wraparound_target, True
            else:
                # Clamp to max limit
                return base_max_limit, False
                
        elif normalized_target < base_min_limit:
            # Try wraparound to positive side
            wraparound_target = normalized_target + 2 * np.pi
            if wraparound_target <= base_max_limit:
                return wraparound_target, True
            else:
                # Clamp to min limit
                return base_min_limit, False
        
        return normalized_target, False
    
    @staticmethod
    def is_near_limit(angle: float, 
                     limit: float, 
                     threshold: float = np.deg2rad(20.0)) -> bool:
        """
        Check if angle is near a rotation limit.
        
        Args:
            angle: Current angle
            limit: Limit to check against
            threshold: Distance threshold for "near"
            
        Returns:
            True if angle is within threshold of limit
        """
        return abs(angle - limit) < threshold
    
    @staticmethod
    def is_at_limit(angle: float, 
                   limit: float, 
                   threshold: float = np.deg2rad(5.0)) -> bool:
        """
        Check if angle is at a rotation limit.
        
        Args:
            angle: Current angle
            limit: Limit to check against
            threshold: Distance threshold for "at limit"
            
        Returns:
            True if angle is within threshold of limit
        """
        return abs(angle - limit) < threshold


class PositionUtils:
    """Utilities for position validation and comparison."""
    
    @staticmethod
    def at_position(position1: List[float], 
                   position2: List[float], 
                   tolerance: float = 0.05) -> bool:
        """
        Check if two joint positions are equivalent within tolerance.
        
        Args:
            position1: First position array
            position2: Second position array
            tolerance: Maximum difference per joint
            
        Returns:
            True if positions are within tolerance
        """
        if len(position1) != len(position2):
            return False
            
        for pos1, pos2 in zip(position1, position2):
            if abs(pos1 - pos2) > tolerance:
                return False
        return True
    
    @staticmethod
    def at_home_position(current_pos: List[float], 
                        home_pos: List[float], 
                        tolerance: float = LuxoConstants.HOME_POSITION_TOLERANCE,
                        ignore_base: bool = True) -> bool:
        """
        Check if robot is at a home position, optionally ignoring base joint.
        
        Args:
            current_pos: Current joint positions
            home_pos: Target home position
            tolerance: Position tolerance
            ignore_base: If True, ignore base joint (index 0) comparison
            
        Returns:
            True if at home position within tolerance
        """
        start_idx = 1 if ignore_base else 0
        
        for i in range(start_idx, min(len(current_pos), len(home_pos))):
            if abs(current_pos[i] - home_pos[i]) > tolerance:
                return False
        return True
    
    @staticmethod
    def calculate_position_difference(pos1: List[float], 
                                    pos2: List[float]) -> List[float]:
        """
        Calculate element-wise difference between two positions.
        
        Args:
            pos1: First position
            pos2: Second position
            
        Returns:
            List of differences [pos1[i] - pos2[i] for each i]
        """
        min_len = min(len(pos1), len(pos2))
        return [pos1[i] - pos2[i] for i in range(min_len)]
    
    @staticmethod
    def validate_joint_limits(position: List[float], 
                             joint_limits: Optional[List[Tuple[float, float]]] = None) -> List[float]:
        """
        Validate and clamp joint positions to limits.
        
        Args:
            position: Joint positions to validate
            joint_limits: List of (min, max) tuples for each joint
            
        Returns:
            Clamped position array
        """
        if joint_limits is None:
            # Default limits - adjust as needed for your robot
            joint_limits = [
                (LuxoConstants.BASE_MIN_LIMIT, LuxoConstants.BASE_MAX_LIMIT),
                (-np.pi, np.pi),    # Shoulder
                (-np.pi, np.pi),    # Elbow  
                (-np.pi, np.pi),    # Wrist
                (-np.pi, np.pi)     # Hand
            ]
        
        validated_pos = position.copy()
        for i, (pos_val, (min_limit, max_limit)) in enumerate(zip(position, joint_limits)):
            if i < len(joint_limits):
                validated_pos[i] = np.clip(pos_val, min_limit, max_limit)
        
        return validated_pos
    
    @staticmethod
    def add_position_variation(base_position: List[float], 
                              variation_range: float = 0.05,
                              exclude_indices: Optional[List[int]] = None) -> List[float]:
        """
        Add random variation to a position.
        
        Args:
            base_position: Base position to vary
            variation_range: Maximum variation per joint
            exclude_indices: Joint indices to exclude from variation
            
        Returns:
            Position with random variation added
        """
        if exclude_indices is None:
            exclude_indices = []
            
        varied_position = base_position.copy()
        for i in range(len(base_position)):
            if i not in exclude_indices:
                variation = random.uniform(-variation_range, variation_range)
                varied_position[i] += variation
                
        return varied_position
    
    @staticmethod
    def is_position_in_unsafe_zone(position: List[float], 
                                  unsafe_zones: List[Tuple[List[float], float]]) -> bool:
        """
        Check if a position is in any recorded unsafe zones.
        
        Args:
            position: Position to check
            unsafe_zones: List of (unsafe_position, radius) tuples
            
        Returns:
            True if position is in any unsafe zone
        """
        for unsafe_pos, radius in unsafe_zones:
            # Calculate Euclidean distance in joint space
            sum_squared = sum((p1 - p2) ** 2 for p1, p2 in zip(position, unsafe_pos))
            distance = math.sqrt(sum_squared)
            
            if distance < radius:
                return True
                
        return False


class ROSUtils:
    """Utilities for ROS message creation and time handling."""
    
    @staticmethod
    def create_joint_state_msg(node: Node,
                              joint_names: List[str],
                              positions: List[float],
                              velocities: Optional[List[float]] = None,
                              efforts: Optional[List[float]] = None) -> JointState:
        """
        Create a JointState message.
        
        Args:
            node: ROS node for timestamp
            joint_names: Names of joints
            positions: Joint positions
            velocities: Joint velocities (optional)
            efforts: Joint efforts (optional)
            
        Returns:
            Populated JointState message
        """
        msg = JointState()
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.name = joint_names
        msg.position = positions
        
        if velocities is not None:
            msg.velocity = velocities
        if efforts is not None:
            msg.effort = efforts
            
        return msg
    
    @staticmethod
    def create_string_msg(data: str) -> String:
        """
        Create a String message.
        
        Args:
            data: String data
            
        Returns:
            String message
        """
        msg = String()
        msg.data = data
        return msg
    
    @staticmethod
    def time_since(start_time: Time, current_time: Time) -> float:
        """
        Calculate time difference in seconds.
        
        Args:
            start_time: Start time
            current_time: Current time
            
        Returns:
            Time difference in seconds
        """
        return (current_time - start_time).nanoseconds / 1e9
    
    @staticmethod
    def is_timeout(start_time: Time, 
                  current_time: Time, 
                  timeout_duration: float) -> bool:
        """
        Check if a timeout has occurred.
        
        Args:
            start_time: Start time
            current_time: Current time
            timeout_duration: Timeout duration in seconds
            
        Returns:
            True if timeout has occurred
        """
        return ROSUtils.time_since(start_time, current_time) > timeout_duration


class SafetyUtils:
    """Utilities for safety calculations and collision handling."""
    
    @staticmethod
    def calculate_adjustment_factor(distance: float, 
                                  severity: str,
                                  soft_limit: float = LuxoConstants.DEFAULT_SOFT_LIMIT_DISTANCE,
                                  hard_limit: float = LuxoConstants.DEFAULT_HARD_LIMIT_DISTANCE) -> float:
        """
        Calculate collision adjustment factor based on distance and severity.
        
        Args:
            distance: Distance to obstacle
            severity: Collision severity ('safe', 'warning', 'danger')
            soft_limit: Soft collision limit distance
            hard_limit: Hard collision limit distance
            
        Returns:
            Adjustment factor between 0.0 and 1.0
        """
        if severity == 'danger':
            return 1.0
            
        if distance <= hard_limit:
            return 1.0
        elif distance <= soft_limit:
            # Linear interpolation between 0.0 and 1.0
            range_fraction = (soft_limit - distance) / (soft_limit - hard_limit)
            return max(0.1, min(1.0, range_fraction))
        
        return 0.0
    
    @staticmethod
    def calculate_escape_magnitude(consecutive_count: int, 
                                 escape_attempts: int,
                                 base_magnitude: float = 1.0) -> float:
        """
        Calculate escape movement magnitude based on persistence.
        
        Args:
            consecutive_count: Number of consecutive collision detections
            escape_attempts: Number of escape attempts made
            base_magnitude: Base magnitude for calculations
            
        Returns:
            Escape magnitude multiplier
        """
        if consecutive_count > 8:
            magnitude = 2.5
        elif consecutive_count > 5:
            magnitude = 2.0
        else:
            magnitude = base_magnitude
            
        # Add variation to avoid repeating patterns
        variation = random.uniform(0.9, 1.1)
        magnitude *= variation
        
        # Increase with escape attempts
        magnitude = min(3.0, magnitude + (escape_attempts * 0.3))
        
        return magnitude
    
    @staticmethod
    def select_collision_acceleration(severity: str, 
                                    emergency: bool = False,
                                    consecutive_count: int = 0) -> float:
        """
        Select appropriate acceleration for collision response.
        
        Args:
            severity: Collision severity
            emergency: If this is an emergency response
            consecutive_count: Number of consecutive collisions
            
        Returns:
            Acceleration value
        """
        if emergency or severity == 'danger':
            acceleration = 22.5  # Maximum acceleration
        elif severity == 'warning':
            acceleration = 16.0  # Higher acceleration for warnings
        else:
            acceleration = 12.0  # Default acceleration
            
        # Increase for persistent collisions (capped at maximum)
        if consecutive_count > 5:
            acceleration = min(22.5, acceleration + (consecutive_count - 5) * 1.0)
            
        return acceleration


class StateUtils:
    """Utilities for state management and transitions."""
    
    @staticmethod
    def should_allow_transition(from_state: str, to_state: str) -> bool:
        """
        Check if a state transition should be allowed.
        
        Args:
            from_state: Current state name
            to_state: Desired state name
            
        Returns:
            True if transition is allowed
        """
        # Define forbidden transitions
        forbidden_transitions = {
            'RETURNING_HOME': ['IDLE', 'ANIMATING'],  # Don't interrupt home return
            'ESCAPE_MODE': ['IDLE'],  # Only exit escape mode after completion
        }
        
        if from_state in forbidden_transitions:
            return to_state not in forbidden_transitions[from_state]
            
        return True
    
    @staticmethod
    def get_state_priority(state: str) -> int:
        """
        Get the priority of a state for transition decisions.
        Higher numbers indicate higher priority.
        
        Args:
            state: State name
            
        Returns:
            Priority value (0-100)
        """
        state_priorities = {
            'ERROR': 100,           # Highest priority
            'SHUTDOWN': 95,
            'ESCAPE_MODE': 90,
            'RETURNING_HOME': 85,
            'COLLISION_AVOIDING': 80,
            'PETTING': 70,
            'USER_CONTROL': 60,
            'EMOTION_REACTING': 50,
            'ANIMATING': 40,
            'IDLE': 30,
            'INITIALIZING': 20,     # Lowest priority
        }
        
        return state_priorities.get(state, 0)


class MathUtils:
    """General mathematical utilities."""
    
    @staticmethod
    def lerp(start: float, end: float, factor: float) -> float:
        """
        Linear interpolation between two values.
        
        Args:
            start: Start value
            end: End value
            factor: Interpolation factor (0.0 to 1.0)
            
        Returns:
            Interpolated value
        """
        return start + (end - start) * np.clip(factor, 0.0, 1.0)
    
    @staticmethod
    def blend_positions(pos1: List[float], 
                       pos2: List[float], 
                       factor: float) -> List[float]:
        """
        Blend between two joint positions.
        
        Args:
            pos1: First position
            pos2: Second position
            factor: Blend factor (0.0 = pos1, 1.0 = pos2)
            
        Returns:
            Blended position
        """
        min_len = min(len(pos1), len(pos2))
        return [MathUtils.lerp(pos1[i], pos2[i], factor) for i in range(min_len)]
    
    @staticmethod
    def euclidean_distance(pos1: List[float], pos2: List[float]) -> float:
        """
        Calculate Euclidean distance between two positions.
        
        Args:
            pos1: First position
            pos2: Second position
            
        Returns:
            Euclidean distance
        """
        min_len = min(len(pos1), len(pos2))
        sum_squared = sum((pos1[i] - pos2[i]) ** 2 for i in range(min_len))
        return math.sqrt(sum_squared)
    
    @staticmethod
    def random_in_range(min_val: float, max_val: float) -> float:
        """
        Generate random value in range.
        
        Args:
            min_val: Minimum value
            max_val: Maximum value
            
        Returns:
            Random value in range
        """
        return random.uniform(min_val, max_val)


# Export all utility classes for easy importing
__all__ = [
    'LuxoConstants',
    'AngleUtils', 
    'PositionUtils',
    'ROSUtils',
    'SafetyUtils', 
    'StateUtils',
    'MathUtils'
]