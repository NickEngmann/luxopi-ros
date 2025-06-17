#!/usr/bin/env python3
"""
IdleBehaviorNode - Manages idle behaviors and animations for the Luxo robot.

This node handles:
- Idle timeout tracking and animation triggering
- Idle head variations for natural movement
- Home position sequence management
- Rest position requests
- Activity monitoring and state coordination

Author: Generated from collision_avoidance.py refactor
"""

import random
import threading
from typing import Optional, List, Tuple

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.timer import Timer
from rclpy.time import Time

# ROS message types
from std_msgs.msg import String, Bool, Float32MultiArray
from sensor_msgs.msg import JointState
from luxo_interfaces.action import PlayAnimation
from luxo_interfaces.msg import IdleRequest, PositionRequest, ActivityUpdate

# Import shared utilities
from shared_utilities import (
    LuxoConstants, 
    PositionUtils, 
    ROSUtils, 
    MathUtils,
    AngleUtils
)


class IdleBehaviorNode(Node):
    """
    ROS2 node responsible for managing idle behaviors and animations.
    """
    
    def __init__(self):
        super().__init__('idle_behavior_node')
        
        # Declare parameters
        self._declare_parameters()
        
        # Load parameters
        self._load_parameters()
        
        # Initialize state variables
        self._initialize_state()
        
        # Create publishers
        self._create_publishers()
        
        # Create subscribers
        self._create_subscribers()
        
        # Create action clients
        self._create_action_clients()
        
        # Create timers
        self._create_timers()
        
        # Thread lock for state protection
        self._state_lock = threading.Lock()
        
        self.get_logger().info("IdleBehaviorNode initialized successfully")
    
    def _declare_parameters(self):
        """Declare ROS parameters with default values."""
        # Idle animation parameters
        self.declare_parameter('idle_animations_enabled', True)
        self.declare_parameter('min_idle_time_before_animation', 5.0)
        self.declare_parameter('idle_animation_interval_min', 10.0)
        self.declare_parameter('idle_animation_interval_max', 60.0)
        self.declare_parameter('extended_idle_timeout', 120.0)
        
        # Idle head variation parameters
        self.declare_parameter('idle_head_variation_enabled', True)
        self.declare_parameter('idle_head_variation_interval_min', 3.5)
        self.declare_parameter('idle_head_variation_interval_max', 10.0)
        self.declare_parameter('idle_head_base_rotation_range', 0.3)
        self.declare_parameter('idle_head_look_up_range', 0.4)
        self.declare_parameter('idle_head_look_down_range', 0.1)
        self.declare_parameter('idle_head_variation_speed', 4.0)
        
        # Home position parameters
        self.declare_parameter('enable_home_position', True)
        self.declare_parameter('home_position_timeout', 30.0)
        
        # Rest position parameters
        self.declare_parameter('enable_rest_position', True)
        self.declare_parameter('rest_variation_range', 0.05)
        
        # Activity tracking parameters
        self.declare_parameter('activity_timeout_min', 45.0)
        self.declare_parameter('activity_timeout_max', 90.0)
    
    def _load_parameters(self):
        """Load parameters from ROS parameter server."""
        # Idle animation parameters
        self.idle_animations_enabled = self.get_parameter('idle_animations_enabled').value
        self.min_idle_time_before_animation = self.get_parameter('min_idle_time_before_animation').value
        self.idle_animation_interval_min = self.get_parameter('idle_animation_interval_min').value
        self.idle_animation_interval_max = self.get_parameter('idle_animation_interval_max').value
        self.extended_idle_timeout = self.get_parameter('extended_idle_timeout').value
        
        # Idle head variation parameters
        self.idle_head_variation_enabled = self.get_parameter('idle_head_variation_enabled').value
        self.idle_head_variation_interval_min = self.get_parameter('idle_head_variation_interval_min').value
        self.idle_head_variation_interval_max = self.get_parameter('idle_head_variation_interval_max').value
        self.idle_head_base_rotation_range = self.get_parameter('idle_head_base_rotation_range').value
        self.idle_head_look_up_range = self.get_parameter('idle_head_look_up_range').value
        self.idle_head_look_down_range = self.get_parameter('idle_head_look_down_range').value
        self.idle_head_variation_speed = self.get_parameter('idle_head_variation_speed').value
        
        # Home position parameters
        self.enable_home_position = self.get_parameter('enable_home_position').value
        self.home_position_timeout = self.get_parameter('home_position_timeout').value
        
        # Rest position parameters
        self.enable_rest_position = self.get_parameter('enable_rest_position').value
        self.rest_variation_range = self.get_parameter('rest_variation_range').value
        
        # Activity tracking parameters
        self.activity_timeout_min = self.get_parameter('activity_timeout_min').value
        self.activity_timeout_max = self.get_parameter('activity_timeout_max').value
    
    def _initialize_state(self):
        """Initialize internal state variables."""
        # Current robot state
        self.current_joints: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.robot_state: str = "IDLE"
        self.is_active: bool = False
        
        # Activity tracking
        self.last_activity_time: Time = self.get_clock().now()
        self.current_idle_timeout: float = MathUtils.random_in_range(
            self.activity_timeout_min, self.activity_timeout_max
        )
        
        # Idle animation state
        self.last_idle_animation_time: Time = self.get_clock().now()
        self.last_idle_animation: Optional[str] = None
        self.current_idle_animation_interval: float = MathUtils.random_in_range(
            self.idle_animation_interval_min, self.idle_animation_interval_max
        )
        self.idle_animation_active: bool = False
        self.idle_animation_goal_handle = None
        
        # Idle head variation state
        self.last_idle_head_variation_time: Time = self.get_clock().now()
        self.current_idle_head_target: Optional[List[float]] = None
        self.idle_head_variation_active: bool = False
        self.current_head_variation_interval: float = MathUtils.random_in_range(
            self.idle_head_variation_interval_min, self.idle_head_variation_interval_max
        )
        
        # Home position state
        self.home_position_stage: int = 1
        self.home_position_requested: bool = False
        self.home_position_start_time: Optional[Time] = None
        self.last_rest_position: Optional[List[float]] = None
        
        # Voice following coordination
        self.voice_following_active: bool = False
        self.voice_influence: float = 0.0
        
        # Collision coordination
        self.collision_active: bool = False
        
        self.get_logger().info(f"Initial idle timeout set to {self.current_idle_timeout:.1f} seconds")
    
    def _create_publishers(self):
        """Create ROS publishers."""
        # Idle animation requests
        self.idle_animation_pub = self.create_publisher(
            IdleRequest,
            '/idle/animation_request',
            10
        )
        
        # Position requests (home/rest positions)
        self.position_request_pub = self.create_publisher(
            PositionRequest,
            '/idle/position_request',
            10
        )
        
        # Idle head variation requests
        self.head_variation_pub = self.create_publisher(
            PositionRequest,
            '/idle/head_variation_request',
            10
        )
        
        # Activity status updates
        self.activity_status_pub = self.create_publisher(
            ActivityUpdate,
            '/idle/activity_status',
            10
        )
        
        # Debug/status information
        self.status_pub = self.create_publisher(
            String,
            '/idle/status',
            10
        )
    
    def _create_subscribers(self):
        """Create ROS subscribers."""
        # Robot joint states
        self.joint_states_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_states_callback,
            10
        )
        
        # Activity updates from other nodes
        self.activity_update_sub = self.create_subscription(
            ActivityUpdate,
            '/robot/activity_update',
            self.activity_update_callback,
            10
        )
        
        # Robot state updates
        self.robot_state_sub = self.create_subscription(
            String,
            '/robot/state',
            self.robot_state_callback,
            10
        )
        
        # Voice following status
        self.voice_status_sub = self.create_subscription(
            Float32MultiArray,
            '/voice/status',
            self.voice_status_callback,
            10
        )
        
        # Collision status
        self.collision_status_sub = self.create_subscription(
            Bool,
            '/collision/active',
            self.collision_status_callback,
            10
        )
        
        # Animation completion notifications
        self.animation_complete_sub = self.create_subscription(
            String,
            '/animation/complete',
            self.animation_complete_callback,
            10
        )
    
    def _create_action_clients(self):
        """Create action clients."""
        # Animation action client
        self.animation_client = ActionClient(
            self,
            PlayAnimation,
            'play_animation'
        )
    
    def _create_timers(self):
        """Create periodic timers."""
        # Main idle behavior timer (runs every 2 seconds)
        self.idle_timer = self.create_timer(2.0, self.idle_timer_callback)
        
        # Head variation timer (runs every 1 second)
        self.head_variation_timer = self.create_timer(1.0, self.head_variation_timer_callback)
    
    def joint_states_callback(self, msg: JointState):
        """Handle joint state updates."""
        if len(msg.position) >= 5:
            with self._state_lock:
                self.current_joints = list(msg.position[:5])
    
    def activity_update_callback(self, msg: ActivityUpdate):
        """Handle activity updates from other behavior nodes."""
        with self._state_lock:
            if msg.activity_type in ['collision_avoidance', 'user_command', 'animation_start']:
                self.last_activity_time = self.get_clock().now()
                self.get_logger().debug(f"Activity update: {msg.activity_type} - reset idle timer")
                
                # Reset idle timeouts when activity detected
                self.current_idle_timeout = MathUtils.random_in_range(
                    self.activity_timeout_min, self.activity_timeout_max
                )
                
                # Clear any active head variations if significant activity
                if msg.activity_type in ['collision_avoidance', 'user_command']:
                    self._clear_head_variation()
    
    def robot_state_callback(self, msg: String):
        """Handle robot state changes."""
        with self._state_lock:
            old_state = self.robot_state
            self.robot_state = msg.data
            
            if old_state != self.robot_state:
                self.get_logger().debug(f"Robot state changed: {old_state} -> {self.robot_state}")
                
                # Update activity time on state changes to non-idle states
                if self.robot_state != "IDLE":
                    self.last_activity_time = self.get_clock().now()
    
    def voice_status_callback(self, msg: Float32MultiArray):
        """Handle voice following status updates."""
        if len(msg.data) >= 2:
            with self._state_lock:
                self.voice_following_active = bool(msg.data[0])
                self.voice_influence = float(msg.data[1])
    
    def collision_status_callback(self, msg: Bool):
        """Handle collision status updates."""
        with self._state_lock:
            self.collision_active = msg.data
    
    def animation_complete_callback(self, msg: String):
        """Handle animation completion notifications."""
        with self._state_lock:
            if msg.data in LuxoConstants.IDLE_ANIMATIONS:
                self.idle_animation_active = False
                self.idle_animation_goal_handle = None
                self.get_logger().info(f"Idle animation '{msg.data}' completed")
                
                # Schedule next idle animation
                self.current_idle_animation_interval = MathUtils.random_in_range(
                    self.idle_animation_interval_min, self.idle_animation_interval_max
                )
                self.last_idle_animation_time = self.get_clock().now()
    
    def idle_timer_callback(self):
        """Main idle behavior timer callback."""
        try:
            with self._state_lock:
                current_time = self.get_clock().now()
                
                # Only process if in IDLE state
                if self.robot_state != "IDLE":
                    return
                
                # Don't interfere with active collisions
                if self.collision_active:
                    return
                
                time_since_activity = ROSUtils.time_since(self.last_activity_time, current_time)
                
                # Check for idle animation trigger
                if self._should_trigger_idle_animation(current_time, time_since_activity):
                    self._trigger_idle_animation()
                
                # Check for extended idle timeout (home position return)
                elif (self.enable_home_position and 
                      time_since_activity > self.extended_idle_timeout and
                      not self._is_at_home_position()):
                    
                    self._request_home_position("Extended idle timeout")
                
                # Publish activity status
                self._publish_activity_status(time_since_activity)
                
        except Exception as e:
            self.get_logger().error(f"Error in idle timer callback: {e}")
    
    def head_variation_timer_callback(self):
        """Head variation timer callback."""
        try:
            with self._state_lock:
                current_time = self.get_clock().now()
                
                # Check if we should apply idle head variation
                if self._should_apply_idle_head_variation(current_time):
                    self._trigger_idle_head_variation()
                    
        except Exception as e:
            self.get_logger().error(f"Error in head variation timer callback: {e}")
    
    def _should_trigger_idle_animation(self, current_time: Time, time_since_activity: float) -> bool:
        """Check if we should trigger an idle animation."""
        if not self.idle_animations_enabled:
            return False
            
        if self.idle_animation_active:
            return False
            
        # Must be idle for minimum time
        if time_since_activity < self.min_idle_time_before_animation:
            return False
            
        # Check interval since last animation
        time_since_last_animation = ROSUtils.time_since(self.last_idle_animation_time, current_time)
        if time_since_last_animation < self.current_idle_animation_interval:
            return False
            
        # Don't interfere with voice following
        if self.voice_following_active and self.voice_influence > 0.1:
            return False
            
        # Don't interfere with active head variation
        if self.idle_head_variation_active:
            return False
            
        return True
    
    def _trigger_idle_animation(self):
        """Trigger a random idle animation."""
        try:
            # Wait for action server
            if not self.animation_client.wait_for_server(timeout_sec=1.0):
                self.get_logger().warn("Animation action server not available")
                return
            
            # Select animation (avoid repeating the last one)
            available_animations = [
                a for a in LuxoConstants.IDLE_ANIMATIONS 
                if a != self.last_idle_animation
            ]
            if not available_animations:
                available_animations = LuxoConstants.IDLE_ANIMATIONS
                
            selected_animation = random.choice(available_animations)
            self.last_idle_animation = selected_animation
            
            # Create animation goal
            goal = PlayAnimation.Goal()
            goal.animation_name = selected_animation
            goal.speed_multiplier = MathUtils.random_in_range(0.8, 1.2)
            goal.allow_interruption = True
            goal.use_hardware_feedback = False
            
            self.get_logger().info(
                f"Triggering idle animation: {selected_animation} "
                f"(speed: {goal.speed_multiplier:.1f})"
            )
            
            # Send goal
            self.idle_animation_active = True
            future = self.animation_client.send_goal_async(goal)
            future.add_done_callback(self._idle_animation_response_callback)
            
            # Update timing
            self.last_idle_animation_time = self.get_clock().now()
            self.last_activity_time = self.get_clock().now()  # Reset activity timer
            
        except Exception as e:
            self.get_logger().error(f"Error triggering idle animation: {e}")
            self.idle_animation_active = False
    
    def _idle_animation_response_callback(self, future):
        """Handle idle animation goal response."""
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.get_logger().debug("Idle animation goal rejected")
                self.idle_animation_active = False
                return
            
            self.idle_animation_goal_handle = goal_handle
            self.get_logger().debug("Idle animation goal accepted")
            
            # Get result future
            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(self._idle_animation_result_callback)
            
        except Exception as e:
            self.get_logger().error(f"Error in idle animation response: {e}")
            self.idle_animation_active = False
    
    def _idle_animation_result_callback(self, future):
        """Handle idle animation completion."""
        try:
            result = future.result()
            self.get_logger().info(f"Idle animation completed with status: {result.status}")
            
            with self._state_lock:
                self.idle_animation_active = False
                self.idle_animation_goal_handle = None
                
        except Exception as e:
            self.get_logger().error(f"Error in idle animation result: {e}")
            self.idle_animation_active = False
    
    def _should_apply_idle_head_variation(self, current_time: Time) -> bool:
        """Check if we should apply idle head variation."""
        if not self.idle_head_variation_enabled:
            return False
            
        if self.robot_state != "IDLE":
            return False
            
        # Don't interfere with active voice following
        if self.voice_following_active and self.voice_influence > 0.1:
            return False
            
        # Don't interfere with collision avoidance
        if self.collision_active:
            return False
            
        # Don't interfere with home position requests
        if self.home_position_requested:
            return False
            
        # Don't interfere with active idle animations
        if self.idle_animation_active:
            return False
            
        # Check timing
        time_since_last_variation = ROSUtils.time_since(self.last_idle_head_variation_time, current_time)
        if time_since_last_variation < self.current_head_variation_interval:
            return False
            
        # Check minimum activity timeout
        time_since_activity = ROSUtils.time_since(self.last_activity_time, current_time)
        if time_since_activity < self.min_idle_time_before_animation:
            return False
            
        return True
    
    def _trigger_idle_head_variation(self):
        """Trigger subtle idle head variation."""
        try:
            variation_target = self._generate_idle_head_variation()
            
            if variation_target:
                # Create position request message
                msg = PositionRequest()
                msg.header.stamp = self.get_clock().now().to_msg()
                msg.request_type = "head_variation"
                msg.positions = variation_target
                msg.speed = self.idle_head_variation_speed
                msg.description = "Idle head variation"
                msg.priority = 1  # Low priority
                msg.allow_interruption = True
                
                # Publish the request
                self.head_variation_pub.publish(msg)
                
                # Update state
                self.current_idle_head_target = variation_target
                self.idle_head_variation_active = True
                self.last_idle_head_variation_time = self.get_clock().now()
                
                # Schedule next variation
                self.current_head_variation_interval = MathUtils.random_in_range(
                    self.idle_head_variation_interval_min,
                    self.idle_head_variation_interval_max
                )
                
                self.get_logger().info(f"Applied idle head variation: {[round(p, 2) for p in variation_target]}")
                
        except Exception as e:
            self.get_logger().error(f"Error in idle head variation: {e}")
    
    def _generate_idle_head_variation(self) -> Optional[List[float]]:
        """Generate a subtle head movement variation."""
        try:
            # Start with current position
            variation = self.current_joints.copy()
            
            # Add subtle base rotation relative to current position
            base_variation = MathUtils.random_in_range(
                -self.idle_head_base_rotation_range,
                self.idle_head_base_rotation_range
            )
            variation[0] += base_variation
            
            # Add vertical look variation (primarily through shoulder)
            look_type = random.random()
            if look_type < 0.85:  # Look up (85% chance - appears more alert)
                shoulder_variation = MathUtils.random_in_range(0.2, self.idle_head_look_up_range)
                variation[1] = LuxoConstants.IDLE_BASE_POSITION[1] - shoulder_variation
                variation_description = f"looking up (+{shoulder_variation:.2f})"
            elif look_type < 0.95:  # Look down (10% chance)
                shoulder_variation = MathUtils.random_in_range(0.0, self.idle_head_look_down_range)
                variation[1] = LuxoConstants.IDLE_BASE_POSITION[1] + shoulder_variation
                variation_description = f"looking down (-{shoulder_variation:.2f})"
            else:  # Stay neutral (5% chance)
                variation[1] = LuxoConstants.IDLE_BASE_POSITION[1]
                variation_description = "staying neutral"
            
            # Use base idle position for other joints with minimal variation
            variation[2] = LuxoConstants.IDLE_BASE_POSITION[2]  # Elbow
            variation[3] = LuxoConstants.IDLE_BASE_POSITION[3]  # Wrist
            variation[4] = LuxoConstants.IDLE_BASE_POSITION[4]  # Hand
            
            # Add tiny natural variations (30% chance for elbow, 20% for wrist)
            if random.random() < 0.3:
                variation[2] += MathUtils.random_in_range(-0.02, 0.02)
            if random.random() < 0.2:
                variation[3] += MathUtils.random_in_range(-0.01, 0.01)
            
            # Ensure exactly 5 elements
            variation = variation[:5]
            
            self.get_logger().info(
                f"Generated idle head variation: base {base_variation:+.2f} "
                f"(current: {self.current_joints[0]*180/3.14159:.1f}° -> "
                f"{variation[0]*180/3.14159:.1f}°), {variation_description}"
            )
            
            return variation
            
        except Exception as e:
            self.get_logger().error(f"Error generating idle head variation: {e}")
            return None
    
    def _clear_head_variation(self):
        """Clear active head variation."""
        if self.idle_head_variation_active:
            self.idle_head_variation_active = False
            self.current_idle_head_target = None
            self.get_logger().debug("Cleared idle head variation")
    
    def _is_at_home_position(self) -> bool:
        """Check if robot is at either home position."""
        return (PositionUtils.at_home_position(self.current_joints, LuxoConstants.HOME_POSITION_1) or
                PositionUtils.at_home_position(self.current_joints, LuxoConstants.HOME_POSITION_2))
    
    def _request_home_position(self, reason: str):
        """Request movement to home position."""
        try:
            if not self.enable_home_position:
                return
                
            self.get_logger().info(f"Requesting home position: {reason}")
            
            # Create position request
            msg = PositionRequest()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.request_type = "home_position"
            msg.positions = LuxoConstants.HOME_POSITION_1  # Start with stage 1
            msg.speed = 8.0  # Moderate speed for home position
            msg.description = f"Home position: {reason}"
            msg.priority = 5  # Medium-high priority
            msg.allow_interruption = False
            
            # Publish the request
            self.position_request_pub.publish(msg)
            
            # Update state
            self.home_position_requested = True
            self.home_position_start_time = self.get_clock().now()
            self.home_position_stage = 1
            
            # Reset activity time to prevent immediate re-triggering
            self.last_activity_time = self.get_clock().now()
            
        except Exception as e:
            self.get_logger().error(f"Error requesting home position: {e}")
    
    def request_rest_position(self, reason: str = "Rest position request"):
        """Request movement to rest position (external interface)."""
        try:
            if not self.enable_rest_position:
                self.get_logger().warn("Rest position disabled")
                return False
                
            rest_position = self._generate_rest_position()
            
            self.get_logger().info(f"Requesting rest position: {reason}")
            
            # Create position request
            msg = PositionRequest()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.request_type = "rest_position"
            msg.positions = rest_position
            msg.speed = 10.0  # Moderate speed for rest position
            msg.description = f"Rest position: {reason}"
            msg.priority = 6  # High priority for rest
            msg.allow_interruption = False
            
            # Publish the request
            self.position_request_pub.publish(msg)
            
            # Update state
            self.last_rest_position = rest_position
            self.last_activity_time = self.get_clock().now()
            
            return True
            
        except Exception as e:
            self.get_logger().error(f"Error requesting rest position: {e}")
            return False
    
    def _generate_rest_position(self) -> List[float]:
        """Generate a rest position with random variation."""
        rest_position = LuxoConstants.BASE_REST_POSITION.copy()
        
        # Add variation using shared utilities
        rest_position = PositionUtils.add_position_variation(
            rest_position,
            self.rest_variation_range,
            exclude_indices=[4]  # Don't vary hand position
        )
        
        return rest_position
    
    def _publish_activity_status(self, time_since_activity: float):
        """Publish current activity status."""
        try:
            msg = ActivityUpdate()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.node_name = "idle_behavior_node"
            msg.activity_type = "idle_status"
            msg.time_since_activity = time_since_activity
            msg.idle_timeout = self.current_idle_timeout
            msg.is_idle = time_since_activity > self.min_idle_time_before_animation
            
            self.activity_status_pub.publish(msg)
            
        except Exception as e:
            self.get_logger().error(f"Error publishing activity status: {e}")
    
    def reset_idle_timeout(self):
        """Reset idle timeout to a new random value (external interface)."""
        with self._state_lock:
            self.current_idle_timeout = MathUtils.random_in_range(
                self.activity_timeout_min, self.activity_timeout_max
            )
            self.last_activity_time = self.get_clock().now()
            
            self.get_logger().info(f"Idle timeout reset to {self.current_idle_timeout:.1f} seconds")
    
    def get_idle_status(self) -> dict:
        """Get current idle status (external interface)."""
        with self._state_lock:
            current_time = self.get_clock().now()
            time_since_activity = ROSUtils.time_since(self.last_activity_time, current_time)
            
            return {
                'time_since_activity': time_since_activity,
                'current_idle_timeout': self.current_idle_timeout,
                'idle_animation_active': self.idle_animation_active,
                'idle_head_variation_active': self.idle_head_variation_active,
                'home_position_requested': self.home_position_requested,
                'robot_state': self.robot_state,
                'is_idle': time_since_activity > self.min_idle_time_before_animation
            }


def main(args=None):
    """Main entry point for the idle behavior node."""
    rclpy.init(args=args)
    
    try:
        node = IdleBehaviorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()