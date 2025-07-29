#!/usr/bin/env python3
#shared_utils.py
"""
Shared utility modules for Luxo behaviors.
Contains common functions used across collision, vision, idle, and other nodes.
"""

import math
import numpy as np
import random
import time
from typing import List, Tuple, Optional, Dict, Any
from std_msgs.msg import String
from sensor_msgs.msg import JointState


class PositionUtils:
    """Utilities for working with joint positions."""
    
    @staticmethod
    def normalize_angle(angle: float) -> float:
        """Normalize angle to [-pi, pi]."""
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle
    
    @staticmethod
    def calculate_position_distance(pos1: List[float], pos2: List[float]) -> float:
        """Calculate the Euclidean distance between two joint positions."""
        if not pos1 or not pos2 or len(pos1) != len(pos2):
            return float('inf')
        
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(pos1, pos2)))
    
    @staticmethod
    def at_position(position1: List[float], position2: List[float], 
                   tolerance: float = 0.05) -> bool:
        """Check if two positions are the same within tolerance."""
        if len(position1) != len(position2):
            return False
            
        for i, (pos1, pos2) in enumerate(zip(position1, position2)):
            if abs(pos1 - pos2) > tolerance:
                return False
        return True
    
    @staticmethod
    def at_home_position(current_pos: List[float], home_pos: List[float], 
                        tolerance: float, ignore_base: bool = True) -> bool:
        """Check if robot is at a home position, optionally ignoring base joint."""
        if ignore_base:
            # Compare all joints except base (index 0)
            for i in range(1, min(len(current_pos), len(home_pos))):
                if abs(current_pos[i] - home_pos[i]) > tolerance:
                    return False
            return True
        else:
            return PositionUtils.at_position(current_pos, home_pos, tolerance)
    
    @staticmethod
    def add_position_noise(position: List[float], noise_range: float = 0.05,
                          exclude_indices: Optional[List[int]] = None) -> List[float]:
        """Add random noise to joint positions."""
        if exclude_indices is None:
            exclude_indices = []
            
        noisy_position = []
        for i, pos in enumerate(position):
            if i in exclude_indices:
                noisy_position.append(pos)
            else:
                noisy_position.append(pos + random.uniform(-noise_range, noise_range))
        
        return noisy_position
    
    @staticmethod
    def clip_to_limits(position: List[float], min_limits: List[float], 
                      max_limits: List[float]) -> List[float]:
        """Clip joint positions to their limits."""
        clipped = []
        for i, pos in enumerate(position):
            if i < len(min_limits) and i < len(max_limits):
                clipped.append(np.clip(pos, min_limits[i], max_limits[i]))
            else:
                clipped.append(pos)
        return clipped
    
    @staticmethod
    def interpolate_positions(start: List[float], end: List[float], 
                            factor: float) -> List[float]:
        """Linearly interpolate between two positions."""
        if len(start) != len(end):
            return start
        
        return [s + (e - s) * factor for s, e in zip(start, end)]
    
    @staticmethod
    def get_position_velocity(pos1: List[float], pos2: List[float], 
                            time_delta: float) -> List[float]:
        """Calculate velocity between two positions given time delta."""
        if len(pos1) != len(pos2) or time_delta <= 0:
            return [0.0] * len(pos1)
        
        return [(p2 - p1) / time_delta for p1, p2 in zip(pos1, pos2)]


