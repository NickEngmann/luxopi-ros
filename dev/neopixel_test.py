#!/usr/bin/env python3
"""
NeoPixel test using proper SPI pins for Raspberry Pi 5
Uses GPIO 10 (MOSI - Pin 19) which is the correct SPI data output pin
"""

import time
import board
import neopixel_spi
import math
import random
import argparse

# Global variable for pixels (will be initialized later)
pixels = None

def init_pixels(pixel_count, brightness):
    """Initialize pixels with GRBW color order (physically swapped R/G)"""
    global pixels
    
    try:
        # Get the SPI bus
        spi = board.SPI()
        
        # Initialize NeoPixels using SPI with GRBW color order (R and G are swapped in hardware)
        pixels = neopixel_spi.NeoPixel_SPI(
            spi,
            pixel_count, 
            brightness=brightness,
            auto_write=False,
            pixel_order=neopixel_spi.GRBW,
            bpp=4
        )
        
        print(f"NeoPixel SPI initialized: {pixel_count} LEDs, Brightness: {brightness*100:.0f}%, Color order: GRBW (hardware has R/G swapped)")
        return True
        
    except Exception as e:
        print(f"Failed to initialize NeoPixel SPI: {e}")
        return False

def clear_all():
    """Turn off all LEDs"""
    pixels.fill((0, 0, 0, 0))  # Added W=0 for RGBW
    pixels.show()

def set_pixel_color(index, r, g, b, w=0):
    """Set a single pixel color - GRBW order (hardware has G/R swapped)"""
    pixels[index] = (r, g, b, w)

def fill_all(r, g, b, w=0):
    """Fill all pixels with color - GRBW order (hardware has G/R swapped)"""
    pixels.fill((r, g, b, w))
    pixels.show()

def simple_test():
    """Simple test to verify basic functionality"""
    print(f"\n=== Running SPI NeoPixel Test (GRBW) ===")
    
    try:
        # Test individual colors
        print("Testing individual colors...")
        
        # Red (GRBW order: G=0, R=255, B=0, W=0)
        print("Testing RED (255,0,0,0)...")
        fill_all(255, 0, 0, 0)  # With GRBW order, first channel is now correct for red
        time.sleep(2)
        
        # Green (GRBW order: G=255, R=0, B=0, W=0) 
        print("Testing GREEN (0,255,0,0)...")
        fill_all(0, 255, 0, 0)  # With GRBW order, second channel is now correct for green
        time.sleep(2)
        
        # Blue
        print("Testing BLUE (0,0,255,0)...")
        fill_all(0, 0, 255, 0)  # R=0, G=0, B=255, W=0
        time.sleep(2)
        
        # White LED (using the dedicated white channel)
        print("Testing WHITE LED (0,0,0,200)...")
        fill_all(0, 0, 0, 200)  # R=0, G=0, B=0, W=200
        time.sleep(2)
        
        # RGB White (mixing colors - with swapped R/G)
        print("Testing RGB WHITE (200,200,200,0)...")
        fill_all(200, 200, 200, 0)  # Swapped R/G, B=200, W=0
        time.sleep(2)
        
        # Warm white (RGB + W - with swapped R/G)
        print("Testing WARM WHITE (50,50,50,200)...")
        fill_all(50, 50, 50, 200)  # Swapped R/G=50, B=50, W=200
        time.sleep(2)
        
        # Test a few pixels individually
        print("Testing individual pixel consistency...")
        clear_all()
        
        # Light up every 10th pixel in red
        for i in range(0, len(pixels), 10):
            set_pixel_color(i, 255, 0, 0, 0)  # Red with GRBW order
        pixels.show()
        time.sleep(1)
        
        # Off
        print("Turning OFF...")
        clear_all()
        
        print("[SUCCESS] GRBW SPI test completed!")
        return True
        
    except Exception as e:
        print(f"[ERROR] SPI test failed: {e}")
        return False

