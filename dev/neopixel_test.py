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

# Configuration
PIXEL_COUNT = 102
# Using proper SPI MOSI pin (GPIO 10, Physical Pin 19)
print("Using GPIO 10 (MOSI - Pin 19) for NeoPixel SPI")

BRIGHTNESS = 0.5     # 0.0 to 1.0 (start dim for safety)
SPI_FREQUENCY = 1000000  # Further reduced to 400kHz for better stability

def init_pixels():
    """Initialize pixels with default GRB color order"""
    global pixels
    
    try:
        # Get the SPI bus
        spi = board.SPI()
        
        # Initialize NeoPixels using SPI with default GRB color order
        pixels = neopixel_spi.NeoPixel_SPI(
            spi, 
            PIXEL_COUNT, 
            brightness=BRIGHTNESS,
            auto_write=False,
            pixel_order=neopixel_spi.GRB,
            bpp=3
        )
        
        print(f"NeoPixel SPI initialized: {PIXEL_COUNT} LEDs, Color order: GRB")
        print(f"SPI Frequency: {SPI_FREQUENCY}Hz for stability")
        return True
        
    except Exception as e:
        print(f"Failed to initialize NeoPixel SPI: {e}")
        return False

# Initialize with default order
if not init_pixels():
    print("Make sure SPI is enabled in /boot/firmware/config.txt")
    print("Check that no other devices are using SPI")
    exit(1)

def clear_all():
    """Turn off all LEDs"""
    pixels.fill((0, 0, 0))
    pixels.show()

def set_pixel_color(index, r, g, b):
    """Set a single pixel color"""
    pixels[index] = (r, g, b)

def fill_all(r, g, b):
    """Fill all pixels with color"""
    pixels.fill((r, g, b))
    pixels.show()

def simple_test():
    """Simple test to verify basic functionality"""
    print(f"\n=== Running SPI NeoPixel Test ===")
    
    try:
        # Test individual colors
        print("Testing individual colors...")
        
        # Red
        print("Testing RED (255,0,0)...")
        fill_all(255, 0, 0)
        time.sleep(2)
        
        # Green
        print("Testing GREEN (0,255,0)...")
        fill_all(0, 255, 0)
        time.sleep(2)
        
        # Blue
        print("Testing BLUE (0,0,255)...")
        fill_all(0, 0, 255)
        time.sleep(2)
        
        # White (dimmed for safety)
        print("Testing WHITE (100,100,100)...")
        fill_all(100, 100, 100)
        time.sleep(2)
        
        # Test a few pixels individually
        print("Testing individual pixel consistency...")
        clear_all()
        
        # Light up every 10th pixel in red
        for i in range(0, PIXEL_COUNT, 10):
            set_pixel_color(i, 255, 0, 0)
        pixels.show()
        time.sleep(1)
        
        # Off
        print("Turning OFF...")
        clear_all()
        
        print("✅ SPI test completed!")
        return True
        
    except Exception as e:
        print(f"❌ SPI test failed: {e}")
        return False

def color_wipe(color, delay=0.03):
    """Light up LEDs one by one with specified color"""
    r, g, b = color
    print(f"Color wipe: {color}")
    for i in range(PIXEL_COUNT):
        set_pixel_color(i, r, g, b)
        pixels.show()
        time.sleep(delay)

def spinning_dot(color=(255, 255, 255), cycles=3, delay=0.04):
    """Single dot spinning around the ring"""
    r, g, b = color
    print(f"Spinning dot: {color}")
    for cycle in range(cycles):
        for i in range(PIXEL_COUNT):
            clear_all()
            set_pixel_color(i, r, g, b)
            pixels.show()
            time.sleep(delay)

