#!/usr/bin/env python3
"""
VoiceFollowingNode - Manages voice direction following and head tracking for the Luxo robot.

This node handles:
- Voice direction detection and angle calculation
- Intelligent wraparound logic for base rotation limits
- Voice variations for face detection (looking up/down while tracking)
- Voice influence tracking and timeout management
- Coordination with other behavior systems

Author: Generated from collision_avoidance.py refactor
"""

import random
import threading
from typing import Optional, List, Tuple

import rclpy
from rclpy.node import Node
from rclpy.timer import Timer
from rclpy.time import Time

# ROS message types
from std_msgs.msg import String, Bool, Float32, Float32MultiArray
from geometry_msgs.msg import Vector3
from sensor_msgs.msg import JointState
from luxo_interfaces.msg import VoiceTarget, PositionRequest, ActivityUpdate

# Import shared utilities
from luxo_behaviors.shared_utilities import (
    LuxoConstants, 
    AngleUtils, 
    PositionUtils, 
    ROSUtils, 
    MathUtils
)

import numpy as np


class VoiceFollowingNode(Node):
    """
    ROS2 node responsible for voice direction following and head tracking.
    """
    
    def __init__(self):
        super().__init__('voice_following_node')
        
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
        
        # Create timers
        self._create_timers()
        
        # Thread lock for state protection
        self._state_lock = threading.Lock()
        
        self.get_logger().info(f"VoiceFollowingNode initialized - enabled: {self.voice_follow_enabled}")
    
    def _declare_parameters(self):
        """Declare ROS parameters with default values."""
        # Main voice following parameters
        self.declare_parameter('enable_voice_following', True)
        self.declare_parameter('voice_follow_speed', 0.3)
        self.declare_parameter('voice_follow_deadzone', 15.0)
        self.declare_parameter('voice_follow_smoothing', 0.3)
        
        # Voice variation parameters
        self.declare_parameter('voice_variation_enabled', True)
        self.declare_parameter('voice_direction_tolerance', 5.0)
        self.declare_parameter('voice_variation_interval', 2.0)
        self.declare_parameter('voice_look_up_range', 1.0)
        self.declare_parameter('voice_look_down_range', 0.2)
        self.declare_parameter('voice_on_target_threshold', 3.0)
        
        # Base rotation limits
        self.declare_parameter('base_min_limit', -260.0)  # degrees
        self.declare_parameter('base_max_limit', 135.0)   # degrees
        self.declare_parameter('enable_base_wraparound', True)
        
        # Timing parameters
        self.declare_parameter('voice_timeout', 2.0)
        self.declare_parameter('voice_influence_decay_rate', 0.8)
        self.declare_parameter('voice_influence_gain', 0.8)
    
    def _load_parameters(self):
        """Load parameters from ROS parameter server."""
        # Main voice following parameters
        self.voice_follow_enabled = self.get_parameter('enable_voice_following').value
        self.voice_follow_speed = self.get_parameter('voice_follow_speed').value
        self.voice_follow_deadzone = self.get_parameter('voice_follow_deadzone').value
        self.voice_follow_smoothing = self.get_parameter('voice_follow_smoothing').value
        
        # Voice variation parameters
        self.voice_variation_enabled = self.get_parameter('voice_variation_enabled').value
        self.voice_direction_tolerance = self.get_parameter('voice_direction_tolerance').value
        self.voice_variation_interval = self.get_parameter('voice_variation_interval').value
        self.voice_look_up_range = self.get_parameter('voice_look_up_range').value
        self.voice_look_down_range = self.get_parameter('voice_look_down_range').value
        self.voice_on_target_threshold = self.get_parameter('voice_on_target_threshold').value
        
        # Base rotation limits (convert degrees to radians)
        self.base_min_limit = np.deg2rad(self.get_parameter('base_min_limit').value)
        self.base_max_limit = np.deg2rad(self.get_parameter('base_max_limit').value)
        self.enable_base_wraparound = self.get_parameter('enable_base_wraparound').value
        
        # Timing parameters
        self.voice_timeout = self.get_parameter('voice_timeout').value
        self.voice_influence_decay_rate = self.get_parameter('voice_influence_decay_rate').value
        self.voice_influence_gain = self.get_parameter('voice_influence_gain').value
    
    def _initialize_state(self):
        """Initialize internal state variables."""
        # Current robot state
        self.current_joints: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.robot_state: str = "IDLE"
        
        # Voice tracking state
        self.last_voice_direction: Optional[float] = None
        self.last_voice_time: Optional[Time] = None
        self.voice_influence: float = 0.0
        self.target_voice_angle: Optional[float] = None
        self.voice_active: bool = False
        
        # Voice variation state
        self.voice_on_target_start_time: Optional[Time] = None
        self.last_voice_variation_time: Optional[Time] = None
        self.current_voice_variation: Optional[List[float]] = None
        
        # Voice neutral position (excluding base joint)
        self.voice_neutral_position = LuxoConstants.VOICE_NEUTRAL_POSITION.copy()
        
        # Coordination state
        self.collision_active: bool = False
        self.other_behaviors_active: bool = False
        
        # Internal tracking
        self.last_command_time: Optional[Time] = None
        self.position_request_active: bool = False
    
    def _create_publishers(self):
        """Create ROS publishers."""
        # Voice target position
        self.voice_target_pub = self.create_publisher(
            VoiceTarget,
            '/voice/target_position',
            10
        )
        
        # Position requests to safety coordinator
        self.position_request_pub = self.create_publisher(
            PositionRequest,
            '/voice/position_request',
            10
        )
        
        # Voice following status
        self.voice_status_pub = self.create_publisher(
            Float32MultiArray,
            '/voice/status',
            10
        )
        
        # Activity updates
        self.activity_update_pub = self.create_publisher(
            ActivityUpdate,
            '/robot/activity_update',
            10
        )
        
        # Debug information
        self.debug_pub = self.create_publisher(
            String,
            '/voice/debug',
            10
        )
    
    def _create_subscribers(self):
        """Create ROS subscribers."""
        # Voice direction input
        self.voice_direction_sub = self.create_subscription(
            Float32,
            '/voice/follow_direction',
            self.voice_direction_callback,
            10
        )
        
        # Voice activity status
        self.voice_active_sub = self.create_subscription(
            Bool,
            '/voice/active',
            self.voice_active_callback,
            10
        )
        
        # Robot joint states
        self.joint_states_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_states_callback,
            10
        )
        
        # Robot state updates
        self.robot_state_sub = self.create_subscription(
            String,
            '/luxo/current_state',
            self.robot_state_callback,
            10
        )
        
        # Collision status
        self.collision_status_sub = self.create_subscription(
            Bool,
            '/collision/active',
            self.collision_status_callback,
            10
        )
        
        # Other behavior activity status
        self.behavior_status_sub = self.create_subscription(
            String,
            '/behavior/active',
            self.behavior_status_callback,
            10
        )
    
    def _create_timers(self):
        """Create periodic timers."""
        # Main voice processing timer (runs every 100ms for responsive tracking)
        self.voice_timer = self.create_timer(0.1, self.voice_timer_callback)
        
        # Status publishing timer (runs every 0.5 seconds)
        self.status_timer = self.create_timer(0.5, self.status_timer_callback)
    
    def voice_direction_callback(self, msg: Float32):
        """Handle voice direction updates with intelligent wraparound and variation."""
        if not self.voice_follow_enabled:
            return
        
        with self._state_lock:
            # Only process if in appropriate state
            if not self._should_process_voice():
                return
            
            # Update voice tracking
            self.last_voice_direction = msg.data
            self.last_voice_time = self.get_clock().now()
            
            # Increase voice influence aggressively
            self.voice_influence = min(1.0, self.voice_influence + self.voice_influence_gain)
            
            # Convert voice direction to target angle with intelligent wraparound
            target_angle_rad = np.deg2rad(self.last_voice_direction)
            target_angle = AngleUtils.normalize_angle(target_angle_rad)
            
            # Calculate wraparound target if needed
            self.target_voice_angle, was_wrapped = AngleUtils.calculate_wraparound_target(
                target_angle, self.base_min_limit, self.base_max_limit
            )
            
            if was_wrapped:
                self.get_logger().info(
                    f"Voice at {self.last_voice_direction}° using wraparound to "
                    f"{np.rad2deg(self.target_voice_angle):.1f}°"
                )
            else:
                self.get_logger().debug(
                    f"Voice detected at {self.last_voice_direction:.1f}°, "
                    f"target angle: {np.rad2deg(self.target_voice_angle):.1f}°"
                )
            
            # Send command immediately
            self._send_voice_following_command()
            
            # Publish activity update
            self._publish_activity_update("voice_direction_detected")
    
    def voice_active_callback(self, msg: Bool):
        """Handle voice activity status."""
        with self._state_lock:
            self.voice_active = msg.data
            
            if not msg.data:
                # Start decay when voice stops
                self.voice_influence *= self.voice_influence_decay_rate
                self.get_logger().debug(f"Voice stopped - influence decaying to {self.voice_influence:.2f}")
    
    def joint_states_callback(self, msg: JointState):
        """Handle joint state updates."""
        if len(msg.position) >= 5:
            with self._state_lock:
                self.current_joints = list(msg.position[:5])
    
    def robot_state_callback(self, msg: String):
        """Handle robot state changes."""
        with self._state_lock:
            self.robot_state = msg.data
    
    def collision_status_callback(self, msg: Bool):
        """Handle collision status updates."""
        with self._state_lock:
            self.collision_active = msg.data
    
    def behavior_status_callback(self, msg: String):
        """Handle other behavior activity status."""
        with self._state_lock:
            # Parse behavior status messages
            active_behaviors = msg.data.split(',') if msg.data else []
            self.other_behaviors_active = any(
                behavior in ['ESCAPE_MODE', 'RETURNING_HOME', 'PETTING'] 
                for behavior in active_behaviors
            )
    
    def voice_timer_callback(self):
        """Main voice processing timer callback."""
        try:
            with self._state_lock:
                current_time = self.get_clock().now()
                
                # Check for voice timeout
                if self._check_voice_timeout(current_time):
                    return
                
                # Process voice variations if on target
                if self._should_add_voice_variation(current_time):
                    self._generate_voice_variation()
                    self._send_voice_following_command()
                
                # Decay influence gradually when not receiving new voice data
                if self.last_voice_time:
                    time_since_voice = ROSUtils.time_since(self.last_voice_time, current_time)
                    if time_since_voice > 0.5:  # Start decaying after 0.5 seconds
                        self.voice_influence *= 0.98  # Gradual decay
                        
                        if self.voice_influence < 0.1:
                            self._clear_voice_following()
                
        except Exception as e:
            self.get_logger().error(f"Error in voice timer callback: {e}")
    
    def status_timer_callback(self):
        """Publish voice following status."""
        try:
            with self._state_lock:
                # Publish voice status
                status_msg = Float32MultiArray()
                status_msg.data = [
                    float(self.voice_active),
                    self.voice_influence,
                    self.last_voice_direction if self.last_voice_direction is not None else 0.0,
                    np.rad2deg(self.target_voice_angle) if self.target_voice_angle is not None else 0.0
                ]
                self.voice_status_pub.publish(status_msg)
                
        except Exception as e:
            self.get_logger().error(f"Error in status timer callback: {e}")
    
    def _should_process_voice(self) -> bool:
        """Check if voice input should be processed."""
        # Don't process if disabled
        if not self.voice_follow_enabled:
            return False
        
        # Don't process if not in appropriate state
        valid_states = ['IDLE', 'ANIMATING', 'EMOTION_REACTING']
        if self.robot_state not in valid_states:
            return False
        
        # Don't process if collision avoidance is active
        if self.collision_active:
            return False
        
        # Don't process if higher priority behaviors are active
        if self.other_behaviors_active:
            return False
        
        return True
    
    def _check_voice_timeout(self, current_time: Time) -> bool:
        """Check for voice timeout and clear if needed."""
        if not self.last_voice_time:
            return False
        
        time_since_voice = ROSUtils.time_since(self.last_voice_time, current_time)
        
        if time_since_voice > self.voice_timeout:
            self._clear_voice_following()
            return True
        
        return False
    
    def _clear_voice_following(self):
        """Clear voice following state."""
        self.voice_influence = 0.0
        self.target_voice_angle = None
        self.voice_on_target_start_time = None
        self.current_voice_variation = None
        self.position_request_active = False
        
        self.get_logger().debug("Voice following cleared due to timeout")
    
    def _check_voice_on_target(self, current_time: Time) -> bool:
        """Check if robot is pointing at voice direction and start variation timer."""
        if not self.voice_variation_enabled or self.target_voice_angle is None:
            return False
        
        current_base = self.current_joints[0] if self.current_joints else 0.0
        angle_diff = abs(AngleUtils.normalize_angle(self.target_voice_angle - current_base))
        angle_diff_deg = np.rad2deg(angle_diff)
        
        if angle_diff_deg <= self.voice_direction_tolerance:
            # We're on target
            if self.voice_on_target_start_time is None:
                self.voice_on_target_start_time = current_time
                self.get_logger().debug(f"Voice on target - starting variation timer (diff: {angle_diff_deg:.1f}°)")
            return True
        else:
            # We're not on target, reset timer
            if self.voice_on_target_start_time is not None:
                self.get_logger().debug(f"Voice off target - resetting timer (diff: {angle_diff_deg:.1f}°)")
            self.voice_on_target_start_time = None
            self.current_voice_variation = None
            return False
    
    def _should_add_voice_variation(self, current_time: Time) -> bool:
        """Check if we should add variation to voice following."""
        if not self.voice_variation_enabled:
            return False
        
        if not self._check_voice_on_target(current_time):
            return False
        
        # Check if we've been on target long enough
        if self.voice_on_target_start_time is None:
            return False
        
        time_on_target = ROSUtils.time_since(self.voice_on_target_start_time, current_time)
        if time_on_target < self.voice_on_target_threshold:
            return False
        
        # Check if enough time has passed since last variation
        if self.last_voice_variation_time is not None:
            time_since_variation = ROSUtils.time_since(self.last_voice_variation_time, current_time)
            if time_since_variation < self.voice_variation_interval:
                return False
        
        return True
    
    def _generate_voice_variation(self):
        """Generate semi-random up/down movement for voice following."""
        current_time = self.get_clock().now()
        
        # Generate random variation - bias towards looking up for face detection
        # 85% chance to look up, 10% chance to look down, 5% chance to return to neutral
        variation_type = random.random()
        
        if variation_type < 0.85:  # Look up (85% chance)
            shoulder_variation = MathUtils.random_in_range(0.2, self.voice_look_up_range)
            elbow_variation = MathUtils.random_in_range(-0.2, 0.2)
            wrist_variation = MathUtils.random_in_range(-0.4, 0.0)
            variation_description = "looking up"
        elif variation_type < 0.95:  # Look down (10% chance)
            shoulder_variation = MathUtils.random_in_range(-self.voice_look_down_range, -0.05)
            elbow_variation = MathUtils.random_in_range(-0.05, 0.05)
            wrist_variation = MathUtils.random_in_range(0.0, 0.1)
            variation_description = "looking down"
        else:  # Return to neutral (5% chance)
            shoulder_variation = 0.0
            elbow_variation = 0.0
            wrist_variation = 0.0
            variation_description = "returning to neutral"
        
        # Create varied position based on neutral
        varied_position = self.voice_neutral_position.copy()
        varied_position[0] += shoulder_variation  # Shoulder
        varied_position[1] += elbow_variation     # Elbow
        varied_position[2] += wrist_variation     # Wrist
        # Keep hand and other joints the same
        
        self.current_voice_variation = varied_position
        self.last_voice_variation_time = current_time
        
        self.get_logger().info(
            f"Voice variation: {variation_description} "
            f"(shoulder: {shoulder_variation:+.2f}, elbow: {elbow_variation:+.2f}, wrist: {wrist_variation:+.2f})"
        )
    
    def _send_voice_following_command(self):
        """Send voice following command to safety coordinator."""
        if not self.voice_follow_enabled or self.voice_influence < 0.1:
            return
        
        if self.target_voice_angle is None:
            return
        
        try:
            # Create position with direct target angle
            voice_position = self.current_joints.copy()
            voice_position[0] = self.target_voice_angle  # Set base directly to target
            
            # Apply variation if we have one
            if self.current_voice_variation is not None:
                # Apply variation to joints 1-4 (shoulder, elbow, wrist, hand)
                for i in range(1, min(5, len(voice_position))):
                    if i-1 < len(self.current_voice_variation):
                        voice_position[i] = self.current_voice_variation[i-1]
            else:
                # Use neutral position for non-base joints
                for i in range(1, min(5, len(voice_position))):
                    if i-1 < len(self.voice_neutral_position):
                        voice_position[i] = self.voice_neutral_position[i-1]
            
            # Ensure we only have 5 joint positions
            if len(voice_position) > 5:
                voice_position = voice_position[:5]
            
            # Create position request message
            msg = PositionRequest()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.request_type = "voice_following"
            msg.positions = voice_position
            msg.speed = 7.0  # Responsive speed for voice following
            msg.description = f"Voice following with face detection (influence: {self.voice_influence:.2f})"
            msg.priority = 3  # Medium priority
            msg.allow_interruption = True
            
            # Publish the request
            self.position_request_pub.publish(msg)
            self.position_request_active = True
            self.last_command_time = self.get_clock().now()
            
            # Also publish voice target for other nodes
            target_msg = VoiceTarget()
            target_msg.header.stamp = self.get_clock().now().to_msg()
            target_msg.target_angle_deg = np.rad2deg(self.target_voice_angle)
            target_msg.influence = self.voice_influence
            target_msg.has_variation = self.current_voice_variation is not None
            target_msg.positions = voice_position
            
            self.voice_target_pub.publish(target_msg)
            
            self.get_logger().debug(
                f"Voice command sent: base to {np.rad2deg(self.target_voice_angle):.1f}° "
                f"with influence {self.voice_influence:.2f}"
            )
            
        except Exception as e:
            self.get_logger().error(f"Error sending voice following command: {e}")
    
    def _publish_activity_update(self, activity_type: str):
        """Publish activity update for coordination."""
        try:
            msg = ActivityUpdate()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.node_name = "voice_following_node"
            msg.activity_type = activity_type
            msg.time_since_activity = 0.0  # Just happened
            msg.is_idle = False
            
            self.activity_update_pub.publish(msg)
            
        except Exception as e:
            self.get_logger().error(f"Error publishing activity update: {e}")
    
    def apply_voice_following_to_position(self, positions: List[float]) -> List[float]:
        """
        Apply voice following to a given position (external interface).
        
        Args:
            positions: Base joint positions to modify
            
        Returns:
            Modified positions with voice following applied
        """
        with self._state_lock:
            # Return original positions if voice following not active
            if self.voice_influence < 0.1 or self.target_voice_angle is None:
                return positions.copy()
            
            # Check for voice timeout
            if self.last_voice_time:
                current_time = self.get_clock().now()
                if ROSUtils.time_since(self.last_voice_time, current_time) > self.voice_timeout:
                    return positions.copy()
            
            # Apply voice following
            adjusted_positions = positions.copy()
            adjusted_positions[0] = self.target_voice_angle  # Set base directly
            
            # Apply variation if available
            if self.current_voice_variation is not None:
                for i in range(1, min(5, len(adjusted_positions))):
                    if i-1 < len(self.current_voice_variation):
                        adjusted_positions[i] = self.current_voice_variation[i-1]
            
            return adjusted_positions
    
    def get_voice_status(self) -> dict:
        """Get current voice following status (external interface)."""
        with self._state_lock:
            return {
                'enabled': self.voice_follow_enabled,
                'active': self.voice_active,
                'influence': self.voice_influence,
                'target_angle_deg': np.rad2deg(self.target_voice_angle) if self.target_voice_angle else None,
                'last_direction_deg': self.last_voice_direction,
                'has_variation': self.current_voice_variation is not None,
                'on_target': self.voice_on_target_start_time is not None,
                'position_request_active': self.position_request_active
            }
    
    def set_voice_enabled(self, enabled: bool):
        """Enable or disable voice following (external interface)."""
        with self._state_lock:
            self.voice_follow_enabled = enabled
            if not enabled:
                self._clear_voice_following()
            
            self.get_logger().info(f"Voice following {'enabled' if enabled else 'disabled'}")
    
    def force_clear_voice_following(self):
        """Force clear voice following state (external interface)."""
        with self._state_lock:
            self._clear_voice_following()
            self.get_logger().info("Voice following force cleared")


def main(args=None):
    """Main entry point for the voice following node."""
    rclpy.init(args=args)
    
    try:
        node = VoiceFollowingNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()