#!/usr/bin/env python3
# petting_behavior.py
"""
Petting behavior module for Luxo robot.
Handles petting detection and reactive animations.
"""

import random
import time
from typing import Optional
from rclpy.action import ActionClient
from luxo_interfaces.action import PlayAnimation
from luxo_behaviors.state_machine import LuxoState
from std_msgs.msg import String


class PettingBehavior:
    """Mixin class for petting behavior functionality."""
    
    def setup_petting_behavior(self):
        """Initialize petting behavior attributes and subscriptions."""
        # Petting behavior tracking
        self.petting_active = False
        self.petting_start_time = None
        self.petting_intensity = 0
        self.last_petting_animation_time = self.node.get_clock().now()
        self.petting_animation_cooldown = 8.0  # seconds between petting animations
        self.petting_animation_active = False  # Track if petting animation is running
        self.petting_animation_goal_handle = None  # Track current petting animation goal
        
        # Add petting state tracking
        self.last_petting_message_time = self.node.get_clock().now()
        self.petting_message_timeout = 5.0  # seconds - if no petting messages for this long, consider stopped
        self.petting_animations = self.idle_config.petting_animations
        
        # Subscribe to petting detection
        self.petting_sub = self.node.create_subscription(
            String,
            '/collision/petting_events',
            self.petting_callback,
            10
        )
        
        self.node.get_logger().info("Petting behavior initialized")
    
    def petting_callback(self, msg):
        """Handle petting detection messages."""
        try:
            # Parse petting message
            # Format: "action:value" e.g., "petting_detected:75", "petting_stopped:0"
            parts = msg.data.split(':')
            if len(parts) < 2:
                self.node.get_logger().warn(f"Invalid petting message format: {msg.data}")
                return
            
            action = parts[0]
            value = parts[1]
            
            # Update last message time
            current_time = self.node.get_clock().now()
            self.last_petting_message_time = current_time
            
            if action == "petting_started":
                # Parse pressure value
                try:
                    pressure = int(value)
                except ValueError:
                    self.node.get_logger().error(f"Invalid pressure value: {value}")
                    return
                
                self.node.get_logger().info(f"Petting started detected with pressure: {pressure}")
                
                # ALWAYS trigger petting response on petting_started, regardless of current state
                self.petting_active = True
                self.petting_start_time = current_time
                self.petting_intensity = pressure
                
                # Check if we should enter PETTING state
                current_state = self._get_current_state()
                if current_state in [LuxoState.IDLE, LuxoState.ANIMATING, LuxoState.VOICE_FOLLOWING]:
                    self.node.get_logger().info("Requesting transition to PETTING state")
                    
                    # Request state transition to PETTING
                    if self._transition_to_state(LuxoState.PETTING):
                        # Check animation cooldown before triggering
                        time_since_last_animation = (current_time - self.last_petting_animation_time).nanoseconds / 1e9
                        
                        if time_since_last_animation > self.petting_animation_cooldown or not self.petting_animation_active:
                            self.node.get_logger().info("Triggering petting animation immediately")
                            self._trigger_petting_animation()
                        else:
                            self.node.get_logger().info(f"Petting animation on cooldown ({time_since_last_animation:.1f}s < {self.petting_animation_cooldown}s)")
                    else:
                        self.node.get_logger().warn("Failed to transition to PETTING state")
                else:
                    self.node.get_logger().info(f"Cannot enter PETTING state from {current_state.name} - but still tracking petting")
                
                # Clear any debounce state
                self.petting_debounce_active = False
                self.petting_debounce_start_time = None
                        
            elif action == "petting_stopped":
                # Only log the stop but don't immediately clear petting state
                # Let the timeout mechanism handle the actual stopping
                self.node.get_logger().debug("Petting stopped message received - will timeout naturally")
                self.petting_active = False  # Mark as inactive but don't clear other state
                
        except Exception as e:
            self.node.get_logger().error(f"Error in petting callback: {e}")
            import traceback
            self.node.get_logger().error(f"Stack trace: {traceback.format_exc()}")

    def _trigger_petting_animation(self):
        """Trigger a petting response animation."""
        try:
            # Don't trigger if action client not ready
            if not self._idle_animation_client.wait_for_server(timeout_sec=0.5):
                self.node.get_logger().info("Animation action server not available for petting animation")
                return
            
            # Don't trigger if we already have a petting animation running
            if self.petting_animation_active:
                self.node.get_logger().info("Petting animation already active - skipping")
                return
            
            # Select a random petting animation
            selected_animation = random.choice(self.petting_animations)
            
            # Create goal for petting animation
            goal = PlayAnimation.Goal()
            goal.animation_name = selected_animation
            goal.speed_multiplier = random.uniform(0.9, 1.1)  # Slower, more gentle movements
            goal.allow_interruption = False  # Don't allow interruption of petting animations
            goal.use_hardware_feedback = False
            
            self.node.get_logger().info(f"Triggering petting animation: {selected_animation}")
            
            # Mark petting animation as active
            self.petting_animation_active = True
            
            # Send goal asynchronously
            future = self._idle_animation_client.send_goal_async(goal)
            future.add_done_callback(self._petting_animation_goal_response_callback)
            
            # Update last animation time
            self.last_petting_animation_time = self.node.get_clock().now()

        except Exception as e:
            self.node.get_logger().error(f"Error triggering petting animation: {e}")
            self.petting_animation_active = False
    
    def _petting_animation_goal_response_callback(self, future):
        """Handle the petting animation goal response."""
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.node.get_logger().info("Petting animation goal rejected")
                self.petting_animation_active = False
                return
            
            self.node.get_logger().info("Petting animation goal accepted")
            self.petting_animation_goal_handle = goal_handle
            
            # Get the result future and add callback for completion
            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(self._petting_animation_result_callback)
            
        except Exception as e:
            self.node.get_logger().error(f"Error in petting animation goal response: {e}")
            self.petting_animation_active = False
    
    def _petting_animation_result_callback(self, future):
        """Handle petting animation completion."""
        try:
            result = future.result()
            self.node.get_logger().info(f"Petting animation completed with status: {result.status}")
            
            # Mark petting animation as completed
            self.petting_animation_active = False
            self.petting_animation_goal_handle = None
            
            # Check if we should transition out of PETTING state
            self._check_petting_state_transition()
            
        except Exception as e:
            self.node.get_logger().error(f"Error in petting animation result: {e}")
            self.petting_animation_active = False
            self.petting_animation_goal_handle = None
    
    def _check_petting_state_transition(self):
        """Check if we should transition out of PETTING state."""
        try:
            # Only transition out if BOTH conditions are met:
            # 1. Petting is no longer active
            # 2. No petting animation is currently running
            if (self._is_in_state(LuxoState.PETTING) and 
                not self.petting_active and 
                not self.petting_animation_active):
                
                self.node.get_logger().info("Petting stopped and animation complete - transitioning to IDLE")
                self._transition_to_state(LuxoState.IDLE)
                
        except Exception as e:
            self.node.get_logger().error(f"Error checking petting state transition: {e}")
    
    def check_petting_timeout(self, current_time):
        """Check for petting timeout and handle state transitions."""
        if self._is_in_state(LuxoState.PETTING):
            # Check for petting timeout (no petting_started messages received recently)
            time_since_petting_message = (current_time - self.last_petting_message_time).nanoseconds / 1e9
            
            # Use a reasonable timeout - long enough for animation to complete
            petting_timeout = 5.0  # 5 seconds - enough time for animation
            
            if time_since_petting_message > petting_timeout:
                # Petting timed out
                self.node.get_logger().info(f"Petting session timed out after {time_since_petting_message:.1f}s")
                self.petting_active = False
                self.petting_start_time = None
                self.petting_intensity = 0
                
                # Check if we can transition out
                self._check_petting_state_transition()
            
            # Always stay in petting state while animation is running, regardless of petting_active status
            if self.petting_animation_active:
                self.node.get_logger().debug("Staying in petting state - animation still running")
                return True
                
            # If we're still in petting state after check, don't do other safety operations
            if self._is_in_state(LuxoState.PETTING):
                return True
        
        return False