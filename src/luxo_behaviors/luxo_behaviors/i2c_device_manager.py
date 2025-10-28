#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool, Int16, Float32, UInt8
from luxo_interfaces.srv import ConfigureI2CSensor
from std_srvs.srv import Trigger
import board
from adafruit_apds9960.apds9960 import APDS9960
import adafruit_vl53l4cd
import adafruit_mpr121
import threading
import time
import queue
from collections import defaultdict
from enum import Enum, auto
from luxo_behaviors.i2c_bus_wrapper import I2CBusWrapper

class SensorType(Enum):
    """Enum for supported sensor types"""
    APDS9960 = auto()
    VL53L4CD = auto()
    MPR121 = auto()
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
        super().__init__(name, 0x39, SensorType.APDS9960)  # Address: 0x39 on I2C bus 1
        self.enable_gestures = False
        self.gesture_queue = queue.Queue()
        
    def initialize(self, i2c_bus):
        """Initialize APDS9960"""
        try:
            self.device = APDS9960(i2c_bus)
            self.device.enable_proximity = True
            self.device.proximity_gain = 1

            # DISABLED: Gesture detection can cause I2C bus hangs
            # The gesture() method is a blocking call that can freeze the entire bus
            # if self.enable_gestures:
            #     self.device.enable_gesture = True

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
    def __init__(self, name: str, address: int, bus_num: int = 1):
        super().__init__(name, address, SensorType.VL53L4CD)
        self.bus_num = bus_num  # I2C bus number (1 or 3)
        # Add filtering
        self.reading_history = []
        self.history_size = 5
        self.outlier_threshold = 15.0  # cm - readings that differ by more than this from median are suspicious
        
    def initialize(self, i2c_bus):
        """Initialize VL53L4CD"""
        try:
            # Add delay before initialization to let bus settle
            time.sleep(0.1)
            self.device = adafruit_vl53l4cd.VL53L4CD(i2c_bus, self.address)
            self.device.inter_measurement = 75  # 75ms between measurements
            self.device.timing_budget = 75    # 75ms timing budget for best long-range performance
            # Add delay after configuration
            time.sleep(0.15)
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

