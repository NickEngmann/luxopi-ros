#!/usr/bin/env python3
"""
Adjust Animation Speed - Configure acceleration values for animations

This script allows you to easily adjust the speed/snappiness of animations by
modifying acceleration values across all keyframes.

Usage:
    python3 adjust_animation_speed.py animation.json --preset fastest
    python3 adjust_animation_speed.py animation.json --preset slow -o slow_version.json
    python3 adjust_animation_speed.py animation.json --custom 15.0
    python3 adjust_animation_speed.py animation.json --custom 12-18
"""

import json
import argparse
import random
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


# Acceleration presets (min, max) - range allows for variation
# NOTE: HIGHER acc values = FASTER movement (API docs are misleading!)
# Based on actual testing: 1-10=slow, 10-30=moderate, 30-100=fast, 100-170=faster, 170-254=FAST+++, 0=max
PRESETS = {
    'slowest': (1.0, 5.0),      # Very slow (low acc values)
    'slow': (5.0, 12.0),        # Slow/moderate
    'medium': (12.0, 25.0),     # Moderate to fast
    'fast': (25.0, 140.0),      # Faster
    'fastest': (140.0, 254.0),   # Very fast (high acc values)
    'max': (0.0, 0.0),           # Absolute maximum speed (special case: acc=0)
}


def parse_acceleration_range(value: str) -> Tuple[float, float]:
    """
    Parse acceleration value or range.

    Examples:
        "15.0" -> (15.0, 15.0)
        "12-18" -> (12.0, 18.0)
        "10.5-22.5" -> (10.5, 22.5)
    """
    if '-' in value:
        parts = value.split('-')
        if len(parts) != 2:
            raise ValueError(f"Invalid range format: {value}")
        min_val = float(parts[0])
        max_val = float(parts[1])
        if min_val > max_val:
            raise ValueError(f"Min value ({min_val}) cannot be greater than max ({max_val})")
        return (min_val, max_val)
    else:
        val = float(value)
        return (val, val)


def generate_acceleration_values(
    num_keyframes: int,
    min_acc: float,
    max_acc: float,
    distribution: str = 'varied'
) -> List[float]:
    """
    Generate acceleration values for keyframes.

    Args:
        num_keyframes: Number of keyframes to generate values for
        min_acc: Minimum acceleration value
        max_acc: Maximum acceleration value
        distribution: How to distribute values:
            - 'uniform': All same value (average of min/max)
            - 'varied': Random variation between min and max
            - 'alternating': Alternate between min and max
            - 'progressive': Gradually increase from min to max

    Returns:
        List of acceleration values
    """
    values = []

    if min_acc == max_acc:
        # All same value
        return [min_acc] * num_keyframes

    if distribution == 'uniform':
        # All at average
        avg = (min_acc + max_acc) / 2
        values = [avg] * num_keyframes

    elif distribution == 'varied':
        # Random variation for dynamic movement
        for i in range(num_keyframes):
            # Favor higher values (70% chance of upper half)
            if random.random() < 0.7:
                acc = random.uniform((min_acc + max_acc) / 2, max_acc)
            else:
                acc = random.uniform(min_acc, (min_acc + max_acc) / 2)
            values.append(round(acc, 1))

    elif distribution == 'alternating':
        # Alternate between high and low for bouncy effect
        for i in range(num_keyframes):
            if i % 2 == 0:
                values.append(max_acc)
            else:
                values.append(min_acc)

    elif distribution == 'progressive':
        # Gradually increase speed through animation
        step = (max_acc - min_acc) / max(num_keyframes - 1, 1)
        for i in range(num_keyframes):
            acc = min_acc + (step * i)
            values.append(round(acc, 1))

    return values


