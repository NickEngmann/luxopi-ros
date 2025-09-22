#!/usr/bin/env python3
#idle_behavior.py
"""
Idle behavior module for Luxo robot.
Handles idle animations and head variations.
"""

import random
import time
from typing import Optional, List
from rclpy.action import ActionClient
from luxo_interfaces.action import PlayAnimation
from luxo_behaviors.state_machine import LuxoState
from luxo_behaviors.shared_utils import IdleAnimationConfig
import numpy as np


class IdleBehavior:
    """Mixin class for idle behavior functionality."""
    
    def setup_idle_behavior(self):
        """Initialize idle behavior attributes and action clients."""
        # Idle animation configuration
        self.idle_config = IdleAnimationConfig()
        self.idle_animations = self.idle_config.idle_animations
        self.idle_animations_enabled = True  # Can be disabled if needed
        
        # Idle animation tracking
        self.last_idle_animation = None
        self.min_idle_time_before_animation = self.idle_config.min_idle_time_before_animation
        self.idle_animation_interval = random.uniform(
            self.idle_config.idle_animation_interval_min, 
            self.idle_config.idle_animation_interval_max
        )
        self.last_idle_animation_time = self.node.get_clock().now()
        
        # Idle head variation tracking
        self.idle_head_variation_enabled = False  # Will be set by hardware interface
        self.idle_head_variation_interval = 5.0  # Maximum interval - actual will be random 1.0 to this value
        self.idle_head_base_rotation_range = 0.3
        self.idle_head_look_up_range = 0.6
        self.idle_head_look_down_range = 0.15
        self.idle_head_variation_speed = 4.0
        self.last_idle_head_variation_time = self.node.get_clock().now()
        self.current_idle_head_target = None
        self.idle_head_variation_active = False
        self.idle_base_position = [0.0, -0.55, 1.2, 1.0, 2.0]  # Standard idle position (without antenna)
        self.idle_antenna_min = 0.5  # Minimum antenna position
        self.idle_antenna_max = 2.6  # Maximum antenna position
        
        # Create action client for triggering animations
        self._idle_animation_client = ActionClient(
            self.node,
            PlayAnimation,
            'play_animation'
        )
        
        self.node.get_logger().info("Idle behavior initialized")
    
    def check_idle_animations(self, current_time) -> bool:
        """
        Check if we should trigger an idle animation.
        Returns True if an animation was triggered.
        """
        # Only trigger idle animations in IDLE state
        if not self._is_in_state(LuxoState.IDLE):
            return False
        
        # Check if idle animations are enabled
        if not getattr(self, 'idle_animations_enabled', True):
            return False
        
        # Check for any active collisions
        if any(status['active'] for status in self.collision_status.values()):
            return False
        
        time_since_activity = (current_time - self.last_activity_time).nanoseconds / 1e9
        time_since_last_animation = (current_time - self.last_idle_animation_time).nanoseconds / 1e9
        
        # Check if voice is very active (only very recent voice should affect idle)
        voice_very_active = False
        if hasattr(self, 'voice_active') and self.voice_active and hasattr(self, 'last_voice_time'):
            if self.last_voice_time is not None:
                time_since_voice = (current_time - self.last_voice_time).nanoseconds / 1e9
            else:
                time_since_voice = float('inf')
            voice_very_active = time_since_voice < 2.0  # Only consider very recent voice activity
        
        if voice_very_active:
            self.node.get_logger().debug("Very recent voice activity - allowing idle animations to coexist")
        
        # If we've been idle for a while and enough time has passed since last animation
        if (time_since_activity > self.min_idle_time_before_animation and 
            time_since_last_animation > self.idle_animation_interval):
            
            self.node.get_logger().info(
                f"Device idle for {time_since_activity:.1f}s - triggering idle animation "
                f"(voice influence: {getattr(self, 'voice_influence', 0.0):.2f})"
            )
            
            # Trigger a random idle animation
            self.trigger_idle_animation()
            
            # Update timers
            self.last_idle_animation_time = current_time
            self.idle_animation_interval = random.uniform(
                self.idle_config.idle_animation_interval_min,
                self.idle_config.idle_animation_interval_max
            )
            
            return True
        
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
            
            # Only clear idle head variation, not voice following
            if self.idle_head_variation_active:
                self.idle_head_variation_active = False
                self.current_idle_head_target = None
                self.node.get_logger().info("Cleared idle head variation for animation")
            
            # Allow voice following to continue during idle animations
            current_voice_influence = getattr(self, 'voice_influence', 0.0)
            if current_voice_influence > 0.1:
                self.node.get_logger().info(
                    f"Triggering idle animation while voice following active "
                    f"(influence: {current_voice_influence:.2f})"
                )
            
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
            
            self.node.get_logger().info(
                f"Triggering idle animation: {selected_animation} "
                f"(speed: {goal.speed_multiplier:.1f})"
            )
            
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
                self.node.get_logger().info("Idle animation goal rejected")
                return
            
            self.node.get_logger().info("Idle animation goal accepted")
            
        except Exception as e:
            self.node.get_logger().error(f"Error in idle animation response: {e}")
    
    def check_idle_head_variation(self, current_time) -> bool:
        """
        Check if we should apply idle head variation.
        Returns True if variation is active.
        """
        self.node.get_logger().debug(f"Checking idle head variation: enabled={self.idle_head_variation_enabled}, voice_influence={getattr(self, 'voice_influence', 0.0)}")
        # Only apply idle head variations in IDLE state
        if not self._is_in_state(LuxoState.IDLE):
            self.idle_head_variation_active = False
            self.current_idle_head_target = None
            return False
        
        # Check if enabled
        if not self.idle_head_variation_enabled:
            return False
        
        # Don't apply if we're doing voice following
        if hasattr(self, 'voice_influence') and self.voice_influence > 0.1:
            self.idle_head_variation_active = False
            self.current_idle_head_target = None
            return False
        
        # Check if it's time for a new variation
        time_since_last_variation = (current_time - self.last_idle_head_variation_time).nanoseconds / 1e9
        
        # Use random interval between 0.75 and idle_head_variation_interval
        current_interval = getattr(self, '_current_idle_variation_interval', self.idle_head_variation_interval)
        
        if time_since_last_variation > current_interval:
            # Generate new idle head target
            self._generate_idle_head_variation()
            
            # Set new random interval for next variation
            self._current_idle_variation_interval = random.uniform(0.75, self.idle_head_variation_interval)
            self.last_idle_head_variation_time = current_time
            
            return True
        
        return self.idle_head_variation_active
    
    def _generate_idle_head_variation(self):
        """Generate a new idle head variation target."""
        try:
            # Start with current position
            base_position = self.current_joints.copy()
            
            # Generate random variation for base rotation
            base_variation = random.uniform(
                -self.idle_head_base_rotation_range, 
                self.idle_head_base_rotation_range
            )
            
            # Apply variation to base, keeping within limits
            new_base = self.position_utils.normalize_angle(base_position[0] + base_variation)
            new_base = np.clip(new_base, self.base_min_limit, self.base_max_limit)
            base_position[0] = new_base
            
            # For other joints, use the idle base position as reference but apply looking up bias
            # Bias towards looking up (70% chance) as it appears more alert/curious
            look_type = random.random()
            if look_type < 0.7:  # Look up (70% chance)
                shoulder_variation = random.uniform(0.1, self.idle_head_look_up_range)
                base_position[1] = self.idle_base_position[1] - shoulder_variation  # More positive = looking up
                variation_description = f"looking up (+{shoulder_variation:.2f})"
            elif look_type < 0.9:  # Look down slightly (20% chance)
                shoulder_variation = random.uniform(0.0, self.idle_head_look_down_range)
                base_position[1] = self.idle_base_position[1] + shoulder_variation  # More negative = looking down
                variation_description = f"looking down (-{shoulder_variation:.2f})"
            else:  # Stay neutral (10% chance)
                base_position[1] = self.idle_base_position[1]  # Use base idle position
                variation_description = "staying neutral"
            
            # Use base idle position for elbow, wrist, hand with small variations
            base_position[2] = self.idle_base_position[2]  # Start with base idle elbow
            base_position[3] = self.idle_base_position[3]  # Start with base idle wrist
            base_position[4] = self.idle_base_position[4]  # Start with base idle hand

            # Add tiny variations to other joints for naturalness, but keep neck straighter
            # Only add elbow variation 30% of the time to keep neck less crooked
            if random.random() < 0.3:
                base_position[2] += random.uniform(-0.02, 0.02)  # Reduced elbow adjustment
            # Only add wrist variation 20% of the time
            if random.random() < 0.2:
                base_position[3] += random.uniform(-0.01, 0.01)  # Reduced wrist adjustment

            # Add antenna movement that correlates with the head movement
            # When looking up (alert/curious), antenna tends to perk up (positive)
            # When looking down or neutral, antenna can droop or stay neutral

            # Ensure we have space for antenna value (7 elements total)
            while len(base_position) < 7:
                if len(base_position) == 5:
                    base_position.append(10.0)  # Default acceleration at index 5
                else:
                    base_position.append(0.0)  # Default antenna at index 6

            # Generate antenna variation based on head position
            # Use range 0.5 to 2.6 for realistic movement
            if look_type < 0.7:  # Looking up - antenna perks up (70% chance)
                # When alert/curious, antenna goes up (1.5 to 2.6)
                antenna_variation = random.uniform(1.5, self.idle_antenna_max)
            elif look_type < 0.9:  # Looking down - antenna droops (20% chance)
                # When looking down, antenna droops (0.5 to 1.2)
                antenna_variation = random.uniform(self.idle_antenna_min, 1.2)
            else:  # Neutral - mid-range movement (10% chance)
                # Neutral position varies in middle range (0.8 to 2.0)
                antenna_variation = random.uniform(0.8, 2.0)

            # Apply antenna variation at index 6
            base_position[6] = antenna_variation

            # Rate-limited logging for antenna variations
            if not hasattr(self, '_last_antenna_variation_log_time'):
                self._last_antenna_variation_log_time = 0

            current_time = self.node.get_clock().now().nanoseconds / 1e9
            if current_time - self._last_antenna_variation_log_time >= 1.0:
                self.node.get_logger().info(f"Added antenna variation: {antenna_variation:.2f} for {variation_description}")
                self._last_antenna_variation_log_time = current_time

            # Set the new target
            self.current_idle_head_target = base_position
            self.idle_head_variation_active = True
            
            self.node.get_logger().info(
                f"Generated idle head variation: base {np.rad2deg(base_variation):.1f}°, {variation_description}"
            )
            
        except Exception as e:
            self.node.get_logger().error(f"Error generating idle head variation: {e}")
            self.idle_head_variation_active = False
    
    def apply_idle_head_variation(self, positions: List[float]) -> List[float]:
        """
        Apply idle head variation to joint positions if active.
        
        Args:
            positions: Current joint positions
            
        Returns:
            Modified positions with idle variation applied
        """
        if not self.idle_head_variation_active or not self.current_idle_head_target:
            return positions
        
        # Only apply in IDLE state
        if not self._is_in_state(LuxoState.IDLE):
            self.idle_head_variation_active = False
            self.current_idle_head_target = None
            return positions
        
        # Don't apply if voice following is active
        if hasattr(self, 'voice_influence') and self.voice_influence > 0.1:
            return positions
        
        # Use the idle head target
        return self.current_idle_head_target.copy()
    
    def check_extended_idle_timeout(self, current_time) -> bool:
        """
        Check if robot has been idle long enough to return home.
        Returns True if we should return home.
        """
        time_since_activity = (current_time - self.last_activity_time).nanoseconds / 1e9
        
        # Check if we're already at home position
        already_at_home = self._at_position(self.current_joints, self.home_position_2, self.home_position_tolerance)
        
        # Extended idle timeout
        if (time_since_activity > 180.0 and  # 3 minutes
            self._is_in_state(LuxoState.IDLE) and 
            not already_at_home):
            
            self.node.get_logger().info(
                f"Device idle for {time_since_activity:.1f}s - returning to home position"
            )
            
            # Request state transition to RETURNING_HOME
            if self._transition_to_state(LuxoState.RETURNING_HOME):
                self.is_returning_to_rest = True
                self.go_to_rest_position("Extended idle timeout")
                return True
            else:
                self.node.get_logger().warn("Failed to transition to RETURNING_HOME state")
        
        return False