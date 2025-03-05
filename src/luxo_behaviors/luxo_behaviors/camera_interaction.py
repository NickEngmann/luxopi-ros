#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np
from std_msgs.msg import String
import time

class CameraInteraction(Node):
    def __init__(self):
        super().__init__('camera_interaction')
        
        # Create CV bridge for image conversion
        self.bridge = CvBridge()
        
        # Subscribe to depth/stereo image
        self.stereo_subscription = self.create_subscription(
            Image,
            '/oak/stereo/image_raw',  # Topic name from your system
            self.stereo_callback,
            10)
        
        # Subscribe to RGB image
        self.rgb_subscription = self.create_subscription(
            Image,
            '/oak/rgb/image_raw',  # Topic name from your system
            self.rgb_callback,
            10)
        
        # Create publisher for animation commands
        self.animation_publisher = self.create_publisher(
            String,
            '/roarm/animation_command',
            10)
        
        # State variables
        self.last_animation_time = self.get_clock().now()
        self.cooldown_seconds = 5.0  # Time between animations
        self.stereo_image = None
        self.rgb_image = None
        
        self.get_logger().info('Camera interaction node initialized')
    
    def stereo_callback(self, msg):
        """Process stereo/depth image and trigger animations."""
        try:
            # Convert ROS Image message to OpenCV image
            self.stereo_image = self.bridge.imgmsg_to_cv2(msg)
            
            # Check if enough time has passed since last animation
            current_time = self.get_clock().now()
            elapsed_time = (current_time.nanoseconds - self.last_animation_time.nanoseconds) / 1e9
            if elapsed_time < self.cooldown_seconds:
                return
            
            # Simple detection: Check for objects in different regions
            if self.stereo_image is not None:
                height, width = self.stereo_image.shape[:2]  # Handle both mono and color images
                
                # Define regions: center, left, right
                center_region = self.stereo_image[height//3:2*height//3, width//3:2*width//3]
                left_region = self.stereo_image[height//3:2*height//3, 0:width//3]
                right_region = self.stereo_image[height//3:2*height//3, 2*width//3:width]
                
                # Simple motion detection (comparing brightness levels)
                # This is a placeholder - implement more sophisticated detection as needed
                center_activity = np.std(center_region)
                left_activity = np.std(left_region)
                right_activity = np.std(right_region)
                
                threshold = 10.0  # Adjust based on your image characteristics
                
                # Decide which animation to trigger
                if center_activity > threshold and center_activity > left_activity and center_activity > right_activity:
                    # Activity in center - curious look
                    self.get_logger().info(f'Detected activity in center, level: {center_activity:.2f}')
                    self.publish_animation('curious')
                    self.last_animation_time = current_time
                
                elif left_activity > threshold and left_activity > center_activity:
                    # Activity on the left - tracking
                    self.get_logger().info(f'Detected activity on the left, level: {left_activity:.2f}')
                    self.publish_animation('sweep')
                    self.last_animation_time = current_time
                
                elif right_activity > threshold and right_activity > center_activity:
                    # Activity on the right - tracking
                    self.get_logger().info(f'Detected activity on the right, level: {right_activity:.2f}')
                    self.publish_animation('sweep')
                    self.last_animation_time = current_time
                
                # Check for sudden large changes (excited hop)
                total_activity = center_activity + left_activity + right_activity
                if total_activity > threshold * 3:
                    self.get_logger().info(f'Detected high activity - getting excited')
                    self.publish_animation('excited')
                    self.last_animation_time = current_time
        
        except Exception as e:
            self.get_logger().error(f'Error processing stereo image: {str(e)}')
    
    def rgb_callback(self, msg):
        """Store RGB image for potential future use."""
        try:
            self.rgb_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            self.get_logger().error(f'Error processing RGB image: {str(e)}')
    
    def publish_animation(self, animation_name):
        """Publish an animation command."""
        msg = String()
        msg.data = animation_name
        self.animation_publisher.publish(msg)
        self.get_logger().info(f'Published animation command: {animation_name}')

def main(args=None):
    rclpy.init(args=args)
    interaction_node = CameraInteraction()
    
    # Keep the node running
    rclpy.spin(interaction_node)
    
    interaction_node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()