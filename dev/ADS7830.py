# SPDX-FileCopyrightText: 2023 Liz Clark for Adafruit Industries
# SPDX-License-Identifier: MIT

# Demo to read analog input on all 8 channels with FSR pressure detection
# Auto-scaling version for different resistor values

import time
import board
import argparse
import adafruit_ads7830.ads7830 as ADC
from adafruit_ads7830.analog_in import AnalogIn

i2c = board.I2C()

# Initialize ADS7830
adc = ADC.ADS7830(i2c, 0x38)

# Create analog input objects for all 8 channels
channels = []
for i in range(8):
    channels.append(AnalogIn(adc, i))

# ============================================================================
# CONFIGURATION: Adjust these values based on your resistor setup
# ============================================================================
ADC_MIN = 48000  # ADC value at maximum pressure (fully pressed)
ADC_MAX = 59000  # ADC value at no pressure (not pressed)

# Pressure level percentages (0% = not pressed, 100% = maximum pressure)
# You can adjust these percentages to fine-tune sensitivity
PRESSURE_LEVELS = [
    (5,   "Light Touch", "1"),   # 5% pressure
    (15,  "Light Press", "2"),   # 15% pressure
    (30,  "Medium Press", "3"),  # 30% pressure
    (50,  "Hard Press", "4"),    # 50% pressure
    (70,  "Very Hard", "5"),     # 70% pressure
    (100, "Maximum", "!"),       # 100% pressure
]

# ============================================================================
# AUTO-CALCULATION: Build threshold table based on configuration
# ============================================================================
def calculate_thresholds():
    """
    Calculate ADC thresholds based on min/max values and pressure percentages
    Returns a list of (threshold, name, symbol) tuples
    """
    range_size = ADC_MAX - ADC_MIN
    thresholds = []
    
    print("\n=== Calculated Thresholds ===")
    print(f"ADC Range: {ADC_MAX} (not pressed) to {ADC_MIN} (max press)")
    print(f"Range Size: {range_size} ADC units\n")
    
    for percent, name, symbol in PRESSURE_LEVELS:
        # Calculate threshold: higher ADC values = less pressure
        # So we subtract the percentage from MAX
        threshold = ADC_MAX - (range_size * percent / 100)
        thresholds.append((int(threshold), name, symbol))
        print(f"{name:12} ({symbol}): >= {int(threshold):5d} (at {percent:3d}% pressure)")
    
    print("=" * 40 + "\n")
    return thresholds

# Calculate thresholds once at startup
THRESHOLDS = calculate_thresholds()

def get_pressure_state(value):
    """
    Map ADC value to pressure state using calculated thresholds
    Returns: (state_number, state_name, state_symbol)
    """
    # Check if not pressed (near maximum ADC value)
    if value >= (ADC_MAX - (ADC_MAX - ADC_MIN) * 0.02):  # 2% tolerance for "not pressed"
        return (0, "Not Pressed", "-")
    
    # Check pressure levels from lightest to hardest
    for i, (threshold, name, symbol) in enumerate(THRESHOLDS):
        if value >= threshold:
            return (i + 1, name, symbol)
    
    # If below all thresholds, it's maximum pressure
    return (len(THRESHOLDS), THRESHOLDS[-1][1], THRESHOLDS[-1][2])

def format_channel_output(channel_num, value):
    """Format output for a single channel"""
    state_num, state_name, symbol = get_pressure_state(value)
    
    # Only show detailed info if pressed
    if state_num > 0:
        return f"a{channel_num}:{symbol}[{state_num}]"
    else:
        return f"a{channel_num}:-"

def calibrate_mode():
    """
    Run calibration mode to help fine-tune thresholds
    Press Ctrl+C to exit calibration and return to normal mode
    """
    print("\n=== CALIBRATION MODE ===")
    print("Press each FSR with different amounts of pressure")
    print("Note the ADC values to set ADC_MIN and ADC_MAX")
    print(f"Current settings: MAX={ADC_MAX} (not pressed), MIN={ADC_MIN} (max press)")
    print("Press Ctrl+C to exit calibration\n")
    
    try:
        min_seen = [ADC_MAX] * 8  # Track minimum value seen per channel
        max_seen = [0] * 8        # Track maximum value seen per channel
        
        while True:
            print("\nChannel ADC Values:")
            for i in range(8):
                value = channels[i].value
                
                # Update min/max tracking
                min_seen[i] = min(min_seen[i], value)
                max_seen[i] = max(max_seen[i], value)
                
                # Calculate pressure percentage
                if ADC_MAX > ADC_MIN:
                    pressure_pct = max(0, min(100, ((ADC_MAX - value) / (ADC_MAX - ADC_MIN)) * 100))
                else:
                    pressure_pct = 0
                
                # Create pressure bar
                bar_length = int(pressure_pct / 2)  # Scale to 50 chars max
                bar = '█' * bar_length
                
                # Show pressure state alongside raw value
                state_num, state_name, symbol = get_pressure_state(value)
                state_str = f" [{state_name}]" if state_num > 0 else ""
                
                print(f"Ch{i}: {value:5d} ({pressure_pct:3.0f}%) {bar}{state_str}")
                print(f"      Range: {max_seen[i]:5d} to {min_seen[i]:5d}")
            
            print(f"\nSuggested settings based on observations:")
            print(f"ADC_MAX = {max(max_seen)}  # Not pressed")
            print(f"ADC_MIN = {min(min_seen)}  # Maximum press")
            
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n=== EXITING CALIBRATION ===\n")
        return

