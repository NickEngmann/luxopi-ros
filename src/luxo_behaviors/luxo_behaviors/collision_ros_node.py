#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool, Int16, Float32
import board
from adafruit_apds9960.apds9960 import APDS9960
import adafruit_vl53l4cd
import time
import threading
import queue

class CollisionNode(Node):
    def __init__(self):
        super().__init__('collision_node')
        
        # Initialize I2C
        self.i2c = board.I2C()  # uses board.SCL and board.SDA
        
        # Error handling variables
        self.error_count = 0
        self.max_errors = 5
        self.last_error_time = time.time()
        self.recovery_active = False
        self.gesture_thread_running = True
        
        # Initialize sensors
        self.initialize_sensors()
        
        # Set the proximity threshold for collision detection
        self.declare_parameter('proximity_threshold', 5)
        self.proximity_threshold = self.get_parameter('proximity_threshold').value
        
        # Set the distance threshold for side collision detection (in cm)
        self.declare_parameter('side_distance_threshold', 8.0)
        self.side_distance_threshold = self.get_parameter('side_distance_threshold').value
        
        # Define severity thresholds (in cm)
        self.declare_parameter('danger_threshold', 5.0)
        self.declare_parameter('warning_threshold', 15.0)
        self.danger_threshold = self.get_parameter('danger_threshold').value
        self.warning_threshold = self.get_parameter('warning_threshold').value
        
        # Previous distance readings for consecutive detection
        self.prev_left_distance = float('inf')
        self.prev_right_distance = float('inf')
        
        # Previous proximity reading for consecutive detection
        self.prev_proximity = 0
        
        # Publishers for APDS9960
        self.collision_pub = self.create_publisher(Bool, '/head_collision_warning', 10)
        self.gesture_pub = self.create_publisher(String, '/gestures', 10)
        self.proximity_pub = self.create_publisher(Int16, '/proximity', 10)
        
        # Publishers for VL53L4CD
        self.left_collision_pub = self.create_publisher(Bool, '/left_collision_warning', 10)
        self.right_collision_pub = self.create_publisher(Bool, '/right_collision_warning', 10)
        self.left_distance_pub = self.create_publisher(Float32, '/left_distance', 10)
        self.right_distance_pub = self.create_publisher(Float32, '/right_distance', 10)
        
        # Enhanced collision detail publishers
        self.collision_details_pub = self.create_publisher(String, '/collision_details', 10)
        self.front_severity_pub = self.create_publisher(String, '/front_collision_severity', 10)
        self.left_severity_pub = self.create_publisher(String, '/left_collision_severity', 10)
        self.right_severity_pub = self.create_publisher(String, '/right_collision_severity', 10)
        
        # Create a queue for thread communication
        self.gesture_queue = queue.Queue()
        
        # Start gesture detection in its own thread
        self.gesture_thread = threading.Thread(target=self.gesture_detection, daemon=True)
        self.gesture_thread.start()
        
        # Create timer for proximity readings
        self.timer = self.create_timer(0.2, self.proximity_callback)
        
        # Create timer for distance readings
        self.distance_timer = self.create_timer(0.2, self.distance_callback)
        
        # Create recovery timer that checks every 5 seconds if recovery is needed
        self.recovery_timer = self.create_timer(5.0, self.check_and_recover)
        
        self.get_logger().info('Collision node initialized')
        self.get_logger().info(f'Proximity threshold set to: {self.proximity_threshold}')
        self.get_logger().info(f'Side distance threshold set to: {self.side_distance_threshold} cm')
        self.get_logger().info(f'Danger threshold set to: {self.danger_threshold} cm')
        self.get_logger().info(f'Warning threshold set to: {self.warning_threshold} cm')

    def initialize_sensors(self):
        """Initialize or reinitialize all sensors"""
        try:
            # Initialize APDS9960 sensor
            self.apds = APDS9960(self.i2c)
            self.apds.enable_proximity = True
            self.apds.proximity_gain = 1
            self.apds.enable_gesture = True
            
            # Initialize VL53L4CD sensors
            self.vl53_right = adafruit_vl53l4cd.VL53L4CD(self.i2c, 0x59)  # Left sensor with custom address
            self.vl53_left = adafruit_vl53l4cd.VL53L4CD(self.i2c)  # Right sensor with default address
            
            # Configure VL53L4CD sensors
            for vl53 in (self.vl53_left, self.vl53_right):
                vl53.inter_measurement = 0
                vl53.timing_budget = 100
                vl53.start_ranging()
                
            self.get_logger().info("All sensors initialized successfully")
            self.error_count = 0
            self.recovery_active = False
            return True
            
        except Exception as e:
            self.get_logger().error(f"Failed to initialize sensors: {e}")
            return False

    def check_and_recover(self):
        """Periodically check if sensors need recovery"""
        try:
            # If we've had errors and it's been more than 10 seconds since the last error
            if self.error_count > 0 and not self.recovery_active:
                self.get_logger().warn(f"Starting sensor recovery after {self.error_count} errors")
                self.recovery_active = True
                
                # Attempt to reinitialize all sensors
                success = self.initialize_sensors()
                
                if success:
                    self.get_logger().info("Sensor recovery successful")
                    # Restart the gesture thread if it failed
                    if not self.gesture_thread.is_alive():
                        self.get_logger().info("Restarting gesture thread")
                        self.gesture_thread_running = True
                        self.gesture_thread = threading.Thread(target=self.gesture_detection, daemon=True)
                        self.gesture_thread.start()
                else:
                    self.get_logger().error("Sensor recovery failed, will retry later")
                
                self.recovery_active = False
                
        except Exception as e:
            self.get_logger().error(f"Recovery mechanism error: {e}")
            self.recovery_active = False

    def determine_severity(self, distance):
        """Determine collision severity based on distance"""
        if distance < self.danger_threshold:
            return "danger"
        elif distance < self.warning_threshold:
            return "warning"
        else:
            return "safe"

    def gesture_detection(self):
        """Gesture detection function running in a separate thread"""
        consecutive_errors = 0
        max_consecutive_errors = 3
        recovery_delay = 1.0  # seconds
        
        while self.gesture_thread_running:
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
                
                # Reset consecutive errors on success
                consecutive_errors = 0
                time.sleep(0.01)  # Small sleep to prevent CPU overload
                
            except Exception as e:
                consecutive_errors += 1
                self.error_count += 1
                self.last_error_time = time.time()
                self.get_logger().error(f"Gesture thread error: {e}")
                
                # Try to recover if multiple consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    self.get_logger().warn(f"Too many consecutive errors ({consecutive_errors}), attempting sensor recovery")
                    try:
                        # Try to reinitialize just the APDS9960
                        self.apds = APDS9960(self.i2c)
                        self.apds.enable_proximity = True
                        self.apds.proximity_gain = 1
                        self.apds.enable_gesture = True
                        self.get_logger().info("APDS9960 reinitialized successfully")
                        consecutive_errors = 0
                    except Exception as reinit_error:
                        self.get_logger().error(f"Failed to reinitialize APDS9960: {reinit_error}")
                        
                time.sleep(recovery_delay)  # Longer sleep after error

    def proximity_callback(self):
        """Timer callback for proximity readings"""
        try:
            # Read proximity
            proximity = self.apds.proximity
            
            # Publish raw proximity value
            proximity_msg = Int16()
            proximity_msg.data = proximity
            self.proximity_pub.publish(proximity_msg)
            
            # Check for collision - require two consecutive readings above threshold
            collision_detected = proximity > self.proximity_threshold and self.prev_proximity > self.proximity_threshold
            collision_msg = Bool()
            collision_msg.data = collision_detected
            self.collision_pub.publish(collision_msg)
            
            # Determine severity for front collision
            # For APDS9960, higher proximity value means closer object
            if collision_detected:
                severity = "danger" if proximity > self.proximity_threshold * 2 else "warning"
                self.get_logger().warn(f"Head Collision warning! Proximity: {proximity}, Severity: {severity}")
                
                # Publish detailed collision information
                severity_msg = String()
                severity_msg.data = severity
                self.front_severity_pub.publish(severity_msg)
                
                details_msg = String()
                details_msg.data = f"front:{proximity}:{severity}"
                self.collision_details_pub.publish(details_msg)
            else:
                severity_msg = String()
                severity_msg.data = "safe"
                self.front_severity_pub.publish(severity_msg)
            
            # Save current proximity for next comparison
            self.prev_proximity = proximity
            
            # Check if there are any gestures in the queue
            while not self.gesture_queue.empty():
                gesture = self.gesture_queue.get_nowait()
                self.get_logger().info(f"Gesture detected: {gesture}")
                
                # Publish gesture
                gesture_msg = String()
                gesture_msg.data = gesture
                self.gesture_pub.publish(gesture_msg)
                
        except Exception as e:
            self.error_count += 1
            self.last_error_time = time.time()
            self.get_logger().error(f"Proximity callback error: {e}")
            
            # Publish safe states when in error
            try:
                severity_msg = String()
                severity_msg.data = "safe"
                self.front_severity_pub.publish(severity_msg)
                
                collision_msg = Bool()
                collision_msg.data = False
                self.collision_pub.publish(collision_msg)
            except:
                pass

    def distance_callback(self):
        """Timer callback for VL53L4CD distance readings"""
        try:
            left_ready = False
            right_ready = False
            
            try:
                # Check if sensors have data ready
                if self.vl53_left.data_ready:
                    left_ready = True
                    self.vl53_left.clear_interrupt()
            except Exception as e:
                self.get_logger().error(f"Left sensor read error: {e}")
                self.error_count += 1
                self.last_error_time = time.time()
                
            try:   
                if self.vl53_right.data_ready:
                    right_ready = True
                    self.vl53_right.clear_interrupt()
            except Exception as e:
                self.get_logger().error(f"Right sensor read error: {e}")
                self.error_count += 1
                self.last_error_time = time.time()
                
            # Process left sensor data if ready
            if left_ready:
                try:
                    left_distance = self.vl53_left.distance
                    
                    # Ignore readings below 1cm (treat as invalid)
                    if left_distance < 1.0:
                        self.get_logger().debug(f"Ignoring invalid left distance reading: {left_distance:.1f} cm")
                        return
                    
                    # Publish raw distance value
                    left_msg = Float32()
                    left_msg.data = left_distance
                    self.left_distance_pub.publish(left_msg)
                    
                    # Determine severity level
                    severity = self.determine_severity(left_distance)
                    
                    # Publish severity
                    severity_msg = String()
                    severity_msg.data = severity
                    self.left_severity_pub.publish(severity_msg)
                    
                    # Check for collision (two consecutive readings below threshold)
                    if left_distance < self.side_distance_threshold and self.prev_left_distance < self.side_distance_threshold:
                        collision_msg = Bool()
                        collision_msg.data = True
                        self.left_collision_pub.publish(collision_msg)
                        self.get_logger().warn(f"Left collision warning! Distance: {left_distance:.1f} cm, Severity: {severity}")
                        
                        # Publish detailed collision information
                        details_msg = String()
                        details_msg.data = f"left:{left_distance:.1f}:{severity}"
                        self.collision_details_pub.publish(details_msg)
                    else:
                        # Ensure we publish False when not in collision state
                        collision_msg = Bool()
                        collision_msg.data = False
                        self.left_collision_pub.publish(collision_msg)
                        self.get_logger().debug(f"Left collision debug --- Distance: {left_distance:.1f} cm, Severity: {severity}")
                        
                    # Save current reading for next comparison
                    self.prev_left_distance = left_distance
                except Exception as e:
                    self.get_logger().error(f"Left distance processing error: {e}")
                    self.error_count += 1
                    self.last_error_time = time.time()
                
            # Process right sensor data if ready
            if right_ready:
                try:
                    right_distance = self.vl53_right.distance
                    
                    # Ignore readings below 1cm (treat as invalid)
                    if right_distance < 1.0:
                        self.get_logger().debug(f"Ignoring invalid right distance reading: {right_distance:.1f} cm")
                        return
                    
                    # Publish raw distance value
                    right_msg = Float32()
                    right_msg.data = right_distance
                    self.right_distance_pub.publish(right_msg)
                    
                    # Determine severity level
                    severity = self.determine_severity(right_distance)
                    
                    # Publish severity
                    severity_msg = String()
                    severity_msg.data = severity
                    self.right_severity_pub.publish(severity_msg)
                    
                    # Check for collision (two consecutive readings below threshold)
                    if right_distance < self.side_distance_threshold and self.prev_right_distance < self.side_distance_threshold:
                        collision_msg = Bool()
                        collision_msg.data = True
                        self.right_collision_pub.publish(collision_msg)
                        self.get_logger().warn(f"Right collision warning! Distance: {right_distance:.1f} cm, Severity: {severity}")
                        
                        # Publish detailed collision information
                        details_msg = String()
                        details_msg.data = f"right:{right_distance:.1f}:{severity}"
                        self.collision_details_pub.publish(details_msg)
                    else:
                        # Ensure we publish False when not in collision state
                        collision_msg = Bool()
                        collision_msg.data = False
                        self.right_collision_pub.publish(collision_msg)
                        self.get_logger().debug(f"Right collision debug --- Distance: {right_distance:.1f} cm, Severity: {severity}")
                        
                    # Save current reading for next comparison
                    self.prev_right_distance = right_distance
                except Exception as e:
                    self.get_logger().error(f"Right distance processing error: {e}")
                    self.error_count += 1
                    self.last_error_time = time.time()
                
        except Exception as e:
            self.error_count += 1
            self.last_error_time = time.time()
            self.get_logger().error(f"Distance callback error: {e}")
            
            # Publish safe states when in error
            try:
                for severity_pub in [self.left_severity_pub, self.right_severity_pub]:
                    severity_msg = String()
                    severity_msg.data = "safe"
                    severity_pub.publish(severity_msg)
                
                for collision_pub in [self.left_collision_pub, self.right_collision_pub]:
                    collision_msg = Bool()
                    collision_msg.data = False
                    collision_pub.publish(collision_msg)
            except:
                pass

    def destroy_node(self):
        self.gesture_thread_running = False
        if self.gesture_thread.is_alive():
            self.gesture_thread.join(timeout=1.0)
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = CollisionNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
