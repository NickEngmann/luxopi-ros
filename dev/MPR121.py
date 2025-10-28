#!/usr/bin/env python3
"""
MPR121 Capacitive Touch Sensor Calibration Script
For testing robot petting detection through PLA dielectric

This script helps you:
1. Monitor baseline and filtered values in real-time
2. See the delta (difference) that triggers detection
3. Test different threshold configurations
4. Identify optimal settings for your electrode setup

CALIBRATED DEFAULTS (per-channel):
  Channel 0 (Bottom):      Touch=7, Release=7 (weak signal)
  Channel 1 (Front-Right): Touch=8, Release=8 (good signal)
  Channel 2 (Front-Left):  Touch=8, Release=8 (good signal)
  Channel 3 (Top-Front):   Touch=8, Release=8 (weak signal)
  Channel 4 (Antenna):     Touch=8, Release=8 (strong signal)

Usage examples:
  # Basic usage with calibrated defaults
  python3 MPR121.py

  # Monitor specific channels only
  python3 MPR121.py --channels 0 2 4

  # Override with global thresholds for all channels
  python3 MPR121.py --touch-threshold 12 --release-threshold 8

  # Override specific channels only
  python3 MPR121.py --channel-thresholds 0:6:4 4:15:10

  # Faster refresh rate
  python3 MPR121.py --refresh-rate 0.2

  # Adjust release event detection (enabled by default)
  python3 MPR121.py --release-event-threshold 20 --release-cooldown 2.0

  # Disable release event detection if you only want touches
  python3 MPR121.py --no-detect-releases

  # Recommended for robot petting: detect both touches and releases
  python3 MPR121.py --channels 4 1 2 3 --touch-threshold 10

  # Custom channel names
  python3 MPR121.py --channel-names "Top" "Bottom" "Left" "Right" "Center"

  # Different I2C address
  python3 MPR121.py --i2c-address 0x5B
"""

import time
import board
import busio
import adafruit_mpr121
import argparse
import sys

# ============================================================================
# ARGUMENT PARSER
# ============================================================================

