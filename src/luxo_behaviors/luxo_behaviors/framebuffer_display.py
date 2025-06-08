#!/usr/bin/env python3
"""
Direct framebuffer display module for camera_interaction.py
This can be integrated into the camera node or used as a separate module
"""

import numpy as np
import cv2
import os
import struct
import mmap
import fcntl
import threading

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
    """Helper class to integrate framebuffer display into camera_interaction.py"""
    
    def __init__(self, node, device='/dev/fb0'):
        self.node = node
        self.display = FramebufferDisplay(device)
        self.enabled = self.display.initialized
        
        if not self.enabled:
            self.node.get_logger().warn("Framebuffer display could not be initialized")
    
    def update_display(self, frame, emotion=None, distance=None, face_bboxes=None, animation_name=None, state=None):
        """Update framebuffer with camera frame and overlays including debug info"""
        if not self.enabled:
            return
        
        try:
            # Create display frame
            display_frame = frame.copy()
            
            # Draw face bounding boxes
            if face_bboxes:
                for bbox in face_bboxes:
                    if len(bbox) >= 4:
                        x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
                        # Draw rectangle around face
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        # Add "Face" label above bbox
                        cv2.putText(display_frame, "Face", (x1, y1 - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Add overlays
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.2
            thickness = 2
            
            # Y position for text
            y_pos = 40
            line_height = 45
            
            # Add state information (top left, larger font)
            if state:
                state_text = f"State: {state}"
                cv2.putText(display_frame, state_text, (30, y_pos), font, 
                           font_scale * 1.2, (255, 255, 0), thickness + 1)  # Yellow, thicker
                y_pos += line_height + 10
            
            # Add animation name
            if animation_name:
                anim_text = f"Animation: {animation_name}"
                cv2.putText(display_frame, anim_text, (30, y_pos), font, 
                           font_scale, (0, 255, 255), thickness)  # Cyan
                y_pos += line_height
            else:
                anim_text = "Animation: None"
                cv2.putText(display_frame, anim_text, (30, y_pos), font, 
                           font_scale, (128, 128, 128), thickness)  # Gray
                y_pos += line_height
            
            # Add emotion text
            if emotion:
                text = f"Emotion: {emotion}"
                cv2.putText(display_frame, text, (30, y_pos), font, 
                           font_scale, (0, 255, 0), thickness)
                y_pos += line_height
            
            # Add distance text
            if distance is not None:
                text = f"Distance: {distance:.2f}m"
                cv2.putText(display_frame, text, (30, y_pos), font, 
                           font_scale, (0, 255, 0), thickness)
            
            # Add timestamp in bottom right corner
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            text_size = cv2.getTextSize(timestamp, font, font_scale, thickness)[0]
            timestamp_x = display_frame.shape[1] - text_size[0] - 30
            timestamp_y = display_frame.shape[0] - 30
            cv2.putText(display_frame, timestamp, (timestamp_x, timestamp_y), 
                       font, font_scale, (255, 255, 255), thickness)
            
            # Add debug info in bottom left corner
            debug_y = display_frame.shape[0] - 100
            debug_font_scale = 0.7
            debug_thickness = 1
            
            # Show number of faces detected
            if face_bboxes:
                face_count_text = f"Faces detected: {len(face_bboxes)}"
            else:
                face_count_text = "Faces detected: 0"
            cv2.putText(display_frame, face_count_text, (30, debug_y), 
                       font, debug_font_scale, (200, 200, 200), debug_thickness)
            
            # Display the frame
            self.display.display_frame(display_frame)
            
        except Exception as e:
            self.node.get_logger().error(f"Error updating framebuffer display: {e}")
    
    def show_shutdown_message(self):
        """Display a shutdown message before cleanup"""
        if not self.enabled:
            return
            
        try:
            # Create a black frame
            frame = np.zeros((self.display.height, self.display.width, 3), dtype=np.uint8)
            
            # Add shutdown message
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            # Main message
            text = "CAMERA STOPPED"
            font_scale = 2.0
            thickness = 3
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            
            # Center the text
            x = (frame.shape[1] - text_size[0]) // 2
            y = (frame.shape[0] + text_size[1]) // 2 - 50
            
            # Draw text with border for visibility
            cv2.putText(frame, text, (x, y), font, font_scale, (0, 0, 0), thickness + 2)  # Black border
            cv2.putText(frame, text, (x, y), font, font_scale, (255, 255, 255), thickness)  # White text
            
            # Add smaller subtitle
            subtitle = "System Shutdown"
            font_scale_sub = 1.0
            thickness_sub = 2
            text_size_sub = cv2.getTextSize(subtitle, font, font_scale_sub, thickness_sub)[0]
            x_sub = (frame.shape[1] - text_size_sub[0]) // 2
            y_sub = y + 60
            
            cv2.putText(frame, subtitle, (x_sub, y_sub), font, font_scale_sub, (128, 128, 128), thickness_sub)
            
            # Add timestamp
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            font_scale_ts = 0.7
            thickness_ts = 1
            text_size_ts = cv2.getTextSize(timestamp, font, font_scale_ts, thickness_ts)[0]
            x_ts = (frame.shape[1] - text_size_ts[0]) // 2
            y_ts = y_sub + 40
            
            cv2.putText(frame, timestamp, (x_ts, y_ts), font, font_scale_ts, (100, 100, 100), thickness_ts)
            
            # Display the frame
            self.display.display_frame(frame)
            
            # Keep the message visible for a moment
            import time
            time.sleep(1.0)
            
        except Exception as e:
            self.node.get_logger().error(f"Error displaying shutdown message: {e}")
    
    def clear(self, color=(0, 0, 0)):
        """Clear the display with a solid color or message"""
        if self.enabled:
            try:
                # Create a black frame
                frame = np.full((self.display.height, self.display.width, 3), color, dtype=np.uint8)
                
                # Add a "No Signal" message
                font = cv2.FONT_HERSHEY_SIMPLEX
                text = "NO SIGNAL"
                font_scale = 1.5
                thickness = 2
                text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                
                # Center the text
                x = (frame.shape[1] - text_size[0]) // 2
                y = (frame.shape[0] + text_size[1]) // 2
                
                # Draw text
                cv2.putText(frame, text, (x, y), font, font_scale, (64, 64, 64), thickness)
                
                self.display.display_frame(frame)
            except Exception as e:
                self.node.get_logger().error(f"Error clearing display: {e}")
                # Fallback to simple clear
                self.display.clear(color)
    
    def cleanup(self):
        """Clean up resources"""
        if self.enabled:
            # Show shutdown message first
            self.show_shutdown_message()
            # Then cleanup
            self.display.cleanup()