#!/usr/bin/env python3
"""
ROS2 Voice Direction Detection Node - Exact copy of vad_doa.py logic
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Bool, String
from sensor_msgs.msg import JointState
import numpy as np
import threading
import time
import sys
import os
import contextlib
from .mic_array import MicArray
from .pixel_ring import pixel_ring
import webrtcvad

# Suppress ALSA warnings
os.environ['ALSA_PCM_CARD'] = 'default'
os.environ['ALSA_PCM_DEVICE'] = '0'


@contextlib.contextmanager
def suppress_alsa_warnings():
    """Context manager to suppress ALSA error messages"""
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(devnull)


class VoiceDirectionNode(Node):
    def __init__(self):
        super().__init__('voice_direction_node')
        
        # Configuration exactly matching vad_doa.py
        self.config = {
            'audio': {'rate': 16000, 'channels': 6, 'vad_frames': 30, 'doa_frames': 400},
            'vad': {'aggressiveness': 3, 'speech_ratio': 0.8, 'timeout': 1.5},
            'amplitude': {'min_amplitude': 300, 'peak_ratio': 0.2, 'peak_decay_rate': 0.995},
            'stability': {'history_size': 5, 'max_angular_std': 60, 'smoothing_factor': 0.7},
            'led': {'brightness': 50},
            'debug': {'print_amplitude': True, 'print_confidence': True, 'disable_stability_filter': True, 'print_raw_direction': True},
            'array': {'direction_offset': 250},
            # NEW: Motor state awareness configuration
            'motor_awareness': {
                'enable': True,
                'base_velocity_threshold': 0.05,  # rad/s - threshold for "motor active"
                'position_change_threshold': 0.02,  # rad - threshold for significant position change
                'suppression_duration': 1.5,  # seconds to suppress voice after motor activity
                'cooldown_duration': 0.5,  # seconds to wait before re-enabling after motor stops
                'monitoring_window': 0.5  # seconds of history to check for motor activity
            }
        }
        
        # Extract configuration values exactly like vad_doa.py
        self.RATE = self.config['audio']['rate']
        self.CHANNELS = self.config['audio']['channels']
        self.VAD_FRAMES = self.config['audio']['vad_frames']
        self.DOA_FRAMES = self.config['audio']['doa_frames']
        self.MIN_AMPLITUDE_THRESHOLD = self.config['amplitude']['min_amplitude']
        self.PEAK_AMPLITUDE_RATIO = self.config['amplitude']['peak_ratio']
        
        # Initialize VAD exactly like vad_doa.py
        self.vad = webrtcvad.Vad(self.config['vad']['aggressiveness'])
        
        # Variables exactly matching vad_doa.py
        self.speech_count = 0
        self.chunks = []
        self.doa_chunks = int(self.DOA_FRAMES / self.VAD_FRAMES)
        self.last_speech_time = time.time()
        self.last_direction = None
        self.leds_on = False
        self.recent_peak_amplitude = self.MIN_AMPLITUDE_THRESHOLD
        self.amplitude_decay_rate = self.config['amplitude']['peak_decay_rate']
        self.direction_history = []
        self.history_size = self.config['stability']['history_size']
        self.max_angular_std = self.config['stability']['max_angular_std']
        
        # Motor state awareness variables
        self.motor_awareness_enabled = self.config['motor_awareness']['enable']
        self.base_velocity_threshold = self.config['motor_awareness']['base_velocity_threshold']
        self.position_change_threshold = self.config['motor_awareness']['position_change_threshold']
        self.suppression_duration = self.config['motor_awareness']['suppression_duration']
        self.cooldown_duration = self.config['motor_awareness']['cooldown_duration']
        self.monitoring_window = self.config['motor_awareness']['monitoring_window']
        
        # Motor state tracking
        self.current_base_position = 0.0
        self.current_base_velocity = 0.0
        self.base_position_history = []  # Store (timestamp, position) tuples
        self.last_motor_activity_time = None
        self.voice_processing_suppressed = False
        self.motor_state_lock = threading.Lock()
        
        # Only essential ROS publishers
        self.voice_direction_pub = self.create_publisher(Float32, '/voice/direction', 10)
        self.voice_active_pub = self.create_publisher(Bool, '/voice/active', 10)
        self.voice_follow_pub = self.create_publisher(Float32, '/voice/follow_direction', 10)
        
        # Joint state subscription for motor monitoring
        self.joint_state_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_state_callback,
            10
        )
        
        # Thread control
        self.running = False
        self.audio_thread = None
        
        # Set LED brightness exactly like vad_doa.py
        if pixel_ring:
            pixel_ring.set_brightness(self.config['led']['brightness'])
        
        self.get_logger().info(f'Voice Direction Node initialized with motor awareness: {self.motor_awareness_enabled}')
        
        # Start audio processing
        self.start_audio_processing()

    def joint_state_callback(self, msg):
        """Monitor joint states for base motor activity"""
        if not self.motor_awareness_enabled:
            return
            
        try:
            current_time = time.time()
            
            # Find base joint index
            base_index = None
            for i, name in enumerate(msg.name):
                if name in ['base', 'base_to_L1']:
                    base_index = i
                    break
            
            if base_index is None or base_index >= len(msg.position):
                return
            
            new_base_position = msg.position[base_index]
            
            with self.motor_state_lock:
                # Calculate velocity if we have velocity data
                if len(msg.velocity) > base_index:
                    self.current_base_velocity = abs(msg.velocity[base_index])
                else:
                    # Estimate velocity from position history
                    if self.base_position_history:
                        last_time, last_pos = self.base_position_history[-1]
                        dt = current_time - last_time
                        if dt > 0:
                            # Handle angle wraparound
                            pos_diff = new_base_position - last_pos
                            if pos_diff > np.pi:
                                pos_diff -= 2 * np.pi
                            elif pos_diff < -np.pi:
                                pos_diff += 2 * np.pi
                            self.current_base_velocity = abs(pos_diff / dt)
                    else:
                        self.current_base_velocity = 0.0
                
                # Update position history
                self.base_position_history.append((current_time, new_base_position))
                
                # Keep only recent history
                cutoff_time = current_time - self.monitoring_window
                self.base_position_history = [
                    (t, p) for t, p in self.base_position_history if t > cutoff_time
                ]
                
                # Check for motor activity
                motor_active = self._is_motor_active(current_time)
                
                if motor_active:
                    self.last_motor_activity_time = current_time
                    if not self.voice_processing_suppressed:
                        self.voice_processing_suppressed = True
                        self.get_logger().info(f"Motor activity detected (vel: {self.current_base_velocity:.3f} rad/s) - suppressing voice processing")
                
                # Check if we should re-enable voice processing
                elif self.voice_processing_suppressed and self.last_motor_activity_time:
                    time_since_activity = current_time - self.last_motor_activity_time
                    if time_since_activity > self.cooldown_duration:
                        self.voice_processing_suppressed = False
                        self.get_logger().info(f"Motor stopped for {time_since_activity:.1f}s - re-enabling voice processing")
                
                self.current_base_position = new_base_position
                
        except Exception as e:
            self.get_logger().error(f"Error in joint state callback: {e}")

    def _is_motor_active(self, current_time):
        """Determine if the base motor is currently active"""
        # Check velocity threshold
        if self.current_base_velocity > self.base_velocity_threshold:
            return True
        
        # Check for significant position changes over monitoring window
        if len(self.base_position_history) < 2:
            return False
        
        oldest_time, oldest_pos = self.base_position_history[0]
        latest_time, latest_pos = self.base_position_history[-1]
        
        # Calculate total position change over monitoring window
        pos_change = abs(latest_pos - oldest_pos)
        # Handle wraparound
        if pos_change > np.pi:
            pos_change = 2 * np.pi - pos_change
        
        time_span = latest_time - oldest_time
        
        # If significant position change in monitoring window, motor is active
        if pos_change > self.position_change_threshold and time_span > 0.1:
            return True
        
        return False

    def _should_suppress_voice_processing(self):
        """Check if voice processing should be suppressed due to motor activity"""
        if not self.motor_awareness_enabled:
            return False
        
        with self.motor_state_lock:
            current_time = time.time()
            
            # Suppress if currently suppressed due to recent motor activity
            if self.voice_processing_suppressed:
                return True
            
            # Also suppress for a period after motor activity stops
            if self.last_motor_activity_time:
                time_since_activity = current_time - self.last_motor_activity_time
                if time_since_activity < self.suppression_duration:
                    return True
        
        return False

    def calculate_rms(self, audio_chunk):
        """Calculate Root Mean Square (RMS) amplitude of audio chunk - exactly from vad_doa.py"""
        return np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))
    
    def convert_mic_to_robot_angle(self, mic_angle):
        """Simple conversion for ROS publishing"""
        return -mic_angle
    
    def publish_voice_direction(self, direction):
        """Publish voice direction - minimal ROS addition"""
        # Check if we should suppress due to motor activity
        if self._should_suppress_voice_processing():
            self.get_logger().info(f"Suppressing voice direction {direction}° due to motor activity")
            return
        
        robot_angle = self.convert_mic_to_robot_angle(direction)
        
        direction_msg = Float32()
        direction_msg.data = float(robot_angle)
        self.voice_direction_pub.publish(direction_msg)
        
        follow_msg = Float32()
        follow_msg.data = float(robot_angle)
        self.voice_follow_pub.publish(follow_msg)
        
        active_msg = Bool()
        active_msg.data = True
        self.voice_active_pub.publish(active_msg)

    def audio_processing_thread(self):
        """Main audio processing thread - EXACT copy of vad_doa.py main() function"""
        self.get_logger().info('Starting audio processing thread')
        
        try:
            with suppress_alsa_warnings():
                with MicArray(self.RATE, self.CHANNELS, self.RATE * self.VAD_FRAMES / 1000, direction_offset=self.config['array']['direction_offset']) as mic:
                    for chunk in mic.read_chunks():
                        if not self.running:
                            break
                    
                        current_time = time.time()
                        
                        # Calculate chunk amplitude - exactly from vad_doa.py
                        chunk_amplitude = self.calculate_rms(chunk)
                        
                        # Update peak amplitude tracker - exactly from vad_doa.py
                        if chunk_amplitude > self.recent_peak_amplitude:
                            self.recent_peak_amplitude = chunk_amplitude
                        else:
                            self.recent_peak_amplitude *= self.amplitude_decay_rate
                        
                        # Use single channel audio to detect voice activity - exactly from vad_doa.py
                        if self.vad.is_speech(chunk[0::self.CHANNELS].tobytes(), self.RATE):
                            self.speech_count += 1
                            self.last_speech_time = current_time
                            # Skip the sys.stdout.write('1') from vad_doa.py
                        else:
                            # Skip the sys.stdout.write('0') from vad_doa.py
                            pass

                        # Turn off LEDs if no speech for configured timeout - exactly from vad_doa.py
                        if current_time - self.last_speech_time > self.config['vad']['timeout'] and self.leds_on:
                            pixel_ring.off()
                            self.leds_on = False
                            self.direction_history.clear()  # Clear history when speech stops

                        self.chunks.append(chunk)
                        if len(self.chunks) == self.doa_chunks:
                            # Calculate average amplitude over the DOA window - exactly from vad_doa.py
                            frames = np.concatenate(self.chunks)
                            avg_amplitude = self.calculate_rms(frames)
                            
                            # Only process DOA if we have enough speech and sufficient amplitude - exactly from vad_doa.py
                            if self.speech_count > (self.doa_chunks * self.config['vad']['speech_ratio']):
                                # Check if amplitude is sufficient for reliable DOA - exactly from vad_doa.py
                                amplitude_ratio = avg_amplitude / max(self.recent_peak_amplitude, self.MIN_AMPLITUDE_THRESHOLD)
                                
                                if avg_amplitude > self.MIN_AMPLITUDE_THRESHOLD and amplitude_ratio > self.PEAK_AMPLITUDE_RATIO:
                                    direction = mic.get_direction(frames)
                                    
                                    # MOTOR AWARENESS CHECK: Skip processing if motor is active
                                    if self._should_suppress_voice_processing():
                                        self.get_logger().info(f"Suppressing DOA processing due to motor activity")
                                        # Continue with the loop but don't process direction
                                        self.speech_count = 0
                                        self.chunks = []
                                        continue
                                    
                                    # Print raw direction if debugging enabled - from vad_doa.py (but skip print)
                                    if self.config['debug'].get('print_raw_direction', False) and direction is not None:
                                        pass  # Skip print for ROS
                                    
                                    # Add to direction history - exactly from vad_doa.py
                                    if direction is not None:
                                        # Skip stability filtering if disabled for debugging - exactly from vad_doa.py
                                        if self.config['debug'].get('disable_stability_filter', False):
                                            pixel_ring.set_direction(int(direction))
                                            self.leds_on = True
                                            self.last_direction = int(direction)
                                            
                                            # Publish for ROS (instead of print) - with motor awareness
                                            self.publish_voice_direction(direction)
                                            
                                            if self.config['debug']['print_amplitude']:
                                                self.get_logger().info(f'{int(direction)}° (amplitude: {int(avg_amplitude)}, ratio: {amplitude_ratio:.2f}) [NO FILTER]')
                                            else:
                                                self.get_logger().info(f'{int(direction)}° [NO FILTER]')
                                        else:
                                            # Apply stability filtering as before - exactly from vad_doa.py
                                            self.direction_history.append(direction)
                                            if len(self.direction_history) > self.history_size:
                                                self.direction_history.pop(0)
                                        
                                        # Only update display if we have enough consistent readings - exactly from vad_doa.py
                                        if len(self.direction_history) >= 2:
                                            # Check for consistency (handle wraparound at 0/360) - exactly from vad_doa.py
                                            angles = np.array(self.direction_history)
                                            # Convert to unit vectors to handle wraparound
                                            x_coords = np.cos(np.radians(angles))
                                            y_coords = np.sin(np.radians(angles))
                                            # Calculate average direction
                                            avg_x = np.mean(x_coords)
                                            avg_y = np.mean(y_coords)
                                            avg_direction = np.degrees(np.arctan2(avg_y, avg_x))
                                            if avg_direction < 0:
                                                avg_direction += 360
                                            
                                            # Calculate angular standard deviation
                                            angular_std = np.degrees(np.sqrt(-np.log(avg_x**2 + avg_y**2)))
                                            
                                            # Only update if directions are reasonably consistent - exactly from vad_doa.py
                                            if angular_std < self.max_angular_std:  # Within configured standard deviation
                                                pixel_ring.set_direction(int(avg_direction))
                                                self.leds_on = True
                                                self.last_direction = int(avg_direction)
                                                
                                                # Publish for ROS (instead of print) - with motor awareness
                                                self.publish_voice_direction(avg_direction)
                                                
                                                if self.config['debug']['print_amplitude']:
                                                    self.get_logger().info(f'{int(avg_direction)}° (amplitude: {int(avg_amplitude)}, ratio: {amplitude_ratio:.2f})')
                                                else:
                                                    self.get_logger().info(f'{int(avg_direction)}°')
                                            else:
                                                self.get_logger().debug(f'[Unstable: std={angular_std:.1f}°]')
                                        else:
                                            # First reading, just store it - from vad_doa.py
                                            self.get_logger().debug('[Acquiring direction...]')
                                else:
                                    # Signal too weak for reliable DOA - exactly from vad_doa.py
                                    self.get_logger().debug(f'[Weak signal: amplitude={int(avg_amplitude)}, ratio={amplitude_ratio:.2f}]')
                            
                            self.speech_count = 0
                            self.chunks = []

        except Exception as e:
            self.get_logger().error(f'Error in audio processing: {e}')
        finally:
            if pixel_ring:
                pixel_ring.off()
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
        
        if pixel_ring:
            pixel_ring.off()
        
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