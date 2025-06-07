#!/usr/bin/env python3
"""
Voice Following Integration for CollisionAvoidance
Enhanced with spectral analysis support and improved voice detection
"""

import numpy as np
import time
from std_msgs.msg import Float32, Bool, String

class VoiceFollowingBehavior:
    """Enhanced mixin class for voice following behavior with spectral analysis"""
    
    def __init__(self):
        # Voice following parameters
        self.voice_follow_enabled = True
        self.voice_follow_speed = 0.3  # radians per second
        self.voice_follow_deadzone = 15.0  # degrees - don't move if within this angle
        self.voice_follow_max_adjustment = 0.5  # max radians to adjust per update
        self.voice_influence_decay = 0.95  # How quickly voice influence fades
        self.voice_timeout = 2.0  # seconds before considering voice inactive
        
        # Enhanced thresholds for better voice detection
        self.min_vad_confidence = 0.5  # Minimum VAD confidence
        self.min_spectral_confidence = 0.6  # Minimum spectral confidence
        self.combined_confidence_threshold = 0.7  # Combined threshold for strong voice detection
        
        # Voice tracking state
        self.last_voice_direction = None
        self.last_voice_time = None
        self.voice_influence = 0.0  # 0-1 scale of how much to follow voice
        self.target_voice_angle = None
        
        # Enhanced confidence tracking
        self.current_vad_confidence = 0.0
        self.current_spectral_confidence = 0.0
        self.combined_confidence = 0.0
        
        # Voice quality tracking for better filtering
        self.voice_quality_history = []
        self.max_quality_history = 10
        
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
        
        self.voice_confidence_sub = self.node.create_subscription(
            Float32,
            '/voice/confidence',
            self.voice_confidence_callback,
            10
        )
        
        # Subscribe to spectral confidence
        self.spectral_confidence_sub = self.node.create_subscription(
            Float32,
            '/voice/spectral_confidence',
            self.spectral_confidence_callback,
            10
        )
        
        # Subscribe to detailed voice info
        self.voice_info_sub = self.node.create_subscription(
            String,
            '/voice/info',
            self.voice_info_callback,
            10
        )
        
        self.node.get_logger().info("Enhanced voice following behavior initialized")
        self.node.get_logger().info(f"VAD threshold: {self.min_vad_confidence}, "
                                    f"Spectral threshold: {self.min_spectral_confidence}")
    
    def voice_confidence_callback(self, msg):
        """Handle VAD confidence updates"""
        self.current_vad_confidence = msg.data
        self._update_combined_confidence()
    
    def spectral_confidence_callback(self, msg):
        """Handle spectral confidence updates"""
        self.current_spectral_confidence = msg.data
        self._update_combined_confidence()
    
    def _update_combined_confidence(self):
        """Update combined confidence from VAD and spectral analysis"""
        # Weight spectral confidence more heavily as it's more reliable for voice
        self.combined_confidence = (
            0.3 * self.current_vad_confidence + 
            0.7 * self.current_spectral_confidence
        )
        
        # Track voice quality over time
        if len(self.voice_quality_history) >= self.max_quality_history:
            self.voice_quality_history.pop(0)
        self.voice_quality_history.append(self.combined_confidence)
    
    def voice_info_callback(self, msg):
        """Parse detailed voice information"""
        try:
            # Parse the info string: "direction:X,vad_confidence:Y,spectral_confidence:Z,..."
            info_parts = msg.data.split(',')
            for part in info_parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    if key == 'vad_confidence':
                        self.current_vad_confidence = float(value)
                    elif key == 'spectral_confidence':
                        self.current_spectral_confidence = float(value)
            
            self._update_combined_confidence()
        except Exception as e:
            self.node.get_logger().debug(f"Error parsing voice info: {e}")
    
    def get_voice_quality_score(self):
        """Get smoothed voice quality score"""
        if not self.voice_quality_history:
            return 0.0
        return np.mean(self.voice_quality_history)
    
    def voice_direction_callback(self, msg):
        """Handle voice direction updates with enhanced quality checking"""
        if not self.voice_follow_enabled:
            return
            
        # Only process if in appropriate state
        if not self.state_machine.is_in_state(LuxoState.IDLE, LuxoState.ANIMATING, LuxoState.EMOTION_REACTING):
            return
        
        # Enhanced quality check - require good combined confidence
        if self.combined_confidence < self.combined_confidence_threshold:
            self.node.get_logger().debug(
                f"Voice direction ignored - low combined confidence: {self.combined_confidence:.2f} "
                f"(VAD: {self.current_vad_confidence:.2f}, Spectral: {self.current_spectral_confidence:.2f})"
            )
            return
        
        # Additional quality gate - require consistent quality
        avg_quality = self.get_voice_quality_score()
        if avg_quality < 0.5:
            self.node.get_logger().debug(
                f"Voice direction ignored - poor average quality: {avg_quality:.2f}"
            )
            return
        
        # Update voice tracking
        self.last_voice_direction = msg.data  # Already in robot angle (-180 to 180)
        self.last_voice_time = self.node.get_clock().now()
        
        # Increase voice influence based on quality
        quality_multiplier = min(1.0, self.combined_confidence / self.combined_confidence_threshold)
        influence_increase = 0.2 * quality_multiplier
        self.voice_influence = min(1.0, self.voice_influence + influence_increase)
        
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
                f"High-quality voice detected at {self.last_voice_direction}°, "
                f"combined confidence: {self.combined_confidence:.2f}, "
                f"current base: {np.rad2deg(current_base):.1f}°, "
                f"target: {np.rad2deg(self.target_voice_angle):.1f}°"
            )
        else:
            self.node.get_logger().debug(
                f"Voice within deadzone: {angle_diff_deg:.1f}° < {self.voice_follow_deadzone}°"
            )
    
    def voice_active_callback(self, msg):
        """Handle voice activity status with enhanced decay"""
        if not msg.data:
            # Voice is not active, apply faster decay if quality was poor
            decay_rate = 0.9 if self.get_voice_quality_score() > 0.6 else 0.7
            self.voice_influence *= decay_rate
            
            # Clear quality history when voice becomes inactive
            if self.voice_influence < 0.1:
                self.voice_quality_history.clear()
    
    def apply_voice_following(self, target_positions):
        """Apply enhanced voice following influence to target positions"""
        if not self.voice_follow_enabled:
            return target_positions
            
        # Check if voice data is recent
        if self.last_voice_time is None:
            return target_positions
            
        current_time = self.node.get_clock().now()
        time_since_voice = (current_time - self.last_voice_time).nanoseconds / 1e9
        
        # Enhanced decay over time
        if time_since_voice > self.voice_timeout:
            self.voice_influence = 0.0
            self.target_voice_angle = None
            self.voice_quality_history.clear()
            return target_positions
        else:
            # Natural decay with quality consideration
            quality_factor = max(0.5, self.get_voice_quality_score())
            self.voice_influence *= self.voice_influence_decay * quality_factor
        
        # Apply voice following if we have a target and sufficient influence
        min_influence = 0.15  # Slightly higher threshold for better reliability
        if self.target_voice_angle is not None and self.voice_influence > min_influence:
            # Make a copy to avoid modifying original
            adjusted_positions = target_positions.copy()
            
            # Calculate adjustment
            current_base = adjusted_positions[0]
            angle_diff = self._normalize_angle(self.target_voice_angle - current_base)
            
            # Scale by influence and quality, limit maximum adjustment
            quality_factor = min(1.0, self.get_voice_quality_score() * 2)  # Boost quality factor
            adjustment = angle_diff * self.voice_influence * quality_factor * 0.3
            adjustment = np.clip(adjustment, -self.voice_follow_max_adjustment, self.voice_follow_max_adjustment)
            
            # Apply adjustment to base joint
            adjusted_positions[0] += adjustment
            
            # Log significant adjustments with quality info
            if abs(adjustment) > 0.05:
                self.node.get_logger().debug(
                    f"Voice following: adjusting base by {np.rad2deg(adjustment):.1f}° "
                    f"(influence: {self.voice_influence:.2f}, quality: {quality_factor:.2f}, "
                    f"combined_conf: {self.combined_confidence:.2f})"
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
        """Check if voice following should interrupt current behavior with enhanced criteria"""
        # More stringent requirements for interruption
        return (
            self.voice_influence > 0.8 and  # Higher influence threshold
            self.combined_confidence > 0.8 and  # High combined confidence
            self.get_voice_quality_score() > 0.7 and  # Good sustained quality
            self.last_voice_time is not None and
            (self.node.get_clock().now() - self.last_voice_time).nanoseconds / 1e9 < 0.3  # Very recent
        )
    
    def get_voice_following_status(self):
        """Get detailed status for debugging"""
        return {
            'enabled': self.voice_follow_enabled,
            'influence': self.voice_influence,
            'vad_confidence': self.current_vad_confidence,
            'spectral_confidence': self.current_spectral_confidence,
            'combined_confidence': self.combined_confidence,
            'quality_score': self.get_voice_quality_score(),
            'last_direction': self.last_voice_direction,
            'target_angle': self.target_voice_angle,
            'time_since_voice': (
                (self.node.get_clock().now() - self.last_voice_time).nanoseconds / 1e9 
                if self.last_voice_time else None
            )
        }