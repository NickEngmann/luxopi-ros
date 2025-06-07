#!/usr/bin/env python3
"""
Debug version of ROS2 Voice Direction Detection Node
Enhanced with debugging output to diagnose voice detection issues
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
        self.declare_parameter('direction_smoothing_window', 5)
        self.declare_parameter('enable_voice_following', True)
        self.declare_parameter('direction_stability_threshold', 90.0)  # degrees
        self.declare_parameter('min_consistent_samples', 1)
        self.declare_parameter('debug_mode', True)  # Add debug parameter
        self.declare_parameter('bypass_state_check', True)  # Bypass state checking for debugging
        
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
        self.bypass_state_check = self.get_parameter('bypass_state_check').value
        self.debug_mode = False
        
        # Initialize VAD
        self.vad = webrtcvad.Vad(self.vad_aggressiveness)
        
        # Calculate chunk size
        self.chunk_size = int(self.rate * self.vad_frames / 1000)
        self.doa_chunks = int(self.doa_frames / self.vad_frames)
        
        # Enhanced history for better smoothing
        self.direction_history = deque(maxlen=self.direction_smoothing_window)
        self.voice_history = deque(maxlen=10)
        self.raw_direction_buffer = deque(maxlen=10)
        
        # State tracking
        self.last_direction = None
        self.last_stable_direction = None
        self.last_report_time = self.get_clock().now()
        self.voice_active = False
        self.current_confidence = 0.0
        self.consistent_direction_count = 0
        self.current_state = "UNKNOWN"
        self.current_animation = None
        
        # Debug counters
        self.audio_chunks_received = 0
        self.speech_detections = 0
        self.direction_calculations = 0
        self.messages_published = 0
        
        # Subscribe to robot state
        self.state_subscriber = self.create_subscription(
            String,
            '/luxo/current_state',
            self.state_callback,
            10
        )
        
        # Subscribe to animation status
        self.animation_subscriber = self.create_subscription(
            String,
            '/roarm/current_animation',
            self.animation_callback,
            10
        )
        
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
        
        self.voice_info_pub = self.create_publisher(
            String,
            '/voice/info',
            10
        )
        
        self.voice_follow_pub = self.create_publisher(
            Float32,
            '/voice/follow_direction',
            10
        )
        
        # Debug publisher
        self.debug_pub = self.create_publisher(
            String,
            '/voice/debug',
            10
        )
        
        # Thread control
        self.running = False
        self.audio_thread = None
        
        # Timer for publishing voice status
        self.status_timer = self.create_timer(1.0 / self.publish_rate, self.publish_voice_status)
        
        # Debug timer
        if self.debug_mode:
            self.debug_timer = self.create_timer(2.0, self.publish_debug_info)
        
        self.get_logger().info('Voice Direction Node initialized (DEBUG MODE)')
        self.get_logger().info(f'Sample rate: {self.rate} Hz, Channels: {self.channels}')
        self.get_logger().info(f'Voice following enabled: {self.enable_voice_following}')
        self.get_logger().info(f'Direction stability threshold: {self.direction_stability_threshold}°')
        self.get_logger().info(f'Bypass state check: {self.bypass_state_check}')
        self.get_logger().info(f'Debug mode: {self.debug_mode}')
        
        # Start audio processing
        self.start_audio_processing()
    
    def publish_debug_info(self):
        """Publish debug information periodically"""
        debug_msg = String()
        debug_msg.data = (
            f"chunks:{self.audio_chunks_received}, "
            f"speech:{self.speech_detections}, "
            f"directions:{self.direction_calculations}, "
            f"published:{self.messages_published}, "
            f"state:{self.current_state}, "
            f"confidence:{self.current_confidence:.2f}, "
            f"active:{self.voice_active}"
        )
        self.debug_pub.publish(debug_msg)
        
        if self.debug_mode:
            self.get_logger().info(f"[DEBUG] {debug_msg.data}")
    
    def state_callback(self, msg):
        """Update current robot state"""
        self.current_state = msg.data
        if self.debug_mode:
            self.get_logger().info(f"Robot state updated: {self.current_state}")
    
    def animation_callback(self, msg):
        """Update current animation"""
        self.current_animation = msg.data if msg.data else None
    
    def should_process_voice(self):
        """Check if we should process voice based on robot state"""
        if self.bypass_state_check:
            return True
            
        allowed_states = ['IDLE', 'ANIMATING', 'EMOTION_REACTING']
        return self.current_state in allowed_states
    
    
    def get_stable_direction(self, new_direction):
        """Simple direction stabilization that filters large jumps"""
        self.raw_direction_buffer.append(new_direction)
        
        # Need at least one sample to start
        if len(self.raw_direction_buffer) < 1:
            return None
        
        # If this is our first direction, accept it
        if self.last_stable_direction is None:
            self.last_stable_direction = new_direction
            self.consistent_direction_count = 1
            if self.debug_mode:
                self.get_logger().info(f"Initial direction: {new_direction}°")
            return None  # Still need more samples
        
        # Calculate angular difference from last stable direction
        angle_diff = abs(new_direction - self.last_stable_direction)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        
        # If direction is consistent (within threshold)
        if angle_diff < self.direction_stability_threshold:
            self.consistent_direction_count += 1
            
            # Update stable direction with smoothing
            alpha = 0.3  # Smoothing factor (0.3 = 30% new, 70% old)
            
            # Circular interpolation
            old_rad = self.last_stable_direction * np.pi / 180
            new_rad = new_direction * np.pi / 180
            
            # Handle wrap-around
            if angle_diff > 90:  # Large enough that we need circular interp
                x = (1 - alpha) * np.cos(old_rad) + alpha * np.cos(new_rad)
                y = (1 - alpha) * np.sin(old_rad) + alpha * np.sin(new_rad)
                smoothed = np.arctan2(y, x) * 180 / np.pi
                if smoothed < 0:
                    smoothed += 360
                self.last_stable_direction = smoothed
            else:
                # Small difference, simple interpolation is fine
                self.last_stable_direction = (1 - alpha) * self.last_stable_direction + alpha * new_direction
            
            if self.debug_mode:
                self.get_logger().debug(
                    f"Direction {new_direction}° consistent (diff: {angle_diff:.1f}°, "
                    f"count: {self.consistent_direction_count}, stable: {self.last_stable_direction:.1f}°)"
                )
            
            # Return stable direction if we have enough samples
            if self.consistent_direction_count >= self.min_consistent_samples:
                return int(self.last_stable_direction)
        else:
            # Large jump detected
            if self.debug_mode:
                self.get_logger().debug(
                    f"Direction jump: {self.last_stable_direction:.1f}° -> {new_direction}° "
                    f"(diff: {angle_diff:.1f}°), ignoring"
                )
            
            # Don't reset count to 0, just don't increment
            # This allows recovery from occasional bad readings
        
        return None
    
    def get_smoothed_direction(self, direction):
        """Apply circular mean to smooth direction readings"""
        self.direction_history.append(direction)
        
        if len(self.direction_history) >= 2:
            angles_rad = np.array([d * np.pi / 180 for d in self.direction_history])
            mean_sin = np.mean(np.sin(angles_rad))
            mean_cos = np.mean(np.cos(angles_rad))
            mean_direction = np.arctan2(mean_sin, mean_cos) * 180 / np.pi
            
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
        info_msg.data = (
            f"direction:{robot_angle:.1f},confidence:{confidence:.2f},"
            f"state:{self.current_state},stable:{self.consistent_direction_count}"
        )
        self.voice_info_pub.publish(info_msg)
        
        # Always publish follow direction if voice following is enabled
        if self.enable_voice_following:
            follow_msg = Float32()
            follow_msg.data = float(robot_angle)
            self.voice_follow_pub.publish(follow_msg)
            
            self.get_logger().info(
                f'[VOICE DETECTED] Direction: {direction}° (robot: {robot_angle}°) '
                f'confidence: {confidence:.0%}, consistency: {self.consistent_direction_count}'
            )
        
        self.messages_published += 1
    
    def publish_voice_status(self):
        """Periodically publish voice activity status"""
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
                self.get_logger().info('Microphone array initialized successfully')
                
                for chunk in mic.read_chunks():
                    if not self.running:
                        break
                    
                    self.audio_chunks_received += 1
                    
                    # Log every 100th chunk in debug mode
                    if self.debug_mode and self.audio_chunks_received % 100 == 0:
                        self.get_logger().info(f"Received {self.audio_chunks_received} audio chunks")
                    
                    # Check if we should process (with bypass option)
                    if not self.should_process_voice():
                        if self.debug_mode and self.audio_chunks_received % 100 == 0:
                            self.get_logger().info(f"Skipping processing - state: {self.current_state}")
                        continue
                    
                    # Use single channel audio for VAD
                    mono_audio = chunk[0::self.channels].tobytes()
                    
                    # Check if speech is detected
                    is_speech = self.vad.is_speech(mono_audio, self.rate)
                    self.voice_history.append(is_speech)
                    
                    if is_speech:
                        speech_count += 1
                        self.speech_detections += 1
                    
                    # Collect chunks for DOA calculation
                    chunks.append(chunk)
                    
                    if len(chunks) == self.doa_chunks:
                        confidence = self.get_voice_confidence()
                        self.current_confidence = confidence
                        
                        # Log VAD window results
                        if self.debug_mode:
                            self.get_logger().info(
                                f"VAD window complete: speech_count={speech_count}/{self.doa_chunks}, "
                                f"confidence={confidence:.2f}, threshold={self.confidence_threshold}"
                            )
                        
                        # Lower the speech detection requirement for debugging
                        min_speech_chunks = self.doa_chunks / 4  # Was / 2
                        
                        if speech_count > min_speech_chunks and confidence >= self.confidence_threshold:
                            frames = np.concatenate(chunks)
                            direction = mic.get_direction(frames)
                            
                            if direction is not None:
                                self.direction_calculations += 1
                                
                                if self.debug_mode:
                                    self.get_logger().info(
                                        f"[RAW DIRECTION] {direction}° "
                                        f"(calculation #{self.direction_calculations})"
                                    )
                                
                                # Try with relaxed stability for debugging
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
                                    
                                    # Always publish in debug mode
                                    if self.debug_mode or time_since_last >= self.min_report_interval:
                                        self.voice_active = True
                                        self.last_direction = smoothed_direction
                                        self.last_report_time = current_time
                                        
                                        # Publish the direction
                                        self.publish_voice_direction(smoothed_direction, confidence)
                                else:
                                    if self.debug_mode:
                                        self.get_logger().info(
                                            f"Direction not stable yet: {self.consistent_direction_count}/"
                                            f"{self.min_consistent_samples} samples"
                                        )
                        
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