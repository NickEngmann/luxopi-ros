#!/usr/bin/env python3
"""
Direct framebuffer display module for camera_interaction.py
Enhanced with Lux robot UI design
"""

import numpy as np
import cv2
import os
import struct
import mmap
import fcntl
import threading
import time
import math

class FramebufferDisplay:
    """Direct framebuffer display without using external tools"""
    
    # ioctl constants for framebuffer
    FBIOGET_VSCREENINFO = 0x4600
    FBIOGET_FSCREENINFO = 0x4602
    
    def __init__(self, device='/dev/fb0'):
        self.device = device
        self.fb_file = None
        self.fb_map = None
        self.screen_info = None
        self.width = 0
        self.height = 0
        self.bits_per_pixel = 0
        self.bytes_per_pixel = 0
        self.line_length = 0
        self.screen_size = 0
        self.initialized = False
        self.lock = threading.Lock()
        
        # Try to initialize
        self.initialize()
    
    def initialize(self):
        """Initialize framebuffer access"""
        try:
            # Open framebuffer device
            self.fb_file = os.open(self.device, os.O_RDWR)
            
            # Get variable screen info
            vinfo = bytearray(160)
            fcntl.ioctl(self.fb_file, self.FBIOGET_VSCREENINFO, vinfo)
            
            # Parse screen info
            self.width = struct.unpack('I', vinfo[0:4])[0]
            self.height = struct.unpack('I', vinfo[4:8])[0]
            self.bits_per_pixel = struct.unpack('I', vinfo[24:28])[0]
            self.bytes_per_pixel = self.bits_per_pixel // 8
            
            # Get fixed screen info
            finfo = bytearray(68)
            fcntl.ioctl(self.fb_file, self.FBIOGET_FSCREENINFO, finfo)
            self.line_length = struct.unpack('I', finfo[48:52])[0]
            
            # Calculate screen size
            self.screen_size = self.line_length * self.height
            
            # Memory map the framebuffer
            self.fb_map = mmap.mmap(
                self.fb_file,
                self.screen_size,
                mmap.MAP_SHARED,
                mmap.PROT_READ | mmap.PROT_WRITE
            )
            
            self.initialized = True
            print(f"Framebuffer initialized: {self.width}x{self.height}, "
                  f"{self.bits_per_pixel}bpp, line_length={self.line_length}")
            
            return True
            
        except Exception as e:
            print(f"Failed to initialize framebuffer: {e}")
            self.cleanup()
            return False
    
    def display_frame(self, frame):
        """Display a frame on the framebuffer"""
        if not self.initialized:
            return False
        
        with self.lock:
            try:
                # Resize frame to fit screen
                if frame.shape[0] != self.height or frame.shape[1] != self.width:
                    frame = cv2.resize(frame, (self.width, self.height))
                
                # Convert color format based on framebuffer settings
                if self.bits_per_pixel == 32:
                    # BGRA format (most common)
                    if len(frame.shape) == 2:  # Grayscale
                        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGRA)
                    elif frame.shape[2] == 3:  # BGR
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
                    
                elif self.bits_per_pixel == 24:
                    # BGR format
                    if len(frame.shape) == 2:  # Grayscale
                        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                    # Already BGR, no conversion needed
                    
                elif self.bits_per_pixel == 16:
                    # RGB565 format
                    if len(frame.shape) == 2:  # Grayscale
                        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                    elif frame.shape[2] == 3:
                        # Convert BGR to RGB565
                        b = (frame[:, :, 0] >> 3).astype(np.uint16)
                        g = (frame[:, :, 1] >> 2).astype(np.uint16)
                        r = (frame[:, :, 2] >> 3).astype(np.uint16)
                        frame = (r << 11) | (g << 5) | b
                        frame = frame.astype(np.uint16)
                
                # Write to framebuffer
                if self.bits_per_pixel == 16:
                    # Special handling for 16-bit
                    self.fb_map.seek(0)
                    self.fb_map.write(frame.tobytes())
                else:
                    # For 24/32 bit, need to handle line padding
                    for y in range(self.height):
                        start = y * self.line_length
                        end = start + self.width * self.bytes_per_pixel
                        self.fb_map[start:end] = frame[y].tobytes()
                
                return True
                
            except Exception as e:
                print(f"Error displaying frame: {e}")
                return False
    
    def clear(self, color=(0, 0, 0)):
        """Clear the framebuffer with a solid color"""
        if not self.initialized:
            return
        
        with self.lock:
            # Create a solid color frame
            frame = np.full((self.height, self.width, 3), color, dtype=np.uint8)
            self.display_frame(frame)
    
    def cleanup(self):
        """Clean up resources"""
        with self.lock:
            if self.fb_map:
                self.fb_map.close()
                self.fb_map = None
            
            if self.fb_file is not None:
                os.close(self.fb_file)
                self.fb_file = None
            
            self.initialized = False
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()


