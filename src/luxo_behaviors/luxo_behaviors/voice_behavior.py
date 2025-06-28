#!/usr/bin/env python3
#voice_behavior.py
"""
Voice behavior module for Luxo robot.
Handles voice direction following and face detection variations.
"""

import random
import time
from typing import Optional, List, Tuple
from std_msgs.msg import Float32, Bool
from luxo_behaviors.state_machine import LuxoState
import numpy as np


class VoiceBehavior:
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
            self.node.declare_parameter('voice_look_up_range', 1.0)
        if not self.node.has_parameter('voice_look_down_range'):
            self.node.declare_parameter('voice_look_down_range', 0.2)
        
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
        self.voice_on_target_threshold = 3.0  # seconds to wait before starting variations
        
        # Voice command cooldown and direction filtering
        self.voice_command_cooldown = 2.5  # seconds between voice commands
        self.last_voice_command_time = None  # Initialize to None to allow immediate first command
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
    
    def voice_direction_callback(self, msg):
        """Handle voice direction messages with cooldown and filtering."""
        if not self.voice_follow_enabled:
            return
        
        # Extract voice direction
        voice_direction = msg.data  # Angle in degrees
        current_time = self.node.get_clock().now()
        
        # Check if we can process voice commands based on current state
        if not self._can_process_voice_command():
            self.node.get_logger().debug(f"Ignoring voice direction in state: {self._get_current_state().name}")
            return
        
        # Cooldown check - skip if too soon since last command
        if self.last_voice_command_time is not None:
            time_since_last_command = (current_time - self.last_voice_command_time).nanoseconds / 1e9
            if time_since_last_command < self.voice_command_cooldown:
                remaining_cooldown = self.voice_command_cooldown - time_since_last_command
                self.node.get_logger().debug(
                    f"Voice command on cooldown for {remaining_cooldown:.1f}s more "
                    f"(direction: {voice_direction:.1f}°)"
                )
                # Still update tracking even if we don't send command
                self.last_voice_direction = voice_direction
                self.last_voice_time = current_time
                return
        
        # Direction filtering - ignore if too close to last acted direction
        if self.last_acted_voice_direction is not None:
            direction_diff = abs(voice_direction - self.last_acted_voice_direction)
            # Handle wraparound
            if direction_diff > 180:
                direction_diff = 360 - direction_diff
            
            if direction_diff < self.voice_direction_filter_threshold:
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
        
        # Send direct command to follow voice
        self._send_voice_following_command()
    
    def voice_active_callback(self, msg):
        """Handle voice activity status."""
        self.voice_active = msg.data
        
        if not self.voice_active:
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
            LuxoState.ANIMATING  # Allow during animations
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
        if self.last_voice_time:
            time_since_voice = (current_time - self.last_voice_time).nanoseconds / 1e9
            if time_since_voice > 0.5:  # Start decaying after 0.5 seconds
                self.voice_influence *= 0.6  # Gradual decay
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
