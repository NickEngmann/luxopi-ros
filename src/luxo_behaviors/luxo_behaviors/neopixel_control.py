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
    
    def __init__(self, pixel_count: int = 76, brightness: float = 0.2,
                 logger=None, max_fps: float = 20.0):
        """
        Initialize NeoPixel controller

        Args:
            pixel_count: Number of pixels in the strip (76 total: 60 lighting + 16 status)
            brightness: Brightness level (0.0 to 1.0)
            logger: Optional logger instance for debugging
            max_fps: Maximum frames per second for animations (default 20)
        """
        self.pixel_count = pixel_count
        self.lighting_pixels = 60  # First 60 pixels for lighting
        self.status_pixels_start = 60  # Status pixels start at index 60
        self.status_pixels_count = 16  # 16 pixels for status (60-75)
        self.brightness = brightness
        self.logger = logger
        self.max_fps = max_fps
        self.min_frame_time = 1.0 / max_fps  # Minimum time between updates
        
        # Thread safety
        self._lock = threading.RLock()

        # Separate stop events and threads for lighting and status pixels
        self._lighting_stop_event = threading.Event()
        self._status_stop_event = threading.Event()
        self._lighting_effect_thread = None
        self._status_effect_thread = None

        # Legacy stop event (for compatibility with effects that don't specify)
        self._stop_event = threading.Event()
        self._effect_thread = None
        
        # Current state - now using RGBW
        self._current_mode = NeoPixelMode.OFF
        self._current_color = (0, 0, 0, 0)  # RGBW
        self._is_initialized = False
        
        # Frame rate limiting
        self._last_update_time = 0
        self._frame_skip_count = 0
        self._total_frames = 0
        
        # SPI health monitoring
        self._spi_error_count = 0
        self._consecutive_errors = 0
        self._total_spi_transactions = 0
        self._spi_health_check_interval = 60.0  # Check health every minute
        self._last_health_check = time.time()
        self._health_status = "healthy"
        self._adaptive_fps_enabled = True
        
        # Pixel state tracking for optimization
        self._pixel_cache = [(0, 0, 0, 0)] * pixel_count
        self._pixels_changed = True
        
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
    
    def _reinitialize_spi(self) -> bool:
        """Attempt to reinitialize just the SPI connection without full reset"""
        try:
            # Try to clear and reset the current pixel state
            if hasattr(self, 'pixels'):
                try:
                    # Clear pixels first
                    self.pixels.fill((0, 0, 0, 0))
                    # Add small delay
                    time.sleep(0.05)
                except:
                    pass
            
            # Get the SPI bus
            spi = board.SPI()
            
            # Try to reset the bus
            try:
                if spi.try_lock():
                    spi.unlock()
                    time.sleep(0.01)
            except:
                pass
            
            self._log("SPI connection reset attempted", "debug")
            return True
            
        except Exception as e:
            self._log(f"Failed to reinitialize SPI: {e}", "error")
            return False
    
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
        """Turn off all LEDs with optimization"""
        with self._lock:
            if not self._is_initialized:
                return False

            # Check if already cleared
            clear_color = (0, 0, 0, 0)
            if all(pixel == clear_color for pixel in self._pixel_cache):
                self._current_mode = NeoPixelMode.OFF
                self._current_color = clear_color
                return True

            try:
                self.pixels.fill(clear_color)  # RGBW

                # Try to show but don't block on DMA errors
                try:
                    self.pixels.show()
                    # Only sleep if show succeeded
                    time.sleep(0.01)  # Small delay to ensure clearing takes effect
                except Exception as show_error:
                    # If DMA timeout, just log and continue
                    if "timeout" in str(show_error).lower() or "110" in str(show_error):
                        self._log(f"DMA timeout clearing pixels, continuing: {show_error}", "warn")
                    else:
                        self._log(f"Failed to show clear: {show_error}", "error")

                # Update cache regardless of show success
                self._pixel_cache = [clear_color] * self.pixel_count
                self._pixels_changed = False  # Reset since we just updated
                self._current_mode = NeoPixelMode.OFF
                self._current_color = clear_color
                return True
            except Exception as e:
                self._log(f"Failed to clear pixels: {e}", "error")
                return False
    
    def set_pixel_color(self, index: int, r: int, g: int, b: int, w: int = 0):
        """Set a single pixel color with RGBW support and change tracking"""
        with self._lock:
            if not self._is_initialized or index >= self.pixel_count:
                return False
            
            try:
                new_color = (r, g, b, w)
                # Check if this is actually a change
                if self._pixel_cache[index] != new_color:
                    self.pixels[index] = new_color
                    self._pixel_cache[index] = new_color
                    self._pixels_changed = True
                return True
            except Exception as e:
                self._log(f"Failed to set pixel {index}: {e}", "error")
                return False
    
    def clear_status_pixels(self):
        """Clear only the status pixels (60-75), leaving lighting pixels unchanged"""
        with self._lock:
            if not self._is_initialized:
                return False

            try:
                for i in range(self.status_pixels_start, self.pixel_count):
                    self.set_pixel_color(i, 0, 0, 0, 0)
                self.show()
                return True
            except Exception as e:
                self._log(f"Failed to clear status pixels: {e}", "error")
                return False

    def fill_status_pixels(self, r: int, g: int, b: int, w: int = 0):
        """Fill only status pixels (60-75) with specified color"""
        with self._lock:
            if not self._is_initialized:
                return False

            try:
                for i in range(self.status_pixels_start, self.pixel_count):
                    self.set_pixel_color(i, r, g, b, w)
                self.show()
                return True
            except Exception as e:
                self._log(f"Failed to fill status pixels: {e}", "error")
                return False

    def fill_all(self, r: int, g: int, b: int, w: int = 0, show: bool = True):
        """Fill all pixels with RGBW color with retry logic"""
        with self._lock:
            if not self._is_initialized:
                return False
            
            max_retries = 3
            base_delay = 0.001
            
            new_color = (r, g, b, w)
            # Check if all pixels are already this color
            if all(pixel == new_color for pixel in self._pixel_cache):
                self._log("Fill skipped - pixels already at target color", "debug")
                self._current_mode = NeoPixelMode.SOLID
                self._current_color = new_color
                return True
            
            for attempt in range(max_retries):
                try:
                    self.pixels.fill(new_color)
                    # Update cache
                    self._pixel_cache = [new_color] * self.pixel_count
                    self._pixels_changed = True
                    if show:
                        # Use our enhanced show method with retry
                        if not self.show():
                            if attempt < max_retries - 1:
                                time.sleep(base_delay * (2 ** attempt))
                                continue
                            else:
                                return False
                    self._current_mode = NeoPixelMode.SOLID
                    self._current_color = (r, g, b, w)
                    return True
                except Exception as e:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        self._log(f"Fill error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay:.3f}s", "warn")
                        time.sleep(delay)
                    else:
                        self._log(f"Failed to fill pixels after {max_retries} attempts: {e}", "error")
                        return False
            
            return False
    
    def show(self):
        """Update the strip with current pixel values with retry logic"""
        with self._lock:
            if not self._is_initialized:
                return False
            
            # Retry with exponential backoff
            max_retries = 3
            base_delay = 0.001  # 1ms base delay
            
            for attempt in range(max_retries):
                try:
                    self.pixels.show()
                    # Track successful transaction
                    self._total_spi_transactions += 1
                    # Reset error counts on success
                    self._spi_error_count = 0
                    self._consecutive_errors = 0
                    return True
                except Exception as e:
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        delay = base_delay * (2 ** attempt)
                        # Check if it's a DMA timeout first
                        if "timeout" in str(e).lower() or "110" in str(e):
                            # DMA timeout - skip retries
                            self._log(f"SPI DMA timeout detected: {e}", "error")
                            self._spi_error_count += 1
                            self._consecutive_errors += 1
                            return False

                        self._log(f"SPI show error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay:.3f}s", "warn")
                        time.sleep(delay)

                        # Try to reinitialize on second retry (but not for DMA issues)
                        if attempt == 1 and "timeout" not in str(e).lower():
                            self._log("Attempting SPI reinitialization", "warn")
                            self._reinitialize_spi()
                    else:
                        # Track failed transaction
                        self._total_spi_transactions += 1
                        # Track consecutive errors
                        self._spi_error_count += 1
                        self._consecutive_errors += 1
                        
                        self._log(f"Failed to show pixels after {max_retries} attempts: {e}", "error")
                        
                        # If too many consecutive errors, try full reinit
                        if self._spi_error_count > 10:
                            self._log("Too many SPI errors, attempting full reinitialization", "error")
                            self._initialize_pixels()
                            self._spi_error_count = 0
                        
                        return False
            
            return False
    
    def _should_skip_frame(self) -> bool:
        """Check if we should skip this frame based on rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self._last_update_time
        
        # If SPI errors are high, reduce frame rate further
        if self._consecutive_errors > 5:
            adjusted_min_time = self.min_frame_time * 2  # Half the frame rate
        elif self._consecutive_errors > 2:
            adjusted_min_time = self.min_frame_time * 1.5
        else:
            adjusted_min_time = self.min_frame_time
        
        if time_since_last < adjusted_min_time:
            self._frame_skip_count += 1
            return True
        
        return False
    
    def show_rate_limited(self) -> bool:
        """Show with frame rate limiting and change detection"""
        # Skip if no changes
        if not self._pixels_changed:
            return True
        
        if self._should_skip_frame():
            return True  # Pretend success but skip the actual update
        
        # Update timing
        self._last_update_time = time.time()
        self._total_frames += 1
        
        # Log frame skip stats periodically
        if self._total_frames % 100 == 0 and self._frame_skip_count > 0:
            skip_rate = (self._frame_skip_count / self._total_frames) * 100
            self._log(f"Frame stats: {self._total_frames} total, {self._frame_skip_count} skipped ({skip_rate:.1f}%)", "debug")
        
        result = self.show()
        if result:
            self._pixels_changed = False  # Reset change flag after successful update
        
        # Periodic health check
        self._check_spi_health()
        
        return result
    
    def _check_spi_health(self):
        """Monitor SPI health and adapt behavior if needed"""
        current_time = time.time()
        
        # Only check periodically
        if current_time - self._last_health_check < self._spi_health_check_interval:
            return
        
        self._last_health_check = current_time
        
        # Calculate error rate
        if self._total_spi_transactions > 0:
            error_rate = self._spi_error_count / self._total_spi_transactions
        else:
            error_rate = 0
        
        # Determine health status and adapt
        previous_status = self._health_status
        
        if error_rate < 0.01:  # Less than 1% errors
            self._health_status = "healthy"
            if self._adaptive_fps_enabled and self.max_fps < 20:
                # Gradually increase FPS if healthy
                self.max_fps = min(20, self.max_fps * 1.1)
                self.min_frame_time = 1.0 / self.max_fps
                self._log(f"SPI health good - increased max FPS to {self.max_fps:.1f}", "info")
                
        elif error_rate < 0.05:  # 1-5% errors
            self._health_status = "degraded"
            if self._adaptive_fps_enabled and self.max_fps > 15:
                # Reduce FPS slightly
                self.max_fps = 15
                self.min_frame_time = 1.0 / self.max_fps
                self._log(f"SPI health degraded ({error_rate:.1%} errors) - reduced max FPS to {self.max_fps}", "warn")
                
        else:  # More than 5% errors
            self._health_status = "poor"
            if self._adaptive_fps_enabled:
                # Significantly reduce FPS
                self.max_fps = 10
                self.min_frame_time = 1.0 / self.max_fps
                self._log(f"SPI health poor ({error_rate:.1%} errors) - reduced max FPS to {self.max_fps}", "error")
        
        # Log health status change
        if previous_status != self._health_status:
            self._log(f"SPI health status changed: {previous_status} -> {self._health_status}", "info")
            self._log(f"Stats: {self._total_spi_transactions} transactions, {self._spi_error_count} errors ({error_rate:.1%})", "info")
        
        # Reset counters periodically to track recent performance
        if self._total_spi_transactions > 10000:
            self._spi_error_count = int(self._spi_error_count * 0.1)  # Keep 10% weight
            self._total_spi_transactions = int(self._total_spi_transactions * 0.1)
    
    def get_health_status(self) -> dict:
        """Get current SPI health status"""
        error_rate = self._spi_error_count / max(1, self._total_spi_transactions)
        return {
            "status": self._health_status,
            "error_rate": error_rate,
            "total_transactions": self._total_spi_transactions,
            "total_errors": self._spi_error_count,
            "consecutive_errors": self._consecutive_errors,
            "current_fps": self.max_fps
        }
    
    def stop_effect(self, section='all'):
        """
        Stop running effects

        Args:
            section: 'all', 'lighting', or 'status' - which section to stop
        """

        if section in ('all', 'lighting'):
            self._lighting_stop_event.set()
            if self._lighting_effect_thread and self._lighting_effect_thread.is_alive():
                self._lighting_effect_thread.join(timeout=1.0)
            self._lighting_stop_event.clear()

        if section in ('all', 'status'):
            self._status_stop_event.set()
            if self._status_effect_thread and self._status_effect_thread.is_alive():
                self._status_effect_thread.join(timeout=1.0)
            self._status_stop_event.clear()

        # Legacy support - stop old-style effects
        if section == 'all':
            self._stop_event.set()
            if self._effect_thread and self._effect_thread.is_alive():
                self._log(f"🛑 Stopping legacy effect thread", "info")
                self._effect_thread.join(timeout=1.0)
            self._stop_event.clear()
    
    def _run_effect(self, effect_func: Callable, section='legacy', *args, **kwargs):
        """
        Run an effect in a separate thread

        Args:
            effect_func: The effect function to run
            section: 'lighting', 'status', or 'legacy' - which thread to use
            *args, **kwargs: Arguments to pass to effect_func
        """
        # Only stop the specific section this effect will use
        if section == 'lighting':
            self.stop_effect(section='lighting')
        elif section == 'status':
            self.stop_effect(section='status')
        else:
            self.stop_effect(section='all')  # Legacy: stop everything

        def effect_wrapper():
            try:
                effect_func(*args, **kwargs)
            except Exception as e:
                self._log(f"Effect error: {e}", "error")

        # Assign to the appropriate thread based on section
        if section == 'lighting':
            self._lighting_effect_thread = threading.Thread(target=effect_wrapper, daemon=True)
            self._lighting_effect_thread.start()
        elif section == 'status':
            self._status_effect_thread = threading.Thread(target=effect_wrapper, daemon=True)
            self._status_effect_thread.start()
        else:
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
    
    def spinning_dot_status(self, color: Union[Tuple[int, int, int], Tuple[int, int, int, int]] = (255, 255, 255, 0),
                           delay: float = 0.04, blocking: bool = False):
        """Single dot spinning around the status pixels (60-75) only"""
        if not self._is_initialized:
            return False

        # Handle both RGB and RGBW color formats
        if len(color) == 3:
            r, g, b = color
            w = 0
        else:
            r, g, b, w = color

        def _spinning_dot_status():
            self._log(f"Status spinning dot: RGBW({r}, {g}, {b}, {w}) - continuous")

            # Clear status pixels first
            self.clear_status_pixels()

            # Spin continuously until stopped, only on status pixels
            while not self._stop_event.is_set():
                for i in range(self.status_pixels_count):
                    if self._stop_event.is_set():
                        break
                    # Clear status pixels
                    for j in range(self.status_pixels_start, self.pixel_count):
                        self.set_pixel_color(j, 0, 0, 0, 0)
                    # Set current status pixel
                    pixel_idx = self.status_pixels_start + i
                    self.set_pixel_color(pixel_idx, r, g, b, w)
                    self.show_rate_limited()
                    time.sleep(delay)

            # Clear status pixels when done
            self.clear_status_pixels()

        if blocking:
            _spinning_dot_status()
        else:
            self._run_effect(_spinning_dot_status)
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
                    self.show_rate_limited()  # Use rate-limited version
                    time.sleep(delay)
            
            self._current_mode = NeoPixelMode.SPINNING_DOT
            self._current_color = (r, g, b, w)
        
        if blocking:
            _spinning_dot()
        else:
            self._run_effect(_spinning_dot)
        return True
    
    def spinning_group_status(self, color: Union[Tuple[int, int, int], Tuple[int, int, int, int]] = (255, 255, 255, 0),
                             group_size: int = 4, delay: float = 0.05, blocking: bool = False):
        """Group of pixels spinning around the status pixels (60-75) only"""
        if not self._is_initialized:
            return False

        # Handle both RGB and RGBW color formats
        if len(color) == 3:
            r, g, b = color
            w = 0
        else:
            r, g, b, w = color

        # Limit group size to status pixel count
        group_size = min(group_size, self.status_pixels_count)

        def _spinning_group_status():
            self._log(f"Status spinning group: RGBW({r}, {g}, {b}, {w}), size: {group_size}")

            # Clear status pixels first
            self.clear_status_pixels()

            # Track previous group positions
            prev_group_positions = set()

            # Spin continuously until stopped
            while not self._stop_event.is_set():
                for start_pos in range(self.status_pixels_count):
                    if self._stop_event.is_set():
                        break

                    # Calculate current group positions within status pixels
                    current_group_positions = set()
                    for i in range(group_size):
                        # Wrap around within status pixels only
                        status_idx = (start_pos + i) % self.status_pixels_count
                        pixel_idx = self.status_pixels_start + status_idx
                        current_group_positions.add(pixel_idx)

                    # Turn off pixels that were on but shouldn't be anymore
                    pixels_to_turn_off = prev_group_positions - current_group_positions
                    for pixel_idx in pixels_to_turn_off:
                        self.set_pixel_color(pixel_idx, 0, 0, 0, 0)

                    # Turn on pixels that should be on
                    for pixel_idx in current_group_positions:
                        self.set_pixel_color(pixel_idx, r, g, b, w)

                    # Update the display
                    self.show_rate_limited()

                    # Store current positions for next iteration
                    prev_group_positions = current_group_positions

                    time.sleep(delay)

            # Clear status pixels when done
            self.clear_status_pixels()

        if blocking:
            _spinning_group_status()
        else:
            self._run_effect(_spinning_group_status)
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
                    
                    # Update the display only once with rate limiting
                    self.show_rate_limited()
                    
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

    def moving_rainbow(self, delay: float = 0.03, blocking: bool = False):
        """
        Create a moving rainbow effect that flows around the LIGHTING pixels only (0-59).
        The rainbow pattern moves continuously until stopped.
        Status pixels (60-75) are left untouched for state machine control.
        """
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

        def _moving_rainbow():
            self._log("🌈 Moving rainbow effect started on lighting pixels (0-59) - continuous", "info")

            # Offset for the rainbow pattern movement
            offset = 0

            # Continuous rainbow movement until stopped (use lighting-specific stop event)
            while not self._lighting_stop_event.is_set():

                # Only update the first 60 LEDs (lighting pixels)
                for i in range(self.lighting_pixels):  # 0-59
                    # Calculate color position with offset for movement
                    # This creates a smooth rainbow that wraps around the lighting ring
                    pixel_index = ((i * 256 // self.lighting_pixels) + offset) & 255
                    r, g, b = _wheel(pixel_index)
                    self.set_pixel_color(i, r, g, b, 0)  # W=0 for pure rainbow colors

                # Update display with rate limiting
                show_result = self.show_rate_limited()

                # Increment offset to move the rainbow
                offset = (offset + 4) % 256  # Adjust speed by changing increment (higher = faster)

                # Wait before next frame
                time.sleep(delay)


            # Clear only lighting LEDs when stopped (leave status pixels alone)
            for i in range(self.lighting_pixels):
                self.set_pixel_color(i, 0, 0, 0, 0)
            self.show()
            self._current_mode = NeoPixelMode.OFF
            self._log("🌈 Rainbow cleared and mode set to OFF", "info")

        if blocking:
            _moving_rainbow()
        else:
            # Run on the lighting-specific thread
            self._run_effect(_moving_rainbow, section='lighting')
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
    
    def set_lighting_color(self, r: int, g: int, b: int, w: int = 255) -> bool:
        """Set color for lighting pixels only (0-59), leaving status pixels unchanged"""
        with self._lock:
            if not self._is_initialized:
                return False

            try:
                for i in range(self.lighting_pixels):
                    self.set_pixel_color(i, r, g, b, w)
                self.show()
                return True
            except Exception as e:
                self._log(f"Failed to set lighting color: {e}", "error")
                return False

    def turn_off_lighting(self) -> bool:
        """Turn off lighting pixels (0-59) only, leaving status pixels unchanged"""
        return self.set_lighting_color(0, 0, 0, 0)

    def set_solid_color(self, r: int, g: int, b: int, w: int = 0) -> bool:
        """Set a solid color across all pixels"""
        return self.fill_all(r, g, b, w)
    
    def set_direction_indicator(self, position: int = 0, primary_color: Tuple[int, int, int, int] = (255, 255, 255, 0),
                               secondary_color: Tuple[int, int, int, int] = (0, 0, 255, 0)) -> bool:
        """
        Create a direction indicator effect similar to pixel_ring
        
        Args:
            position: Primary LED position (0 to pixel_count-1)
            primary_color: Color for the main indicator (default white)
            secondary_color: Color for surrounding LEDs (default blue)
        """
        with self._lock:
            if not self._is_initialized:
                return False
            
            try:
                # Clear all pixels first
                for i in range(self.pixel_count):
                    self._pixel_cache[i] = (0, 0, 0, 0)
                
                # Set primary position
                self.set_pixel_color(position, *primary_color)
                
                # Set adjacent pixels with secondary color
                # Handle wraparound for circular strip
                prev_pos = (position - 1) % self.pixel_count
                next_pos = (position + 1) % self.pixel_count
                
                self.set_pixel_color(prev_pos, *secondary_color)
                self.set_pixel_color(next_pos, *secondary_color)
                
                # Optional: Add dimmer secondary colors further out
                prev_prev = (position - 2) % self.pixel_count
                next_next = (position + 2) % self.pixel_count
                
                # Dim the secondary color for outer ring
                dim_r = secondary_color[0] // 3
                dim_g = secondary_color[1] // 3
                dim_b = secondary_color[2] // 3
                dim_w = secondary_color[3] // 3
                
                self.set_pixel_color(prev_prev, dim_r, dim_g, dim_b, dim_w)
                self.set_pixel_color(next_next, dim_r, dim_g, dim_b, dim_w)
                
                # Update the display
                return self.show()
                
            except Exception as e:
                self._log(f"Failed to set direction indicator: {e}", "error")
                return False

    def spinning_talking_indicator(self, base_color: Tuple[int, int, int, int] = (0, 100, 255, 0),
                                     indicator_color: Tuple[int, int, int, int] = (255, 255, 255, 0),
                                     speed: float = 0.08, blocking: bool = False) -> bool:
        """
        Create a spinning white indicator on blue background for wake word detection.
        All 16 status LEDs are blue, with a white indicator that spins through them.

        Args:
            base_color: Base color for all status LEDs (default blue)
            indicator_color: Color for the spinning indicator (default white)
            speed: Delay between frames in seconds (default 0.08)
            blocking: Whether to block execution (default False)
        """
        def _spinning_talking():
            position = 0

            # Use status-specific stop event (allows lighting effects to run simultaneously)
            while not self._status_stop_event.is_set():
                # First, set all status pixels to the base color
                for i in range(self.status_pixels_start, self.pixel_count):
                    self.set_pixel_color(i, *base_color)

                # Then set the current position to the indicator color
                actual_position = self.status_pixels_start + position
                self.set_pixel_color(actual_position, *indicator_color)

                # Update the display
                self.show_rate_limited()

                # Wait for next frame
                time.sleep(speed)

                # Move to next position (wrapping around)
                position = (position + 1) % self.status_pixels_count

            # Clear status pixels when done
            self.clear_status_pixels()
            self._current_mode = NeoPixelMode.OFF

        if blocking:
            _spinning_talking()
        else:
            # Run on the status-specific thread (won't interfere with lighting effects)
            self._run_effect(_spinning_talking, section='status')
        return True
    
    def get_current_mode(self) -> NeoPixelMode:
        """Get the current mode"""
        return self._current_mode
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_effect()
        self.clear_all()
        self._log("NeoPixel controller cleaned up")