class StateUtils:
    """Utilities for working with global state management."""
    
    @staticmethod
    def request_state_transition(node, requested_state, priority: int = 50, force: bool = False, completion: bool = False):
        """Request a state transition from the global state manager."""
        try:
            from luxo_interfaces.srv import RequestStateTransition
            
            # Create service client if it doesn't exist
            if not hasattr(node, '_state_client'):
                node._state_client = node.create_client(
                    RequestStateTransition,
                    '/luxo/request_state_transition'
                )
            
            if not node._state_client.wait_for_service(timeout_sec=1.0):
                node.get_logger().warn("State manager service not available")
                return False
            
            request = RequestStateTransition.Request()
            request.requested_state = requested_state.name
            request.requesting_node = node.get_name()
            request.priority = priority
            request.force = force
            if hasattr(request, 'completion'):
                request.completion = completion
            
            future = node._state_client.call_async(request)
            # Don't wait for response to avoid blocking
            
            return True
        except Exception as e:
            node.get_logger().error(f"Error requesting state transition: {e}")
            return False
    
    @staticmethod
    def is_in_state(node, *states):
        """Check if node is in any of the given states."""
        # First check if node has a current_state attribute directly
        if hasattr(node, 'current_state'):
            # Check if we need to use a lock (for thread safety)
            if hasattr(node, 'state_lock'):
                with node.state_lock:
                    return node.current_state in states
            else:
                return node.current_state in states
        # If no current_state attribute, check if there's a get_current_state method
        elif hasattr(node, 'get_current_state'):
            return node.get_current_state() in states
        else:
            node.get_logger().warn("No state information available")
            return False
    
    @staticmethod
    def get_current_state(node):
        """Get current state from node."""
        # First check for current_state attribute directly
        if hasattr(node, 'current_state'):
            # Check if we need to use a lock (for thread safety)
            if hasattr(node, 'state_lock'):
                with node.state_lock:
                    return node.current_state
            else:
                return node.current_state
        # If no current_state attribute, check for get_current_state method
        elif hasattr(node, 'get_current_state'):
            return node.get_current_state()
        else:
            return None


class MovementSourcePublisher:
    """Handles publishing movement source information for DEMA coordination."""
    
    @staticmethod
    def publish_movement_source(node, source: str, current_joints: List[float],
                              joint_states_publisher=None, 
                              movement_source_publisher=None):
        """Publish movement source information for DEMA coordination."""
        try:
            # Check if node has movement source integration enabled
            if not hasattr(node, 'enable_movement_source_integration') or \
               not node.enable_movement_source_integration:
                return
                
            node.get_logger().debug(f"Publishing movement source: {source}")
            
            # Try with joint_states style encoding for hardware interface
            if joint_states_publisher:
                msg = JointState()
                msg.header.stamp = node.get_clock().now().to_msg()
                msg.name = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
                msg.position = current_joints.copy()
                
                # Encode movement source in velocity field
                source_code = MovementSourcePublisher.get_source_code(source)
                msg.velocity = [float(source_code)]
                joint_states_publisher.publish(msg)
            
            # Also try with the String message approach for compatibility
            if movement_source_publisher:
                str_msg = String()
                str_msg.data = source
                movement_source_publisher.publish(str_msg)
                
        except Exception as e:
            node.get_logger().error(f"Error publishing movement source: {e}")
    
    @staticmethod
    def get_source_code(source: str) -> int:
        """Convert movement source string to numeric code."""
        source_codes = {
            "idle": 0,
            "animation": 1,
            "collision": 2,
            "user": 3,
            "voice": 4,
            "petting": 5,
            "escape": 6,
            "home": 7
        }
        return source_codes.get(source.lower(), 0)


class CollisionStatusTracker:
    """Tracks collision status for different directions."""
    
    def __init__(self):
        self.status = {
            'front': {'active': False, 'distance': float('inf'), 
                     'severity': 'safe', 'consecutive_count': 0},
            'left': {'active': False, 'distance': float('inf'), 
                    'severity': 'safe', 'consecutive_count': 0},
            'right': {'active': False, 'distance': float('inf'), 
                     'severity': 'safe', 'consecutive_count': 0}
        }
    
    def update_status(self, direction: str, active: bool = None, 
                     distance: float = None, severity: str = None):
        """Update collision status for a direction."""
        if direction not in self.status:
            return
            
        if active is not None:
            self.status[direction]['active'] = active
        if distance is not None:
            self.status[direction]['distance'] = distance
        if severity is not None:
            self.status[direction]['severity'] = severity
    
    def increment_count(self, direction: str):
        """Increment consecutive collision count."""
        if direction in self.status:
            self.status[direction]['consecutive_count'] += 1
    
    def reset_count(self, direction: str):
        """Reset consecutive collision count."""
        if direction in self.status:
            self.status[direction]['consecutive_count'] = 0
    
    def reset_all_counts(self):
        """Reset all consecutive collision counts."""
        for direction in self.status:
            self.status[direction]['consecutive_count'] = 0
    
    def any_active(self) -> bool:
        """Check if any collision is active."""
        return any(status['active'] for status in self.status.values())
    
    def get_most_severe(self) -> Tuple[Optional[str], Optional[str]]:
        """Get the direction with most severe collision."""
        severities = ['danger', 'warning', 'safe']
        
        for severity in severities:
            for direction, status in self.status.items():
                if status['active'] and status['severity'] == severity:
                    return direction, severity
        
        return None, None


