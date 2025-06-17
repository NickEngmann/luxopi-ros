#!/usr/bin/env python3
"""
SafetyCoordinatorNode - High-level safety coordination and arbitration.

This node handles:
- Target position override management and priority arbitration
- Safety limit application and validation
- Coordination between competing behaviors (voice vs collision vs idle)
- Final joint command interface with hardware
- State machine coordination and transition management

Author: Generated from collision_avoidance.py refactor
"""

import threading
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
import math

import rclpy
from rclpy.node import Node
from rclpy.time import Time

# ROS message types
from std_msgs.msg import String, Bool, Float32MultiArray
from sensor_msgs.msg import JointState
from geometry_msgs.msg import Vector3
from luxo_interfaces.msg import (
    CollisionStatus, EmergencyAction, PositionRequest, 
    ActivityUpdate, VoiceTarget, PettingStatus,
    SafetyOverride, SystemStatus
)

# Import shared utilities
from shared_utilities import (
    LuxoConstants, 
    SafetyUtils,
    AngleUtils, 
    PositionUtils, 
    ROSUtils,
    StateUtils,
    MathUtils
)


class BehaviorPriority(Enum):
    """Priority levels for different behaviors."""
    EMERGENCY = 10
    COLLISION_AVOIDANCE = 9
    ESCAPE_MODE = 8
    RETURNING_HOME = 7
    PETTING = 6
    ANIMATING = 5
    EMOTION_REACTING = 4
    VOICE_FOLLOWING = 3
    IDLE_ANIMATION = 2
    IDLE_HEAD_VARIATION = 1
    USER_COMMAND = 5  # Configurable priority


@dataclass
class TargetOverride:
    """Represents a target position override with metadata."""
    positions: List[float]
    priority: int
    source: str
    reason: str
    timestamp: Time
    timeout: float
    allow_interruption: bool = True
    acceleration: Optional[float] = None
    blend_factor: float = 1.0  # How much to blend with original target (0.0-1.0)


@dataclass
class BehaviorRequest:
    """Represents a behavior request from any source."""
    request_id: str
    source_node: str
    request_type: str
    target_positions: List[float]
    priority: int
    speed: float
    description: str
    allow_interruption: bool
    timestamp: Time
    metadata: Dict[str, Any] = field(default_factory=dict)


