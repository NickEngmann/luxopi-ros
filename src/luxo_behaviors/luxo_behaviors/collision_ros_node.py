#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool, Int16, Float32, UInt8
from luxo_interfaces.srv import ConfigureI2CSensor

class CollisionNode(Node):
    def __init__(self):
        super().__init__('collision_node')
        
        # Track startup time to prevent false positives
        self._startup_time = self.get_clock().now()
        
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
        
        # Add petting state tracking to prevent spam
        self.petting_currently_active = False
        self.last_petting_publish_time = self.get_clock().now()
        self.petting_publish_rate = 0.5  # seconds between petting messages when continuously pressed
        
        # Track last received data time for timeout detection
        self.last_proximity_time = self.get_clock().now()
        self.last_left_distance_time = self.get_clock().now()
        self.last_right_distance_time = self.get_clock().now()
        self.data_timeout = 2.0  # seconds
        
        # Current sensor values
        self.current_proximity = 0
        self.current_left_distance = float('inf')
        self.current_right_distance = float('inf')
        
        # FSR touch sensor state tracking
        self.touch_sensors = {
            'head_top': 0,
            'head_left': 0,
            'head_bottom': 0,
            'head_right': 0
        }
        self.last_touch_sensor_time = {
            'head_top': self.get_clock().now(),
            'head_left': self.get_clock().now(),
            'head_bottom': self.get_clock().now(),
            'head_right': self.get_clock().now()
        }
        
        # FSR collision state tracking
        self.fsr_collision_active = {
            'front': False,
            'left': False,
            'right': False
        }
        self.fsr_collision_start_time = {
            'front': None,
            'left': None,
            'right': None
        }
        
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
        
        # FSR touch sensor subscribers
        self.touch_head_top_sub = self.create_subscription(
            UInt8,
            '/touch_sensors/head_top',
            self.touch_head_top_callback,
            10
        )
        
        self.touch_head_left_sub = self.create_subscription(
            UInt8,
            '/touch_sensors/head_left',
            self.touch_head_left_callback,
            10
        )
        
        self.touch_head_bottom_sub = self.create_subscription(
            UInt8,
            '/touch_sensors/head_bottom',
            self.touch_head_bottom_callback,
            10
        )
        
        self.touch_head_right_sub = self.create_subscription(
            UInt8,
            '/touch_sensors/head_right',
            self.touch_head_right_callback,
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
        self.petting_event_pub = self.create_publisher(String, '/collision/petting_events', 10)
        
        # Service client for sensor configuration
        self.sensor_config_client = self.create_client(
            ConfigureI2CSensor,
            'configure_i2c_sensor'
        )
        
        # Timer to check for data timeouts and publish safe states
        self.timeout_timer = self.create_timer(1.0, self.check_data_timeout)
        
        # Timer for periodic collision evaluation
        self.collision_timer = self.create_timer(0.1, self.evaluate_collisions)
        
        # Timer to check FSR collision durations
        self.fsr_timer = self.create_timer(0.1, self.check_fsr_collisions)
        
        self.get_logger().info('Collision node initialized (using I2C Device Manager)')
        self.get_logger().info(f'Proximity threshold: {self.proximity_threshold}')
        self.get_logger().info(f'Side distance threshold: {self.side_distance_threshold} cm')
        self.get_logger().info(f'Danger threshold: {self.danger_threshold} cm')
        self.get_logger().info(f'Warning threshold: {self.warning_threshold} cm')
        
        self.get_logger().info('FSR touch sensor collision detection enabled')
        
        # Add startup delay timer to prevent initial false positives
        self.startup_delay = 5.0  # seconds
        self.startup_complete = False
        self.startup_timer = self.create_timer(
            self.startup_delay, 
            self._complete_startup
        )
        
        self.get_logger().info(f'Collision detection will be fully active after {self.startup_delay}s startup delay')
    
    def _complete_startup(self):
        """Mark startup as complete and enable full collision detection."""
        self.startup_complete = True
        if hasattr(self, 'startup_timer'):
            self.startup_timer.cancel()
        self.get_logger().info('Startup complete - full collision detection active')
    
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
    
    def touch_head_top_callback(self, msg):
        """Handle head top touch sensor data - triggers petting behavior"""
        self.touch_sensors['head_top'] = msg.data
        self.last_touch_sensor_time['head_top'] = self.get_clock().now()
        
        # Don't process petting during startup period
        if not self.startup_complete:
            self.get_logger().debug(f"Ignoring head touch during startup: {msg.data}")
            return
        
        current_time = self.get_clock().now()
        
        # Check for petting trigger (any pressure > 1)
        if msg.data > 1:
            # Only publish if we weren't already petting OR enough time has passed for rate limiting
            time_since_last_publish = (current_time - self.last_petting_publish_time).nanoseconds / 1e9
            
            if not self.petting_currently_active:
                # New petting session started
                self.get_logger().info(f"Petting started on head top (pressure: {msg.data})")
                self.petting_currently_active = True
                self.last_petting_publish_time = current_time
                
                # Publish petting trigger
                petting_msg = String()
                petting_msg.data = f"petting_started:{msg.data}"
                self.petting_event_pub.publish(petting_msg)
                
            elif time_since_last_publish > self.petting_publish_rate:
                # Continue petting session, but rate limited
                self.get_logger().debug(f"Petting continues (pressure: {msg.data})")
                self.last_petting_publish_time = current_time
                
                # Publish continued petting (for intensity updates)
                petting_msg = String()
                petting_msg.data = f"petting_started:{msg.data}"
                self.petting_event_pub.publish(petting_msg)
        else:
            # Petting stopped
            if self.petting_currently_active:
                self.get_logger().info("Petting stopped")
                self.petting_currently_active = False
                
                petting_msg = String()
                petting_msg.data = "petting_stopped:0"
                self.petting_event_pub.publish(petting_msg)
    
    def touch_head_left_callback(self, msg):
        """Handle head left touch sensor data"""
        self.touch_sensors['head_left'] = msg.data
        self.last_touch_sensor_time['head_left'] = self.get_clock().now()
        self._process_touch_collision('head_left', msg.data)
    
    def touch_head_bottom_callback(self, msg):
        """Handle head bottom touch sensor data"""
        self.touch_sensors['head_bottom'] = msg.data
        self.last_touch_sensor_time['head_bottom'] = self.get_clock().now()
        self._process_touch_collision('head_bottom', msg.data)
    
    def touch_head_right_callback(self, msg):
        """Handle head right touch sensor data"""
        self.touch_sensors['head_right'] = msg.data
        self.last_touch_sensor_time['head_right'] = self.get_clock().now()
        self._process_touch_collision('head_right', msg.data)
    
    def _process_touch_collision(self, touch_location, pressure_state):
        """Process touch sensor data and trigger appropriate collision responses"""
        # Check for simultaneous left and right touches (likely false positive)
        if touch_location in ['head_left', 'head_right']:
            if self.touch_sensors['head_left'] > 1 and self.touch_sensors['head_right'] > 1:
                self.get_logger().info(
                    f"Simultaneous left ({self.touch_sensors['head_left']}) and "
                    f"right ({self.touch_sensors['head_right']}) touch detected - "
                    f"ignoring as potential false positive"
                )
                return
        
        # Determine if this is a collision (any pressure state > 1)
        is_collision = pressure_state > 1
        
        # Map touch locations to collision directions
        collision_direction = None
        if touch_location == 'head_left':
            collision_direction = 'left'
        elif touch_location == 'head_right':
            collision_direction = 'right'
        elif touch_location == 'head_bottom':
            collision_direction = 'front'
        else:
            return  # Unknown touch location
        
        current_time = self.get_clock().now()
        
        if is_collision:
            # New collision detected
            if not self.fsr_collision_active[collision_direction]:
                self.fsr_collision_active[collision_direction] = True
                self.fsr_collision_start_time[collision_direction] = current_time
                
                self.get_logger().info(f"FSR touch collision detected: {touch_location} (pressure: {pressure_state}) -> {collision_direction} collision")
                
                # Treat all FSR touches as severe collisions
                severity = 'danger'
                
                # Update collision status
                collision_msg = Bool()
                collision_msg.data = True
                
                # Publish collision warnings
                if collision_direction == 'left':
                    self.left_collision_pub.publish(collision_msg)
                elif collision_direction == 'right':
                    self.right_collision_pub.publish(collision_msg)
                elif collision_direction == 'front':
                    self.collision_pub.publish(collision_msg)
                
                # Publish severity
                severity_msg = String()
                severity_msg.data = severity
                
                if collision_direction == 'left':
                    self.left_severity_pub.publish(severity_msg)
                elif collision_direction == 'right':
                    self.right_severity_pub.publish(severity_msg)
                elif collision_direction == 'front':
                    self.front_severity_pub.publish(severity_msg)
                
                # Publish detailed collision information with simulated distance
                # Use a very small distance (1cm) to indicate immediate contact
                simulated_distance = 1.0  # cm - represents direct contact
                details_msg = String()
                details_msg.data = f"{collision_direction}:{simulated_distance}:{severity}"
                self.collision_details_pub.publish(details_msg)
                
                # Also publish distance for hardware interface consumption
                distance_msg = Float32()
                distance_msg.data = simulated_distance
                
                if collision_direction == 'left':
                    self.left_distance_pub.publish(distance_msg)
                elif collision_direction == 'right':
                    self.right_distance_pub.publish(distance_msg)
                # For front collisions, we use proximity sensor, not distance
                
        else:
            # Touch released - clear collision if it was from this sensor
            if self.fsr_collision_active[collision_direction]:
                duration = (current_time - self.fsr_collision_start_time[collision_direction]).nanoseconds / 1e9
                self.get_logger().info(f"FSR collision cleared for {collision_direction} after {duration:.2f}s")
                
                self.fsr_collision_active[collision_direction] = False
                self.fsr_collision_start_time[collision_direction] = None
                
                # Clear collision status
                collision_msg = Bool()
                collision_msg.data = False
                
                if collision_direction == 'left':
                    self.left_collision_pub.publish(collision_msg)
                elif collision_direction == 'right':
                    self.right_collision_pub.publish(collision_msg)
                elif collision_direction == 'front':
                    self.collision_pub.publish(collision_msg)
                
                # Clear severity
                severity_msg = String()
                severity_msg.data = "safe"
                
                if collision_direction == 'left':
                    self.left_severity_pub.publish(severity_msg)
                elif collision_direction == 'right':
                    self.right_severity_pub.publish(severity_msg)
                elif collision_direction == 'front':
                    self.front_severity_pub.publish(severity_msg)
    
    def check_fsr_collisions(self):
        """Check FSR collision durations and handle timeouts"""
        current_time = self.get_clock().now()
        
        for direction in ['front', 'left', 'right']:
            if self.fsr_collision_active[direction]:
                # Check if collision has been active too long
                if self.fsr_collision_start_time[direction]:
                    duration = (current_time - self.fsr_collision_start_time[direction]).nanoseconds / 1e9
                    
                    # Auto-clear FSR collisions after 2 seconds to prevent sticking
                    if duration > 0.5:
                        self.get_logger().warn(f"FSR collision for {direction} auto-cleared after {duration:.2f}s (timeout)")
                        
                        self.fsr_collision_active[direction] = False
                        self.fsr_collision_start_time[direction] = None
                        
                        # Clear collision status
                        collision_msg = Bool()
                        collision_msg.data = False
                        
                        if direction == 'left':
                            self.left_collision_pub.publish(collision_msg)
                        elif direction == 'right':
                            self.right_collision_pub.publish(collision_msg)
                        elif direction == 'front':
                            self.collision_pub.publish(collision_msg)
                        
                        # Clear severity
                        severity_msg = String()
                        severity_msg.data = "safe"
                        
                        if direction == 'left':
                            self.left_severity_pub.publish(severity_msg)
                        elif direction == 'right':
                            self.right_severity_pub.publish(severity_msg)
                        elif direction == 'front':
                            self.front_severity_pub.publish(severity_msg)
    
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
        
        # Check FSR touch sensor timeouts
        for sensor_name, last_time in self.last_touch_sensor_time.items():
            time_since_data = (current_time - last_time).nanoseconds / 1e9
            if time_since_data > self.data_timeout:
                self.get_logger().debug(f"FSR touch sensor {sensor_name} data timeout - assuming no touch")
                # Reset the sensor value to 0 (no touch)
                self.touch_sensors[sensor_name] = 0
    
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