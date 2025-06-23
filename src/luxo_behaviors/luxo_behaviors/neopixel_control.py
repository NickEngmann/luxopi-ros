#!/usr/bin/env python3
"""
Shared NeoPixel Control Module for LuxoPi
Based on neopixel_test.py - provides reusable NeoPixel control functionality
"""

import time
import board
import neopixel_spi
import math
import random
import threading
from typing import Tuple, Optional, Callable
from enum import Enum, auto

class NeoPixelMode(Enum):
    """Available NeoPixel modes"""
    OFF = auto()
    SOLID = auto()
    COLOR_WIPE = auto()
    SPINNING_DOT = auto()
    RAINBOW_CYCLE = auto()
    THEATER_CHASE = auto()
    BREATHING = auto()
    WAVE = auto()
    SPARKLE = auto()
    SEGMENT = auto()

class NeoPixelController:
    """
    Shared NeoPixel controller for LuxoPi system
    Provides thread-safe control of NeoPixel strip with various effects
    """
    
    def __init__(self, pixel_count: int = 76, brightness: float = 0.8, 
                 spi_frequency: int = 100000, logger=None):
        """
        Initialize NeoPixel controller
        
        Args:
            pixel_count: Number of pixels in the strip
            brightness: Brightness level (0.0 to 1.0)
            spi_frequency: SPI frequency for communication
            logger: Optional logger instance for debugging
        """
        self.pixel_count = pixel_count
        self.brightness = brightness
        self.spi_frequency = spi_frequency
        self.logger = logger
        
        # Thread safety
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._effect_thread = None
        
        # Current state
        self._current_mode = NeoPixelMode.OFF
        self._current_color = (0, 0, 0)
        self._is_initialized = False
        
        # Initialize pixels
        self._initialize_pixels()
    
    def _log(self, message: str, level: str = "info"):
        """Internal logging method"""
        if self.logger:
            if level == "info":
                self.logger.info(f"[NeoPixel] {message}")
            elif level == "warn":
                self.logger.warn(f"[NeoPixel] {message}")
            elif level == "error":
                self.logger.error(f"[NeoPixel] {message}")
            elif level == "debug":
                self.logger.debug(f"[NeoPixel] {message}")
        else:
            print(f"[NeoPixel] {message}")
    
    def _initialize_pixels(self) -> bool:
        """Initialize the NeoPixel strip"""
        try:
            # Get the SPI bus
            spi = board.SPI()
            
            # Initialize NeoPixels using SPI
            self.pixels = neopixel_spi.NeoPixel_SPI(
                spi, 
                self.pixel_count, 
                brightness=self.brightness,
                auto_write=False,
                pixel_order=neopixel_spi.GRBW,
                bpp=3
            )
            
            self._log(f"NeoPixel SPI initialized: {self.pixel_count} LEDs, Brightness: {self.brightness}")
            self._is_initialized = True
            return True
            
        except Exception as e:
            self._log(f"Failed to initialize NeoPixel SPI: {e}", "error")
            self._is_initialized = False
            return False
    
    def is_initialized(self) -> bool:
        """Check if NeoPixels are properly initialized"""
        return self._is_initialized
    
    def set_brightness(self, brightness: float):
        """Set global brightness (0.0 to 1.0)"""
        with self._lock:
            if not self._is_initialized:
                return False
            
            self.brightness = max(0.0, min(1.0, brightness))
            try:
                self.pixels.brightness = self.brightness
                self._log(f"Brightness set to {self.brightness * 100:.1f}%")
                return True
            except Exception as e:
                self._log(f"Failed to set brightness: {e}", "error")
                return False
    
    def clear_all(self):
        """Turn off all LEDs"""
        with self._lock:
            if not self._is_initialized:
                return False
            
            try:
                self.pixels.fill((0, 0, 0))
                self.pixels.show()
                self._current_mode = NeoPixelMode.OFF
                self._current_color = (0, 0, 0)
                return True
            except Exception as e:
                self._log(f"Failed to clear pixels: {e}", "error")
                return False
    
    def set_pixel_color(self, index: int, r: int, g: int, b: int):
        """Set a single pixel color"""
        with self._lock:
            if not self._is_initialized or index >= self.pixel_count:
                return False
            
            try:
                self.pixels[index] = (r, g, b)
                return True
            except Exception as e:
                self._log(f"Failed to set pixel {index}: {e}", "error")
                return False
    
    def fill_all(self, r: int, g: int, b: int, show: bool = True):
        """Fill all pixels with color"""
        with self._lock:
            if not self._is_initialized:
                return False
            
            try:
                self.pixels.fill((r, g, b))
                if show:
                    self.pixels.show()
                self._current_mode = NeoPixelMode.SOLID
                self._current_color = (r, g, b)
                return True
            except Exception as e:
                self._log(f"Failed to fill pixels: {e}", "error")
                return False
    
    def show(self):
        """Update the strip with current pixel values"""
        with self._lock:
            if not self._is_initialized:
                return False
            
            try:
                self.pixels.show()
                return True
            except Exception as e:
                self._log(f"Failed to show pixels: {e}", "error")
                return False
    
    def stop_effect(self):
        """Stop any running effect"""
        self._stop_event.set()
        if self._effect_thread and self._effect_thread.is_alive():
            self._effect_thread.join(timeout=1.0)
        self._stop_event.clear()
    
    def _run_effect(self, effect_func: Callable, *args, **kwargs):
        """Run an effect in a separate thread"""
        self.stop_effect()
        
        def effect_wrapper():
            try:
                effect_func(*args, **kwargs)
            except Exception as e:
                self._log(f"Effect error: {e}", "error")
        
        self._effect_thread = threading.Thread(target=effect_wrapper, daemon=True)
        self._effect_thread.start()
    
    # ==========================================================================
    # Effect Methods
    # ==========================================================================
    
    def color_wipe(self, color: Tuple[int, int, int], delay: float = 0.03, 
                   blocking: bool = False):
        """Light up LEDs one by one with specified color"""
        if not self._is_initialized:
            return False
        
        def _color_wipe():
            r, g, b = color
            self._log(f"Color wipe: {color}")
            for i in range(self.pixel_count):
                if self._stop_event.is_set():
                    break
                self.set_pixel_color(i, r, g, b)
                self.show()
                time.sleep(delay)
            self._current_mode = NeoPixelMode.COLOR_WIPE
            self._current_color = color
        
        if blocking:
            _color_wipe()
        else:
            self._run_effect(_color_wipe)
        return True
    
    def spinning_dot(self, color: Tuple[int, int, int] = (255, 255, 255), 
                     cycles: int = 3, delay: float = 0.04, blocking: bool = False):
        """Single dot spinning around the ring - spins continuously until stopped"""
        if not self._is_initialized:
            return False
        
        def _spinning_dot():
            r, g, b = color
            self._log(f"Spinning dot: {color} - continuous")
            
            # Spin continuously until stopped
            while not self._stop_event.is_set():
                for i in range(self.pixel_count):
                    if self._stop_event.is_set():
                        break
                    self.clear_all()
                    self.set_pixel_color(i, r, g, b)
                    self.show()
                    time.sleep(delay)
            
            self._current_mode = NeoPixelMode.SPINNING_DOT
            self._current_color = color
        
        if blocking:
            _spinning_dot()
        else:
            self._run_effect(_spinning_dot)
        return True
    
    def spinning_group(self, color: Tuple[int, int, int] = (255, 255, 255), 
                       group_size: int = 8, cycles: int = 3, 
                       delay_first_60: float = 0.04, delay_last_16: float = 0.08, 
                       blocking: bool = False):
        """Group of pixels spinning around the ring - spins continuously until stopped"""
        if not self._is_initialized:
            return False
        
        def _spinning_group():
            r, g, b = color
            self._log(f"Spinning group: {color}, size: {group_size} - continuous")
            
            # Track previous group positions to avoid unnecessary clearing
            prev_group_positions = set()
            
            # Spin continuously until stopped
            while not self._stop_event.is_set():
                for start_pos in range(self.pixel_count):
                    if self._stop_event.is_set():
                        break
                    
                    # Calculate current group positions
                    current_group_positions = set()
                    for i in range(group_size):
                        pixel_idx = (start_pos + i) % self.pixel_count
                        current_group_positions.add(pixel_idx)
                    
                    # Turn off pixels that were on but shouldn't be anymore
                    pixels_to_turn_off = prev_group_positions - current_group_positions
                    for pixel_idx in pixels_to_turn_off:
                        self.set_pixel_color(pixel_idx, 0, 0, 0)
                    
                    # Turn on pixels that should be on
                    for pixel_idx in current_group_positions:
                        self.set_pixel_color(pixel_idx, r, g, b)
                    
                    # Update the display only once
                    self.show()
                    
                    # Store current positions for next iteration
                    prev_group_positions = current_group_positions
                    
                    # Use different delays based on position
                    # First 60 pixels (0-59) use faster speed
                    # Last 16 pixels (60-75) use slower speed
                    if start_pos < 60:
                        time.sleep(delay_first_60)
                    else:
                        time.sleep(delay_last_16)
            
            self._current_mode = NeoPixelMode.SPINNING_DOT  # Reuse this mode
            self._current_color = color
        
        if blocking:
            _spinning_group()
        else:
            self._run_effect(_spinning_group)
        return True
    
    def rainbow_cycle(self, cycles: int = 2, delay: float = 0.01, 
                      blocking: bool = False):
        """Generate rainbow colors across all LEDs"""
        if not self._is_initialized:
            return False
        
        def _wheel(pos):
            """Generate rainbow colors across 0-255 positions"""
            if pos < 85:
                return (pos * 3, 255 - pos * 3, 0)
            elif pos < 170:
                pos -= 85
                return (255 - pos * 3, 0, pos * 3)
            else:
                pos -= 170
                return (0, pos * 3, 255 - pos * 3)
        
        def _rainbow_cycle():
            self._log("Rainbow cycle")
            for cycle in range(cycles):
                if self._stop_event.is_set():
                    break
                for j in range(256):
                    if self._stop_event.is_set():
                        break
                    for i in range(self.pixel_count):
                        pixel_index = (i * 256 // self.pixel_count) + j
                        r, g, b = _wheel(pixel_index & 255)
                        self.set_pixel_color(i, r, g, b)
                    self.show()
                    time.sleep(delay)
            self._current_mode = NeoPixelMode.RAINBOW_CYCLE
        
        if blocking:
            _rainbow_cycle()
        else:
            self._run_effect(_rainbow_cycle)
        return True
    
    def theater_chase(self, color: Tuple[int, int, int], cycles: int = 3, 
                      delay: float = 0.1, blocking: bool = False):
        """Theater-style chasing lights"""
        if not self._is_initialized:
            return False
        
        def _theater_chase():
            r, g, b = color
            self._log(f"Theater chase: {color}")
            for cycle in range(cycles):
                if self._stop_event.is_set():
                    break
                for q in range(3):
                    if self._stop_event.is_set():
                        break
                    self.clear_all()
                    for i in range(0, self.pixel_count, 3):
                        if (i + q) < self.pixel_count:
                            self.set_pixel_color(i + q, r, g, b)
                    self.show()
                    time.sleep(delay)
            self._current_mode = NeoPixelMode.THEATER_CHASE
            self._current_color = color
        
        if blocking:
            _theater_chase()
        else:
            self._run_effect(_theater_chase)
        return True
    
    def breathing_effect(self, color: Tuple[int, int, int], cycles: int = 2, 
                        steps: int = 40, blocking: bool = False):
        """Breathing effect - fade in and out"""
        if not self._is_initialized:
            return False
        
        def _breathing_effect():
            r, g, b = color
            self._log(f"Breathing effect: {color}")
            
            for cycle in range(cycles):
                if self._stop_event.is_set():
                    break
                
                # Fade in
                for i in range(steps):
                    if self._stop_event.is_set():
                        break
                    brightness = (i / steps) ** 2
                    dimmed_r = int(r * brightness)
                    dimmed_g = int(g * brightness)
                    dimmed_b = int(b * brightness)
                    self.fill_all(dimmed_r, dimmed_g, dimmed_b)
                    time.sleep(0.02)
                
                # Fade out
                for i in range(steps, 0, -1):
                    if self._stop_event.is_set():
                        break
                    brightness = (i / steps) ** 2
                    dimmed_r = int(r * brightness)
                    dimmed_g = int(g * brightness)
                    dimmed_b = int(b * brightness)
                    self.fill_all(dimmed_r, dimmed_g, dimmed_b)
                    time.sleep(0.02)
            
            self._current_mode = NeoPixelMode.BREATHING
            self._current_color = color
        
        if blocking:
            _breathing_effect()
        else:
            self._run_effect(_breathing_effect)
        return True
    
    def wave_effect(self, cycles: int = 2, delay: float = 0.03, 
                    blocking: bool = False):
        """Sine wave moving around the ring"""
        if not self._is_initialized:
            return False
        
        def _wave_effect():
            self._log("Wave effect")
            for cycle in range(cycles):
                if self._stop_event.is_set():
                    break
                for offset in range(self.pixel_count):
                    if self._stop_event.is_set():
                        break
                    for i in range(self.pixel_count):
                        angle = (i + offset) * 2 * math.pi / self.pixel_count
                        intensity = (math.sin(angle) + 1) / 2
                        
                        blue_val = int(100 + (155 * intensity))
                        white_val = int(50 * intensity)
                        self.set_pixel_color(i, white_val, white_val, blue_val)
                    
                    self.show()
                    time.sleep(delay)
            self._current_mode = NeoPixelMode.WAVE
        
        if blocking:
            _wave_effect()
        else:
            self._run_effect(_wave_effect)
        return True
    
    def random_sparkle(self, duration: float = 4, delay: float = 0.1, 
                      blocking: bool = False):
        """Random sparkling effect"""
        if not self._is_initialized:
            return False
        
        def _random_sparkle():
            self._log("Random sparkle")
            start_time = time.time()
            self.clear_all()
            
            while time.time() - start_time < duration:
                if self._stop_event.is_set():
                    break
                
                # Turn off some random LEDs
                for _ in range(5):
                    self.set_pixel_color(random.randint(0, self.pixel_count - 1), 0, 0, 0)
                
                # Turn on some random LEDs with random colors
                for _ in range(8):
                    i = random.randint(0, self.pixel_count - 1)
                    r = random.randint(50, 255)
                    g = random.randint(50, 255)
                    b = random.randint(50, 255)
                    self.set_pixel_color(i, r, g, b)
                
                self.show()
                time.sleep(delay)
            
            self._current_mode = NeoPixelMode.SPARKLE
        
        if blocking:
            _random_sparkle()
        else:
            self._run_effect(_random_sparkle)
        return True
    
    def segment_test(self, colors: Optional[list] = None, blocking: bool = False):
        """Test different segments of the ring"""
        if not self._is_initialized:
            return False
        
        def _segment_test():
            self._log("Segment test - dividing ring into colored sections")
            if colors is None:
                segment_colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
            else:
                segment_colors = colors
            
            segments = self.pixel_count // len(segment_colors)
            self.clear_all()
            
            for i, (r, g, b) in enumerate(segment_colors):
                start_idx = i * segments
                end_idx = min((i + 1) * segments, self.pixel_count)
                
                self._log(f"Segment {i+1}: LEDs {start_idx}-{end_idx-1} = ({r}, {g}, {b})")
                
                for j in range(start_idx, end_idx):
                    self.set_pixel_color(j, r, g, b)
            
            self.show()
            time.sleep(3)
            self._current_mode = NeoPixelMode.SEGMENT
        
        if blocking:
            _segment_test()
        else:
            self._run_effect(_segment_test)
        return True
    
    # ==========================================================================
    # Convenience Methods
    # ==========================================================================
    
    def set_solid_color(self, r: int, g: int, b: int):
        """Set a solid color across all pixels"""
        return self.fill_all(r, g, b)
    
    def set_white(self, intensity: int = 255):
        """Set all pixels to white"""
        return self.fill_all(intensity, intensity, intensity)
    
    def set_red(self, intensity: int = 255):
        """Set all pixels to red"""
        return self.fill_all(intensity, 0, 0)
    
    def set_green(self, intensity: int = 255):
        """Set all pixels to green"""
        return self.fill_all(0, intensity, 0)
    
    def set_blue(self, intensity: int = 255):
        """Set all pixels to blue"""
        return self.fill_all(0, 0, intensity)
    
    def get_current_mode(self) -> NeoPixelMode:
        """Get the current mode"""
        return self._current_mode
    
    def get_current_color(self) -> Tuple[int, int, int]:
        """Get the current color"""
        return self._current_color
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_effect()
        self.clear_all()
        self._log("NeoPixel controller cleaned up")
        self._log("NeoPixel controller cleaned up")