class SafetyCoordinatorNode(Node):
    """
    ROS2 node responsible for high-level safety coordination and arbitration.
    """
    
    def __init__(self):
        super().__init__('safety_coordinator_node')
        
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
        self._coordination_lock = threading.Lock()
        self._override_lock = threading.Lock()
        self._safety_lock = threading.Lock()
        
        self.get_logger().info("SafetyCoordinatorNode initialized successfully")
    
    def _declare_parameters(self):
        """Declare ROS parameters with default values."""
        # Safety limits
        self.declare_parameter('soft_limit_distance', 15.0)
        self.declare_parameter('hard_limit_distance', 8.0)
        
        # Override management
        self.declare_parameter('default_override_timeout', 10.0)
        self.declare_parameter('max_override_duration', 30.0)
        self.declare_parameter('blend_transition_time', 2.0)
        
        # Base rotation limits
        self.declare_parameter('base_min_limit', -260.0)  # degrees
        self.declare_parameter('base_max_limit', 135.0)   # degrees
        self.declare_parameter('enable_base_wraparound', True)
        
        # Joint limits (radians) - for validation
        self.declare_parameter('shoulder_min_limit', -3.14)
        self.declare_parameter('shoulder_max_limit', 3.14)
        self.declare_parameter('elbow_min_limit', -3.14)
        self.declare_parameter('elbow_max_limit', 3.14)
        self.declare_parameter('wrist_min_limit', -3.14)
        self.declare_parameter('wrist_max_limit', 3.14)
        self.declare_parameter('hand_min_limit', -3.14)
        self.declare_parameter('hand_max_limit', 3.14)
        
        # Coordination parameters
        self.declare_parameter('enable_voice_coordination', True)
        self.declare_parameter('enable_collision_coordination', True)
        self.declare_parameter('enable_movement_source_integration', True)
        self.declare_parameter('command_rate_limit', 50.0)  # Hz
        
        # Hardware interface parameters
        self.declare_parameter('joint_command_topic', '/roarm/joint_command')
        self.declare_parameter('joint_names', ['base', 'shoulder', 'elbow', 'wrist', 'hand'])
    
    def _load_parameters(self):
        """Load parameters from ROS parameter server."""
        self.soft_limit_distance = self.get_parameter('soft_limit_distance').value
        self.hard_limit_distance = self.get_parameter('hard_limit_distance').value
        
        self.default_override_timeout = self.get_parameter('default_override_timeout').value
        self.max_override_duration = self.get_parameter('max_override_duration').value
        self.blend_transition_time = self.get_parameter('blend_transition_time').value
        
        # Convert base limits to radians
        self.base_min_limit = math.radians(self.get_parameter('base_min_limit').value)
        self.base_max_limit = math.radians(self.get_parameter('base_max_limit').value)
        self.enable_base_wraparound = self.get_parameter('enable_base_wraparound').value
        
        # Joint limits
        self.joint_limits = [
            (self.base_min_limit, self.base_max_limit),
            (self.get_parameter('shoulder_min_limit').value, self.get_parameter('shoulder_max_limit').value),
            (self.get_parameter('elbow_min_limit').value, self.get_parameter('elbow_max_limit').value),
            (self.get_parameter('wrist_min_limit').value, self.get_parameter('wrist_max_limit').value),
            (self.get_parameter('hand_min_limit').value, self.get_parameter('hand_max_limit').value)
        ]
        
        self.enable_voice_coordination = self.get_parameter('enable_voice_coordination').value
        self.enable_collision_coordination = self.get_parameter('enable_collision_coordination').value
        self.enable_movement_source_integration = self.get_parameter('enable_movement_source_integration').value
        self.command_rate_limit = self.get_parameter('command_rate_limit').value
        
        self.joint_command_topic = self.get_parameter('joint_command_topic').value
        self.joint_names = self.get_parameter('joint_names').value
    
    def _initialize_state(self):
        """Initialize internal state variables."""
        # Current robot state
        self.current_joints: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.target_joints: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.joint_velocities: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.robot_state: str = "IDLE"
        
        # Target override management
        self.active_overrides: Dict[str, TargetOverride] = {}
        self.current_override: Optional[TargetOverride] = None
        self.last_override_evaluation: Time = self.get_clock().now()
        
        # Behavior coordination
        self.pending_requests: Dict[str, BehaviorRequest] = {}
        self.last_processed_request: Optional[str] = None
        self.request_counter = 0
        
        # Status tracking from other nodes
        self.collision_status: Optional[CollisionStatus] = None
        self.voice_target: Optional[VoiceTarget] = None
        self.petting_status: Optional[PettingStatus] = None
        self.animation_active: bool = False
        self.escape_mode_active: bool = False
        
        # Command rate limiting
        self.last_command_time: Time = self.get_clock().now()
        self.min_command_interval = 1.0 / self.command_rate_limit
        
        # Safety state
        self.safety_limits_enabled: bool = True
        self.emergency_stop_active: bool = False
        self.system_healthy: bool = True
        
        # Movement source tracking for DEMA integration
        self.current_movement_source: str = "idle"
        self.last_movement_source_time: Time = self.get_clock().now()
    
    def _create_publishers(self):
        """Create ROS publishers."""
        # Hardware interface - final joint commands
        self.joint_command_pub = self.create_publisher(
            JointState,
            self.joint_command_topic,
            10
        )
        
        # System status and coordination
        self.system_status_pub = self.create_publisher(
            SystemStatus,
            '/safety/system_status',
            10
        )
        
        # Active override information
        self.active_override_pub = self.create_publisher(
            SafetyOverride,
            '/safety/active_override',
            10
        )
        
        # Movement source for DEMA integration
        self.movement_source_pub = self.create_publisher(
            String,
            '/robot/movement_source',
            10
        )
        
        # Safety coordinator status
        self.coordinator_status_pub = self.create_publisher(
            String,
            '/safety/coordinator_status',
            10
        )
        
        # Robot state updates
        self.robot_state_pub = self.create_publisher(
            String,
            '/robot/state',
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
        # Robot joint states
        self.joint_states_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_states_callback,
            10
        )
        
        # Collision monitoring
        self.collision_status_sub = self.create_subscription(
            CollisionStatus,
            '/collision/status',
            self.collision_status_callback,
            10
        )
        
        self.emergency_action_sub = self.create_subscription(
            EmergencyAction,
            '/collision/emergency_action',
            self.emergency_action_callback,
            10
        )
        
        self.collision_adjustment_sub = self.create_subscription(
            PositionRequest,
            '/collision/position_adjustment',
            self.collision_adjustment_callback,
            10
        )
        
        # Voice following
        self.voice_target_sub = self.create_subscription(
            VoiceTarget,
            '/voice/target_position',
            self.voice_target_callback,
            10
        )
        
        # Idle behavior
        self.idle_position_sub = self.create_subscription(
            PositionRequest,
            '/idle/position_request',
            self.idle_position_callback,
            10
        )
        
        self.idle_head_variation_sub = self.create_subscription(
            PositionRequest,
            '/idle/head_variation_request',
            self.idle_head_variation_callback,
            10
        )
        
        # Petting response
        self.petting_status_sub = self.create_subscription(
            PettingStatus,
            '/petting/status',
            self.petting_status_callback,
            10
        )
        
        self.petting_position_sub = self.create_subscription(
            PositionRequest,
            '/petting/position_request',
            self.petting_position_callback,
            10
        )
        
        # User commands and external targets
        self.user_target_sub = self.create_subscription(
            PositionRequest,
            '/user/target_position',
            self.user_target_callback,
            10
        )
        
        # Animation coordination
        self.animation_target_sub = self.create_subscription(
            PositionRequest,
            '/animation/target_position',
            self.animation_target_callback,
            10
        )
        
        # External safety overrides
        self.external_override_sub = self.create_subscription(
            SafetyOverride,
            '/safety/external_override',
            self.external_override_callback,
            10
        )
        
        # System commands
        self.system_command_sub = self.create_subscription(
            String,
            '/safety/system_command',
            self.system_command_callback,
            10
        )
    
    def _create_timers(self):
        """Create periodic timers."""
        # Main coordination timer (runs at command rate limit)
        self.coordination_timer = self.create_timer(
            self.min_command_interval, 
            self.coordination_timer_callback
        )
        
        # Override management timer (runs every 100ms)
        self.override_timer = self.create_timer(0.1, self.override_management_callback)
        
        # Status publishing timer (runs every 500ms)
        self.status_timer = self.create_timer(0.5, self.status_publish_callback)
    
    def joint_states_callback(self, msg: JointState):
        """Handle joint state updates from hardware."""
        if len(msg.position) >= 5:
            self.current_joints = list(msg.position[:5])
            
        if len(msg.velocity) >= 5:
            self.joint_velocities = list(msg.velocity[:5])
    
    def collision_status_callback(self, msg: CollisionStatus):
        """Handle collision status updates."""
        with self._safety_lock:
            self.collision_status = msg
            self.escape_mode_active = msg.escape_mode_active
    
    def emergency_action_callback(self, msg: EmergencyAction):
        """Handle emergency actions from collision monitor."""
        try:
            self.get_logger().warn(f"Emergency action received: {msg.action_type} for {msg.direction}")
            
            # Create high-priority override
            override = TargetOverride(
                positions=list(msg.target_position),
                priority=BehaviorPriority.EMERGENCY.value,
                source="collision_monitor",
                reason=f"Emergency {msg.action_type} for {msg.direction}",
                timestamp=self.get_clock().now(),
                timeout=5.0,  # Short timeout for emergency actions
                allow_interruption=False,
                acceleration=msg.acceleration
            )
            
            with self._override_lock:
                self.active_overrides["emergency"] = override
                self.current_override = override
                
            # Immediately update movement source
            self._update_movement_source("collision")
            
            # Force immediate execution
            self._execute_current_target(force=True)
            
        except Exception as e:
            self.get_logger().error(f"Error handling emergency action: {e}")
    
    def collision_adjustment_callback(self, msg: PositionRequest):
        """Handle collision adjustment requests."""
        self._handle_position_request(msg, "collision_adjustment")
    
    def voice_target_callback(self, msg: VoiceTarget):
        """Handle voice following target updates."""
        if not self.enable_voice_coordination:
            return
            
        try:
            self.voice_target = msg
            
            # Create voice following override if voice is active
            if msg.active and msg.influence > 0.1:
                override = TargetOverride(
                    positions=list(msg.target_position),
                    priority=BehaviorPriority.VOICE_FOLLOWING.value,
                    source="voice_following",
                    reason=f"Voice following at {msg.direction:.1f}° (influence: {msg.influence:.2f})",
                    timestamp=self.get_clock().now(),
                    timeout=3.0,  # Short timeout for voice following
                    allow_interruption=True,
                    acceleration=msg.speed,
                    blend_factor=msg.influence  # Use voice influence as blend factor
                )
                
                with self._override_lock:
                    self.active_overrides["voice_following"] = override
                    
                self._update_movement_source("voice")
            else:
                # Clear voice following override if voice is inactive
                with self._override_lock:
                    if "voice_following" in self.active_overrides:
                        del self.active_overrides["voice_following"]
                        
        except Exception as e:
            self.get_logger().error(f"Error handling voice target: {e}")
    
    def idle_position_callback(self, msg: PositionRequest):
        """Handle idle behavior position requests."""
        priority = BehaviorPriority.IDLE_ANIMATION.value
        if msg.request_type == "home_position":
            priority = BehaviorPriority.RETURNING_HOME.value
        elif msg.request_type == "rest_position":
            priority = BehaviorPriority.RETURNING_HOME.value
            
        self._handle_position_request(msg, f"idle_{msg.request_type}", priority)
    
    def idle_head_variation_callback(self, msg: PositionRequest):
        """Handle idle head variation requests."""
        self._handle_position_request(msg, "idle_head_variation", BehaviorPriority.IDLE_HEAD_VARIATION.value)
    
    def petting_status_callback(self, msg: PettingStatus):
        """Handle petting status updates."""
        self.petting_status = msg
    
    def petting_position_callback(self, msg: PositionRequest):
        """Handle petting response position requests."""
        self._handle_position_request(msg, "petting_response", BehaviorPriority.PETTING.value)
    
    def user_target_callback(self, msg: PositionRequest):
        """Handle user command position requests."""
        self._handle_position_request(msg, "user_command", BehaviorPriority.USER_COMMAND.value)
    
    def animation_target_callback(self, msg: PositionRequest):
        """Handle animation target position requests."""
        self.animation_active = True
        self._handle_position_request(msg, "animation", BehaviorPriority.ANIMATING.value)
    
    def external_override_callback(self, msg: SafetyOverride):
        """Handle external safety overrides."""
        try:
            if msg.override_type == "emergency_stop":
                self.emergency_stop_active = msg.active
                self.get_logger().warn(f"Emergency stop: {'ACTIVE' if msg.active else 'CLEARED'}")
                
            elif msg.override_type == "safety_limits":
                self.safety_limits_enabled = msg.active
                self.get_logger().info(f"Safety limits: {'ENABLED' if msg.active else 'DISABLED'}")
                
            elif msg.override_type == "position_override" and msg.active:
                # External position override
                override = TargetOverride(
                    positions=list(msg.target_position),
                    priority=msg.priority,
                    source="external",
                    reason=msg.reason,
                    timestamp=self.get_clock().now(),
                    timeout=msg.timeout,
                    allow_interruption=msg.allow_interruption
                )
                
                with self._override_lock:
                    self.active_overrides["external"] = override
                    
        except Exception as e:
            self.get_logger().error(f"Error handling external override: {e}")
    
    def system_command_callback(self, msg: String):
        """Handle system-level commands."""
        try:
            command = msg.data.lower()
            
            if command == "emergency_stop":
                self.emergency_stop_active = True
                self.get_logger().error("EMERGENCY STOP ACTIVATED")
                
            elif command == "emergency_clear":
                self.emergency_stop_active = False
                self.get_logger().warn("Emergency stop cleared")
                
            elif command == "clear_overrides":
                with self._override_lock:
                    self.active_overrides.clear()
                    self.current_override = None
                self.get_logger().info("All overrides cleared")
                
            elif command == "go_home":
                self._request_home_position("System command")
                
            elif command == "enable_safety":
                self.safety_limits_enabled = True
                self.get_logger().info("Safety limits enabled")
                
            elif command == "disable_safety":
                self.safety_limits_enabled = False
                self.get_logger().warn("Safety limits disabled")
                
        except Exception as e:
            self.get_logger().error(f"Error handling system command: {e}")
    
    def _handle_position_request(self, msg: PositionRequest, source_type: str, priority: Optional[int] = None):
        """Handle incoming position requests from any source."""
        try:
            # Use priority from message or provided priority
            actual_priority = priority if priority is not None else msg.priority
            
            # Create override
            override = TargetOverride(
                positions=list(msg.positions),
                priority=actual_priority,
                source=source_type,
                reason=msg.description,
                timestamp=self.get_clock().now(),
                timeout=getattr(msg, 'timeout', self.default_override_timeout),
                allow_interruption=msg.allow_interruption,
                acceleration=msg.speed
            )
            
            with self._override_lock:
                self.active_overrides[source_type] = override
                
            # Update movement source based on type
            if "collision" in source_type:
                self._update_movement_source("collision")
            elif "voice" in source_type:
                self._update_movement_source("voice")
            elif "user" in source_type:
                self._update_movement_source("user")
            elif "animation" in source_type:
                self._update_movement_source("animation")
            else:
                self._update_movement_source("idle")
                
            self.get_logger().debug(f"Position request received: {source_type} (priority: {actual_priority})")
            
        except Exception as e:
            self.get_logger().error(f"Error handling position request from {source_type}: {e}")
    
    def coordination_timer_callback(self):
        """Main coordination timer - determines and executes final target."""
        try:
            # Skip if emergency stop active
            if self.emergency_stop_active:
                return
                
            # Rate limiting check
            current_time = self.get_clock().now()
            time_since_last_command = ROSUtils.time_since(self.last_command_time, current_time)
            
            if time_since_last_command < self.min_command_interval:
                return
                
            # Determine effective target position
            effective_target = self._determine_effective_target()
            
            if effective_target is not None:
                # Apply safety limits
                safe_target = self._apply_safety_limits(effective_target)
                
                # Validate target
                if self._validate_target_position(safe_target):
                    # Execute the command
                    self._execute_joint_command(safe_target)
                    self.last_command_time = current_time
                else:
                    self.get_logger().warn("Target position validation failed")
            
        except Exception as e:
            self.get_logger().error(f"Error in coordination timer: {e}")
    
    def override_management_callback(self):
        """Manage override timeouts and priority resolution."""
        try:
            current_time = self.get_clock().now()
            
            with self._override_lock:
                # Remove expired overrides
                expired_keys = []
                for key, override in self.active_overrides.items():
                    age = ROSUtils.time_since(override.timestamp, current_time)
                    if age > override.timeout or age > self.max_override_duration:
                        expired_keys.append(key)
                        
                for key in expired_keys:
                    self.get_logger().debug(f"Override expired: {key}")
                    del self.active_overrides[key]
                
                # Determine current highest priority override
                if self.active_overrides:
                    highest_priority_override = max(
                        self.active_overrides.values(),
                        key=lambda x: x.priority
                    )
                    
                    if self.current_override != highest_priority_override:
                        old_source = self.current_override.source if self.current_override else "none"
                        self.current_override = highest_priority_override
                        self.get_logger().info(
                            f"Override priority change: {old_source} -> {highest_priority_override.source} "
                            f"(priority: {highest_priority_override.priority})"
                        )
                else:
                    if self.current_override is not None:
                        self.get_logger().debug("All overrides cleared")
                        self.current_override = None
                        
        except Exception as e:
            self.get_logger().error(f"Error in override management: {e}")
    
    def status_publish_callback(self):
        """Publish system status and coordination information."""
        try:
            current_time = self.get_clock().now()
            
            # Publish system status
            system_status = SystemStatus()
            system_status.header.stamp = current_time.to_msg()
            system_status.robot_state = self.robot_state
            system_status.emergency_stop_active = self.emergency_stop_active
            system_status.safety_limits_enabled = self.safety_limits_enabled
            system_status.system_healthy = self.system_healthy
            system_status.current_movement_source = self.current_movement_source
            
            # Add override information
            with self._override_lock:
                system_status.active_override_count = len(self.active_overrides)
                if self.current_override:
                    system_status.current_override_source = self.current_override.source
                    system_status.current_override_priority = self.current_override.priority
                    system_status.current_override_reason = self.current_override.reason
                    
            self.system_status_pub.publish(system_status)
            
            # Publish active override details
            if self.current_override:
                override_msg = SafetyOverride()
                override_msg.header.stamp = current_time.to_msg()
                override_msg.override_type = "position_override"
                override_msg.active = True
                override_msg.source = self.current_override.source
                override_msg.reason = self.current_override.reason
                override_msg.priority = self.current_override.priority
                override_msg.target_position = self.current_override.positions
                override_msg.timeout = self.current_override.timeout
                override_msg.allow_interruption = self.current_override.allow_interruption
                
                self.active_override_pub.publish(override_msg)
                
        except Exception as e:
            self.get_logger().error(f"Error publishing status: {e}")
    
    def _determine_effective_target(self) -> Optional[List[float]]:
        """Determine the effective target position considering all inputs."""
        try:
            # If no override, use current target joints
            if self.current_override is None:
                return self.target_joints.copy()
                
            # Use override position
            override_target = self.current_override.positions.copy()
            
            # Apply blending if specified
            if self.current_override.blend_factor < 1.0:
                override_target = MathUtils.blend_positions(
                    self.target_joints,
                    override_target,
                    self.current_override.blend_factor
                )
                
            return override_target
            
        except Exception as e:
            self.get_logger().error(f"Error determining effective target: {e}")
            return None
    
    def _apply_safety_limits(self, target_positions: List[float]) -> List[float]:
        """Apply safety limits based on current collision status."""
        if not self.safety_limits_enabled or not self.enable_collision_coordination:
            return target_positions
            
        try:
            safe_positions = target_positions.copy()
            
            # Skip safety limits if returning home (except for hard limits)
            if (self.current_override and 
                "home" in self.current_override.source and
                self.current_override.priority >= BehaviorPriority.RETURNING_HOME.value):
                
                # Only apply hard joint limits for home positions
                return PositionUtils.validate_joint_limits(safe_positions, self.joint_limits)
            
            # Apply collision-based safety limits
            if self.collision_status:
                safe_positions = self._apply_collision_safety_limits(safe_positions)
                
            # Apply joint limits
            safe_positions = PositionUtils.validate_joint_limits(safe_positions, self.joint_limits)
            
            return safe_positions
            
        except Exception as e:
            self.get_logger().error(f"Error applying safety limits: {e}")
            return target_positions
    
    def _apply_collision_safety_limits(self, positions: List[float]) -> List[float]:
        """Apply safety limits based on collision status."""
        safe_positions = positions.copy()
        
        try:
            # Front collision limits (affects shoulder and elbow)
            if self.collision_status.front_active:
                severity = self.collision_status.front_severity
                distance = self.collision_status.front_distance
                
                if severity == "danger" or distance <= self.hard_limit_distance:
                    # Hard limits - prevent forward movement
                    safe_positions[1] = max(safe_positions[1], self.current_joints[1])  # Shoulder
                    safe_positions[2] = max(safe_positions[2], self.current_joints[2])  # Elbow
                    
                elif severity == "warning" or distance <= self.soft_limit_distance:
                    # Soft limits - graduated restriction
                    limit_factor = min(1.0, (distance - self.hard_limit_distance) / 
                                     (self.soft_limit_distance - self.hard_limit_distance))
                    
                    if safe_positions[1] < self.current_joints[1]:  # Moving shoulder forward
                        delta = self.current_joints[1] - safe_positions[1]
                        safe_positions[1] = self.current_joints[1] - (delta * limit_factor)
                        
                    if safe_positions[2] < self.current_joints[2]:  # Extending elbow
                        delta = self.current_joints[2] - safe_positions[2]
                        safe_positions[2] = self.current_joints[2] - (delta * limit_factor)
            
            # Left collision limits (affects base rotation)
            if self.collision_status.left_active:
                severity = self.collision_status.left_severity
                distance = self.collision_status.left_distance
                
                if ((severity == "danger" or distance <= self.hard_limit_distance) and 
                    safe_positions[0] > self.current_joints[0]):
                    # Prevent further right rotation
                    safe_positions[0] = self.current_joints[0]
                elif ((severity == "warning" or distance <= self.soft_limit_distance) and 
                      safe_positions[0] > self.current_joints[0]):
                    # Graduated limit
                    limit_factor = min(1.0, (distance - self.hard_limit_distance) / 
                                     (self.soft_limit_distance - self.hard_limit_distance))
                    delta = safe_positions[0] - self.current_joints[0]
                    safe_positions[0] = self.current_joints[0] + (delta * limit_factor)
            
            # Right collision limits (affects base rotation)
            if self.collision_status.right_active:
                severity = self.collision_status.right_severity
                distance = self.collision_status.right_distance
                
                if ((severity == "danger" or distance <= self.hard_limit_distance) and 
                    safe_positions[0] < self.current_joints[0]):
                    # Prevent further left rotation
                    safe_positions[0] = self.current_joints[0]
                elif ((severity == "warning" or distance <= self.soft_limit_distance) and 
                      safe_positions[0] < self.current_joints[0]):
                    # Graduated limit
                    limit_factor = min(1.0, (distance - self.hard_limit_distance) / 
                                     (self.soft_limit_distance - self.hard_limit_distance))
                    delta = self.current_joints[0] - safe_positions[0]
                    safe_positions[0] = self.current_joints[0] - (delta * limit_factor)
            
            return safe_positions
            
        except Exception as e:
            self.get_logger().error(f"Error applying collision safety limits: {e}")
            return positions
    
    def _validate_target_position(self, positions: List[float]) -> bool:
        """Validate that target position is safe and achievable."""
        try:
            # Check array length
            if len(positions) < 5:
                self.get_logger().warn(f"Target position has insufficient joints: {len(positions)}")
                return False
                
            # Check for NaN or infinite values
            for i, pos in enumerate(positions):
                if not math.isfinite(pos):
                    self.get_logger().warn(f"Invalid value in joint {i}: {pos}")
                    return False
            
            # Check joint limits
            for i, (pos, (min_limit, max_limit)) in enumerate(zip(positions, self.joint_limits)):
                if pos < min_limit or pos > max_limit:
                    self.get_logger().warn(
                        f"Joint {i} position {pos:.3f} outside limits [{min_limit:.3f}, {max_limit:.3f}]"
                    )
                    return False
            
            # Check for excessive change from current position
            max_change_per_command = 0.5  # radians
            for i, (target, current) in enumerate(zip(positions, self.current_joints)):
                change = abs(target - current)
                if change > max_change_per_command:
                    self.get_logger().warn(
                        f"Excessive change in joint {i}: {change:.3f} > {max_change_per_command}"
                    )
                    return False
            
            return True
            
        except Exception as e:
            self.get_logger().error(f"Error validating target position: {e}")
            return False
    
    def _execute_joint_command(self, positions: List[float]):
        """Execute final joint command to hardware."""
        try:
            # Create joint state message
            msg = ROSUtils.create_joint_state_msg(
                self,
                self.joint_names,
                positions
            )
            
            # Add acceleration if specified in current override
            if self.current_override and self.current_override.acceleration:
                # Encode acceleration in velocity field for hardware interface
                msg.velocity = [self.current_override.acceleration]
            
            # Publish command
            self.joint_command_pub.publish(msg)
            
            # Update target joints for next cycle
            self.target_joints = positions.copy()
            
            # Log significant position changes
            if not PositionUtils.at_position(positions, self.current_joints, 0.1):
                source = self.current_override.source if self.current_override else "default"
                self.get_logger().debug(
                    f"Joint command executed (source: {source}): "
                    f"{[round(p, 3) for p in positions]}"
                )
                
        except Exception as e:
            self.get_logger().error(f"Error executing joint command: {e}")
    
    def _execute_current_target(self, force: bool = False):
        """Force immediate execution of current target (for emergency situations)."""
        try:
            if force or not self.emergency_stop_active:
                effective_target = self._determine_effective_target()
                if effective_target:
                    safe_target = self._apply_safety_limits(effective_target)
                    if self._validate_target_position(safe_target):
                        self._execute_joint_command(safe_target)
                        
        except Exception as e:
            self.get_logger().error(f"Error in forced execution: {e}")
    
    def _update_movement_source(self, source: str):
        """Update movement source for DEMA integration."""
        try:
            if source != self.current_movement_source:
                self.current_movement_source = source
                self.last_movement_source_time = self.get_clock().now()
                
                if self.enable_movement_source_integration:
                    # Publish movement source
                    source_msg = String()
                    source_msg.data = source
                    self.movement_source_pub.publish(source_msg)
                    
                    self.get_logger().debug(f"Movement source updated: {source}")
                    
        except Exception as e:
            self.get_logger().error(f"Error updating movement source: {e}")
    
    def _request_home_position(self, reason: str):
        """Request return to home position."""
        try:
            # Create high-priority home position override
            override = TargetOverride(
                positions=LuxoConstants.HOME_POSITION_1,
                priority=BehaviorPriority.RETURNING_HOME.value,
                source="safety_coordinator_home",
                reason=f"Home position request: {reason}",
                timestamp=self.get_clock().now(),
                timeout=30.0,  # Long timeout for home position
                allow_interruption=False,
                acceleration=8.0  # Moderate speed
            )
            
            with self._override_lock:
                self.active_overrides["home_position"] = override
                
            self._update_movement_source("collision")
            self.get_logger().info(f"Home position requested: {reason}")
            
        except Exception as e:
            self.get_logger().error(f"Error requesting home position: {e}")
    
    def get_system_status(self) -> dict:
        """Get current system status (external interface)."""
        with self._override_lock:
            return {
                'robot_state': self.robot_state,
                'emergency_stop_active': self.emergency_stop_active,
                'safety_limits_enabled': self.safety_limits_enabled,
                'system_healthy': self.system_healthy,
                'current_movement_source': self.current_movement_source,
                'active_override_count': len(self.active_overrides),
                'current_override_source': self.current_override.source if self.current_override else None,
                'current_override_priority': self.current_override.priority if self.current_override else 0,
                'collision_active': self.collision_status.any_collision_active if self.collision_status else False,
                'escape_mode_active': self.escape_mode_active
            }
    
    def clear_all_overrides(self):
        """Clear all active overrides (external interface)."""
        with self._override_lock:
            self.active_overrides.clear()
            self.current_override = None
            
        self.get_logger().info("All overrides cleared via external command")
    
    def set_emergency_stop(self, active: bool):
        """Set emergency stop state (external interface)."""
        self.emergency_stop_active = active
        status = "ACTIVATED" if active else "CLEARED"
        self.get_logger().warn(f"Emergency stop {status} via external command")


def main(args=None):
    """Main entry point for the safety coordinator node."""
    rclpy.init(args=args)
    
    try:
        node = SafetyCoordinatorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()