# Integration code for camera_interaction.py
class CameraFramebufferDisplay:
    """Helper class to integrate Lux robot UI framebuffer display into camera_interaction.py"""
    
    def __init__(self, node, device='/dev/fb0'):
        self.node = node
        self.display = FramebufferDisplay(device)
        self.enabled = self.display.initialized
        
        # Lux robot UI colors
        self.colors = {
            'lux_gold': (120, 220, 255),    # Gold/yellow for Lux name
            'teal': (226, 219, 120),        # Teal for main elements
            'orange': (77, 183, 255),       # Orange for emotions
            'pink': (158, 160, 255),        # Pink for audio
            'purple': (221, 160, 221),      # Purple for joints
            'green': (207, 230, 168),       # Green for state
            'blue': (235, 206, 135),        # Blue for end effector
            'white': (255, 255, 255),
            'gray': (128, 128, 128),
            'dark_gray': (64, 64, 64),
            'black': (0, 0, 0)
        }
        
        # Animation states for visual feedback
        self.animation_time = 0
        self.last_update_time = time.time()
        
        # State mapping for friendly descriptions
        self.state_descriptions = {
            'IDLE': 'Gently swaying, waiting...',
            'OBSERVING': 'Analyzing environment...',
            'THINKING': 'Processing information...',
            'REACHING': 'Moving to target...',
            'GRASPING': 'Carefully picking up...',
            'ANALYZING': 'Understanding what I see...',
            'FRIENDLY_WAVE': 'Saying hello to humans!',
            'CURIOUS_PEEK': "What's that interesting?",
            'LAMP_CURIOUS': 'Bouncing with curiosity...',
            'LAMP_EXCITED': 'Hopping with joy!',
            'LAMP_FOCUSED': 'Intensely studying...',
            'LAMP_PLAYFUL': 'Ready to play!',
            'LAMP_SHY': 'Hiding a bit, feeling bashful...',
            'LAMP_TRACKING': 'Following a human friend...',
            'LAMP_HAPPY': 'Glowing with happiness!',
            'UNKNOWN': 'Initializing...'
        }
        
        # Emotion to mood mapping
        self.emotion_moods = {
            'happy': (':)', 'DETECTING JOY'),
            'sad': (':(', 'SENSING SADNESS'),
            'surprise': (':O', 'FEELING SURPRISE'),
            'anger': ('>:(', 'READING TENSION'),
            'neutral': (':|', 'CALM PRESENCE'),
            None: ('?', 'NO FACE DETECTED')
        }
        
        if not self.enabled:
            self.node.get_logger().warn("Framebuffer display could not be initialized")
    
    def get_friendly_state_info(self, state):
        """Get friendly state name and description"""
        if not state or state == "UNKNOWN":
            return "INITIALIZING", "Starting up systems..."
        
        # Convert technical states to friendly ones
        friendly_states = {
            'IDLE': 'LAMP_IDLE',
            'ANIMATING': 'LAMP_ANIMATING', 
            'EMOTION_REACTING': 'LAMP_EMOTION',
            'VOICE_FOLLOWING': 'LAMP_TRACKING',
            'MANUAL_CONTROL': 'LAMP_FOCUSED'
        }
        
        friendly_state = friendly_states.get(state, state)
        description = self.state_descriptions.get(friendly_state, 'Doing robot things...')
        
        return friendly_state, description
    
    def draw_circular_gauge(self, frame, center, radius, value, max_value, color, label, unit=""):
        """Draw a circular gauge with modern styling"""
        x, y = center
        
        # Background circle
        cv2.circle(frame, center, radius, self.colors['dark_gray'], 2)
        
        # Calculate angle for progress (0 to 270 degrees)
        angle = int((value / max_value) * 270)
        
        # Draw progress arc
        if angle > 0:
            # Create arc points
            arc_thickness = 3
            start_angle = -90  # Start from top
            end_angle = start_angle + angle
            
            # Draw the arc (OpenCV doesn't have a direct arc function, so we'll draw lines)
            for i in range(0, angle, 2):
                current_angle = math.radians(start_angle + i)
                next_angle = math.radians(start_angle + i + 2)
                
                x1 = int(x + (radius - arc_thickness) * math.cos(current_angle))
                y1 = int(y + (radius - arc_thickness) * math.sin(current_angle))
                x2 = int(x + radius * math.cos(current_angle))
                y2 = int(y + radius * math.sin(current_angle))
                
                cv2.line(frame, (x1, y1), (x2, y2), color, 2)
        
        # Label above gauge
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
        label_x = x - label_size[0] // 2
        label_y = y - radius - 10
        cv2.putText(frame, label, (label_x, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.colors['white'], 1)
        
        # Value in center
        value_text = f"{int(value)}{unit}"
        value_size = cv2.getTextSize(value_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        value_x = x - value_size[0] // 2
        value_y = y + value_size[1] // 2
        cv2.putText(frame, value_text, (value_x, value_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors['white'], 1)
    
    def draw_rounded_panel(self, frame, top_left, bottom_right, color, alpha=0.7):
        """Draw a rounded panel with transparency effect"""
        x1, y1 = top_left
        x2, y2 = bottom_right
        
        # Create overlay for transparency
        overlay = frame.copy()
        
        # Draw rounded rectangle (approximated with regular rectangle for simplicity)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        
        # Apply transparency
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        # Draw border
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    
    def draw_touch_sensor_indicator(self, frame, x, y, sensor_name, value):
        """Draw touch sensor status with visual feedback"""
        # Map pressure states to colors and symbols
        pressure_states = {
            0: (self.colors['gray'], "-", "Not Pressed"),
            1: (self.colors['teal'], "1", "Light Touch"),
            2: (self.colors['orange'], "2", "Light Press"),
            3: (self.colors['pink'], "3", "Medium Press"), 
            4: ((0, 165, 255), "4", "Hard Press"),  # Orange-red
            5: ((0, 0, 255), "5", "Very Hard"),     # Red
            6: ((0, 0, 200), "!", "Maximum")        # Dark red
        }
        
        color, symbol, description = pressure_states.get(value, (self.colors['gray'], "?", "Unknown"))
        
        # Draw sensor circle
        radius = 15
        cv2.circle(frame, (x, y), radius, color, -1 if value > 0 else 2)
        
        # Draw symbol in center
        symbol_size = cv2.getTextSize(symbol, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        symbol_x = x - symbol_size[0] // 2
        symbol_y = y + symbol_size[1] // 2
        cv2.putText(frame, symbol, (symbol_x, symbol_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                   self.colors['black'] if value > 0 else color, 1)
        
        # Sensor name below
        name_size = cv2.getTextSize(sensor_name, cv2.FONT_HERSHEY_SIMPLEX, 0.3, 1)[0]
        name_x = x - name_size[0] // 2
        name_y = y + radius + 15
        cv2.putText(frame, sensor_name, (name_x, name_y), cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.colors['white'], 1)
    
    def draw_collision_sensors(self, frame, collision_sensors):
        """Draw collision sensor status"""
        if not collision_sensors:
            return
        
        # Position collision sensors in top-right area
        base_x = frame.shape[1] - 100
        base_y = 150
        
        # Head sensor (top)
        head_color = self.colors['orange'] if collision_sensors.get('head', False) else self.colors['gray']
        cv2.rectangle(frame, (base_x - 20, base_y), (base_x + 20, base_y + 15), head_color, -1 if collision_sensors.get('head', False) else 2)
        cv2.putText(frame, "HEAD", (base_x - 15, base_y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.colors['black'] if collision_sensors.get('head', False) else head_color, 1)
        
        # Left and right sensors
        left_color = self.colors['orange'] if collision_sensors.get('left', False) else self.colors['gray']
        right_color = self.colors['orange'] if collision_sensors.get('right', False) else self.colors['gray']
        
        # Left sensor
        cv2.rectangle(frame, (base_x - 45, base_y + 25), (base_x - 25, base_y + 40), left_color, -1 if collision_sensors.get('left', False) else 2)
        cv2.putText(frame, "L", (base_x - 40, base_y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.colors['black'] if collision_sensors.get('left', False) else left_color, 1)
        
        # Right sensor  
        cv2.rectangle(frame, (base_x + 5, base_y + 25), (base_x + 25, base_y + 40), right_color, -1 if collision_sensors.get('right', False) else 2)
        cv2.putText(frame, "R", (base_x + 12, base_y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.colors['black'] if collision_sensors.get('right', False) else right_color, 1)
    
    def draw_audio_visualization(self, frame, voice_info):
        """Draw audio visualization bars"""
        if not voice_info:
            return
        
        # Position audio bars in the voice tracking panel
        bar_x = 120
        bar_y = 250  # Adjusted for new panel position
        bar_width = 4
        bar_spacing = 6
        max_bar_height = 20
        
        # Create animated bars based on voice activity
        active = voice_info.get('active', False)
        confidence = voice_info.get('confidence', 0.0)
        
        # Draw 5 audio bars with animation
        for i in range(5):
            if active:
                # Animate bars when voice is active
                height = int(max_bar_height * (0.3 + 0.7 * confidence * (0.5 + 0.5 * math.sin(self.animation_time * 3 + i))))
            else:
                # Small static bars when inactive
                height = int(max_bar_height * 0.1)
            
            bar_color = self.colors['pink'] if active else self.colors['gray']
            x = bar_x + i * (bar_width + bar_spacing)
            cv2.rectangle(frame, (x, bar_y), (x + bar_width, bar_y - height), bar_color, -1)
        
        # Audio status text
        status_text = "LISTENING" if active else "QUIET"
        cv2.putText(frame, status_text, (bar_x + 40, bar_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.colors['pink'], 1)

    def update_display(self, frame, emotion=None, distance=None, face_bboxes=None, 
                      animation_name=None, state=None, voice_info=None, 
                      system_metrics=None, touch_sensors=None, collision_sensors=None,
                      joint_states=None):
        """Update framebuffer with Lux robot UI design"""
        if not self.enabled:
            return
        
        try:
            # Update animation time
            current_time = time.time()
            dt = current_time - self.last_update_time
            self.animation_time += dt
            self.last_update_time = current_time
            
            # Create display frame
            display_frame = frame.copy()
            
            # Draw face bounding boxes with friendly styling
            if face_bboxes:
                for bbox in face_bboxes:
                    if len(bbox) >= 4:
                        x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
                        # Draw rounded rectangle around face
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), self.colors['teal'], 2)
                        # Add friendly "Face" label
                        cv2.putText(display_frame, "Human Friend", (x1, y1 - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors['teal'], 2)
            
            # === TOP HUD SECTION ===
            
            # Robot name with lamp indicator (top left)
            lamp_color = self.colors['lux_gold']
            # Animate lamp glow
            glow_intensity = int(100 + 50 * math.sin(self.animation_time * 2))
            lamp_glow_color = (min(255, lamp_color[0] + glow_intensity//4), 
                              min(255, lamp_color[1] + glow_intensity//4), 
                              min(255, lamp_color[2] + glow_intensity//4))
            
            # Draw lamp indicator circle
            cv2.circle(display_frame, (60, 40), 8, lamp_glow_color, -1)
            cv2.circle(display_frame, (60, 40), 10, lamp_color, 2)
            
            # Robot name
            cv2.putText(display_frame, "LUX", (80, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, lamp_color, 2)
            
            # System time (top right)
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            time_size = cv2.getTextSize(timestamp, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
            time_x = display_frame.shape[1] - time_size[0] - 20
            cv2.putText(display_frame, timestamp, (time_x, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['teal'], 1)
            
            # === SYSTEM GAUGES (top right area) ===
            if system_metrics:
                gauge_centers = [
                    (display_frame.shape[1] - 120, 80),   # Temp
                    (display_frame.shape[1] - 180, 130),  # CPU  
                    (display_frame.shape[1] - 60, 130)    # RAM
                ]
                
                metrics = [
                    (system_metrics.get('temperature', 55), 100, self.colors['pink'], "TEMP", "C"),
                    (system_metrics.get('cpu_usage', 35), 100, self.colors['green'], "CPU", "%"),
                    (system_metrics.get('ram_usage', 62), 100, self.colors['lux_gold'], "RAM", "%")
                ]
                
                for i, ((value, max_val, color, label, unit), center) in enumerate(zip(metrics, gauge_centers)):
                    self.draw_circular_gauge(display_frame, center, 25, value, max_val, color, label, unit)
            
            # === STATE MACHINE DISPLAY (left side) ===
            if state:
                friendly_state, description = self.get_friendly_state_info(state)
                
                # State panel background
                self.draw_rounded_panel(display_frame, (20, 80), (280, 150), self.colors['dark_gray'], 0.8)
                
                # State label
                cv2.putText(display_frame, "CURRENT STATE", (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.colors['green'], 1)
                
                # State name with glow effect
                cv2.putText(display_frame, friendly_state, (30, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.8, self.colors['green'], 2)
                
                # State description
                cv2.putText(display_frame, description, (30, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.colors['gray'], 1)
            
            # === EMOTION DISPLAY (left side) ===
            emotion_face, emotion_text = self.emotion_moods.get(emotion, self.emotion_moods[None])
            
            # Emotion panel
            self.draw_rounded_panel(display_frame, (20, 160), (280, 210), self.colors['dark_gray'], 0.8)
            
            # Emotion emoji (larger)
            cv2.putText(display_frame, emotion_face, (30, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.0, self.colors['orange'], 2)
            
            # Emotion text
            cv2.putText(display_frame, emotion_text, (70, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['orange'], 1)
            
            # === AUDIO VISUALIZATION (left side) ===
            if voice_info:
                # Audio panel with clearer title
                audio_y = 220
                self.draw_rounded_panel(display_frame, (20, audio_y), (200, audio_y + 50), self.colors['dark_gray'], 0.8)
                
                # Audio title
                cv2.putText(display_frame, "[VOICE TRACKING]", (30, audio_y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.colors['pink'], 1)
                
                # Draw audio bars
                self.draw_audio_visualization(display_frame, voice_info)
                
                # Voice direction if available
                if voice_info.get('direction') is not None:
                    direction_text = f"DIR: {voice_info['direction']:.0f}°"
                    cv2.putText(display_frame, direction_text, (30, audio_y + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.colors['pink'], 1)
                else:
                    cv2.putText(display_frame, "DIR: ---", (30, audio_y + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.colors['gray'], 1)
            
            # === TOUCH SENSORS (left side) ===
            if touch_sensors:
                # Touch panel
                touch_y = 280  # Moved down to accommodate voice panel
                self.draw_rounded_panel(display_frame, (20, touch_y), (200, touch_y + 80), self.colors['dark_gray'], 0.8)
                
                cv2.putText(display_frame, "[TOUCH SENSORS]", (30, touch_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.colors['purple'], 1)
                
                # Draw touch sensors in a head-like pattern
                sensor_positions = {
                    'head_top': (100, touch_y + 35),
                    'head_left': (70, touch_y + 50),
                    'head_right': (130, touch_y + 50),
                    'head_bottom': (100, touch_y + 65)
                }
                
                for sensor_name, (x, y) in sensor_positions.items():
                    value = touch_sensors.get(sensor_name, 0)
                    self.draw_touch_sensor_indicator(display_frame, x, y, sensor_name.split('_')[1].upper(), value)
            
            # === COLLISION SENSORS (top right) ===
            if collision_sensors:
                self.draw_collision_sensors(display_frame, collision_sensors)
            
            # === BOTTOM PANELS ===
            
            # End Effector Panel (bottom right)
            panel_bottom = display_frame.shape[0] - 20
            panel_top = panel_bottom - 100
            panel_right = display_frame.shape[1] - 20
            panel_left = panel_right - 180
            
            self.draw_rounded_panel(display_frame, (panel_left, panel_top), (panel_right, panel_bottom), self.colors['dark_gray'], 0.8)
            
            cv2.putText(display_frame, "[LAMP HEAD]", (panel_left + 10, panel_top + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors['blue'], 1)
            
            # Position info (simulated for now)
            position_y = panel_top + 40
            # Lamp status
            lamp_status = "[LAMP ON]" if (int(self.animation_time) % 3) < 2 else "[LAMP OFF]"  # Simulate lamp control
            lamp_bg_color = self.colors['lux_gold'] if "ON" in lamp_status else self.colors['gray']
            cv2.rectangle(display_frame, (panel_left + 10, panel_bottom - 25), (panel_right - 10, panel_bottom - 5), lamp_bg_color, -1)
            cv2.putText(display_frame, lamp_status, (panel_left + 15, panel_bottom - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.colors['black'], 1)
            
            # Joint Status Panel (bottom left)
            joint_panel_right = display_frame.shape[1] - 200
            joint_panel_left = joint_panel_right - 200
            
            self.draw_rounded_panel(display_frame, (joint_panel_left, panel_top), (joint_panel_right, panel_bottom), self.colors['dark_gray'], 0.8)
            
            cv2.putText(display_frame, "[LAMP JOINTS]", (joint_panel_left + 10, panel_top + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors['purple'], 1)
            
            # Display real joint angles if available, otherwise show offline message
            if joint_states and len(joint_states) > 0:
                # Define expected joint names and their display names
                joint_mapping = {
                    'base_joint': 'Base Rot',
                    'shoulder_joint': 'Shoulder', 
                    'elbow_joint': 'Elbow',
                    'wrist_joint': 'Wrist',
                    'head_pan_joint': 'Head Pan',
                    'head_tilt_joint': 'Head Tilt',
                    'lower_arm_joint': 'Lower Arm',
                    'upper_arm_joint': 'Upper Arm'
                }
                
                # Get available joints from joint_states
                available_joints = []
                for joint_name, display_name in joint_mapping.items():
                    if joint_name in joint_states:
                        angle = joint_states[joint_name]
                        available_joints.append((display_name, f"{angle:.1f}°"))
                
                # If no mapped joints found, show all available joints
                if not available_joints:
                    for joint_name, angle in list(joint_states.items())[:5]:  # Limit to first 5
                        display_name = joint_name.replace('_', ' ').title()
                        available_joints.append((display_name, f"{angle:.1f}°"))
                
                # Display the joints
                joint_y = panel_top + 35
                for i, (joint_name, angle) in enumerate(available_joints[:5]):  # Max 5 joints
                    y_pos = joint_y + i * 12
                    # Truncate long joint names
                    if len(joint_name) > 12:
                        joint_name = joint_name[:12] + "..."
                    
                    cv2.putText(display_frame, joint_name, (joint_panel_left + 10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.colors['purple'], 1)
                    cv2.putText(display_frame, angle, (joint_panel_left + 120, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.colors['lux_gold'], 1)
                
                # Show joint count if we have more than 5
                if len(joint_states) > 5:
                    extra_count = len(joint_states) - 5
                    cv2.putText(display_frame, f"+ {extra_count} more", (joint_panel_left + 10, joint_y + 5 * 12), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.colors['gray'], 1)
            else:
                # Show offline message when no joint data available
                offline_text = "JOINTS OFFLINE"
                cv2.putText(display_frame, offline_text, (joint_panel_left + 10, panel_top + 40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors['gray'], 1)
                
                # Show waiting message
                waiting_text = "Waiting for /joint_states..."
                cv2.putText(display_frame, waiting_text, (joint_panel_left + 10, panel_top + 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.colors['gray'], 1)
            
            # === CENTRAL CROSSHAIR ===
            # Draw friendly crosshair in center
            center_x, center_y = display_frame.shape[1] // 2, display_frame.shape[0] // 2
            
            # Breathing animation
            breath_scale = 1.0 + 0.1 * math.sin(self.animation_time * 1.5)
            crosshair_radius = int(25 * breath_scale)
            
            cv2.circle(display_frame, (center_x, center_y), crosshair_radius, self.colors['lux_gold'], 2)
            cv2.circle(display_frame, (center_x, center_y), 4, self.colors['lux_gold'], -1)
            
            # === CAMERA INFO (bottom center) ===
            camera_info = "[CAM] Lux Vision | 1920x1080@30fps | Raspberry Pi 5"
            info_size = cv2.getTextSize(camera_info, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
            info_x = (display_frame.shape[1] - info_size[0]) // 2
            info_y = display_frame.shape[0] - 10
            
            # Background for camera info
            cv2.rectangle(display_frame, (info_x - 5, info_y - 15), (info_x + info_size[0] + 5, info_y + 5), self.colors['dark_gray'], -1)
            cv2.putText(display_frame, camera_info, (info_x, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.colors['white'], 1)
            
            # === ANIMATED SCAN LINE ===
            # Add subtle scan line animation
            scan_y = int((self.animation_time * 100) % display_frame.shape[0])
            cv2.line(display_frame, (0, scan_y), (display_frame.shape[1], scan_y), (*self.colors['lux_gold'], 50), 2)
            
            # Display the frame
            self.display.display_frame(display_frame)
            
        except Exception as e:
            self.node.get_logger().error(f"Error updating Lux framebuffer display: {e}")
    
    def show_shutdown_message(self):
        """Display a Lux-themed shutdown message before cleanup"""
        if not self.enabled:
            return
            
        try:
            # Create a black frame
            frame = np.zeros((self.display.height, self.display.width, 3), dtype=np.uint8)
            
            # Add Lux shutdown message
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            # Main message
            text = "LUX POWERING DOWN"
            font_scale = 1.5
            thickness = 3
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            
            # Center the text
            x = (frame.shape[1] - text_size[0]) // 2
            y = (frame.shape[0] + text_size[1]) // 2 - 50
            
            # Draw text with glow effect
            cv2.putText(frame, text, (x, y), font, font_scale, (0, 0, 0), thickness + 2)  # Black border
            cv2.putText(frame, text, (x, y), font, font_scale, self.colors['lux_gold'], thickness)  # Gold text
            
            # Add lamp icon
            cv2.circle(frame, (x - 30, y - 15), 15, self.colors['lux_gold'], -1)
            cv2.putText(frame, "[L]", (x - 40, y - 5), font, 1.0, self.colors['black'], 2)
            
            # Add smaller subtitle
            subtitle = "Thank you for playing!"
            font_scale_sub = 1.0
            thickness_sub = 2
            text_size_sub = cv2.getTextSize(subtitle, font, font_scale_sub, thickness_sub)[0]
            x_sub = (frame.shape[1] - text_size_sub[0]) // 2
            y_sub = y + 60
            
            cv2.putText(frame, subtitle, (x_sub, y_sub), font, font_scale_sub, self.colors['teal'], thickness_sub)
            
            # Add timestamp
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            font_scale_ts = 0.7
            thickness_ts = 1
            text_size_ts = cv2.getTextSize(timestamp, font, font_scale_ts, thickness_ts)[0]
            x_ts = (frame.shape[1] - text_size_ts[0]) // 2
            y_ts = y_sub + 40
            
            cv2.putText(frame, timestamp, (x_ts, y_ts), font, font_scale_ts, self.colors['gray'], thickness_ts)
            
            # Display the frame
            self.display.display_frame(frame)
            
            # Keep the message visible for a moment
            import time
            time.sleep(2.0)
            
        except Exception as e:
            self.node.get_logger().error(f"Error displaying Lux shutdown message: {e}")
    
    def clear(self, color=(0, 0, 0)):
        """Clear the display with Lux-themed no signal message"""
        if self.enabled:
            try:
                # Create a frame with Lux colors
                frame = np.full((self.display.height, self.display.width, 3), color, dtype=np.uint8)
                
                # Add Lux-themed "No Signal" message
                font = cv2.FONT_HERSHEY_SIMPLEX
                text = "LUX SLEEPING"
                font_scale = 1.5
                thickness = 2
                text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                
                # Center the text
                x = (frame.shape[1] - text_size[0]) // 2
                y = (frame.shape[0] + text_size[1]) // 2
                
                # Draw text
                cv2.putText(frame, text, (x, y), font, font_scale, self.colors['lux_gold'], thickness)
                
                # Add sleeping lamp icon
                cv2.circle(frame, (x - 30, y - 15), 12, self.colors['gray'], 2)
                cv2.putText(frame, "Z", (x - 35, y - 5), font, 0.8, self.colors['gray'], 1)
                
                self.display.display_frame(frame)
            except Exception as e:
                self.node.get_logger().error(f"Error clearing Lux display: {e}")
                # Fallback to simple clear
                self.display.clear(color)
    
    def cleanup(self):
        """Clean up resources with Lux-themed shutdown"""
        if self.enabled:
            # Show shutdown message first
            self.show_shutdown_message()
            # Then cleanup
            self.display.cleanup()