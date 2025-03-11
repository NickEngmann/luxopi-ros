#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool, Int16
import board
from adafruit_apds9960.apds9960 import APDS9960
import time
import threading
import queue

class APDS9960Node(Node):
    def __init__(self):
        super().__init__('apds9960_node')
        
        # Initialize I2C and sensor
        self.i2c = board.I2C()  # uses board.SCL and board.SDA
        self.apds = APDS9960(self.i2c)
        self.apds.enable_proximity = True
        self.apds.proximity_gain = 1
        self.apds.enable_gesture = True
        
        # Set the proximity threshold for collision detection
        self.declare_parameter('proximity_threshold', 5)
        self.proximity_threshold = self.get_parameter('proximity_threshold').value
        
        # Publishers
        self.collision_pub = self.create_publisher(Bool, '/collision_warning', 10)
        self.gesture_pub = self.create_publisher(String, '/gestures', 10)
        self.proximity_pub = self.create_publisher(Int16, '/proximity', 10)
        
        # Create a queue for thread communication
        self.gesture_queue = queue.Queue()
        
        # Start gesture detection in its own thread
        self.gesture_thread = threading.Thread(target=self.gesture_detection, daemon=True)
        self.gesture_thread.start()
        
        # Create timer for proximity readings
        self.timer = self.create_timer(0.2, self.proximity_callback)
        
        self.get_logger().info('APDS9960 node initialized')
        self.get_logger().info(f'Proximity threshold set to: {self.proximity_threshold}')

    def gesture_detection(self):
        """Gesture detection function running in a separate thread"""
        while True:
            try:
                # Call gesture() in its own thread
                gesture = self.apds.gesture()
                if gesture:  # Only put on queue if there's a valid gesture
                    if gesture == 0x01:
                        self.gesture_queue.put("up")
                    elif gesture == 0x02:
                        self.gesture_queue.put("down")
                    elif gesture == 0x03:
                        self.gesture_queue.put("left")
                    elif gesture == 0x04:
                        self.gesture_queue.put("right")
                time.sleep(0.01)  # Small sleep to prevent CPU overload
            except Exception as e:
                self.get_logger().error(f"Gesture thread error: {e}")
                time.sleep(1)

    def proximity_callback(self):
        """Timer callback for proximity readings"""
        try:
            # Read proximity
            proximity = self.apds.proximity
            
            # Publish raw proximity value
            proximity_msg = Int16()
            proximity_msg.data = proximity
            self.proximity_pub.publish(proximity_msg)
            
            # Check for collision
            collision_detected = proximity > self.proximity_threshold
            collision_msg = Bool()
            collision_msg.data = collision_detected
            self.collision_pub.publish(collision_msg)
            
            if collision_detected:
                self.get_logger().warn(f"Collision warning! Proximity: {proximity}")
            
            # Check if there are any gestures in the queue
            while not self.gesture_queue.empty():
                gesture = self.gesture_queue.get_nowait()
                self.get_logger().info(f"Gesture detected: {gesture}")
                
                # Publish gesture
                gesture_msg = String()
                gesture_msg.data = gesture
                self.gesture_pub.publish(gesture_msg)
                
        except Exception as e:
            self.get_logger().error(f"Proximity callback error: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = APDS9960Node()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
