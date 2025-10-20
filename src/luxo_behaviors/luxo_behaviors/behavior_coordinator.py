#!/usr/bin/env python3
#behavior_coordinator.py

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
from luxo_behaviors.idle_behavior import IdleBehavior
from luxo_behaviors.voice_following_behavior import VoiceFollowingBehavior
from luxo_behaviors.collision_behavior import CollisionBehavior
from luxo_behaviors.command_behavior import CommandBehavior

class BehaviorCoordinator(PettingBehavior, IdleBehavior, VoiceFollowingBehavior, CollisionBehavior, CommandBehavior):
    """Class to handle behavior coordination for the Luxo robot."""
    
    def __init__(self, node, send_safe_joint_command_callback, publish_actual_joint_states_callback):
        """
        Initialize the BehaviorCoordinator system.
        
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
            self.base_max_limit = np.deg2rad(140.0)
            self.base_soft_min = self.base_min_limit + np.deg2rad(10.0)
            self.base_soft_max = self.base_max_limit - np.deg2rad(10.0)
            self.enable_base_wraparound = True
        
        # Initialize shared utilities
        self.position_utils = PositionUtils()
        self.movement_publisher = MovementSourcePublisher()
        self.collision_tracker = CollisionStatusTracker()
        self.animation_tracker = AnimationTracker()
        self.time_utils = TimeUtils()
        
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
        self.current_joints = [0.0, 0.0, 0.0, 0.0, 0.0, 10.0, 0.0]  # Current joint positions including acceleration and antenna
        self.target_joints = [0.0, 0.0, 0.0, 0.0, 0.0, 10.0, 0.0]   # Target joint positions including acceleration and antenna
        self.joint_velocities = [0.0, 0.0, 0.0, 0.0, 0.0] # Current joint velocities
        
        # Additional tracking variables with ROS time
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

        # Initialize all behavior modules after core attributes are set
        self.setup_collision_behavior()  # Initialize collision behavior
        self.setup_idle_behavior()       # Initialize idle behavior
        self.setup_petting_behavior()    # Initialize petting behavior
        self.setup_voice_behavior()      # Initialize voice behavior
        self.setup_command_behavior(setup_publishers=False)  # Initialize command behavior (coordination only, no publishers)

        # Subscribe to sleep mode commands for complete sleep sequence handling
        self.sleep_mode_subscription = self.node.create_subscription(
            Bool,
            '/luxo/sleep_mode',
            self._sleep_mode_callback,
            10
        )

        # Subscribe to stay mode commands for position freezing
        self.stay_mode_subscription = self.node.create_subscription(
            Bool,
            '/luxo/stay_mode',
            self._stay_mode_callback,
            10
        )

        # Create publishers for sleep mode control
        self.light_control_publisher = self.node.create_publisher(
            Bool,
            '/luxo/light_control',
            10
        )

        self.pixel_ring_control_publisher = self.node.create_publisher(
            Bool,
            '/voice/pixel_ring_control',
            10
        )

        # Track sleep state
        self.sleep_state = False
        self.sleep_animation_in_progress = False

        # Track stay state
        self.stay_state = False
        self.stay_frozen_position = None  # The position to stay frozen at
        self.stay_timer = None  # Timer for continuously feeding position
        self.stay_entry_retry_timer = None  # Timer for retrying STAY entry
        self.stay_entry_requested = False  # Track if we're trying to enter STAY
        self.stay_exit_retry_timer = None  # Timer for retrying STAY exit
        self.stay_exit_requested = False  # Track if we're trying to exit STAY

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

    def _transition_to_state(self, new_state, wait_for_result=False, timeout_sec=1.0):
        """Request a state transition.

        Args:
            new_state: The target state to transition to
            wait_for_result: If True, wait for transition response (default: False for backward compatibility)
            timeout_sec: Timeout for waiting when wait_for_result=True

        Returns:
            bool: True if transition succeeded (or if not waiting), False otherwise
        """
        try:
            request = RequestStateTransition.Request()
            request.requested_state = new_state.name
            request.requesting_node = "behavior_coordinator"
            request.priority = 100  # High priority
            request.force = False

            future = self.request_state_transition_client.call_async(request)

            if wait_for_result:
                # Wait for the response using future.result() - this blocks the current thread
                # but doesn't interfere with the executor
                try:
                    response = future.result(timeout=timeout_sec)
                    return response.success
                except Exception as e:
                    self.node.get_logger().warn(f"State transition request to {new_state.name} failed: {e}")
                    return False
            else:
                # Fire and forget - assume success for backward compatibility
                return True
        except Exception as e:
            self.node.get_logger().error(f"Error requesting state transition: {e}")
            return False
    
    def _can_process_voice_command(self) -> bool:
        """Check if current state allows voice command processing."""
        current_state = self._get_current_state()
        
        # States that allow voice following
        allowed_states = [
            LuxoState.IDLE,
            LuxoState.VOICE_FOLLOWING,
            LuxoState.ANIMATING,  # Allow during animations
            LuxoState.PETTING,    # Allow during petting
            LuxoState.EMOTION_REACTING  # Allow during emotion reactions
        ]
        
        return current_state in allowed_states

    def apply_voice_following(self, positions):
        """Apply voice following with state-aware handling - ALWAYS apply in VOICE_FOLLOWING state."""
        current_state = self._get_current_state()

        # CRITICAL: Always apply voice following if we're in VOICE_FOLLOWING state
        # This ensures voice commands are never ignored when the state is active
        if current_state == LuxoState.VOICE_FOLLOWING:
            result = super().apply_voice_following(positions)
            # If voice following actually modified the position, use it
            # Otherwise fall through to check other conditions
            if result != positions:
                return result
            # If no voice target yet, continue to check other conditions

        # For other states, only apply if voice influence is very high
        if hasattr(self, 'voice_influence') and self.voice_influence > 0.7:
            return super().apply_voice_following(positions)

        # Fall back to idle head variation for non-voice states
        if (hasattr(self, 'idle_head_variation_active') and
            self.idle_head_variation_active and
            current_state == LuxoState.IDLE):
            return self.apply_idle_head_variation(positions)

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
                    self.node.get_logger().debug(f"New target received - clearing non-collision override")
                    self.target_override_active = False
                    self.target_override_joints = None
        
        # Update the timestamp for target changes
        self.last_original_target_change_time = current_time
    
    def update_joint_velocities(self, velocities):
        """Update the current joint velocities."""
        self.joint_velocities = velocities.copy()
    
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
            
            # Update voice decay first (this reduces voice_influence over time)
            self.update_voice_decay(current_time)

            # Check for command completion
            if self.check_command_completion(current_time):
                return  # Command completed, skip other checks

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
                        if self._at_home_position(self.current_joints, self.home_position_1, self.home_position_tolerance):
                            # Check if enough time has passed at stage 1
                            time_at_stage_1 = (current_time - self.home_position_stage_change_time).nanoseconds / 1e9
                            if time_at_stage_1 > self.home_position_stage_timeout:
                                self.node.get_logger().info("Moving from home position stage 1 to stage 2")
                                self.home_position_stage = 2
                                self.home_position_stage_change_time = current_time
                                
                                # Add variation to home_position_2
                                noise_range = 0.05
                                home_with_variation = [
                                    pos + random.uniform(-noise_range, noise_range) 
                                    for pos in self.home_position_2
                                ]
                                
                                # Update target override to stage 2
                                self.target_override_joints = home_with_variation
                                self.target_override_time = current_time
                                self.target_override_reason = "Home position stage 2"
                                
                                # Send command to move to stage 2
                                self.send_safe_joint_command(home_with_variation, "Moving to home position stage 2")
                            else:
                                self.node.get_logger().debug(f"At home position stage 1, waiting {self.home_position_stage_timeout - time_at_stage_1:.1f}s before stage 2")
                        
                    elif self.home_position_stage == 2:
                        if self._at_home_position(self.current_joints, self.home_position_2, self.home_position_tolerance):
                            self.node.get_logger().info("Successfully reached final home position - transitioning to IDLE")
                            # Clear the override and transition back to IDLE
                            self.target_override_active = False
                            self.target_override_joints = None
                            self.home_position_stage = 1  # Reset for next time
                            self._transition_to_state(LuxoState.IDLE)
                return  # Skip other checks when returning to home
            
            # Check for persistent collisions and determine action
            collision_action = self.check_persistent_collision(current_time)
            if collision_action == 'home':
                self.node.get_logger().warn(f"Persistent head collision for over {self.extended_collision_timeout:.1f}s - returning to home position")
                # Force go to home by transitioning to RETURNING_HOME state
                self._transition_to_state(LuxoState.RETURNING_HOME)
                self.returning_to_home_start_time = current_time
                self.go_to_home_position("Extended persistent head collision - return to home")
                return  # Skip remaining checks
            elif collision_action == 'escape':
                self.node.get_logger().warn(f"Persistent head collision - attempting escape mode")
                self._activate_escape_mode('front')
                return  # Skip remaining checks
            
            # Check idle timeout for idle animations
            if self.check_idle_animations(current_time):
                return  # Skip other checks if animation was triggered

            # Check for idle head variation
            if self.check_idle_head_variation(current_time):
                # If we generated a new variation, apply it
                if self.current_idle_head_target:
                    self.target_override_active = True
                    self.target_override_time = current_time
                    self.target_override_joints = self.current_idle_head_target.copy()
                    self.target_override_reason = "idle head variation"
                    self.send_safe_joint_command(self.current_idle_head_target, "Idle head variation")
            
            # Check for extended idle timeout
            if self.check_extended_idle_timeout(current_time):
                return  # Skip other checks if returning home
            
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
            
            # Handle escape mode if active
            if self.check_escape_mode_status(current_time):
                return  # Still in escape mode
                
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
            voice_applied = self.apply_voice_following(original_target)
            # IDLE HEAD VARIATION: Apply idle head variation if voice following isn't active
            return self.apply_idle_head_variation(voice_applied)
        
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

    def _sleep_mode_callback(self, msg):
        """Handle sleep mode commands - complete sequence with lights and DEMA."""
        try:
            if msg.data and not self.sleep_state:
                # Going to sleep
                self.node.get_logger().info("Sleep mode activated - handling lights and DEMA")
                self.sleep_state = True
                self.sleep_animation_in_progress = True

                # Turn off lights immediately
                light_msg = Bool()
                light_msg.data = False
                self.light_control_publisher.publish(light_msg)
                self.node.get_logger().info("Lights turned OFF for sleep")

                # Turn off pixel ring
                pixel_msg = Bool()
                pixel_msg.data = False
                self.pixel_ring_control_publisher.publish(pixel_msg)
                self.node.get_logger().info("Pixel ring turned OFF for sleep")

                # Schedule DEMA enable after animation completes (sleep animation is ~2-4 seconds)
                # Add some buffer time
                sleep_animation_duration = 3.5
                self._schedule_dema_enable(sleep_animation_duration)

            elif not msg.data and self.sleep_state:
                # Waking up - use staged sequence to gradually reduce DEMA
                self.node.get_logger().info("Wake mode activated - turning on lights and starting staged DEMA reduction")
                self.sleep_state = False
                self.sleep_animation_in_progress = False

                # Turn on lights immediately
                light_msg = Bool()
                light_msg.data = True
                self.light_control_publisher.publish(light_msg)
                self.node.get_logger().info("Lights turned ON for wake up")

                # Turn on pixel ring immediately
                pixel_msg = Bool()
                pixel_msg.data = True
                self.pixel_ring_control_publisher.publish(pixel_msg)
                self.node.get_logger().info("Pixel ring turned ON for wake up")

                # Start the staged wake-up sequence for DEMA reduction only
                self._staged_wake_up()

        except Exception as e:
            self.node.get_logger().error(f"Error in sleep mode callback: {e}")

    def _schedule_dema_enable(self, delay_seconds):
        """Schedule DEMA enable after animation completes."""
        def enable_dema_after_delay():
            try:
                time.sleep(delay_seconds)
                if self.sleep_state and self.sleep_animation_in_progress:
                    self.node.get_logger().info("Sleep animation completed - enabling DEMA")

                    # Enable DEMA mode
                    if hasattr(self.node, 'enable_dynamic_adaptation_mode'):
                        success = self.node.enable_dynamic_adaptation_mode()
                        if success:
                            self.node.get_logger().info("DEMA enabled - robot is now immobilized for sleep")
                            self.node.disable_torque()
                            self.node.get_logger().info("Torque disabled for sleep mode")
                        else:
                            self.node.get_logger().warn("Failed to enable DEMA for sleep mode")

                    self.sleep_animation_in_progress = False
            except Exception as e:
                self.node.get_logger().error(f"Error enabling DEMA after sleep animation: {e}")

        # Start thread to enable DEMA after delay
        import threading
        dema_thread = threading.Thread(target=enable_dema_after_delay, daemon=True)
        dema_thread.start()

    def _staged_wake_up(self):
        """
        Staged wake-up sequence to gradually reduce DEMA compliance.

        Stage 1 (4s): Very high torque limits (900 - most compliant, gentle wake)
        Stage 2 (3s): High torque limits (700 - still quite compliant)
        Stage 3 (2s): Medium torque limits (400 - firming up)
        Stage 4: DEMA off, full motor control
        """
        def wake_up_sequence():
            try:
                # Stage 1: Very high torque limits (most compliant)
                # Using higher values = more compliant (easier to move manually)
                self.node.get_logger().info("🌅 Wake Stage 1/4: Gentle wake-up (very high compliance) - 4 seconds")
                if hasattr(self.node, 'serial_manager'):
                    self.node.serial_manager.set_dynamic_adaptation(
                        mode=1,
                        base=900,      # Very compliant
                        shoulder=950,
                        elbow=900,
                        wrist=900,
                        roll=900,
                        hand=900
                    )
                time.sleep(4.0)

                # Stage 2: High torque limits (still quite compliant)
                self.node.get_logger().info("🌅 Wake Stage 2/4: Gradual firming - 3 seconds")
                if hasattr(self.node, 'serial_manager'):
                    self.node.serial_manager.set_dynamic_adaptation(
                        mode=1,
                        base=750,      # High compliance
                        shoulder=750,
                        elbow=750,
                        wrist=750,
                        roll=750,
                        hand=750
                    )
                time.sleep(3.0)

                # Stage 3: Medium torque limits (firming up)
                self.node.get_logger().info("🌅 Wake Stage 3/4: Increasing resistance - 2 seconds")
                if hasattr(self.node, 'serial_manager'):
                    self.node.serial_manager.set_dynamic_adaptation(
                        mode=1,
                        base=450,      # Medium compliance
                        shoulder=450,
                        elbow=450,
                        wrist=450,
                        roll=450,
                        hand=450
                    )
                time.sleep(2.0)

                # Stage 4: Disable DEMA completely and enable torque
                self.node.get_logger().info("🌅 Wake Stage 4/4: Full motor control - DEMA OFF")
                if hasattr(self.node, 'disable_dynamic_adaptation_mode'):
                    success = self.node.disable_dynamic_adaptation_mode()
                    if success:
                        time.sleep(0.2)
                        self.node.enable_torque()
                        self.node.get_logger().info("✅ Wake-up complete! DEMA disabled, torque enabled, full control restored")
                    else:
                        self.node.get_logger().error("❌ Failed to disable DEMA in final wake stage")

            except Exception as e:
                self.node.get_logger().error(f"Error in staged wake-up sequence: {e}")
                # Fallback: try to disable DEMA anyway
                try:
                    if hasattr(self.node, 'disable_dynamic_adaptation_mode'):
                        self.node.disable_dynamic_adaptation_mode()
                        self.node.enable_torque()
                except:
                    pass

        # Start thread for staged wake-up
        import threading
        wake_thread = threading.Thread(target=wake_up_sequence, daemon=True)
        wake_thread.start()

    def _stay_mode_callback(self, msg):
        """Handle stay mode commands - freeze position without DEMA."""
        current_state = self._get_current_state()
        self.node.get_logger().info(f"🔔 _stay_mode_callback CALLED: msg.data={msg.data}, stay_state={self.stay_state}, actual_state={current_state.name}")
        try:
            if msg.data and not self.stay_state:
                # Entering stay mode - mark as requested
                self.stay_entry_requested = True
                self.node.get_logger().info(f"🧊 Stay mode requested - current state is {current_state.name}")

                # Capture current position
                self.stay_frozen_position = self.current_joints[:5].copy()  # Only the first 5 joints

                # Try to transition to STAY state
                self._attempt_stay_entry()

            elif not msg.data:
                # FIXED: Exit STAY if we're actually IN the STAY state (check state machine, not just flag)
                if current_state == LuxoState.STAY or self.stay_state or self.stay_entry_requested:
                    # Exiting stay mode (or canceling entry attempt)
                    self.node.get_logger().info("🔓 Stay mode exit requested - attempting to resume normal operation")

                    # Mark exit as requested and cancel entry if it was in progress
                    self.stay_exit_requested = True
                    self.stay_entry_requested = False

                    # Cancel the entry retry timer if active
                    if self.stay_entry_retry_timer is not None:
                        self.stay_entry_retry_timer.cancel()
                        self.stay_entry_retry_timer = None

                    # Attempt to exit STAY state with retry logic
                    self._attempt_stay_exit()
                else:
                    self.node.get_logger().info(f"🔕 Ignoring STAY exit - not in STAY state (current: {current_state.name})")

        except Exception as e:
            self.node.get_logger().error(f"Error in stay mode callback: {e}")
            # Clean up on error
            self.stay_state = False
            self.stay_entry_requested = False
            self.stay_exit_requested = False
            if self.stay_timer is not None:
                self.stay_timer.cancel()
                self.stay_timer = None
            if self.stay_entry_retry_timer is not None:
                self.stay_entry_retry_timer.cancel()
                self.stay_entry_retry_timer = None
            if self.stay_exit_retry_timer is not None:
                self.stay_exit_retry_timer.cancel()
                self.stay_exit_retry_timer = None
            self.stay_frozen_position = None

    def _stay_position_callback(self):
        """Timer callback to continuously feed the frozen position."""
        try:
            if self.stay_state and self.stay_frozen_position is not None:
                # Feed the frozen position to hardware
                self.send_safe_joint_command(
                    self.stay_frozen_position,
                    "Stay mode - holding position"
                )
        except Exception as e:
            self.node.get_logger().error(f"Error in stay position callback: {e}")

    def _attempt_stay_entry(self):
        """Attempt to enter STAY state, with retry logic."""
        try:
            # Cancel any existing retry timer
            if self.stay_entry_retry_timer is not None:
                self.stay_entry_retry_timer.cancel()
                self.stay_entry_retry_timer = None

            current_state = self._get_current_state()

            # Try to transition to STAY
            transition_success = self._transition_to_state(LuxoState.STAY, wait_for_result=True, timeout_sec=2.0)

            if transition_success:
                # Successfully entered STAY state
                self.node.get_logger().info(f"✅ Stay mode activated - freezing current position")
                self.stay_state = True
                self.stay_entry_requested = False

                # Create timer to continuously feed the same position (10Hz = 0.1s interval)
                if self.stay_timer is not None:
                    self.stay_timer.cancel()

                self.stay_timer = self.node.create_timer(0.1, self._stay_position_callback)

                self.node.get_logger().info(f"Position frozen at: {[round(p, 2) for p in self.stay_frozen_position]}")

            else:
                # Transition failed - retry after delay
                self.node.get_logger().warn(
                    f"⚠️ Cannot enter STAY from {current_state.name} - will retry in 1 second"
                )

                # Schedule retry
                self.stay_entry_retry_timer = self.node.create_timer(1.0, self._retry_stay_entry, one_shot=True)

        except Exception as e:
            self.node.get_logger().error(f"Error attempting STAY entry: {e}")
            # Retry on error
            if self.stay_entry_requested:
                self.stay_entry_retry_timer = self.node.create_timer(1.0, self._retry_stay_entry, one_shot=True)

    def _retry_stay_entry(self):
        """Timer callback to retry STAY entry."""
        try:
            # Check if we're still trying to enter STAY
            if not self.stay_entry_requested or self.stay_state:
                # No longer needed
                return

            self.node.get_logger().info("🔁 Retrying STAY entry...")
            self._attempt_stay_entry()

        except Exception as e:
            self.node.get_logger().error(f"Error in STAY entry retry: {e}")

    def _attempt_stay_exit(self):
        """Attempt to exit STAY state, with retry logic."""
        try:
            # Cancel any existing retry timer
            if self.stay_exit_retry_timer is not None:
                self.stay_exit_retry_timer.cancel()
                self.stay_exit_retry_timer = None

            current_state = self._get_current_state()

            # Try to transition to IDLE
            transition_success = self._transition_to_state(LuxoState.IDLE, wait_for_result=True, timeout_sec=2.0)

            if transition_success:
                # Successfully exited STAY state
                self.node.get_logger().info(f"✅ Stay mode deactivated - resuming normal operation")
                self.stay_state = False
                self.stay_exit_requested = False

                # Cancel the position-feeding timer
                if self.stay_timer is not None:
                    self.stay_timer.cancel()
                    self.stay_timer = None

                # Clear frozen position
                self.stay_frozen_position = None

                # Schedule verification check after 5 seconds to ensure we actually left STAY
                self.node.create_timer(5.0, self._verify_stay_exit, one_shot=True)

            else:
                # Transition failed - retry after delay
                self.node.get_logger().warn(
                    f"⚠️ Cannot exit STAY from {current_state.name} - will retry in 1 second"
                )

                # Schedule retry
                self.stay_exit_retry_timer = self.node.create_timer(1.0, self._retry_stay_exit, one_shot=True)

        except Exception as e:
            self.node.get_logger().error(f"Error attempting STAY exit: {e}")
            # Retry on error
            if self.stay_exit_requested:
                self.stay_exit_retry_timer = self.node.create_timer(1.0, self._retry_stay_exit, one_shot=True)

    def _retry_stay_exit(self):
        """Timer callback to retry STAY exit."""
        try:
            # Check if we're still trying to exit STAY
            if not self.stay_exit_requested or not self.stay_state:
                # No longer needed
                return

            self.node.get_logger().info("🔁 Retrying STAY exit...")
            self._attempt_stay_exit()

        except Exception as e:
            self.node.get_logger().error(f"Error in STAY exit retry: {e}")

    def _verify_stay_exit(self):
        """Verify that we actually exited STAY state after move command."""
        try:
            current_state = self._get_current_state()

            if current_state == LuxoState.STAY:
                # Still in STAY after 5 seconds - force transition to IDLE
                self.node.get_logger().warn(
                    "⚠️ Still in STAY state 5 seconds after exit command - forcing IDLE transition"
                )

                # Force transition with higher priority
                success = self._transition_to_state(LuxoState.IDLE, wait_for_result=True, timeout_sec=2.0)

                if success:
                    self.node.get_logger().info("✅ Successfully forced IDLE transition after STAY verification failure")
                else:
                    self.node.get_logger().error(
                        "❌ Failed to force IDLE transition - STAY state may be stuck. "
                        "Manual intervention may be required."
                    )
            else:
                # Successfully exited STAY (could be in IDLE, ANIMATING, VOICE_FOLLOWING, etc - any state is fine)
                self.node.get_logger().info(f"✅ STAY exit verified - successfully transitioned to {current_state.name}")

        except Exception as e:
            self.node.get_logger().error(f"Error in stay exit verification: {e}")