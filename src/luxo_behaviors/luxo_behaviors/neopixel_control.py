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
from typing import Tuple, Optional, Callable, Union
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

class NeoPixelController:
    """
    Shared NeoPixel controller for LuxoPi system
    Provides thread-safe control of NeoPixel strip with various effects
    Supports RGBW color format
    """
    
    def __init__(self, pixel_count: int = 60, brightness: float = 0.2, 
                 logger=None):
        """
        Initialize NeoPixel controller
        
        Args:
            pixel_count: Number of pixels in the strip
            brightness: Brightness level (0.0 to 1.0)
            logger: Optional logger instance for debugging
        """
        self.pixel_count = pixel_count
        self.brightness = brightness
        self.logger = logger
        
        # Thread safety
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._effect_thread = None
        
        # Current state - now using RGBW
        self._current_mode = NeoPixelMode.OFF
        self._current_color = (0, 0, 0, 0)  # RGBW
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
        """Initialize the NeoPixel strip with error recovery"""
        try:
            # Get current frequency to try   
            # Get the SPI bus - this returns a shared instance
            spi = board.SPI()
            
            try:
                # Attempt to acquire and configure the bus
                acquired = False
                for _ in range(10):  # Try up to 10 times
                    if spi.try_lock():
                        acquired = True
                        break
                    time.sleep(0.01)
                
                if acquired:
                    spi.unlock()
                else:
                    self._log(f"Could not acquire SPI lock, using default settings", "warn")
            except Exception as e:
                self._log(f"Could not configure SPI: {e}. Using default.", "warn")
            
            # Initialize NeoPixels using SPI with RGBW support
            self.pixels = neopixel_spi.NeoPixel_SPI(
                spi, 
                self.pixel_count, 
                brightness=self.brightness,
                auto_write=False,
                pixel_order=neopixel_spi.GRBW,
                bpp=4
            )
            
            # Clear the strip with a small delay
            time.sleep(0.1)
            
            self._log(f"NeoPixel SPI initialized: {self.pixel_count} LEDs, Brightness: {self.brightness}, Color: RGBW")
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
                self.pixels.fill((0, 0, 0, 0))  # RGBW
                self.pixels.show()
                time.sleep(0.01)  # Small delay to ensure clearing takes effect
                self._current_mode = NeoPixelMode.OFF
                self._current_color = (0, 0, 0, 0)  # RGBW
                return True
            except Exception as e:
                self._log(f"Failed to clear pixels: {e}", "error")
                return False
    
    def set_pixel_color(self, index: int, r: int, g: int, b: int, w: int = 0):
        """Set a single pixel color with RGBW support"""
        with self._lock:
            if not self._is_initialized or index >= self.pixel_count:
                return False
            
            try:
                self.pixels[index] = (r, g, b, w)
                return True
            except Exception as e:
                self._log(f"Failed to set pixel {index}: {e}", "error")
                return False
    
    def fill_all(self, r: int, g: int, b: int, w: int = 0, show: bool = True):
        """Fill all pixels with RGBW color"""
        with self._lock:
            if not self._is_initialized:
                return False
            
            try:
                self.pixels.fill((r, g, b, w))
                if show:
                    self.pixels.show()
                self._current_mode = NeoPixelMode.SOLID
                self._current_color = (r, g, b, w)
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
    
    def color_wipe(self, color: Union[Tuple[int, int, int], Tuple[int, int, int, int]], 
                   delay: float = 0.03, blocking: bool = False):
        """Light up LEDs one by one with specified color"""
        if not self._is_initialized:
            return False
        
        # Handle both RGB and RGBW color formats
        if len(color) == 3:
            r, g, b = color
            w = 0
        else:
            r, g, b, w = color
        
        def _color_wipe():
            self._log(f"Color wipe: RGBW({r}, {g}, {b}, {w})")
            for i in range(self.pixel_count):
                if self._stop_event.is_set():
                    break
                self.set_pixel_color(i, r, g, b, w)
                self.show()
                time.sleep(delay)
            self._current_mode = NeoPixelMode.COLOR_WIPE
            self._current_color = (r, g, b, w)
        
        if blocking:
            _color_wipe()
        else:
            self._run_effect(_color_wipe)
        return True
    
    def spinning_dot(self, color: Union[Tuple[int, int, int], Tuple[int, int, int, int]] = (255, 255, 255, 0), 
                     cycles: int = 3, delay: float = 0.04, blocking: bool = False):
        """Single dot spinning around the ring - spins continuously until stopped"""
        if not self._is_initialized:
            return False
        
        # Handle both RGB and RGBW color formats
        if len(color) == 3:
            r, g, b = color
            w = 0
        else:
            r, g, b, w = color
        
        def _spinning_dot():
            self._log(f"Spinning dot: RGBW({r}, {g}, {b}, {w}) - continuous")
            
            # Spin continuously until stopped
            while not self._stop_event.is_set():
                for i in range(self.pixel_count):
                    if self._stop_event.is_set():
                        break
                    self.clear_all()
                    self.set_pixel_color(i, r, g, b, w)
                    self.show()
                    time.sleep(delay)
            
            self._current_mode = NeoPixelMode.SPINNING_DOT
            self._current_color = (r, g, b, w)
        
        if blocking:
            _spinning_dot()
        else:
            self._run_effect(_spinning_dot)
        return True
    
    def spinning_group(self, color: Union[Tuple[int, int, int], Tuple[int, int, int, int]] = (255, 255, 255, 0), 
                       group_size: int = 8, cycles: int = 3, 
                       delay_first_60: float = 0.04, delay_last_16: float = 0.08, 
                       blocking: bool = False):
        """Group of pixels spinning around the ring - spins continuously until stopped"""
        if not self._is_initialized:
            return False
        
        # Handle both RGB and RGBW color formats
        if len(color) == 3:
            r, g, b = color
            w = 0
        else:
            r, g, b, w = color
        
        def _spinning_group():
            self._log(f"Spinning group: RGBW({r}, {g}, {b}, {w}), size: {group_size} - continuous")
            
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
                        self.set_pixel_color(pixel_idx, 0, 0, 0, 0)
                    
                    # Turn on pixels that should be on
                    for pixel_idx in current_group_positions:
                        self.set_pixel_color(pixel_idx, r, g, b, w)
                    
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
            self._current_color = (r, g, b, w)
        
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
                        self.set_pixel_color(i, r, g, b, 0)  # W=0 for rainbow
                    self.show()
                    time.sleep(delay)
            self._current_mode = NeoPixelMode.RAINBOW_CYCLE
        
        if blocking:
            _rainbow_cycle()
        else:
            self._run_effect(_rainbow_cycle)
        return True
    
    def theater_chase(self, color: Union[Tuple[int, int, int], Tuple[int, int, int, int]], 
                      cycles: int = 3, delay: float = 0.1, blocking: bool = False):
        """Theater-style chasing lights"""
        if not self._is_initialized:
            return False
        
        # Handle both RGB and RGBW color formats
        if len(color) == 3:
            r, g, b = color
            w = 0
        else:
            r, g, b, w = color
        
        def _theater_chase():
            self._log(f"Theater chase: RGBW({r}, {g}, {b}, {w})")
            for cycle in range(cycles):
                if self._stop_event.is_set():
                    break
                for q in range(3):
                    if self._stop_event.is_set():
                        break
                    self.clear_all()
                    for i in range(0, self.pixel_count, 3):
                        if (i + q) < self.pixel_count:
                            self.set_pixel_color(i + q, r, g, b, w)
                    self.show()
                    time.sleep(delay)
            self._current_mode = NeoPixelMode.THEATER_CHASE
            self._current_color = (r, g, b, w)
        
        if blocking:
            _theater_chase()
        else:
            self._run_effect(_theater_chase)
        return True
    
    def breathing_effect(self, color: Union[Tuple[int, int, int], Tuple[int, int, int, int]], 
                        cycles: int = 2, steps: int = 40, blocking: bool = False):
        """Breathing effect - fade in and out"""
        if not self._is_initialized:
            return False
        
        # Handle both RGB and RGBW color formats
        if len(color) == 3:
            r, g, b = color
            w = 0
        else:
            r, g, b, w = color
        
        def _breathing_effect():
            self._log(f"Breathing effect: RGBW({r}, {g}, {b}, {w})")
            
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
                    dimmed_w = int(w * brightness)
                    self.fill_all(dimmed_r, dimmed_g, dimmed_b, dimmed_w)
                    time.sleep(0.02)
                
                # Fade out
                for i in range(steps, 0, -1):
                    if self._stop_event.is_set():
                        break
                    brightness = (i / steps) ** 2
                    dimmed_r = int(r * brightness)
                    dimmed_g = int(g * brightness)
                    dimmed_b = int(b * brightness)
                    dimmed_w = int(w * brightness)
                    self.fill_all(dimmed_r, dimmed_g, dimmed_b, dimmed_w)
                    time.sleep(0.02)
            
            self._current_mode = NeoPixelMode.BREATHING
            self._current_color = (r, g, b, w)
        
        if blocking:
            _breathing_effect()
        else:
            self._run_effect(_breathing_effect)
        return True
    def set_solid_color(self, r: int, g: int, b: int, w: int = 0) -> bool:
        """Set a solid color across all pixels"""
        return self.fill_all(r, g, b, w)
    
    def get_current_mode(self) -> NeoPixelMode:
        """Get the current mode"""
        return self._current_mode
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_effect()
        self.clear_all()
        self._log("NeoPixel controller cleaned up")