def main():
    """Main function with argument parsing"""
    global ADC_MIN, ADC_MAX, THRESHOLDS

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Read analog input from ADS7830 with FSR pressure detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Normal mode (compact output)
  %(prog)s -v                       # Verbose mode (show all values)
  %(prog)s -c                       # Calibration mode
  %(prog)s --channels 2 6           # Only monitor channels 2 and 6
  %(prog)s -v --channels 0 1 2      # Verbose mode, channels 0, 1, 2 only
  %(prog)s --adc-min 48000 --adc-max 59000  # Custom ADC range
  %(prog)s -v -r 0.1                # Verbose mode, 10Hz sample rate
        """
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose mode: show all channel values continuously'
    )

    parser.add_argument(
        '-c', '--calibrate',
        action='store_true',
        help='Run calibration mode to determine ADC min/max values'
    )

    parser.add_argument(
        '--adc-min',
        type=int,
        default=ADC_MIN,
        metavar='VALUE',
        help=f'Minimum ADC value at maximum pressure (default: {ADC_MIN})'
    )

    parser.add_argument(
        '--adc-max',
        type=int,
        default=ADC_MAX,
        metavar='VALUE',
        help=f'Maximum ADC value at no pressure (default: {ADC_MAX})'
    )

    parser.add_argument(
        '-r', '--rate',
        type=float,
        default=0.25,
        metavar='SECONDS',
        help='Sample rate in seconds (default: 0.25)'
    )

    parser.add_argument(
        '--channels',
        type=int,
        nargs='+',
        metavar='N',
        help='Only monitor specific channels (0-7). Example: --channels 2 6'
    )

    args = parser.parse_args()

    # Validate and setup channel filter
    if args.channels is not None:
        # Validate channel numbers
        for ch in args.channels:
            if ch < 0 or ch > 7:
                parser.error(f"Channel {ch} is out of range. Valid channels are 0-7.")
        # Remove duplicates and sort
        args.channels = sorted(set(args.channels))
    else:
        # Default: all channels
        args.channels = list(range(8))

    # Update configuration from arguments
    if args.adc_min != ADC_MIN or args.adc_max != ADC_MAX:
        ADC_MIN = args.adc_min
        ADC_MAX = args.adc_max
        THRESHOLDS = calculate_thresholds()

    # Run calibration mode if requested
    if args.calibrate:
        calibrate_mode()
        return

    # Print header
    print(f"FSR Pressure Detection - Auto-Scaled")
    print(f"Range: {ADC_MAX} (not pressed) to {ADC_MIN} (max press)")
    if args.verbose:
        print("Mode: VERBOSE (showing all channel values)")
    else:
        print("Mode: COMPACT (showing only active channels)")

    # Show which channels are being monitored
    if len(args.channels) < 8:
        print(f"Monitoring channels: {', '.join(map(str, args.channels))}")
    else:
        print("Monitoring channels: All (0-7)")

    print("=" * 70)
    print("Press Ctrl+C to exit\n")

    try:
        while True:
            if args.verbose:
                # Verbose mode: show all channels with full details
                print(f"\n{'=' * 70}")
                print(f"Timestamp: {time.strftime('%H:%M:%S')}")
                print(f"{'=' * 70}")

                for i in args.channels:
                    value = channels[i].value
                    state_num, state_name, symbol = get_pressure_state(value)

                    # Calculate pressure percentage
                    if ADC_MAX > ADC_MIN:
                        pressure_pct = max(0, min(100, ((ADC_MAX - value) / (ADC_MAX - ADC_MIN)) * 100))
                    else:
                        pressure_pct = 0

                    # Create pressure bar
                    bar_length = int(pressure_pct / 2)  # Scale to 50 chars max
                    bar = '█' * bar_length

                    # Format state indicator
                    state_indicator = f"[{symbol}] {state_name}" if state_num > 0 else "[-] Not Pressed"

                    print(f"Channel {i}: {value:5d} ({pressure_pct:3.0f}%) {bar}")
                    print(f"           State: {state_indicator}")
            else:
                # Compact mode: original behavior
                output_parts = []
                active_channels = []

                for i in args.channels:
                    value = channels[i].value
                    state_num, state_name, symbol = get_pressure_state(value)

                    # Track active channels
                    if state_num > 0:
                        active_channels.append((i, value, state_num, state_name))

                    output_parts.append(format_channel_output(i, value))

                # Print compact status line
                print(" ".join(output_parts))

                # If any channels are active, show detailed info on next line
                if active_channels:
                    details = []
                    for ch, val, state, name in active_channels:
                        # Calculate pressure percentage for display
                        pressure_pct = max(0, min(100, ((ADC_MAX - val) / (ADC_MAX - ADC_MIN)) * 100))
                        details.append(f"  Ch{ch}: {name} ({val} = {pressure_pct:.0f}%)")
                    print("\n".join(details))
                    print()  # Extra line for readability

            time.sleep(args.rate)

    except KeyboardInterrupt:
        print("\n\nExiting...")

if __name__ == '__main__':
    main()