class MPR121Sensor(I2CSensor):
    """MPR121 Capacitive Touch Sensor for petting and collision detection"""
    def __init__(self, name: str = "mpr121", address: int = 0x5A):
        super().__init__(name, address, SensorType.MPR121)  # Address: 0x5A on I2C bus 1

        # Channel mapping
        self.channel_names = {
            0: "bottom",      # Bottom sensor (collision)
            1: "front_right", # Front-right sensor (collision)
            2: "front_left",  # Front-left sensor (collision)
            3: "top_front",   # Top-front sensor (petting)
            4: "antenna"      # Antenna sensor (petting)
        }

        # Calibrated per-channel thresholds from MPR121.py
        # Format: (touch_threshold, release_threshold)
        self.channel_thresholds = {
            0: (7, 7),   # Bottom - weak signal
            1: (7, 7),   # Front-Right - good signal
            2: (7, 7),   # Front-Left - good signal
            3: (7, 7),   # Top-Front - good signal
            4: (20, 20),   # Antenna - strong signal (excellent)
        }

        # Active channels (0-4)
        self.active_channels = list(self.channel_names.keys())

        # Release event detection
        self.release_event_threshold = 20  # Trigger on delta < -20
        self.release_cooldown = 2.0  # seconds
        self.last_release_time = {ch: 0 for ch in self.active_channels}

        # Consecutive touch tracking (need 3 in a row to confirm)
        self.consecutive_touches = {ch: 0 for ch in self.active_channels}
        self.touch_confirmation_required = 4  # Need 4 consecutive touches

        # Noise recovery tracking - ignore readings after spike until baseline returns
        self.noise_spike_threshold = 50  # Delta values > this are considered noise spikes
        self.noise_recovery_threshold = 5  # Must return below this to clear recovery state
        self.in_noise_recovery = {ch: False for ch in self.active_channels}

    def initialize(self, i2c_bus):
        """Initialize MPR121"""
        try:
            self.device = adafruit_mpr121.MPR121(i2c_bus, address=self.address)

            # Configure thresholds for each channel
            for channel_num in self.active_channels:
                touch_threshold, release_threshold = self.channel_thresholds[channel_num]
                self.device[channel_num].threshold = touch_threshold
                self.device[channel_num].release_threshold = release_threshold

            self.active = True
            return True
        except Exception as e:
            raise Exception(f"Failed to initialize MPR121 at {hex(self.address)}: {e}")

    def read(self):
        """
        Read all MPR121 capacitive touch values with release detection and consecutive touch filtering.

        Touch Logic:
        - Requires 2 consecutive positive detections to confirm touch (reduces false positives)
        - Immediately reports touch=False when no longer detected

        Release Event Logic:
        - Triggers when delta < -release_event_threshold (detects hand removal)
        - Only fires once per cooldown period to avoid spam during baseline recovery
        - Fires immediately (no consecutive requirement)

        Returns dict with channel_name -> {'touched': bool, 'released': bool, 'delta': int}
        """
        if not self.active or not self.device:
            return None

        try:
            current_time = time.time()
            sensor_data = {}

            for channel_num in self.active_channels:
                try:
                    # Get raw values for touch and release detection
                    baseline = self.device.baseline_data(channel_num)
                    filtered = self.device[channel_num].raw_value
                    delta_raw = baseline - filtered  # Store original delta for debugging

                    # === NOISE SPIKE RECOVERY LOGIC ===
                    # Track noise spikes and ignore all readings until baseline returns
                    if abs(delta_raw) > self.noise_spike_threshold:
                        # Detected noise spike - enter recovery mode
                        if not self.in_noise_recovery[channel_num]:
                            self.in_noise_recovery[channel_num] = True
                            # Optional: log the spike (only once when entering recovery)
                            # self.get_logger().debug(f"Ch{channel_num} noise spike detected: {delta_raw}")
                    elif abs(delta_raw) < self.noise_recovery_threshold:
                        # Baseline has recovered - exit recovery mode
                        self.in_noise_recovery[channel_num] = False

                    # If in recovery mode, ignore this reading for touch detection
                    if self.in_noise_recovery[channel_num]:
                        delta = 0  # Treat as no touch while recovering
                    else:
                        delta = delta_raw  # Use actual reading

                    # Get threshold for this channel
                    threshold, _ = self.channel_thresholds[channel_num]

                    # Use absolute value for touch detection (handles both positive and negative deltas)
                    is_touched_raw = abs(delta) >= threshold

                    channel_name = self.channel_names[channel_num]

                    # === CONSECUTIVE TOUCH LOGIC ===
                    # Increment/reset consecutive touch counter
                    if is_touched_raw:
                        self.consecutive_touches[channel_num] += 1
                    else:
                        self.consecutive_touches[channel_num] = 0

                    # Confirm touch only after N consecutive detections
                    confirmed_touch = self.consecutive_touches[channel_num] >= self.touch_confirmation_required

                    # === RELEASE EVENT DETECTION ===
                    # Check for large negative delta (hand removal)
                    is_release_event = False
                    if delta < -self.release_event_threshold:
                        # Check cooldown
                        time_since_last_release = current_time - self.last_release_time[channel_num]
                        if time_since_last_release > self.release_cooldown:
                            is_release_event = True
                            self.last_release_time[channel_num] = current_time

                    sensor_data[channel_name] = {
                        'touched': confirmed_touch,
                        'released': is_release_event,
                        'delta': delta_raw,  # Publish raw delta for debugging (shows actual spikes)
                        'baseline': baseline,
                        'filtered': filtered,
                        'consecutive': self.consecutive_touches[channel_num],
                        'in_recovery': self.in_noise_recovery[channel_num]  # Show recovery state
                    }
                except Exception as channel_error:
                    # Channel-specific error - continue with other channels
                    continue

            # Return data even if some channels failed, as long as we got something
            return sensor_data if sensor_data else None
        except Exception as e:
            raise Exception(f"Failed to read MPR121: {e}")

