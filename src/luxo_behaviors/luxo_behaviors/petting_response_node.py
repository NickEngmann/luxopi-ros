#!/usr/bin/env python3
"""
PettingResponseNode - Handles petting detection and response behaviors.

This node manages:
- Petting event detection and processing
- Petting animation triggering and coordination
- Petting state tracking and timeouts
- Integration with the Luxo state machine for PETTING state

Subscribes to:
- /collision/petting_events (String): Petting detection messages

Publishes:
- /petting/status (String): Current petting status for coordination
- /petting/animation_request (String): Animation requests for petting responses

Uses Actions:
- play_animation (PlayAnimation): Triggers petting response animations
"""

import random
import threading
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String
from luxo_interfaces.action import PlayAnimation
from luxo_behaviors.state_machine import LuxoState, LuxoStateMachine

from luxo_behaviors.shared_utilities import (
    LuxoConstants, 
    ROSUtils, 
    StateUtils
)


class PettingStatus:
    """Enumeration of petting status states."""
    INACTIVE = "inactive"
    ACTIVE = "active" 
    ANIMATION_PLAYING = "animation_playing"
    TIMEOUT = "timeout"
    ERROR = "error"


class PettingResponseNode(Node):
    """
    ROS2 node for handling petting detection and response behaviors.
    
    Manages petting event processing, animation triggering, and state coordination
    with other behavior nodes through published status messages.
    """
    
    def __init__(self):
        super().__init__('petting_response_node')
        
        # Initialize state machine integration
        self.state_machine = LuxoStateMachine()
        self.state_machine.set_node(self)
        
        # Track startup time to prevent false positives
        self._startup_time = self.get_clock().now()
        self._startup_grace_period = 10.0  # seconds
        
        # Declare parameters
        self._declare_parameters()
        
        # Initialize petting state tracking
        self._init_petting_state()
        
        # Create callback group for thread safety
        self._callback_group = ReentrantCallbackGroup()
        
        # Create subscribers
        self._create_subscribers()
        
        # Create publishers  
        self._create_publishers()
        
        # Create action clients
        self._create_action_clients()
        
        # Create timers
        self._create_timers()
        
        # Thread safety
        self._state_lock = threading.Lock()
        
        self.get_logger().info("PettingResponseNode initialized")
    
    def _declare_parameters(self):
        """Declare ROS parameters with defaults."""
        self.declare_parameter('petting_message_timeout', LuxoConstants.PETTING_MESSAGE_TIMEOUT)
        self.declare_parameter('petting_animation_cooldown', LuxoConstants.PETTING_ANIMATION_COOLDOWN)
        self.declare_parameter('startup_grace_period', 10.0)
        self.declare_parameter('petting_animations', LuxoConstants.PETTING_ANIMATIONS)
        self.declare_parameter('enable_petting_response', True)
        self.declare_parameter('max_petting_intensity', 100)
        self.declare_parameter('min_petting_pressure', 2)
        
        # Get parameter values
        self.petting_message_timeout = self.get_parameter('petting_message_timeout').value
        self.petting_animation_cooldown = self.get_parameter('petting_animation_cooldown').value
        self.startup_grace_period = self.get_parameter('startup_grace_period').value
        self.petting_animations = self.get_parameter('petting_animations').value
        self.enable_petting_response = self.get_parameter('enable_petting_response').value
        self.max_petting_intensity = self.get_parameter('max_petting_intensity').value
        self.min_petting_pressure = self.get_parameter('min_petting_pressure').value
    
    def _init_petting_state(self):
        """Initialize petting state variables."""
        self.petting_active = False
        self.petting_intensity = 0
        self.petting_start_time = None
        self.last_petting_message_time = self.get_clock().now()
        self.last_petting_animation_time = self.get_clock().now()
        
        # Animation tracking
        self.petting_animation_active = False
        self.petting_animation_goal_handle = None
        self.current_animation_name = None
        
        # Status tracking
        self.current_status = PettingStatus.INACTIVE
        self.last_status_publish_time = self.get_clock().now()
        self.status_publish_interval = 0.5  # seconds
    
    def _create_subscribers(self):
        """Create ROS subscribers."""
        self.petting_events_sub = self.create_subscription(
            String,
            '/collision/petting_events',
            self.petting_events_callback,
            10,
            callback_group=self._callback_group
        )
        
        self.get_logger().info("Created subscription to /collision/petting_events")
    
    def _create_publishers(self):
        """Create ROS publishers."""
        self.status_pub = self.create_publisher(
            String,
            '/petting/status',
            10
        )
        
        self.animation_request_pub = self.create_publisher(
            String, 
            '/petting/animation_request',
            10
        )
        
        self.get_logger().info("Created publishers for petting status and animation requests")
    
    def _create_action_clients(self):
        """Create action clients."""
        self.animation_client = ActionClient(
            self,
            PlayAnimation,
            'play_animation',
            callback_group=self._callback_group
        )
        
        self.get_logger().info("Created action client for play_animation")
    
    def _create_timers(self):
        """Create periodic timers."""
        # Status monitoring timer
        self.status_timer = self.create_timer(
            0.1,  # 10 Hz monitoring
            self.status_monitor_callback,
            callback_group=self._callback_group
        )
        
        # Status publishing timer
        self.status_publish_timer = self.create_timer(
            self.status_publish_interval,
            self.publish_status_callback,
            callback_group=self._callback_group
        )
    
    def petting_events_callback(self, msg: String):
        """
        Handle incoming petting event messages.
        
        Expected message format: "petting_started:pressure" or "petting_stopped:0"
        """
        try:
            # Parse the message
            parts = msg.data.split(':')
            if len(parts) != 2:
                self.get_logger().warn(f"Invalid petting message format: {msg.data}")
                return
                
            action = parts[0]
            pressure = int(parts[1]) if parts[1].isdigit() else 0
            
            # Check if petting response is enabled
            if not self.enable_petting_response:
                self.get_logger().debug(f"Petting response disabled, ignoring: {msg.data}")
                return
            
            # Prevent false positives during startup
            current_time = self.get_clock().now()
            time_since_startup = ROSUtils.time_since(self._startup_time, current_time)
            
            if time_since_startup < self.startup_grace_period:
                self.get_logger().debug(
                    f"Ignoring petting during startup period ({time_since_startup:.1f}s): {msg.data}"
                )
                return
            
            # Update last message time
            self.last_petting_message_time = current_time
            
            # Process the petting event
            with self._state_lock:
                self._process_petting_event(action, pressure, current_time)
                
        except Exception as e:
            self.get_logger().error(f"Error in petting events callback: {e}")
            self._update_status(PettingStatus.ERROR)
    
    def _process_petting_event(self, action: str, pressure: int, current_time):
        """Process a petting event with thread safety."""
        was_petting = self.petting_active
        new_petting_state = (action == "petting_started" and pressure > self.min_petting_pressure)
        
        if new_petting_state:
            # Petting started or continuing
            self.petting_active = True
            self.petting_intensity = min(pressure, self.max_petting_intensity)
            
            if not was_petting:
                # Newly started petting
                self.get_logger().info(
                    f"Petting started (pressure: {pressure}) - transitioning to PETTING state"
                )
                self.petting_start_time = current_time
                
                # Transition to PETTING state if appropriate
                if self._can_transition_to_petting():
                    self.state_machine.transition_to(LuxoState.PETTING)
                    self._update_status(PettingStatus.ACTIVE)
                    
                    # Trigger immediate petting response
                    self._trigger_petting_animation()
                else:
                    self.get_logger().warn(
                        f"Cannot transition to petting from current state: {self.state_machine.current_state.name}"
                    )
                    self.petting_active = False  # Reset since we can't transition
                    self._update_status(PettingStatus.INACTIVE)
                    
            else:
                # Continuing petting, update intensity
                self.get_logger().debug(f"Petting continues with pressure: {pressure}")
                self.petting_intensity = pressure
                
                # Check if we should trigger another animation (with cooldown)
                if self._should_trigger_additional_animation(current_time):
                    self.get_logger().info("Triggering additional petting animation")
                    self._trigger_petting_animation()
                    
        elif action == "petting_stopped":
            # Explicit stop message
            if was_petting:
                self.get_logger().info("Petting explicitly stopped - waiting for animation to complete")
                self.petting_active = False
                self.petting_start_time = None
                self.petting_intensity = 0
                self._update_status(PettingStatus.INACTIVE)
                
                # Check if we can transition out immediately
                self._check_petting_state_transition()
    
    def _can_transition_to_petting(self) -> bool:
        """Check if we can transition to PETTING state."""
        valid_states = [LuxoState.IDLE, LuxoState.ANIMATING, LuxoState.EMOTION_REACTING]
        return self.state_machine.is_in_state(*valid_states)
    
    def _should_trigger_additional_animation(self, current_time) -> bool:
        """Check if we should trigger an additional petting animation."""
        if not self.state_machine.is_in_state(LuxoState.PETTING):
            return False
            
        if self.petting_animation_active:
            return False
            
        time_since_last_animation = ROSUtils.time_since(
            self.last_petting_animation_time, 
            current_time
        )
        
        return time_since_last_animation > self.petting_animation_cooldown
    
    def _trigger_petting_animation(self):
        """Trigger a petting response animation."""
        try:
            # Check if action server is available
            if not self.animation_client.wait_for_server(timeout_sec=0.5):
                self.get_logger().warn("Animation action server not available for petting animation")
                return
            
            # Don't trigger if already active
            if self.petting_animation_active:
                self.get_logger().debug("Petting animation already active - skipping")
                return
            
            # Select random petting animation
            if not self.petting_animations:
                self.get_logger().warn("No petting animations configured")
                return
                
            selected_animation = random.choice(self.petting_animations)
            
            # Create animation goal
            goal = PlayAnimation.Goal()
            goal.animation_name = selected_animation
            goal.speed_multiplier = random.uniform(0.9, 1.1)  # Gentle speed variation
            goal.allow_interruption = False  # Don't allow interruption of petting animations
            goal.use_hardware_feedback = False
            
            self.get_logger().info(f"Triggering petting animation: {selected_animation}")
            
            # Mark animation as active
            self.petting_animation_active = True
            self.current_animation_name = selected_animation
            self._update_status(PettingStatus.ANIMATION_PLAYING)
            
            # Send goal asynchronously
            future = self.animation_client.send_goal_async(goal)
            future.add_done_callback(self._petting_animation_goal_response_callback)
            
            # Update timing
            self.last_petting_animation_time = self.get_clock().now()
            
            # Publish animation request for coordination
            self._publish_animation_request(selected_animation)
            
        except Exception as e:
            self.get_logger().error(f"Error triggering petting animation: {e}")
            self.petting_animation_active = False
            self._update_status(PettingStatus.ERROR)
    
    def _petting_animation_goal_response_callback(self, future):
        """Handle petting animation goal response."""
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.get_logger().warn("Petting animation goal rejected")
                with self._state_lock:
                    self.petting_animation_active = False
                    self._update_status(PettingStatus.ACTIVE if self.petting_active else PettingStatus.INACTIVE)
                return
            
            self.get_logger().debug("Petting animation goal accepted")
            self.petting_animation_goal_handle = goal_handle
            
            # Get result future and add completion callback
            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(self._petting_animation_result_callback)
            
        except Exception as e:
            self.get_logger().error(f"Error in petting animation goal response: {e}")
            with self._state_lock:
                self.petting_animation_active = False
                self._update_status(PettingStatus.ERROR)
    
    def _petting_animation_result_callback(self, future):
        """Handle petting animation completion."""
        try:
            result = future.result()
            self.get_logger().info(f"Petting animation completed with status: {result.status}")
            
            with self._state_lock:
                # Mark animation as completed
                self.petting_animation_active = False
                self.petting_animation_goal_handle = None
                self.current_animation_name = None
                
                # Update status based on current petting state
                if self.petting_active:
                    self._update_status(PettingStatus.ACTIVE)
                else:
                    self._update_status(PettingStatus.INACTIVE)
                
                # Check if we should transition out of PETTING state
                self._check_petting_state_transition()
                
        except Exception as e:
            self.get_logger().error(f"Error in petting animation result: {e}")
            with self._state_lock:
                self.petting_animation_active = False
                self.petting_animation_goal_handle = None
                self._update_status(PettingStatus.ERROR)
    
    def _check_petting_state_transition(self):
        """Check if we should transition out of PETTING state."""
        try:
            # Only transition out if BOTH conditions are met:
            # 1. Petting is no longer active
            # 2. No petting animation is currently running
            if (self.state_machine.is_in_state(LuxoState.PETTING) and 
                not self.petting_active and 
                not self.petting_animation_active):
                
                self.get_logger().info("Petting stopped and animation complete - transitioning to IDLE")
                self.state_machine.transition_to(LuxoState.IDLE)
                self._update_status(PettingStatus.INACTIVE)
                
        except Exception as e:
            self.get_logger().error(f"Error checking petting state transition: {e}")
    
    def status_monitor_callback(self):
        """Monitor petting status and handle timeouts."""
        try:
            current_time = self.get_clock().now()
            
            with self._state_lock:
                # Check for petting message timeout
                if self.petting_active:
                    time_since_message = ROSUtils.time_since(
                        self.last_petting_message_time, 
                        current_time
                    )
                    
                    if time_since_message > self.petting_message_timeout:
                        # Petting timed out
                        self.get_logger().info(
                            f"Petting timed out after {time_since_message:.1f}s - stopping petting"
                        )
                        self.petting_active = False
                        self.petting_start_time = None
                        self.petting_intensity = 0
                        self._update_status(PettingStatus.TIMEOUT)
                        
                        # Check if we can transition out
                        self._check_petting_state_transition()
                
                # Handle ongoing petting state updates
                if self.state_machine.is_in_state(LuxoState.PETTING):
                    if self.petting_active and self._should_trigger_additional_animation(current_time):
                        # Trigger periodic animations during extended petting
                        self._trigger_petting_animation()
                    elif not self.petting_active:
                        # Check if we can transition out
                        self._check_petting_state_transition()
                        
        except Exception as e:
            self.get_logger().error(f"Error in status monitor: {e}")
    
    def publish_status_callback(self):
        """Publish current petting status for coordination."""
        try:
            current_time = self.get_clock().now()
            
            # Only publish if status has changed or it's been a while
            time_since_publish = ROSUtils.time_since(self.last_status_publish_time, current_time)
            
            if time_since_publish >= self.status_publish_interval:
                self._publish_status()
                self.last_status_publish_time = current_time
                
        except Exception as e:
            self.get_logger().error(f"Error publishing status: {e}")
    
    def _update_status(self, new_status: str):
        """Update internal status and trigger immediate publish."""
        if self.current_status != new_status:
            self.current_status = new_status
            self.get_logger().debug(f"Petting status changed to: {new_status}")
            self._publish_status()
    
    def _publish_status(self):
        """Publish current petting status."""
        try:
            # Create detailed status message
            status_data = {
                'status': self.current_status,
                'active': self.petting_active,
                'intensity': self.petting_intensity,
                'animation_active': self.petting_animation_active,
                'current_animation': self.current_animation_name or 'none',
                'state': self.state_machine.current_state.name if self.state_machine.current_state else 'unknown'
            }
            
            # Format as string for simple consumption
            status_str = f"status:{self.current_status},active:{self.petting_active},intensity:{self.petting_intensity}"
            
            msg = ROSUtils.create_string_msg(status_str)
            self.status_pub.publish(msg)
            
            self.get_logger().debug(f"Published petting status: {status_str}")
            
        except Exception as e:
            self.get_logger().error(f"Error publishing petting status: {e}")
    
    def _publish_animation_request(self, animation_name: str):
        """Publish animation request for coordination."""
        try:
            request_str = f"petting_animation:{animation_name}"
            msg = ROSUtils.create_string_msg(request_str)
            self.animation_request_pub.publish(msg)
            
            self.get_logger().debug(f"Published animation request: {request_str}")
            
        except Exception as e:
            self.get_logger().error(f"Error publishing animation request: {e}")
    
    def get_petting_status_dict(self) -> dict:
        """Get current petting status as dictionary for external queries."""
        with self._state_lock:
            return {
                'status': self.current_status,
                'active': self.petting_active,
                'intensity': self.petting_intensity,
                'animation_active': self.petting_animation_active,
                'current_animation': self.current_animation_name,
                'start_time': self.petting_start_time.nanoseconds if self.petting_start_time else None,
                'last_message_time': self.last_petting_message_time.nanoseconds,
                'state': self.state_machine.current_state.name if self.state_machine.current_state else None
            }
    
    def emergency_stop_petting(self):
        """Emergency stop all petting activities."""
        try:
            self.get_logger().warn("Emergency stop petting requested")
            
            with self._state_lock:
                # Cancel any active animation
                if self.petting_animation_goal_handle:
                    cancel_future = self.petting_animation_goal_handle.cancel_goal_async()
                    cancel_future.add_done_callback(
                        lambda future: self.get_logger().info("Petting animation cancelled")
                    )
                
                # Reset all petting state
                self.petting_active = False
                self.petting_intensity = 0
                self.petting_start_time = None
                self.petting_animation_active = False
                self.petting_animation_goal_handle = None
                self.current_animation_name = None
                
                # Update status
                self._update_status(PettingStatus.INACTIVE)
                
                # Transition out of petting state
                if self.state_machine.is_in_state(LuxoState.PETTING):
                    self.state_machine.transition_to(LuxoState.IDLE)
                    
        except Exception as e:
            self.get_logger().error(f"Error in emergency stop: {e}")


def main(args=None):
    """Main entry point for the petting response node."""
    rclpy.init(args=args)
    
    try:
        node = PettingResponseNode()
        
        # Use MultiThreadedExecutor for handling callbacks
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        
        node.get_logger().info("PettingResponseNode started - waiting for petting events...")
        
        try:
            executor.spin()
        except KeyboardInterrupt:
            node.get_logger().info("Shutting down PettingResponseNode...")
        finally:
            # Emergency stop any ongoing activities
            node.emergency_stop_petting()
            executor.shutdown()
            
    except Exception as e:
        print(f"Failed to start PettingResponseNode: {e}")
        
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()