class TimeUtils:
    """Utilities for working with ROS time and timing operations."""
    
    @staticmethod
    def get_elapsed_time(node, start_time) -> float:
        """Get elapsed time in seconds from a ROS time."""
        current_time = node.get_clock().now()
        return (current_time - start_time).nanoseconds / 1e9
    
    @staticmethod
    def has_elapsed(node, start_time, duration: float) -> bool:
        """Check if a duration has elapsed since start_time."""
        return TimeUtils.get_elapsed_time(node, start_time) >= duration
    
    @staticmethod
    def get_time_since(node, timestamp) -> float:
        """Get time elapsed since a timestamp in seconds."""
        if timestamp is None:
            return float('inf')
        current_time = node.get_clock().now()
        return (current_time - timestamp).nanoseconds / 1e9
    
    @staticmethod
    def create_rate_limiter(node, rate_hz: float):
        """Create a rate limiter that tracks time between calls."""
        class RateLimiter:
            def __init__(self, node, rate_hz):
                self.node = node
                self.min_interval = 1.0 / rate_hz
                self.last_time = None
            
            def ready(self) -> bool:
                """Check if enough time has passed for next call."""
                current_time = self.node.get_clock().now()
                if self.last_time is None:
                    return True
                elapsed = (current_time - self.last_time).nanoseconds / 1e9
                return elapsed >= self.min_interval
            
            def mark(self):
                """Mark that an action was taken."""
                self.last_time = self.node.get_clock().now()
        
        return RateLimiter(node, rate_hz)
    
    @staticmethod
    def exponential_backoff(attempt: int, base_delay: float = 1.0, 
                          max_delay: float = 60.0) -> float:
        """Calculate exponential backoff delay."""
        delay = base_delay * (2 ** attempt)
        return min(delay, max_delay)


class SafetyLimits:
    """Manages joint safety limits and soft/hard boundaries."""
    
    def __init__(self, base_min: float = -np.pi, base_max: float = np.pi,
                 soft_margin: float = np.deg2rad(10.0)):
        self.base_min_limit = base_min
        self.base_max_limit = base_max
        self.base_soft_min = base_min + soft_margin
        self.base_soft_max = base_max - soft_margin
        
        # Default joint limits for other joints (shoulder, elbow, wrist, hand)
        self.joint_limits = {
            'shoulder': {'min': -1.57, 'max': 1.57},
            'elbow': {'min': -2.0, 'max': 2.0},
            'wrist': {'min': -2.0, 'max': 2.0},
            'hand': {'min': -3.14, 'max': 3.14}
        }
    
    def is_near_base_limit(self, angle: float, threshold: float = np.deg2rad(20.0)) -> str:
        """Check if base angle is near a limit. Returns 'min', 'max', or 'none'."""
        if abs(angle - self.base_min_limit) < threshold:
            return 'min'
        elif abs(angle - self.base_max_limit) < threshold:
            return 'max'
        return 'none'
    
    def is_at_base_limit(self, angle: float, threshold: float = np.deg2rad(5.0)) -> str:
        """Check if base angle is at a limit. Returns 'min', 'max', or 'none'."""
        if abs(angle - self.base_min_limit) < threshold:
            return 'min'
        elif abs(angle - self.base_max_limit) < threshold:
            return 'max'
        return 'none'
    
    def clamp_base_angle(self, angle: float) -> float:
        """Clamp base angle to limits."""
        return np.clip(angle, self.base_min_limit, self.base_max_limit)
    
    def get_safe_base_direction(self, current_angle: float, 
                              preferred_direction: int) -> int:
        """Get safe rotation direction considering limits."""
        at_min = self.is_at_base_limit(current_angle) == 'min'
        at_max = self.is_at_base_limit(current_angle) == 'max'
        
        if at_min and preferred_direction < 0:
            return 1  # Force positive direction
        elif at_max and preferred_direction > 0:
            return -1  # Force negative direction
        else:
            return preferred_direction


