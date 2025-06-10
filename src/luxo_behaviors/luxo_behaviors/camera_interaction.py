#!/usr/bin/env python3
#camera_interaction.py
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from .MultiMsgSync import TwoStageHostSeqSync
import blobconverter
import depthai as dai
import numpy as np
import time
import sys
import cv2
import subprocess
import math
import os
import threading
from std_msgs.msg import String, Float32, Bool, UInt8, Int16
from sensor_msgs.msg import Image, JointState
from cv_bridge import CvBridge
from collections import deque
from luxo_interfaces.action import PlayAnimation

def frame_norm(frame, bbox):
    normVals = np.full(len(bbox), frame.shape[0])
    normVals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

emotions = ['neutral', 'happy', 'sad', 'surprise', 'anger']

class CameraInteraction(Node):
    def __init__(self):
        super().__init__('camera_interaction')
        
        # Camera connection state
        self.camera_connected = False
        self.camera_retry_interval = 30.0  # seconds
        self.camera_retry_attempts = 0
        self.max_retry_attempts = -1  # -1 means infinite retries

        # Error tracking for camera disconnection detection
        self.consecutive_camera_errors = 0
        self.max_consecutive_errors = 5  # Trigger reconnect after 5 consecutive errors
        self.last_camera_error_log_time = self.get_clock().now()
        self.camera_error_log_interval = 5.0  # Log errors at most every 5 seconds
        
        # Create ROS publishers
        self.emotion_publisher = self.create_publisher(String, '/camera/emotion', 10)
        self.distance_publisher = self.create_publisher(Float32, '/camera/person_distance', 10)
        
        # Publisher for notifying animation command about emotion trigger
        self.animation_trigger_publisher = self.create_publisher(String, '/animation_trigger_source', 10)
        
        # Create action client for animation control
        self._animation_action_client = ActionClient(
            self,
            PlayAnimation,
            'play_animation'
        )
        
        # Wait for action server to be available
        self.get_logger().info('Waiting for animation action server...')
        if not self._animation_action_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().warn('Animation action server not available after 10 seconds')
        else:
            self.get_logger().info('Connected to animation action server')
        
        # Track active animation goals
        self._active_goal_handle = None
        
        # Parameter for publishing the camera feed
        self.declare_parameter('publish_camera_feed', False)
        self.publish_camera_feed = self.get_parameter('publish_camera_feed').get_parameter_value().bool_value
        
        if self.publish_camera_feed:
            self.bridge = CvBridge()
            self.image_publisher = self.create_publisher(Image, '/camera/image_raw', 10)
        
        # Parameter for framebuffer display
        self.declare_parameter('enable_framebuffer_display', True)
        self.enable_framebuffer_display = self.get_parameter('enable_framebuffer_display').get_parameter_value().bool_value
        
        # Framebuffer display parameters
        self.declare_parameter('framebuffer_device', '/dev/fb0')
        self.framebuffer_device = self.get_parameter('framebuffer_device').get_parameter_value().string_value
        
        self.declare_parameter('framebuffer_tty', '1')
        self.framebuffer_tty = self.get_parameter('framebuffer_tty').get_parameter_value().string_value
        
        self.declare_parameter('framebuffer_update_interval', 0.05)  # seconds
        self.framebuffer_update_interval = self.get_parameter('framebuffer_update_interval').get_parameter_value().double_value
        self.last_framebuffer_update = self.get_clock().now()
        # Framebuffer display state
        if self.enable_framebuffer_display:
            # Import the framebuffer display class
            from .framebuffer_display import CameraFramebufferDisplay
            self.framebuffer_display = CameraFramebufferDisplay(self, self.framebuffer_device)
            
            if self.framebuffer_display.enabled:
                self.get_logger().info(f'Direct framebuffer display initialized on {self.framebuffer_device}')
            else:
                self.get_logger().warn('Failed to initialize framebuffer display')
                self.enable_framebuffer_display = False
        
        # Parameter for verbose mode
        self.declare_parameter('verbose', False)
        self.verbose = self.get_parameter('verbose').get_parameter_value().bool_value
        
        # Parameter to enable/disable emotional reactions
        self.declare_parameter('react_to_emotions', True)
        self.react_to_emotions = self.get_parameter('react_to_emotions').get_parameter_value().bool_value
        
        # Add parameter for camera rotation (0 = normal, 180 = flipped)
        self.declare_parameter('camera_rotation', False)
        self.camera_rotation = self.get_parameter('camera_rotation').get_parameter_value().bool_value
        if self.verbose:
            rotation_msg = "180 degrees" if self.camera_rotation else "normal (0 degrees)"
            self.get_logger().info(f'Camera rotation set to: {rotation_msg}')
        
        # Add parameter for emotion buffer duration
        self.declare_parameter('emotion_buffer_duration', 2.0)
        self.emotion_buffer_duration = self.get_parameter('emotion_buffer_duration').get_parameter_value().double_value
        
        # Add parameter for emotion detection threshold
        self.declare_parameter('emotion_threshold', 50.0)
        self.emotion_threshold = self.get_parameter('emotion_threshold').get_parameter_value().double_value
        
        # Add parameter for emotion cooldown
        self.declare_parameter('emotion_cooldown', 5.0)
        self.emotion_cooldown = self.get_parameter('emotion_cooldown').get_parameter_value().double_value
        
        # Add parameter for camera retry interval
        self.declare_parameter('camera_retry_interval', 30.0)
        self.camera_retry_interval = self.get_parameter('camera_retry_interval').get_parameter_value().double_value
        
        # Add parameter for emotion timeout
        self.declare_parameter('emotion_timeout', 3.0)
        self.emotion_timeout = self.get_parameter('emotion_timeout').get_parameter_value().double_value
        
        # Track last emotion and animation time for cooldown - using ROS2 time
        self.last_emotion = "neutral"
        self.last_animation_time = self.get_clock().now()
        
        # Track last emotion detection time
        self.last_emotion_detection_time = None

        # Add a history of recent emotions to avoid repetition
        self.recent_emotions = deque(maxlen=3)  # Keep track of last 3 emotions that triggered animations
        
        # Map emotions to animations
        self.emotion_to_animation = {
            'happy': ['excited', 'playful', 'dance'],
            'sad': ['sad', 'droop'],
            'surprise': ['startled', 'curious'],
            'anger': ['shake', 'think', 'startled'],
            'neutral': ['idle', 'curious', 'stretch', 'nod']
        }
        
        # Emotion buffer system - using ROS2 time
        self.emotion_buffer = deque(maxlen=60)
        self.emotion_buffer_start_time = self.get_clock().now()
        
        # Log configuration summary
        if self.react_to_emotions:
            self.get_logger().info('Emotion-triggered animations are ENABLED')
        else:
            self.get_logger().info('Emotion-triggered animations are DISABLED')
        
        # Initialize camera-related variables
        self.device = None
        self.stereo = False
        self.sync = None
        self.queues = {}
        self.timer = None
        
        # Try to initialize camera
        self.get_logger().info('Attempting to initialize camera...')
        self.get_logger().info(f'Emotion detection parameters: buffer_duration={self.emotion_buffer_duration}s, '
                             f'threshold={self.emotion_threshold}%, cooldown={self.emotion_cooldown}s')
        
        self._active_goal_handle = None
        self._goal_is_active = False  # Track state manually

        # Store face bounding boxes for display
        self.last_face_bboxes = []  # List of (x1, y1, x2, y2) tuples
        
        # Voice parameters for debugging
        self.voice_active = False
        self.voice_direction = None
        self.voice_confidence = 0.0
        self.voice_spectral_confidence = 0.0
        self.voice_snr = 0.0
        self.voice_last_detection_time = None
        
        # Subscribe to animation name and state topics
        self.current_animation_name = None
        self.current_state = "UNKNOWN"
        
        # Subscribe to animation status
        self.animation_status_sub = self.create_subscription(
            String,
            '/roarm/current_animation',
            self.animation_status_callback,
            10
        )
        
        # Subscribe to state machine status
        self.state_status_sub = self.create_subscription(
            String,
            '/luxo/current_state',
            self.state_status_callback,
            10
        )
        
        # Subscribe to voice topics for debugging
        self.voice_active_sub = self.create_subscription(
            Bool,
            '/voice/active',
            self.voice_active_callback,
            10
        )
        
        self.voice_direction_sub = self.create_subscription(
            Float32,
            '/voice/direction',
            self.voice_direction_callback,
            10
        )
        
        self.voice_confidence_sub = self.create_subscription(
            Float32,
            '/voice/confidence',
            self.voice_confidence_callback,
            10
        )
        
        self.voice_spectral_confidence_sub = self.create_subscription(
            Float32,
            '/voice/spectral_confidence',
            self.voice_spectral_confidence_callback,
            10
        )
        
        self.voice_snr_sub = self.create_subscription(
            Float32,
            '/voice/snr',
            self.voice_snr_callback,
            10
        )

        # Subscribe to system metrics for display
        self.system_metrics = {
            'cpu_usage': 0.0,
            'ram_usage': 0.0,
            'temperature': 0.0
        }
        
        # Subscribe to system monitor topics
        self.cpu_usage_sub = self.create_subscription(
            Float32, '/system/cpu_usage',
            lambda msg: self.update_system_metric('cpu_usage', msg.data), 10
        )
        self.ram_usage_sub = self.create_subscription(
            Float32, '/system/ram_usage', 
            lambda msg: self.update_system_metric('ram_usage', msg.data), 10
        )
        self.temperature_sub = self.create_subscription(
            Float32, '/system/temperature',
            lambda msg: self.update_system_metric('temperature', msg.data), 10
        )
        
        # Subscribe to joint states for real-time joint display
        self.joint_states = {}
        self.joint_states_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_states_callback,
            10
        )
        
        # Subscribe to I2C sensor data for touch and collision
        self.touch_sensors = {
            'head_top': 0,
            'head_left': 0,
            'head_bottom': 0,
            'head_right': 0
        }
        
        self.collision_sensors = {
            'left': False,
            'right': False,
            'head': False
        }
        
        # Touch sensor subscribers
        self.touch_head_top_sub = self.create_subscription(
            UInt8, '/touch_sensors/head_top', 
            lambda msg: self.update_touch_sensor('head_top', msg.data), 10
        )
        self.touch_head_left_sub = self.create_subscription(
            UInt8, '/touch_sensors/head_left',
            lambda msg: self.update_touch_sensor('head_left', msg.data), 10
        )
        self.touch_head_bottom_sub = self.create_subscription(
            UInt8, '/touch_sensors/head_bottom',
            lambda msg: self.update_touch_sensor('head_bottom', msg.data), 10
        )
        self.touch_head_right_sub = self.create_subscription(
            UInt8, '/touch_sensors/head_right',
            lambda msg: self.update_touch_sensor('head_right', msg.data), 10
        )
        
        # Distance sensors for collision detection
        self.distance_left_sub = self.create_subscription(
            Float32, '/i2c/vl53_left/distance',
            lambda msg: self.update_collision_sensor('left', msg.data), 10
        )
        self.distance_right_sub = self.create_subscription(
            Float32, '/i2c/vl53_right/distance',
            lambda msg: self.update_collision_sensor('right', msg.data), 10
        )
        
        # Proximity sensor for head collision
        self.proximity_sub = self.create_subscription(
            Int16, '/i2c/apds9960/proximity',
            lambda msg: self.update_collision_sensor('head', msg.data), 10
        )

        if self.initialize_camera():
            self.get_logger().info('Camera initialized successfully')
        else:
            self.get_logger().warn(f'Camera not found. Will retry every {self.camera_retry_interval} seconds...')
            # Show camera not found message on framebuffer
            if self.enable_framebuffer_display and hasattr(self, 'framebuffer_display'):
                self._show_camera_not_found_message()
            # Create retry timer
            self.create_camera_retry_timer()

    def update_system_metric(self, metric_name, value):
        """Update system metrics for display"""
        self.system_metrics[metric_name] = value

    def update_touch_sensor(self, sensor_name, value):
        """Update touch sensor values"""
        self.touch_sensors[sensor_name] = value

    def update_collision_sensor(self, sensor_name, value):
        """Update collision sensor values"""
        if sensor_name in ['left', 'right']:
            # For distance sensors, collision if distance < 10cm
            self.collision_sensors[sensor_name] = value < 0.1
        elif sensor_name == 'head':
            # For proximity sensor, collision if value > threshold
            self.collision_sensors[sensor_name] = value > 200

    def voice_active_callback(self, msg):
        """Update voice active status."""
        self.voice_active = msg.data
        if self.voice_active:
            self.voice_last_detection_time = self.get_clock().now()

    def voice_direction_callback(self, msg):
        """Update voice direction."""
        self.voice_direction = msg.data

    def voice_confidence_callback(self, msg):
        """Update voice confidence."""
        self.voice_confidence = msg.data

    def voice_spectral_confidence_callback(self, msg):
        """Update voice spectral confidence."""
        self.voice_spectral_confidence = msg.data

    def voice_snr_callback(self, msg):
        """Update voice SNR."""
        self.voice_snr = msg.data

    def animation_status_callback(self, msg):
        """Update current animation name."""
        self.current_animation_name = msg.data if msg.data else None

    def state_status_callback(self, msg):
        """Update current state machine state."""
        self.current_state = msg.data
    
    def joint_states_callback(self, msg):
        """Update joint states for display"""
        # Convert joint state message to a dictionary for easy access
        for i, name in enumerate(msg.name):
            if i < len(msg.position):
                # Convert radians to degrees for display
                angle_deg = math.degrees(msg.position[i])
                self.joint_states[name] = angle_deg

    def _update_framebuffer_display(self, frame):
        """Update the framebuffer display with the latest frame"""
        if not self.enable_framebuffer_display:
            return
        
        current_time = self.get_clock().now()
        time_since_last_update = (current_time - self.last_framebuffer_update).nanoseconds / 1e9
        
        # Only update at the specified interval
        if time_since_last_update < self.framebuffer_update_interval:
            return
        
        try:
            # Determine current emotion based on timeout
            emotion = None
            if self.last_emotion_detection_time is not None:
                time_since_last_emotion = (current_time - self.last_emotion_detection_time).nanoseconds / 1e9
                if time_since_last_emotion <= self.emotion_timeout:
                    emotion = getattr(self, 'last_detected_emotion', None)
                # If timeout exceeded, emotion remains None
            
            distance = getattr(self, 'last_person_distance', None)
            
            # Get face bounding boxes
            face_bboxes = getattr(self, 'last_face_bboxes', [])
            
            # Get animation and state info
            animation_name = self.current_animation_name
            state = self.current_state
            
            # Collect voice debug info
            voice_info = {
                'active': self.voice_active,
                'direction': self.voice_direction,
                'confidence': self.voice_confidence,
                'spectral_confidence': self.voice_spectral_confidence,
                'snr': self.voice_snr,
                'last_detection_time': self.voice_last_detection_time
            }
            
            # Update display with all info including joint states
            self.framebuffer_display.update_display(
                frame, 
                emotion=emotion, 
                distance=distance,
                face_bboxes=face_bboxes,
                animation_name=animation_name,
                state=state,
                voice_info=voice_info,
                system_metrics=self.system_metrics,
                touch_sensors=self.touch_sensors,
                collision_sensors=self.collision_sensors,
                joint_states=self.joint_states
            )
            
            self.last_framebuffer_update = current_time
            
            if self.verbose:
                self.get_logger().debug("Updated framebuffer display with debug info")
                
        except Exception as e:
            self.get_logger().error(f"Error updating framebuffer display: {e}")
    
    def create_camera_retry_timer(self):
        """Create a timer to periodically retry camera connection."""
        self.camera_retry_timer = self.create_timer(
            self.camera_retry_interval,
            self.retry_camera_connection
        )
    
    def retry_camera_connection(self):
        """Attempt to reconnect to the camera."""
        self.camera_retry_attempts += 1
        self.get_logger().info(f'Retrying camera connection (attempt {self.camera_retry_attempts})...')
        
        # Show attempting connection message
        if self.enable_framebuffer_display and hasattr(self, 'framebuffer_display'):
            self._show_camera_attempting_connection()
        
        if self.initialize_camera():
            self.get_logger().info('Camera reconnection successful!')
            # Show success message briefly
            if self.enable_framebuffer_display and hasattr(self, 'framebuffer_display'):
                self._show_camera_reconnected_message()
            # Cancel the retry timer
            self.camera_retry_timer.cancel()
            self.camera_retry_timer = None
            self.camera_retry_attempts = 0
            # Reset error tracking
            self.consecutive_camera_errors = 0
        else:
            if self.max_retry_attempts > 0 and self.camera_retry_attempts >= self.max_retry_attempts:
                self.get_logger().error(f'Maximum camera retry attempts ({self.max_retry_attempts}) reached. Giving up.')
                self.camera_retry_timer.cancel()
                self.camera_retry_timer = None
            else:
                self.get_logger().warn(f'Camera still not found. Will retry again in {self.camera_retry_interval} seconds...')
    
    def initialize_camera(self):
        """Initialize the camera system. Returns True if successful, False otherwise."""
        try:
            # Check if a device is available
            device_infos = dai.Device.getAllAvailableDevices()
            if not device_infos:
                self.get_logger().warn("No DepthAI devices found")
                return False
            
            # Initialize device and determine if stereo is available
            self.device = dai.Device()
            self.stereo = 1 < len(self.device.getConnectedCameras())
            self.get_logger().info(f"{'Stereo' if self.stereo else 'Mono'} camera detected")
            
            # Start pipeline
            self.device.startPipeline(self.create_pipeline())
            
            # Initialize sync and queues
            self.sync = TwoStageHostSeqSync()
            self.queues = {}
            
            # Create output queues
            for name in ["color", "detection", "recognition"]:
                self.queues[name] = self.device.getOutputQueue(name)
            
            # Create timer callback for processing camera data if not already created
            if self.timer is None:
                self.timer = self.create_timer(0.03, self.process_camera_data)  # ~30fps
            
            self.camera_connected = True
            return True
            
        except Exception as e:
            self.get_logger().error(f'Failed to initialize camera: {e}')
            # Clean up any partial initialization
            if self.device is not None:
                try:
                    self.device.close()
                except:
                    pass
                self.device = None
            self.camera_connected = False
            return False
    
    def create_pipeline(self):
        pipeline = dai.Pipeline()

        if self.verbose:
            self.get_logger().info("Creating Color Camera...")
        cam = pipeline.create(dai.node.ColorCamera)
        cam.setPreviewSize(1080, 1080)
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam.setInterleaved(False)
        cam.setBoardSocket(dai.CameraBoardSocket.RGB)
        
        # Set camera orientation based on parameter
        if self.camera_rotation:
            cam.setImageOrientation(dai.CameraImageOrientation.ROTATE_180_DEG)
            if self.verbose:
                self.get_logger().info("Camera image orientation: ROTATE_180_DEG")
        else:
            cam.setImageOrientation(dai.CameraImageOrientation.AUTO)
            if self.verbose:
                self.get_logger().info("Camera image orientation: AUTO")

        cam_xout = pipeline.create(dai.node.XLinkOut)
        cam_xout.setStreamName("color")
        cam.preview.link(cam_xout.input)

        # Workaround: remove in 2.18, use `cam.setPreviewNumFramesPool(10)`
        # This manip uses 15*3.5 MB => 52 MB of RAM.
        copy_manip = pipeline.create(dai.node.ImageManip)
        copy_manip.setNumFramesPool(15)
        copy_manip.setMaxOutputFrameSize(3499200)
        cam.preview.link(copy_manip.inputImage)

        # ImageManip that will crop the frame before sending it to the Face detection NN node
        face_det_manip = pipeline.create(dai.node.ImageManip)
        face_det_manip.initialConfig.setResize(300, 300)
        face_det_manip.initialConfig.setFrameType(dai.RawImgFrame.Type.RGB888p)
        copy_manip.out.link(face_det_manip.inputImage)

        if self.stereo:
            monoLeft = pipeline.create(dai.node.MonoCamera)
            monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
            monoLeft.setBoardSocket(dai.CameraBoardSocket.LEFT)

            monoRight = pipeline.create(dai.node.MonoCamera)
            monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
            monoRight.setBoardSocket(dai.CameraBoardSocket.RIGHT)

            stereo = pipeline.create(dai.node.StereoDepth)
            stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
            stereo.setDepthAlign(dai.CameraBoardSocket.RGB)
            monoLeft.out.link(stereo.left)
            monoRight.out.link(stereo.right)

            # Spatial Detection network if OAK-D
            if self.verbose:
                self.get_logger().info("OAK-D detected, spatial coordinates will be available")
            face_det_nn = pipeline.create(dai.node.MobileNetSpatialDetectionNetwork)
            face_det_nn.setBoundingBoxScaleFactor(0.8)
            face_det_nn.setDepthLowerThreshold(100)
            face_det_nn.setDepthUpperThreshold(5000)
            stereo.depth.link(face_det_nn.inputDepth)
        else: # Detection network if OAK-1
            if self.verbose:
                self.get_logger().info("OAK-1 detected, spatial coordinates won't be available")
            face_det_nn = pipeline.create(dai.node.MobileNetDetectionNetwork)

        face_det_nn.setConfidenceThreshold(0.5)
        face_det_nn.setBlobPath(blobconverter.from_zoo(name="face-detection-retail-0004", shaves=6))
        face_det_manip.out.link(face_det_nn.input)

        # Send face detections to the host (for bounding boxes)
        face_det_xout = pipeline.create(dai.node.XLinkOut)
        face_det_xout.setStreamName("detection")
        face_det_nn.out.link(face_det_xout.input)

        # Script node will take the output from the face detection NN as an input and set ImageManipConfig
        # to the 'age_gender_manip' to crop the initial frame
        image_manip_script = pipeline.create(dai.node.Script)
        face_det_nn.out.link(image_manip_script.inputs['face_det_in'])

        # Only send metadata, we are only interested in timestamp, so we can sync
        # depth frames with NN output
        face_det_nn.passthrough.link(image_manip_script.inputs['passthrough'])
        copy_manip.out.link(image_manip_script.inputs['preview'])

        image_manip_script.setScript("""
        import time
        msgs = dict()

        def add_msg(msg, name, seq = None):
            global msgs
            if seq is None:
                seq = msg.getSequenceNum()
            seq = str(seq)

            # Each seq number has it's own dict of msgs
            if seq not in msgs:
                msgs[seq] = dict()
            msgs[seq][name] = msg

            # To avoid freezing (not necessary for this ObjDet model)
            if 15 < len(msgs):
                node.warn(f"Removing first element! len {len(msgs)}")
                msgs.popitem() # Remove first element

        def get_msgs():
            global msgs
            seq_remove = [] # Arr of sequence numbers to get deleted
            for seq, syncMsgs in msgs.items():
                seq_remove.append(seq) # Will get removed from dict if we find synced msgs pair

                # Check if we have both detections and color frame with this sequence number
                if len(syncMsgs) == 2: # 1 frame, 1 detection
                    for rm in seq_remove:
                        del msgs[rm]
                    return syncMsgs # Returned synced msgs
            return None

        def correct_bb(bb):
            if bb.xmin < 0: bb.xmin = 0.001
            if bb.ymin < 0: bb.ymin = 0.001
            if bb.xmax > 1: bb.xmax = 0.999
            if bb.ymax > 1: bb.ymax = 0.999
            return bb

        while True:
            time.sleep(0.001) # Avoid lazy looping

            preview = node.io['preview'].tryGet()
            if preview is not None:
                add_msg(preview, 'preview')

            face_dets = node.io['face_det_in'].tryGet()
            if face_dets is not None:
                # TODO: in 2.18.0.0 use face_dets.getSequenceNum()
                passthrough = node.io['passthrough'].get()
                seq = passthrough.getSequenceNum()
                add_msg(face_dets, 'dets', seq)

            sync_msgs = get_msgs()
            if sync_msgs is not None:
                img = sync_msgs['preview']
                dets = sync_msgs['dets']
                for i, det in enumerate(dets.detections):
                    cfg = ImageManipConfig()
                    correct_bb(det)
                    cfg.setCropRect(det.xmin, det.ymin, det.xmax, det.ymax)
                    cfg.setResize(64, 64)
                    cfg.setKeepAspectRatio(False)
                    node.io['manip_cfg'].send(cfg)
                    node.io['manip_img'].send(img)
        """)

        manip_manip = pipeline.create(dai.node.ImageManip)
        manip_manip.initialConfig.setResize(64, 64)
        manip_manip.setWaitForConfigInput(True)
        image_manip_script.outputs['manip_cfg'].link(manip_manip.inputConfig)
        image_manip_script.outputs['manip_img'].link(manip_manip.inputImage)

        # This ImageManip will crop the mono frame based on the NN detections. Resulting image will be the cropped
        # face that was detected by the face-detection NN.
        emotions_nn = pipeline.create(dai.node.NeuralNetwork)
        emotions_nn.setBlobPath(blobconverter.from_zoo(name="emotions-recognition-retail-0003", shaves=6))
        manip_manip.out.link(emotions_nn.input)

        recognition_xout = pipeline.create(dai.node.XLinkOut)
        recognition_xout.setStreamName("recognition")
        emotions_nn.out.link(recognition_xout.input)

        return pipeline

    def process_camera_data(self):
        """Process camera data and publish emotion results as ROS messages"""
        # Skip if camera is not connected
        if not self.camera_connected or self.device is None:
            return
        
        try:
            # Process all available messages
            for name, q in self.queues.items():
                # Add all msgs (color frames, object detections and age/gender recognitions) to the Sync class.
                if q.has():
                    self.sync.add_msg(q.get(), name)

            msgs = self.sync.get_msgs()
            if msgs is not None:
                frame = msgs["color"].getCvFrame()
                detections = msgs["detection"].detections
                recognitions = msgs["recognition"]

                # Clear face bboxes if no detections
                if not detections:
                    self.last_face_bboxes = []
                    # Update framebuffer display even with no faces - show "No faces detected" overlay
                    if self.enable_framebuffer_display and frame is not None:
                        self._update_framebuffer_display(frame)
                    # Reset error counter on successful processing (even with no detections)
                    self.consecutive_camera_errors = 0
                    return
                
                # Store all face bounding boxes
                face_bboxes = []
                for detection in detections:
                    bbox = frame_norm(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
                    face_bboxes.append(bbox)
                self.last_face_bboxes = face_bboxes
                
                # Find the closest person if stereo camera is available
                closest_person_idx = 0
                if self.stereo and len(detections) > 1:
                    min_distance = float('inf')
                    for i, detection in enumerate(detections):
                        person_distance = detection.spatialCoordinates.z / 1000.0  # mm to m
                        if person_distance < min_distance:
                            min_distance = person_distance
                            closest_person_idx = i
                            
                    if self.verbose:
                        self.get_logger().info(f"Multiple people detected, focusing on closest person at index {closest_person_idx}")
                
                # Process only the closest person (or the first one if no distance data)
                detection = detections[closest_person_idx]
                rec = recognitions[closest_person_idx]

                bbox = frame_norm(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
                emotion_results = np.array(rec.getFirstLayerFp16())
                emotion_name = emotions[np.argmax(emotion_results)]
                
                # Store for framebuffer display and update detection time
                self.last_detected_emotion = emotion_name
                self.last_emotion_detection_time = self.get_clock().now()
                
                # Update framebuffer display with all data
                if self.enable_framebuffer_display and frame is not None:
                    self._update_framebuffer_display(frame)

                # Always publish current emotion for monitoring/debugging
                emotion_msg = String()
                emotion_msg.data = emotion_name
                self.emotion_publisher.publish(emotion_msg)
                
                # Get person distance if stereo camera is available
                person_distance = None
                if self.stereo:
                    distance_msg = Float32()
                    # Convert from millimeters to meters
                    raw_distance = detection.spatialCoordinates.z / 1000.0
                    
                    # Filter out invalid readings
                    if raw_distance <= 0.001:  # Too close to be real
                        person_distance = None
                        if self.verbose:
                            self.get_logger().debug(f"Invalid distance reading: {raw_distance:.3f}m")
                    else:
                        person_distance = raw_distance
                        self.last_person_distance = person_distance  # Store for framebuffer display
                        distance_msg.data = person_distance
                        self.distance_publisher.publish(distance_msg)
                    
                    if self.verbose and person_distance is not None:
                        self.get_logger().info(f"Tracked person with emotion: {emotion_name} at {person_distance:.2f}m")
                else:
                    if self.verbose:
                        self.get_logger().info(f"Tracked person with emotion: {emotion_name}")
                
                # Add to emotion buffer with ROS2 timestamp
                current_time = self.get_clock().now()
                self.emotion_buffer.append((emotion_name, person_distance, current_time))
                
                # Trigger animations based on buffered emotions if enabled
                if self.react_to_emotions:
                    self.process_emotion_buffer()
                    
                # Reset error counter on successful processing
                self.consecutive_camera_errors = 0
                
        except Exception as e:
            # Increment error counter
            self.consecutive_camera_errors += 1
            
            # Throttle error logging
            current_time = self.get_clock().now()
            time_since_last_log = (current_time - self.last_camera_error_log_time).nanoseconds / 1e9
            
            if time_since_last_log >= self.camera_error_log_interval:
                self.get_logger().error(f"Error processing camera data: {e} (consecutive errors: {self.consecutive_camera_errors})")
                self.last_camera_error_log_time = current_time
            
            # Check if we should attempt reconnection
            if self.consecutive_camera_errors >= self.max_consecutive_errors:
                self.get_logger().warn(f"Camera appears to be disconnected after {self.consecutive_camera_errors} consecutive errors. Attempting reconnection...")
                self.handle_camera_disconnection()

    def handle_camera_disconnection(self):
        """Handle camera disconnection by cleaning up and starting retry timer"""
        # Mark camera as disconnected
        self.camera_connected = False
        
        # Show disconnection message on framebuffer if enabled
        if self.enable_framebuffer_display and hasattr(self, 'framebuffer_display'):
            self._show_camera_disconnected_message()
        
        # Clean up the device
        if self.device is not None:
            try:
                self.device.close()
                self.get_logger().info("Closed disconnected camera device")
            except Exception as e:
                self.get_logger().debug(f"Error closing device: {e}")
            finally:
                self.device = None
        
        # Reset error counter
        self.consecutive_camera_errors = 0
        
        # Clear queues and sync
        self.queues = {}
        self.sync = None
        
        # Start retry timer if not already running
        if not hasattr(self, 'camera_retry_timer') or self.camera_retry_timer is None:
            self.get_logger().info(f"Starting camera reconnection timer (retry every {self.camera_retry_interval} seconds)")
            self.create_camera_retry_timer()
        else:
            self.get_logger().debug("Camera retry timer already active")
    
    def _show_camera_not_found_message(self):
        """Show camera not found message on framebuffer during initial startup"""
        if not self.enable_framebuffer_display or not hasattr(self, 'framebuffer_display'):
            return
            
        try:
            # Create a black frame
            frame = np.zeros((240, 320, 3), dtype=np.uint8)  # Default size
            
            # Try to get actual display size
            if hasattr(self.framebuffer_display, 'display') and hasattr(self.framebuffer_display.display, 'height'):
                height = self.framebuffer_display.display.height
                width = self.framebuffer_display.display.width
                frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            # Main message
            text = "CAMERA NOT FOUND"
            font_scale = 1.5
            thickness = 2
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            
            # Center the text
            x = (frame.shape[1] - text_size[0]) // 2
            y = (frame.shape[0] + text_size[1]) // 2 - 40
            
            # Draw text with border
            cv2.putText(frame, text, (x, y), font, font_scale, (0, 0, 0), thickness + 2)  # Black border
            cv2.putText(frame, text, (x, y), font, font_scale, (255, 165, 0), thickness)  # Orange text
            
            # Add info about retry
            retry_text = "Searching for camera..."
            font_scale_sub = 0.8
            thickness_sub = 1
            text_size_sub = cv2.getTextSize(retry_text, font, font_scale_sub, thickness_sub)[0]
            x_sub = (frame.shape[1] - text_size_sub[0]) // 2
            y_sub = y + 50
            
            cv2.putText(frame, retry_text, (x_sub, y_sub), font, font_scale_sub, (200, 200, 200), thickness_sub)
            
            # Add retry interval info
            interval_text = f"Retry every {self.camera_retry_interval}s"
            text_size_int = cv2.getTextSize(interval_text, font, font_scale_sub, thickness_sub)[0]
            x_int = (frame.shape[1] - text_size_int[0]) // 2
            y_int = y_sub + 30
            
            cv2.putText(frame, interval_text, (x_int, y_int), font, font_scale_sub, (150, 150, 150), thickness_sub)
            
            # Display the frame directly
            if hasattr(self.framebuffer_display, 'display') and self.framebuffer_display.display:
                self.framebuffer_display.display.display_frame(frame)
            
        except Exception as e:
            self.get_logger().error(f"Error showing camera not found message: {e}")
    
    def _show_camera_disconnected_message(self):
        """Show camera disconnected message on framebuffer"""
        if not self.enable_framebuffer_display or not hasattr(self, 'framebuffer_display'):
            return
            
        try:
            # Create a black frame
            frame = np.zeros((240, 320, 3), dtype=np.uint8)  # Default size
            
            # Try to get actual display size
            if hasattr(self.framebuffer_display, 'display') and hasattr(self.framebuffer_display.display, 'height'):
                height = self.framebuffer_display.display.height
                width = self.framebuffer_display.display.width
                frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            # Main message
            text = "CAMERA DISCONNECTED"
            font_scale = 1.5
            thickness = 2
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            
            # Center the text
            x = (frame.shape[1] - text_size[0]) // 2
            y = (frame.shape[0] + text_size[1]) // 2 - 40
            
            # Draw text with border
            cv2.putText(frame, text, (x, y), font, font_scale, (0, 0, 0), thickness + 2)  # Black border
            cv2.putText(frame, text, (x, y), font, font_scale, (0, 0, 255), thickness)  # Red text
            
            # Add retry info
            retry_text = f"Retrying in {self.camera_retry_interval}s..."
            font_scale_sub = 0.8
            thickness_sub = 1
            text_size_sub = cv2.getTextSize(retry_text, font, font_scale_sub, thickness_sub)[0]
            x_sub = (frame.shape[1] - text_size_sub[0]) // 2
            y_sub = y + 50
            
            cv2.putText(frame, retry_text, (x_sub, y_sub), font, font_scale_sub, (200, 200, 200), thickness_sub)
            
            # Add attempt counter if available
            if hasattr(self, 'camera_retry_attempts') and self.camera_retry_attempts > 0:
                attempt_text = f"Attempt: {self.camera_retry_attempts}"
                text_size_att = cv2.getTextSize(attempt_text, font, font_scale_sub, thickness_sub)[0]
                x_att = (frame.shape[1] - text_size_att[0]) // 2
                y_att = y_sub + 30
                cv2.putText(frame, attempt_text, (x_att, y_att), font, font_scale_sub, (150, 150, 150), thickness_sub)
            
            # Display the frame directly
            if hasattr(self.framebuffer_display, 'display') and self.framebuffer_display.display:
                self.framebuffer_display.display.display_frame(frame)
            
        except Exception as e:
            self.get_logger().error(f"Error showing camera disconnected message: {e}")
    
    def _show_camera_reconnected_message(self):
        """Show camera reconnected success message on framebuffer"""
        if not self.enable_framebuffer_display or not hasattr(self, 'framebuffer_display'):
            return
            
        try:
            # Create a black frame
            frame = np.zeros((240, 320, 3), dtype=np.uint8)  # Default size
            
            # Try to get actual display size
            if hasattr(self.framebuffer_display, 'display') and hasattr(self.framebuffer_display.display, 'height'):
                height = self.framebuffer_display.display.height
                width = self.framebuffer_display.display.width
                frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            # Main message
            text = "CAMERA CONNECTED"
            font_scale = 1.5
            thickness = 2
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            
            # Center the text
            x = (frame.shape[1] - text_size[0]) // 2
            y = (frame.shape[0] + text_size[1]) // 2 - 20
            
            # Draw text with border
            cv2.putText(frame, text, (x, y), font, font_scale, (0, 0, 0), thickness + 2)  # Black border
            cv2.putText(frame, text, (x, y), font, font_scale, (0, 255, 0), thickness)  # Green text
            
            # Add success message
            success_text = "Resuming operation..."
            font_scale_sub = 0.8
            thickness_sub = 1
            text_size_sub = cv2.getTextSize(success_text, font, font_scale_sub, thickness_sub)[0]
            x_sub = (frame.shape[1] - text_size_sub[0]) // 2
            y_sub = y + 40
            
            cv2.putText(frame, success_text, (x_sub, y_sub), font, font_scale_sub, (200, 200, 200), thickness_sub)
            
            # Display the frame directly
            if hasattr(self.framebuffer_display, 'display') and self.framebuffer_display.display:
                self.framebuffer_display.display.display_frame(frame)
            
            # Show briefly then it will be replaced by camera feed
            import time
            time.sleep(1.0)
            
        except Exception as e:
            self.get_logger().error(f"Error showing camera reconnected message: {e}")
    
    def _show_camera_attempting_connection(self):
        """Show attempting connection message on framebuffer"""
        if not self.enable_framebuffer_display or not hasattr(self, 'framebuffer_display'):
            return
            
        try:
            # Create a black frame
            frame = np.zeros((240, 320, 3), dtype=np.uint8)  # Default size
            
            # Try to get actual display size
            if hasattr(self.framebuffer_display, 'display') and hasattr(self.framebuffer_display.display, 'height'):
                height = self.framebuffer_display.display.height
                width = self.framebuffer_display.display.width
                frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            # Main message
            text = "CONNECTING..."
            font_scale = 1.8
            thickness = 2
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            
            # Center the text
            x = (frame.shape[1] - text_size[0]) // 2
            y = (frame.shape[0] + text_size[1]) // 2 - 30
            
            # Draw text with border
            cv2.putText(frame, text, (x, y), font, font_scale, (0, 0, 0), thickness + 2)  # Black border
            cv2.putText(frame, text, (x, y), font, font_scale, (255, 255, 0), thickness)  # Yellow text
            
            # Add attempt info
            attempt_text = f"Attempt #{self.camera_retry_attempts}"
            font_scale_sub = 0.9
            thickness_sub = 1
            text_size_sub = cv2.getTextSize(attempt_text, font, font_scale_sub, thickness_sub)[0]
            x_sub = (frame.shape[1] - text_size_sub[0]) // 2
            y_sub = y + 50
            
            cv2.putText(frame, attempt_text, (x_sub, y_sub), font, font_scale_sub, (200, 200, 200), thickness_sub)
            
            # Add a simple loading animation (dots)
            dots = "." * ((self.camera_retry_attempts % 4))
            dots_text = f"Please wait{dots}"
            text_size_dots = cv2.getTextSize(dots_text, font, font_scale_sub, thickness_sub)[0]
            x_dots = (frame.shape[1] - text_size_dots[0]) // 2
            y_dots = y_sub + 30
            
            cv2.putText(frame, dots_text, (x_dots, y_dots), font, font_scale_sub, (150, 150, 150), thickness_sub)
            
            # Display the frame directly
            if hasattr(self.framebuffer_display, 'display') and self.framebuffer_display.display:
                self.framebuffer_display.display.display_frame(frame)
            
        except Exception as e:
            self.get_logger().error(f"Error showing attempting connection message: {e}")
    
    def process_emotion_buffer(self):
        """Process the emotion buffer and trigger an animation if conditions are met"""
        current_time = self.get_clock().now()
        
        # Check if we've collected enough data and if the buffer duration has elapsed
        if (len(self.emotion_buffer) > 0 and 
                ((current_time - self.emotion_buffer_start_time).nanoseconds / 1e9) >= self.emotion_buffer_duration):
            
            # Get the current elapsed time since last animation
            time_since_last_animation = (current_time - self.last_animation_time).nanoseconds / 1e9
            
            # Count occurrences of each emotion in the buffer
            emotion_counts = {}
            valid_distances = []
            
            for emotion, distance, timestamp in self.emotion_buffer:
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
                # Filter out invalid distance readings (0.00m or >4.0m likely errors)
                if distance is not None and 0.3 < distance < 4.0:
                    valid_distances.append(distance)
            
            # Calculate average distance from valid readings only
            avg_distance = None
            if valid_distances:
                avg_distance = sum(valid_distances) / len(valid_distances)
                if self.verbose:
                    self.get_logger().debug(f"Valid distances: {len(valid_distances)}/{len(self.emotion_buffer)}, avg: {avg_distance:.2f}m")
            
            # Check if we have at least 3 emotion samples
            if len(self.emotion_buffer) < 3:
                self.get_logger().debug(f"Not enough emotion samples ({len(self.emotion_buffer)}), need at least 3")
                # Reset buffer and start time
                self.emotion_buffer.clear()
                self.emotion_buffer_start_time = current_time
                return
            
            # Find the most common emotion
            if emotion_counts:
                # Sort emotions by count (highest first)
                sorted_emotions = sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)
                dominant_emotion = sorted_emotions[0][0]
                
                # Calculate percentage of dominant emotion
                dominant_percentage = (emotion_counts[dominant_emotion] / len(self.emotion_buffer)) * 100
                
                # Log buffer statistics
                if self.verbose:
                    self.get_logger().info(f"Buffer stats: {emotion_counts}, samples: {len(self.emotion_buffer)}")
                
                # Only trigger if dominant enough (using configurable threshold)
                if dominant_percentage >= self.emotion_threshold:
                    # Check cooldown period
                    if time_since_last_animation > self.emotion_cooldown:
                        # Check if this emotion is too repetitive
                        if self._is_too_repetitive(dominant_emotion):
                            self.get_logger().info(f"Emotion {dominant_emotion} is repetitive, but checking if we should override...")
                            
                            # If it's been a long time since last animation, allow it anyway
                            if time_since_last_animation > self.emotion_cooldown * 2:
                                self.get_logger().info(f"Overriding repetition check due to long idle time ({time_since_last_animation:.1f}s)")
                                # Trigger the animation
                                self.trigger_animation(dominant_emotion, avg_distance)
                            else:
                                self.get_logger().info(f"Skipping repetitive emotion: {dominant_emotion}")
                        else:
                            self.get_logger().info(f"Triggering animation for emotion: {dominant_emotion} ({dominant_percentage:.1f}%)")
                            # Trigger the animation
                            self.trigger_animation(dominant_emotion, avg_distance)
                    else:
                        remaining_cooldown = self.emotion_cooldown - time_since_last_animation
                        self.get_logger().info(f"Still in cooldown period, {remaining_cooldown:.1f}s remaining")
                else:
                    self.get_logger().debug(f"No dominant emotion found, highest: {dominant_emotion} ({dominant_percentage:.1f}%)")
            
            # Reset the buffer and start time
            self.emotion_buffer.clear()
            self.emotion_buffer_start_time = current_time

    def _is_too_repetitive(self, emotion):
        """Check if an emotion is being detected too repetitively"""
        # If it's the same as the last triggered emotion, check how long ago that was
        if emotion == self.last_emotion:
            # But allow it if enough time has passed
            current_time = self.get_clock().now()
            time_since_last = (current_time - self.last_animation_time).nanoseconds / 1e9
            if time_since_last > self.emotion_cooldown * 1.5:  # 7.5 seconds
                return False  # Allow it after extended time
            return True
            
        # If this emotion appears too frequently in our recent history
        if len(self.recent_emotions) >= 3:  # Check last 3 animations
            emotion_counts = {}
            for e in self.recent_emotions:
                emotion_counts[e] = emotion_counts.get(e, 0) + 1
                
            # If this emotion was ALL of our last 3 animations, skip it
            if emotion in emotion_counts and emotion_counts[emotion] >= 3:
                return True
        
        return False

    def trigger_animation(self, emotion, distance=None):
        """Trigger an animation based on detected emotion using the action system"""
        # Update state with ROS2 time
        self.last_emotion = emotion
        self.last_animation_time = self.get_clock().now()
        
        # Add to recent emotions history
        self.recent_emotions.append(emotion)
        
        # Get corresponding animation options
        if emotion in self.emotion_to_animation:
            animation_options = self.emotion_to_animation[emotion]
            # Randomly select one animation from the available options
            animation = np.random.choice(animation_options)
            
            # Add speed modifier based on distance if available
            speed_modifier = 1.0
            if distance is not None:
                # Closer distance = faster reaction (within reason)
                if 0.5 <= distance <= 3.0:
                    # Map 0.5m->1.5 (faster) and 3.0m->0.7 (slower)
                    speed = 1.5 - ((distance - 0.5) * 0.32)
                    speed_modifier = speed
                
            # Cancel any existing animation goal
            if self._active_goal_handle:
                self.get_logger().info("Cancelling previous emotion-triggered animation")
                self._active_goal_handle.cancel_goal_async()
            
            # Notify animation command that this is an emotion trigger
            self._notify_animation_trigger('emotion')
            
            # Send animation goal using action system
            self._send_animation_goal(animation, speed_modifier, emotion)
    
    def _notify_animation_trigger(self, source: str):
        """Notify the animation command server about the trigger source."""
        try:
            msg = String()
            msg.data = source
            self.animation_trigger_publisher.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing animation trigger source: {e}")
    
    def _send_animation_goal(self, animation_name, speed_multiplier, trigger_emotion):
        """Send an animation goal to the action server"""
        if not self._animation_action_client.server_is_ready():
            self.get_logger().warn("Animation action server not ready")
            return
        
        # Create goal message
        goal_msg = PlayAnimation.Goal()
        goal_msg.animation_name = animation_name
        goal_msg.speed_multiplier = speed_multiplier
        goal_msg.allow_interruption = True  # Emotions can be interrupted
        goal_msg.use_hardware_feedback = False
        
        self.get_logger().info(
            f"Sending emotion-triggered animation: {animation_name} "
            f"(speed: {speed_multiplier:.1f}, emotion: {trigger_emotion})"
        )
        
        # Send goal asynchronously
        send_goal_future = self._animation_action_client.send_goal_async(
            goal_msg,
            feedback_callback=self._animation_feedback_callback
        )
        
        # Add callback for when goal is accepted/rejected
        send_goal_future.add_done_callback(
            lambda future: self._goal_response_callback(future, animation_name)
        )
    
    def _goal_response_callback(self, future, animation_name):
        """Handle the goal response from the action server"""
        try:
            goal_handle = future.result()
            
            if not goal_handle.accepted:
                self.get_logger().warn(f'Animation goal rejected: {animation_name}')
                return
            
            self.get_logger().info(f'Animation goal accepted: {animation_name}')
            self._active_goal_handle = goal_handle
            
            # Get the result asynchronously
            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(
                lambda future: self._get_result_callback(future, animation_name)
            )
            
        except Exception as e:
            self.get_logger().error(f"Error in goal response callback: {e}")
    
    def _get_result_callback(self, future, animation_name):
        """Handle the result of the animation"""
        try:
            result = future.result().result
            
            if result.success:
                self.get_logger().info(
                    f"Emotion-triggered animation completed: {animation_name} "
                    f"(duration: {result.actual_duration:.1f}s)"
                )
            else:
                self.get_logger().warn(
                    f"Emotion-triggered animation failed: {animation_name} - {result.message}"
                )
                
            # Clear the active goal handle
            self._active_goal_handle = None
            
        except Exception as e:
            self.get_logger().error(f"Error in result callback: {e}")
    
    def _animation_feedback_callback(self, feedback_msg):
        """Handle feedback from the animation action"""
        feedback = feedback_msg.feedback
        
        if self.verbose:
            self.get_logger().debug(
                f"Animation progress: {feedback.progress*100:.1f}% "
                f"(step {feedback.current_keyframe+1}/{feedback.total_keyframes})"
            )
    
    def destroy_node(self):
        """Clean up resources when the node is shut down"""
        # Show shutdown message on framebuffer before cleanup
        if self.enable_framebuffer_display and hasattr(self, 'framebuffer_display'):
            self.get_logger().info("Displaying shutdown message on framebuffer")
            self.framebuffer_display.cleanup()
        
        if hasattr(self, 'camera_retry_timer') and self.camera_retry_timer is not None:
            self.camera_retry_timer.cancel()
            
        if hasattr(self, 'device') and self.device is not None:
            self.get_logger().info("Shutting down camera")
            try:
                self.device.close()
            except:
                pass
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    camera_node = CameraInteraction()
    
    try:
        rclpy.spin(camera_node)
    except KeyboardInterrupt:
        pass
    finally:
        camera_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()