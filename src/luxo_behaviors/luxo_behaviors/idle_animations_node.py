#!/usr/bin/env python3
#idle_animations_node.py

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String, Float64MultiArray
from sensor_msgs.msg import JointState
from luxo_interfaces.action import PlayAnimation
from luxo_interfaces.srv import RequestStateTransition
from luxo_behaviors.state_machine import LuxoState
import random
import time
import numpy as np


class IdleAnimationsNode(Node):
    """
    Shadow node for idle animation behavior.
    Monitors idle state and logs when animations would be triggered.
    """
    
    def __init__(self):
        super().__init__('idle_animations')
        
        # Parameters
        self.declare_parameter('shadow_mode', True)  # Run in shadow mode (no actual animations)
        self.declare_parameter('min_idle_time_before_animation', 5.0)  # seconds
        self.declare_parameter('idle_animation_interval_min', 10.0)
        self.declare_parameter('idle_animation_interval_max', 60.0)
        self.declare_parameter('enable_idle_animations', True)
        
        # Idle head variation parameters
        self.declare_parameter('enable_idle_head_variation', True)
        self.declare_parameter('idle_head_variation_interval', 10.0)  # Max interval
        self.declare_parameter('idle_head_base_rotation_range', 0.3)
        self.declare_parameter('idle_head_look_up_range', 0.4)
        self.declare_parameter('idle_head_look_down_range', 0.1)
        
        self.shadow_mode = self.get_parameter('shadow_mode').value
        self.min_idle_time = self.get_parameter('min_idle_time_before_animation').value
        self.interval_min = self.get_parameter('idle_animation_interval_min').value
        self.interval_max = self.get_parameter('idle_animation_interval_max').value
        self.enabled = self.get_parameter('enable_idle_animations').value
        
        # Head variation parameters
        self.head_variation_enabled = self.get_parameter('enable_idle_head_variation').value
        self.head_variation_interval = self.get_parameter('idle_head_variation_interval').value
        self.head_base_rotation_range = self.get_parameter('idle_head_base_rotation_range').value
        self.head_look_up_range = self.get_parameter('idle_head_look_up_range').value
        self.head_look_down_range = self.get_parameter('idle_head_look_down_range').value
        
        # State tracking
        self.current_state = None
        self.idle_start_time = None
        self.last_animation_time = None
        self.next_animation_interval = self._get_random_interval()
        
        # Head variation tracking
        self.last_head_variation_time = None
        self.next_head_variation_interval = self._get_random_head_variation_interval()
        self.idle_base_position = [0.0, -0.55, 1.2, 1.0, 2.0]  # Standard idle position
        self.current_joints = [0.0, 0.0, 0.0, 0.0, 0.0]  # Current joint positions
        
        # Animation list (same as in collision_avoidance)
        self.idle_animations = [
            'gentle_sway', 'curious_exploration', 'breathing', 
            'attentive_listening', 'playful_bob', 'scanning_watch',
            'settling_adjust', 'dreamy_drift', 'neck_stretch',
            'yawning_stretch', 'shoulder_shimmy', 'look_around_casual'
        ]
        self.last_idle_animation = None
        
        # Subscribe to current state
        self.state_sub = self.create_subscription(
            String,
            '/luxo/current_state',
            self.state_callback,
            10
        )
        
        # Subscribe to joint states (for head variations)
        self.joint_state_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_state_callback,
            10
        )
        
        # Publisher for joint commands (head variations)
        self.joint_command_pub = self.create_publisher(
            Float64MultiArray,
            '/roarm_target_joint_positions',
            10
        )
        
        # Create service client for state transitions (for future use)
        self.state_transition_client = self.create_client(
            RequestStateTransition,
            '/luxo/request_state_transition'
        )
        
        # Create action client for animations (for future use)
        self.animation_client = ActionClient(
            self,
            PlayAnimation,
            'play_animation'
        )
        
        # Heartbeat publisher
        self.heartbeat_pub = self.create_publisher(
            String,
            '/luxo/node_heartbeat',
            10
        )
        
        # Timer for checking idle state
        self.check_timer = self.create_timer(1.0, self.check_idle_state)  # Check every second
        self.heartbeat_timer = self.create_timer(2.0, self.send_heartbeat)  # Heartbeat every 2s
        
        # Log startup
        if self.shadow_mode:
            self.get_logger().info("Idle Animations Node started in SHADOW MODE - monitoring only")
        else:
            self.get_logger().info("Idle Animations Node started in ACTIVE MODE")
            
        self.get_logger().info(f"Configuration: min_idle_time={self.min_idle_time}s, "
                              f"animation_interval={self.interval_min}-{self.interval_max}s, "
                              f"head_variation_interval=3.5-{self.head_variation_interval}s")
    
    def joint_state_callback(self, msg):
        """Update current joint positions"""
        if len(msg.position) >= 5:
            self.current_joints = list(msg.position[:5])
    
    def state_callback(self, msg):
        """Handle state updates from state manager"""
        new_state = msg.data
        old_state = self.current_state
        self.current_state = new_state
        
        # Check if we just entered IDLE state
        if new_state == 'IDLE' and old_state != 'IDLE':
            self.idle_start_time = time.time()
            self.last_head_variation_time = None  # Reset head variation timer
            self.get_logger().info(f"Entered IDLE state - starting idle timer")
            
        # Check if we left IDLE state
        elif old_state == 'IDLE' and new_state != 'IDLE':
            if self.idle_start_time:
                idle_duration = time.time() - self.idle_start_time
                self.get_logger().info(f"Left IDLE state after {idle_duration:.1f}s")
            self.idle_start_time = None
            self.last_head_variation_time = None  # Reset head variation timer
    
    def check_idle_state(self):
        """Check if we should trigger an idle animation or head variation"""
        if not self.current_state == 'IDLE':
            return
            
        if self.idle_start_time is None:
            return
            
        current_time = time.time()
        time_idle = current_time - self.idle_start_time
        
        # Check for idle head variations (more frequent than full animations)
        if self.head_variation_enabled:
            if self.last_head_variation_time is None:
                # First head variation can happen immediately when idle
                self.trigger_idle_head_variation()
            else:
                time_since_variation = current_time - self.last_head_variation_time
                if time_since_variation >= self.next_head_variation_interval:
                    self.trigger_idle_head_variation()
        
        # Check for full idle animations
        if self.enabled:
            # Check if we've been idle long enough for first animation
            if self.last_animation_time is None:
                if time_idle >= self.min_idle_time:
                    self.trigger_idle_animation()
            else:
                # Check if enough time passed since last animation
                time_since_last = current_time - self.last_animation_time
                if time_since_last >= self.next_animation_interval:
                    self.trigger_idle_animation()
    
    def trigger_idle_animation(self):
        """Trigger an idle animation (or log in shadow mode)"""
        # Select animation
        available = [a for a in self.idle_animations if a != self.last_idle_animation]
        if not available:
            available = self.idle_animations
        
        selected_animation = random.choice(available)
        speed_multiplier = random.uniform(0.8, 1.2)
        
        if self.shadow_mode:
            # Just log what we would do
            self.get_logger().info(
                f"[SHADOW] Would trigger idle animation: {selected_animation} "
                f"(speed: {speed_multiplier:.1f}x)"
            )
            
            # Log timing info
            if self.last_animation_time:
                interval = time.time() - self.last_animation_time
                self.get_logger().debug(f"[SHADOW] Time since last animation: {interval:.1f}s")
            
            time_idle = time.time() - self.idle_start_time if self.idle_start_time else 0
            self.get_logger().debug(f"[SHADOW] Total idle time: {time_idle:.1f}s")
        else:
            # Actually trigger animation in active mode
            self.get_logger().info(f"Triggering idle animation: {selected_animation}")
            
            # Wait for action server to be ready
            if not self.animation_client.wait_for_server(timeout_sec=1.0):
                self.get_logger().warn("Animation action server not available")
                return
            
            # Create and send goal
            goal = PlayAnimation.Goal()
            goal.animation_name = selected_animation
            goal.speed_multiplier = speed_multiplier
            goal.allow_interruption = True
            goal.use_hardware_feedback = False
            
            # Send goal asynchronously
            future = self.animation_client.send_goal_async(goal)
            future.add_done_callback(self._animation_goal_response_callback)
        
        # Update tracking
        self.last_idle_animation = selected_animation
        self.last_animation_time = time.time()
        self.next_animation_interval = self._get_random_interval()
        
        self.get_logger().debug(f"Next animation in {self.next_animation_interval:.1f}s")
    
    def _animation_goal_response_callback(self, future):
        """Handle animation goal response"""
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.get_logger().warn("Animation goal rejected")
            else:
                self.get_logger().debug("Animation goal accepted")
        except Exception as e:
            self.get_logger().error(f"Error in animation goal response: {e}")
    
    def _get_random_interval(self):
        """Get a random interval for next animation"""
        return random.uniform(self.interval_min, self.interval_max)
    
    def _get_random_head_variation_interval(self):
        """Get a random interval for next head variation"""
        return random.uniform(3.5, self.head_variation_interval)
    
    def trigger_idle_head_variation(self):
        """Trigger an idle head variation (or log in shadow mode)"""
        # Generate head variation
        variation = self._generate_idle_head_variation()
        
        if variation and self.shadow_mode:
            # Log what we would do
            base_change = variation[0]
            look_direction = variation[1]
            
            self.get_logger().info(
                f"[SHADOW] Would trigger idle head variation: "
                f"base {base_change:+.2f} rad ({np.rad2deg(base_change):+.1f}°), "
                f"{look_direction}"
            )
            
            # Log timing info
            if self.last_head_variation_time:
                interval = time.time() - self.last_head_variation_time
                self.get_logger().debug(f"[SHADOW] Time since last head variation: {interval:.1f}s")
        elif variation and not self.shadow_mode:
            # TODO: Actually send head variation command in active mode
            self.get_logger().info(f"Triggering idle head variation: {variation}")
        
        # Update tracking
        self.last_head_variation_time = time.time()
        self.next_head_variation_interval = self._get_random_head_variation_interval()
        
        self.get_logger().debug(f"Next head variation in {self.next_head_variation_interval:.1f}s")
    
    def _generate_idle_head_variation(self):
        """Generate a subtle head movement variation"""
        try:
            # Add subtle base rotation (looking left/right slightly)
            base_variation = random.uniform(-self.head_base_rotation_range, 
                                          self.head_base_rotation_range)
            
            # Add vertical look variation (primarily through shoulder adjustment)
            # Bias towards looking up (70% chance) as it appears more alert/curious
            look_type = random.random()
            if look_type < 0.7:  # Look up
                shoulder_variation = random.uniform(0.1, self.head_look_up_range)
                variation_description = f"looking up (+{shoulder_variation:.2f})"
            elif look_type < 0.9:  # Look down slightly
                shoulder_variation = random.uniform(0.0, self.head_look_down_range)
                shoulder_variation = -shoulder_variation  # Make it negative for down
                variation_description = f"looking down ({shoulder_variation:.2f})"
            else:  # Stay neutral
                shoulder_variation = 0.0
                variation_description = "staying neutral"
            
            return (base_variation, variation_description)
            
        except Exception as e:
            self.get_logger().error(f"Error generating idle head variation: {e}")
            return None
    
    def send_heartbeat(self):
        """Send heartbeat to state manager"""
        msg = String()
        msg.data = f"idle_animations:IDLE:30"  # node_name:preferred_state:priority
        self.heartbeat_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    
    node = IdleAnimationsNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()