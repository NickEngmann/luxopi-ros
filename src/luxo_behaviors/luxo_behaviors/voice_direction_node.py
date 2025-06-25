#!/usr/bin/env python3
"""
ROS2 Voice Direction Detection Node - Exact copy of vad_doa.py logic
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Bool, String
import numpy as np
import threading
import time
import sys
from .mic_array import MicArray
from .pixel_ring import pixel_ring
import webrtcvad


class VoiceDirectionNode(Node):
    def __init__(self):
        super().__init__('voice_direction_node')
        
        # Configuration exactly matching vad_doa.py
        self.config = {
            'audio': {'rate': 16000, 'channels': 6, 'vad_frames': 20, 'doa_frames': 400},
            'vad': {'aggressiveness': 3, 'speech_ratio': 0.7, 'timeout': 1.5},
            'amplitude': {'min_amplitude': 300, 'peak_ratio': 0.2, 'peak_decay_rate': 0.995},
            'stability': {'history_size': 5, 'max_angular_std': 60, 'smoothing_factor': 0.7},
            'led': {'brightness': 50},
            'debug': {'print_amplitude': True, 'print_confidence': True, 'disable_stability_filter': True, 'print_raw_direction': True},
            'array': {'direction_offset': 250},
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
        
        # Only essential ROS publishers
        self.voice_direction_pub = self.create_publisher(Float32, '/voice/direction', 10)
        self.voice_active_pub = self.create_publisher(Bool, '/voice/active', 10)
        self.voice_follow_pub = self.create_publisher(Float32, '/voice/follow_direction', 10)
        
        # Thread control
        self.running = False
        self.audio_thread = None
        
        # Set LED brightness exactly like vad_doa.py
        if pixel_ring:
            pixel_ring.set_brightness(self.config['led']['brightness'])
        
        self.get_logger().info('Voice Direction Node initialized (Exact vad_doa.py copy)')
        
        # Start audio processing
        self.start_audio_processing()

    def calculate_rms(self, audio_chunk):
        """Calculate Root Mean Square (RMS) amplitude of audio chunk - exactly from vad_doa.py"""
        return np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))
    
    def convert_mic_to_robot_angle(self, mic_angle):
        """Simple conversion for ROS publishing"""
        return -mic_angle
    
    def publish_voice_direction(self, direction):
        """Publish voice direction - minimal ROS addition"""
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
                                        
                                        # Publish for ROS (instead of print)
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
                                            
                                            # Publish for ROS (instead of print)
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