class AnimationTracker:
    """Tracks animation state and progress."""
    
    def __init__(self):
        self.current_animation_name: Optional[str] = None
        self.animation_allow_interruption: bool = True
        self.animation_progress: float = 0.0
        self.animation_preempted: bool = False
        self.animation_preemption_time = None
    
    def set_active(self, animation_name: str, allow_interruption: bool = True):
        """Set the currently active animation."""
        self.current_animation_name = animation_name
        self.animation_allow_interruption = allow_interruption
        self.animation_progress = 0.0
        self.animation_preempted = False
    
    def clear(self):
        """Clear the active animation tracking."""
        self.current_animation_name = None
        self.animation_progress = 0.0
        self.animation_preempted = False
    
    def update_progress(self, progress: float):
        """Update animation progress (0.0 to 1.0)."""
        self.animation_progress = max(0.0, min(1.0, progress))
    
    def should_preempt(self, severity: str = "warning") -> bool:
        """Determine if current animation should be preempted."""
        if not self.current_animation_name:
            return False
        
        if not self.animation_allow_interruption:
            return False
        
        # Only preempt for danger, not warnings
        if severity != "danger":
            return False
        
        return True


class IdleAnimationConfig:
    """Configuration for idle animations."""
    
    DEFAULT_IDLE_ANIMATIONS = [
        'gentle_sway', 'curious_exploration', 'breathing', 
        'attentive_listening', 'playful_bob', 'scanning_watch',
        'settling_adjust', 'dreamy_drift', 'neck_stretch',
        'yawning_stretch', 'shoulder_shimmy', 'look_around_casual',
        'pondering', 'tail_wag', 'head_bobbing', 'contented_sigh'
    ]
    
    DEFAULT_PETTING_ANIMATIONS = [
        'folded_wiggle', 'bouncy_wiggle', 'sleepy_melt'
    ]

    DEFAULT_SLEEPING_ANIMATIONS = [
        'sleep'
    ]
    
    def __init__(self):
        self.idle_animations = self.DEFAULT_IDLE_ANIMATIONS.copy()
        self.petting_animations = self.DEFAULT_PETTING_ANIMATIONS.copy()
        self.sleeping_animations = self.DEFAULT_SLEEPING_ANIMATIONS.copy()
        self.min_idle_time_before_animation = 5.0  # seconds
        self.idle_animation_interval_min = 10.0
        self.idle_animation_interval_max = 60.0
        self.petting_animation_cooldown = 8.0  # seconds
        
    def get_random_idle_animation(self, exclude: Optional[str] = None) -> str:
        """Get a random idle animation, optionally excluding the last one."""
        available = [a for a in self.idle_animations if a != exclude]
        if not available:
            available = self.idle_animations
        return random.choice(available)
    
    def get_random_interval(self) -> float:
        """Get a random interval for next idle animation."""
        return random.uniform(self.idle_animation_interval_min, 
                            self.idle_animation_interval_max)


