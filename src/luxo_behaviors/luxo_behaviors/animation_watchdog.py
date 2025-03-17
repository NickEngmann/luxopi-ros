#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String
import time
import threading

class AnimationWatchdog(Node):
    def __init__(self):
        super().__init__('animation_watchdog')
        
        # Parameters
        self.declare_parameter('animation_timeout', 30.0)  # Seconds before considering animation stuck
        self.declare_parameter('check_interval', 2.0)  # How often to check animation progress
        
        self.animation_timeout = self.get_parameter('animation_timeout').value
        self.check_interval = self.get_parameter('check_interval').value
        
        # Subscribe to joint states to track movement
        self.joint_state_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_state_callback,
            10)
            
        # Command publisher to send reset if needed
        self.command_pub = self.create_publisher(
            String,
            '/roarm/animation_command',
            10)
            
        # State tracking
        self.last_position = None
        self.last_movement_time = time.time()
        self.position_history = []
        self.animation_start_time = None
        self.active_animation = False
        self.watchdog_lock = threading.Lock()
        
        # Create timer for checking animation status
        self.timer = self.create_timer(self.check_interval, self.check_animation_status)
        
        self.get_logger().info("Animation watchdog initialized")
        
    def joint_state_callback(self, msg):
        """Track joint positions to detect stuck animations"""
        current_time = time.time()
        
        # Convert to list for easier comparison
        current_position = list(msg.position)
        
        # Skip if no valid position
        if not current_position:
            return
            
        with self.watchdog_lock:
            # If first callback, just store the position
            if self.last_position is None:
                self.last_position = current_position
                self.last_movement_time = current_time
                return
                
            # Calculate difference between positions
            movement_detected = False
            if len(current_position) == len(self.last_position):
                diff_sum = sum([abs(c - p) for c, p in zip(current_position, self.last_position)])
                if diff_sum > 0.02:  # Movement threshold
                    movement_detected = True
            
            # Update tracking if movement detected
            if movement_detected:
                self.last_movement_time = current_time
                self.last_position = current_position
                
                # Add to history with timestamp
                self.position_history.append((current_time, current_position))
                
                # Keep history manageable
                while len(self.position_history) > 20:
                    self.position_history.pop(0)
                
                # If movement detected, assume animation is active
                if not self.active_animation:
                    self.active_animation = True
                    self.animation_start_time = current_time
                    self.get_logger().info("Animation activity detected")
    
    def check_animation_status(self):
        """Check if animation appears to be stuck"""
        current_time = time.time()
        
        with self.watchdog_lock:
            # Skip if no animation seems to be running
            if not self.active_animation:
                return
                
            # Check time since last movement
            time_since_movement = current_time - self.last_movement_time
            
            # If stuck for too long, attempt recovery
            if time_since_movement > self.animation_timeout:
                self.get_logger().warn(f"Animation appears stuck for {time_since_movement:.1f}s - attempting recovery")
                self.recover_from_stuck_animation()
            
            # Check if animation has been running too long overall
            if self.animation_start_time and (current_time - self.animation_start_time) > 60.0:  # 1 minute max
                self.get_logger().warn("Animation running too long - may be in a loop or stuck")
                self.recover_from_stuck_animation()
    
    def recover_from_stuck_animation(self):
        """Attempt to recover from stuck animation"""
        # First stop any current animation
        stop_msg = String()
        stop_msg.data = "stop"
        self.command_pub.publish(stop_msg)
        self.get_logger().info("Sent stop command to animation system")
        
        # Wait a moment
        time.sleep(1.0)
        
        # Return to a safe position
        home_msg = String()
        home_msg.data = "idle"  # Use idle animation to get to safe position
        self.command_pub.publish(home_msg)
        self.get_logger().info("Sent command to return to idle position")
        
        # Reset tracking state
        with self.watchdog_lock:
            self.active_animation = False
            self.animation_start_time = None
            self.position_history = []

def main(args=None):
    rclpy.init(args=args)
    node = AnimationWatchdog()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
