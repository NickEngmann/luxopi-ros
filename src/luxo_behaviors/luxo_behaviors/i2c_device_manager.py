#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool, Int16, Float32
from luxo_interfaces.srv import ConfigureI2CSensor
import board
from adafruit_apds9960.apds9960 import APDS9960
import adafruit_vl53l4cd
import threading
import time
import queue
from collections import defaultdict
from enum import Enum, auto

class SensorType(Enum):
    """Enum for supported sensor types"""
    APDS9960 = auto()
    VL53L4CD = auto()
    # Add more sensor types here as needed

class I2CSensor:
    """Base class for I2C sensors"""
    def __init__(self, name: str, address: int, sensor_type: SensorType):
        self.name = name
        self.address = address
        self.sensor_type = sensor_type
        self.device = None
        self.active = False
        self.error_count = 0
        self.total_errors = 0
        self.successful_reads = 0
        self.last_success_time = None
        self.last_error_time = None
        self.initialization_attempts = 0
        self.last_initialization_attempt = None
        
    def initialize(self, i2c_bus):
        """Initialize the sensor (to be overridden by subclasses)"""
        raise NotImplementedError
        
    def read(self):
        """Read data from the sensor (to be overridden by subclasses)"""
        raise NotImplementedError

class APDS9960Sensor(I2CSensor):
    """APDS9960 proximity and gesture sensor"""
    def __init__(self, name: str = "apds9960"):
        super().__init__(name, 0x39, SensorType.APDS9960)
        self.enable_gestures = False
        self.gesture_queue = queue.Queue()
        
    def initialize(self, i2c_bus):
        """Initialize APDS9960"""
        try:
            self.device = APDS9960(i2c_bus)
            self.device.enable_proximity = True
            self.device.proximity_gain = 1
            
            if self.enable_gestures:
                self.device.enable_gesture = True
                
            self.active = True
            return True
        except Exception as e:
            raise Exception(f"Failed to initialize APDS9960: {e}")
            
    def read(self):
        """Read proximity data"""
        if not self.active or not self.device:
            return None
            
        try:
            proximity = self.device.proximity
            return {'proximity': proximity}
        except Exception as e:
            raise Exception(f"Failed to read APDS9960: {e}")
            
    def read_gesture(self):
        """Read gesture data (non-blocking)"""
        if not self.active or not self.device or not self.enable_gestures:
            return None
            
        try:
            gesture = self.device.gesture()
            if gesture == 0x01:
                return "up"
            elif gesture == 0x02:
                return "down"
            elif gesture == 0x03:
                return "left"
            elif gesture == 0x04:
                return "right"
            return None
        except Exception as e:
            raise Exception(f"Failed to read gesture: {e}")

