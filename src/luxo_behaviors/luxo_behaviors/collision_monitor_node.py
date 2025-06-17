#!/usr/bin/env python3
"""
CollisionMonitorNode - Pure collision detection and immediate safety responses.

This node handles:
- Collision sensor data processing and status tracking
- Immediate emergency avoidance maneuvers
- Escape mode logic for persistent collisions
- Safety limit calculations and validation
- Real-time collision status publishing

Author: Generated from collision_avoidance.py refactor
"""

import random
import threading
import math
from typing import Dict, List, Optional, Tuple
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.time import Time

# ROS message types
from std_msgs.msg import String, Bool, Float32, Int32
from sensor_msgs.msg import JointState
from geometry_msgs.msg import Vector3
from luxo_interfaces.msg import (
    CollisionStatus, CollisionDetails, EmergencyAction, 
    PositionRequest, ActivityUpdate
)

# Import shared utilities
from luxo_behaviors.shared_utilities import (
    LuxoConstants, 
    SafetyUtils,
    AngleUtils, 
    PositionUtils, 
    ROSUtils,
    MathUtils
)


class CollisionSeverity(Enum):
    """Collision severity levels."""
    SAFE = "safe"
    WARNING = "warning" 
    DANGER = "danger"


class CollisionDirection(Enum):
    """Collision detection directions."""
    FRONT = "front"
    LEFT = "left"
    RIGHT = "right"