def adjust_durations_for_acceleration(
    keyframes: List[Dict],
    old_acc_values: List[float],
    new_acc_values: List[float],
    verbose: bool = True
) -> None:
    """
    Adjust keyframe durations based on acceleration changes.

    IMPORTANT: HIGHER acc value = FASTER movement (tested empirically!)
    - acc increases (e.g., 10→100) = movement gets FASTER = duration gets SHORTER
    - acc decreases (e.g., 100→10) = movement gets SLOWER = duration gets LONGER

    Args:
        keyframes: List of keyframe dictionaries
        old_acc_values: Original acceleration values
        new_acc_values: New acceleration values
        verbose: Print information about changes
    """
    if len(keyframes) != len(old_acc_values) or len(keyframes) != len(new_acc_values):
        if verbose:
            print("⚠ Warning: Keyframe/acceleration count mismatch, skipping duration adjustment")
        return

    old_durations = []
    new_durations = []

    for kf, old_acc, new_acc in zip(keyframes, old_acc_values, new_acc_values):
        old_duration = kf.get('duration', 1.0)
        old_durations.append(old_duration)

        # Calculate new duration based on acceleration change
        # Higher acc = faster movement = shorter duration
        # Lower acc = slower movement = longer duration
        if old_acc > 0 and new_acc > 0:
            # CORRECT FORMULA: old_acc / new_acc
            # Example: old=10, new=100 → ratio=0.1 → duration becomes 10x SHORTER (faster)
            # Example: old=100, new=10 → ratio=10 → duration becomes 10x LONGER (slower)
            duration_ratio = old_acc / new_acc
            new_duration = old_duration * duration_ratio
            # Clamp to reasonable range (0.1s to 5.0s)
            new_duration = max(0.1, min(5.0, new_duration))
        else:
            # Handle edge case where acc=0 (maximum speed)
            if new_acc == 0 and old_acc > 0:
                # Going to max speed - make duration very short
                new_duration = max(0.1, old_duration * 0.05)
            elif old_acc == 0 and new_acc > 0:
                # Going from max speed to slower - make duration longer
                new_duration = min(5.0, old_duration * 20.0)
            else:
                new_duration = old_duration

        kf['duration'] = round(new_duration, 2)
        new_durations.append(new_duration)

    if verbose:
        old_total = sum(old_durations)
        new_total = sum(new_durations)
        print(f"\n✓ Adjusted durations based on acceleration changes")
        print(f"  Old total duration: {old_total:.2f}s")
        print(f"  New total duration: {new_total:.2f}s")
        print(f"  Speed change: {(old_total / new_total):.2f}x {'faster' if new_total < old_total else 'slower'}")