def rainbow_cycle(cycles=2, delay=0.01):
    """Generate rainbow colors across all LEDs"""
    print("Rainbow cycle")
    
    def wheel(pos):
        """Generate rainbow colors across 0-255 positions"""
        if pos < 85:
            return (pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return (255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return (0, pos * 3, 255 - pos * 3)
    
    for cycle in range(cycles):
        for j in range(256):
            for i in range(PIXEL_COUNT):
                pixel_index = (i * 256 // PIXEL_COUNT) + j
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
            for i in range(0, PIXEL_COUNT, 3):
                if (i + q) < PIXEL_COUNT:
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
        for offset in range(PIXEL_COUNT):
            for i in range(PIXEL_COUNT):
                # Calculate sine wave value
                angle = (i + offset) * 2 * math.pi / PIXEL_COUNT
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
        for _ in range(5):
            set_pixel_color(random.randint(0, PIXEL_COUNT - 1), 0, 0, 0)

        # Turn on some random LEDs with random colors
        for _ in range(8):
            i = random.randint(0, PIXEL_COUNT - 1)
            r = random.randint(50, 255)
            g = random.randint(50, 255)
            b = random.randint(50, 255)
            set_pixel_color(i, r, g, b)

        pixels.show()
        time.sleep(delay)

def segment_test():
    """Test different segments of the ring"""
    print("Segment test - dividing ring into colored sections")
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    segments = PIXEL_COUNT // 4

    clear_all()
    
    for i, (r, g, b) in enumerate(colors):
        start_idx = i * segments
        end_idx = min((i + 1) * segments, PIXEL_COUNT)
        
        print(f"  Segment {i+1}: LEDs {start_idx}-{end_idx-1} = ({r}, {g}, {b})")

        for j in range(start_idx, end_idx):
            set_pixel_color(j, r, g, b)

    pixels.show()
    time.sleep(3)

def hold_color(r, g, b, color_name):
    """Hold a solid color until interrupted"""
    print(f"Setting all LEDs to {color_name} ({r}, {g}, {b})")
    print("Press Ctrl+C to stop")
    
    # Set the color once
    fill_all(r, g, b)
    
    # Add a small delay to ensure data is fully transmitted
    time.sleep(0.1)
    
    try:
        # Simply wait indefinitely without refreshing
        # The LEDs will maintain their state
        while True:
            time.sleep(1)  # Sleep for 1 second intervals
                
    except KeyboardInterrupt:
        print(f"\n🛑 {color_name} mode stopped")
        clear_all()

def main():
    """Main test sequence with argparse"""
    parser = argparse.ArgumentParser(description='NeoPixel SPI Test for Raspberry Pi 5')
    parser.add_argument('--mode', '-m', choices=['simple', 'full', 'wipe', 'spin', 'rainbow', 'chase', 'breathe', 'wave', 'sparkle', 'segment', 'white', 'red', 'green', 'blue'],
                       default='simple', help='Test mode to run (default: simple)')
    parser.add_argument('--cycles', '-c', type=int, default=3, help='Number of cycles for effects (default: 3)')
    parser.add_argument('--delay', '-d', type=float, default=0.03, help='Delay between steps (default: 0.03)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("NeoPixel SPI Test for Raspberry Pi 5")
    print(f"LEDs: {PIXEL_COUNT}")
    print(f"Pin: GPIO 10 (MOSI - Physical Pin 19)")
    print(f"Brightness: {BRIGHTNESS * 100:.0f}%")
    print(f"Mode: {args.mode}")
    print("=" * 60)

    try:
        if args.mode == 'white':
            hold_color(255, 255, 255, "WHITE")
        elif args.mode == 'red':
            hold_color(255, 0, 0, "RED")
        elif args.mode == 'green':
            hold_color(0, 255, 0, "GREEN")
        elif args.mode == 'blue':
            hold_color(0, 0, 255, "BLUE")
        elif args.mode == 'simple':
            simple_test()
        elif args.mode == 'wipe':
            color_wipe((255, 0, 0), args.delay)
            color_wipe((0, 255, 0), args.delay)
            color_wipe((0, 0, 255), args.delay)
        elif args.mode == 'spin':
            spinning_dot((255, 255, 255), args.cycles, args.delay)
        elif args.mode == 'rainbow':
            rainbow_cycle(args.cycles, args.delay)
        elif args.mode == 'chase':
            theater_chase((255, 0, 0), args.cycles, args.delay)
        elif args.mode == 'breathe':
            breathing_effect((255, 100, 0), args.cycles)
        elif args.mode == 'wave':
            wave_effect(args.cycles, args.delay)
        elif args.mode == 'sparkle':
            random_sparkle(args.cycles * 2, args.delay)
        elif args.mode == 'segment':
            segment_test()
        elif args.mode == 'full':
            # Run full test sequence
            if not simple_test():
                print("\n❌ Basic test failed!")
                return
                
            print("\n✅ Basic test successful! Running extended tests...")
            
            effect_count = 0
            while effect_count < args.cycles:
                effect_count += 1
                print(f"\n--- Effect Cycle {effect_count} ---")
                
                clear_all()
                time.sleep(0.5)

                # Basic color wipes
                color_wipe((255, 0, 0), 0.01)
                time.sleep(0.5)
                color_wipe((0, 255, 0), 0.01)
                time.sleep(0.5)
                color_wipe((0, 0, 255), 0.01)
                time.sleep(0.5)
                
                # Dynamic effects
                spinning_dot((255, 0, 255), 2, 0.02)
                theater_chase((0, 255, 255), 2)
                breathing_effect((255, 100, 0), 1)
                wave_effect(1)
                rainbow_cycle(1)
                random_sparkle(3)
                segment_test()

                clear_all()
                print(f"Cycle {effect_count} complete!")
                time.sleep(2)

    except KeyboardInterrupt:
        print("\n\n🛑 Test stopped by user")
        clear_all()
        print("✅ All LEDs turned off safely")
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        clear_all()
        print("✅ All LEDs turned off safely")


if __name__ == "__main__":
    main()