#!/usr/bin/env python3
"""
Voice Following Integration for CollisionAvoidance
Enhanced with spectral analysis support and improved voice detection
"""

import numpy as np
import time
from std_msgs.msg import Float32, Bool, String
from collections import deque

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
        
        # MATCH STANDALONE: More lenient thresholds
        # The standalone script uses 40% speech detection and no additional confidence checks
        self.min_vad_confidence = 0.2  # Very lenient VAD threshold
        self.min_spectral_confidence = 0.3  # Very lenient spectral threshold
        self.combined_confidence_threshold = 0.3  # Much lower combined threshold
        self.min_snr_threshold = -10.0  # Very lenient SNR (standalone doesn't strictly enforce SNR)
        
        # Voice tracking state
        self.last_voice_direction = None
        self.last_voice_time = None
        self.voice_influence = 0.0  # 0-1 scale of how much to follow voice
        self.target_voice_angle = None
        
        # Enhanced confidence tracking
        self.current_vad_confidence = 0.0
        self.current_spectral_confidence = 0.0
        self.combined_confidence = 0.0
        self.current_snr = 0.0
        
        # Voice quality tracking for better filtering
        self.voice_quality_history = []
        self.snr_history = deque(maxlen=10)  # Track SNR over time
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
        
        # Subscribe to SNR
        self.snr_sub = self.node.create_subscription(
            Float32,
            '/voice/snr',
            self.snr_callback,
            10
        )
        
        self.node.get_logger().info("Enhanced voice following behavior initialized")
        self.node.get_logger().info(f"VAD threshold: {self.min_vad_confidence}, "
                                    f"Spectral threshold: {self.min_spectral_confidence}, "
                                    f"Combined threshold: {self.combined_confidence_threshold}, "
                                    f"SNR threshold: {self.min_snr_threshold} dB")
    
    def voice_confidence_callback(self, msg):
        """Handle VAD confidence updates"""
        self.current_vad_confidence = msg.data
        self._update_combined_confidence()
    
    def spectral_confidence_callback(self, msg):
        """Handle spectral confidence updates"""
        self.current_spectral_confidence = msg.data
        self._update_combined_confidence()
    
    def snr_callback(self, msg):
        """Handle SNR updates"""
        self.current_snr = msg.data
        self.snr_history.append(self.current_snr)
    
    def get_average_snr(self):
        """Get smoothed SNR over recent history"""
        if not self.snr_history:
            return 0.0
        return np.mean(list(self.snr_history))
    
    def _update_combined_confidence(self):
        """Update combined confidence from VAD, spectral analysis, and SNR"""
        # MATCH STANDALONE: Simple confidence calculation without strict requirements
        # The standalone mostly relies on VAD with spectral as confirmation
        base_confidence = max(self.current_vad_confidence, self.current_spectral_confidence)
        
        # Very lenient SNR handling - don't penalize too much
        avg_snr = self.get_average_snr()
        if avg_snr > 3.0:  # Good SNR
            snr_multiplier = 1.1
        elif avg_snr < self.min_snr_threshold:  # Poor SNR
            snr_multiplier = 0.9  # Only slight penalty
        else:  # Acceptable SNR
            snr_multiplier = 1.0
        
        self.combined_confidence = base_confidence * snr_multiplier
        
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
        """Handle voice direction updates with direct angle targeting - no complex wraparound logic"""
        if not self.voice_follow_enabled:
            return
            
        # Only process if in appropriate state
        if not self.state_machine.is_in_state(LuxoState.IDLE, LuxoState.ANIMATING, LuxoState.EMOTION_REACTING):
            return
        
        if self.combined_confidence < self.combined_confidence_threshold:
            # Still log but with lower frequency
            if hasattr(self, '_last_low_confidence_log') and time.time() - self._last_low_confidence_log < 1.0:
                pass  # Skip logging
            else:
                self._last_low_confidence_log = time.time()
                self.node.get_logger().debug(
                    f"Voice direction ignored - low combined confidence: {self.combined_confidence:.2f} "
                    f"(VAD: {self.current_vad_confidence:.2f}, Spectral: {self.current_spectral_confidence:.2f}, "
                    f"SNR: {self.current_snr:.1f}dB)"
                )
            return
        
        # Update voice tracking
        self.last_voice_direction = msg.data
        self.last_voice_time = self.node.get_clock().now()
        
        # Full influence - we want aggressive following
        self.voice_influence = 1.0
        
        # Convert voice direction DIRECTLY to target angle
        voice_angle_rad = np.deg2rad(self.last_voice_direction)
        
        # Normalize to robot's coordinate system [-pi, pi]
        self.target_voice_angle = self._normalize_angle(voice_angle_rad)
        
        self.node.get_logger().info(
            f"Voice detected at {self.last_voice_direction}°, "
            f"setting DIRECT target: {np.rad2deg(self.target_voice_angle):.1f}°, "
            f"combined confidence: {self.combined_confidence:.2f}, "
            f"SNR: {self.get_average_snr():.1f}dB"
        )

    def voice_active_callback(self, msg):
        """Handle voice activity status with enhanced decay"""
        if not msg.data:
            # Voice is not active, apply simple decay
            self.voice_influence *= 0.85  # Slower decay for smoother behavior
            
            # Clear quality history when voice becomes inactive for a while
            if self.voice_influence < 0.1:
                self.voice_quality_history.clear()
                self.snr_history.clear()
    
    def apply_voice_following(self, target_positions):
        """Apply DIRECT voice following influence to target positions"""
        if not self.voice_follow_enabled:
            return target_positions
            
        # Check if voice data is recent
        if self.last_voice_time is None:
            return target_positions
            
        current_time = self.node.get_clock().now()
        time_since_voice = (current_time - self.last_voice_time).nanoseconds / 1e9
        
        # Voice timeout
        if time_since_voice > self.voice_timeout:
            self.voice_influence = 0.0
            self.target_voice_angle = None
            self.voice_quality_history.clear()
            return target_positions
        
        # Apply DIRECT voice following if we have a target
        if self.target_voice_angle is not None and self.voice_influence > 0.5:
            # Make a copy to avoid modifying original
            adjusted_positions = target_positions.copy()
            
            # Set base joint DIRECTLY to target angle - no gradual adjustment
            adjusted_positions[0] = self.target_voice_angle
            
            self.node.get_logger().info(
                f"Voice following: setting base DIRECTLY to {np.rad2deg(self.target_voice_angle):.1f}° "
                f"(influence: {self.voice_influence:.2f})"
            )
            
            return adjusted_positions
        
        return target_positions

    def _normalize_angle(self, angle):
        """Normalize angle to [-pi, pi] range consistently"""
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle <= -np.pi:
            angle += 2 * np.pi
        return angle

    def should_interrupt_for_voice(self):
        """Check if voice following should interrupt current behavior with enhanced criteria"""
        # MATCH STANDALONE: Less strict interruption criteria
        avg_snr = self.get_average_snr()
        return (
            self.voice_influence > 0.5 and  # Lower influence threshold
            self.combined_confidence > 0.4 and  # Much lower confidence threshold
            self.last_voice_time is not None and
            (self.node.get_clock().now() - self.last_voice_time).nanoseconds / 1e9 < 0.5
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
            'snr': self.current_snr,
            'avg_snr': self.get_average_snr(),
            'last_direction': self.last_voice_direction,
            'target_angle': self.target_voice_angle,
            'time_since_voice': (
                (self.node.get_clock().now() - self.last_voice_time).nanoseconds / 1e9 
                if self.last_voice_time else None
            )
        }