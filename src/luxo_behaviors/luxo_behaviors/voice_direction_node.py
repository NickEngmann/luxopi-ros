#!/usr/bin/env python3
"""
ROS2 Voice Direction Detection Node
Detects voice direction using ReSpeaker Mic Array and publishes to ROS topics
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32, Bool, String, Header
import numpy as np
import threading
import time
from collections import deque
from .mic_array import MicArray
from .pixel_ring import pixel_ring
    
import webrtcvad


class VoiceDirectionNode(Node):
    def __init__(self):
        super().__init__('voice_direction_node')
        
        # Declare parameters
        self.declare_parameter('sample_rate', 16000)
        self.declare_parameter('channels', 4)
        self.declare_parameter('vad_frames', 10)
        self.declare_parameter('doa_frames', 200)
        self.declare_parameter('vad_aggressiveness', 3)
        self.declare_parameter('confidence_threshold', 0.5)
        self.declare_parameter('publish_rate', 10.0)  # Hz
        self.declare_parameter('enable_pixel_ring', True)
        self.declare_parameter('min_report_interval', 0.5)  # seconds
        self.declare_parameter('direction_smoothing_window', 10)  # Increased from 5
        self.declare_parameter('enable_voice_following', True)
        self.declare_parameter('direction_stability_threshold', 30.0)  # degrees - new parameter
        self.declare_parameter('min_consistent_samples', 3)  # new parameter
        
        # Get parameters
        self.rate = self.get_parameter('sample_rate').value
        self.channels = self.get_parameter('channels').value
        self.vad_frames = self.get_parameter('vad_frames').value
        self.doa_frames = self.get_parameter('doa_frames').value
        self.vad_aggressiveness = self.get_parameter('vad_aggressiveness').value
        self.confidence_threshold = self.get_parameter('confidence_threshold').value
        self.publish_rate = self.get_parameter('publish_rate').value
        self.enable_pixel_ring = self.get_parameter('enable_pixel_ring').value
        self.min_report_interval = self.get_parameter('min_report_interval').value
        self.direction_smoothing_window = self.get_parameter('direction_smoothing_window').value
        self.enable_voice_following = self.get_parameter('enable_voice_following').value
        self.direction_stability_threshold = self.get_parameter('direction_stability_threshold').value
        self.min_consistent_samples = self.get_parameter('min_consistent_samples').value
        
        # Initialize VAD
        self.vad = webrtcvad.Vad(self.vad_aggressiveness)
        
        # Calculate chunk size
        self.chunk_size = int(self.rate * self.vad_frames / 1000)
        self.doa_chunks = int(self.doa_frames / self.vad_frames)
        
        # Enhanced history for better smoothing
        self.direction_history = deque(maxlen=self.direction_smoothing_window)
        self.voice_history = deque(maxlen=10)
        self.raw_direction_buffer = deque(maxlen=20)  # Buffer for raw readings
        
        # State tracking
        self.last_direction = None
        self.last_stable_direction = None  # Last stable direction reported
        self.last_report_time = self.get_clock().now()
        self.voice_active = False
        self.current_confidence = 0.0
        self.consistent_direction_count = 0
        
        # Subscribe to robot state to only activate when appropriate
        self.state_subscriber = self.create_subscription(
            String,
            '/luxo/current_state',
            self.state_callback,
            10
        )
        self.current_state = "UNKNOWN"
        
        # Subscribe to animation status
        self.animation_subscriber = self.create_subscription(
            String,
            '/roarm/current_animation',
            self.animation_callback,
            10
        )
        self.current_animation = None
        
        # Publishers
        self.voice_direction_pub = self.create_publisher(
            Float32,
            '/voice/direction',
            10
        )
        
        self.voice_active_pub = self.create_publisher(
            Bool,
            '/voice/active',
            10
        )
        
        self.voice_confidence_pub = self.create_publisher(
            Float32,
            '/voice/confidence',
            10
        )
        
        # Publisher for detailed voice info (custom message would be better)
        self.voice_info_pub = self.create_publisher(
            String,
            '/voice/info',
            10
        )
        
        # Publisher for voice following command
        self.voice_follow_pub = self.create_publisher(
            Float32,
            '/voice/follow_direction',
            10
        )
        
        # Thread control
        self.running = False
        self.audio_thread = None
        
        # Timer for publishing voice status
        self.status_timer = self.create_timer(1.0 / self.publish_rate, self.publish_voice_status)
        
        self.get_logger().info('Voice Direction Node initialized')
        self.get_logger().info(f'Sample rate: {self.rate} Hz, Channels: {self.channels}')
        self.get_logger().info(f'Voice following enabled: {self.enable_voice_following}')
        self.get_logger().info(f'Direction stability threshold: {self.direction_stability_threshold}°')
        
        # Start audio processing
        self.start_audio_processing()
    
    def state_callback(self, msg):
        """Update current robot state"""
        self.current_state = msg.data
    
    def animation_callback(self, msg):
        """Update current animation"""
        self.current_animation = msg.data if msg.data else None
    
    def should_process_voice(self):
        """Check if we should process voice based on robot state"""
        # Only process voice in IDLE or ANIMATING states
        allowed_states = ['IDLE', 'ANIMATING', 'EMOTION_REACTING']
        return self.current_state in allowed_states
    
    def get_stable_direction(self, new_direction):
        """Enhanced direction stabilization with consistency checking"""
        # Add to raw buffer
        self.raw_direction_buffer.append(new_direction)
        
        if len(self.raw_direction_buffer) < 3:
            return None  # Need more samples
        
        # Calculate circular statistics on recent samples
        recent_samples = list(self.raw_direction_buffer)[-5:]  # Last 5 samples
        angles_rad = np.array([d * np.pi / 180 for d in recent_samples])
        
        # Calculate circular mean
        mean_sin = np.mean(np.sin(angles_rad))
        mean_cos = np.mean(np.cos(angles_rad))
        mean_direction = np.arctan2(mean_sin, mean_cos) * 180 / np.pi
        
        if mean_direction < 0:
            mean_direction += 360
        
        # Calculate circular variance to check consistency
        R = np.sqrt(mean_sin**2 + mean_cos**2)  # Resultant vector length
        circular_variance = 1 - R
        
        # Convert to angular standard deviation (in degrees)
        angular_std = np.sqrt(-2 * np.log(R)) * 180 / np.pi if R > 0 else 180
        
        # Check if directions are consistent enough
        if angular_std < self.direction_stability_threshold:
            # Directions are consistent
            if self.last_stable_direction is None:
                self.consistent_direction_count = 1
            else:
                # Check if this is consistent with last stable direction
                angle_diff = abs(mean_direction - self.last_stable_direction)
                if angle_diff > 180:
                    angle_diff = 360 - angle_diff
                
                if angle_diff < self.direction_stability_threshold:
                    self.consistent_direction_count += 1
                else:
                    self.consistent_direction_count = 1
            
            # Only update stable direction if we have enough consistent samples
            if self.consistent_direction_count >= self.min_consistent_samples:
                self.last_stable_direction = mean_direction
                return int(mean_direction)
        else:
            # Reset consistency count if variance is too high
            self.consistent_direction_count = 0
        
        # Return last stable direction if current samples are inconsistent
        return self.last_stable_direction
    
    def get_smoothed_direction(self, direction):
        """Apply circular mean to smooth direction readings"""
        self.direction_history.append(direction)
        
        if len(self.direction_history) >= 3:
            # Use circular mean for angle averaging
            angles_rad = np.array([d * np.pi / 180 for d in self.direction_history])
            mean_sin = np.mean(np.sin(angles_rad))
            mean_cos = np.mean(np.cos(angles_rad))
            mean_direction = np.arctan2(mean_sin, mean_cos) * 180 / np.pi
            
            # Convert back to 0-359 range
            if mean_direction < 0:
                mean_direction += 360
                
            return int(mean_direction)
        
        return direction
    
    def get_voice_confidence(self):
        """Calculate confidence based on recent voice detections"""
        if len(self.voice_history) > 0:
            return sum(self.voice_history) / len(self.voice_history)
        return 0
    
    def convert_mic_to_robot_angle(self, mic_angle):
        """Convert microphone array angle to robot base angle
        
        The mic array may be mounted differently than the robot's forward direction.
        Adjust this method based on your hardware setup.
        """
        # Assuming mic 0° is robot forward, adjust as needed
        # You might need to add an offset here based on how the mic is mounted
        robot_angle = mic_angle
        
        # Convert to -180 to 180 range for robot base
        if robot_angle > 180:
            robot_angle -= 360
            
        return robot_angle
    
    def publish_voice_direction(self, direction, confidence):
        """Publish voice direction information"""
        current_time = self.get_clock().now()
        
        # Convert mic angle to robot angle
        robot_angle = self.convert_mic_to_robot_angle(direction)
        
        # Publish raw direction
        direction_msg = Float32()
        direction_msg.data = float(robot_angle)
        self.voice_direction_pub.publish(direction_msg)
        
        # Publish confidence
        conf_msg = Float32()
        conf_msg.data = confidence
        self.voice_confidence_pub.publish(conf_msg)
        
        # Publish detailed info
        info_msg = String()
        info_msg.data = f"direction:{robot_angle:.1f},confidence:{confidence:.2f},state:{self.current_state},stable:{self.consistent_direction_count}"
        self.voice_info_pub.publish(info_msg)
        
        # If voice following is enabled and we're in an appropriate state
        if self.enable_voice_following and self.should_process_voice():
            # Publish follow direction command
            follow_msg = Float32()
            follow_msg.data = float(robot_angle)
            self.voice_follow_pub.publish(follow_msg)
            
            self.get_logger().info(
                f'Voice detected at {direction}° (robot: {robot_angle}°) '
                f'with confidence {confidence:.0%}, consistency: {self.consistent_direction_count}'
            )
    
    def publish_voice_status(self):
        """Periodically publish voice activity status"""
        # Publish voice active status
        active_msg = Bool()
        active_msg.data = self.voice_active
        self.voice_active_pub.publish(active_msg)
        
        # Update voice active based on recent detections
        current_time = self.get_clock().now()
        time_since_last = (current_time - self.last_report_time).nanoseconds / 1e9
        
        # Consider voice inactive if no detection for 2 seconds
        if time_since_last > 2.0:
            self.voice_active = False
            self.current_confidence = 0.0
            self.consistent_direction_count = 0  # Reset consistency
            
            # Turn off pixel ring when voice inactive
            if self.enable_pixel_ring and not self.voice_active:
                try:
                    pixel_ring.off()
                except:
                    pass
    
    def audio_processing_thread(self):
        """Main audio processing thread"""
        self.get_logger().info('Starting audio processing thread')
        
        speech_count = 0
        chunks = []
        
        try:
            with MicArray(self.rate, self.channels, self.chunk_size) as mic:
                self.get_logger().info('Microphone array initialized')
                
                for chunk in mic.read_chunks():
                    if not self.running:
                        break
                    
                    # Skip processing if not in appropriate state
                    if not self.should_process_voice():
                        continue
                    
                    # Use single channel audio for VAD
                    mono_audio = chunk[0::self.channels].tobytes()
                    
                    # Check if speech is detected
                    is_speech = self.vad.is_speech(mono_audio, self.rate)
                    self.voice_history.append(is_speech)
                    
                    if is_speech:
                        speech_count += 1
                    
                    # Collect chunks for DOA calculation
                    chunks.append(chunk)
                    
                    if len(chunks) == self.doa_chunks:
                        confidence = self.get_voice_confidence()
                        self.current_confidence = confidence
                        
                        # If enough speech was detected
                        if speech_count > (self.doa_chunks / 2) and confidence >= self.confidence_threshold:
                            # Calculate DOA from accumulated audio
                            frames = np.concatenate(chunks)
                            direction = mic.get_direction(frames)
                            
                            if direction is not None:
                                # Get stable direction with enhanced filtering
                                stable_direction = self.get_stable_direction(direction)
                                
                                if stable_direction is not None:
                                    # Apply additional smoothing
                                    smoothed_direction = self.get_smoothed_direction(stable_direction)
                                    
                                    # Update pixel ring if enabled
                                    if self.enable_pixel_ring:
                                        try:
                                            pixel_ring.set_direction(smoothed_direction)
                                        except:
                                            pass
                                    
                                    # Check if we should report
                                    current_time = self.get_clock().now()
                                    time_since_last = (current_time - self.last_report_time).nanoseconds / 1e9
                                    
                                    if time_since_last >= self.min_report_interval:
                                        self.voice_active = True
                                        self.last_direction = smoothed_direction
                                        self.last_report_time = current_time
                                        
                                        # Publish the direction
                                        self.publish_voice_direction(smoothed_direction, confidence)
                        
                        # Reset for next window
                        speech_count = 0
                        chunks = []
                        
        except Exception as e:
            self.get_logger().error(f'Error in audio processing: {e}')
            import traceback
            traceback.print_exc()
        finally:
            if self.enable_pixel_ring:
                try:
                    pixel_ring.off()
                except:
                    pass
            self.get_logger().info('Audio processing thread stopped')
    
    def start_audio_processing(self):
        """Start the audio processing thread"""
        if not self.running:
            self.running = True
            self.audio_thread = threading.Thread(target=self.audio_processing_thread, daemon=True)
            self.audio_thread.start()
            self.get_logger().info('Audio processing started')
    
    def stop_audio_processing(self):
        """Stop the audio processing thread"""
        if self.running:
            self.running = False
            if self.audio_thread:
                self.audio_thread.join(timeout=2.0)
            self.get_logger().info('Audio processing stopped')
    
    def destroy_node(self):
        """Clean up when node is destroyed"""
        self.get_logger().info('Shutting down Voice Direction Node')
        self.stop_audio_processing()
        
        if self.enable_pixel_ring:
            try:
                pixel_ring.off()
            except:
                pass
        
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = VoiceDirectionNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()