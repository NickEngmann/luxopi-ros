#!/usr/bin/env python3
"""
Voice Following Integration - Simplified to work with exact vad_doa.py copy
"""

import numpy as np
import time
from std_msgs.msg import Float32, Bool

class VoiceFollowingBehavior:
    """Simplified voice following behavior matching vad_doa.py reliability"""
    
    def __init__(self):
        # Simple voice following parameters
        self.voice_follow_enabled = True
        self.voice_timeout = 2.0  # seconds before considering voice inactive
        
        # Voice tracking state - minimal
        self.last_voice_direction = None
        self.last_voice_time = None
        self.voice_active = False
        self.target_voice_angle = None
        
        # Create subscribers for voice data - minimal set
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
        
        self.node.get_logger().info("Simplified voice following behavior initialized")
    
    def voice_direction_callback(self, msg):
        """Handle voice direction updates - simple and direct"""
        if not self.voice_follow_enabled:
            return
            
        # Update voice tracking
        self.last_voice_direction = msg.data
        self.last_voice_time = self.node.get_clock().now()
        
        # Convert voice direction to target angle
        voice_angle_rad = np.deg2rad(self.last_voice_direction)
        self.target_voice_angle = self._normalize_angle(voice_angle_rad)
        
        self.node.get_logger().info(f"Voice detected at {self.last_voice_direction}°")

    def voice_active_callback(self, msg):
        """Handle voice activity status"""
        self.voice_active = msg.data
    
    def apply_voice_following(self, target_positions):
        """Apply voice following influence to target positions - direct and simple"""
        if not self.voice_follow_enabled or not self.voice_active:
            return target_positions
            
        # Check if voice data is recent
        if self.last_voice_time is None:
            return target_positions
            
        current_time = self.node.get_clock().now()
        time_since_voice = (current_time - self.last_voice_time).nanoseconds / 1e9
        
        # Voice timeout
        if time_since_voice > self.voice_timeout:
            self.target_voice_angle = None
            return target_positions
        
        # Apply voice following if we have a target
        if self.target_voice_angle is not None:
            # Make a copy to avoid modifying original
            adjusted_positions = target_positions.copy()
            
            # Set base joint directly to target angle
            adjusted_positions[0] = self.target_voice_angle
            
            self.node.get_logger().info(f"Voice following: setting base to {np.rad2deg(self.target_voice_angle):.1f}°")
            
            return adjusted_positions
        
        return target_positions

    def _normalize_angle(self, angle):
        """Normalize angle to [-pi, pi] range"""
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle <= -np.pi:
            angle += 2 * np.pi
        return angle

    def should_interrupt_for_voice(self):
        """Check if voice following should interrupt current behavior"""
        return (
            self.voice_active and
            self.target_voice_angle is not None and
            self.last_voice_time is not None and
            (self.node.get_clock().now() - self.last_voice_time).nanoseconds / 1e9 < 0.5
        )
    
    def get_voice_following_status(self):
        """Get status for debugging"""
        return {
            'enabled': self.voice_follow_enabled,
            'active': self.voice_active,
            'last_direction': self.last_voice_direction,
            'target_angle': self.target_voice_angle,
            'time_since_voice': (
                (self.node.get_clock().now() - self.last_voice_time).nanoseconds / 1e9 
                if self.last_voice_time else None
            )
        }