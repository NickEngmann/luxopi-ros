#!/usr/bin/env python3
from pathlib import Path
import threading
import numpy as np
import time
import traceback
from datetime import datetime, timedelta

# Import depthai BEFORE rclpy to avoid context issues
import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, GatherData, ImgDetectionsBridge
from depthai_nodes.node.utils import generate_script_content

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String, Float32, Bool
from sensor_msgs.msg import JointState
from luxo_interfaces.action import PlayAnimation
from diagnostic_msgs.msg import DiagnosticStatus, DiagnosticArray, KeyValue

# Try both import paths for utils
try:
    # When running installed via ros2 run
    from luxo_behaviors.utils.arguments import initialize_argparser
    from luxo_behaviors.utils.annotation_node import AnnotationNode
except ImportError:
    try:
        # When running from source directory
        from utils.arguments import initialize_argparser
        from utils.annotation_node import AnnotationNode
    except ImportError:
        # Fallback with relative import
        from .utils.arguments import initialize_argparser
        from .utils.annotation_node import AnnotationNode

# Define emotions list
emotions = ['neutral', 'happy', 'sad', 'surprise', 'anger']

class CameraInteraction(Node):
    def __init__(self):
        super().__init__('camera_interaction')

        # Initialize ROS2 parameters
        self.declare_parameter('verbose', False)
        self.verbose = self.get_parameter('verbose').get_parameter_value().bool_value

        self.declare_parameter('react_to_emotions', True)
        self.react_to_emotions = self.get_parameter('react_to_emotions').get_parameter_value().bool_value

        self.declare_parameter('emotion_cooldown', 5.0)
        self.emotion_cooldown = self.get_parameter('emotion_cooldown').get_parameter_value().double_value

        # Create ROS publishers
        self.emotion_publisher = self.create_publisher(String, '/camera/emotion', 10)
        self.distance_publisher = self.create_publisher(Float32, '/camera/person_distance', 10)
        self.animation_trigger_publisher = self.create_publisher(String, '/animation_trigger_source', 10)

        # Create action client for animation control
        self._animation_action_client = ActionClient(
            self,
            PlayAnimation,
            'play_animation'
        )

        # Don't wait for action server immediately - it may not be running
        self.get_logger().info('Animation action client created')

        # Track active animation goals
        self._active_goal_handle = None

        # Subscribe to animation and state topics
        self.current_animation_name = None
        self.current_state = "UNKNOWN"

        self.animation_status_sub = self.create_subscription(
            String,
            '/roarm/current_animation',
            self.animation_status_callback,
            10
        )

        self.state_status_sub = self.create_subscription(
            String,
            '/luxo/current_state',
            self.state_status_callback,
            10
        )

        # Subscribe to joint states
        self.joint_states = {}
        self.joint_states_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_states_callback,
            10
        )

        # Track last emotion and animation time
        self.last_emotion = "neutral"
        self.last_animation_time = self.get_clock().now()
        self.last_any_animation_end_time = self.get_clock().now()

        # Map emotions to animations
        self.emotion_to_animation = {
            'happiness': ['excited', 'playful', 'dance'],
            'sadness': ['sad', 'droop'],
            'surprise': ['startled'],
            'anger': ['shake', 'think', 'startled'],
            'fear': ['startled', 'shake', 'settling_adjust', 'neck_stretch'],
            'disgust': ['shake', 'think', 'scanning_watch', 'look_around_casual'],
            'contempt': ['shake', 'shoulder_shimmy', 'pondering', 'attentive_listening'],
            'neutral': ['idle', 'nod']
        }

        # Thread control
        self.shutdown_event = threading.Event()
        self.ros_processing_thread = None
        self.pipeline_thread = None
        self.pipeline_running = False

        # Health monitoring
        self.camera_healthy = False
        self.last_frame_time = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.recovery_attempts = 0
        self.max_recovery_attempts = 10
        self.last_recovery_attempt = None
        self.recovery_backoff = 5.0  # Initial retry delay in seconds
        self.max_backoff = 300.0  # Max 5 minutes between retries

        # Add health check parameters
        self.declare_parameter('health_check_interval', 30.0)
        self.health_check_interval = self.get_parameter('health_check_interval').get_parameter_value().double_value

        self.declare_parameter('frame_timeout', 120.0)
        self.frame_timeout = self.get_parameter('frame_timeout').get_parameter_value().double_value

        # Health publishers
        self.health_publisher = self.create_publisher(Bool, '/camera/health', 10)
        self.diagnostic_publisher = self.create_publisher(DiagnosticArray, '/diagnostics', 10)

        # Optimized resolution for faster processing on RVC2
        self.REQ_WIDTH, self.REQ_HEIGHT = (
            640,
            480,
        )  # Reduced resolution for better performance on RVC2

        # Create health check timer
        self.health_check_timer = self.create_timer(
            self.health_check_interval,
            self.check_camera_health
        )

        # Start camera initialization with recovery
        self.start_camera_initialization()

    def init_camera(self):
        """Initialize camera system - DO NOT MODIFY ANYTHING IN THIS METHOD"""
        # Parse arguments, but filter out ROS2 args first
        import sys
        # Save original args
        original_args = sys.argv

        # Keep only the program name and any non-ROS arguments
        filtered_args = [sys.argv[0]]  # Keep program name

        # Iterate through args and skip ROS2-specific ones
        skip_next = False
        for i, arg in enumerate(sys.argv[1:], 1):
            if skip_next:
                skip_next = False
                continue
            if arg.startswith('--ros-args'):
                continue
            if arg.startswith('--params-file'):
                skip_next = True  # Skip the next arg which is the file path
                continue
            if arg in ['-p', '-r', '--log-level']:
                skip_next = True  # Skip the next arg
                continue
            if ':=' in arg:  # Skip parameter assignments
                continue
            # This is a valid argument for our argparser
            filtered_args.append(arg)

        sys.argv = filtered_args

        _, self.args = initialize_argparser()

        # Restore original args
        sys.argv = original_args

        # Try to create visualizer, but make it optional
        self.visualizer = None
        for port in [8082, 8083, 8084, 8085]:
            try:
                self.visualizer = dai.RemoteConnection(httpPort=port)
                self.get_logger().info(f"Visualizer connected on port {port}")
                break
            except Exception as e:
                if port == 8085:  # Last port
                    self.get_logger().info(f"Running without visualizer (headless mode)")
                    self.visualizer = None
                else:
                    continue

        # RVC2 optimized settings
        self.frame_type = dai.ImgFrame.Type.BGR888p

        if self.args.fps_limit is None:
            self.args.fps_limit = 2
            self.get_logger().info(
                f"FPS limit set to {self.args.fps_limit} for RVC2. Use --fps_limit flag to customize."
            )

        self.create_and_start_pipeline()

    def create_and_start_pipeline(self):
        """Create and start the DepthAI pipeline with monitoring."""
        # Try to create device with better error handling
        try:
            # Close existing device if any
            if hasattr(self, 'device') and self.device:
                try:
                    self.device.close()
                except:
                    pass
                self.device = None

            # Try to connect to device with retries
            max_device_retries = 3
            for retry in range(max_device_retries):
                try:
                    self.device = dai.Device(dai.DeviceInfo(self.args.device)) if self.args.device else dai.Device()
                    platform = self.device.getPlatform().name
                    self.get_logger().info(f"Connected to device. Platform: {platform}")
                    break
                except RuntimeError as e:
                    if retry < max_device_retries - 1:
                        self.get_logger().warn(f"Device connection attempt {retry + 1} failed, retrying...")
                        time.sleep(2)
                    else:
                        raise

            if not self.device:
                raise Exception("Failed to connect to camera device")

            # Start pipeline thread with monitoring
            self.pipeline_running = True
            self.pipeline_thread = threading.Thread(target=self._run_pipeline_with_monitoring, daemon=True)
            self.pipeline_thread.start()

            # Wait briefly to ensure pipeline starts
            time.sleep(2)

        except Exception as e:
            self.get_logger().error(f"Failed to create pipeline: {e}")
            raise

    def _run_pipeline_with_monitoring(self):
        """Run the pipeline with monitoring for crashes."""
        try:
            self._create_and_run_pipeline()
        except Exception as e:
            self.get_logger().error(f"Pipeline crashed: {e}")
            self.get_logger().error(f"Traceback: {traceback.format_exc()}")
            self.pipeline_running = False
            self.camera_healthy = False

            # Trigger recovery
            if not self.shutdown_event.is_set():
                self.get_logger().info("Triggering automatic recovery...")
                self.start_camera_initialization()

    def _create_and_run_pipeline(self):
        """Create and run the pipeline in its own thread with proper context management"""
        # Create pipeline with device passed to context manager, EXACTLY like original
        with dai.Pipeline(self.device) as pipeline:
            self.get_logger().info("Creating pipeline...")

            # Get the path to the models directory
            import os
            # Try multiple possible locations for the model files
            possible_dirs = [
                "/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/depthai_models",
                "/home/pi/luxopi-ros/dev/depthai_models",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "depthai_models"),
                "./depthai_models"
            ]

            models_dir = None
            for dir_path in possible_dirs:
                if os.path.exists(os.path.join(dir_path, "yunet.RVC2.yaml")):
                    models_dir = dir_path
                    self.get_logger().info(f"Found model files in: {models_dir}")
                    break

            if models_dir is None:
                raise FileNotFoundError("Could not find depthai_models directory with yunet.RVC2.yaml")

            # face detection model - RVC2 only
            det_model_description = dai.NNModelDescription.fromYamlFile(
                os.path.join(models_dir, "yunet.RVC2.yaml")
            )
            det_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))
            det_model_w, det_model_h = det_model_nn_archive.getInputSize()

            # emotion recognition model - RVC2 only
            rec_model_description = dai.NNModelDescription.fromYamlFile(
                os.path.join(models_dir, "emotion_recognition.RVC2.yaml")
            )
            rec_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(rec_model_description))

            # media/camera input
            if self.args.media_path:
                replay = pipeline.create(dai.node.ReplayVideo)
                replay.setReplayVideoFile(Path(self.args.media_path))
                replay.setOutFrameType(self.frame_type)
                replay.setLoop(True)
                if self.args.fps_limit:
                    replay.setFps(self.args.fps_limit)
                replay.setSize(self.REQ_WIDTH, self.REQ_HEIGHT)
            else:
                # Optimized camera configuration for RVC2
                cam = pipeline.create(dai.node.Camera).build()
                cam = cam.requestOutput(
                    size=(self.REQ_WIDTH, self.REQ_HEIGHT), type=self.frame_type, fps=self.args.fps_limit
                )
            input_node = replay.out if self.args.media_path else cam

            # resize to det model input size
            resize_node = pipeline.create(dai.node.ImageManip)
            resize_node.initialConfig.setOutputSize(det_model_w, det_model_h)
            resize_node.initialConfig.setReusePreviousImage(False)
            resize_node.inputImage.setBlocking(False)  # Non-blocking for better performance
            input_node.link(resize_node.inputImage)

            # Create the detection neural network node exactly like original
            det_nn = pipeline.create(ParsingNeuralNetwork).build(
                resize_node.out, det_model_nn_archive
            )

            # detection processing
            det_bridge = pipeline.create(ImgDetectionsBridge).build(
                det_nn.out
            )  # TODO: remove once we have it working with ImgDetectionsExtended
            script_node = pipeline.create(dai.node.Script)
            det_bridge.out.link(script_node.inputs["det_in"])
            input_node.link(script_node.inputs["preview"])
            script_content = generate_script_content(
                resize_width=rec_model_nn_archive.getInputWidth(),
                resize_height=rec_model_nn_archive.getInputHeight(),
            )
            script_node.setScript(script_content)

            crop_node = pipeline.create(dai.node.ImageManip)
            crop_node.inputConfig.setWaitForMessage(True)

            script_node.outputs["manip_cfg"].link(crop_node.inputConfig)
            script_node.outputs["manip_img"].link(crop_node.inputImage)

            rec_nn = pipeline.create(ParsingNeuralNetwork).build(
                crop_node.out, rec_model_nn_archive
            )

            # detections and recognitions sync
            gather_data_node = pipeline.create(GatherData).build(self.args.fps_limit)
            rec_nn.out.link(gather_data_node.input_data)
            det_nn.out.link(gather_data_node.input_reference)

            # annotation - this is a HostNode that will process the data
            # Pass our emotion callback to the annotation node
            self.annotation_node = pipeline.create(AnnotationNode).build(
                gather_data_node.out,
                emotion_callback=self.on_emotion_detected
            )

            # Store references for later use
            self.det_nn = det_nn
            self.gather_data_node = gather_data_node
            self.rec_nn = rec_nn

            # visualization - only add if visualizer is available
            if self.visualizer:
                self.visualizer.addTopic("Video", det_nn.passthrough, "images")
                self.visualizer.addTopic("Emotions", self.annotation_node.out, "images")
            else:
                # Create XLinkOut to consume the annotation output when no visualizer
                # This prevents the pipeline from blocking
                xout = pipeline.create(dai.node.XLinkOut)
                xout.setStreamName("annotations_dummy")
                self.annotation_node.out.link(xout.input)

            self.get_logger().info("Pipeline configuration complete.")

            # NOW START THE PIPELINE AND KEEP IT RUNNING WITHIN THIS CONTEXT
            # THIS IS THE KEY - WE MUST STAY WITHIN THE with BLOCK
            self.get_logger().info("Starting pipeline...")
            pipeline.start()

            if self.visualizer:
                self.visualizer.registerPipeline(pipeline)
            else:
                # Create queue to consume dummy output when no visualizer
                self.dummy_queue = self.device.getOutputQueue("annotations_dummy", maxSize=4, blocking=False)

            self.get_logger().info("Camera pipeline started successfully")

            # Count emotions for logging
            self.emotion_count = 0

            # Update last frame time when pipeline starts
            self.last_frame_time = datetime.now()

            # Main loop - EXACTLY like the working example
            # This loop MUST stay within the context manager
            while pipeline.isRunning() and not self.shutdown_event.is_set() and self.pipeline_running:
                current_time = time.time()

                if self.visualizer:
                    key = self.visualizer.waitKey(1)
                    if key == ord("q"):
                        self.get_logger().info("Got q key. Exiting...")
                        break
                else:
                    # No visualizer - consume dummy queue to prevent blocking
                    if hasattr(self, 'dummy_queue'):
                        try:
                            _ = self.dummy_queue.tryGet()
                            # Update frame time to indicate we're still receiving data
                            self.last_frame_time = datetime.now()
                        except:
                            pass
                    time.sleep(0.001)

            self.get_logger().info("Pipeline loop ended")


    def on_emotion_detected(self, emotion: str, confidence: float):
        """Callback when emotion is detected by the annotation node"""
        try:
            # Update frame time
            self.last_frame_time = datetime.now()

            # Increment counter
            if hasattr(self, 'emotion_count'):
                self.emotion_count += 1

            # Publish emotion to ROS topic
            emotion_msg = String()
            emotion_msg.data = emotion
            self.emotion_publisher.publish(emotion_msg)

            if self.verbose:
                self.get_logger().info(f"Published emotion: {emotion} (confidence: {confidence:.2f})")

            # Check if we should trigger animation
            current_time = self.get_clock().now()
            time_since_last = (current_time - self.last_animation_time).nanoseconds / 1e9

            # Only trigger animation if enough time has passed and emotion changed
            if (time_since_last > self.emotion_cooldown and
                emotion != self.last_emotion and
                self.react_to_emotions and
                emotion in self.emotion_to_animation):

                self.trigger_animation(emotion)
                self.last_emotion = emotion

        except Exception as e:
            self.get_logger().error(f"Error in emotion callback: {e}")

    def animation_status_callback(self, msg):
        """Update current animation name and track animation state changes."""
        previous_animation = self.current_animation_name
        self.current_animation_name = msg.data if msg.data else None

        if previous_animation and not self.current_animation_name:
            # Animation just ended
            self.last_any_animation_end_time = self.get_clock().now()
            self.get_logger().debug(f"Animation '{previous_animation}' ended")

    def state_status_callback(self, msg):
        """Update current state machine state."""
        self.current_state = msg.data

    def joint_states_callback(self, msg):
        """Update joint states"""
        import math
        for i, name in enumerate(msg.name):
            if i < len(msg.position):
                # Convert radians to degrees
                angle_deg = math.degrees(msg.position[i])
                self.joint_states[name] = angle_deg

    def trigger_animation(self, emotion, distance=None):
        """Trigger an animation based on detected emotion using the action system"""
        # Check if action server is available
        if not self._animation_action_client.wait_for_server(timeout_sec=0.1):
            self.get_logger().debug("Animation action server not available")
            return

        # Update state with ROS2 time
        self.last_emotion = emotion
        self.last_animation_time = self.get_clock().now()

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

            self.get_logger().debug(f'Animation goal accepted: {animation_name}')
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
            self.last_any_animation_end_time = self.get_clock().now()

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

    def start_camera_initialization(self):
        """Start camera initialization in a separate thread with recovery."""
        if self.pipeline_thread and self.pipeline_thread.is_alive():
            self.get_logger().warn("Pipeline thread already running, skipping initialization")
            return

        init_thread = threading.Thread(target=self._initialize_camera_with_recovery, daemon=True)
        init_thread.start()

    def _initialize_camera_with_recovery(self):
        """Initialize camera with recovery logic."""
        while not self.shutdown_event.is_set() and self.recovery_attempts < self.max_recovery_attempts:
            try:
                # Check if we should wait before retry
                if self.last_recovery_attempt:
                    time_since_last = datetime.now() - self.last_recovery_attempt
                    if time_since_last.total_seconds() < self.recovery_backoff:
                        wait_time = self.recovery_backoff - time_since_last.total_seconds()
                        self.get_logger().info(f"Waiting {wait_time:.1f}s before retry...")
                        time.sleep(wait_time)

                self.last_recovery_attempt = datetime.now()
                self.recovery_attempts += 1

                self.get_logger().info(f"Camera initialization attempt {self.recovery_attempts}/{self.max_recovery_attempts}")

                # Try to initialize camera
                self.init_camera()

                # If we get here, initialization succeeded
                self.get_logger().info("Camera initialized successfully")
                self.camera_healthy = True
                self.consecutive_failures = 0
                self.recovery_attempts = 0
                self.recovery_backoff = 5.0  # Reset backoff
                self.publish_health_status(True)
                return

            except Exception as e:
                self.get_logger().error(f"Camera initialization failed: {e}")
                self.get_logger().error(f"Traceback: {traceback.format_exc()}")

                # Exponential backoff
                self.recovery_backoff = min(self.recovery_backoff * 2, self.max_backoff)

                # Cleanup any partial initialization
                self.cleanup_camera()

                # Publish health status
                self.publish_health_status(False)

                if self.recovery_attempts >= self.max_recovery_attempts:
                    self.get_logger().error(f"Max recovery attempts ({self.max_recovery_attempts}) reached. Giving up.")
                    break

    def check_camera_health(self):
        """Periodic health check for the camera."""
        try:
            # Check if pipeline thread is alive
            if self.pipeline_thread and not self.pipeline_thread.is_alive():
                self.get_logger().warn("Pipeline thread died, triggering recovery")
                self.camera_healthy = False
                self.pipeline_running = False
                self.publish_health_status(False)
                self.start_camera_initialization()
                return

            # Check for frame timeout
            if self.last_frame_time:
                time_since_frame = (datetime.now() - self.last_frame_time).total_seconds()
                if time_since_frame > self.frame_timeout:
                    self.get_logger().warn(f"No frames for {time_since_frame:.1f}s, camera may be frozen")
                    self.consecutive_failures += 1

                    if self.consecutive_failures >= self.max_consecutive_failures:
                        self.get_logger().error("Max consecutive failures reached, triggering recovery")
                        self.camera_healthy = False
                        self.publish_health_status(False)

                        # Stop current pipeline
                        self.pipeline_running = False
                        self.cleanup_camera()

                        # Start recovery
                        self.start_camera_initialization()
                else:
                    self.consecutive_failures = 0
                    if not self.camera_healthy:
                        self.camera_healthy = True
                        self.publish_health_status(True)

            # Publish diagnostic info
            self.publish_diagnostics()

        except Exception as e:
            self.get_logger().error(f"Error in health check: {e}")

    def publish_health_status(self, healthy):
        """Publish camera health status."""
        msg = Bool()
        msg.data = healthy
        self.health_publisher.publish(msg)

    def publish_diagnostics(self):
        """Publish detailed diagnostic information."""
        diag_array = DiagnosticArray()
        diag_array.header.stamp = self.get_clock().now().to_msg()

        status = DiagnosticStatus()
        status.name = "camera_interaction"
        status.hardware_id = "oak-d"

        if self.camera_healthy:
            status.level = DiagnosticStatus.OK
            status.message = "Camera operating normally"
        elif self.pipeline_running:
            status.level = DiagnosticStatus.WARN
            status.message = f"Camera degraded - {self.consecutive_failures} failures"
        else:
            status.level = DiagnosticStatus.ERROR
            status.message = f"Camera offline - recovery attempt {self.recovery_attempts}"

        # Add diagnostic values
        status.values = [
            KeyValue(key="healthy", value=str(self.camera_healthy)),
            KeyValue(key="pipeline_running", value=str(self.pipeline_running)),
            KeyValue(key="consecutive_failures", value=str(self.consecutive_failures)),
            KeyValue(key="recovery_attempts", value=str(self.recovery_attempts)),
            KeyValue(key="recovery_backoff", value=f"{self.recovery_backoff:.1f}s"),
        ]

        if self.last_frame_time:
            time_since_frame = (datetime.now() - self.last_frame_time).total_seconds()
            status.values.append(KeyValue(key="time_since_frame", value=f"{time_since_frame:.1f}s"))

        if self.last_recovery_attempt:
            time_since_recovery = (datetime.now() - self.last_recovery_attempt).total_seconds()
            status.values.append(KeyValue(key="time_since_recovery", value=f"{time_since_recovery:.1f}s"))

        diag_array.status = [status]
        self.diagnostic_publisher.publish(diag_array)

    def cleanup_camera(self):
        """Clean up camera resources."""
        try:
            # Stop pipeline
            self.pipeline_running = False

            # Close device
            if hasattr(self, 'device') and self.device:
                try:
                    self.device.close()
                except:
                    pass
                self.device = None

            # Wait for thread to finish
            if self.pipeline_thread and self.pipeline_thread.is_alive():
                self.pipeline_thread.join(timeout=5.0)

            self.pipeline_thread = None

        except Exception as e:
            self.get_logger().error(f"Error during cleanup: {e}")

    def destroy_node(self):
        """Clean up resources when the node is shut down"""
        # Signal threads to stop
        self.shutdown_event.set()
        self.pipeline_running = False

        # Cancel health check timer if it exists
        if hasattr(self, 'health_check_timer'):
            self.health_check_timer.cancel()

        # Clean up camera
        self.cleanup_camera()

        # Wait for ROS processing thread to finish
        if hasattr(self, 'ros_processing_thread') and self.ros_processing_thread and self.ros_processing_thread.is_alive():
            self.get_logger().info("Waiting for ROS processing thread to stop...")
            self.ros_processing_thread.join(timeout=2.0)

        # Close camera device
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