class VL53L4CDSensor(I2CSensor):
    """VL53L4CD time-of-flight distance sensor"""
    def __init__(self, name: str, address: int):
        super().__init__(name, address, SensorType.VL53L4CD)
        # Add filtering
        self.reading_history = []
        self.history_size = 5
        self.outlier_threshold = 15.0  # cm - readings that differ by more than this from median are suspicious
        
    def initialize(self, i2c_bus):
        """Initialize VL53L4CD"""
        try:
            self.device = adafruit_vl53l4cd.VL53L4CD(i2c_bus, self.address)
            # Increase timing for more stable readings
            self.device.inter_measurement = 100  # Increased from 50ms
            self.device.timing_budget = 100  # Increased from 50ms for better accuracy
            self.device.start_ranging()
            self.active = True
            self.reading_history = []  # Clear history on init
            return True
        except Exception as e:
            raise Exception(f"Failed to initialize VL53L4CD at {hex(self.address)}: {e}")
            
    def read(self):
        """Read distance data with filtering"""
        if not self.active or not self.device:
            return None
            
        try:
            if self.device.data_ready:
                raw_distance = self.device.distance
                self.device.clear_interrupt()
                
                # Filter out invalid readings
                if raw_distance <= 0 or raw_distance > 400:  # VL53L4CD max range is 400cm
                    return None
                
                # Add to history
                self.reading_history.append(raw_distance)
                if len(self.reading_history) > self.history_size:
                    self.reading_history.pop(0)
                
                # Need at least 3 readings for median filter
                if len(self.reading_history) < 3:
                    return {'distance': raw_distance, 'filtered': False}
                
                # Calculate median
                sorted_history = sorted(self.reading_history)
                median = sorted_history[len(sorted_history) // 2]
                
                # Check if current reading is an outlier
                if abs(raw_distance - median) > self.outlier_threshold:
                    # Use median instead of outlier
                    return {'distance': median, 'filtered': True, 'raw': raw_distance}
                
                # Use moving average of non-outlier readings
                valid_readings = [r for r in self.reading_history 
                                if abs(r - median) <= self.outlier_threshold]
                
                if valid_readings:
                    filtered_distance = sum(valid_readings) / len(valid_readings)
                    return {'distance': filtered_distance, 'filtered': True, 'raw': raw_distance}
                else:
                    return {'distance': median, 'filtered': True, 'raw': raw_distance}
                    
            return None
        except Exception as e:
            raise Exception(f"Failed to read VL53L4CD: {e}")

class I2CDeviceManager(Node):
    """Centralized I2C device manager to prevent bus contention"""
    
    def __init__(self):
        super().__init__('i2c_device_manager')
        
        # Initialize I2C bus
        self.i2c_bus = board.I2C()
        self.i2c_lock = threading.Lock()
        
        # Sensor registries
        self.sensors = {}  # Successfully initialized sensors
        self.pending_sensors = {}  # Sensors waiting to be initialized
        self.failed_sensors = {}  # Sensors that failed with details
        
        # Error tracking
        self.error_counts = defaultdict(int)
        self.max_consecutive_errors = 5
        self.recovery_interval = 3.0  # Try to recover every 3 seconds
        self.max_init_attempts = 10  # Maximum initialization attempts before giving up
        self.error_log_throttle = 10.0  # Log errors at most every 10 seconds per sensor
        self.last_error_log = {}
        
        # Parameters
        self.declare_parameter('enable_gestures', False)
        self.declare_parameter('enable_apds9960', True)
        self.declare_parameter('enable_vl53_left', True)
        self.declare_parameter('enable_vl53_right', True)
        self.declare_parameter('publish_rate', 5.0)  # Hz
        self.declare_parameter('recovery_interval', 3.0)  # seconds
        self.declare_parameter('max_init_attempts', 10)
        
        # Get parameters
        self.enable_gestures = self.get_parameter('enable_gestures').value
        self.enable_apds9960 = self.get_parameter('enable_apds9960').value
        self.enable_vl53_left = self.get_parameter('enable_vl53_left').value
        self.enable_vl53_right = self.get_parameter('enable_vl53_right').value
        publish_rate = self.get_parameter('publish_rate').value
        self.recovery_interval = self.get_parameter('recovery_interval').value
        self.max_init_attempts = self.get_parameter('max_init_attempts').value
        
        # Create publishers for sensor data
        self.proximity_pub = self.create_publisher(Int16, '/i2c/apds9960/proximity', 10)
        self.gesture_pub = self.create_publisher(String, '/i2c/apds9960/gesture', 10)
        self.left_distance_pub = self.create_publisher(Float32, '/i2c/vl53_left/distance', 10)
        self.right_distance_pub = self.create_publisher(Float32, '/i2c/vl53_right/distance', 10)
        
        # Status publishers
        self.status_pub = self.create_publisher(String, '/i2c/status', 10)
        self.sensor_health_pub = self.create_publisher(String, '/i2c/sensor_health', 10)
        
        # Service for sensor configuration
        self.config_service = self.create_service(
            ConfigureI2CSensor,
            'configure_i2c_sensor',
            self.configure_sensor_callback
        )
        
        # Initialize sensors based on configuration
        self._initialize_configured_sensors()
        
        # Create timers for sensor polling
        self.sensor_timer = self.create_timer(1.0 / publish_rate, self.poll_sensors)
        
        # Create recovery timer
        self.recovery_timer = self.create_timer(self.recovery_interval, self.check_and_recover)
        
        # Create health status timer
        self.health_timer = self.create_timer(10.0, self.publish_health_summary)
        
        # Gesture thread for APDS9960 (if enabled)
        self.gesture_thread_running = False
        if self.enable_gestures and 'apds9960' in self.sensors:
            self.gesture_thread_running = True
            self.gesture_thread = threading.Thread(target=self.gesture_thread_worker, daemon=True)
            self.gesture_thread.start()
        
        self.get_logger().info('I2C Device Manager initialized')
        self._publish_status("I2C Device Manager started")
        
    def _initialize_configured_sensors(self):
        """Initialize sensors based on configuration"""
        # Create sensor objects and add to pending list
        if self.enable_apds9960:
            apds = APDS9960Sensor()
            apds.enable_gestures = self.enable_gestures
            self.pending_sensors['apds9960'] = apds
            
        if self.enable_vl53_left:
            vl53_left = VL53L4CDSensor('vl53_left', 0x29)
            self.pending_sensors['vl53_left'] = vl53_left
            
        if self.enable_vl53_right:
            vl53_right = VL53L4CDSensor('vl53_right', 0x59)
            self.pending_sensors['vl53_right'] = vl53_right
        
        # Try to initialize all pending sensors
        self._initialize_pending_sensors()
            
    def _initialize_pending_sensors(self):
        """Try to initialize all pending sensors"""
        sensors_to_remove = []
        
        for sensor_name, sensor in self.pending_sensors.items():
            if self._try_initialize_sensor(sensor):
                # Success - move to active sensors
                self.sensors[sensor_name] = sensor
                sensors_to_remove.append(sensor_name)
                self.get_logger().info(f"{sensor_name} initialized successfully")
                
                # Start gesture thread if APDS9960 just came online
                if sensor_name == 'apds9960' and self.enable_gestures and not self.gesture_thread_running:
                    self.gesture_thread_running = True
                    self.gesture_thread = threading.Thread(target=self.gesture_thread_worker, daemon=True)
                    self.gesture_thread.start()
            else:
                # Failed - check if we should give up
                if sensor.initialization_attempts >= self.max_init_attempts:
                    self.failed_sensors[sensor_name] = sensor
                    sensors_to_remove.append(sensor_name)
                    self.get_logger().error(f"{sensor_name} failed after {self.max_init_attempts} attempts, giving up")
                    self._publish_sensor_health(sensor_name, "failed", 
                        f"Initialization failed after {self.max_init_attempts} attempts")
        
        # Remove successfully initialized or permanently failed sensors from pending
        for sensor_name in sensors_to_remove:
            del self.pending_sensors[sensor_name]
            
    def _try_initialize_sensor(self, sensor: I2CSensor) -> bool:
        """Try to initialize a single sensor"""
        current_time = self.get_clock().now()
        sensor.initialization_attempts += 1
        sensor.last_initialization_attempt = current_time
        
        with self.i2c_lock:
            try:
                sensor.initialize(self.i2c_bus)
                sensor.last_success_time = current_time
                sensor.error_count = 0
                sensor.total_errors = 0
                self._publish_sensor_health(sensor.name, "online", "Sensor initialized")
                return True
            except Exception as e:
                sensor.last_error_time = current_time
                
                # Throttle error logging
                should_log = True
                if sensor.name in self.last_error_log:
                    time_since_last_log = (current_time - self.last_error_log[sensor.name]).nanoseconds / 1e9
                    if time_since_last_log < self.error_log_throttle:
                        should_log = False
                
                if should_log:
                    self.get_logger().error(f"Failed to initialize {sensor.name} (attempt {sensor.initialization_attempts}): {e}")
                    self.last_error_log[sensor.name] = current_time
                
                sensor.active = False
                return False
                
    def poll_sensors(self):
        """Poll all active sensors and publish data"""
        for sensor_name, sensor in self.sensors.items():
            if not sensor.active:
                continue
                
            try:
                # Read sensor data with bus protection
                with self.i2c_lock:
                    data = sensor.read()
                    
                if data:
                    sensor.last_success_time = self.get_clock().now()
                    sensor.error_count = 0
                    sensor.successful_reads += 1
                    
                    # Publish based on sensor type
                    if sensor_name == 'apds9960' and 'proximity' in data:
                        msg = Int16()
                        msg.data = data['proximity']
                        self.proximity_pub.publish(msg)
                        
                    elif sensor_name == 'vl53_left' and 'distance' in data:
                        msg = Float32()
                        msg.data = data['distance']
                        self.left_distance_pub.publish(msg)
                        
                    elif sensor_name == 'vl53_right' and 'distance' in data:
                        msg = Float32()
                        msg.data = data['distance']
                        self.right_distance_pub.publish(msg)
                        
            except Exception as e:
                sensor.error_count += 1
                sensor.total_errors += 1
                sensor.last_error_time = self.get_clock().now()
                
                if sensor.error_count == 1:  # Log on first error
                    self.get_logger().warn(f"{sensor_name} read error: {e}")
                
                if sensor.error_count >= self.max_consecutive_errors:
                    self.get_logger().error(f"{sensor_name} exceeded error threshold, marking inactive for recovery")
                    sensor.active = False
                    self._publish_sensor_health(sensor_name, "error", f"Read errors: {sensor.error_count}")
                    
    def gesture_thread_worker(self):
        """Dedicated thread for gesture detection"""
        apds = self.sensors.get('apds9960')
        if not apds:
            return
            
        while self.gesture_thread_running:
            try:
                if apds and apds.active:
                    with self.i2c_lock:
                        gesture = apds.read_gesture()
                        
                    if gesture:
                        msg = String()
                        msg.data = gesture
                        self.gesture_pub.publish(msg)
                        self.get_logger().info(f"Gesture detected: {gesture}")
                        
                time.sleep(0.01)  # Small delay to prevent CPU overload
                
            except Exception as e:
                self.get_logger().error(f"Gesture thread error: {e}")
                time.sleep(1.0)
                
    def check_and_recover(self):
        """Periodically check sensor health and attempt recovery"""
        current_time = self.get_clock().now()
        
        # Try to initialize pending sensors
        if self.pending_sensors:
            self.get_logger().debug(f"Attempting to initialize {len(self.pending_sensors)} pending sensors")
            self._initialize_pending_sensors()
        
        # Check active sensors for problems
        for sensor_name, sensor in self.sensors.items():
            # Try to recover inactive sensors
            if not sensor.active:
                self.get_logger().info(f"Attempting to recover {sensor_name}")
                
                if self._try_initialize_sensor(sensor):
                    self.get_logger().info(f"{sensor_name} recovered successfully")
                    self._publish_sensor_health(sensor_name, "recovered", 
                        f"Recovered after {sensor.total_errors} total errors")
                else:
                    # Move back to pending if recovery failed
                    if sensor_name not in self.pending_sensors:
                        self.pending_sensors[sensor_name] = sensor
                        del self.sensors[sensor_name]
                        self.get_logger().warn(f"{sensor_name} moved back to pending sensors")
                    
            # Check for sensors that haven't reported in a while
            elif sensor.last_success_time:
                time_since_success = (current_time - sensor.last_success_time).nanoseconds / 1e9
                if time_since_success > 10.0:  # 10 seconds timeout
                    self.get_logger().warn(f"{sensor_name} hasn't reported data for {time_since_success:.1f}s")
                    sensor.active = False
                    self._publish_sensor_health(sensor_name, "timeout", 
                        f"No data for {time_since_success:.1f}s")
                    
    def publish_health_summary(self):
        """Publish a summary of all sensor health"""
        active_sensors = len([s for s in self.sensors.values() if s.active])
        inactive_sensors = len([s for s in self.sensors.values() if not s.active])
        pending_sensors = len(self.pending_sensors)
        failed_sensors = len(self.failed_sensors)
        
        summary = f"Active: {active_sensors}, Inactive: {inactive_sensors}, Pending: {pending_sensors}, Failed: {failed_sensors}"
        
        # Publish detailed status
        msg = String()
        msg.data = f"SUMMARY: {summary}"
        self.sensor_health_pub.publish(msg)
        
        # Log if there are issues
        if inactive_sensors > 0 or pending_sensors > 0 or failed_sensors > 0:
            self.get_logger().info(f"Sensor health: {summary}")
            
            # Log details of problematic sensors
            for name, sensor in self.pending_sensors.items():
                self.get_logger().debug(f"  Pending: {name} (attempts: {sensor.initialization_attempts})")
            
            for name, sensor in self.sensors.items():
                if not sensor.active:
                    self.get_logger().debug(f"  Inactive: {name} (errors: {sensor.error_count})")
                    
    def configure_sensor_callback(self, request, response):
        """Handle sensor configuration requests"""
        try:
            sensor_name = request.sensor_name
            config_type = request.config_type
            config_value = request.config_value
            
            # Check all sensor lists
            sensor = None
            if sensor_name in self.sensors:
                sensor = self.sensors[sensor_name]
            elif sensor_name in self.pending_sensors:
                sensor = self.pending_sensors[sensor_name]
            elif sensor_name in self.failed_sensors:
                sensor = self.failed_sensors[sensor_name]
                
            if not sensor:
                response.success = False
                response.message = f"Sensor {sensor_name} not found"
                return response
                
            # Handle configuration based on type
            if config_type == "enable":
                sensor.active = bool(config_value)
            elif config_type == "reinitialize":
                # Reset counters and try to initialize
                sensor.initialization_attempts = 0
                sensor.error_count = 0
                
                # Move to pending if not already there
                if sensor_name in self.failed_sensors:
                    self.pending_sensors[sensor_name] = sensor
                    del self.failed_sensors[sensor_name]
                elif sensor_name in self.sensors and not sensor.active:
                    self.pending_sensors[sensor_name] = sensor
                    del self.sensors[sensor_name]
                    
                self._initialize_pending_sensors()
                
            response.success = True
            response.message = f"Configuration applied to {sensor_name}"
            
        except Exception as e:
            response.success = False
            response.message = str(e)
            
        return response
        
    def _publish_status(self, message: str):
        """Publish status message"""
        msg = String()
        msg.data = f"[{self.get_clock().now().nanoseconds}] {message}"
        self.status_pub.publish(msg)
        
    def _publish_sensor_health(self, sensor_name: str, status: str, details: str = ""):
        """Publish sensor health status"""
        msg = String()
        msg.data = f"{sensor_name}:{status}:{details}"
        self.sensor_health_pub.publish(msg)
        
    def destroy_node(self):
        """Clean shutdown"""
        self.get_logger().info("Shutting down I2C Device Manager")
        
        # Stop gesture thread
        if hasattr(self, 'gesture_thread_running'):
            self.gesture_thread_running = False
            if hasattr(self, 'gesture_thread') and self.gesture_thread.is_alive():
                self.gesture_thread.join(timeout=1.0)
        
        # Stop all sensors
        with self.i2c_lock:
            for sensor in self.sensors.values():
                sensor.active = False
                
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = I2CDeviceManager()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error in I2C Device Manager: {e}")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()