def convert_json_to_python(json_filepath: Path, verbose: bool = True) -> bool:
    """
    Convert JSON animation to Python using json_to_animation.py script.

    Args:
        json_filepath: Path to JSON file
        verbose: Print conversion progress

    Returns:
        True if conversion succeeded, False otherwise
    """
    try:
        python_dir = Path('./python')
        python_dir.mkdir(parents=True, exist_ok=True)

        # Find converter script (should be in same directory)
        script_dir = Path(__file__).parent
        converter_script = script_dir / 'json_to_animation.py'

        if not converter_script.exists():
            if verbose:
                print(f"\n⚠ Warning: Converter script not found at {converter_script}")
            return False

        if verbose:
            print(f"\n🔄 Converting to Python animation...")

        # Build output filename
        python_filename = f"{json_filepath.stem}.py"

        # Run converter script
        result = subprocess.run(
            [sys.executable, str(converter_script), str(json_filepath),
             '-o', str(python_dir / python_filename)],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            if verbose:
                # Extract success message from output
                for line in result.stdout.split('\n'):
                    if 'written to:' in line.lower() or '✓' in line:
                        print(f"  {line.strip()}")
                print(f"✓ Python animation saved to: python/{python_filename}")
            return True
        else:
            if verbose:
                print(f"\n⚠ Conversion failed:")
                print(result.stderr)
            return False

    except subprocess.TimeoutExpired:
        if verbose:
            print(f"\n⚠ Conversion timed out after 30 seconds")
        return False
    except Exception as e:
        if verbose:
            print(f"\n⚠ Error during conversion: {e}")
        return False


def adjust_animation_speed(
    json_data: Dict,
    min_acc: float,
    max_acc: float,
    distribution: str = 'varied',
    adjust_duration: bool = True,
    verbose: bool = True
) -> Dict:
    """
    Adjust acceleration values in animation JSON.

    Args:
        json_data: Animation JSON data
        min_acc: Minimum acceleration value
        max_acc: Maximum acceleration value
        distribution: How to distribute values
        adjust_duration: Also adjust durations based on acceleration changes
        verbose: Print information about changes

    Returns:
        Modified animation JSON
    """
    keyframes = json_data.get('keyframes', [])

    if not keyframes:
        print("⚠ No keyframes found in animation")
        return json_data

    # Get existing acceleration values
    old_values = [kf['servos'].get('acc', 10.0) for kf in keyframes]
    old_min = min(old_values)
    old_max = max(old_values)

    # Generate new acceleration values
    new_values = generate_acceleration_values(
        len(keyframes),
        min_acc,
        max_acc,
        distribution
    )

    # Apply new values
    for kf, new_acc in zip(keyframes, new_values):
        kf['servos']['acc'] = new_acc

    if verbose:
        print(f"\n✓ Updated {len(keyframes)} keyframes")
        print(f"  Old acceleration range: {old_min:.1f} - {old_max:.1f}")
        print(f"  New acceleration range: {min(new_values):.1f} - {max(new_values):.1f}")
        print(f"  Distribution: {distribution}")

        # Show value distribution
        value_counts = {}
        for val in new_values:
            value_counts[val] = value_counts.get(val, 0) + 1

        print(f"\n  Value distribution:")
        for val in sorted(value_counts.keys()):
            count = value_counts[val]
            bar = '█' * (count * 40 // len(keyframes))
            print(f"    {val:4.1f}: {count:2d} keyframes {bar}")

    # Adjust durations if requested
    if adjust_duration:
        adjust_durations_for_acceleration(keyframes, old_values, new_values, verbose)

    return json_data


def main():
    parser = argparse.ArgumentParser(
        description='Adjust animation speed by modifying acceleration values',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Presets (NOTE: HIGHER acc = FASTER movement):
  slowest   - 1-10 (very slow)
  slow      - 10-30 (slow/moderate)
  medium    - 30-100 (moderate to fast)
  fast      - 100-170 (faster)
  fastest   - 170-254 (very fast)
  max       - 0 (absolute maximum speed)

Distribution modes:
  uniform      - All keyframes same value (average)
  varied       - Random variation (default, more dynamic)
  alternating  - Alternate min/max (bouncy effect)
  progressive  - Gradually increase through animation

Examples:
  # Make animation super fast (high acc values)
  python3 adjust_animation_speed.py bounce.json --preset fastest

  # Make it slow and smooth (low acc values)
  python3 adjust_animation_speed.py bounce.json --preset slow -o slow_bounce.json

  # Custom range with varied distribution
  python3 adjust_animation_speed.py bounce.json --custom 100-170

  # All keyframes at exactly 50 (moderate speed, uniform)
  python3 adjust_animation_speed.py bounce.json --custom 50 --dist uniform

  # Progressive speed increase (acc increases from 10 to 200, speeds up over time)
  python3 adjust_animation_speed.py bounce.json --custom 10-200 --dist progressive
        """
    )

    parser.add_argument(
        'json_file',
        help='Input JSON animation file'
    )

    # Speed options (mutually exclusive)
    speed_group = parser.add_mutually_exclusive_group(required=True)
    speed_group.add_argument(
        '--preset', '-p',
        choices=list(PRESETS.keys()),
        help='Use preset acceleration range'
    )
    speed_group.add_argument(
        '--custom', '-c',
        help='Custom acceleration value or range (e.g., "15.0" or "12-18")'
    )

    parser.add_argument(
        '--distribution', '--dist', '-d',
        choices=['uniform', 'varied', 'alternating', 'progressive'],
        default='varied',
        help='How to distribute values (default: varied)'
    )

    parser.add_argument(
        '--output', '-o',
        help='Output file path (defaults to overwriting input file)'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress output messages'
    )

    parser.add_argument(
        '--adjust-duration',
        action='store_true',
        default=True,
        help='Adjust keyframe durations based on acceleration changes (default: enabled)'
    )

    parser.add_argument(
        '--no-adjust-duration',
        action='store_false',
        dest='adjust_duration',
        help='Do not adjust keyframe durations'
    )

    parser.add_argument(
        '--convert',
        action='store_true',
        default=True,
        help='Automatically convert to Python animation after saving (default: enabled)'
    )

    parser.add_argument(
        '--no-convert',
        action='store_false',
        dest='convert',
        help='Do not convert to Python animation'
    )

    args = parser.parse_args()

    # Load JSON
    input_file = Path(args.json_file)
    if not input_file.exists():
        print(f"✗ File not found: {input_file}")
        return 1

    if not args.quiet:
        print(f"Loading {input_file}...")

    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON: {e}")
        return 1

    animation_name = data.get('name', 'unknown')
    keyframe_count = len(data.get('keyframes', []))

    if not args.quiet:
        print(f"✓ Loaded animation: {animation_name}")
        print(f"  Keyframes: {keyframe_count}")

    # Determine acceleration range
    if args.preset:
        min_acc, max_acc = PRESETS[args.preset]
        if not args.quiet:
            print(f"\n  Using preset: {args.preset} ({min_acc:.1f}-{max_acc:.1f})")
    else:
        min_acc, max_acc = parse_acceleration_range(args.custom)
        if not args.quiet:
            print(f"\n  Using custom range: {min_acc:.1f}-{max_acc:.1f}")

    # Validate range
    if min_acc < 0.0 or max_acc > 254.0:
        print(f"⚠ Warning: Acceleration values should be between 0.0 and 254.0")
        print(f"  (You specified: {min_acc:.1f}-{max_acc:.1f})")

    if min_acc > max_acc:
        print(f"⚠ Error: Min acceleration ({min_acc:.1f}) cannot be greater than max ({max_acc:.1f})")
        return 1

    # Adjust animation
    modified_data = adjust_animation_speed(
        data,
        min_acc,
        max_acc,
        args.distribution,
        adjust_duration=args.adjust_duration,
        verbose=not args.quiet
    )

    # Determine output file
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = input_file

    # Save modified JSON
    try:
        with open(output_file, 'w') as f:
            json.dump(modified_data, f, indent=2)

        if not args.quiet:
            print(f"\n✓ Saved to: {output_file}")

            if output_file == input_file:
                print(f"  (Original file overwritten)")
    except Exception as e:
        print(f"\n✗ Error saving file: {e}")
        return 1

    # Convert to Python if requested
    if args.convert:
        success = convert_json_to_python(output_file, verbose=not args.quiet)
        if not success and not args.quiet:
            print(f"\n⚠ Note: JSON saved successfully, but Python conversion failed")

    return 0


if __name__ == '__main__':
    exit(main())
