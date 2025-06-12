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
from std_msgs.msg import Bool

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
            'happy': ('->', 'DETECTING JOY'),
            'sad': ('->', 'SENSING SADNESS'),
            'surprise': ('->', 'FEELING SURPRISE'),
            'anger': ('!', 'READING TENSION'),
            'neutral': ('-', 'NEUTRAL'),
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
        
        # Background circle (larger)
        cv2.circle(frame, center, radius, self.colors['dark_gray'], 3)
        
        # Calculate angle for progress (0 to 270 degrees)
        angle = int((value / max_value) * 270)
        
        # Draw progress arc
        if angle > 0:
            # Create arc points (thicker)
            arc_thickness = 6
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
                
                cv2.line(frame, (x1, y1), (x2, y2), color, 3)
        
        # Label above gauge (larger font)
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        label_x = x - label_size[0] // 2
        label_y = y - radius - 20
        cv2.putText(frame, label, (label_x, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, self.colors['white'], 2)
        
        # Value in center (larger font)
        value_text = f"{int(value)}{unit}"
        value_size = cv2.getTextSize(value_text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
        value_x = x - value_size[0] // 2
        value_y = y + value_size[1] // 2
        cv2.putText(frame, value_text, (value_x, value_y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, self.colors['white'], 2)
    
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
        
        # Draw border (thicker)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
    
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
        
        # Draw sensor circle (larger with more spacing)
        radius = 30
        cv2.circle(frame, (x, y), radius, color, -1 if value > 0 else 3)
        
        # Draw symbol in center (larger font)
        symbol_size = cv2.getTextSize(symbol, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
        symbol_x = x - symbol_size[0] // 2
        symbol_y = y + symbol_size[1] // 2
        cv2.putText(frame, symbol, (symbol_x, symbol_y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 
                   self.colors['black'] if value > 0 else color, 2)
        
        # Sensor name below (larger font with more spacing)
        name_size = cv2.getTextSize(sensor_name, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
        name_x = x - name_size[0] // 2
        name_y = y + radius + 35  # Increased spacing
        cv2.putText(frame, sensor_name, (name_x, name_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['white'], 1)

    def draw_collision_sensors(self, frame, collision_sensors):
        """Draw collision sensor status with improved modern design"""
        if not collision_sensors:
            return
        
        # Position collision sensors in top-right area with better spacing
        base_x = frame.shape[1] - 200
        base_y = 320  # Positioned below system gauges
        
        # Create a larger panel for the collision sensors
        panel_width = 160
        panel_height = 140
        self.draw_rounded_panel(frame, 
                               (base_x - 20, base_y - 20), 
                               (base_x + panel_width, base_y + panel_height), 
                               self.colors['dark_gray'], 0.8)
        
        # Panel title
        cv2.putText(frame, "[COLLISION]", (base_x, base_y + 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.colors['white'], 2)
        
        # Modern sensor indicators with consistent sizing
        sensor_size = 35  # Larger sensors
        sensor_spacing = 50
        
        # Head sensor (top center)
        head_x = base_x + panel_width // 2 - sensor_size // 2
        head_y = base_y + 25
        head_active = collision_sensors.get('head', False)
        head_color = self.colors['orange'] if head_active else self.colors['gray']
        
        # Draw head sensor as rounded rectangle
        cv2.rectangle(frame, (head_x, head_y), (head_x + sensor_size, head_y + 25), 
                     head_color, -1 if head_active else 3)
        
        # Head sensor label
        cv2.putText(frame, "HEAD", (head_x + 2, head_y + 18), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                   self.colors['black'] if head_active else head_color, 1)
        
        # Status indicator dot for head
        dot_color = self.colors['orange'] if head_active else self.colors['dark_gray']
        cv2.circle(frame, (head_x + sensor_size + 5, head_y + 12), 4, dot_color, -1)
        
        # Left sensor (bottom left)
        left_x = base_x + 20
        left_y = base_y + 70
        left_active = collision_sensors.get('left', False)
        left_color = self.colors['orange'] if left_active else self.colors['gray']
        
        # Draw left sensor as rounded rectangle
        cv2.rectangle(frame, (left_x, left_y), (left_x + sensor_size, left_y + 25), 
                     left_color, -1 if left_active else 3)
        
        # Left sensor label
        cv2.putText(frame, "LEFT", (left_x + 4, left_y + 18), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                   self.colors['black'] if left_active else left_color, 1)
        
        # Status indicator dot for left
        dot_color = self.colors['orange'] if left_active else self.colors['dark_gray']
        cv2.circle(frame, (left_x + sensor_size + 5, left_y + 12), 4, dot_color, -1)
        
        # Right sensor (bottom right)
        right_x = base_x + panel_width - sensor_size - 20
        right_y = base_y + 70
        right_active = collision_sensors.get('right', False)
        right_color = self.colors['orange'] if right_active else self.colors['gray']
        
        # Draw right sensor as rounded rectangle
        cv2.rectangle(frame, (right_x, right_y), (right_x + sensor_size, right_y + 25), 
                     right_color, -1 if right_active else 3)
        
        # Right sensor label
        cv2.putText(frame, "RIGHT", (right_x + 2, right_y + 18), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                   self.colors['black'] if right_active else right_color, 1)
        
        # Status indicator dot for right
        dot_color = self.colors['orange'] if right_active else self.colors['dark_gray']
        cv2.circle(frame, (right_x + sensor_size + 5, right_y + 12), 4, dot_color, -1)
        
        # Overall collision status at bottom of panel
        any_collision = any(collision_sensors.values())
        status_text = "COLLISION!" if any_collision else "ALL CLEAR"
        status_color = self.colors['orange'] if any_collision else self.colors['green']
        
        # Center the status text
        status_size = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        status_x = base_x + (panel_width - status_size[0]) // 2
        status_y = base_y + panel_height - 15
        
        cv2.putText(frame, status_text, (status_x, status_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
    
    def draw_audio_visualization(self, frame, voice_info):
        """Draw audio visualization bars"""
        if not voice_info:
            return
        
        # Position audio bars aligned with DIR text (same Y axis)
        bar_x = 180
        bar_y = 500  # Aligned with DIR text position
        bar_width = 8
        bar_spacing = 12
        max_bar_height = 40
        
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
        
        # Audio status text aligned with DIR text (same Y position)
        status_text = "LISTENING" if active else "QUIET"
        cv2.putText(frame, status_text, (bar_x + 100, bar_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['pink'], 1)

    def update_display(self, frame, emotion=None, distance=None, face_bboxes=None, 
                      animation_name=None, state=None, voice_info=None, 
                      system_metrics=None, touch_sensors=None, collision_sensors=None,
                      joint_states=None, lamp_info=None):
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
            
            # Draw face bounding boxes with friendly styling (thicker lines)
            if face_bboxes:
                for bbox in face_bboxes:
                    if len(bbox) >= 4:
                        x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
                        # Draw rounded rectangle around face (thicker)
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), self.colors['teal'], 4)
                        # Add friendly "Face" label (larger font)
                        cv2.putText(display_frame, "Human Friend", (x1, y1 - 15), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, self.colors['teal'], 3)
            
            # === TOP HUD SECTION ===
            
            # Robot name with lamp indicator (top left, larger)
            lamp_color = self.colors['lux_gold']
            # Use lamp_info if provided, otherwise default to off
            current_lamp_status = lamp_info.get('status', False) if lamp_info else False
            # Animate lamp glow only if lamp is actually on
            if current_lamp_status:
                glow_intensity = int(100 + 50 * math.sin(self.animation_time * 2))
                lamp_glow_color = (min(255, lamp_color[0] + glow_intensity//4), 
                                  min(255, lamp_color[1] + glow_intensity//4), 
                                  min(255, lamp_color[2] + glow_intensity//4))
            else:
                # Dim lamp indicator when off
                lamp_glow_color = self.colors['gray']
                lamp_color = self.colors['gray']
            
            # Draw lamp indicator circle (larger)
            cv2.circle(display_frame, (80, 60), 15, lamp_glow_color, -1)
            cv2.circle(display_frame, (80, 60), 18, lamp_color, 3)
            
            # Robot name (much larger)
            cv2.putText(display_frame, "LUX", (110, 75), cv2.FONT_HERSHEY_SIMPLEX, 2.4, lamp_color, 4)
            
            # System time (top right, larger)
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            time_size = cv2.getTextSize(timestamp, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 2)[0]
            time_x = display_frame.shape[1] - time_size[0] - 30
            cv2.putText(display_frame, timestamp, (time_x, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, self.colors['teal'], 2)
            
            # === SYSTEM GAUGES (top right area, moved down to avoid clock overlap) ===
            if system_metrics:
                gauge_centers = [
                    (display_frame.shape[1] - 180, 180),   # Temp - moved down
                    (display_frame.shape[1] - 280, 240),   # CPU - moved down 
                    (display_frame.shape[1] - 80, 240)     # RAM - moved down
                ]
                
                metrics = [
                    (system_metrics.get('temperature', 55), 100, self.colors['pink'], "TEMP", "C"),
                    (system_metrics.get('cpu_usage', 35), 100, self.colors['green'], "CPU", "%"),
                    (system_metrics.get('ram_usage', 62), 100, self.colors['lux_gold'], "RAM", "%")
                ]
                
                for i, ((value, max_val, color, label, unit), center) in enumerate(zip(metrics, gauge_centers)):
                    self.draw_circular_gauge(display_frame, center, 40, value, max_val, color, label, unit)
            
            # === STATE MACHINE DISPLAY (left side, much larger panel) ===
            if state:
                friendly_state, description = self.get_friendly_state_info(state)
                
                # State panel background (increased width by 10%)
                self.draw_rounded_panel(display_frame, (30, 120), (550, 250), self.colors['dark_gray'], 0.8)
                
                # State label (larger font with more spacing)
                cv2.putText(display_frame, "CURRENT STATE", (45, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, self.colors['green'], 2)
                
                # State name with glow effect (larger font with more spacing)
                cv2.putText(display_frame, friendly_state, (45, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.6, self.colors['green'], 3)
                
                # State description (larger font with more spacing)
                cv2.putText(display_frame, description, (45, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.8, self.colors['gray'], 2)
            
            # === EMOTION DISPLAY (left side, much larger panel with more spacing) ===
            emotion_face, emotion_text = self.emotion_moods.get(emotion, self.emotion_moods[None])
            
            # Emotion panel (increased width by 10% and moved down for more spacing)
            self.draw_rounded_panel(display_frame, (30, 280), (550, 380), self.colors['dark_gray'], 0.8)
            
            # Emotion emoji (much larger with more spacing)
            cv2.putText(display_frame, emotion_face, (45, 340), cv2.FONT_HERSHEY_SIMPLEX, 2.0, self.colors['orange'], 4)
            
            # Emotion text (larger with more spacing)
            cv2.putText(display_frame, emotion_text, (140, 340), cv2.FONT_HERSHEY_SIMPLEX, 1.2, self.colors['orange'], 2)
            
            # === AUDIO VISUALIZATION (left side, much larger panel) ===
            if voice_info:
                # Audio panel with clearer title (much larger, moved down for spacing)
                audio_y = 400
                self.draw_rounded_panel(display_frame, (30, audio_y), (400, audio_y + 120), self.colors['dark_gray'], 0.8)
                
                # Audio title (larger font with more spacing)
                cv2.putText(display_frame, "[VOICE TRACKING]", (45, audio_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, self.colors['pink'], 2)
                
                # Draw audio bars (adjusted position)
                self.draw_audio_visualization(display_frame, voice_info)
                
                # Voice direction if available (larger font with more spacing)
                if voice_info.get('direction') is not None:
                    direction_text = f"DIR: {voice_info['direction']:.0f}"
                    cv2.putText(display_frame, direction_text, (45, audio_y + 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.colors['pink'], 1)
                else:
                    cv2.putText(display_frame, "DIR: ---", (45, audio_y + 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.colors['gray'], 1)
            
            # === TOUCH SENSORS (left side, much larger panel) ===
            if touch_sensors:
                # Touch panel (increased height by 15% and moved down for spacing)
                touch_y = 550  # Moved down to accommodate larger panels above
                self.draw_rounded_panel(display_frame, (30, touch_y), (400, touch_y + 230), self.colors['dark_gray'], 0.8)
                
                cv2.putText(display_frame, "[TOUCH SENSORS]", (45, touch_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, self.colors['purple'], 2)
                
                # Draw touch sensors in a head-like pattern (adjusted for larger panel)
                sensor_positions = {
                    'head_top': (215, touch_y + 80),      # Centered horizontally
                    'head_left': (140, touch_y + 130),    # Left side
                    'head_right': (290, touch_y + 130),   # Right side  
                    'head_bottom': (215, touch_y + 180)   # Bottom, more spacing from top
                }
                
                for sensor_name, (x, y) in sensor_positions.items():
                    value = touch_sensors.get(sensor_name, 0)
                    self.draw_touch_sensor_indicator(display_frame, x, y, sensor_name.split('_')[1].upper(), value)
            
            # === COLLISION SENSORS (top right) ===
            if collision_sensors:
                self.draw_collision_sensors(display_frame, collision_sensors)
            
            # === BOTTOM PANELS (much larger) ===
            
            # End Effector Panel (bottom right) - much larger for lamp status
            panel_bottom = display_frame.shape[0] - 40
            panel_top = panel_bottom - 180  # Increased height
            panel_right = display_frame.shape[1] - 40
            panel_left = panel_right - 350  # Increased width
            
            self.draw_rounded_panel(display_frame, (panel_left, panel_top), (panel_right, panel_bottom), self.colors['dark_gray'], 0.8)
            
            cv2.putText(display_frame, "[LAMP HEAD]", (panel_left + 20, panel_top + 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, self.colors['blue'], 2)
            
            # Position info (simulated for now)
            position_y = panel_top + 70
            
            # Show actual lamp status from hardware (use lamp_info if available)
            lamp_status = "[LAMP ON]" if current_lamp_status else "[LAMP OFF]"
            lamp_bg_color = self.colors['lux_gold'] if current_lamp_status else self.colors['gray']
            lamp_text_color = self.colors['black'] if current_lamp_status else self.colors['white']
            
            # Check if lamp status is stale (no updates for more than 5 seconds)
            # Only check staleness if lamp_info provides an update timestamp
            if lamp_info and 'last_update' in lamp_info:
                time_since_update = current_time - lamp_info['last_update']
                if time_since_update > 5.0:
                    lamp_status = "[LAMP ???]"
                    lamp_bg_color = self.colors['orange']
                    lamp_text_color = self.colors['black']
                    
                # Add lamp status timestamp for debugging (larger text with more spacing)
                if time_since_update < 60.0:  # Only show if recent
                    timestamp_text = f"Updated {time_since_update:.0f}s ago"
                    cv2.putText(display_frame, timestamp_text, (panel_left + 20, panel_top + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors['gray'], 1)
            
            # Draw lamp status background and text (much larger with more spacing)
            cv2.rectangle(display_frame, (panel_left + 20, panel_bottom - 50), (panel_right - 20, panel_bottom - 15), lamp_bg_color, -1)
            cv2.putText(display_frame, lamp_status, (panel_left + 30, panel_bottom - 28), cv2.FONT_HERSHEY_SIMPLEX, 1.0, lamp_text_color, 2)
            
            # Joint Status Panel (bottom left, much larger)
            joint_panel_right = display_frame.shape[1] - 400  # More spacing from lamp panel
            joint_panel_left = joint_panel_right - 400  # Increased width
            
            self.draw_rounded_panel(display_frame, (joint_panel_left, panel_top), (joint_panel_right, panel_bottom), self.colors['dark_gray'], 0.8)
            
            cv2.putText(display_frame, "[LAMP JOINTS]", (joint_panel_left + 20, panel_top + 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, self.colors['purple'], 2)
            
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
                        available_joints.append((display_name, f"{angle:.1f}"))
                
                # If no mapped joints found, show all available joints
                if not available_joints:
                    for joint_name, angle in list(joint_states.items())[:5]:  # Limit to first 5
                        display_name = joint_name.replace('_', ' ').title()
                        available_joints.append((display_name, f"{angle:.1f}"))
                
                # Display the joints (larger font and much more spacing)
                joint_y = panel_top + 65
                for i, (joint_name, angle) in enumerate(available_joints[:6]):  # Show up to 6 joints now
                    y_pos = joint_y + i * 25  # Increased spacing between lines
                    # Truncate long joint names
                    if len(joint_name) > 15:
                        joint_name = joint_name[:15] + "..."
                    
                    cv2.putText(display_frame, joint_name, (joint_panel_left + 20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.colors['purple'], 1)
                    cv2.putText(display_frame, angle, (joint_panel_left + 250, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.colors['lux_gold'], 1)
                
                # Show joint count if we have more than 6 (larger font with more spacing)
                if len(joint_states) > 6:
                    extra_count = len(joint_states) - 6
                    cv2.putText(display_frame, f"+ {extra_count} more", (joint_panel_left + 20, joint_y + 6 * 25), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colors['gray'], 1)
            else:
                # Show offline message when no joint data available (larger font with more spacing)
                offline_text = "JOINTS OFFLINE"
                cv2.putText(display_frame, offline_text, (joint_panel_left + 20, panel_top + 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, self.colors['gray'], 2)
                
                # Show waiting message (larger font with more spacing)
                waiting_text = "Waiting for /joint_states..."
                cv2.putText(display_frame, waiting_text, (joint_panel_left + 20, panel_top + 110), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.colors['gray'], 1)
            
            # === CENTRAL CROSSHAIR (larger) ===
            # Draw friendly crosshair in center
            center_x, center_y = display_frame.shape[1] // 2, display_frame.shape[0] // 2
            
            # Breathing animation (larger)
            breath_scale = 1.0 + 0.1 * math.sin(self.animation_time * 1.5)
            crosshair_radius = int(40 * breath_scale)
            
            cv2.circle(display_frame, (center_x, center_y), crosshair_radius, self.colors['lux_gold'], 3)
            cv2.circle(display_frame, (center_x, center_y), 8, self.colors['lux_gold'], -1)
            
            # === CAMERA INFO (bottom center, larger) ===
            camera_info = "[CAM] Lux Vision | 1920x1080-30fps | @cyril.engman"
            info_size = cv2.getTextSize(camera_info, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            info_x = (display_frame.shape[1] - info_size[0]) // 2
            info_y = display_frame.shape[0] - 15
            
            # Background for camera info (larger)
            cv2.rectangle(display_frame, (info_x - 10, info_y - 25), (info_x + info_size[0] + 10, info_y + 10), self.colors['dark_gray'], -1)
            cv2.putText(display_frame, camera_info, (info_x, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, self.colors['white'], 2)
            
            # === ANIMATED SCAN LINE (thicker) ===
            # Add subtle scan line animation
            scan_y = int((self.animation_time * 100) % display_frame.shape[0])
            cv2.line(display_frame, (0, scan_y), (display_frame.shape[1], scan_y), (*self.colors['lux_gold'], 50), 3)
            
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
            
            # Add Lux shutdown message (larger fonts)
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            # Main message (much larger)
            text = "LUX POWERING DOWN"
            font_scale = 3.0
            thickness = 6
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            
            # Center the text
            x = (frame.shape[1] - text_size[0]) // 2
            y = (frame.shape[0] + text_size[1]) // 2 - 80
            
            # Draw text with glow effect (thicker)
            cv2.putText(frame, text, (x, y), font, font_scale, (0, 0, 0), thickness + 4)  # Black border
            cv2.putText(frame, text, (x, y), font, font_scale, self.colors['lux_gold'], thickness)  # Gold text
            
            # Add lamp icon (larger)
            cv2.circle(frame, (x - 50, y - 25), 25, self.colors['lux_gold'], -1)
            cv2.putText(frame, "[L]", (x - 65, y - 5), font, 2.0, self.colors['black'], 4)
            
            # Add smaller subtitle (larger)
            subtitle = "Thank you for playing!"
            font_scale_sub = 2.0
            thickness_sub = 4
            text_size_sub = cv2.getTextSize(subtitle, font, font_scale_sub, thickness_sub)[0]
            x_sub = (frame.shape[1] - text_size_sub[0]) // 2
            y_sub = y + 100
            
            cv2.putText(frame, subtitle, (x_sub, y_sub), font, font_scale_sub, self.colors['teal'], thickness_sub)
            
            # Add timestamp (larger)
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            font_scale_ts = 1.4
            thickness_ts = 2
            text_size_ts = cv2.getTextSize(timestamp, font, font_scale_ts, thickness_ts)[0]
            x_ts = (frame.shape[1] - text_size_ts[0]) // 2
            y_ts = y_sub + 60
            
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
                
                # Add Lux-themed "No Signal" message (larger fonts)
                font = cv2.FONT_HERSHEY_SIMPLEX
                text = "LUX SLEEPING"
                font_scale = 3.0
                thickness = 4
                text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                
                # Center the text
                x = (frame.shape[1] - text_size[0]) // 2
                y = (frame.shape[0] + text_size[1]) // 2
                
                # Draw text (larger)
                cv2.putText(frame, text, (x, y), font, font_scale, self.colors['lux_gold'], thickness)
                
                # Add sleeping lamp icon (larger)
                cv2.circle(frame, (x - 50, y - 25), 20, self.colors['gray'], 3)
                cv2.putText(frame, "Z", (x - 60, y - 5), font, 1.6, self.colors['gray'], 2)
                
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