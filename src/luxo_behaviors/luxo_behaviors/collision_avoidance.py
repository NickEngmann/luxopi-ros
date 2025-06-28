#!/usr/bin/env python3
#collision_avoidance.py

import random
import time
import math
import threading
import rclpy
from rclpy.action import ActionClient
from luxo_interfaces.action import PlayAnimation
import time
from sensor_msgs.msg import JointState
from std_msgs.msg import String, Float32, Bool
from luxo_interfaces.srv import RequestStateTransition
from luxo_interfaces.msg import StateInfo
from luxo_behaviors.state_machine import LuxoState
import numpy as np

# Import shared utilities
from luxo_behaviors.shared_utils import (
    PositionUtils, MovementSourcePublisher, CollisionStatusTracker,
    TimeUtils, SafetyLimits, AnimationTracker, IdleAnimationConfig,
    MovementValidator, CollisionMath
)

from luxo_behaviors.petting_behavior import PettingBehavior

class CollisionAvoidance(PettingBehavior):
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
        
        # Create service clients for state management
        self.request_state_transition_client = self.node.create_client(
            RequestStateTransition, 
            '/luxo/request_state_transition'
        )
        
        # Wait for state management services
        while not self.request_state_transition_client.wait_for_service(timeout_sec=1.0):
            self.node.get_logger().info('Waiting for state management services...')
        
        # Subscribe to state changes
        self.state_subscription = self.node.create_subscription(
            StateInfo,
            '/luxo/state_info',
            self._state_info_callback,
            10
        )
        
        # Cache current state locally for quick access
        self._cached_state = None
        self._state_info = None
        self._state_lock = threading.Lock()
        
        # Track startup time to prevent false petting detection
        self._startup_time = self.node.get_clock().now()
        
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
        
        # Initialize safety limits
        if hasattr(node, 'base_min_limit'):
            self.safety_limits = SafetyLimits(
                base_min=node.base_min_limit,
                base_max=node.base_max_limit,
                soft_margin=np.deg2rad(10.0)
            )
            self.base_min_limit = node.base_min_limit
            self.base_max_limit = node.base_max_limit
            self.base_soft_min = node.base_soft_min
            self.base_soft_max = node.base_soft_max
            self.enable_base_wraparound = node.enable_base_wraparound
        else:
            # Fallback values if not available
            self.safety_limits = SafetyLimits()
            self.base_min_limit = np.deg2rad(-260.0)
            self.base_max_limit = np.deg2rad(135.0)
            self.base_soft_min = self.base_min_limit + np.deg2rad(10.0)
            self.base_soft_max = self.base_max_limit - np.deg2rad(10.0)
            self.enable_base_wraparound = True
        
        # Initialize shared utilities
        self.position_utils = PositionUtils()
        self.movement_publisher = MovementSourcePublisher()
        self.collision_tracker = CollisionStatusTracker()
        self.animation_tracker = AnimationTracker()
        self.idle_config = IdleAnimationConfig()
        self.time_utils = TimeUtils()
        
        # Collision tracking with ROS time
        self.collision_status = self.collision_tracker.status
        self.collision_lock = threading.Lock()
        self.last_collision_time = self.node.get_clock().now()
        self.last_avoidance_direction = None  # Track which direction last triggered avoidance
        
        # Adjustment tracking with ROS time
        self.adjustment_history = {
            'front': {'last_time': self.node.get_clock().now(), 'last_position': None, 'adjustment_made': False},
            'left': {'last_time': self.node.get_clock().now(), 'last_position': None, 'adjustment_made': False},
            'right': {'last_time': self.node.get_clock().now(), 'last_position': None, 'adjustment_made': False}
        }
        self.adjustment_cooldown = 1.0 
        self.adjustment_position_threshold = 0.1  # Difference threshold to consider a new position
        
        # Escape mode variables with ROS time
        self.escape_mode_start_time = self.node.get_clock().now()
        self.unsafe_zones = []  # List of positions to avoid
        self.last_escape_direction = None  # Track last escape direction
        self.retreat_level = 0  # Tracks how far we've retreated
        self.escape_attempts = 0  # Count escape attempts
        
        # Target override tracking with ROS time
        self.target_override_active = False  # Flag to indicate override is active
        self.target_override_time = self.node.get_clock().now()  # When the override was activated
        self.target_override_joints = None  # The safe position we've moved to
        self.target_override_reason = ""  # Why the override exists
        self.target_override_timeout = 10.0  # Time before reconsidering original target
        self.last_original_target_change_time = self.node.get_clock().now()  # Last time original target changed
        
        # Rest position tracking
        self.last_rest_position = None  # Track the last used rest position
        self.is_returning_to_rest = False  # Flag to track when we're returning to rest
        
        # External shared state
        self.current_joints = [0.0, 0.0, 0.0, 0.0, 0.0]  # Current joint positions
        self.target_joints = [0.0, 0.0, 0.0, 0.0, 0.0]   # Target joint positions
        self.joint_velocities = [0.0, 0.0, 0.0, 0.0, 0.0] # Current joint velocities
        
        # Additional tracking variables with ROS time
        self.last_failed_adjustment_time = self.node.get_clock().now()
        self.last_proactive_check = self.node.get_clock().now()
        
        # Two-stage home position sequence
        self.home_position_1 = [0.5, 0.5, 1.3, 1.4, -1.5]  # Initial home position
        self.home_position_2 = [0.5, -0.85, 1.3, 1.4, -1.5]  # Final home position
        self.home_position_tolerance = 0.2  # Tolerance to determine if we're at a position
        self.home_position_stage = 1  # Track which stage of the home sequence we're in
        self.home_position_stage_change_time = self.node.get_clock().now()  # When we switched home position stages
        self.home_position_stage_timeout = 0.5  # Time to wait at home_position_1 before moving to home_position_2
        
        # Animation state tracking with ROS time
        self.last_movement_time = self.node.get_clock().now()
        self.recent_command_times = []

        # Animation action tracking for collision coordination
        self.current_animation_name = None
        self.animation_allow_interruption = True
        self.animation_progress = 0.0
        self.animation_lock = threading.Lock()
        
        # Track if we've preempted an animation
        self.animation_preempted = False
        self.animation_preemption_time = self.node.get_clock().now()
        # Add tracking for persistent front (head) collision with ROS time
        self.persistent_head_collision_start = self.node.get_clock().now()
        self.persistent_head_collision_active = False
        self.persistent_head_collision_last_log = self.node.get_clock().now()  # For log throttling
        
        # Add timeout config for persistent collisions
        self.short_collision_timeout = 1.25  # Original timeout for quick response (seconds)
        self.extended_collision_timeout = 8.0  # Extended timeout for persistent collisions (seconds)
        self.max_collision_timeout = 15.0     # Maximum time before force reset (seconds)
        
        # Add tracking for idle time with ROS time
        self.last_activity_time = self.node.get_clock().now()
        # Random idle timeout between 3-12 seconds
        self.idle_timeout = random.uniform(4.0, 16.0)
        self.idle_check_active = True  # Flag to enable/disable idle detection
        self.idle_check_last_log = self.node.get_clock().now()  # For log throttling
        
        # Log the selected timeout
        self.node.get_logger().info(f"Idle timeout set to {self.idle_timeout:.1f} seconds")
        
        # Add flags for special operations
        self.returning_to_home_start_time = self.node.get_clock().now()  # When we started returning to home
        
        # Initialize all ROS time tracking variables
        self.last_error_time = self.node.get_clock().now()
        self.last_position_log_time = self.node.get_clock().now()
        self.last_animation_end_time = self.node.get_clock().now()
        self.last_source_log = self.node.get_clock().now()
        self.last_home_override_log = self.node.get_clock().now()
        
        # Timer for idle reset (will be created when needed)
        self.idle_reset_timer = None

        self.idle_animations = self.idle_config.idle_animations
        self.last_idle_animation = None
        self.min_idle_time_before_animation = 5.0  # seconds before first idle animation
        self.idle_animation_interval = random.uniform(10.0, 60.0)  # time between animations
        self.last_idle_animation_time = self.node.get_clock().now()
        
        # Add idle head variation tracking
        self.idle_head_variation_enabled = False  # Will be set by hardware interface
        self.idle_head_variation_interval = 10.0  # Maximum interval - actual will be random 1.0 to this value
        self.idle_head_base_rotation_range = 0.3
        self.idle_head_look_up_range = 0.4
        self.idle_head_look_down_range = 0.1
        self.idle_head_variation_speed = 4.0
        self.last_idle_head_variation_time = self.node.get_clock().now()
        self.current_idle_head_target = None
        self.idle_head_variation_active = False
        self.idle_base_position = [0.0, -0.55, 1.2, 1.0, 2.0]  # Standard idle position
        
        # Create action client for triggering animations
        self._idle_animation_client = ActionClient(
            self.node,
            PlayAnimation,
            'play_animation'
        )
        # Initialize petting behavior after all other attributes are set
        self.setup_petting_behavior()
        # Voice following parameters
        self.node.declare_parameter('enable_voice_following', True)
        self.node.declare_parameter('voice_follow_speed', 0.3)
        self.node.declare_parameter('voice_follow_deadzone', 15.0)
        self.node.declare_parameter('voice_follow_smoothing', 0.3)
        # Add voice variation parameters
        self.node.declare_parameter('voice_variation_enabled', True)
        self.node.declare_parameter('voice_direction_tolerance', 5.0)
        self.node.declare_parameter('voice_variation_interval', 2.0)
        self.node.declare_parameter('voice_look_up_range', 1.0)  # How far up to look
        self.node.declare_parameter('voice_look_down_range', 0.2)  # How far down to look
        
        self.voice_follow_enabled = self.node.get_parameter('enable_voice_following').value
        self.voice_follow_speed = self.node.get_parameter('voice_follow_speed').value
        self.voice_follow_deadzone = self.node.get_parameter('voice_follow_deadzone').value
        self.voice_follow_smoothing = self.node.get_parameter('voice_follow_smoothing').value
        self.voice_variation_enabled = self.node.get_parameter('voice_variation_enabled').value
        self.voice_direction_tolerance = self.node.get_parameter('voice_direction_tolerance').value
        self.voice_variation_interval = self.node.get_parameter('voice_variation_interval').value
        self.voice_look_up_range = self.node.get_parameter('voice_look_up_range').value
        self.voice_look_down_range = self.node.get_parameter('voice_look_down_range').value
        
        # Voice tracking state
        self.last_voice_direction = None
        self.last_voice_time = self.node.get_clock().now()
        self.voice_influence = 0.0
        self.target_voice_angle = None
        self.voice_active = False
        
        # Voice variation tracking
        self.voice_on_target_start_time = None
        self.last_voice_variation_time = None
        self.current_voice_variation = None
        self.voice_neutral_position = [-0.55, 1.2, 1.0, -2.0, 10.0]  # Baseline position (excluding base)
        self.voice_on_target_threshold = 3.0  # seconds to wait before starting variations
        
        # NEW: Voice command cooldown and direction filtering
        self.voice_command_cooldown = 2.5  # seconds between voice commands
        # Initialize to None to allow immediate first command
        self.last_voice_command_time = None
        self.last_acted_voice_direction = None  # Last direction we actually sent a command for
        self.voice_direction_filter_threshold = 5.0  # degrees - ignore directions within this range
        
        # Create subscribers for voice data
        self.voice_direction_sub = self.node.create_subscription(
            Float32,
            '/voice/follow_direction',
            self.voice_direction_callback,
            10
        )
        
        self.voice_active_sub = self.node.create_subscription(
            Bool,
            '/voice/active', 
            self.voice_active_callback,
            10
        )
        
        self.node.get_logger().info(f"Voice following enabled: {self.voice_follow_enabled}")

    def _state_info_callback(self, msg):
        """Callback for state info updates."""
        with self._state_lock:
            try:
                self._cached_state = LuxoState[msg.current_state]
                self._state_info = msg
            except KeyError:
                self.node.get_logger().error(f"Unknown state received: {msg.current_state}")

    def _get_current_state(self):
        """Get the current state from cache."""
        with self._state_lock:
            if self._cached_state is not None:
                return self._cached_state
        
        # Default to IDLE if we haven't received state yet
        self.node.get_logger().warn("No state info received yet, defaulting to IDLE")
        return LuxoState.IDLE

    def _is_in_state(self, *states):
        """Check if the current state matches any of the given states."""
        current_state = self._get_current_state()
        return current_state in states

    def _transition_to_state(self, new_state):
        """Request a state transition."""
        try:
            request = RequestStateTransition.Request()
            request.requested_state = new_state.name
            request.requesting_node = "collision_avoidance"
            request.priority = 5  # Medium priority for collision avoidance
            request.force = False
            
            future = self.request_state_transition_client.call_async(request)
            # Fire and forget - don't wait for response
            return True
        except Exception as e:
            self.node.get_logger().error(f"Error requesting state transition: {e}")
            return False

    def voice_active_callback(self, msg):
        """Handle voice activity status"""
        self.voice_active = msg.data
        if not msg.data:
            # Start decay when voice stops
            self.voice_influence *= 0.8
    
    def voice_direction_callback(self, msg):
        """Handle voice direction updates with intelligent wraparound and variation"""
        if not self.voice_follow_enabled:
            return
            
        # Only process if in appropriate state
        if not self._is_in_state(LuxoState.IDLE, LuxoState.ANIMATING, LuxoState.EMOTION_REACTING):
            return
        
        current_time = self.node.get_clock().now()
        voice_direction = msg.data
        
        # Check cooldown timer - don't process if we sent a command too recently
        if self.last_voice_command_time is not None:
            time_since_last_command = (current_time - self.last_voice_command_time).nanoseconds / 1e9
            if time_since_last_command < self.voice_command_cooldown:
                remaining_cooldown = self.voice_command_cooldown - time_since_last_command
                self.node.get_logger().debug(
                    f"Voice command on cooldown - {remaining_cooldown:.2f}s remaining "
                    f"(last command: {time_since_last_command:.2f}s ago)"
                )
                return
        
        # Check if direction is too similar to last acted-upon direction
        if self.last_acted_voice_direction is not None:
            direction_diff = abs(voice_direction - self.last_acted_voice_direction)
            # Handle wraparound case (e.g., 359° vs 1°)
            if direction_diff > 180:
                direction_diff = 360 - direction_diff
                
            if direction_diff <= self.voice_direction_filter_threshold:
                self.node.get_logger().debug(
                    f"Ignoring similar voice direction: {voice_direction:.1f}° "
                    f"(last: {self.last_acted_voice_direction:.1f}°, diff: {direction_diff:.1f}°)"
                )
                # Still update tracking but don't send command
                self.last_voice_direction = voice_direction
                self.last_voice_time = current_time
                return
        
        # Update voice tracking
        self.last_voice_direction = voice_direction
        self.last_voice_time = current_time
        
        # REMOVED: Voice following should NOT reset idle timeout
        # This allows idle animations to still trigger while voice following is active
        
        # Increase voice influence more aggressively
        self.voice_influence = min(1.0, self.voice_influence + 0.8)  # Very aggressive following
        
        # Convert voice direction to target angle with intelligent wraparound
        target_angle_rad = np.deg2rad(voice_direction)
        target_angle = self.position_utils.normalize_angle(target_angle_rad)
        
        # Check if we need wraparound due to base limits
        if target_angle > self.base_max_limit:
            if self.enable_base_wraparound:
                # Calculate wraparound path
                wraparound_target = target_angle - 2 * np.pi
                if wraparound_target >= self.base_min_limit:
                    self.target_voice_angle = wraparound_target
                    self.node.get_logger().info(
                        f"Voice at {voice_direction}° beyond max limit - "
                        f"using wraparound to {np.rad2deg(wraparound_target):.1f}°"
                    )
                else:
                    # Even wraparound doesn't work, clamp to nearest reachable
                    self.target_voice_angle = self.base_max_limit
                    self.node.get_logger().warn(
                        f"Voice at {voice_direction}° unreachable - clamping to max limit"
                    )
            else:
                self.target_voice_angle = self.base_max_limit
                self.node.get_logger().warn(f"Voice beyond max limit - clamping (wraparound disabled)")
        elif target_angle < self.base_min_limit:
            if self.enable_base_wraparound:
                # Calculate wraparound path
                wraparound_target = target_angle + 2 * np.pi
                if wraparound_target <= self.base_max_limit:
                    self.target_voice_angle = wraparound_target
                    self.node.get_logger().info(
                        f"Voice at {voice_direction}° beyond min limit - "
                        f"using wraparound to {np.rad2deg(wraparound_target):.1f}°"
                    )
                else:
                    # Even wraparound doesn't work, clamp to nearest reachable
                    self.target_voice_angle = self.base_min_limit
                    self.node.get_logger().warn(
                        f"Voice at {voice_direction}° unreachable - clamping to min limit"
                    )
            else:
                self.target_voice_angle = self.base_min_limit
                self.node.get_logger().warn(f"Voice beyond min limit - clamping (wraparound disabled)")
        else:
            # Target is within normal range
            self.target_voice_angle = target_angle
        
        self.node.get_logger().info(
            f"Voice detected at {voice_direction:.1f}°, "
            f"target angle: {np.rad2deg(self.target_voice_angle):.1f}°, "
            f"sending direct command (influence: {self.voice_influence:.2f})"
        )
        
        # SEND COMMAND IMMEDIATELY with the calculated target
        self._send_voice_following_command()
        
        # Update tracking for cooldown and filtering
        self.last_voice_command_time = current_time
        self.last_acted_voice_direction = voice_direction

    def _check_voice_on_target(self):
        """Check if robot is pointing at voice direction and start variation timer"""
        if not self.voice_variation_enabled or self.target_voice_angle is None:
            return False
            
        current_base = self.current_joints[0] if self.current_joints else 0.0
        angle_diff = abs(self.position_utils.normalize_angle(self.target_voice_angle - current_base))
        angle_diff_deg = np.rad2deg(angle_diff)
        
        current_time = self.node.get_clock().now()
        
        if angle_diff_deg <= self.voice_direction_tolerance:
            # We're on target
            if self.voice_on_target_start_time is None:
                self.voice_on_target_start_time = current_time
                self.node.get_logger().info(f"Voice on target - starting variation timer (diff: {angle_diff_deg:.1f}°)")
            return True
        else:
            # We're not on target, reset timer
            if self.voice_on_target_start_time is not None:
                self.node.get_logger().debug(f"Voice off target - resetting timer (diff: {angle_diff_deg:.1f}°)")
            self.voice_on_target_start_time = None
            self.current_voice_variation = None
            return False

    def _should_add_voice_variation(self):
        """Check if we should add variation to voice following"""
        if not self.voice_variation_enabled:
            return False
            
        if not self._check_voice_on_target():
            return False
            
        current_time = self.node.get_clock().now()
        
        # Check if we've been on target long enough
        if self.voice_on_target_start_time is None:
            return False
            
        time_on_target = (current_time - self.voice_on_target_start_time).nanoseconds / 1e9
        if time_on_target < self.voice_on_target_threshold:
            return False
        
        # Check if enough time has passed since last variation
        if self.last_voice_variation_time is not None:
            time_since_variation = (current_time - self.last_voice_variation_time).nanoseconds / 1e9
            if time_since_variation < self.voice_variation_interval:
                return False
        
        return True

    def _generate_voice_variation(self):
        """Generate semi-random up/down movement for voice following"""
        current_time = self.node.get_clock().now()
        
        # Generate random variation - bias towards looking up for face detection
        # 70% chance to look up, 20% chance to look down, 10% chance to return to neutral
        variation_type = random.random()
        
        if variation_type < 0.85:  # Look up (85% chance)
            # Look up with some randomness - semi dramatic but not too much
            shoulder_variation = random.uniform(0.2, self.voice_look_up_range)
            elbow_variation = random.uniform(-0.2, 0.2)  # Small elbow adjustment
            wrist_variation = random.uniform(-0.4, 0.0)  # Slight wrist adjustment to help with head angle
            variation_description = "looking up"
        elif variation_type < 0.95:  # Look down (10% chance)
            # Look down slightly
            shoulder_variation = random.uniform(-self.voice_look_down_range, -0.05)
            elbow_variation = random.uniform(-0.05, 0.05)
            wrist_variation = random.uniform(0.0, 0.1)
            variation_description = "looking down"
        else:  # Return to neutral (5% chance)
            shoulder_variation = 0.0
            elbow_variation = 0.0
            wrist_variation = 0.0
            variation_description = "returning to neutral"
        
        # Create varied position based on neutral
        varied_position = self.voice_neutral_position.copy()
        varied_position[0] += shoulder_variation  # Shoulder (index 1 in full array)
        varied_position[1] += elbow_variation     # Elbow (index 2 in full array)
        varied_position[2] += wrist_variation     # Wrist (index 3 in full array)
        # Keep hand and acceleration the same
        
        self.current_voice_variation = varied_position
        self.last_voice_variation_time = current_time
        
        self.node.get_logger().info(
            f"Voice variation: {variation_description} "
            f"(shoulder: {shoulder_variation:+.2f}, elbow: {elbow_variation:+.2f}, wrist: {wrist_variation:+.2f})"
        )
        
        return varied_position

    def _send_voice_following_command(self):
        """Send direct voice following command to target angle with optional variation"""
        if not self.voice_follow_enabled or self.voice_influence < 0.1:
            return
            
        if self.target_voice_angle is None:
            return
        
        # Create position with DIRECT target angle - no adjustments
        voice_position = self.current_joints.copy()
        voice_position[0] = self.target_voice_angle  # Set base directly to target
        
        # Check if we should add variation
        if self._should_add_voice_variation():
            variation = self._generate_voice_variation()
            # Apply variation to joints 1-4 (shoulder, elbow, wrist, hand)
            for i in range(1, min(5, len(voice_position))):
                if i-1 < len(variation):
                    voice_position[i] = variation[i-1]
            self.node.get_logger().info("Applied voice following variation for face detection")
        elif self.current_voice_variation is not None:
            # Continue using current variation if we have one
            for i in range(1, min(5, len(voice_position))):
                if i-1 < len(self.current_voice_variation):
                    voice_position[i] = self.current_voice_variation[i-1]
        else:
            # Use neutral position for non-base joints
            for i in range(1, min(5, len(voice_position))):
                if i-1 < len(self.voice_neutral_position):
                    voice_position[i] = self.voice_neutral_position[i-1]
        
        # Ensure we only have 5 joint positions, then add acceleration as 6th element
        if len(voice_position) > 5:
            voice_position = voice_position[:5]  # Truncate to 5 joints
        
        # Add acceleration as the 6th element
        voice_position_with_accel = voice_position + [7.0]
        
        self.node.get_logger().info(
            f"Sending voice command: base to {np.rad2deg(self.target_voice_angle):.1f}° "
            f"with position: {[round(p, 2) for p in voice_position]}"
        )
        
        # Send the command with high priority
        self.send_safe_joint_command(voice_position_with_accel, "Voice following with variation")
        
        # Set this as a target override to prevent other systems from interfering
        self.target_override_active = True
        self.target_override_time = self.node.get_clock().now()
        self.target_override_joints = voice_position.copy()
        self.target_override_reason = "Voice following with face detection"
        self.target_override_timeout = 3.0  # Short timeout for voice following
        
        # REMOVED: Do not update activity time for voice following
        # This prevents voice following from interfering with idle animation timing
    
    def apply_voice_following(self, positions):
        """Apply direct voice following to joint positions with variation support"""
        if not self.voice_follow_enabled or self.voice_influence < 0.1:
            # If no voice following, check if we should maintain idle head variation
            if (self.idle_head_variation_active and 
                self.current_idle_head_target and 
                self._is_in_state(LuxoState.IDLE)):
                
                # Continue using the idle head variation target
                return self.current_idle_head_target.copy()
            return positions
            
        # Check if in escape mode or returning home - don't apply voice following
        if self._is_in_state(LuxoState.ESCAPE_MODE, LuxoState.RETURNING_HOME):
            return positions
        
        # Clear any idle head variation when voice following starts
        if self.idle_head_variation_active:
            self.idle_head_variation_active = False
            self.current_idle_head_target = None
            self.node.get_logger().debug("Cleared idle head variation for voice following")
            
        # Check voice timeout
        if self.last_voice_time:
            current_time = self.node.get_clock().now()
            time_since_voice = (current_time - self.last_voice_time).nanoseconds / 1e9
            
            if time_since_voice > 2.0:  # 2 second timeout
                self.voice_influence = 0.0
                self.target_voice_angle = None
                self.voice_on_target_start_time = None
                self.current_voice_variation = None
                return positions
        
        # Apply DIRECT voice following - no gradual adjustment
        if self.target_voice_angle is not None:
            adjusted_positions = positions.copy()
            
            # Set base joint DIRECTLY to target angle
            adjusted_positions[0] = self.target_voice_angle
            
            # Apply variation if we have one
            if self.current_voice_variation is not None:
                for i in range(1, min(5, len(adjusted_positions))):
                    if i-1 < len(self.current_voice_variation):
                        adjusted_positions[i] = self.current_voice_variation[i-1]
            
            # Check if we've reached the target
            current_base = self.current_joints[0] if self.current_joints else 0.0
            angle_diff = abs(self.position_utils.normalize_angle(self.target_voice_angle - current_base))
            
            if angle_diff < 0.1:  # Within ~6 degrees
                # Don't immediately clear - let variation system handle it
                self.node.get_logger().debug("Voice target reached, maintaining for variation")
                
            return adjusted_positions
            
        return positions

    def set_active_animation(self, animation_name, allow_interruption=True):
        """Track the currently active animation."""
        with self.animation_lock:
            # Only log if animation name is actually changing
            if self.current_animation_name != animation_name:
                self.current_animation_name = animation_name
                self.animation_allow_interruption = allow_interruption
                self.animation_preempted = False
                self.node.get_logger().debug(f"Tracking animation: {animation_name} (interruptible: {allow_interruption})")
                
                # Reset activity time when animation starts to prevent idle timeout
                self.last_activity_time = self.node.get_clock().now()
                
                # If we're currently returning to home, cancel it immediately
                if self._is_in_state(LuxoState.RETURNING_HOME):
                    self.node.get_logger().info("Animation starting - cancelling return to home operation")
                    self.target_override_active = False
                    self._transition_to_state(LuxoState.ANIMATING)
                    
            # If same animation, just update the interruption flag if needed
            elif self.animation_allow_interruption != allow_interruption:
                self.animation_allow_interruption = allow_interruption
                self.node.get_logger().debug(f"Updated interruption flag for {animation_name}: {allow_interruption}")

    
    def clear_active_animation(self):
        """Clear the active animation tracking."""
        with self.animation_lock:
            if self.current_animation_name:
                self.node.get_logger().info(f"Animation {self.current_animation_name} completed")
            self.current_animation_name = None
            self.animation_progress = 0.0
            self.animation_preempted = False
    
    
    def should_preempt_animation(self, severity="warning"):
        """Determine if current animation should be preempted."""
        with self.animation_lock:
            if not self.current_animation_name:
                return False
            
            # Don't preempt if not allowed
            if not self.animation_allow_interruption:
                return False
            
            # Only preempt for danger, not warnings
            if severity != "danger":
                return False
            
            # Don't preempt same animation repeatedly
            time_since_preemption = (self.node.get_clock().now() - self.animation_preemption_time).nanoseconds / 1e9
            if self.animation_preempted and time_since_preemption < 2.0:
                return False
            
            return True

    def validate_animation_keyframe(self, keyframe, animation_name=None):
        """
        Check if a keyframe is safe to execute given current collision status.
        
        Args:
            keyframe: List of joint positions [base, shoulder, elbow, wrist, hand]
            animation_name: Optional name for animation-specific handling
            
        Returns:
            Tuple of (is_safe, adjusted_keyframe, severity)
        """
        # Use MovementValidator to check safety
        is_safe, reason = MovementValidator.check_movement_safety(
            self.current_joints, keyframe, self.collision_status
        )
        
        # Validate and adjust the keyframe
        adjusted_keyframe = MovementValidator.validate_position(keyframe, self.safety_limits)
        
        # Determine severity based on collision status
        severity = "safe"
        with self.collision_lock:
            for direction, status in self.collision_status.items():
                if status['active'] and status['severity'] == 'danger':
                    severity = "danger"
                    break
                elif status['active'] and status['severity'] == 'warning':
                    severity = "warning"
        
        # Log adjustments if any were made
        if not is_safe:
            self.node.get_logger().debug(f"Animation keyframe adjusted: {reason}")
        
        return is_safe, adjusted_keyframe, severity
    
    def get_animation_collision_status(self):
        """Return collision status formatted for animation feedback."""
        with self.collision_lock:
            active_collisions = []
            
            if self.collision_status['front']['active']:
                active_collisions.append(f"front:{self.collision_status['front']['severity']}")
            if self.collision_status['left']['active']:
                active_collisions.append(f"left:{self.collision_status['left']['severity']}")
            if self.collision_status['right']['active']:
                active_collisions.append(f"right:{self.collision_status['right']['severity']}")
            
            if not active_collisions:
                return "safe"
            elif any('danger' in c for c in active_collisions):
                return "danger:" + ",".join(active_collisions)
            else:
                return "warning:" + ",".join(active_collisions)
    
    def update_current_joints(self, joints):
        """Update the current joint positions."""
        self.current_joints = joints.copy()
    
    def update_target_joints(self, joints):
        """Update the target joint positions."""
        # Check if position has changed enough to update activity time
        current_time = self.node.get_clock().now()
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
            # Don't count idle-specific movements as breaking idleness
            is_idle_movement = (self.target_override_active and 
                               self.target_override_reason and
                               "idle head variation" in self.target_override_reason.lower())
            
            if not is_idle_movement:
                self.last_activity_time = current_time
                self.node.get_logger().debug(f"Activity timestamp updated due to significant joint position change")
            else:
                self.node.get_logger().debug(f"Idle head variation detected - not updating activity timestamp")
            
        # MODIFIED: Only clear collision-related overrides for VERY significant target changes
        # This prevents clearing overrides when the system is just updating with the same target
        if self.target_override_active:
            is_collision_override = ("collision" in self.target_override_reason.lower() or 
                                "avoidance" in self.target_override_reason.lower() or
                                "escape" in self.target_override_reason.lower())
            
            if is_collision_override:
                # For collision overrides, only clear if the new target is very different
                distance = self.position_utils.calculate_position_distance(joints, self.target_override_joints)
                if distance > 0.5:  # Much higher threshold for collision overrides
                    self.node.get_logger().info(f"Major target change detected (distance: {distance:.3f}) - clearing collision override")
                    self.target_override_active = False
                    self.target_override_joints = None
                else:
                    self.node.get_logger().debug(f"Minor target change (distance: {distance:.3f}) - keeping collision override active")
            else:
                # For non-collision overrides, use the original logic
                distance = self.position_utils.calculate_position_distance(joints, self.target_override_joints)
                if distance > 0.1:
                    self.node.get_logger().info(f"New target received - clearing non-collision override")
                    self.target_override_active = False
                    self.target_override_joints = None
        
        # Update the timestamp for target changes
        self.last_original_target_change_time = current_time
    
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
                current_time = self.node.get_clock().now()
                
                # Track persistent head collision even when returning home
                if direction == 'front':
                    if is_active and self.collision_status[direction]['severity'] == 'danger':
                        # Start timing persistent head collision if not already tracking
                        if not self.persistent_head_collision_active:
                            self.persistent_head_collision_start = current_time
                            self.persistent_head_collision_active = True
                            self.node.get_logger().info("Started tracking persistent head collision")
                        # Throttle logs for persistent collisions
                        else:
                            time_since_log = (current_time - self.persistent_head_collision_last_log).nanoseconds / 1e9
                            if time_since_log > 2.0:
                                duration = (current_time - self.persistent_head_collision_start).nanoseconds / 1e9
                                self.node.get_logger().info(f"Persistent head collision ongoing for {duration:.1f}s")
                                self.persistent_head_collision_last_log = current_time
                    else:
                        # Reset persistent head collision tracking
                        if self.persistent_head_collision_active:
                            self.node.get_logger().info("Persistent head collision cleared")
                            self.persistent_head_collision_active = False
                
                # If we're already returning to home, just track state but don't react to collisions
                # This prevents collision reactions from interrupting the return to home
                if self._is_in_state(LuxoState.RETURNING_HOME):
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
                    
                    # Transition to COLLISION_AVOIDING state
                    self._transition_to_state(LuxoState.COLLISION_AVOIDING)
                    
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
                    
                    # Check if all collisions are cleared
                    if not any(status['active'] for status in self.collision_status.values()):
                        # Transition back to IDLE if no collisions remain
                        if self._is_in_state(LuxoState.COLLISION_AVOIDING):
                            self._transition_to_state(LuxoState.IDLE)
                    return
                    
                # Update the active state
                self.collision_status[direction]['active'] = is_active
                
                if is_active:  # If collision is still active
                    # Check if an adjustment was recently made before increasing count
                    adjustment_made = self.adjustment_history[direction]['adjustment_made']
                    time_since_adjustment = (current_time - self.adjustment_history[direction]['last_time']).nanoseconds / 1e9
                    
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
                            if not self._is_in_state(LuxoState.ESCAPE_MODE):
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
            
            # Use CollisionMath to calculate severity
            severity = CollisionMath.calculate_severity(
                distance, 
                danger_threshold=self.hard_limit_distance,
                warning_threshold=self.soft_limit_distance
            )
            self.collision_status[direction]['severity'] = severity
            
            # Fast reaction path: If distance is critically low and we haven't reacted recently
            current_time = self.node.get_clock().now()
            
            # Enhanced trigger conditions: react when distance DECREASES below threshold
            distance_getting_smaller = old_distance == float('inf') or distance < old_distance
            time_since_collision = TimeUtils.get_elapsed_time(self.node, self.last_collision_time)
            
            if (distance <= self.hard_limit_distance and 
                distance_getting_smaller and
                time_since_collision > 0.25 and  # Prevent rapid reactions
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
    
    def update_severity(self, direction, severity):
        """Update severity information with immediate reaction for danger."""
        with self.collision_lock:
            old_severity = self.collision_status[direction]['severity']
            self.collision_status[direction]['severity'] = severity
            
            # Update persistent head collision tracking for front direction
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
            
            # Fast reaction path: If severity changed to danger, react immediately
            if severity == 'danger' and old_severity != 'danger':
                current_time = self.node.get_clock().now()
                time_since_collision = TimeUtils.get_elapsed_time(self.node, self.last_collision_time)
                if time_since_collision > 0.25:  # Prevent too rapid reactions
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

    def _at_home_position(self, current_pos, home_pos, tolerance):
        """Check if robot is at a home position, ignoring base joint."""
        return self.position_utils.at_home_position(current_pos, home_pos, tolerance, ignore_base=True)
    
    def safety_monitor_callback(self):
        """Periodic callback to monitor safety and adjust motion if needed"""
        if not self.enable_collision_avoidance:
            self.node.get_logger().debug(f"Collision avoidance disabled - skipping safety check")
            return
            
        try:
            # Get current time for this check cycle
            current_time = self.node.get_clock().now()
            
            # Handle petting state updates and timeout detection
            if self.check_petting_timeout(current_time):
                return
            
            # Check if target override is stuck (not in RETURNING_HOME state)
            if self.target_override_active and not self._is_in_state(LuxoState.RETURNING_HOME):
                # Don't clear voice following overrides too quickly
                if self.target_override_reason != "Voice following":
                    override_duration = (current_time - self.target_override_time).nanoseconds / 1e9
                    if override_duration > 30.0:  # 30 second timeout
                        self.node.get_logger().warn(f"Clearing stuck target override after {override_duration:.1f} seconds")
                        self.target_override_active = False
                        self.target_override_joints = None
                        self.target_override_reason = "Cleared due to timeout"
            
            # Check if we're currently trying to go home and handle timeouts
            if self._is_in_state(LuxoState.RETURNING_HOME):
                time_since_home_attempt = (current_time - self.returning_to_home_start_time).nanoseconds / 1e9
                if time_since_home_attempt > self.idle_timeout:
                    self.node.get_logger().warn(f"Home position return timeout after {time_since_home_attempt:.1f}s - giving up")
                    # Clear ALL home-related flags
                    self.target_override_active = False
                    self.target_override_joints = None
                    self.home_position_stage = 1
                    self.persistent_head_collision_active = False
                    self.is_returning_to_rest = False
                    # Transition back to IDLE
                    self._transition_to_state(LuxoState.IDLE)
                    # Reset other state variables for clean slate
                    self.escape_attempts = 0
                    with self.collision_lock:
                        for direction in self.collision_status:
                            self.collision_status[direction]['consecutive_count'] = 0
                    return  # Skip other checks when timing out
                
                # Check for home position stage transitions
                if self.target_override_active and self.target_override_joints is not None:
                    # Check if we're in stage 1 and at home_position_1
                    if self.home_position_stage == 1:
                        # Calculate current position difference from home_position_1
                        # Preserve base position when comparing
                        mod_home_1 = self.home_position_1.copy()
                        mod_home_1[0] = self.current_joints[0]  # Use current base position
                        
                        if self._at_home_position(self.current_joints, self.home_position_1, self.home_position_tolerance):
                            # Initialize stage change time if not set
                            if not hasattr(self, '_stage1_reached_time'):
                                self._stage1_reached_time = current_time
                                self.node.get_logger().info(f"Reached home_position_1, waiting {self.home_position_stage_timeout}s before stage 2")
                            
                            # Check if we've waited long enough
                            time_at_stage1 = (current_time - self._stage1_reached_time).nanoseconds / 1e9
                            if time_at_stage1 >= self.home_position_stage_timeout:
                                self.node.get_logger().info(f"Transitioning to home_position_2 after {time_at_stage1:.1f}s at position 1")
                                
                                # Transition to stage 2
                                self.home_position_stage = 2
                                delattr(self, '_stage1_reached_time')  # Clean up the timer
                                
                                # Preserve current base position
                                mod_home_2 = self.home_position_2.copy()
                                mod_home_2[0] = self.current_joints[0]
                                
                                # Add slight random variation
                                noise_range = 0.05
                                home_with_variation = [
                                    mod_home_2[i] + (0 if i == 0 else random.uniform(-noise_range, noise_range))
                                    for i in range(len(mod_home_2))
                                ]
                                
                                # Update target override
                                self.target_override_joints = home_with_variation
                                self.target_override_time = current_time
                                self.target_override_reason = "Home position sequence stage 2"
                                
                                # Send command to move to stage 2
                                self.send_safe_joint_command(home_with_variation, "Home position stage 2")
                        else:
                            # Not at position 1, reset timer
                            if hasattr(self, '_stage1_reached_time'):
                                delattr(self, '_stage1_reached_time')
                    
                    # Check if we're in stage 2 and at home_position_2
                    elif self.home_position_stage == 2:
                        mod_home_2 = self.home_position_2.copy()
                        mod_home_2[0] = self.current_joints[0]  # Use current base position
                        
                        if self._at_home_position(self.current_joints, self.home_position_2, self.home_position_tolerance):
                            self.node.get_logger().info("Successfully reached final home position (stage 2)")
                            # Clear all flags
                            self.target_override_active = False
                            self.target_override_joints = None
                            self.persistent_head_collision_active = False
                            self.is_returning_to_rest = False
                            # Transition back to IDLE
                            self._transition_to_state(LuxoState.IDLE)
                            # Reset collision counters
                            with self.collision_lock:
                                for direction in self.collision_status:
                                    self.collision_status[direction]['consecutive_count'] = 0
                
                return  # Skip other checks when returning to home
            
            # Check persistent head collision duration
            if self.persistent_head_collision_active:
                head_collision_duration = (current_time - self.persistent_head_collision_start).nanoseconds / 1e9
                # Log the duration periodically
                time_since_log = (current_time - self.persistent_head_collision_last_log).nanoseconds / 1e9
                if time_since_log > 1.0:
                    self.node.get_logger().info(f"Persistent head collision duration: {head_collision_duration:.1f}s")
                    self.persistent_head_collision_last_log = current_time
                
                # Check if we need to return to home based on collision duration
                if head_collision_duration > self.extended_collision_timeout:
                    self.node.get_logger().warn(f"Persistent head collision for over {self.extended_collision_timeout:.1f}s - returning to home position")
                    # Force go to home by transitioning to RETURNING_HOME state
                    self._transition_to_state(LuxoState.RETURNING_HOME)
                    self.returning_to_home_start_time = current_time
                    self.go_to_home_position("Extended persistent head collision - return to home")
                    return  # Skip remaining checks as we're already taking action
                elif head_collision_duration > self.short_collision_timeout:
                    # First try more moderate correction for shorter duration collisions
                    if not self._is_in_state(LuxoState.ESCAPE_MODE):
                        self.node.get_logger().warn(f"Persistent head collision for {head_collision_duration:.1f}s - attempting escape mode")
                        self._activate_escape_mode('front')
                        return  # Skip remaining checks as we're already taking action
            
            # Check idle timeout for idle animations
            if self.idle_check_active and not any(status['active'] for status in self.collision_status.values()):
                time_since_activity = (current_time - self.last_activity_time).nanoseconds / 1e9
                time_since_last_animation = (current_time - self.last_idle_animation_time).nanoseconds / 1e9
                
                # UPDATED: Voice following should not prevent idle animations
                # Only log when voice is very active (multiple recent detections)
                voice_very_active = False
                if hasattr(self, 'voice_active') and self.voice_active and hasattr(self, 'last_voice_time'):
                    if self.last_voice_time is not None:
                        time_since_voice = (current_time - self.last_voice_time).nanoseconds / 1e9
                    else:
                        # If no voice time recorded yet, set to a large value to allow voice
                        time_since_voice = float('inf')
                    voice_very_active = time_since_voice < 2.0  # Only consider very recent voice activity
                
                if voice_very_active:
                    self.node.get_logger().debug("Very recent voice activity - allowing idle animations to coexist")
                
                # Check if we're already at or very close to home positions
                already_at_home2 = self._at_position(self.current_joints, self.home_position_2, self.home_position_tolerance)
                
                # If we've been idle for a while and enough time has passed since last animation
                if (time_since_activity > self.min_idle_time_before_animation and 
                    time_since_last_animation > self.idle_animation_interval and
                    self._is_in_state(LuxoState.IDLE) and
                    getattr(self, 'idle_animations_enabled', True)):  # Check if enabled
                    
                    self.node.get_logger().info(f"Device idle for {time_since_activity:.1f}s - triggering idle animation (voice influence: {getattr(self, 'voice_influence', 0.0):.2f})")
                    
                    # Trigger a random idle animation
                    self.trigger_idle_animation()
                    
                    # Update timers
                    self.last_idle_animation_time = current_time
                    self.idle_animation_interval = random.uniform(10.0, 60.0)  # Random interval for next animation
                    
                # Still check for extended idle to return home eventually
                elif time_since_activity > 120.0 and not already_at_home2:  # 2 minutes
                    self.node.get_logger().info(f"Extended idle timeout - returning to home position")
                    self._transition_to_state(LuxoState.RETURNING_HOME)
                    self.returning_to_home_start_time = current_time
                    self.go_to_home_position("Extended idle timeout")
                    return
                
                # Check for idle head variation (only if no major idle animations are happening AND no active voice following)
                elif (self._should_apply_idle_head_variation() and 
                      time_since_last_animation > 5.0 and
                      not (hasattr(self, 'voice_influence') and self.voice_influence > 0.1)):  # Don't conflict with voice following
                    self.trigger_idle_head_variation()
            
            # Fast path: Check if there are any active collisions or we're in escape mode
            with self.collision_lock:
                any_collision_active = any(status['active'] for status in self.collision_status.values())
                any_persistent_collision = any(status['consecutive_count'] > 5 for status in self.collision_status.values())
                
                # If nothing needs attention, return early to reduce overhead
                if not any_collision_active and not any_persistent_collision and not self._is_in_state(LuxoState.ESCAPE_MODE):
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
            if self._is_in_state(LuxoState.ESCAPE_MODE):
                # Check if escape mode has been active too long
                escape_duration = (current_time - self.escape_mode_start_time).nanoseconds / 1e9
                if escape_duration > self.escape_mode_duration:
                    # Transition back to IDLE
                    self._transition_to_state(LuxoState.IDLE)
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
                                # Transition back to IDLE
                                self._transition_to_state(LuxoState.IDLE)
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
                self.node.get_logger().debug(f"Attempting path adjustment for active collisions: Front={front_status['active']}, Left={left_status['active']}, Right={right_status['active']}")
                # Calculate a safe adjustment vector based on collision directions
                self.adjust_path_for_collision(front_status, left_status, right_status)
        
        except Exception as e:
            self.node.get_logger().error(f"Error in safety monitor: {e}")
            
            # Add stack trace for better debugging
            import traceback
            self.node.get_logger().error(f"Stack trace: {traceback.format_exc()}")

    def perform_collision_avoidance(self, direction, distance, emergency=False):
        """Perform collision avoidance with rotation limit awareness and dynamic acceleration."""
        # Update activity time when performing collision avoidance
        current_time = self.node.get_clock().now()
        self.last_activity_time = current_time
        
        if emergency and self.should_preempt_animation("danger"):
            with self.animation_lock:
                self.animation_preempted = True
                self.animation_preemption_time = current_time
                self.node.get_logger().warn(f"Animation '{self.current_animation_name}' should be preempted due to {direction} collision")
        
        self.node.get_logger().debug(f"Activity timestamp updated due to collision avoidance action")
        
        # Report collision movement source for DEMA coordination
        self._publish_movement_source("collision")
        
        try:
            # Start with current position
            new_position = self.current_joints.copy()
            
            # Get the consecutive count for this direction
            consecutive_count = self.collision_status[direction]['consecutive_count']
            severity = self.collision_status[direction]['severity']
            
            # Use CollisionMath to calculate acceleration and magnitude
            acceleration = CollisionMath.calculate_acceleration(
                severity, consecutive_count, base_acceleration=12.5
            )
            
            magnitude = CollisionMath.calculate_avoidance_magnitude(
                severity, consecutive_count, emergency
            )
            
            self.node.get_logger().info(f"Using acceleration {acceleration} and magnitude {magnitude:.2f} for {direction} collision")
            
            # Get current base position and check limits
            current_base = new_position[0]
            near_min_limit = self.safety_limits.is_near_base_limit(current_base) == 'min'
            near_max_limit = self.safety_limits.is_near_base_limit(current_base) == 'max'
            at_min_limit = self.safety_limits.is_at_base_limit(current_base) == 'min'
            at_max_limit = self.safety_limits.is_at_base_limit(current_base) == 'max'
            
            if direction == 'front':
                # Pull back shoulder and elbow
                new_position[1] -= 0.6 * magnitude  # Shoulder back
                new_position[2] += 0.4 * magnitude  # Elbow fold
                
                # Use CollisionMath for escape rotation
                if consecutive_count > 5:
                    # For persistent collisions, use smarter rotation with wraparound support
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
                        rotation = -abs(rotation)  # Force toward min
                    elif near_min_limit:
                        rotation = abs(rotation)   # Force toward max
                        
                new_position[0] += rotation
                
            elif direction == 'left':
                rotation = CollisionMath.calculate_escape_rotation(direction, 0.4, magnitude)
                if at_min_limit and self.enable_base_wraparound:
                    new_position[0] = self.base_max_limit - 0.2
                    self.node.get_logger().info("Left collision at min limit - wraparound to max side")
                elif at_min_limit:
                    new_position[0] += abs(rotation) * 1.5  # Force opposite direction
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
                    new_position[0] += rotation * 1.5  # Force opposite direction
                    self.node.get_logger().info("Right collision at max limit - rotating LEFT instead")
                else:
                    new_position[0] += rotation
                new_position[1] += 0.1 * magnitude
            
            # Use SafetyLimits to clamp base position
            new_position[0] = self.safety_limits.clamp_base_angle(new_position[0])
            
            # Validate the entire position
            new_position = MovementValidator.validate_position(new_position, self.safety_limits)
            
            # Add acceleration to the position array for the command
            new_position_with_acceleration = new_position.copy() + [acceleration]
            
            # Send command with high priority and dynamic acceleration
            self.send_safe_joint_command(new_position_with_acceleration, f"Collision avoidance (count: {consecutive_count}, accel: {acceleration})")
            
            # Create a persistent override
            self.target_override_active = True
            self.target_override_time = current_time
            self.target_override_joints = new_position.copy()
            self.target_override_reason = f"Collision avoidance for {direction} at {distance:.1f}cm (accel: {acceleration})"
            self.target_joints = new_position.copy()
            
            # If emergency and avoidance doesn't work after multiple attempts, schedule rest return
            if emergency and consecutive_count > self.escape_threshold:
                self.node.get_logger().warn(f"Multiple path adjustments failed, will return to rest position")
                self.go_to_rest_position("Emergency rest return")
                
                # Reset collision counts after going to rest
                with self.collision_lock:
                    for direction in self.collision_status:
                        self.collision_status[direction]['consecutive_count'] = 0
            
            self.node.get_logger().warn(f"Collision avoidance COMPLETED for {direction} at {distance:.1f}cm with acceleration {acceleration}")
            
        except Exception as e:
            self.node.get_logger().error(f"Error in collision avoidance: {e}")

    def _at_position(self, position1, position2=None, tolerance=0.05):
        """Check if two positions are the same within tolerance."""
        if position2 is None:
            position2 = self.current_joints
        
        # Use shared utility
        return self.position_utils.at_position(position1, position2, tolerance)
    
    def get_effective_target_position(self, original_target):
        """Determine which target position to use based on overrides and safety."""
        current_time = self.node.get_clock().now()
        
        # When returning to home, always return the home position override
        if self._is_in_state(LuxoState.RETURNING_HOME) and self.target_override_active and self.target_override_joints is not None:
            # Log that we're enforcing home position override (throttled)
            time_since_log = (current_time - self.last_home_override_log).nanoseconds / 1e9
            if time_since_log > 5.0:  # Increased from 1.0 to reduce log spam
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
                elif self._at_home_position(self.current_joints, self.home_position_2, self.home_position_tolerance):
                    # We've successfully reached the final home position
                    self.node.get_logger().debug("Successfully reached final home position (stage 2)")
                    # Transition back to IDLE will be handled in safety_monitor_callback
            
            # Always return the override position when in home movement sequence
            return self.target_override_joints
        
        # Regular override handling
        if not self.target_override_active or self.target_override_joints is None:
            # VOICE FOLLOWING ADDITION: Apply voice following to the original target
            return self.apply_voice_following(original_target)
        
        # MODIFIED: Only clear override for SIGNIFICANT target changes, not just any difference
        # Check if we have a genuinely NEW target that's significantly different from our current override position
        override_to_new_target_distance = self.position_utils.calculate_position_distance(original_target, self.target_override_joints)
        
        # Only clear override if the new target is significantly different from where we currently are
        # This prevents returning to the original position just because collisions cleared
        if override_to_new_target_distance > 0.3:  # Significant movement required (increased from 0.05)
            self.node.get_logger().info(f"Significant new target detected (distance: {override_to_new_target_distance:.3f}) - clearing collision override")
            self.target_override_active = False
            # Update our internal target to the new position
            self.target_joints = original_target.copy()
            return self.apply_voice_following(original_target)
        
        # MODIFIED: Don't automatically clear overrides just because collisions are gone
        # Instead, make the collision avoidance position the "new normal"
        any_collision_active = any(self.collision_status[direction]['active'] for direction in self.collision_status)
        override_duration = (current_time - self.target_override_time).nanoseconds / 1e9
        
        # Only clear collision avoidance overrides for very specific reasons:
        # 1. If it's been a very long time (extended timeout)
        # 2. If it's a non-collision override that has timed out
        is_collision_override = ("collision" in self.target_override_reason.lower() or 
                            "avoidance" in self.target_override_reason.lower() or
                            "escape" in self.target_override_reason.lower())
        
        if not is_collision_override and override_duration > self.target_override_timeout:
            # Non-collision overrides (like voice following) can still timeout normally
            self.node.get_logger().debug(f"Non-collision override expired after {override_duration:.1f}s")
            self.target_override_active = False
            return self.apply_voice_following(original_target)
        elif is_collision_override and override_duration > 60.0:  # Much longer timeout for collision overrides
            # Only clear collision overrides after a very long time of no new commands
            self.node.get_logger().info(f"Collision override cleared after extended timeout ({override_duration:.1f}s)")
            self.target_override_active = False
            # Make the collision avoidance position the new "normal" target
            self.target_joints = self.target_override_joints.copy()
            return self.apply_voice_following(self.target_joints)
        
        # Continue using the override position - this makes collision avoidance positions "stick"
        return self.apply_voice_following(self.target_override_joints)
    
    def apply_safety_limits(self, positions):
        """Apply safety limits to joint positions based on collision status."""
        # If returning to home position, don't apply collision-based safety limits
        if self._is_in_state(LuxoState.RETURNING_HOME):
            return positions
            
        # Use MovementValidator to validate the position
        validated_positions = MovementValidator.validate_position(positions, self.safety_limits)
        
        # Additional collision-based restrictions
        safe_positions = validated_positions.copy()
        
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
                safe_positions[0] = self.current_joints[0]
            elif (severity == 'warning' or distance <= self.soft_limit_distance) and safe_positions[0] > self.current_joints[0]:
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
                safe_positions[0] = self.current_joints[0]
            elif (severity == 'warning' or distance <= self.soft_limit_distance) and safe_positions[0] < self.current_joints[0]:
                limit_factor = min(1.0, (distance - self.hard_limit_distance) / 
                                (self.soft_limit_distance - self.hard_limit_distance))
                delta = self.current_joints[0] - safe_positions[0]
                safe_positions[0] = self.current_joints[0] - (delta * limit_factor)
        
        return safe_positions
    
    def adjust_path_for_collision(self, front_status, left_status, right_status):
        """Adjust the current motion path to avoid obstacles."""
        # Skip if we're returning to home - don't adjust the home positioning
        if self._is_in_state(LuxoState.RETURNING_HOME):
            return
            
        # Update activity time when adjusting path
        current_time = self.node.get_clock().now()
        self.last_activity_time = current_time
        self.node.get_logger().debug(f"Activity timestamp updated due to collision path adjustment")
        
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
            (current_time - self.adjustment_history['right']['last_time']).nanoseconds / 1e9 < self.adjustment_cooldown and
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
            time_since_adjustment = (current_time - self.adjustment_history['right']['last_time']).nanoseconds / 1e9
            self.node.get_logger().debug(f"Skipping right adjustment - on cooldown ({time_since_adjustment:.1f}s)")
            
            # If we've been in cooldown for a while and still have collisions, reset
            if time_since_adjustment > (self.adjustment_cooldown * 0.75):
                # Artificially decrease the consecutive count to prevent escalation
                with self.collision_lock:
                    # Don't reset completely, but prevent unlimited growth
                    if self.collision_status['right']['consecutive_count'] > 3:
                        self.collision_status['right']['consecutive_count'] = 3
                        self.node.get_logger().info("Adjusting right collision count to prevent escalation")
        
        # Check for cooldown period on left adjustments
        left_cooldown_active = (
            (current_time - self.adjustment_history['left']['last_time']).nanoseconds / 1e9 < self.adjustment_cooldown and
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
            time_since_adjustment = (current_time - self.adjustment_history['left']['last_time']).nanoseconds / 1e9
            self.node.get_logger().debug(f"Skipping left adjustment - on cooldown ({time_since_adjustment:.1f}s)")
            
            # If we've been in cooldown for a while and still have collisions, reset
            if time_since_adjustment > (self.adjustment_cooldown * 0.75):
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
            (current_time - self.adjustment_history['front']['last_time']).nanoseconds / 1e9 < self.adjustment_cooldown and
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
            time_since_adjustment = (current_time - self.adjustment_history['front']['last_time']).nanoseconds / 1e9
            self.node.get_logger().debug(f"Skipping front adjustment - on cooldown ({time_since_adjustment:.1f}s)")
            
            # If we've been in cooldown for a while and still have collisions, reset
            if time_since_adjustment > (self.adjustment_cooldown * 0.75):
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
            time_since_failed = (current_time - self.last_failed_adjustment_time).nanoseconds / 1e9
            
            # If we've been stuck for more than 2 seconds, try escape mode
            if time_since_failed > 2.0:
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
        self.target_override_time = self.node.get_clock().now()
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
        self.last_movement_time = self.node.get_clock().now()
    
    def calculate_adjustment_factor(self, status):
        """Calculate adjustment factor (0.0-1.0) based on collision status."""
        # Use CollisionMath to determine severity if not already set
        if 'severity' not in status or not status['severity']:
            severity = CollisionMath.calculate_severity(
                status['distance'],
                danger_threshold=self.hard_limit_distance,
                warning_threshold=self.soft_limit_distance
            )
        else:
            severity = status['severity']
        
        # Always return a strong value for danger severity regardless of distance
        if severity == 'danger':
            return 1.0
        
        # For other cases, check activity and distance
        if status['active'] or severity == 'warning':
            if status['distance'] <= self.hard_limit_distance:
                return 1.0
            elif status['distance'] <= self.soft_limit_distance:
                # Linear interpolation between 0.0 and 1.0
                range_fraction = (self.soft_limit_distance - status['distance']) / \
                                (self.soft_limit_distance - self.hard_limit_distance)
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
                # Transition back to IDLE when returning to rest
                self._transition_to_state(LuxoState.IDLE)
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
        """Move to home position using a two-stage sequence with rotation limit awareness"""
        try:
            # Transition to RETURNING_HOME state
            self._transition_to_state(LuxoState.RETURNING_HOME)
            
            # IMPORTANT: Set the start time for timeout tracking
            self.returning_to_home_start_time = self.node.get_clock().now()
            
            # Publish a "collision" movement source to disable DEMA during home movement
            self._publish_movement_source("collision")
            
            # Force disable any other modes that might interfere
            self.target_override_active = False  # Clear any previous override
            
            current_time = self.node.get_clock().now()
            current_base_position = self.current_joints[0]
            
            # Check if base is near its limits
            base_min_limit = -3.14  # -180 degrees
            base_max_limit = 3.14   # +180 degrees
            
            # If we're near a limit, reset base to center (0) during home position
            if abs(current_base_position - base_max_limit) < 0.5 or abs(current_base_position - base_min_limit) < 0.5:
                self.node.get_logger().info(
                    f"Base near rotation limit ({np.rad2deg(current_base_position):.1f}°), "
                    f"resetting to center during home position"
                )
                reset_base_position = 0.0
            else:
                reset_base_position = current_base_position
            
            # Create modified home positions
            mod_home_position_1 = self.home_position_1.copy()
            mod_home_position_1[0] = reset_base_position
            
            mod_home_position_2 = self.home_position_2.copy()
            mod_home_position_2[0] = reset_base_position
            
            # Continue with rest of home position logic...
            # (Rest of the original go_to_home_position code follows here)
            
            # IMPROVED: Check if we're already at or near home_position_2 - use a more relaxed tolerance
            # Skip checking joint 0 (base) when determining if we're at home
            hp2_diffs = [abs(curr - target) if i > 0 else 0.0 
                        for i, (curr, target) in enumerate(zip(self.current_joints, mod_home_position_2))]
            already_at_home2 = max(hp2_diffs) <= 0.2
            
            if already_at_home2:
                self.home_position_stage = 2
                self.node.get_logger().debug(f"Already at final home position (diffs: {[round(d, 2) for d in hp2_diffs]})")
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
                    reset_base_position if i == 0 else pos + random.uniform(-noise_range, noise_range) 
                    for i, pos in enumerate(mod_home_position_1)
                ]
            else:
                home_with_variation = [
                    reset_base_position if i == 0 else pos + random.uniform(-noise_range, noise_range) 
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
                # The arm is moving to home
                self.escape_attempts = 0
                with self.collision_lock:
                    for direction in self.collision_status:
                        self.collision_status[direction]['consecutive_count'] = 0
            else:
                self.node.get_logger().error("Failed to send home position command")
                # Return to IDLE state if command failed
                self._transition_to_state(LuxoState.IDLE)
            
            # Reset idle timer
            self.last_activity_time = current_time
            
            return success
        except Exception as e:
            self.node.get_logger().error(f"Error moving to home position: {e}")
            # Return to IDLE state on error
            self._transition_to_state(LuxoState.IDLE)
            return False

    def trigger_idle_animation(self):
        """Trigger a random idle animation."""
        try:
            # Don't trigger if not in IDLE state or action client not ready
            if not self._is_in_state(LuxoState.IDLE):
                return
                
            if not self._idle_animation_client.wait_for_server(timeout_sec=1.0):
                self.node.get_logger().warn("Animation action server not available for idle animation")
                return
            
            # UPDATED: Only clear idle head variation, not voice following
            if self.idle_head_variation_active:
                self.idle_head_variation_active = False
                self.current_idle_head_target = None
                self.node.get_logger().debug("Cleared idle head variation for animation")
            
            # Allow voice following to continue during idle animations
            current_voice_influence = getattr(self, 'voice_influence', 0.0)
            if current_voice_influence > 0.1:
                self.node.get_logger().info(f"Triggering idle animation while voice following active (influence: {current_voice_influence:.2f})")
            
            # Select a random animation, avoiding the last one
            available_animations = [a for a in self.idle_animations if a != self.last_idle_animation]
            if not available_animations:
                available_animations = self.idle_animations
                
            selected_animation = random.choice(available_animations)
            self.last_idle_animation = selected_animation
            
            # Create goal for idle animation
            goal = PlayAnimation.Goal()
            goal.animation_name = selected_animation
            goal.speed_multiplier = random.uniform(0.8, 1.2)  # Slight speed variation
            goal.allow_interruption = True  # Always allow interruption for idle animations
            goal.use_hardware_feedback = False
            
            self.node.get_logger().info(f"Triggering idle animation: {selected_animation} (speed: {goal.speed_multiplier:.1f})")
            
            # Send goal asynchronously
            future = self._idle_animation_client.send_goal_async(goal)
            future.add_done_callback(self._idle_animation_response_callback)
            
            # Update activity time to prevent immediate re-triggering
            self.last_activity_time = self.node.get_clock().now()
            
        except Exception as e:
            self.node.get_logger().error(f"Error triggering idle animation: {e}")
    
    def _idle_animation_response_callback(self, future):
        """Handle the response from idle animation goal."""
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.node.get_logger().debug("Idle animation goal rejected")
            else:
                self.node.get_logger().debug("Idle animation goal accepted")
        except Exception as e:
            self.node.get_logger().error(f"Error in idle animation response: {e}")

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
            self.last_movement_time = self.node.get_clock().now()
            
            # Send the command
            success = self.send_safe_joint_command(safe_position, description)
            
            # Short delay to let the movement start
            time.sleep(0.1)  # Hardware timing delay - keep as time.sleep
            
            return success
        except Exception as e:
            self.node.get_logger().error(f"Error in move_to_safe_position: {e}")
            return False
    
    def _is_position_in_unsafe_zone(self, position):
        """Check if a position is in any of the recorded unsafe zones."""
        for unsafe_pos, radius in self.unsafe_zones:
            # Calculate Euclidean distance in joint space
            distance = self.position_utils.calculate_position_distance(position, unsafe_pos)
            
            if distance < radius:
                return True
                
        return False
    
    def _activate_escape_mode(self, direction):
        """Activate escape mode to avoid persistent collisions in a direction."""
        # Transition to ESCAPE_MODE state
        self._transition_to_state(LuxoState.ESCAPE_MODE)
        
        self.escape_mode_start_time = self.node.get_clock().now()
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
        
        # Use CollisionMath to calculate escape parameters
        escape_magnitude = min(2.0, 1.0 + (self.escape_attempts * 0.3))
        
        # Get current base position and check limits
        current_base = new_position[0]
        at_min_limit = self.safety_limits.is_at_base_limit(current_base) == 'min'
        at_max_limit = self.safety_limits.is_at_base_limit(current_base) == 'max'
        
        if direction == 'front':
            # Pull back arm dramatically
            new_position[1] -= 0.6 * escape_magnitude  # Shoulder back
            new_position[2] += 0.4 * escape_magnitude  # Elbow fold
            
            # Use CollisionMath for escape rotation with wraparound support
            if at_max_limit and self.enable_base_wraparound:
                new_position[0] = self.base_min_limit + 0.5
                self.node.get_logger().warn("Escape: wraparound from max to min limit")
            elif at_min_limit and self.enable_base_wraparound:
                new_position[0] = self.base_max_limit - 0.5
                self.node.get_logger().warn("Escape: wraparound from min to max limit")
            else:
                rotation = CollisionMath.calculate_escape_rotation(direction, 0.8, escape_magnitude)
                if self.escape_attempts % 2 == 0:
                    new_position[0] += abs(rotation)  # Rotate right
                else:
                    new_position[0] -= abs(rotation)  # Rotate left
                
        elif direction == 'left':
            # Escape to the RIGHT with limit awareness
            if at_min_limit and self.enable_base_wraparound:
                new_position[0] = self.base_max_limit - 0.3
                self.node.get_logger().warn("Left escape: wraparound to max limit")
            else:
                rotation = CollisionMath.calculate_escape_rotation(direction, 0.8, escape_magnitude)
                new_position[0] += rotation  # Positive rotation for left collision
            new_position[1] += 0.3 * escape_magnitude  # Pull back
            
        elif direction == 'right':
            # Escape to the LEFT with limit awareness
            if at_max_limit and self.enable_base_wraparound:
                new_position[0] = self.base_min_limit + 0.3
                self.node.get_logger().warn("Right escape: wraparound to min side")
            else:
                rotation = CollisionMath.calculate_escape_rotation(direction, 0.8, escape_magnitude)
                new_position[0] += rotation  # Negative rotation for right collision
            new_position[1] += 0.3 * escape_magnitude  # Pull back
        
        # Use SafetyLimits to ensure we stay within hard limits
        new_position[0] = self.safety_limits.clamp_base_angle(new_position[0])
        
        # Validate the entire position
        new_position = MovementValidator.validate_position(new_position, self.safety_limits)
        
        # Send the escape command with high priority
        self.send_safe_joint_command(new_position, f"Escape maneuver ({direction}, attempt {self.escape_attempts})")
        
        # Update tracking variables
        self.target_override_active = True
        self.target_override_time = self.node.get_clock().now()
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
            
            # Use CollisionMath for small rotation
            rotation = CollisionMath.calculate_escape_rotation(direction, 0.3, escape_magnitude)
            if self.escape_attempts % 2 == 0:
                new_position[0] += abs(rotation)
            else:
                new_position[0] -= abs(rotation)
                
        elif direction == 'left':
            # Smaller rotation to RIGHT
            rotation = CollisionMath.calculate_escape_rotation(direction, 0.4, escape_magnitude)
            new_position[0] += rotation
            
        elif direction == 'right':
            # Smaller rotation to LEFT
            rotation = CollisionMath.calculate_escape_rotation(direction, 0.4, escape_magnitude)
            new_position[0] += rotation
        
        # Validate the position
        new_position = MovementValidator.validate_position(new_position, self.safety_limits)
        
        # Send command with note about animation-aware escape
        self.send_safe_joint_command(new_position, f"Animation-safe escape ({direction})")
        
        # Set shorter escape duration during animations
        self.escape_mode_duration = min(self.escape_mode_duration, 3.0)
    
    def is_animating(self):
        """Determine if the robot is currently executing an animation."""
        # Check state machine first
        if self._is_in_state(LuxoState.ANIMATING):
            return True
            
        # Check if we have an active animation tracked
        with self.animation_lock:
            if self.current_animation_name is not None:
                return True
        
        # Fall back to movement detection
        time_since_last_command = (self.node.get_clock().now() - self.last_movement_time).nanoseconds / 1e9
        
        if time_since_last_command < 0.5:
            return True
            
        max_velocity = max([abs(v) for v in self.joint_velocities]) if self.joint_velocities else 0
        if max_velocity > 0.5:
            return True
            
        if len(self.recent_command_times) >= 3:
            intervals = [self.recent_command_times[i+1] - self.recent_command_times[i] 
                        for i in range(len(self.recent_command_times)-1)]
            if intervals and max(intervals) - min(intervals) < 0.2:
                return True
        
        return False
    
    def _publish_movement_source(self, source):
        """Publish movement source information for DEMA coordination."""
        self.movement_publisher.publish_movement_source(
            self.node, 
            source, 
            self.current_joints,
            getattr(self.node, 'joint_states_publisher', None),
            getattr(self.node, 'movement_source_publisher', None)
        )

    def trigger_idle_head_variation(self):
        """Trigger subtle head movements during idle periods."""
        try:
            # Don't trigger if not enabled or not in IDLE state
            if not self.idle_head_variation_enabled or not self._is_in_state(LuxoState.IDLE):
                return
                
            # UPDATED: Don't interfere with ACTIVE voice following, but allow coexistence
            # Only prevent if voice is very recently active (within last 1 second)
            if hasattr(self, 'voice_active') and self.voice_active and hasattr(self, 'last_voice_time'):
                time_since_voice = (self.node.get_clock().now() - self.last_voice_time).nanoseconds / 1e9
                if time_since_voice < 1.0:  # Very recent voice activity
                    self.node.get_logger().debug("Very recent voice activity - skipping idle head variation")
                    return
                
            # Don't interfere with collision avoidance
            if any(status['active'] for status in self.collision_status.values()):
                return
            
            current_time = self.node.get_clock().now()
            
            # Generate a subtle head variation target
            variation_target = self._generate_idle_head_variation()
            
            if variation_target:
                self.current_idle_head_target = variation_target
                self.idle_head_variation_active = True
                self.last_idle_head_variation_time = current_time
                
                # Ensure we only have exactly 5 joint positions
                if len(variation_target) > 5:
                    variation_target = variation_target[:5]
                
                # Create target with acceleration - use list() + [acceleration] to avoid repeated concatenation
                target_with_accel = list(variation_target) + [self.idle_head_variation_speed]
                
                # Send the gentle movement command
                self.send_safe_joint_command(target_with_accel, "Idle head variation")
                
                # Set a gentle override to maintain the movement (without acceleration for internal tracking)
                self.target_override_active = True
                self.target_override_time = current_time
                self.target_override_joints = variation_target.copy()
                self.target_override_reason = "Idle head variation"
                self.target_override_timeout = 2.0  # Short timeout for gentle movements
                
                self.node.get_logger().info(f"Applied idle head variation: {[round(p, 2) for p in variation_target]}")
                
        except Exception as e:
            self.node.get_logger().error(f"Error in idle head variation: {e}")
    
    def _generate_idle_head_variation(self):
        """Generate a subtle head movement variation based on idle position."""
        try:
            # Start with the CURRENT position, not the base idle position
            variation = self.current_joints.copy()
            
            # Ensure we only work with 5 joints maximum
            if len(variation) > 5:
                variation = variation[:5]
            
            # Add subtle base rotation (looking left/right slightly) RELATIVE to current position
            base_variation = random.uniform(-self.idle_head_base_rotation_range, self.idle_head_base_rotation_range)
            variation[0] += base_variation  # Apply variation to current base position
            
            # For other joints, use the idle base position as reference but apply relative variations
            # Add vertical look variation (primarily through shoulder adjustment)
            # Bias towards looking up (70% chance) as it appears more alert/curious
            look_type = random.random()
            if look_type < 0.7:  # Look up
                shoulder_variation = random.uniform(0.1, self.idle_head_look_up_range)
                variation[1] = self.idle_base_position[1] - shoulder_variation  # More positive = looking up
                variation_description = f"looking up (+{shoulder_variation:.2f})"
            elif look_type < 0.9:  # Look down slightly
                shoulder_variation = random.uniform(0.0, self.idle_head_look_down_range)
                variation[1] = self.idle_base_position[1] + shoulder_variation  # More negative = looking down
                variation_description = f"looking down (-{shoulder_variation:.2f})"
            else:  # Stay neutral
                variation[1] = self.idle_base_position[1]  # Use base idle position
                variation_description = "staying neutral"
            
            # Use base idle position for elbow, wrist, hand with small variations
            variation[2] = self.idle_base_position[2]  # Start with base idle elbow
            variation[3] = self.idle_base_position[3]  # Start with base idle wrist
            variation[4] = self.idle_base_position[4]  # Start with base idle hand
            
            # Add tiny variations to other joints for naturalness, but keep neck straighter
            # Only add elbow variation 30% of the time to keep neck less crooked
            if random.random() < 0.3:
                variation[2] += random.uniform(-0.02, 0.02)  # Reduced elbow adjustment
            # Only add wrist variation 20% of the time 
            if random.random() < 0.2:
                variation[3] += random.uniform(-0.01, 0.01)  # Reduced wrist adjustment
            # Keep hand position stable
            
            # Ensure we return exactly 5 elements
            variation = variation[:5]
            
            self.node.get_logger().info(
                f"Generated idle head variation: base {base_variation:+.2f} (current: {np.rad2deg(self.current_joints[0]):.1f}° -> {np.rad2deg(variation[0]):.1f}°), {variation_description}"
            )
            
            return variation
            
        except Exception as e:
            self.node.get_logger().error(f"Error generating idle head variation: {e}")
            return None
    
    def _should_apply_idle_head_variation(self):
        """Check if we should apply idle head variation."""
        if not self.idle_head_variation_enabled:
            return False
            
        # Only in IDLE state
        if not self._is_in_state(LuxoState.IDLE):
            return False
            
        # Don't interfere with ACTIVE voice following, but allow coexistence
        if hasattr(self, 'voice_active') and self.voice_active and hasattr(self, 'last_voice_time'):
            time_since_voice = (self.node.get_clock().now() - self.last_voice_time).nanoseconds / 1e9
            if time_since_voice < 1.0:  # Very recent voice activity
                return False
            
        # Don't interfere with collision avoidance
        if any(status['active'] for status in self.collision_status.values()):
            return False
            
        # Don't interfere with returning to home
        if self.target_override_active and "home" in self.target_override_reason.lower():
            return False
            
        current_time = self.node.get_clock().now()
        time_since_last_variation = (current_time - self.last_idle_head_variation_time).nanoseconds / 1e9
        
        # Check if enough time has passed - use random interval between 1.0 and max interval
        random_interval = random.uniform(3.5, self.idle_head_variation_interval)
        return time_since_last_variation > random_interval