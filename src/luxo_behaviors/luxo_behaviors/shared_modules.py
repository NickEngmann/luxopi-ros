#!/usr/bin/env python3
#shared_modules.py
"""
Shared utility modules for Luxo behaviors.
Contains common functions used across collision, vision, idle, and other nodes.
"""

import math
import numpy as np
import random
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
            # Note: completion field needs to be added to the service definition
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
    """Utilities for working with ROS time."""
    
    @staticmethod
    def get_elapsed_time(node, start_time) -> float:
        """Get elapsed time in seconds from a ROS time."""
        current_time = node.get_clock().now()
        return (current_time - start_time).nanoseconds / 1e9
    
    @staticmethod
    def has_elapsed(node, start_time, duration: float) -> bool:
        """Check if a duration has elapsed since start_time."""
        return TimeUtils.get_elapsed_time(node, start_time) >= duration


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
        'yawning_stretch', 'shoulder_shimmy', 'look_around_casual'
    ]
    
    DEFAULT_PETTING_ANIMATIONS = [
        'folded_wiggle'
    ]
    
    def __init__(self):
        self.idle_animations = self.DEFAULT_IDLE_ANIMATIONS.copy()
        self.petting_animations = self.DEFAULT_PETTING_ANIMATIONS.copy()
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