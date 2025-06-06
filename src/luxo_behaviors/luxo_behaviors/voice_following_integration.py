#!/usr/bin/env python3
"""
Voice Following Integration for CollisionAvoidance
Add this to your collision_avoidance.py or use as a mixin
"""

import numpy as np
import time
from std_msgs.msg import Float32, Bool

class VoiceFollowingBehavior:
    """Mixin class for voice following behavior"""
    
    def __init__(self):
        # Voice following parameters
        self.voice_follow_enabled = True
        self.voice_follow_speed = 0.3  # radians per second
        self.voice_follow_deadzone = 15.0  # degrees - don't move if within this angle
        self.voice_follow_max_adjustment = 0.5  # max radians to adjust per update
        self.voice_influence_decay = 0.95  # How quickly voice influence fades
        self.voice_timeout = 2.0  # seconds before considering voice inactive
        
        # Voice tracking state
        self.last_voice_direction = None
        self.last_voice_time = None
        self.voice_influence = 0.0  # 0-1 scale of how much to follow voice
        self.target_voice_angle = None
        
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
        
        self.node.get_logger().info("Voice following behavior initialized")
    
    def voice_direction_callback(self, msg):
        """Handle voice direction updates"""
        if not self.voice_follow_enabled:
            return
            
        # Only process if in appropriate state
        if not self.state_machine.is_in_state(LuxoState.IDLE, LuxoState.ANIMATING, LuxoState.EMOTION_REACTING):
            return
        
        # Update voice tracking
        self.last_voice_direction = msg.data  # Already in robot angle (-180 to 180)
        self.last_voice_time = self.node.get_clock().now()
        
        # Increase voice influence when voice is detected
        self.voice_influence = min(1.0, self.voice_influence + 0.2)
        
        # Calculate target angle for base joint
        current_base = self.current_joints[0] if self.current_joints else 0.0
        
        # Convert voice direction to radians
        voice_angle_rad = np.deg2rad(self.last_voice_direction)
        
        # Calculate the difference
        angle_diff = self._normalize_angle(voice_angle_rad - current_base)
        angle_diff_deg = np.rad2deg(abs(angle_diff))
        
        # Only update if outside deadzone
        if angle_diff_deg > self.voice_follow_deadzone:
            self.target_voice_angle = current_base + angle_diff
            self.node.get_logger().debug(
                f"Voice detected at {self.last_voice_direction}°, "
                f"current base: {np.rad2deg(current_base):.1f}°, "
                f"target: {np.rad2deg(self.target_voice_angle):.1f}°"
            )
    
    def voice_active_callback(self, msg):
        """Handle voice activity status"""
        if not msg.data:
            # Voice is not active, start decay
            self.voice_influence *= 0.9
    
    def apply_voice_following(self, target_positions):
        """Apply voice following influence to target positions
        
        This should be called in your collision avoidance update loop
        """
        if not self.voice_follow_enabled:
            return target_positions
            
        # Check if voice data is recent
        if self.last_voice_time is None:
            return target_positions
            
        current_time = self.node.get_clock().now()
        time_since_voice = (current_time - self.last_voice_time).nanoseconds / 1e9
        
        # Decay influence over time
        if time_since_voice > self.voice_timeout:
            self.voice_influence = 0.0
            self.target_voice_angle = None
            return target_positions
        else:
            # Natural decay
            self.voice_influence *= self.voice_influence_decay
        
        # Apply voice following if we have a target and influence
        if self.target_voice_angle is not None and self.voice_influence > 0.1:
            # Make a copy to avoid modifying original
            adjusted_positions = target_positions.copy()
            
            # Calculate adjustment
            current_base = adjusted_positions[0]
            angle_diff = self._normalize_angle(self.target_voice_angle - current_base)
            
            # Scale by influence and limit maximum adjustment
            adjustment = angle_diff * self.voice_influence * 0.3  # 30% of the difference
            adjustment = np.clip(adjustment, -self.voice_follow_max_adjustment, self.voice_follow_max_adjustment)
            
            # Apply adjustment to base joint
            adjusted_positions[0] += adjustment
            
            # Log significant adjustments
            if abs(adjustment) > 0.05:
                self.node.get_logger().debug(
                    f"Voice following: adjusting base by {np.rad2deg(adjustment):.1f}° "
                    f"(influence: {self.voice_influence:.2f})"
                )
            
            return adjusted_positions
        
        return target_positions
    
    def _normalize_angle(self, angle):
        """Normalize angle to [-pi, pi]"""
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle
    
    def should_interrupt_for_voice(self):
        """Check if voice following should interrupt current behavior"""
        # Only interrupt if voice is strong and persistent
        return (self.voice_influence > 0.7 and 
                self.last_voice_time is not None and
                (self.node.get_clock().now() - self.last_voice_time).nanoseconds / 1e9 < 0.5)