class CollisionMath:
    """Mathematical utilities for collision detection and response."""
    
    @staticmethod
    def calculate_severity(distance: float, danger_threshold: float = 7.0, 
                         warning_threshold: float = 15.0) -> str:
        """Calculate collision severity based on distance."""
        if distance < danger_threshold:
            return 'danger'
        elif distance < warning_threshold:
            return 'warning'
        else:
            return 'safe'
    
    @staticmethod
    def calculate_avoidance_magnitude(severity: str, consecutive_count: int,
                                    emergency: bool = False) -> float:
        """Calculate how much to adjust position based on collision severity."""
        base_magnitude = 0.8
        
        if consecutive_count > 8:
            magnitude = 2.5
        elif consecutive_count > 5:
            magnitude = 2.0
        elif emergency or severity == 'danger':
            magnitude = 1.5
        else:
            magnitude = base_magnitude
        
        # Add variation to avoid repeating patterns
        variation = random.uniform(0.9, 1.1)
        return magnitude * variation
    
    @staticmethod
    def calculate_acceleration(severity: str, consecutive_count: int,
                             base_acceleration: float = 12.5) -> float:
        """Calculate joint acceleration based on urgency."""
        if severity == 'danger':
            acceleration = 17.5
        else:
            acceleration = base_acceleration
        
        # Increase for persistent collisions
        if consecutive_count > 5:
            acceleration = min(22.5, acceleration + (consecutive_count - 5) * 1.0)
        
        return acceleration
    
    @staticmethod
    def calculate_escape_rotation(direction: str, base_rotation: float = 0.3,
                                escape_multiplier: float = 2.0) -> float:
        """Calculate rotation amount for escape maneuvers."""
        if direction == 'left':
            return base_rotation * escape_multiplier  # Rotate right
        elif direction == 'right':
            return -base_rotation * escape_multiplier  # Rotate left
        else:
            # For front collision, alternate direction
            return random.choice([-1, 1]) * base_rotation * escape_multiplier
    
    @staticmethod
    def check_path_blocked(collision_status: Dict[str, Dict]) -> Tuple[bool, List[str]]:
        """Check if path is blocked and return blocked directions."""
        blocked_directions = []
        
        for direction, status in collision_status.items():
            if status['active'] and status['severity'] == 'danger':
                blocked_directions.append(direction)
        
        # Path is blocked if 2+ directions have danger collisions
        is_blocked = len(blocked_directions) >= 2
        return is_blocked, blocked_directions
    
    @staticmethod
    def calculate_safe_direction(blocked_directions: List[str], 
                               current_base: float) -> float:
        """Calculate safe rotation direction when path is blocked."""
        if 'left' in blocked_directions and 'right' not in blocked_directions:
            # Left blocked, go right
            return current_base + np.deg2rad(45)
        elif 'right' in blocked_directions and 'left' not in blocked_directions:
            # Right blocked, go left
            return current_base - np.deg2rad(45)
        else:
            # Both sides blocked or front only, try 180 turn
            return current_base + np.pi


class MovementValidator:
    """Validates and adjusts movements for safety."""
    
    @staticmethod
    def validate_position(position: List[float], limits: SafetyLimits) -> List[float]:
        """Validate and clamp a position to safety limits."""
        validated = position.copy()
        
        # Validate base
        if len(validated) > 0:
            validated[0] = limits.clamp_base_angle(validated[0])
        
        # Validate other joints using limit dictionary
        joint_names = ['shoulder', 'elbow', 'wrist', 'hand']
        for i, joint_name in enumerate(joint_names, 1):
            if i < len(validated) and joint_name in limits.joint_limits:
                joint_limit = limits.joint_limits[joint_name]
                validated[i] = np.clip(validated[i], joint_limit['min'], joint_limit['max'])
        
        return validated
    
    @staticmethod
    def check_movement_safety(current: List[float], target: List[float],
                            collision_status: Dict[str, Dict]) -> Tuple[bool, str]:
        """Check if movement from current to target is safe."""
        # Check for active collisions
        for direction, status in collision_status.items():
            if not status['active']:
                continue
            
            if status['severity'] == 'danger':
                # Check if movement would worsen collision
                if direction == 'front' and len(current) > 1 and len(target) > 1:
                    if target[1] < current[1]:  # Shoulder moving forward
                        return False, f"Movement blocked by {direction} collision"
                elif direction == 'left' and len(current) > 0 and len(target) > 0:
                    if target[0] < current[0]:  # Base rotating left
                        return False, f"Movement blocked by {direction} collision"
                elif direction == 'right' and len(current) > 0 and len(target) > 0:
                    if target[0] > current[0]:  # Base rotating right
                        return False, f"Movement blocked by {direction} collision"
        
        return True, "Movement safe"