class I2CDeviceManager(Node):
    """Centralized I2C device manager to prevent bus contention"""
    
    def __init__(self):
        super().__init__('i2c_device_manager')

        # Initialize I2C buses
        self.i2c_bus_1 = board.I2C()  # Primary I2C bus (bus 1)
        self.i2c_bus_3 = None  # Secondary I2C bus (bus 3) - initialized on demand
        self.i2c_lock = threading.Lock()

        # Try to initialize I2C bus 3 if available
        # Bus 3 uses GPIO 6 (SCL) and GPIO 5 (SDA) via dtoverlay=i2c-gpio,bus=3
        # Accessed via /dev/i2c-3
        try:
            self.i2c_bus_3 = I2CBusWrapper(3)  # Software I2C bus 3
            self.get_logger().info("I2C bus 3 initialized successfully (/dev/i2c-3, GPIO 6/SCL, GPIO 5/SDA)")
        except Exception as e:
            self.get_logger().warn(f"I2C bus 3 not available: {e}")
        
        # Bus health monitoring
        self.consecutive_bus_errors = 0
        self.max_consecutive_bus_errors = 5
        self.last_successful_read = self.get_clock().now()
        self.bus_timeout = 120.0  # seconds
        
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
        self.declare_parameter('enable_mpr121', True)
        self.declare_parameter('mpr121_address', 0x5A)  # Default MPR121 address
        self.declare_parameter('publish_rate', 10.0)  # Hz - increased for faster collision response
        self.declare_parameter('recovery_interval', 3.0)  # seconds
        self.declare_parameter('max_init_attempts', 10)

        # Get parameters
        self.enable_gestures = self.get_parameter('enable_gestures').value
        self.enable_apds9960 = self.get_parameter('enable_apds9960').value
        self.enable_vl53_left = self.get_parameter('enable_vl53_left').value
        self.enable_vl53_right = self.get_parameter('enable_vl53_right').value
        self.enable_mpr121 = self.get_parameter('enable_mpr121').value
        self.mpr121_address = self.get_parameter('mpr121_address').value
        publish_rate = self.get_parameter('publish_rate').value
        self.recovery_interval = self.get_parameter('recovery_interval').value
        self.max_init_attempts = self.get_parameter('max_init_attempts').value
        
        # Create publishers for sensor data
        self.proximity_pub = self.create_publisher(Int16, '/i2c/apds9960/proximity', 10)
        self.gesture_pub = self.create_publisher(String, '/i2c/apds9960/gesture', 10)
        self.left_distance_pub = self.create_publisher(Float32, '/i2c/vl53_left/distance', 10)
        self.right_distance_pub = self.create_publisher(Float32, '/i2c/vl53_right/distance', 10)

        # MPR121 Capacitive Touch publishers - Boolean touch state
        # Channels 0-2: Collision detection
        self.mpr121_ch0_pub = self.create_publisher(Bool, '/touch_sensors/bottom', 10)
        self.mpr121_ch1_pub = self.create_publisher(Bool, '/touch_sensors/front_right', 10)
        self.mpr121_ch2_pub = self.create_publisher(Bool, '/touch_sensors/front_left', 10)
        # Channels 3-4: Petting detection
        self.mpr121_ch3_pub = self.create_publisher(Bool, '/touch_sensors/top_front', 10)
        self.mpr121_ch4_pub = self.create_publisher(Bool, '/touch_sensors/antenna', 10)

        # MPR121 Release Event publishers - Boolean release events (hand removed)
        self.mpr121_ch0_release_pub = self.create_publisher(Bool, '/touch_sensors/bottom/released', 10)
        self.mpr121_ch1_release_pub = self.create_publisher(Bool, '/touch_sensors/front_right/released', 10)
        self.mpr121_ch2_release_pub = self.create_publisher(Bool, '/touch_sensors/front_left/released', 10)
        self.mpr121_ch3_release_pub = self.create_publisher(Bool, '/touch_sensors/top_front/released', 10)
        self.mpr121_ch4_release_pub = self.create_publisher(Bool, '/touch_sensors/antenna/released', 10)

        # MPR121 Raw Data publisher - for debugging (delta, baseline, filtered values)
        self.mpr121_raw_data_pub = self.create_publisher(String, '/i2c/mpr121/raw_data', 10)

        # Track latest MPR121 sensor data for 1 Hz publishing
        self.latest_mpr121_data = None

        # Status publishers
        self.status_pub = self.create_publisher(String, '/i2c/status', 10)
        self.sensor_health_pub = self.create_publisher(String, '/i2c/sensor_health', 10)
        
        # Service for sensor configuration
        self.config_service = self.create_service(
            ConfigureI2CSensor,
            'configure_i2c_sensor',
            self.configure_sensor_callback
        )
        
        # Service for bus reset
        self.reset_service = self.create_service(
            Trigger,
            '/i2c/reset_bus',
            self.reset_bus_callback
        )
        
        # Initialize sensors based on configuration
        self._initialize_configured_sensors()
        
        # Create timers for sensor polling
        self.sensor_timer = self.create_timer(1.0 / publish_rate, self.poll_sensors)
        
        # Create recovery timer
        self.recovery_timer = self.create_timer(self.recovery_interval, self.check_and_recover)
        
        # Create health status timer
        self.health_timer = self.create_timer(10.0, self.publish_health_summary)

        # Create MPR121 raw data debug timer (1 Hz)
        self.mpr121_debug_timer = self.create_timer(1.0, self.publish_mpr121_raw_data)

        # Gesture thread for APDS9960 - DISABLED to prevent I2C bus hangs
        self.gesture_thread_running = False
        # DISABLED: Gesture detection causes I2C bus freezes
        # The gesture() method blocks and can hang the entire I2C bus
        # if self.enable_gestures and 'apds9960' in self.sensors:
        #     self.gesture_thread_running = True
        #     self.gesture_thread = threading.Thread(target=self.gesture_thread_worker, daemon=True)
        #     self.gesture_thread.start()
        
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
            # Left sensor on I2C bus 3 at address 0x29
            vl53_left = VL53L4CDSensor('vl53_left', 0x29, bus_num=3)
            self.pending_sensors['vl53_left'] = vl53_left

        if self.enable_vl53_right:
            # Right sensor on I2C bus 1 at address 0x29 (changed from 0x59)
            vl53_right = VL53L4CDSensor('vl53_right', 0x29, bus_num=1)
            self.pending_sensors['vl53_right'] = vl53_right

        if self.enable_mpr121:
            mpr121 = MPR121Sensor('mpr121', self.mpr121_address)
            self.pending_sensors['mpr121'] = mpr121

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
                # Add delay between sensor initializations to prevent bus congestion
                time.sleep(0.05)

                # DISABLED: Gesture thread causes I2C bus hangs
                # if sensor_name == 'apds9960' and self.enable_gestures and not self.gesture_thread_running:
                #     self.gesture_thread_running = True
                #     self.gesture_thread = threading.Thread(target=self.gesture_thread_worker, daemon=True)
                #     self.gesture_thread.start()
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
                # Select the correct I2C bus based on sensor configuration
                if hasattr(sensor, 'bus_num') and sensor.bus_num == 3:
                    if self.i2c_bus_3 is None:
                        raise Exception("I2C bus 3 not available")
                    i2c_bus = self.i2c_bus_3
                else:
                    i2c_bus = self.i2c_bus_1

                sensor.initialize(i2c_bus)
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
        sensors_read = 0
        sensors_failed = 0
        
        for sensor_name, sensor in self.sensors.items():
            if not sensor.active:
                continue
                
            try:
                # Read sensor data with bus protection
                with self.i2c_lock:
                    data = sensor.read()
                    # Add small delay between sensor reads to prevent bus congestion
                    time.sleep(0.002)  # 2ms delay
                    
                if data:
                    sensor.last_success_time = self.get_clock().now()
                    sensor.error_count = 0
                    sensor.successful_reads += 1
                    sensors_read += 1
                    
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

                    elif sensor_name == 'mpr121':
                        # Publish MPR121 capacitive touch sensor data
                        # Touch state (requires 2 consecutive detections)
                        # Release events (immediate, detects hand removal)

                        # Channels 0-2: Collision detection
                        if 'bottom' in data:
                            # Touch state
                            touch_msg = Bool()
                            touch_msg.data = data['bottom']['touched']
                            self.mpr121_ch0_pub.publish(touch_msg)
                            # Log confirmed touch
                            if data['bottom']['touched'] and data['bottom']['consecutive'] == 2:
                                self.get_logger().info(f"🐾 MPR121 CH0 (bottom) TOUCH confirmed (consecutive: {data['bottom']['consecutive']})")
                            # Release event
                            if data['bottom']['released']:
                                release_msg = Bool()
                                release_msg.data = True
                                self.mpr121_ch0_release_pub.publish(release_msg)
                                self.get_logger().info("👋 MPR121 CH0 (bottom) RELEASE detected")

                        if 'front_right' in data:
                            touch_msg = Bool()
                            touch_msg.data = data['front_right']['touched']
                            self.mpr121_ch1_pub.publish(touch_msg)
                            if data['front_right']['touched'] and data['front_right']['consecutive'] == 2:
                                self.get_logger().info(f"🐾 MPR121 CH1 (front_right) TOUCH confirmed (consecutive: {data['front_right']['consecutive']})")
                            if data['front_right']['released']:
                                release_msg = Bool()
                                release_msg.data = True
                                self.mpr121_ch1_release_pub.publish(release_msg)
                                self.get_logger().info("👋 MPR121 CH1 (front_right) RELEASE detected")

                        if 'front_left' in data:
                            touch_msg = Bool()
                            touch_msg.data = data['front_left']['touched']
                            self.mpr121_ch2_pub.publish(touch_msg)
                            if data['front_left']['touched'] and data['front_left']['consecutive'] == 2:
                                self.get_logger().info(f"🐾 MPR121 CH2 (front_left) TOUCH confirmed (consecutive: {data['front_left']['consecutive']})")
                            if data['front_left']['released']:
                                release_msg = Bool()
                                release_msg.data = True
                                self.mpr121_ch2_release_pub.publish(release_msg)
                                self.get_logger().info("👋 MPR121 CH2 (front_left) RELEASE detected")

                        # Channels 3-4: Petting detection
                        if 'top_front' in data:
                            touch_msg = Bool()
                            touch_msg.data = data['top_front']['touched']
                            self.mpr121_ch3_pub.publish(touch_msg)
                            if data['top_front']['touched'] and data['top_front']['consecutive'] == 2:
                                self.get_logger().info(f"🐾 MPR121 CH3 (top_front) TOUCH confirmed (consecutive: {data['top_front']['consecutive']})")
                            if data['top_front']['released']:
                                release_msg = Bool()
                                release_msg.data = True
                                self.mpr121_ch3_release_pub.publish(release_msg)
                                self.get_logger().info("👋 MPR121 CH3 (top_front) RELEASE detected")

                        if 'antenna' in data:
                            touch_msg = Bool()
                            touch_msg.data = data['antenna']['touched']
                            self.mpr121_ch4_pub.publish(touch_msg)
                            if data['antenna']['touched'] and data['antenna']['consecutive'] == 2:
                                self.get_logger().info(f"🐾 MPR121 CH4 (antenna) TOUCH confirmed (consecutive: {data['antenna']['consecutive']})")
                            if data['antenna']['released']:
                                release_msg = Bool()
                                release_msg.data = True
                                self.mpr121_ch4_release_pub.publish(release_msg)
                                self.get_logger().info("👋 MPR121 CH4 (antenna) RELEASE detected")

                        # Store latest MPR121 data for 1 Hz debug publishing
                        self.latest_mpr121_data = data

            except Exception as e:
                sensor.error_count += 1
                sensor.total_errors += 1
                sensor.last_error_time = self.get_clock().now()
                sensors_failed += 1
                
                if sensor.error_count == 1:  # Log on first error
                    self.get_logger().warn(f"{sensor_name} read error: {e}")
                
                if sensor.error_count >= self.max_consecutive_errors:
                    self.get_logger().error(f"{sensor_name} exceeded error threshold, marking inactive for recovery")
                    sensor.active = False
                    self._publish_sensor_health(sensor_name, "error", f"Read errors: {sensor.error_count}")
        
        # Check for bus-wide failures
        if sensors_failed >= 2 and sensors_read == 0:
            self.consecutive_bus_errors += 1
            if self.consecutive_bus_errors >= self.max_consecutive_bus_errors:
                self.get_logger().error(f"I2C bus appears to be locked up ({self.consecutive_bus_errors} consecutive failures)")
                # Trigger bus reset
                self._perform_bus_recovery()
        else:
            # Reset error counter on successful reads
            if sensors_read > 0:
                self.consecutive_bus_errors = 0
                    
    def _perform_bus_recovery(self):
        """Perform emergency I2C bus recovery"""
        self.get_logger().warn("Performing emergency I2C bus recovery")
        
        # Reset error counter to prevent immediate re-trigger
        self.consecutive_bus_errors = 0
        
        # Use the existing reset_bus_callback logic
        from std_srvs.srv import Trigger
        request = Trigger.Request()
        response = Trigger.Response()
        self.reset_bus_callback(request, response)
                    
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
        
        # Check active sensors for problems - create a copy of items to avoid iteration issues
        sensors_to_move = []
        
        for sensor_name, sensor in list(self.sensors.items()):
            # Try to recover inactive sensors
            if not sensor.active:
                self.get_logger().info(f"Attempting to recover {sensor_name}")
                
                if self._try_initialize_sensor(sensor):
                    self.get_logger().info(f"{sensor_name} recovered successfully")
                    self._publish_sensor_health(sensor_name, "recovered", 
                        f"Recovered after {sensor.total_errors} total errors")
                else:
                    # Mark for moving back to pending
                    sensors_to_move.append(sensor_name)
                    
            # Check for sensors that haven't reported in a while
            elif sensor.last_success_time:
                time_since_success = (current_time - sensor.last_success_time).nanoseconds / 1e9
                if time_since_success > 10.0:  # 10 seconds timeout
                    self.get_logger().warn(f"{sensor_name} hasn't reported data for {time_since_success:.1f}s")
                    sensor.active = False
                    self._publish_sensor_health(sensor_name, "timeout", 
                        f"No data for {time_since_success:.1f}s")
        
        # Move failed recovery sensors back to pending (outside the iteration)
        for sensor_name in sensors_to_move:
            if sensor_name in self.sensors:
                sensor = self.sensors[sensor_name]
                # Only move if we haven't exceeded max attempts
                if sensor.initialization_attempts < self.max_init_attempts:
                    self.pending_sensors[sensor_name] = sensor
                    del self.sensors[sensor_name]
                    self.get_logger().warn(f"{sensor_name} moved back to pending sensors")
                else:
                    # Move to failed sensors if max attempts exceeded
                    self.failed_sensors[sensor_name] = sensor
                    del self.sensors[sensor_name]
                    self.get_logger().error(f"{sensor_name} moved to failed sensors after {sensor.initialization_attempts} attempts")

    def publish_mpr121_raw_data(self):
        """Publish raw MPR121 sensor data at 1 Hz for debugging"""
        if self.latest_mpr121_data is None:
            return

        try:
            import json

            # Format data for all 5 channels
            debug_data = {}
            for channel_name, channel_data in self.latest_mpr121_data.items():
                debug_data[channel_name] = {
                    'delta': channel_data['delta'],
                    'baseline': channel_data['baseline'],
                    'filtered': channel_data['filtered'],
                    'touched': channel_data['touched'],
                    'released': channel_data['released'],
                    'consecutive': channel_data['consecutive']
                }

            # Publish as JSON string
            msg = String()
            msg.data = json.dumps(debug_data, indent=2)
            self.mpr121_raw_data_pub.publish(msg)

        except Exception as e:
            self.get_logger().error(f"Error publishing MPR121 raw data: {e}")

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
                    
    def reset_bus_callback(self, request, response):
        """Handle I2C bus reset requests"""
        self.get_logger().warn("I2C bus reset requested")

        try:
            # Mark all sensors as inactive (do this before taking the lock)
            for sensor in self.sensors.values():
                sensor.active = False
                sensor.error_count = 0

            # Deinitialize both buses
            with self.i2c_lock:
                try:
                    if hasattr(self.i2c_bus_1, 'deinit'):
                        self.i2c_bus_1.deinit()
                except Exception as e:
                    self.get_logger().debug(f"Bus 1 deinit error (expected): {e}")

                try:
                    if self.i2c_bus_3 is not None and hasattr(self.i2c_bus_3, 'deinit'):
                        self.i2c_bus_3.deinit()
                except Exception as e:
                    self.get_logger().debug(f"Bus 3 deinit error (expected): {e}")

            # Wait outside the lock
            time.sleep(1.5)

            # Reinitialize both buses
            with self.i2c_lock:
                self.i2c_bus_1 = board.I2C()

                # Try to reinitialize bus 3
                # Bus 3 uses GPIO 6 (SCL) and GPIO 5 (SDA) via dtoverlay=i2c-gpio,bus=3
                try:
                    self.i2c_bus_3 = I2CBusWrapper(3)  # Software I2C bus 3
                    self.get_logger().info("I2C bus 3 reinitialized (/dev/i2c-3, GPIO 6/SCL, GPIO 5/SDA)")
                except Exception as e:
                    self.get_logger().warn(f"I2C bus 3 not available after reset: {e}")
                    self.i2c_bus_3 = None

            # Move all sensors to pending for reinitialization
            for sensor_name, sensor in list(self.sensors.items()):
                sensor.initialization_attempts = 0
                self.pending_sensors[sensor_name] = sensor
            self.sensors.clear()

            # Try to reinitialize
            self._initialize_pending_sensors()

            response.success = True
            response.message = "I2C bus reset completed"
            self.get_logger().info("I2C bus reset completed")

        except Exception as e:
            response.success = False
            response.message = f"Bus reset failed: {str(e)}"
            self.get_logger().error(f"I2C bus reset failed: {e}")

        return response
    
    def configure_sensor_callback(self, request, response):
        """Handle sensor configuration requests"""
        try:
            sensor_name = request.sensor_name
            config_type = request.config_type
            config_value = request.config_value
            
            # Check all sensor lists
            sensor = None
            current_location = None
            
            if sensor_name in self.sensors:
                sensor = self.sensors[sensor_name]
                current_location = 'active'
            elif sensor_name in self.pending_sensors:
                sensor = self.pending_sensors[sensor_name]
                current_location = 'pending'
            elif sensor_name in self.failed_sensors:
                sensor = self.failed_sensors[sensor_name]
                current_location = 'failed'
                
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
                sensor.total_errors = 0
                
                # Move to pending based on current location
                if current_location == 'failed':
                    self.pending_sensors[sensor_name] = sensor
                    del self.failed_sensors[sensor_name]
                elif current_location == 'active' and not sensor.active:
                    self.pending_sensors[sensor_name] = sensor
                    del self.sensors[sensor_name]
                    
                # Try to initialize immediately
                self._initialize_pending_sensors()
                
            response.success = True
            response.message = f"Configuration applied to {sensor_name} (was in {current_location})"
            
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