def parse_arguments():
    """Parse command-line arguments for calibration configuration."""
    parser = argparse.ArgumentParser(
        description='MPR121 Capacitive Touch Sensor Calibration Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --channels 0 1 2                    # Monitor first 3 channels only
  %(prog)s --touch-threshold 12                # Set touch threshold to 12
  %(prog)s --channel-thresholds 0:12:8 1:10:6  # Different thresholds per channel
  %(prog)s --refresh-rate 0.1                  # Fast refresh (100ms)
  %(prog)s --quiet                             # Minimal output
        """
    )

    # Channel configuration
    channel_group = parser.add_argument_group('Channel Configuration')
    channel_group.add_argument(
        '--channels', '-c',
        type=int,
        nargs='+',
        default=None,
        metavar='N',
        help='Specific channels to monitor (0-11). Default: all configured channels'
    )
    channel_group.add_argument(
        '--num-channels', '-n',
        type=int,
        default=5,
        metavar='N',
        help='Total number of channels to configure (1-12). Default: 5'
    )
    channel_group.add_argument(
        '--channel-names',
        type=str,
        nargs='+',
        default=None,
        metavar='NAME',
        help='Custom names for each channel. Must match number of channels.'
    )

    # Threshold configuration
    threshold_group = parser.add_argument_group('Threshold Configuration')
    threshold_group.add_argument(
        '--touch-threshold', '-t',
        type=int,
        default=5,
        metavar='N',
        help='Touch threshold for all channels (0-255). Overrides calibrated per-channel defaults. Default: use per-channel calibration'
    )
    threshold_group.add_argument(
        '--release-threshold', '-r',
        type=int,
        default=6,
        metavar='N',
        help='Release threshold for all channels (0-255). Overrides calibrated per-channel defaults. Default: use per-channel calibration'
    )
    threshold_group.add_argument(
        '--channel-thresholds',
        type=str,
        nargs='+',
        default=None,
        metavar='CH:TOUCH:RELEASE',
        help='Per-channel thresholds in format "channel:touch:release" (e.g., "0:12:8 1:10:6")'
    )
    threshold_group.add_argument(
        '--detect-releases',
        action='store_true',
        default=True,
        help='Detect release events (large negative deltas) in addition to touches (default: enabled)'
    )
    threshold_group.add_argument(
        '--no-detect-releases',
        dest='detect_releases',
        action='store_false',
        help='Disable release event detection'
    )
    threshold_group.add_argument(
        '--release-event-threshold',
        type=int,
        default=20,
        metavar='N',
        help='Negative delta threshold for release detection (positive number). Default: 20'
    )
    threshold_group.add_argument(
        '--release-cooldown',
        type=float,
        default=2.0,
        metavar='SEC',
        help='Cooldown time after release event before next release can trigger. Default: 2.0'
    )

    # Display configuration
    display_group = parser.add_argument_group('Display Configuration')
    display_group.add_argument(
        '--refresh-rate',
        type=float,
        default=0.1,
        metavar='SEC',
        help='Display refresh rate in seconds. Default: 0.1'
    )
    display_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output (no banner, compact display)'
    )
    display_group.add_argument(
        '--show-raw',
        action='store_true',
        help='Show raw sensor values in addition to delta'
    )
    display_group.add_argument(
        '--csv',
        action='store_true',
        help='Output in CSV format for logging/analysis'
    )

    # Hardware configuration
    hw_group = parser.add_argument_group('Hardware Configuration')
    hw_group.add_argument(
        '--i2c-address',
        type=lambda x: int(x, 0),  # Accept hex (0x5A) or decimal
        default=0x5A,
        metavar='ADDR',
        help='I2C address of MPR121 (hex or decimal). Default: 0x5A'
    )
    hw_group.add_argument(
        '--baseline-only',
        action='store_true',
        help='Show baseline readings only and exit (for initial calibration)'
    )

    return parser.parse_args()

# ============================================================================
# CONFIGURATION FROM ARGUMENTS
# ============================================================================

args = parse_arguments()

# Number of channels
NUM_CHANNELS = args.num_channels

# Channel names (default or custom)
if args.channel_names:
    if len(args.channel_names) != NUM_CHANNELS:
        print(f"Error: --channel-names must provide exactly {NUM_CHANNELS} names")
        sys.exit(1)
    CHANNEL_NAMES = args.channel_names
else:
    CHANNEL_NAMES = [
        "Bottom",
        "Front-Right",
        "Front-Left",
        "Top-Front",
        "Antenna",
        "Channel 5",
        "Channel 6",
        "Channel 7",
        "Channel 8",
        "Channel 9",
        "Channel 10",
        "Channel 11"
    ][:NUM_CHANNELS]

# Channels to monitor (default: all)
MONITOR_CHANNELS = args.channels if args.channels else list(range(NUM_CHANNELS))

# Validate channel numbers
for ch in MONITOR_CHANNELS:
    if ch >= NUM_CHANNELS or ch < 0:
        print(f"Error: Channel {ch} is out of range (0-{NUM_CHANNELS-1})")
        sys.exit(1)

# Threshold settings (global defaults)
TOUCH_THRESHOLD = args.touch_threshold
RELEASE_THRESHOLD = args.release_threshold

# Per-channel default thresholds (calibrated values)
# These are used unless overridden by command-line arguments
DEFAULT_CHANNEL_THRESHOLDS = {
    0: (25, 25),   # Bottom - weak signal
    1: (25, 25),   # Front-Right - good signal
    2: (25, 25),   # Front-Left - good signal
    3: (22, 22),   # Top-Front - good signal
    4: (35, 45),   # Antenna - strong signal (excellent)
}

# Check if user explicitly provided global thresholds (non-default values)
user_provided_global = (args.touch_threshold != 5 or args.release_threshold != 6)

# Start with calibrated defaults (unless user wants global thresholds)
if user_provided_global:
    # User wants global thresholds for all channels
    CHANNEL_THRESHOLDS = {}
else:
    # Use calibrated per-channel defaults
    CHANNEL_THRESHOLDS = DEFAULT_CHANNEL_THRESHOLDS.copy()

# Apply user-specified per-channel overrides
if args.channel_thresholds:
    for threshold_spec in args.channel_thresholds:
        try:
            parts = threshold_spec.split(':')
            if len(parts) != 3:
                raise ValueError(f"Invalid format: {threshold_spec}")
            ch = int(parts[0])
            touch = int(parts[1])
            release = int(parts[2])

            if ch >= NUM_CHANNELS or ch < 0:
                raise ValueError(f"Channel {ch} out of range")
            if touch < 0 or touch > 255:
                raise ValueError(f"Touch threshold {touch} out of range (0-255)")
            if release < 0 or release > 255:
                raise ValueError(f"Release threshold {release} out of range (0-255)")

            CHANNEL_THRESHOLDS[ch] = (touch, release)
        except Exception as e:
            print(f"Error parsing threshold '{threshold_spec}': {e}")
            sys.exit(1)

# Display settings
REFRESH_RATE = args.refresh_rate
QUIET_MODE = args.quiet
SHOW_RAW = args.show_raw
CSV_MODE = args.csv
BASELINE_ONLY = args.baseline_only

# Release detection settings
DETECT_RELEASES = args.detect_releases
RELEASE_EVENT_THRESHOLD = args.release_event_threshold
RELEASE_COOLDOWN = args.release_cooldown

# Validate refresh rate
if REFRESH_RATE < 0.01:
    print("Error: Refresh rate must be at least 0.01 seconds")
    sys.exit(1)

# ============================================================================
# INITIALIZATION
# ============================================================================

if not QUIET_MODE and not CSV_MODE:
    print("=" * 80)
    print("MPR121 Capacitive Touch Calibration Tool")
    print("=" * 80)
    print()

# Create I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Create MPR121 object with custom address
try:
    mpr121 = adafruit_mpr121.MPR121(i2c, address=args.i2c_address)
    if not QUIET_MODE and not CSV_MODE:
        print(f"✓ MPR121 sensor initialized successfully at address 0x{args.i2c_address:02X}")
except Exception as e:
    print(f"✗ Failed to initialize MPR121 at address 0x{args.i2c_address:02X}: {e}")
    exit(1)

# Configure thresholds
if not QUIET_MODE and not CSV_MODE:
    print(f"\nConfiguring thresholds:")
    if CHANNEL_THRESHOLDS:
        if user_provided_global:
            print("  ERROR: This shouldn't happen - CHANNEL_THRESHOLDS set with user_provided_global")
        else:
            print("  Using calibrated per-channel thresholds:")
            for ch in MONITOR_CHANNELS:
                if ch in CHANNEL_THRESHOLDS:
                    touch, release = CHANNEL_THRESHOLDS[ch]
                    print(f"    Channel {ch} ({CHANNEL_NAMES[ch]}): Touch={touch}, Release={release}")
                else:
                    print(f"    Channel {ch} ({CHANNEL_NAMES[ch]}): Touch={TOUCH_THRESHOLD}, Release={RELEASE_THRESHOLD}")
    else:
        print(f"  Global Touch Threshold: {TOUCH_THRESHOLD}")
        print(f"  Global Release Threshold: {RELEASE_THRESHOLD}")
        print("  (Applied to all channels)")

    if DETECT_RELEASES:
        print(f"\n  Release Event Detection: ENABLED")
        print(f"    Negative Delta Threshold: -{RELEASE_EVENT_THRESHOLD}")
        print(f"    Cooldown Period: {RELEASE_COOLDOWN}s")
    print()

# Apply thresholds to all channels
for i in range(NUM_CHANNELS):
    if i in CHANNEL_THRESHOLDS:
        touch, release = CHANNEL_THRESHOLDS[i]
        mpr121[i].threshold = touch
        mpr121[i].release_threshold = release
    else:
        mpr121[i].threshold = TOUCH_THRESHOLD
        mpr121[i].release_threshold = RELEASE_THRESHOLD

# Wait for sensor to stabilize
if not QUIET_MODE and not CSV_MODE:
    print("Waiting for sensor to stabilize...")
time.sleep(2)

# ============================================================================
# CALIBRATION BASELINE
# ============================================================================

if not CSV_MODE:
    if not QUIET_MODE:
        print("\n" + "=" * 80)
        print("INITIAL BASELINE READINGS")
        print("=" * 80)
        print(f"\nMonitoring channels: {MONITOR_CHANNELS}")
        print("Take your hands away from the sensor...\n")
    time.sleep(2)

baseline_values = {}
for i in MONITOR_CHANNELS:
    baseline = mpr121.baseline_data(i)
    filtered = mpr121[i].raw_value
    delta = baseline - filtered
    baseline_values[i] = baseline

    if not CSV_MODE and not QUIET_MODE:
        print(f"Channel {i} ({CHANNEL_NAMES[i]}):")
        print(f"  Baseline:  {baseline:4d}")
        print(f"  Filtered:  {filtered:4d}")
        print(f"  Delta:     {delta:4d}")
        if i in CHANNEL_THRESHOLDS:
            print(f"  Touch Threshold: {CHANNEL_THRESHOLDS[i][0]}")
        else:
            print(f"  Touch Threshold: {TOUCH_THRESHOLD}")
        print()

# Exit early if baseline-only mode
if BASELINE_ONLY:
    if not CSV_MODE:
        print("\nBaseline calibration complete!")
        print("\nRecommended settings based on readings:")
        for i in MONITOR_CHANNELS:
            baseline = baseline_values[i]
            # Suggest threshold based on typical 10-20 delta for touch
            suggested_touch = max(8, min(20, baseline // 20))
            suggested_release = suggested_touch + 2
            print(f"  Channel {i}: --channel-thresholds {i}:{suggested_touch}:{suggested_release}")
    sys.exit(0)

if not CSV_MODE:
    if not QUIET_MODE:
        print("\nNow you can start testing! Touch different areas of the sensor.")
        print("Watch the Delta values - when Delta > Threshold, a touch is detected.\n")

# ============================================================================
# REAL-TIME MONITORING
# ============================================================================

if not CSV_MODE and not QUIET_MODE:
    print("=" * 80)
    print("REAL-TIME MONITORING")
    print("=" * 80)
    print("\nPress Ctrl+C to exit\n")
elif CSV_MODE:
    # CSV header
    header_parts = ["timestamp"]
    for i in MONITOR_CHANNELS:
        header_parts.append(f"ch{i}_baseline")
        header_parts.append(f"ch{i}_filtered")
        header_parts.append(f"ch{i}_delta")
        header_parts.append(f"ch{i}_touched")
    print(",".join(header_parts))

# Track last release event time for cooldown (per-channel)
last_release_time = {ch: 0 for ch in MONITOR_CHANNELS}

# Track noise spike recovery state (per-channel)
# Matches robot implementation in i2c_device_manager.py lines 213-216
NOISE_SPIKE_THRESHOLD = 65  # Delta values > this are considered noise spikes
NOISE_RECOVERY_THRESHOLD = 5  # Must return below this to clear recovery state
in_noise_recovery = {ch: False for ch in MONITOR_CHANNELS}

try:
    iteration = 0
    start_time = time.time()

    while True:
        current_time = time.time() - start_time

        if CSV_MODE:
            # CSV output mode
            row_parts = [f"{current_time:.3f}"]
            for i in MONITOR_CHANNELS:
                baseline = mpr121.baseline_data(i)
                filtered = mpr121[i].raw_value
                delta = baseline - filtered
                threshold = CHANNEL_THRESHOLDS[i][0] if i in CHANNEL_THRESHOLDS else TOUCH_THRESHOLD
                is_touched = 1 if abs(delta) >= threshold else 0

                row_parts.append(str(baseline))
                row_parts.append(str(filtered))
                row_parts.append(str(delta))
                row_parts.append(str(is_touched))

            print(",".join(row_parts))

        else:
            # Normal display mode
            if iteration % 20 == 0 and not QUIET_MODE:
                print("\n" + "-" * 80)
                print("Delta symbols: [xxx]=Spike(>65) | *xxx*=Recovery/High | xxx=Normal")
                print("-" * 80)
                if SHOW_RAW:
                    print(f"{'Channel':<25} {'Baseline':<10} {'Filtered':<10} {'Delta':<8} {'Threshold':<10} {'Status':<10}")
                else:
                    print(f"{'Channel':<25} {'Delta':<8} {'Threshold':<10} {'Status':<10}")
                print("-" * 80)

            # Read monitored channels
            touched_any = False
            touched_channels = []
            released_any = False
            released_channels = []

            for i in MONITOR_CHANNELS:
                baseline = mpr121.baseline_data(i)
                filtered = mpr121[i].raw_value
                delta_raw = baseline - filtered  # Raw delta for display

                # === NOISE SPIKE RECOVERY LOGIC ===
                # Matches robot implementation in i2c_device_manager.py lines 263-279
                # Track noise spikes and ignore all readings until baseline returns
                if abs(delta_raw) > NOISE_SPIKE_THRESHOLD:
                    # Detected noise spike - enter recovery mode
                    if not in_noise_recovery[i]:
                        in_noise_recovery[i] = True
                elif abs(delta_raw) < NOISE_RECOVERY_THRESHOLD:
                    # Baseline has recovered - exit recovery mode
                    in_noise_recovery[i] = False

                # If in recovery mode, ignore this reading for touch detection
                if in_noise_recovery[i]:
                    delta = 0  # Treat as no touch while recovering
                else:
                    delta = delta_raw  # Use actual reading

                # Get thresholds for this channel
                if i in CHANNEL_THRESHOLDS:
                    threshold = CHANNEL_THRESHOLDS[i][0]
                    release_threshold = CHANNEL_THRESHOLDS[i][1]
                else:
                    threshold = TOUCH_THRESHOLD
                    release_threshold = RELEASE_EVENT_THRESHOLD

                is_touched = abs(delta) >= threshold

                # Check for release events (large negative deltas)
                is_release_event = False
                if DETECT_RELEASES:
                    if delta < -release_threshold:
                        # Check cooldown
                        time_since_last_release = current_time - last_release_time[i]
                        if time_since_last_release > RELEASE_COOLDOWN:
                            is_release_event = True
                            last_release_time[i] = current_time
                            released_any = True
                            released_channels.append(i)

                # Format status with recovery indicator
                if in_noise_recovery[i]:
                    status = "🔴 RECOVERY (ignoring)"
                elif is_touched:
                    status = "🐾 TOUCHED!"
                    touched_any = True
                    touched_channels.append(i)
                elif is_release_event:
                    status = "👋 RELEASED!"
                else:
                    status = ""

                # Highlight high deltas - use raw delta for display
                delta_str = f"{delta_raw:4d}"
                if abs(delta_raw) > NOISE_SPIKE_THRESHOLD:  # Noise spike
                    delta_str = f"[{delta_raw:3d}]"  # Brackets for spike
                elif in_noise_recovery[i]:  # In recovery
                    delta_str = f"*{delta_raw:3d}*"  # Asterisks for recovery
                elif delta > threshold * 0.7:  # Approaching touch threshold
                    delta_str = f"*{delta_raw:3d}*"
                elif DETECT_RELEASES and delta_raw < -release_threshold * 0.7:  # Approaching release
                    delta_str = f"*{delta_raw:3d}*"

                # Print row (in quiet mode, only print if there's a touch/release)
                if not QUIET_MODE or status:
                    channel_name = f"Ch{i} ({CHANNEL_NAMES[i]})"

                    if SHOW_RAW:
                        print(f"{channel_name:<25} {baseline:<10} {filtered:<10} {delta_str:<8} {threshold:<10} {status:<10}")
                    else:
                        print(f"{channel_name:<25} {delta_str:<8} {threshold:<10} {status:<10}")

            # Summary lines
            if touched_any and not QUIET_MODE:
                channels_str = ", ".join([CHANNEL_NAMES[ch] for ch in touched_channels])
                print(f"\n⚡ TOUCH DETECTED on: {channels_str} ⚡")

            if released_any and not QUIET_MODE:
                channels_str = ", ".join([CHANNEL_NAMES[ch] for ch in released_channels])
                print(f"\n👋 RELEASE DETECTED on: {channels_str} 👋")

        time.sleep(REFRESH_RATE)
        iteration += 1

except KeyboardInterrupt:
    if CSV_MODE or QUIET_MODE:
        # Just exit cleanly in CSV or quiet mode
        sys.exit(0)

    print("\n\n" + "=" * 80)
    print("CALIBRATION SUMMARY")
    print("=" * 80)
    print(f"\nFinal readings for monitored channels {MONITOR_CHANNELS}:")
    print()

    max_delta = 0
    min_delta = 999
    channel_stats = {}

    for i in MONITOR_CHANNELS:
        baseline = mpr121.baseline_data(i)
        filtered = mpr121[i].raw_value
        delta = baseline - filtered

        max_delta = max(max_delta, delta)
        min_delta = min(min_delta, delta)
        channel_stats[i] = {
            'baseline': baseline,
            'filtered': filtered,
            'delta': delta,
            'touch_threshold': mpr121[i].threshold,
            'release_threshold': mpr121[i].release_threshold
        }

        print(f"Channel {i} ({CHANNEL_NAMES[i]}):")
        print(f"  Baseline:  {baseline:4d}")
        print(f"  Filtered:  {filtered:4d}")
        print(f"  Delta:     {delta:4d}")
        print(f"  Touch Threshold: {mpr121[i].threshold}")
        print(f"  Release Threshold: {mpr121[i].release_threshold}")
        print()

    print("=" * 80)
    print("CALIBRATION TIPS")
    print("=" * 80)
    print("""
Based on your observations:

1. If Delta when touching is < 12:
   → Reduce touch threshold (try 6-8)
   → Your PLA might be thick or electrodes small
   Example: --channel-thresholds 0:8:6 1:8:6

2. If Delta when touching is > 20:
   → Increase touch threshold (try 15-20)
   → Good electrode contact and thin PLA
   Example: --channel-thresholds 0:15:10 1:15:10

3. If you see false triggers (touches when not touching):
   → Increase touch threshold
   → Check for electrical noise or grounding issues
   → Ensure electrodes are spaced apart
   Example: --touch-threshold 12

4. If touches are inconsistent:
   → Check wire connections are solid
   → Ensure aluminum foil has good contact with copper tape
   → Make sure sensor has good ground reference
   → Try monitoring specific channels: --channels 0 1 2

5. Ideal Delta range when touching: 15-30
   → Gives good detection with noise margin

6. For release event detection (detects hand removal):
   → Enable with: --detect-releases
   → Adjust sensitivity: --release-event-threshold 20
   → Adjust cooldown: --release-cooldown 2.0
   → Useful for detecting "petting end" events

7. For data logging and analysis:
   → Use CSV mode: --csv > calibration_log.csv
   → Monitor only problem channels: --channels 2 3
   → Use baseline-only for quick check: --baseline-only
    """)

    # Generate recommended command
    print("\n" + "=" * 80)
    print("RECOMMENDED SETTINGS")
    print("=" * 80)

    if not user_provided_global and not args.channel_thresholds:
        print("\n✓ Using calibrated per-channel defaults:")
        for ch in sorted(DEFAULT_CHANNEL_THRESHOLDS.keys()):
            if ch < NUM_CHANNELS:
                touch, release = DEFAULT_CHANNEL_THRESHOLDS[ch]
                print(f"  Channel {ch} ({CHANNEL_NAMES[ch]}): Touch={touch}, Release={release}")
        print("\nTo run with these defaults:")
        print("python3 MPR121.py")
        if len(MONITOR_CHANNELS) < NUM_CHANNELS:
            print(f"  --channels {' '.join(map(str, MONITOR_CHANNELS))}")
    else:
        print("\nBased on your current configuration:")
        print()

        if len(MONITOR_CHANNELS) < NUM_CHANNELS:
            print(f"python3 MPR121.py --channels {' '.join(map(str, MONITOR_CHANNELS))} \\")
        else:
            print(f"python3 MPR121.py \\")

        if CHANNEL_THRESHOLDS and not user_provided_global:
            # User provided specific channel overrides
            threshold_args = []
            for ch, (touch, release) in sorted(CHANNEL_THRESHOLDS.items()):
                if ch in MONITOR_CHANNELS:
                    threshold_args.append(f"{ch}:{touch}:{release}")
            if threshold_args:
                print(f"  --channel-thresholds {' '.join(threshold_args)} \\")
        elif user_provided_global:
            # User wants global thresholds
            print(f"  --touch-threshold {TOUCH_THRESHOLD} \\")
            print(f"  --release-threshold {RELEASE_THRESHOLD} \\")

        if REFRESH_RATE != 0.1:
            print(f"  --refresh-rate {REFRESH_RATE} \\")

        if DETECT_RELEASES:
            print(f"  --detect-releases \\")
            if RELEASE_EVENT_THRESHOLD != 20:
                print(f"  --release-event-threshold {RELEASE_EVENT_THRESHOLD} \\")
            if RELEASE_COOLDOWN != 2.0:
                print(f"  --release-cooldown {RELEASE_COOLDOWN} \\")

        if args.i2c_address != 0x5A:
            print(f"  --i2c-address 0x{args.i2c_address:02X}")
        else:
            print()  # End the command

    print("\nCalibration session complete. Goodbye! 👋\n")