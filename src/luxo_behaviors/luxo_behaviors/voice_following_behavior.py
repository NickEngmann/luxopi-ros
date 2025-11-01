#!/usr/bin/env python3
#voice_following_behavior.py
"""
Voice following behavior module for Luxo robot.
Handles voice direction following and face detection variations.
"""

import random
import time
from typing import Optional, List, Tuple
from std_msgs.msg import Float32, Bool
from luxo_behaviors.state_machine import LuxoState
import numpy as np


class VoiceFollowingBehavior:
    """Mixin class for voice following behavior functionality."""
    
    def setup_voice_behavior(self):
        """Initialize voice behavior attributes and subscriptions."""
        # Voice following parameters - check before declaring
        if not self.node.has_parameter('enable_voice_following'):
            self.node.declare_parameter('enable_voice_following', True)
        if not self.node.has_parameter('voice_follow_speed'):
            self.node.declare_parameter('voice_follow_speed', 0.3)
        if not self.node.has_parameter('voice_follow_deadzone'):
            self.node.declare_parameter('voice_follow_deadzone', 15.0)
        if not self.node.has_parameter('voice_follow_smoothing'):
            self.node.declare_parameter('voice_follow_smoothing', 0.3)
        
        # Voice variation parameters - check before declaring
        if not self.node.has_parameter('voice_variation_enabled'):
            self.node.declare_parameter('voice_variation_enabled', True)
        if not self.node.has_parameter('voice_direction_tolerance'):
            self.node.declare_parameter('voice_direction_tolerance', 5.0)
        if not self.node.has_parameter('voice_variation_interval'):
            self.node.declare_parameter('voice_variation_interval', 2.0)
        if not self.node.has_parameter('voice_look_up_range'):
            self.node.declare_parameter('voice_look_up_range', 1.1)  # Increased 15%
        if not self.node.has_parameter('voice_look_down_range'):
            self.node.declare_parameter('voice_look_down_range', 0.1)  # Decreased 20%
        
        # Load parameters
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
        self.voice_neutral_position = [-0.55, 1.2, 1.0, 2.0]  # Baseline position (shoulder, elbow, wrist, hand - excluding base)
        self.voice_on_target_threshold = 2.0  # seconds to wait before starting variations
        
        # Voice command cooldown and direction filtering
        self.voice_command_cooldown = 0.3  # seconds between voice commands (reduced from 1.0 for faster response)
        self.last_voice_command_time = None  # Initialize to None to allow immediate first command
        self.last_acted_voice_direction = None  # Last direction we actually sent a command for
        self.voice_direction_filter_threshold = 5.0  # degrees - ignore directions within this range if already at target
        
        # Voice state management
        self.voice_following_state_requested = False
        self.voice_following_previous_state = None
        self.voice_completion_timer = None
        self.voice_completion_timeout = 3.0  # seconds of no voice activity before completing

        # Voice position feeding timer (continuously spam position like STAY mode)
        self.voice_position_timer = None
        self.voice_position_timer_active = False

        # Adaptive movement tracking - prevent wild spinning in noisy environments
        self.movement_history = []  # List of (timestamp, base_position) tuples
        self.movement_history_duration = 20.0  # Track last 20 seconds of movement
        self.direction_reversal_threshold = 2.1  # radians (~120 degrees)
        self.thrashing_reversal_count = 3  # Number of reversals to trigger adaptive mode (reduced for faster detection)
        self.thrashing_time_window = 10.0  # Time window to count reversals (seconds)
        self.is_thrashing = False
        self.adaptive_cooldown_multiplier = 1.0  # Multiplier for cooldown (1.0 = normal, 6.0 = max)
        self.adaptive_filter_multiplier = 1.0  # Multiplier for direction filter
        self.last_adaptive_check_time = self.node.get_clock().now()
        self.adaptive_recovery_rate = 0.95  # Recovery multiplier per second (5% reduction)
        self.last_movement_direction = 0  # 1 = positive, -1 = negative, 0 = unknown

        # TTS state tracking - prevent robot from following its own voice
        self.tts_active = False

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

        # Subscribe to TTS status to prevent following robot's own voice
        self.tts_active_sub = self.node.create_subscription(
            Bool,
            '/voice/tts_active',
            self.tts_active_callback,
            10
        )

        # Subscribe to rainbow mode to disable voice following during demo mode
        self.rainbow_mode_active = False
        self.rainbow_mode_sub = self.node.create_subscription(
            Bool,
            '/luxo/rainbow_mode',
            self.rainbow_mode_callback,
            10
        )

        self.node.get_logger().info(f"Voice following enabled: {self.voice_follow_enabled}")
    
    def tts_active_callback(self, msg):
        """Handle TTS active status - prevent following robot's own voice."""
        self.tts_active = msg.data
        if self.tts_active:
            self.node.get_logger().debug("TTS started - voice following will be suppressed")
        else:
            self.node.get_logger().debug("TTS finished - voice following re-enabled")

    def rainbow_mode_callback(self, msg):
        """Handle rainbow mode changes - disable voice following during demo mode."""
        self.rainbow_mode_active = msg.data
        if self.rainbow_mode_active:
            self.node.get_logger().info("🌈 Rainbow demo mode: Voice following disabled")
        else:
            self.node.get_logger().info("Normal mode: Voice following re-enabled")

    def voice_direction_callback(self, msg):
        """Handle voice direction messages with cooldown and filtering."""
        if not self.voice_follow_enabled:
            self.node.get_logger().warn(f"🚫 Voice following DISABLED - ignoring direction {msg.data:.1f}°")
            return

        # Disable voice following during rainbow demo mode
        if self.rainbow_mode_active:
            self.node.get_logger().debug(f"🌈 Ignoring voice direction {msg.data:.1f}° - rainbow demo mode active")
            return

        # Ignore voice directions when TTS is active to prevent following own voice
        if self.tts_active:
            self.node.get_logger().info(f"🔇 Ignoring voice direction {msg.data:.1f}° - TTS is active (robot is speaking)")
            return

        # Extract voice direction
        voice_direction = msg.data  # Angle in degrees
        current_time = self.node.get_clock().now()

        self.node.get_logger().info(f"📡 Received voice direction: {voice_direction:.1f}°")

        # Request transition to VOICE_FOLLOWING state if not already there
        current_state = self._get_current_state()
        if current_state != LuxoState.VOICE_FOLLOWING and not self.voice_following_state_requested:
            self.voice_following_previous_state = current_state
            self.voice_following_state_requested = True
            self._transition_to_voice_following_state()
            self.node.get_logger().info(f"🔄 Voice command received - transitioning from {current_state.name} to VOICE_FOLLOWING")

        # Check if we can process voice commands based on current state
        if not self._can_process_voice_command():
            self.node.get_logger().info(f"⏸️  Cannot process voice in state: {self._get_current_state().name}")
            return
        
        # Cooldown check - skip if too soon since last command (with adaptive multiplier)
        if self.last_voice_command_time is not None:
            # Apply adaptive cooldown multiplier to prevent thrashing
            effective_cooldown = self.voice_command_cooldown * self.adaptive_cooldown_multiplier
            time_since_last_command = (current_time - self.last_voice_command_time).nanoseconds / 1e9
            if time_since_last_command < effective_cooldown:
                remaining_cooldown = effective_cooldown - time_since_last_command
                adaptive_status = f" [ADAPTIVE x{self.adaptive_cooldown_multiplier:.1f}]" if self.adaptive_cooldown_multiplier > 1.0 else ""
                self.node.get_logger().info(
                    f"⏳ Voice command on cooldown for {remaining_cooldown:.1f}s more "
                    f"(direction: {voice_direction:.1f}°){adaptive_status}"
                )
                # Still update tracking even if we don't send command
                self.last_voice_direction = voice_direction
                self.last_voice_time = current_time
                return

        # Direction filtering - only ignore if similar direction AND robot is already at target
        # Apply adaptive filter multiplier to prevent thrashing
        if self.last_acted_voice_direction is not None:
            direction_diff = abs(voice_direction - self.last_acted_voice_direction)
            # Handle wraparound
            if direction_diff > 180:
                direction_diff = 360 - direction_diff

            # Apply adaptive filter threshold (increases when thrashing detected)
            effective_filter_threshold = self.voice_direction_filter_threshold * self.adaptive_filter_multiplier

            # Check if direction is similar to last acted direction
            if direction_diff < effective_filter_threshold:
                # Also check if robot has reached the target position
                # Convert voice direction to target angle
                target_angle_rad = np.deg2rad(voice_direction)
                target_angle = self.position_utils.normalize_angle(target_angle_rad)

                # Get current base position
                current_base = self.current_joints[0] if self.current_joints else 0

                # Calculate how far we are from the target
                angle_to_target = abs(self.position_utils.normalize_angle(target_angle - current_base))
                angle_to_target_deg = np.rad2deg(angle_to_target)

                # Only filter if we're already close to the target (within 10 degrees)
                if angle_to_target_deg < 10.0:
                    self.node.get_logger().info(
                        f"📍 Ignoring similar voice direction: {voice_direction:.1f}° "
                        f"(last: {self.last_acted_voice_direction:.1f}°, diff: {direction_diff:.1f}°, "
                        f"already at target: {angle_to_target_deg:.1f}° away)"
                    )
                    # Still update tracking but don't send command
                    self.last_voice_direction = voice_direction
                    self.last_voice_time = current_time
                    return
                else:
                    # Similar direction but NOT at target - resend command
                    self.node.get_logger().info(
                        f"🔄 Resending command for similar direction: {voice_direction:.1f}° "
                        f"(robot still {angle_to_target_deg:.1f}° from target)"
                    )
        
        # Update voice tracking
        self.last_voice_direction = voice_direction
        self.last_voice_time = current_time
        
        # Increase voice influence more aggressively
        self.voice_influence = min(1.0, self.voice_influence + 0.8)  # Very aggressive following
        
        # Convert voice direction to target angle with intelligent wraparound
        target_angle_rad = np.deg2rad(voice_direction)
        target_angle = self.position_utils.normalize_angle(target_angle_rad)

        # Log current robot position and target for debugging
        current_base = self.current_joints[0] if self.current_joints else 0
        current_base_deg = np.rad2deg(current_base)
        target_deg = np.rad2deg(target_angle)
        angle_diff = np.rad2deg(self.position_utils.normalize_angle(target_angle - current_base))

        self.node.get_logger().info(
            f"🎤 Voice Command: direction={voice_direction:.1f}°, "
            f"current_base={current_base_deg:.1f}°, "
            f"target={target_deg:.1f}°, "
            f"diff={angle_diff:.1f}°"
        )

        # Check if we need wraparound due to base limits
        if target_angle > self.base_max_limit:
            if self.enable_base_wraparound:
                # Calculate wraparound path
                wraparound_target = target_angle + 2 * np.pi
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
                wraparound_target = target_angle - 2 * np.pi
                if wraparound_target <= self.base_max_limit:
                    self.target_voice_angle = wraparound_target
                    self.node.get_logger().info(
                        f"Voice at {voice_direction}° beyond min limit - "
                        f"using wraparound to {np.rad2deg(wraparound_target):.1f}°"
                    )
                else:
                    self.target_voice_angle = self.base_min_limit
                    self.node.get_logger().warn(
                        f"Voice at {voice_direction}° unreachable - clamping to min limit"
                    )
            else:
                self.target_voice_angle = self.base_min_limit
                self.node.get_logger().warn(f"Voice beyond min limit - clamping (wraparound disabled)")
        else:
            self.target_voice_angle = target_angle
        
        # Record this as an acted direction and update cooldown
        self.last_acted_voice_direction = voice_direction
        self.last_voice_command_time = current_time

        # Update rest position to current target so robot doesn't reset later
        # This is the key to preventing the robot from returning to its original position
        if hasattr(self, 'last_rest_position') and self.last_rest_position is not None:
            self.last_rest_position[0] = self.target_voice_angle
            self.node.get_logger().info(
                f"Updated last_rest_position to voice target: {np.rad2deg(self.target_voice_angle):.1f}°"
            )

        # CRITICAL: Also update base_rest_position so it persists across state changes
        # Without this, _generate_rest_position() will use the old base position
        if hasattr(self, 'base_rest_position') and self.base_rest_position is not None:
            self.base_rest_position[0] = self.target_voice_angle
            self.node.get_logger().info(
                f"🔒 Updated base_rest_position to voice target: {np.rad2deg(self.target_voice_angle):.1f}° (STICKY)"
            )

        # Also update idle_base_position to prevent idle head variations from resetting
        if hasattr(self, 'idle_base_position') and self.idle_base_position is not None:
            self.idle_base_position[0] = self.target_voice_angle
            self.node.get_logger().debug(
                f"Updated idle_base_position to voice target: {np.rad2deg(self.target_voice_angle):.1f}°"
            )

        # Check if we're on target for variation purposes
        current_base = self.current_joints[0] if self.current_joints else 0
        angle_error = abs(self.position_utils.normalize_angle(self.target_voice_angle - current_base))
        
        if angle_error < np.deg2rad(self.voice_direction_tolerance):
            # We're on target
            if self.voice_on_target_start_time is None:
                self.voice_on_target_start_time = current_time
                self.node.get_logger().info("Voice following reached target - starting on-target timer")
        else:
            # Not on target, reset timer
            self.voice_on_target_start_time = None
            self.last_voice_variation_time = None
            self.current_voice_variation = None
        
        # Track movement for adaptive behavior (before sending command)
        self._track_movement_history(current_time)

        # Send direct command to follow voice
        self._send_voice_following_command()

        # Ensure continuous position feeding timer is running if we're in VOICE_FOLLOWING state
        current_state = self._get_current_state()
        if current_state == LuxoState.VOICE_FOLLOWING:
            # Check if timer is not already running
            if self.voice_position_timer is None or not hasattr(self, 'voice_position_timer_active'):
                # Start continuous position feeding timer (10Hz = 0.1s interval)
                if self.voice_position_timer is not None:
                    self.voice_position_timer.cancel()
                self.voice_position_timer = self.node.create_timer(0.1, self._voice_position_callback)
                self.voice_position_timer_active = True
                self.node.get_logger().info("🔄 Started continuous voice position feeding at 10Hz")

        # Reset completion timer since we received new voice input
        self.voice_completion_timer = current_time
    
    def voice_active_callback(self, msg):
        """Handle voice activity status."""
        self.voice_active = msg.data
        current_time = self.node.get_clock().now()
        
        if self.voice_active:
            # Voice is active, reset completion timer
            self.voice_completion_timer = current_time
        else:
            # Voice stopped, start completion timer if not already set
            if self.voice_completion_timer is None:
                self.voice_completion_timer = current_time
            
            # Voice stopped, start decay
            self.voice_influence *= 0.5  # Quick initial drop
            if self.voice_influence < 0.1:
                self.target_voice_angle = None
                self.voice_on_target_start_time = None
                self.last_voice_variation_time = None
                self.current_voice_variation = None
                self.node.get_logger().debug("Voice inactive - cleared voice following state")
    
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
    
    def _should_add_voice_variation(self) -> bool:
        """Check if we should add variation to voice following for face detection."""
        if not self.voice_variation_enabled:
            return False
        
        if not self.voice_on_target_start_time:
            return False
        
        current_time = self.node.get_clock().now()
        
        # Check if we've been on target long enough
        time_on_target = (current_time - self.voice_on_target_start_time).nanoseconds / 1e9
        if time_on_target < self.voice_on_target_threshold:
            return False
        
        # Check if enough time has passed since last variation
        if self.last_voice_variation_time:
            time_since_variation = (current_time - self.last_voice_variation_time).nanoseconds / 1e9
            if time_since_variation < self.voice_variation_interval:
                return False
        
        return True
    
    def _generate_voice_variation(self) -> List[float]:
        """Generate variation in non-base joints for better face detection."""
        current_time = self.node.get_clock().now()
        
        # Random choice of variation type
        variation_type = random.random()
        
        if variation_type < 0.45:  # Look up (45% chance)
            # Look up for better face detection
            shoulder_variation = random.uniform(0.1, self.voice_look_up_range)
            elbow_variation = random.uniform(-0.2, 0.1)
            wrist_variation = random.uniform(-0.1, 0.1)
            variation_description = "looking up"
        elif variation_type < 0.9:  # Look neutral/forward (45% chance)
            # Return closer to neutral for variety
            shoulder_variation = random.uniform(-0.1, 0.1)
            elbow_variation = random.uniform(-0.1, 0.1)
            wrist_variation = random.uniform(-0.05, 0.05)
            variation_description = "neutral position"
        elif variation_type < 0.95:  # Look down (5% chance)
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
        # Keep hand the same
        
        self.current_voice_variation = varied_position
        self.last_voice_variation_time = current_time
        
        self.node.get_logger().info(
            f"Voice variation: {variation_description} "
            f"(shoulder: {shoulder_variation:+.2f}, elbow: {elbow_variation:+.2f}, "
            f"wrist: {wrist_variation:+.2f})"
        )
        
        return varied_position

    def _track_movement_history(self, current_time):
        """Track base movement to detect thrashing behavior."""
        try:
            # Get current base position
            if not self.current_joints or len(self.current_joints) == 0:
                return

            current_base = self.current_joints[0]

            # Add to movement history
            self.movement_history.append((current_time, current_base))

            # Clean old entries (older than movement_history_duration)
            cutoff_time = current_time.nanoseconds / 1e9 - self.movement_history_duration
            self.movement_history = [
                (t, pos) for t, pos in self.movement_history
                if t.nanoseconds / 1e9 > cutoff_time
            ]

            # Detect thrashing (check every 0.5 seconds to avoid overhead)
            time_since_check = (current_time - self.last_adaptive_check_time).nanoseconds / 1e9
            if time_since_check > 0.5:
                self._detect_and_adapt_thrashing(current_time)
                self.last_adaptive_check_time = current_time

        except Exception as e:
            self.node.get_logger().error(f"Error tracking movement history: {e}")

    def _detect_and_adapt_thrashing(self, current_time):
        """Detect thrashing (rapid back-and-forth) and adapt parameters."""
        try:
            # Need at least 3 data points to detect reversals
            if len(self.movement_history) < 3:
                return

            # Count direction reversals in recent history
            reversals = 0
            cutoff_time = current_time.nanoseconds / 1e9 - self.thrashing_time_window

            # Get recent movements within the time window
            recent_movements = [
                (t, pos) for t, pos in self.movement_history
                if t.nanoseconds / 1e9 > cutoff_time
            ]

            if len(recent_movements) < 3:
                # Not enough recent data, apply gradual recovery
                self._apply_adaptive_recovery()
                return

            # Detect direction reversals (>120 degree changes)
            last_direction = 0
            for i in range(1, len(recent_movements)):
                prev_pos = recent_movements[i-1][1]
                curr_pos = recent_movements[i][1]

                # Calculate movement delta
                delta = self.position_utils.normalize_angle(curr_pos - prev_pos)

                # Determine direction (positive or negative)
                current_direction = 1 if delta > 0 else -1 if delta < 0 else 0

                # Check for large movement (>120 degrees)
                if abs(delta) > self.direction_reversal_threshold:
                    # Check if direction reversed
                    if last_direction != 0 and current_direction != 0 and last_direction != current_direction:
                        reversals += 1
                    last_direction = current_direction

            # Determine if we're thrashing
            was_thrashing = self.is_thrashing
            self.is_thrashing = (reversals >= self.thrashing_reversal_count)

            if self.is_thrashing:
                # Apply adaptive penalties
                if not was_thrashing:
                    self.node.get_logger().warn(
                        f"🌀 THRASHING DETECTED: {reversals} reversals in {self.thrashing_time_window:.1f}s - "
                        f"applying adaptive cooldown"
                    )

                # Increase cooldown and filter thresholds
                # Max multiplier of 6.0 (cooldown goes from 0.3s to 1.8s)
                self.adaptive_cooldown_multiplier = min(6.0, self.adaptive_cooldown_multiplier + 0.5)
                self.adaptive_filter_multiplier = min(3.0, self.adaptive_filter_multiplier + 0.3)

                self.node.get_logger().info(
                    f"📊 Adaptive params: cooldown={self.voice_command_cooldown * self.adaptive_cooldown_multiplier:.2f}s "
                    f"(x{self.adaptive_cooldown_multiplier:.1f}), "
                    f"filter={self.voice_direction_filter_threshold * self.adaptive_filter_multiplier:.1f}° "
                    f"(x{self.adaptive_filter_multiplier:.1f})"
                )
            else:
                # Apply gradual recovery when stable
                self._apply_adaptive_recovery()

        except Exception as e:
            self.node.get_logger().error(f"Error detecting thrashing: {e}")

    def _apply_adaptive_recovery(self):
        """Gradually reduce adaptive penalties when movement stabilizes."""
        try:
            # Only recover if we have penalties applied
            if self.adaptive_cooldown_multiplier <= 1.0 and self.adaptive_filter_multiplier <= 1.0:
                return

            # Gradually reduce multipliers (5% per check, which is ~10% per second)
            old_cooldown = self.adaptive_cooldown_multiplier
            old_filter = self.adaptive_filter_multiplier

            self.adaptive_cooldown_multiplier = max(1.0, self.adaptive_cooldown_multiplier * self.adaptive_recovery_rate)
            self.adaptive_filter_multiplier = max(1.0, self.adaptive_filter_multiplier * self.adaptive_recovery_rate)

            # Log when fully recovered
            if old_cooldown > 1.0 and self.adaptive_cooldown_multiplier == 1.0:
                self.node.get_logger().info("✅ Adaptive cooldown fully recovered - back to normal responsiveness")
                self.is_thrashing = False

        except Exception as e:
            self.node.get_logger().error(f"Error applying adaptive recovery: {e}")

    def _voice_position_callback(self):
        """Timer callback to continuously feed voice target position (10Hz like STAY mode)."""
        try:
            # Only feed position if we're in VOICE_FOLLOWING state and have a target
            if (self._get_current_state() == LuxoState.VOICE_FOLLOWING and
                self.target_voice_angle is not None):

                # Send voice following command continuously until target is reached
                self._send_voice_following_command()

        except Exception as e:
            self.node.get_logger().error(f"Error in voice position callback: {e}")

    def _transition_to_voice_following_state(self):
        """Request transition to VOICE_FOLLOWING state."""
        try:
            if hasattr(self, '_transition_to_state'):
                success = self._transition_to_state(LuxoState.VOICE_FOLLOWING)
                if success:
                    self.node.get_logger().info("✅ Successfully transitioned to VOICE_FOLLOWING state")

                    # Start continuous position feeding timer (10Hz = 0.1s interval)
                    if self.voice_position_timer is not None:
                        self.voice_position_timer.cancel()
                    self.voice_position_timer = self.node.create_timer(0.1, self._voice_position_callback)
                    self.node.get_logger().info("🔄 Started continuous voice position feeding at 10Hz")
                else:
                    self.node.get_logger().warn("Failed to transition to VOICE_FOLLOWING state")
            elif hasattr(self, 'request_state_transition_client'):
                # Use the service client directly if available
                self._request_voice_following_state_via_service()
            else:
                self.node.get_logger().warn("No state transition method available")
        except Exception as e:
            self.node.get_logger().error(f"Error transitioning to VOICE_FOLLOWING state: {e}")
    
    def _request_voice_following_state_via_service(self):
        """Request VOICE_FOLLOWING state via service client."""
        try:
            from luxo_interfaces.srv import RequestStateTransition
            
            if not self.request_state_transition_client.wait_for_service(timeout_sec=0.1):
                self.node.get_logger().debug("State manager service not available")
                return
            
            request = RequestStateTransition.Request()
            request.requested_state = 'VOICE_FOLLOWING'
            request.requesting_node = 'voice_following'
            request.priority = 90  # Very high priority for voice commands (increased from 75)
            request.force = False
            
            future = self.request_state_transition_client.call_async(request)
            self.node.get_logger().info("Requested transition to VOICE_FOLLOWING state")
            
        except Exception as e:
            self.node.get_logger().error(f"Error requesting voice following state: {e}")
    
    def _complete_voice_following(self):
        """Complete voice following and return to previous state."""
        try:
            # Determine return state
            if self.voice_following_previous_state and self.voice_following_previous_state != LuxoState.VOICE_FOLLOWING:
                return_state = self.voice_following_previous_state
            else:
                return_state = LuxoState.IDLE  # Default fallback

            # IMPORTANT: Store the final position BEFORE clearing voice state
            # This prevents the robot from resetting back to where it was
            if self.current_joints and len(self.current_joints) > 0:
                final_base_position = self.current_joints[0]
                self.node.get_logger().info(
                    f"💾 Voice following completed - preserving final position: {np.rad2deg(final_base_position):.1f}°"
                )

                # Update idle behavior's rest position to match where we ended up
                # This prevents idle animations from moving the robot back
                if hasattr(self, 'last_rest_position') and self.last_rest_position is not None:
                    # Update the base (first element) of the rest position
                    self.last_rest_position[0] = final_base_position
                    self.node.get_logger().info(
                        f"📍 Updated last_rest_position base to: {np.rad2deg(final_base_position):.1f}°"
                    )

                # CRITICAL: Also update base_rest_position to make it PERMANENT
                # This ensures the position persists even after _generate_rest_position() is called
                if hasattr(self, 'base_rest_position') and self.base_rest_position is not None:
                    self.base_rest_position[0] = final_base_position
                    self.node.get_logger().info(
                        f"🔒 Updated base_rest_position to final: {np.rad2deg(final_base_position):.1f}° (PERMANENT)"
                    )

                # CRITICAL: Also update idle_base_position to prevent idle head variations from resetting base
                # idle_base_position is used as reference in idle head variation generation
                if hasattr(self, 'idle_base_position') and self.idle_base_position is not None:
                    self.idle_base_position[0] = final_base_position
                    self.node.get_logger().info(
                        f"🔒 Updated idle_base_position to final: {np.rad2deg(final_base_position):.1f}° (STICKY IDLE)"
                    )

                # Delay idle animations to prevent immediate movement
                if hasattr(self, 'last_activity_time'):
                    self.last_activity_time = self.node.get_clock().now()
                    self.node.get_logger().info("⏰ Reset idle timer - delaying animations")

            self.node.get_logger().info(f"Voice following completed - returning to {return_state.name}")

            # Stop continuous position feeding timer
            if self.voice_position_timer is not None:
                self.voice_position_timer.cancel()
                self.voice_position_timer = None
                self.voice_position_timer_active = False
                self.node.get_logger().info("⏹️  Stopped continuous voice position feeding")

            # Reset voice following state tracking
            self.voice_following_state_requested = False
            self.voice_following_previous_state = None
            self.voice_completion_timer = None

            # Clear voice following state
            self.voice_influence = 0.0
            self.target_voice_angle = None
            self.voice_on_target_start_time = None
            self.last_voice_variation_time = None
            self.current_voice_variation = None

            # Reset adaptive tracking
            self.movement_history.clear()
            self.is_thrashing = False
            self.adaptive_cooldown_multiplier = 1.0
            self.adaptive_filter_multiplier = 1.0
            self.last_movement_direction = 0
            self.node.get_logger().debug("Reset adaptive movement tracking")

            # Request transition back to previous state
            if hasattr(self, '_transition_to_state'):
                self._transition_to_state(return_state)
            elif hasattr(self, 'request_state_transition_client'):
                self._request_completion_state_via_service(return_state)
            
        except Exception as e:
            self.node.get_logger().error(f"Error completing voice following: {e}")
    
    def _request_completion_state_via_service(self, return_state):
        """Request completion transition via service client."""
        try:
            from luxo_interfaces.srv import RequestStateTransition
            
            request = RequestStateTransition.Request()
            request.requested_state = return_state.name
            request.requesting_node = 'voice_behavior'
            request.priority = 75
            request.force = False
            if hasattr(request, 'completion'):
                request.completion = True
            
            future = self.request_state_transition_client.call_async(request)
            self.node.get_logger().info(f"Voice following completed - returning to {return_state.name}")
            
        except Exception as e:
            self.node.get_logger().error(f"Error requesting completion state: {e}")
    
    def _send_voice_following_command(self):
        """Send direct voice following command to target angle with optional variation."""
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
        
        # get a random acceleration value between 7 and 12
        acceleration = random.uniform(7.0, 12.0)

        # Add acceleration as the 6th element
        voice_position_with_accel = voice_position + [acceleration]

        # Get current base for comparison
        current_base_deg = np.rad2deg(self.current_joints[0]) if self.current_joints else 0.0
        target_base_deg = np.rad2deg(self.target_voice_angle)
        movement_deg = target_base_deg - current_base_deg

        self.node.get_logger().info(
            f"📤 Sending voice command: "
            f"current_base={current_base_deg:.1f}° → target={target_base_deg:.1f}° "
            f"(movement: {movement_deg:+.1f}°) "
            f"position: {[round(p, 2) for p in voice_position]}"
        )
        
        # Send the command with high priority
        self.send_safe_joint_command(voice_position_with_accel, "Voice following with variation")
        
        # Set this as a target override to prevent other systems from interfering
        self.target_override_active = True
        self.target_override_time = self.node.get_clock().now()
        self.target_override_joints = voice_position.copy()
        self.target_override_reason = "Voice following with face detection"
        self.target_override_timeout = 3.0  # Short timeout for voice following
    
    def apply_voice_following(self, positions: List[float]) -> List[float]:
        """
        Apply direct voice following to joint positions with variation support.
        
        Args:
            positions: Current joint positions
            
        Returns:
            Modified positions with voice following applied
        """
        if not self.voice_follow_enabled or self.voice_influence < 0.1:
            # If no voice following, check if we should maintain idle head variation
            if (hasattr(self, 'idle_head_variation_active') and 
                self.idle_head_variation_active and 
                hasattr(self, 'current_idle_head_target') and
                self.current_idle_head_target and 
                self._is_in_state(LuxoState.IDLE)):
                
                # Continue using the idle head variation target
                return self.current_idle_head_target.copy()
            return positions
        
        if self.target_voice_angle is None:
            return positions
        
        # DIRECT voice following - immediately use target angle
        voice_positions = positions.copy()
        voice_positions[0] = self.target_voice_angle
        
        # Add variation if we have one
        if self.current_voice_variation is not None:
            # Apply current variation to joints 1-4 (shoulder, elbow, wrist, hand)
            for i in range(1, min(5, len(voice_positions))):
                if i-1 < len(self.current_voice_variation):
                    voice_positions[i] = self.current_voice_variation[i-1]
        
        return voice_positions
    
    def update_voice_decay(self, current_time):
        """Update voice influence decay over time."""
        current_state = self._get_current_state()

        # CRITICAL: When in VOICE_FOLLOWING state, keep voice influence at maximum
        # This prevents decay from clearing the target while we're actively following
        if current_state == LuxoState.VOICE_FOLLOWING:
            self.voice_influence = 1.0  # Always max influence when in VOICE_FOLLOWING state

            # Check for voice following completion timeout
            if (self.voice_following_state_requested and
                self.voice_completion_timer):

                time_since_last_voice = (current_time - self.voice_completion_timer).nanoseconds / 1e9
                if time_since_last_voice > self.voice_completion_timeout:
                    self.node.get_logger().info(f"Voice inactive for {time_since_last_voice:.1f}s - completing voice following")
                    self._complete_voice_following()
            return  # Don't decay while in VOICE_FOLLOWING state

        # For other states, apply normal decay logic
        if self.last_voice_time:
            time_since_voice = (current_time - self.last_voice_time).nanoseconds / 1e9
            if time_since_voice > 0.5:  # Start decaying after 0.5 seconds
                self.voice_influence *= 0.9  # Gradual decay
                if self.voice_influence < 0.1:
                    # Clear voice state
                    self.voice_influence = 0.0
                    self.target_voice_angle = None
                    self.voice_on_target_start_time = None
                    self.last_voice_variation_time = None
                    self.current_voice_variation = None
            else:
                # Still active, keep influence high
                self.voice_influence = min(1.0, self.voice_influence + 0.1)
        else:
            # No voice received yet, keep influence at 0
            self.voice_influence = 0.0
