#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool, Int16, Float32, UInt8
from luxo_interfaces.srv import ConfigureI2CSensor
from collections import deque

class CollisionNode(Node):
    def __init__(self):
        super().__init__('collision_node')
        
        # Track startup time to prevent false positives
        self._startup_time = self.get_clock().now()
        
        # Set the proximity threshold for collision detection
        self.declare_parameter('proximity_threshold', 3)  # Changed from 15 to 3 for more sensitive detection
        self.proximity_threshold = self.get_parameter('proximity_threshold').value
        
        # Set the distance threshold for side collision detection (in cm)
        self.declare_parameter('side_distance_threshold', 7.0)  # Default 7.0 cm (was 8.0)
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

        # VL53L4CD stability tracking - require 3 stable readings (reduced from 5 for faster response)
        self.left_distance_history = deque(maxlen=3)
        self.right_distance_history = deque(maxlen=3)
        self.vl53_stability_threshold = 1.0  # cm - readings must be within 0.7cm of each other (increased from 0.5 for easier triggering)
        self.vl53_min_valid_distance = 1.6   # cm - minimum distance to consider valid
        
        # Add petting state tracking to prevent spam
        self.petting_currently_active = False
        self.last_petting_publish_time = self.get_clock().now()
        self.petting_publish_rate = 0.75  # seconds between petting messages when continuously pressed
        
        # Track last received data time for timeout detection
        self.last_proximity_time = self.get_clock().now()
        self.last_left_distance_time = self.get_clock().now()
        self.last_right_distance_time = self.get_clock().now()
        self.data_timeout = 2.0  # seconds
        
        # Current sensor values
        self.current_proximity = 0
        self.current_left_distance = float('inf')
        self.current_right_distance = float('inf')
        
        # MPR121 capacitive touch sensor state tracking
        self.touch_sensors = {
            'bottom': False,       # Channel 0 - collision
            'front_right': False,  # Channel 1 - collision
            'front_left': False,   # Channel 2 - collision
            'top_front': False,    # Channel 3 - petting
            # Note: antenna (Channel 4) removed - now used for mute toggle
        }
        self.last_touch_sensor_time = {
            'bottom': self.get_clock().now(),
            'front_right': self.get_clock().now(),
            'front_left': self.get_clock().now(),
            'top_front': self.get_clock().now(),
            # Note: antenna removed - now used for mute toggle
        }

        # MPR121 collision state tracking (channels 0-2)
        self.mpr121_collision_active = {
            'bottom': False,
            'front_right': False,
            'front_left': False
        }
        self.mpr121_collision_start_time = {
            'bottom': None,
            'front_right': None,
            'front_left': None
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
        
        # MPR121 Capacitive touch sensor subscribers
        # Channels 0-2: Collision detection
        self.mpr121_ch0_sub = self.create_subscription(
            Bool,
            '/touch_sensors/bottom',
            self.mpr121_bottom_callback,
            10
        )

        self.mpr121_ch1_sub = self.create_subscription(
            Bool,
            '/touch_sensors/front_right',
            self.mpr121_front_right_callback,
            10
        )

        self.mpr121_ch2_sub = self.create_subscription(
            Bool,
            '/touch_sensors/front_left',
            self.mpr121_front_left_callback,
            10
        )

        # Channels 3-4: Petting detection
        self.mpr121_ch3_sub = self.create_subscription(
            Bool,
            '/touch_sensors/top_front',
            self.mpr121_top_front_callback,
            10
        )

        # Note: Channel 4 (antenna) removed from petting - now used for mute toggle in voice_assistant_node

        # MPR121 Release event subscribers (for petting detection)
        # Release events fire immediately (no consecutive requirement)
        self.mpr121_ch3_release_sub = self.create_subscription(
            Bool,
            '/touch_sensors/top_front/released',
            self.mpr121_top_front_release_callback,
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

        # Timer to check MPR121 collision durations
        self.mpr121_timer = self.create_timer(0.1, self.check_mpr121_collisions)

        self.get_logger().info('Collision node initialized (using I2C Device Manager)')
        self.get_logger().info(f'Proximity threshold: {self.proximity_threshold}')
        self.get_logger().info(f'Side distance threshold: {self.side_distance_threshold} cm')
        self.get_logger().info(f'Danger threshold: {self.danger_threshold} cm')
        self.get_logger().info(f'Warning threshold: {self.warning_threshold} cm')

        self.get_logger().info('MPR121 capacitive touch sensor collision/petting detection enabled')
        
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

    def is_stable_reading(self, history):
        """
        Check if VL53L4CD readings are stable.
        Requires:
        - 3 consecutive readings (reduced from 5 for faster response)
        - All within 1.0cm of each other (even if decreasing)
        - Minimum value >= 1.6cm

        Returns: (is_stable, min_value)
        """
        # Need exactly 5 readings
        if len(history) < 5:
            return False, None

        readings = list(history)

        # Check minimum value threshold
        min_value = min(readings)
        if min_value < self.vl53_min_valid_distance:
            return False, None

        # Check stability - all readings within 0.5cm of each other
        max_value = max(readings)
        range_spread = max_value - min_value

        if range_spread <= self.vl53_stability_threshold:
            return True, min_value

        return False, None

    def evaluate_collisions(self):
        """Evaluate collision states based on current sensor data"""
        # Front/head collision detection
        collision_detected = (self.current_proximity >= self.proximity_threshold and
                            self.prev_proximity >= self.proximity_threshold)

        collision_msg = Bool()
        collision_msg.data = collision_detected
        self.collision_pub.publish(collision_msg)

        # Determine severity for front collision based on new scale (0-10+)
        if collision_detected:
            # New severity levels: 3-5 = warning, 6-9 = caution, 10+ = danger
            if self.current_proximity >= 10:
                severity = "danger"  # Right in front of us
            elif self.current_proximity >= 6:
                severity = "caution"  # Close proximity
            else:
                severity = "warning"  # Something detected (3-5)
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
        
        # Left collision detection with stability check
        if self.current_left_distance < float('inf'):
            # Add reading to history (only if >= minimum valid distance)
            if self.current_left_distance >= self.vl53_min_valid_distance:
                self.left_distance_history.append(self.current_left_distance)

                # Check for stable readings
                is_stable, stable_distance = self.is_stable_reading(self.left_distance_history)

                if is_stable:
                    severity = self.determine_severity(stable_distance)

                    # Publish severity
                    severity_msg = String()
                    severity_msg.data = severity
                    self.left_severity_pub.publish(severity_msg)

                    # Check for collision if stable readings are below threshold
                    if stable_distance < self.side_distance_threshold:
                        collision_msg = Bool()
                        collision_msg.data = True
                        self.left_collision_pub.publish(collision_msg)
                        self.get_logger().debug(f"Left collision warning! Stable distance: {stable_distance:.1f} cm (3 readings), Severity: {severity}")

                        # Publish detailed collision information
                        details_msg = String()
                        details_msg.data = f"left:{stable_distance:.1f}:{severity}"
                        self.collision_details_pub.publish(details_msg)
                    else:
                        collision_msg = Bool()
                        collision_msg.data = False
                        self.left_collision_pub.publish(collision_msg)
                else:
                    # Not stable or too close - publish safe
                    collision_msg = Bool()
                    collision_msg.data = False
                    self.left_collision_pub.publish(collision_msg)

                    severity_msg = String()
                    severity_msg.data = "safe"
                    self.left_severity_pub.publish(severity_msg)

                self.prev_left_distance = self.current_left_distance
        
        # Right collision detection with stability check
        if self.current_right_distance < float('inf'):
            # Add reading to history (only if >= minimum valid distance)
            if self.current_right_distance >= self.vl53_min_valid_distance:
                self.right_distance_history.append(self.current_right_distance)

                # Check for stable readings
                is_stable, stable_distance = self.is_stable_reading(self.right_distance_history)

                if is_stable:
                    severity = self.determine_severity(stable_distance)

                    # Publish severity
                    severity_msg = String()
                    severity_msg.data = severity
                    self.right_severity_pub.publish(severity_msg)

                    # Check for collision if stable readings are below threshold
                    if stable_distance < self.side_distance_threshold:
                        collision_msg = Bool()
                        collision_msg.data = True
                        self.right_collision_pub.publish(collision_msg)
                        self.get_logger().debug(f"Right collision warning! Stable distance: {stable_distance:.1f} cm (3 readings), Severity: {severity}")

                        # Publish detailed collision information
                        details_msg = String()
                        details_msg.data = f"right:{stable_distance:.1f}:{severity}"
                        self.collision_details_pub.publish(details_msg)
                    else:
                        collision_msg = Bool()
                        collision_msg.data = False
                        self.right_collision_pub.publish(collision_msg)
                else:
                    # Not stable or too close - publish safe
                    collision_msg = Bool()
                    collision_msg.data = False
                    self.right_collision_pub.publish(collision_msg)

                    severity_msg = String()
                    severity_msg.data = "safe"
                    self.right_severity_pub.publish(severity_msg)

                self.prev_right_distance = self.current_right_distance
    
    # MPR121 Collision callbacks (Channels 0-2)
    def mpr121_bottom_callback(self, msg):
        """Handle MPR121 channel 0 (bottom) - collision detection"""
        self.touch_sensors['bottom'] = msg.data
        self.last_touch_sensor_time['bottom'] = self.get_clock().now()
        self._process_mpr121_collision('bottom', msg.data)

    def mpr121_front_right_callback(self, msg):
        """Handle MPR121 channel 1 (front_right) - collision detection"""
        self.touch_sensors['front_right'] = msg.data
        self.last_touch_sensor_time['front_right'] = self.get_clock().now()
        self._process_mpr121_collision('front_right', msg.data)

    def mpr121_front_left_callback(self, msg):
        """Handle MPR121 channel 2 (front_left) - collision detection"""
        self.touch_sensors['front_left'] = msg.data
        self.last_touch_sensor_time['front_left'] = self.get_clock().now()
        self._process_mpr121_collision('front_left', msg.data)

    # MPR121 Petting callbacks (Channels 3-4)
    def mpr121_top_front_callback(self, msg):
        """Handle MPR121 channel 3 (top_front) - petting detection"""
        self.touch_sensors['top_front'] = msg.data
        self.last_touch_sensor_time['top_front'] = self.get_clock().now()
        self._process_mpr121_petting('top_front', msg.data)

    # Note: mpr121_antenna_callback removed - antenna now used for mute toggle in voice_assistant_node

    # MPR121 Release event callbacks (immediate petting triggers)
    def mpr121_top_front_release_callback(self, msg):
        """Handle MPR121 channel 3 (top_front) release event - immediate petting trigger"""
        if msg.data:  # Release event occurred
            self.get_logger().info("👋 Petting RELEASE event on top_front - triggering immediate petting")
            self._trigger_immediate_petting('top_front')

    # Note: mpr121_antenna_release_callback removed - antenna now used for mute toggle

    def _trigger_immediate_petting(self, touch_location):
        """
        Trigger petting event immediately from a release event.
        Release events bypass the 2-consecutive-touch requirement.
        """
        current_time = self.get_clock().now()

        # Always trigger on release events (no rate limiting for releases)
        self.petting_currently_active = True
        self.last_petting_publish_time = current_time

        # Publish petting trigger
        petting_msg = String()
        petting_msg.data = f"petting_started:1"
        self.petting_event_pub.publish(petting_msg)
        self.get_logger().info(f"Petting event triggered by RELEASE on {touch_location}")

    def _process_mpr121_collision(self, touch_location, is_touched):
        """Process MPR121 touch sensor data for collision detection (channels 0-2)"""
        current_time = self.get_clock().now()

        # MPR121 collision active flag is already using the channel names
        if is_touched:
            # New collision detected
            if not self.mpr121_collision_active[touch_location]:
                self.mpr121_collision_active[touch_location] = True
                self.mpr121_collision_start_time[touch_location] = current_time

                self.get_logger().info(f"MPR121 touch collision detected: {touch_location}")

                # Treat all MPR121 touches as collisions with danger severity
                severity = 'danger'

                # Update collision status
                collision_msg = Bool()
                collision_msg.data = True

                # Publish collision warnings (map to old API for compatibility)
                if touch_location == 'front_left' or touch_location == 'front_right':
                    # Front collisions go to head collision
                    self.collision_pub.publish(collision_msg)
                elif touch_location == 'bottom':
                    # Bottom also treated as front collision for now
                    self.collision_pub.publish(collision_msg)

                # Publish severity
                severity_msg = String()
                severity_msg.data = severity

                if touch_location == 'front_left' or touch_location == 'front_right' or touch_location == 'bottom':
                    self.front_severity_pub.publish(severity_msg)

                # Publish detailed collision information
                simulated_distance = 1.0  # cm - represents direct contact
                details_msg = String()
                details_msg.data = f"front:{simulated_distance}:{severity}"
                self.collision_details_pub.publish(details_msg)

        else:
            # Touch released - clear collision
            if self.mpr121_collision_active[touch_location]:
                duration = (current_time - self.mpr121_collision_start_time[touch_location]).nanoseconds / 1e9
                self.get_logger().info(f"MPR121 collision cleared for {touch_location} after {duration:.2f}s")

                self.mpr121_collision_active[touch_location] = False
                self.mpr121_collision_start_time[touch_location] = None

                # Clear collision status
                collision_msg = Bool()
                collision_msg.data = False
                self.collision_pub.publish(collision_msg)

                # Clear severity
                severity_msg = String()
                severity_msg.data = "safe"
                self.front_severity_pub.publish(severity_msg)

    def _process_mpr121_petting(self, touch_location, is_touched):
        """Process MPR121 touch sensor data for petting detection (channel 3 only - antenna moved to mute toggle)"""
        # Don't process petting during startup period
        if not self.startup_complete:
            self.get_logger().debug(f"Ignoring {touch_location} touch during startup")
            return

        current_time = self.get_clock().now()

        if is_touched:
            # Only publish if we weren't already petting OR enough time has passed for rate limiting
            time_since_last_publish = (current_time - self.last_petting_publish_time).nanoseconds / 1e9

            if not self.petting_currently_active:
                # New petting session started
                self.get_logger().info(f"Petting started on {touch_location}")
                self.petting_currently_active = True
                self.last_petting_publish_time = current_time

                # Publish petting trigger
                petting_msg = String()
                petting_msg.data = f"petting_started:1"
                self.petting_event_pub.publish(petting_msg)

            elif time_since_last_publish > self.petting_publish_rate:
                # Continue petting session, but rate limited
                self.get_logger().debug(f"Petting continues on {touch_location}")
                self.last_petting_publish_time = current_time

                # Publish continued petting
                petting_msg = String()
                petting_msg.data = f"petting_started:1"
                self.petting_event_pub.publish(petting_msg)
        else:
            # Petting stopped
            if self.petting_currently_active:
                # Check if ANY petting sensor is still active (only top_front now)
                still_petting = self.touch_sensors['top_front']

                if not still_petting:
                    self.get_logger().info("Petting stopped")
                    self.petting_currently_active = False

                    petting_msg = String()
                    petting_msg.data = "petting_stopped:0"
                    self.petting_event_pub.publish(petting_msg)
    
    def check_mpr121_collisions(self):
        """Check MPR121 collision durations and handle timeouts"""
        current_time = self.get_clock().now()

        for touch_location in ['bottom', 'front_right', 'front_left']:
            if self.mpr121_collision_active[touch_location]:
                # Check if collision has been active too long
                if self.mpr121_collision_start_time[touch_location]:
                    duration = (current_time - self.mpr121_collision_start_time[touch_location]).nanoseconds / 1e9

                    # Auto-clear MPR121 collisions after 2 seconds to prevent sticking
                    if duration > 2.0:
                        self.get_logger().warn(f"MPR121 collision for {touch_location} auto-cleared after {duration:.2f}s (timeout)")

                        self.mpr121_collision_active[touch_location] = False
                        self.mpr121_collision_start_time[touch_location] = None

                        # Clear collision status
                        collision_msg = Bool()
                        collision_msg.data = False
                        self.collision_pub.publish(collision_msg)

                        # Clear severity
                        severity_msg = String()
                        severity_msg.data = "safe"
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