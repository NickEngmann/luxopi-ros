#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool, Int16, Float32
from luxo_interfaces.srv import ConfigureI2CSensor

class CollisionNode(Node):
    def __init__(self):
        super().__init__('collision_node')
        
        # Set the proximity threshold for collision detection
        self.declare_parameter('proximity_threshold', 15)
        self.proximity_threshold = self.get_parameter('proximity_threshold').value
        
        # Set the distance threshold for side collision detection (in cm)
        self.declare_parameter('side_distance_threshold', 8.0)
        self.side_distance_threshold = self.get_parameter('side_distance_threshold').value
        
        # Define severity thresholds (in cm)
        self.declare_parameter('danger_threshold', 5.0)
        self.declare_parameter('warning_threshold', 15.0)
        self.danger_threshold = self.get_parameter('danger_threshold').value
        self.warning_threshold = self.get_parameter('warning_threshold').value
        
        # Parameter to enable/disable gesture passthrough
        self.declare_parameter('enable_gestures', False)
        self.enable_gestures = self.get_parameter('enable_gestures').value
        
        # Previous sensor readings for consecutive detection
        self.prev_left_distance = float('inf')
        self.prev_right_distance = float('inf')
        self.prev_proximity = 0
        
        # Track last received data time for timeout detection
        self.last_proximity_time = self.get_clock().now()
        self.last_left_distance_time = self.get_clock().now()
        self.last_right_distance_time = self.get_clock().now()
        self.data_timeout = 2.0  # seconds
        
        # Current sensor values
        self.current_proximity = 0
        self.current_left_distance = float('inf')
        self.current_right_distance = float('inf')
        
        # Subscribers to I2C device manager topics
        self.proximity_sub = self.create_subscription(
            Int16,
            '/i2c/apds9960/proximity',
            self.proximity_data_callback,
            10
        )
        
        self.left_distance_sub = self.create_subscription(
            Float32,
            '/i2c/vl53_left/distance',
            self.left_distance_callback,
            10
        )
        
        self.right_distance_sub = self.create_subscription(
            Float32,
            '/i2c/vl53_right/distance',
            self.right_distance_callback,
            10
        )
        
        # Optional gesture subscriber
        if self.enable_gestures:
            self.gesture_sub = self.create_subscription(
                String,
                '/i2c/apds9960/gesture',
                self.gesture_callback,
                10
            )
            self.gesture_pub = self.create_publisher(String, '/gestures', 10)
            self.get_logger().info('Gesture passthrough enabled')
        
        # Subscribe to sensor health for monitoring
        self.sensor_health_sub = self.create_subscription(
            String,
            '/i2c/sensor_health',
            self.sensor_health_callback,
            10
        )
        
        # Publishers for collision detection results
        self.collision_pub = self.create_publisher(Bool, '/head_collision_warning', 10)
        self.proximity_pub = self.create_publisher(Int16, '/proximity', 10)
        
        self.left_collision_pub = self.create_publisher(Bool, '/left_collision_warning', 10)
        self.right_collision_pub = self.create_publisher(Bool, '/right_collision_warning', 10)
        self.left_distance_pub = self.create_publisher(Float32, '/left_distance', 10)
        self.right_distance_pub = self.create_publisher(Float32, '/right_distance', 10)
        
        # Enhanced collision detail publishers
        self.collision_details_pub = self.create_publisher(String, '/collision_details', 10)
        self.front_severity_pub = self.create_publisher(String, '/front_collision_severity', 10)
        self.left_severity_pub = self.create_publisher(String, '/left_collision_severity', 10)
        self.right_severity_pub = self.create_publisher(String, '/right_collision_severity', 10)
        
        # Service client for sensor configuration
        self.sensor_config_client = self.create_client(
            ConfigureI2CSensor,
            'configure_i2c_sensor'
        )
        
        # Timer to check for data timeouts and publish safe states
        self.timeout_timer = self.create_timer(1.0, self.check_data_timeout)
        
        # Timer for periodic collision evaluation
        self.collision_timer = self.create_timer(0.1, self.evaluate_collisions)
        
        self.get_logger().info('Collision node initialized (using I2C Device Manager)')
        self.get_logger().info(f'Proximity threshold: {self.proximity_threshold}')
        self.get_logger().info(f'Side distance threshold: {self.side_distance_threshold} cm')
        self.get_logger().info(f'Danger threshold: {self.danger_threshold} cm')
        self.get_logger().info(f'Warning threshold: {self.warning_threshold} cm')
    
    def proximity_data_callback(self, msg):
        """Handle proximity data from I2C manager"""
        self.current_proximity = msg.data
        self.last_proximity_time = self.get_clock().now()
        
        # Republish raw proximity value
        self.proximity_pub.publish(msg)
    
    def left_distance_callback(self, msg):
        """Handle left distance data from I2C manager"""
        self.current_left_distance = msg.data
        self.last_left_distance_time = self.get_clock().now()
        
        # Republish raw distance value
        self.left_distance_pub.publish(msg)
    
    def right_distance_callback(self, msg):
        """Handle right distance data from I2C manager"""
        self.current_right_distance = msg.data
        self.last_right_distance_time = self.get_clock().now()
        
        # Republish raw distance value
        self.right_distance_pub.publish(msg)
    
    def gesture_callback(self, msg):
        """Pass through gesture data if enabled"""
        if self.enable_gestures:
            self.get_logger().info(f"Gesture detected: {msg.data}")
            self.gesture_pub.publish(msg)
    
    def sensor_health_callback(self, msg):
        """Monitor sensor health status"""
        # Parse health message format: "sensor_name:status:details"
        parts = msg.data.split(':')
        if len(parts) >= 2:
            sensor_name = parts[0]
            status = parts[1]
            details = parts[2] if len(parts) > 2 else ""
            
            if status == "error":
                self.get_logger().warn(f"Sensor {sensor_name} error: {details}")
            elif status == "recovered":
                self.get_logger().info(f"Sensor {sensor_name} recovered")
    
    def determine_severity(self, distance):
        """Determine collision severity based on distance"""
        if distance < self.danger_threshold:
            return "danger"
        elif distance < self.warning_threshold:
            return "warning"
        else:
            return "safe"
    
    def evaluate_collisions(self):
        """Evaluate collision states based on current sensor data"""
        # Front/head collision detection
        collision_detected = (self.current_proximity > self.proximity_threshold and 
                            self.prev_proximity > self.proximity_threshold)
        
        collision_msg = Bool()
        collision_msg.data = collision_detected
        self.collision_pub.publish(collision_msg)
        
        # Determine severity for front collision
        if collision_detected:
            severity = "danger" if self.current_proximity > self.proximity_threshold * 2 else "warning"
            self.get_logger().debug(f"Head Collision warning! Proximity: {self.current_proximity}, Severity: {severity}")
            
            # Publish severity
            severity_msg = String()
            severity_msg.data = severity
            self.front_severity_pub.publish(severity_msg)
            
            # Publish detailed collision information
            details_msg = String()
            details_msg.data = f"front:{self.current_proximity}:{severity}"
            self.collision_details_pub.publish(details_msg)
        else:
            severity_msg = String()
            severity_msg.data = "safe"
            self.front_severity_pub.publish(severity_msg)
        
        self.prev_proximity = self.current_proximity
        
        # Left collision detection
        if self.current_left_distance < float('inf'):
            # Ignore invalid readings below 1cm
            if self.current_left_distance >= 1.0:
                severity = self.determine_severity(self.current_left_distance)
                
                # Publish severity
                severity_msg = String()
                severity_msg.data = severity
                self.left_severity_pub.publish(severity_msg)
                
                # Check for collision (two consecutive readings below threshold)
                if (self.current_left_distance < self.side_distance_threshold and 
                    self.prev_left_distance < self.side_distance_threshold):
                    
                    collision_msg = Bool()
                    collision_msg.data = True
                    self.left_collision_pub.publish(collision_msg)
                    self.get_logger().debug(f"Left collision warning! Distance: {self.current_left_distance:.1f} cm, Severity: {severity}")
                    
                    # Publish detailed collision information
                    details_msg = String()
                    details_msg.data = f"left:{self.current_left_distance:.1f}:{severity}"
                    self.collision_details_pub.publish(details_msg)
                else:
                    collision_msg = Bool()
                    collision_msg.data = False
                    self.left_collision_pub.publish(collision_msg)
                
                self.prev_left_distance = self.current_left_distance
        
        # Right collision detection
        if self.current_right_distance < float('inf'):
            # Ignore invalid readings below 1cm
            if self.current_right_distance >= 1.0:
                severity = self.determine_severity(self.current_right_distance)
                
                # Publish severity
                severity_msg = String()
                severity_msg.data = severity
                self.right_severity_pub.publish(severity_msg)
                
                # Check for collision (two consecutive readings below threshold)
                if (self.current_right_distance < self.side_distance_threshold and 
                    self.prev_right_distance < self.side_distance_threshold):
                    
                    collision_msg = Bool()
                    collision_msg.data = True
                    self.right_collision_pub.publish(collision_msg)
                    self.get_logger().debug(f"Right collision warning! Distance: {self.current_right_distance:.1f} cm, Severity: {severity}")
                    
                    # Publish detailed collision information
                    details_msg = String()
                    details_msg.data = f"right:{self.current_right_distance:.1f}:{severity}"
                    self.collision_details_pub.publish(details_msg)
                else:
                    collision_msg = Bool()
                    collision_msg.data = False
                    self.right_collision_pub.publish(collision_msg)
                
                self.prev_right_distance = self.current_right_distance
    
    def check_data_timeout(self):
        """Check if sensor data has timed out and publish safe states"""
        current_time = self.get_clock().now()
        
        # Check proximity timeout
        if (current_time - self.last_proximity_time).nanoseconds / 1e9 > self.data_timeout:
            self.get_logger().debug("Proximity data timeout - publishing safe state")
            
            # Publish safe states
            severity_msg = String()
            severity_msg.data = "safe"
            self.front_severity_pub.publish(severity_msg)
            
            collision_msg = Bool()
            collision_msg.data = False
            self.collision_pub.publish(collision_msg)
            
            # Request sensor reinitialization if available
            self.request_sensor_reinit('apds9960')
        
        # Check left distance timeout
        if (current_time - self.last_left_distance_time).nanoseconds / 1e9 > self.data_timeout:
            self.get_logger().debug("Left distance data timeout - publishing safe state")
            
            severity_msg = String()
            severity_msg.data = "safe"
            self.left_severity_pub.publish(severity_msg)
            
            collision_msg = Bool()
            collision_msg.data = False
            self.left_collision_pub.publish(collision_msg)
            
            self.request_sensor_reinit('vl53_left')
        
        # Check right distance timeout
        if (current_time - self.last_right_distance_time).nanoseconds / 1e9 > self.data_timeout:
            self.get_logger().debug("Right distance data timeout - publishing safe state")
            
            severity_msg = String()
            severity_msg.data = "safe"
            self.right_severity_pub.publish(severity_msg)
            
            collision_msg = Bool()
            collision_msg.data = False
            self.right_collision_pub.publish(collision_msg)
            
            self.request_sensor_reinit('vl53_right')
    
    def request_sensor_reinit(self, sensor_name):
        """Request sensor reinitialization via service"""
        if not self.sensor_config_client.wait_for_service(timeout_sec=1.0):
            return
        
        request = ConfigureI2CSensor.Request()
        request.sensor_name = sensor_name
        request.config_type = "reinitialize"
        request.config_value = 1.0
        
        future = self.sensor_config_client.call_async(request)
        future.add_done_callback(
            lambda f: self.get_logger().debug(f"Reinit request for {sensor_name} completed")
        )

def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = CollisionNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error in collision node: {e}")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()