def color_wipe(color, delay=0.03):
    """Light up LEDs one by one with specified color"""
    if len(color) == 3:
        r, g, b = color
        w = 0
    else:
        r, g, b, w = color
    
    print(f"Color wipe: RGBW({r}, {g}, {b}, {w})")
    for i in range(len(pixels)):
        set_pixel_color(i, r, g, b, w)
        pixels.show()
        time.sleep(delay)

def spinning_dot(color=(255, 255, 255, 0), cycles=3, delay=0.04):
    """Single dot spinning around the ring"""
    if len(color) == 3:
        r, g, b = color
        w = 0
    else:
        r, g, b, w = color
        
    print(f"Spinning dot: RGBW({r}, {g}, {b}, {w})")
    for cycle in range(cycles):
        for i in range(len(pixels)):
            clear_all()
            set_pixel_color(i, r, g, b, w)
            pixels.show()
            time.sleep(delay)

def hold_color(r, g, b, w, color_name):
    """Hold a solid color until interrupted"""
    print(f"Setting all LEDs to {color_name} RGBW({r}, {g}, {b}, {w})")
    print("Press Ctrl+C to stop")
    
    # Set the color once
    fill_all(r, g, b, w)
    
    # Add a small delay to ensure data is fully transmitted
    time.sleep(0.1)
    
    try:
        while True:
            time.sleep(1)
                
    except KeyboardInterrupt:
        print(f"\n[STOP] {color_name} mode stopped")
        clear_all()