class EscapeMode(Enum):
    """Escape mode states."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    ANIMATION_SAFE = "animation_safe"


class CollisionMonitorNode(Node):
    """
    ROS2 node responsible for collision detection and immediate safety responses.
    """
    
    def __init__(self):
        super().__init__('collision_monitor_node')
        
        # Declare parameters
        self._declare_parameters()
        
        # Load parameters
        self._load_parameters()
        
        # Initialize state variables
        self._initialize_state()
        
        # Create publishers
        self._create_publishers()
        
        # Create subscribers
        self._create_subscribers()
        
        # Create timers
        self._create_timers()
        
        # Thread locks for state protection
        self._collision_lock = threading.Lock()
        self._escape_lock = threading.Lock()
        
        self.get_logger().info("CollisionMonitorNode initialized successfully")
    
    def _declare_parameters(self):
        """Declare ROS parameters with default values."""
        # Basic collision parameters
        self.declare_parameter('enable_collision_avoidance', True)
        self.declare_parameter('soft_limit_distance', 15.0)
        self.declare_parameter('hard_limit_distance', 8.0)
        self.declare_parameter('max_deceleration', 22.5)
        
        # Collision tracking parameters
        self.declare_parameter('consecutive_collision_threshold', 5)
        self.declare_parameter('escape_threshold', 8)
        self.declare_parameter('max_escape_attempts', 3)
        self.declare_parameter('adjustment_cooldown', 1.0)
        
        # Escape mode parameters
        self.declare_parameter('escape_mode_duration', 5.0)
        self.declare_parameter('max_retreat_angle', 1.0)
        self.declare_parameter('side_avoidance_magnitude', 0.4)
        
        # Timeout parameters
        self.declare_parameter('collision_recovery_timeout', 2.0)
        self.declare_parameter('short_collision_timeout', 1.25)
        self.declare_parameter('extended_collision_timeout', 8.0)
        self.declare_parameter('max_collision_timeout', 15.0)
        
        # Base rotation limits
        self.declare_parameter('base_min_limit', -260.0)  # degrees
        self.declare_parameter('base_max_limit', 135.0)   # degrees
        self.declare_parameter('enable_base_wraparound', True)
    
    def _load_parameters(self):
        """Load parameters from ROS parameter server."""
        self.enable_collision_avoidance = self.get_parameter('enable_collision_avoidance').value
        self.soft_limit_distance = self.get_parameter('soft_limit_distance').value
        self.hard_limit_distance = self.get_parameter('hard_limit_distance').value
        self.max_deceleration = self.get_parameter('max_deceleration').value
        
        self.consecutive_collision_threshold = self.get_parameter('consecutive_collision_threshold').value
        self.escape_threshold = self.get_parameter('escape_threshold').value
        self.max_escape_attempts = self.get_parameter('max_escape_attempts').value
        self.adjustment_cooldown = self.get_parameter('adjustment_cooldown').value
        
        self.escape_mode_duration = self.get_parameter('escape_mode_duration').value
        self.max_retreat_angle = self.get_parameter('max_retreat_angle').value
        self.side_avoidance_magnitude = self.get_parameter('side_avoidance_magnitude').value
        
        self.collision_recovery_timeout = self.get_parameter('collision_recovery_timeout').value
        self.short_collision_timeout = self.get_parameter('short_collision_timeout').value
        self.extended_collision_timeout = self.get_parameter('extended_collision_timeout').value
        self.max_collision_timeout = self.get_parameter('max_collision_timeout').value
        
        # Convert base limits to radians
        self.base_min_limit = math.radians(self.get_parameter('base_min_limit').value)
        self.base_max_limit = math.radians(self.get_parameter('base_max_limit').value)
        self.enable_base_wraparound = self.get_parameter('enable_base_wraparound').value
        
        # Calculate soft limits
        self.base_soft_min = self.base_min_limit + LuxoConstants.BASE_SOFT_MIN_OFFSET
        self.base_soft_max = self.base_max_limit - LuxoConstants.BASE_SOFT_MAX_OFFSET
    
    def _initialize_state(self):
        """Initialize internal state variables."""
        # Current robot state
        self.current_joints: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.joint_velocities: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.robot_state: str = "IDLE"
        
        # Collision status tracking
        self.collision_status: Dict[str, Dict] = {
            'front': {
                'active': False, 
                'distance': float('inf'), 
                'severity': CollisionSeverity.SAFE.value,
                'consecutive_count': 0,
                'last_detection_time': self.get_clock().now()
            },
            'left': {
                'active': False, 
                'distance': float('inf'), 
                'severity': CollisionSeverity.SAFE.value,
                'consecutive_count': 0,
                'last_detection_time': self.get_clock().now()
            },
            'right': {
                'active': False, 
                'distance': float('inf'), 
                'severity': CollisionSeverity.SAFE.value,
                'consecutive_count': 0,
                'last_detection_time': self.get_clock().now()
            }
        }
        
        # Collision timing
        self.last_collision_time = self.get_clock().now()
        self.last_avoidance_direction: Optional[str] = None
        
        # Adjustment tracking
        self.adjustment_history: Dict[str, Dict] = {
            'front': {
                'last_time': self.get_clock().now(), 
                'last_position': None, 
                'adjustment_made': False
            },
            'left': {
                'last_time': self.get_clock().now(), 
                'last_position': None, 
                'adjustment_made': False
            },
            'right': {
                'last_time': self.get_clock().now(), 
                'last_position': None, 
                'adjustment_made': False
            }
        }
        
        # Escape mode state
        self.escape_mode = EscapeMode.INACTIVE
        self.escape_mode_start_time = self.get_clock().now()
        self.last_escape_direction: Optional[str] = None
        self.escape_attempts = 0
        self.unsafe_zones: List[Tuple[List[float], float]] = []
        
        # Persistent collision tracking
        self.persistent_head_collision_active = False
        self.persistent_head_collision_start = self.get_clock().now()
        self.persistent_head_collision_last_log = self.get_clock().now()
        
        # Animation coordination
        self.current_animation_name: Optional[str] = None
        self.animation_allow_interruption = True
        self.animation_progress = 0.0
        self.is_animating = False
        
        # External coordination flags
        self.voice_following_active = False
        self.petting_active = False
        self.returning_home = False
    
    def _create_publishers(self):
        """Create ROS publishers."""
        # Collision status for other nodes
        self.collision_status_pub = self.create_publisher(
            CollisionStatus,
            '/collision/status',
            10
        )
        
        # Emergency actions for safety coordinator
        self.emergency_action_pub = self.create_publisher(
            EmergencyAction,
            '/collision/emergency_action',
            10
        )
        
        # Collision activity updates
        self.collision_active_pub = self.create_publisher(
            Bool,
            '/collision/active',
            10
        )
        
        # Escape mode status
        self.escape_mode_pub = self.create_publisher(
            String,
            '/collision/escape_mode',
            10
        )
        
        # Position adjustment requests
        self.position_adjustment_pub = self.create_publisher(
            PositionRequest,
            '/collision/position_adjustment',
            10
        )
        
        # Activity updates
        self.activity_update_pub = self.create_publisher(
            ActivityUpdate,
            '/robot/activity_update',
            10
        )
    
    def _create_subscribers(self):
        """Create ROS subscribers."""
        # Collision sensor data
        self.collision_details_sub = self.create_subscription(
            CollisionDetails,
            '/collision_details',
            self.collision_details_callback,
            10
        )
        
        # Individual sensor subscriptions for compatibility
        self.front_distance_sub = self.create_subscription(
            Float32,
            '/collision/front_distance',
            lambda msg: self.distance_callback('front', msg.data),
            10
        )
        
        self.left_distance_sub = self.create_subscription(
            Float32,
            '/collision/left_distance', 
            lambda msg: self.distance_callback('left', msg.data),
            10
        )
        
        self.right_distance_sub = self.create_subscription(
            Float32,
            '/collision/right_distance',
            lambda msg: self.distance_callback('right', msg.data),
            10
        )
        
        # Proximity sensor (for front collision detection)
        self.proximity_sub = self.create_subscription(
            Int32,
            '/proximity_sensor',
            self.proximity_callback,
            10
        )
        
        # Robot joint states
        self.joint_states_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_states_callback,
            10
        )
        
        # Robot state updates
        self.robot_state_sub = self.create_subscription(
            String,
            '/robot/state',
            self.robot_state_callback,
            10
        )
        
        # Animation status for coordination
        self.animation_status_sub = self.create_subscription(
            String,
            '/animation/status',
            self.animation_status_callback,
            10
        )
        
        # Voice following status
        self.voice_status_sub = self.create_subscription(
            Bool,
            '/voice/active',
            self.voice_status_callback,
            10
        )
        
        # Petting status
        self.petting_status_sub = self.create_subscription(
            Bool,
            '/petting/active',
            self.petting_status_callback,
            10
        )
    
    def _create_timers(self):
        """Create periodic timers."""
        # Main collision monitoring timer (runs every 100ms for quick response)
        self.collision_timer = self.create_timer(0.1, self.collision_monitor_callback)
        
        # Status publishing timer (runs every 500ms)
        self.status_timer = self.create_timer(0.5, self.status_publish_callback)
    
    def collision_details_callback(self, msg: CollisionDetails):
        """Handle comprehensive collision details message."""
        try:
            # Update all collision information at once
            with self._collision_lock:
                # Front collision
                self._update_collision_status(
                    'front', 
                    msg.front_active, 
                    msg.front_distance, 
                    msg.front_severity
                )
                
                # Left collision
                self._update_collision_status(
                    'left',
                    msg.left_active,
                    msg.left_distance, 
                    msg.left_severity
                )
                
                # Right collision
                self._update_collision_status(
                    'right',
                    msg.right_active,
                    msg.right_distance,
                    msg.right_severity
                )
                
        except Exception as e:
            self.get_logger().error(f"Error in collision_details_callback: {e}")
    
    def distance_callback(self, direction: str, distance: float):
        """Handle individual distance sensor updates."""
        try:
            with self._collision_lock:
                self._update_distance(direction, distance)
                
        except Exception as e:
            self.get_logger().error(f"Error in {direction}_distance_callback: {e}")
    
    def proximity_callback(self, msg: Int32):
        """Handle proximity sensor data (front collision detection)."""
        try:
            # Convert proximity to approximate distance
            proximity = max(1, min(255, msg.data))
            distance = max(1.0, 30.0 * (1.0 - proximity / 255.0))
            
            with self._collision_lock:
                self._update_distance('front', distance, is_proximity=True)
                
        except Exception as e:
            self.get_logger().error(f"Error in proximity_callback: {e}")
    
    def joint_states_callback(self, msg: JointState):
        """Handle joint state updates."""
        if len(msg.position) >= 5:
            self.current_joints = list(msg.position[:5])
            
        if len(msg.velocity) >= 5:
            self.joint_velocities = list(msg.velocity[:5])
    
    def robot_state_callback(self, msg: String):
        """Handle robot state changes."""
        old_state = self.robot_state
        self.robot_state = msg.data
        
        if old_state != self.robot_state:
            self.get_logger().debug(f"Robot state changed: {old_state} -> {self.robot_state}")
            
            # Update coordination flags
            self.returning_home = (self.robot_state == "RETURNING_HOME")
            
            # If transitioning to escape mode, activate it
            if self.robot_state == "ESCAPE_MODE" and self.escape_mode == EscapeMode.INACTIVE:
                self._set_escape_mode(EscapeMode.ACTIVE)
    
    def animation_status_callback(self, msg: String):
        """Handle animation status updates."""
        if msg.data.startswith("started:"):
            animation_name = msg.data.split(":", 1)[1]
            self.current_animation_name = animation_name
            self.is_animating = True
            self.animation_progress = 0.0
            
        elif msg.data.startswith("progress:"):
            try:
                progress = float(msg.data.split(":", 1)[1])
                self.animation_progress = progress
            except ValueError:
                pass
                
        elif msg.data.startswith("completed:") or msg.data.startswith("aborted:"):
            self.current_animation_name = None
            self.is_animating = False
            self.animation_progress = 0.0
    
    def voice_status_callback(self, msg: Bool):
        """Handle voice following status."""
        self.voice_following_active = msg.data
    
    def petting_status_callback(self, msg: Bool):
        """Handle petting status."""
        self.petting_active = msg.data
    
    def collision_monitor_callback(self):
        """Main collision monitoring timer callback."""
        if not self.enable_collision_avoidance:
            return
            
        try:
            current_time = self.get_clock().now()
            
            with self._collision_lock:
                # Check for persistent head collision
                self._check_persistent_head_collision(current_time)
                
                # Check escape mode status
                self._update_escape_mode(current_time)
                
                # Process active collisions
                self._process_active_collisions(current_time)
                
                # Check for emergency situations
                self._check_emergency_conditions(current_time)
                
        except Exception as e:
            self.get_logger().error(f"Error in collision monitor: {e}")
    
    def status_publish_callback(self):
        """Publish collision status for other nodes."""
        try:
            with self._collision_lock:
                # Publish detailed collision status
                status_msg = CollisionStatus()
                status_msg.header.stamp = self.get_clock().now().to_msg()
                
                # Front collision
                status_msg.front_active = self.collision_status['front']['active']
                status_msg.front_distance = self.collision_status['front']['distance']
                status_msg.front_severity = self.collision_status['front']['severity']
                status_msg.front_consecutive_count = self.collision_status['front']['consecutive_count']
                
                # Left collision
                status_msg.left_active = self.collision_status['left']['active']
                status_msg.left_distance = self.collision_status['left']['distance']
                status_msg.left_severity = self.collision_status['left']['severity']
                status_msg.left_consecutive_count = self.collision_status['left']['consecutive_count']
                
                # Right collision
                status_msg.right_active = self.collision_status['right']['active']
                status_msg.right_distance = self.collision_status['right']['distance']
                status_msg.right_severity = self.collision_status['right']['severity']
                status_msg.right_consecutive_count = self.collision_status['right']['consecutive_count']
                
                # Overall status
                any_collision_active = any(
                    self.collision_status[direction]['active'] 
                    for direction in self.collision_status
                )
                status_msg.any_collision_active = any_collision_active
                status_msg.escape_mode_active = (self.escape_mode != EscapeMode.INACTIVE)
                status_msg.persistent_head_collision = self.persistent_head_collision_active
                
                self.collision_status_pub.publish(status_msg)
                
                # Publish simple collision active flag
                active_msg = Bool()
                active_msg.data = any_collision_active
                self.collision_active_pub.publish(active_msg)
                
                # Publish escape mode status
                escape_msg = String()
                escape_msg.data = self.escape_mode.value
                self.escape_mode_pub.publish(escape_msg)
                
        except Exception as e:
            self.get_logger().error(f"Error publishing collision status: {e}")
    
    def _update_collision_status(self, direction: str, is_active: bool, 
                                distance: float, severity: str):
        """Update collision status for a specific direction."""
        old_status = self.collision_status[direction].copy()
        current_time = self.get_clock().now()
        
        # Update basic status
        self.collision_status[direction]['active'] = is_active
        self.collision_status[direction]['distance'] = distance
        self.collision_status[direction]['severity'] = severity
        self.collision_status[direction]['last_detection_time'] = current_time
        
        # Handle state changes
        if not old_status['active'] and is_active:
            # Newly active collision
            self.collision_status[direction]['consecutive_count'] = 1
            self.last_collision_time = current_time
            self.get_logger().warn(f"{direction.capitalize()} collision activated: {distance:.1f}cm, {severity}")
            
            # Trigger immediate response for danger
            if severity == CollisionSeverity.DANGER.value:
                self._trigger_emergency_avoidance(direction, distance, severity)
                
        elif old_status['active'] and is_active:
            # Continuing collision - check for escalation
            time_since_adjustment = ROSUtils.time_since(
                self.adjustment_history[direction]['last_time'], current_time
            )
            
            if (not self.adjustment_history[direction]['adjustment_made'] or 
                time_since_adjustment > self.adjustment_cooldown):
                
                self.collision_status[direction]['consecutive_count'] += 1
                
                # Check for escape mode trigger
                if (self.collision_status[direction]['consecutive_count'] > self.escape_threshold and
                    self.escape_mode == EscapeMode.INACTIVE):
                    
                    self._activate_escape_mode(direction)
                    
        elif old_status['active'] and not is_active:
            # Collision cleared
            self.collision_status[direction]['consecutive_count'] = 0
            self.adjustment_history[direction]['adjustment_made'] = False
            self.get_logger().info(f"{direction.capitalize()} collision cleared")
            
            # Clear persistent head collision if front cleared
            if direction == 'front' and self.persistent_head_collision_active:
                self.persistent_head_collision_active = False
                self.get_logger().info("Persistent head collision cleared")
    
    def _update_distance(self, direction: str, value: float, is_proximity: bool = False):
        """Update distance information with fast reaction for dangerous values."""
        if is_proximity:
            # Convert proximity to distance
            proximity = max(1, min(255, value))
            distance = max(1.0, 30.0 * (1.0 - proximity / 255.0))
        else:
            distance = value
            
        old_distance = self.collision_status[direction]['distance']
        self.collision_status[direction]['distance'] = distance
        
        # Determine severity based on distance
        if distance <= self.hard_limit_distance:
            severity = CollisionSeverity.DANGER.value
        elif distance <= self.soft_limit_distance:
            severity = CollisionSeverity.WARNING.value
        else:
            severity = CollisionSeverity.SAFE.value
            
        self.collision_status[direction]['severity'] = severity
        
        # Fast reaction for dangerous decreasing distances
        current_time = self.get_clock().now()
        distance_decreasing = (old_distance == float('inf') or distance < old_distance)
        time_since_collision = ROSUtils.time_since(self.last_collision_time, current_time)
        
        if (distance <= self.hard_limit_distance and 
            distance_decreasing and
            time_since_collision > 0.25 and
            not self.adjustment_history[direction]['adjustment_made']):
            
            self.last_collision_time = current_time
            self.collision_status[direction]['active'] = True
            
            self._trigger_emergency_avoidance(direction, distance, severity)
    
    def _trigger_emergency_avoidance(self, direction: str, distance: float, severity: str):
        """Trigger immediate emergency avoidance."""
        try:
            self.get_logger().warn(f"EMERGENCY: {direction} collision at {distance:.1f}cm, severity: {severity}")
            
            # Calculate emergency position
            emergency_position = self._calculate_emergency_position(direction, distance)
            
            if emergency_position:
                # Create emergency action message
                emergency_msg = EmergencyAction()
                emergency_msg.header.stamp = self.get_clock().now().to_msg()
                emergency_msg.action_type = "collision_avoidance"
                emergency_msg.direction = direction
                emergency_msg.distance = distance
                emergency_msg.severity = severity
                emergency_msg.target_position = emergency_position
                emergency_msg.acceleration = SafetyUtils.select_collision_acceleration(
                    severity, emergency=True, 
                    consecutive_count=self.collision_status[direction]['consecutive_count']
                )
                emergency_msg.priority = 10  # Maximum priority
                
                self.emergency_action_pub.publish(emergency_msg)
                
                # Update adjustment tracking
                current_time = self.get_clock().now()
                self.adjustment_history[direction]['last_time'] = current_time
                self.adjustment_history[direction]['adjustment_made'] = True
                self.adjustment_history[direction]['last_position'] = self.current_joints.copy()
                
                # Publish activity update
                self._publish_activity_update("collision_avoidance")
                
        except Exception as e:
            self.get_logger().error(f"Error in emergency avoidance: {e}")
    
    def _calculate_emergency_position(self, direction: str, distance: float) -> Optional[List[float]]:
        """Calculate emergency avoidance position."""
        try:
            new_position = self.current_joints.copy()
            current_base = new_position[0]
            
            # Calculate escape magnitude
            consecutive_count = self.collision_status[direction]['consecutive_count']
            magnitude = SafetyUtils.calculate_escape_magnitude(
                consecutive_count, self.escape_attempts
            )
            
            # Check base rotation limits
            at_min_limit = AngleUtils.is_at_limit(current_base, self.base_min_limit)
            at_max_limit = AngleUtils.is_at_limit(current_base, self.base_max_limit)
            near_min_limit = AngleUtils.is_near_limit(current_base, self.base_min_limit)
            near_max_limit = AngleUtils.is_near_limit(current_base, self.base_max_limit)
            
            if direction == 'front':
                # Pull back shoulder and elbow
                new_position[1] -= 0.6 * magnitude  # Shoulder back
                new_position[2] += 0.4 * magnitude  # Elbow fold
                
                # Add rotation with wraparound support
                if at_max_limit and self.enable_base_wraparound:
                    new_position[0] = self.base_min_limit + 0.5
                    self.get_logger().warn("Emergency: wraparound from max to min limit")
                elif at_min_limit and self.enable_base_wraparound:
                    new_position[0] = self.base_max_limit - 0.5
                    self.get_logger().warn("Emergency: wraparound from min to max limit")
                elif near_max_limit:
                    new_position[0] -= 0.5 * magnitude  # Rotate toward min
                elif near_min_limit:
                    new_position[0] += 0.5 * magnitude  # Rotate toward max
                else:
                    # Alternate rotation direction based on consecutive count
                    if consecutive_count % 2 == 0:
                        new_position[0] += 0.5 * magnitude
                    else:
                        new_position[0] -= 0.5 * magnitude
                        
            elif direction == 'left':
                # Escape to the RIGHT
                if at_min_limit and self.enable_base_wraparound:
                    new_position[0] = self.base_max_limit - 0.3
                    self.get_logger().warn("Left collision: wraparound to max limit")
                else:
                    new_position[0] += 0.8 * magnitude
                new_position[1] += 0.3 * magnitude  # Pull back
                
            elif direction == 'right':
                # Escape to the LEFT
                if at_max_limit and self.enable_base_wraparound:
                    new_position[0] = self.base_min_limit + 0.3
                    self.get_logger().warn("Right collision: wraparound to min limit")
                else:
                    new_position[0] -= 0.8 * magnitude
                new_position[1] += 0.3 * magnitude  # Pull back
            
            # Ensure we stay within hard limits
            new_position[0] = AngleUtils.normalize_angle(new_position[0])
            new_position[0] = max(self.base_min_limit, min(self.base_max_limit, new_position[0]))
            
            return new_position
            
        except Exception as e:
            self.get_logger().error(f"Error calculating emergency position: {e}")
            return None
    
    def _check_persistent_head_collision(self, current_time: Time):
        """Check and handle persistent head (front) collisions."""
        if (self.collision_status['front']['active'] and 
            self.collision_status['front']['severity'] == CollisionSeverity.DANGER.value):
            
            if not self.persistent_head_collision_active:
                self.persistent_head_collision_start = current_time
                self.persistent_head_collision_active = True
                self.persistent_head_collision_last_log = current_time
                self.get_logger().warn("Started tracking persistent head collision")
            else:
                # Check duration
                duration = ROSUtils.time_since(self.persistent_head_collision_start, current_time)
                
                # Throttled logging
                time_since_log = ROSUtils.time_since(self.persistent_head_collision_last_log, current_time)
                if time_since_log > 2.0:
                    self.get_logger().warn(f"Persistent head collision ongoing for {duration:.1f}s")
                    self.persistent_head_collision_last_log = current_time
                
                # Check for escalation
                if duration > self.extended_collision_timeout:
                    self.get_logger().error(f"Persistent head collision for {duration:.1f}s - requesting home position")
                    self._request_emergency_home_position()
        else:
            if self.persistent_head_collision_active:
                self.get_logger().info("Persistent head collision cleared")
                self.persistent_head_collision_active = False
    
    def _activate_escape_mode(self, direction: str):
        """Activate escape mode for persistent collisions."""
        with self._escape_lock:
            self.escape_mode = EscapeMode.ANIMATION_SAFE if self.is_animating else EscapeMode.ACTIVE
            self.escape_mode_start_time = self.get_clock().now()
            self.last_escape_direction = direction
            self.escape_attempts = 0
            
            self.get_logger().warn(f"Activating escape mode ({self.escape_mode.value}) for {direction} collision")
            
            # Record current position as unsafe
            unsafe_radius = 0.4  # Joint space radius
            self.unsafe_zones.append((self.current_joints.copy(), unsafe_radius))
            
            # Execute escape maneuver
            self._execute_escape_maneuver(direction)
    
    def _execute_escape_maneuver(self, direction: str):
        """Execute escape maneuver based on current mode."""
        try:
            if self.escape_mode == EscapeMode.ANIMATION_SAFE:
                escape_position = self._calculate_animation_safe_escape(direction)
            else:
                escape_position = self._calculate_emergency_position(direction, 
                                                                   self.collision_status[direction]['distance'])
            
            if escape_position:
                # Create emergency action for escape
                escape_msg = EmergencyAction()
                escape_msg.header.stamp = self.get_clock().now().to_msg()
                escape_msg.action_type = "escape_maneuver"
                escape_msg.direction = direction
                escape_msg.distance = self.collision_status[direction]['distance']
                escape_msg.severity = self.collision_status[direction]['severity']
                escape_msg.target_position = escape_position
                escape_msg.acceleration = SafetyUtils.select_collision_acceleration(
                    self.collision_status[direction]['severity'], 
                    emergency=True,
                    consecutive_count=self.collision_status[direction]['consecutive_count']
                )
                escape_msg.priority = 9  # Very high priority
                
                self.emergency_action_pub.publish(escape_msg)
                self.escape_attempts += 1
                
                self.get_logger().warn(f"Executed escape maneuver for {direction} (attempt {self.escape_attempts})")
                
        except Exception as e:
            self.get_logger().error(f"Error executing escape maneuver: {e}")
    
    def _calculate_animation_safe_escape(self, direction: str) -> Optional[List[float]]:
        """Calculate gentler escape suitable during animations."""
        try:
            new_position = self.current_joints.copy()
            magnitude = min(1.2, 0.8 + (self.escape_attempts * 0.1))
            
            if direction == 'front':
                new_position[1] -= 0.5 * magnitude  # Shoulder back
                new_position[2] += 0.3 * magnitude  # Elbow fold
                # Small rotation
                if self.escape_attempts % 2 == 0:
                    new_position[0] += 0.3 * magnitude
                else:
                    new_position[0] -= 0.3 * magnitude
            elif direction == 'left':
                new_position[0] += 0.4 * magnitude  # Small rotation right
            elif direction == 'right':
                new_position[0] -= 0.4 * magnitude  # Small rotation left
            
            # Ensure limits
            new_position[0] = max(self.base_min_limit, min(self.base_max_limit, new_position[0]))
            
            return new_position
            
        except Exception as e:
            self.get_logger().error(f"Error calculating animation-safe escape: {e}")
            return None
    
    def _update_escape_mode(self, current_time: Time):
        """Update escape mode status and handle timeouts."""
        if self.escape_mode == EscapeMode.INACTIVE:
            return
            
        with self._escape_lock:
            # Check escape mode timeout
            escape_duration = ROSUtils.time_since(self.escape_mode_start_time, current_time)
            
            if escape_duration > self.escape_mode_duration:
                self.get_logger().info(f"Escape mode timeout after {escape_duration:.1f}s")
                self._set_escape_mode(EscapeMode.INACTIVE)
                return
            
            # Check if we need another escape attempt
            if (self.last_escape_direction and 
                self.collision_status[self.last_escape_direction]['active'] and
                self.collision_status[self.last_escape_direction]['consecutive_count'] > self.consecutive_collision_threshold):
                
                if self.escape_attempts >= self.max_escape_attempts:
                    self.get_logger().error(f"Max escape attempts ({self.max_escape_attempts}) exceeded")
                    self._request_emergency_home_position()
                    self._set_escape_mode(EscapeMode.INACTIVE)
                else:
                    # Try another escape
                    self._execute_escape_maneuver(self.last_escape_direction)
    
    def _set_escape_mode(self, mode: EscapeMode):
        """Set escape mode and publish status."""
        self.escape_mode = mode
        if mode == EscapeMode.INACTIVE:
            self.last_escape_direction = None
            self.escape_attempts = 0
        
        # Publish escape mode status
        escape_msg = String()
        escape_msg.data = self.escape_mode.value
        self.escape_mode_pub.publish(escape_msg)
    
    def _process_active_collisions(self, current_time: Time):
        """Process all active collisions and trigger appropriate responses."""
        for direction in ['front', 'left', 'right']:
            if not self.collision_status[direction]['active']:
                continue
                
            # Check if we need to make an adjustment
            if self._should_make_adjustment(direction, current_time):
                self._request_collision_adjustment(direction)
    
    def _should_make_adjustment(self, direction: str, current_time: Time) -> bool:
        """Check if we should make a collision adjustment."""
        # Skip if already returning home
        if self.returning_home:
            return False
            
        # Check cooldown
        time_since_adjustment = ROSUtils.time_since(
            self.adjustment_history[direction]['last_time'], current_time
        )
        
        if (self.adjustment_history[direction]['adjustment_made'] and 
            time_since_adjustment < self.adjustment_cooldown):
            return False
            
        # Check severity
        severity = self.collision_status[direction]['severity']
        distance = self.collision_status[direction]['distance']
        
        return (severity in [CollisionSeverity.WARNING.value, CollisionSeverity.DANGER.value] or
                distance <= self.soft_limit_distance)
    
    def _request_collision_adjustment(self, direction: str):
        """Request a collision adjustment through position request."""
        try:
            adjustment_factor = SafetyUtils.calculate_adjustment_factor(
                self.collision_status[direction]['distance'],
                self.collision_status[direction]['severity'],
                self.soft_limit_distance,
                self.hard_limit_distance
            )
            
            if adjustment_factor < 0.1:
                return
                
            # Calculate adjustment position
            adjusted_position = self._calculate_adjustment_position(direction, adjustment_factor)
            
            if adjusted_position:
                # Create position request
                request_msg = PositionRequest()
                request_msg.header.stamp = self.get_clock().now().to_msg()
                request_msg.request_type = "collision_adjustment"
                request_msg.positions = adjusted_position
                request_msg.speed = SafetyUtils.select_collision_acceleration(
                    self.collision_status[direction]['severity'],
                    consecutive_count=self.collision_status[direction]['consecutive_count']
                )
                request_msg.description = f"Collision adjustment for {direction}"
                request_msg.priority = 8  # High priority
                request_msg.allow_interruption = True
                
                self.position_adjustment_pub.publish(request_msg)
                
                # Update adjustment tracking
                current_time = self.get_clock().now()
                self.adjustment_history[direction]['last_time'] = current_time
                self.adjustment_history[direction]['adjustment_made'] = True
                self.adjustment_history[direction]['last_position'] = self.current_joints.copy()
                
                self.get_logger().info(f"Requested collision adjustment for {direction} (factor: {adjustment_factor:.2f})")
                
        except Exception as e:
            self.get_logger().error(f"Error requesting collision adjustment: {e}")
    
    def _calculate_adjustment_position(self, direction: str, factor: float) -> Optional[List[float]]:
        """Calculate position adjustment for collision avoidance."""
        try:
            adjusted_position = self.current_joints.copy()
            consecutive_count = self.collision_status[direction]['consecutive_count']
            
            # Calculate persistence multiplier
            persistence_multiplier = min(3.0, 1.0 + consecutive_count * 0.1)
            
            if direction == 'front':
                # Pull back arm
                shoulder_adjustment = factor * 0.4 * persistence_multiplier
                elbow_adjustment = factor * 0.3 * persistence_multiplier
                adjusted_position[1] -= shoulder_adjustment
                adjusted_position[2] -= elbow_adjustment
                
            elif direction == 'left':
                # Rotate right (positive adjustment)
                adjustment = factor * self.side_avoidance_magnitude * persistence_multiplier
                adjusted_position[0] += adjustment
                adjusted_position[1] += 0.1 * factor  # Slight pull back
                
            elif direction == 'right':
                # Rotate left (negative adjustment)
                adjustment = factor * self.side_avoidance_magnitude * persistence_multiplier
                adjusted_position[0] -= adjustment
                adjusted_position[1] += 0.1 * factor  # Slight pull back
            
            # Ensure base limits
            adjusted_position[0] = max(self.base_min_limit, min(self.base_max_limit, adjusted_position[0]))
            
            return adjusted_position
            
        except Exception as e:
            self.get_logger().error(f"Error calculating adjustment position: {e}")
            return None
    
    def _check_emergency_conditions(self, current_time: Time):
        """Check for emergency conditions requiring immediate action."""
        # Check for multiple simultaneous collisions
        active_directions = [
            direction for direction in self.collision_status
            if self.collision_status[direction]['active']
        ]
        
        if len(active_directions) >= 2:
            danger_directions = [
                direction for direction in active_directions
                if self.collision_status[direction]['severity'] == CollisionSeverity.DANGER.value
            ]
            
            if danger_directions:
                self.get_logger().error(f"Multiple danger collisions detected: {danger_directions}")
                self._request_emergency_home_position()
    
    def _request_emergency_home_position(self):
        """Request emergency return to home position."""
        try:
            emergency_msg = EmergencyAction()
            emergency_msg.header.stamp = self.get_clock().now().to_msg()
            emergency_msg.action_type = "emergency_home"
            emergency_msg.direction = "multiple"
            emergency_msg.distance = 0.0
            emergency_msg.severity = CollisionSeverity.DANGER.value
            emergency_msg.target_position = LuxoConstants.HOME_POSITION_1
            emergency_msg.acceleration = self.max_deceleration
            emergency_msg.priority = 10  # Maximum priority
            
            self.emergency_action_pub.publish(emergency_msg)
            
            self.get_logger().error("Emergency home position requested due to persistent/multiple collisions")
            
        except Exception as e:
            self.get_logger().error(f"Error requesting emergency home position: {e}")
    
    def _publish_activity_update(self, activity_type: str):
        """Publish activity update for coordination."""
        try:
            msg = ActivityUpdate()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.node_name = "collision_monitor_node"
            msg.activity_type = activity_type
            msg.time_since_activity = 0.0  # Just happened
            
            self.activity_update_pub.publish(msg)
            
        except Exception as e:
            self.get_logger().error(f"Error publishing activity update: {e}")
    
    def get_collision_status(self) -> dict:
        """Get current collision status (external interface)."""
        with self._collision_lock:
            return {
                'collision_status': self.collision_status.copy(),
                'escape_mode': self.escape_mode.value,
                'escape_attempts': self.escape_attempts,
                'persistent_head_collision': self.persistent_head_collision_active,
                'any_collision_active': any(
                    status['active'] for status in self.collision_status.values()
                )
            }


def main(args=None):
    """Main entry point for the collision monitor node."""
    rclpy.init(args=args)
    
    try:
        node = CollisionMonitorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()