def rainbow_cycle(cycles=2, delay=0.01):
    """Generate rainbow colors across all LEDs"""
    print("Rainbow cycle")
    
    def wheel(pos):
        """Generate rainbow colors across 0-255 positions (GRBW order)"""
        if pos < 85:
            # Returns (R, G, B) for GRBW pixel order
            return (pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return (255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return (0, pos * 3, 255 - pos * 3)
    
    for cycle in range(cycles):
        for j in range(256):
            for i in range(len(pixels)):
                pixel_index = (i * 256 // len(pixels)) + j
                r, g, b = wheel(pixel_index & 255)
                set_pixel_color(i, r, g, b)
            pixels.show()
            time.sleep(delay)

def theater_chase(color, cycles=3, delay=0.1):
    """Theater-style chasing lights"""
    r, g, b = color
    print(f"Theater chase: {color}")
    for cycle in range(cycles):
        for q in range(3):
            clear_all()
            for i in range(0, len(pixels), 3):
                if (i + q) < len(pixels):
                    set_pixel_color(i + q, r, g, b)
            pixels.show()
            time.sleep(delay)

def breathing_effect(color, cycles=2, steps=40):
    """Breathing effect - fade in and out"""
    r, g, b = color
    print(f"Breathing effect: {color}")

    for cycle in range(cycles):
        # Fade in
        for i in range(steps):
            brightness = (i / steps) ** 2  # Quadratic easing for smoother effect
            dimmed_r = int(r * brightness)
            dimmed_g = int(g * brightness)
            dimmed_b = int(b * brightness)
            fill_all(dimmed_r, dimmed_g, dimmed_b)
            time.sleep(0.02)

        # Fade out
        for i in range(steps, 0, -1):
            brightness = (i / steps) ** 2
            dimmed_r = int(r * brightness)
            dimmed_g = int(g * brightness)
            dimmed_b = int(b * brightness)
            fill_all(dimmed_r, dimmed_g, dimmed_b)
            time.sleep(0.02)

def wave_effect(cycles=2, delay=0.03):
    """Sine wave moving around the ring"""
    print("Wave effect")
    for cycle in range(cycles):
        for offset in range(len(pixels)):
            for i in range(len(pixels)):
                # Calculate sine wave value
                angle = (i + offset) * 2 * math.pi / len(pixels)
                intensity = (math.sin(angle) + 1) / 2  # Normalize to 0-1

                # Create a blue-to-white wave
                blue_val = int(100 + (155 * intensity))
                white_val = int(50 * intensity)
                set_pixel_color(i, white_val, white_val, blue_val)

            pixels.show()
            time.sleep(delay)

def random_sparkle(duration=4, delay=0.1):
    """Random sparkling effect"""
    print("Random sparkle")
    start_time = time.time()
    
    # Start with all LEDs off
    clear_all()
    
    while time.time() - start_time < duration:
        # Turn off some random LEDs
        for _ in range(min(5, len(pixels))):
            set_pixel_color(random.randint(0, len(pixels) - 1), 0, 0, 0)

        # Turn on some random LEDs with random colors
        for _ in range(min(8, len(pixels))):
            i = random.randint(0, len(pixels) - 1)
            r = random.randint(50, 255)
            g = random.randint(50, 255)
            b = random.randint(50, 255)
            set_pixel_color(i, r, g, b)

        pixels.show()
        time.sleep(delay)

def segment_test():
    """Test different segments of the ring"""
    print("Segment test - dividing ring into colored sections")
    # GRBW order: Red=(255,0,0), Green=(0,255,0), Blue=(0,0,255), Yellow=(255,255,0)
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    segments = max(1, len(pixels) // 4)

    clear_all()
    
    for i, (r, g, b) in enumerate(colors):
        start_idx = i * segments
        end_idx = min((i + 1) * segments, len(pixels))
        
        if start_idx < len(pixels):
            print(f"  Segment {i+1}: LEDs {start_idx}-{end_idx-1} = ({r}, {g}, {b})")

            for j in range(start_idx, end_idx):
                set_pixel_color(j, r, g, b)

    pixels.show()
    time.sleep(3)

def hold_single_leds(r, g, b, w, num_leds, color_name):
    """Light up specific number of LEDs with a color"""
    print(f"Setting {num_leds} LED(s) to {color_name} RGBW({r}, {g}, {b}, {w})")
    print("Press Ctrl+C to stop")
    
    # Clear all first
    clear_all()
    
    # Light up only the specified number of LEDs
    for i in range(min(num_leds, len(pixels))):
        set_pixel_color(i, r, g, b, w)
    
    pixels.show()
    
    # Add a small delay to ensure data is fully transmitted
    time.sleep(0.1)
    
    try:
        while True:
            time.sleep(1)
                
    except KeyboardInterrupt:
        print(f"\n[STOP] {color_name} mode stopped")
        clear_all()

def main():
    """Main test sequence with argparse"""
    parser = argparse.ArgumentParser(description='NeoPixel SPI Test for Raspberry Pi 5')
    parser.add_argument('--mode', '-m', choices=['simple', 'full', 'wipe', 'spin', 'rainbow', 'chase', 'breathe', 'wave', 'sparkle', 'segment', 'white', 'red', 'green', 'blue', 'single'],
                       default='simple', help='Test mode to run (default: simple)')
    parser.add_argument('--cycles', '-c', type=int, default=3, help='Number of cycles for effects (default: 3)')
    parser.add_argument('--delay', '-d', type=float, default=0.03, help='Delay between steps (default: 0.03)')
    parser.add_argument('--leds', '-l', type=int, default=1, help='Number of LEDs to turn on (default: 1 for safety)')
    parser.add_argument('--brightness', '-b', type=float, default=0.1, help='Brightness (0.0 to 1.0, default: 0.1 for safety)')
    parser.add_argument('--pixel-count', '-p', type=int, default=60, help='Total number of pixels in the strip (default: 60)')
    
    args = parser.parse_args()
    
    # Validate brightness
    if 0.0 <= args.brightness <= 1.0:
        brightness = args.brightness
    else:
        print(f"Warning: Brightness must be between 0.0 and 1.0. Using default: 0.1")
        brightness = 0.1
    
    # Initialize pixels with parsed arguments
    print("Using GPIO 10 (MOSI - Pin 19) for NeoPixel SPI")
    if not init_pixels(args.pixel_count, brightness):
        print("Make sure SPI is enabled in /boot/firmware/config.txt")
        print("Check that no other devices are using SPI")
        exit(1)
    
    print("=" * 60)
    print("NeoPixel SPI Test for Raspberry Pi 5")
    print(f"Total LEDs: {args.pixel_count}")
    print(f"Pin: GPIO 10 (MOSI - Physical Pin 19)")
    print(f"Brightness: {brightness * 100:.0f}%")
    print(f"Mode: {args.mode}")
    if args.mode in ['single', 'white', 'red', 'green', 'blue']:
        print(f"LEDs to light: {args.leds}")
    print("=" * 60)

    try:
        if args.mode == 'single':
            # Single LED mode with white at low brightness
            hold_single_leds(0, 0, 0, 255, args.leds, "WHITE (single mode)")
        elif args.mode == 'white':
            hold_single_leds(0, 0, 0, 255, args.leds, "WHITE")  # Pure white LED
        elif args.mode == 'red':
            hold_single_leds(255, 0, 0, 0, args.leds, "RED")  # GRBW order
        elif args.mode == 'green':
            hold_single_leds(0, 255, 0, 0, args.leds, "GREEN")  # GRBW order
        elif args.mode == 'blue':
            hold_single_leds(0, 0, 255, 0, args.leds, "BLUE")
        elif args.mode == 'simple':
            simple_test()
        elif args.mode == 'wipe':
            color_wipe((255, 0, 0, 0), args.delay)  # Red (GRBW)
            color_wipe((0, 255, 0, 0), args.delay)  # Green (GRBW)
            color_wipe((0, 0, 255, 0), args.delay)  # Blue
            color_wipe((0, 0, 0, 200), args.delay)  # White LED
        elif args.mode == 'spin':
            spinning_dot((255, 255, 255, 0), args.cycles, args.delay)
        elif args.mode == 'rainbow':
            rainbow_cycle(args.cycles, args.delay)
        elif args.mode == 'chase':
            theater_chase((255, 0, 0, 0), args.cycles, args.delay)  # Red (GRBW)
        elif args.mode == 'breathe':
            breathing_effect((255, 100, 0, 0), args.cycles)  # Orange-red (GRBW)
        elif args.mode == 'wave':
            wave_effect(args.cycles, args.delay)
        elif args.mode == 'sparkle':
            random_sparkle(args.cycles * 2, args.delay)
        elif args.mode == 'segment':
            segment_test()
        elif args.mode == 'full':
            # Run full test sequence
            if not simple_test():
                print("\n[ERROR] Basic test failed!")
                return
                
            print("\n[SUCCESS] Basic test successful! Running extended tests...")
            
            effect_count = 0
            while effect_count < args.cycles:
                effect_count += 1
                print(f"\n--- Effect Cycle {effect_count} ---")
                
                clear_all()
                time.sleep(0.5)

                # Basic color wipes (GRBW order)
                color_wipe((255, 0, 0, 0), 0.01)  # Red
                time.sleep(0.5)
                color_wipe((0, 255, 0, 0), 0.01)  # Green
                time.sleep(0.5)
                color_wipe((0, 0, 255, 0), 0.01)
                time.sleep(0.5)
                
                # Dynamic effects
                spinning_dot((255, 0, 255, 0), 2, 0.02)  # Magenta (G+B with swap)
                theater_chase((0, 255, 255, 0), 2)
                breathing_effect((255, 100, 0, 0), 1)
                wave_effect(1)
                rainbow_cycle(1)
                random_sparkle(3)
                segment_test()

                clear_all()
                print(f"Cycle {effect_count} complete!")
                time.sleep(2)

    except KeyboardInterrupt:
        print("\n\n[STOP] Test stopped by user")
        clear_all()
        print("[SUCCESS] All LEDs turned off safely")
        
    except Exception as e:
        print(f"\n[ERROR] Error during test: {e}")
        clear_all()
        print("[SUCCESS] All LEDs turned off safely")


if __name__ == "__main__":
    main()