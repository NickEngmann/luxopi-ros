#!/usr/bin/env python3
"""
Convert JSON animation to Python animation plugin with hand/acceleration variations.

This script takes a JSON animation file and converts it to a Python animation plugin
that matches the format used in the LuxoPi system, with proper hand (eyebrow/antenna)
and acceleration variations for emotional expression.

Usage:
    python3 json_to_animation.py animations/json/animation_hopping.json
    python3 json_to_animation.py animations/json/animation_hopping.json --output hopping_animation.py
    python3 json_to_animation.py animations/json/animation_hopping.json --install
"""

import json
import argparse
import re
import math
from pathlib import Path
from typing import Dict, List, Tuple


def to_class_name(name: str) -> str:
    """Convert animation name to PascalCase class name."""
    # Remove special characters and convert to words
    words = re.sub(r'[^a-zA-Z0-9]+', ' ', name).split()
    # Capitalize each word and join
    class_name = ''.join(word.capitalize() for word in words)
    # Ensure it ends with 'Animation'
    if not class_name.endswith('Animation'):
        class_name += 'Animation'
    return class_name


def calculate_movement_distance(kf1: Dict, kf2: Dict) -> float:
    """
    Calculate the total angular distance between two keyframes.

    Returns the sum of absolute angular differences for all joints.
    """
    s1 = kf1['servos']
    s2 = kf2['servos']

    distance = 0.0
    distance += abs(s1.get('base', 0) - s2.get('base', 0))
    distance += abs(s1.get('shoulder', 0) - s2.get('shoulder', 0))
    distance += abs(s1.get('elbow', 0) - s2.get('elbow', 0))
    distance += abs(s1.get('wrist', 0) - s2.get('wrist', 0))
    distance += abs(s1.get('hand', 0) - s2.get('hand', 0))

    return distance


def calculate_duration(kf1: Dict, kf2: Dict, base_speed: float = 2.0) -> float:
    """
    Calculate realistic duration based on movement distance.

    Args:
        kf1: Starting keyframe
        kf2: Target keyframe
        base_speed: Base speed in radians/second (default: 2.0)

    Returns:
        Estimated duration in seconds
    """
    distance = calculate_movement_distance(kf1, kf2)

    # Calculate time based on distance and speed
    # Add a minimum duration of 0.3s for very small movements
    duration = max(0.3, distance / base_speed)

    # Round to 2 decimal places
    return round(duration, 2)


def suggest_hand_variations(keyframes: List[Dict]) -> List[float]:
    """
    Suggest hand/antenna variations based on keyframe positions.

    The hand position represents eyebrows/antenna and should vary
    to show emotion and expression.

    Range: 0.5 to 2.6 radians
    - Low (0.5-1.0): Droopy, sad, relaxed
    - Mid (1.0-1.8): Neutral, normal
    - High (1.8-2.6): Alert, excited, surprised
    """
    variations = []

    for i, kf in enumerate(keyframes):
        servos = kf['servos']

        # Analyze movement to suggest expression
        shoulder = servos.get('shoulder', 0)
        elbow = servos.get('elbow', 0)

        # Higher positions = more alert/excited
        # Lower positions = more relaxed/droopy

        if shoulder > -0.5:  # High position
            # Alert, excited - high eyebrows
            hand = 1.8 + (abs(shoulder) * 0.3)
        elif shoulder < -1.5:  # Low position
            # Relaxed, calm - mid eyebrows
            hand = 1.2 + (abs(shoulder) * 0.1)
        else:  # Mid position
            # Neutral
            hand = 1.5

        # Add some variation based on position in sequence
        if i % 3 == 0:
            hand += 0.1
        elif i % 3 == 1:
            hand -= 0.1

        # Clamp to valid range
        hand = max(0.5, min(2.6, hand))
        variations.append(round(hand, 2))

    return variations


def suggest_acceleration_variations(keyframes: List[Dict]) -> List[float]:
    """
    Suggest acceleration variations based on movement characteristics.

    Range: 10.0 to 22.5
    - Low (10.0-12.0): Smooth, gentle, flowing
    - Mid (12.0-16.0): Normal, natural
    - High (16.0-22.5): Snappy, quick, energetic
    """
    variations = []

    for i in range(len(keyframes)):
        # Calculate movement speed to next keyframe
        if i < len(keyframes) - 1:
            distance = calculate_movement_distance(keyframes[i], keyframes[i + 1])

            if distance > 1.5:  # Large movement
                # Use lower acceleration for smoothness
                acc = 10.0 + (distance * 0.5)
            elif distance > 0.5:  # Medium movement
                # Normal acceleration
                acc = 12.0 + (distance * 1.0)
            else:  # Small movement
                # Can use higher acceleration for snappiness
                acc = 14.0 + (distance * 2.0)
        else:
            # Last frame - use gentle acceleration
            acc = 11.0

        # Clamp to valid range
        acc = max(10.0, min(22.5, acc))
        variations.append(round(acc, 1))

    return variations


def json_to_python_plugin(
    json_data: Dict,
    class_name: str = None,
    auto_durations: bool = True,
    auto_hand: bool = True,
    auto_acceleration: bool = True
) -> str:
    """
    Convert JSON animation to Python animation plugin.

    Args:
        json_data: Loaded JSON animation data
        class_name: Optional custom class name
        auto_durations: Calculate durations based on movement (default: True)
        auto_hand: Auto-suggest hand/antenna variations (default: True)
        auto_acceleration: Auto-suggest acceleration variations (default: True)

    Returns:
        Generated Python code
    """
    # Extract metadata
    name = json_data.get('name', 'custom_animation')
    description = json_data.get('description', 'Custom animation')
    category = json_data.get('category', 'custom')
    keyframes_data = json_data.get('keyframes', [])

    if not keyframes_data:
        return ""

    # Generate class name if not provided
    if not class_name:
        class_name = to_class_name(name)

    # Calculate durations if requested
    if auto_durations:
        durations = []
        for i in range(len(keyframes_data)):
            if i < len(keyframes_data) - 1:
                duration = calculate_duration(keyframes_data[i], keyframes_data[i + 1])
            else:
                duration = 0.5  # Last frame hold time
            durations.append(duration)
    else:
        durations = [kf.get('duration', 0.5) for kf in keyframes_data]

    # Generate hand variations if requested
    if auto_hand:
        hand_variations = suggest_hand_variations(keyframes_data)
    else:
        hand_variations = [kf['servos'].get('hand', 1.5) for kf in keyframes_data]

    # Check if acceleration values are already customized (not all defaults)
    existing_acc_values = [kf['servos'].get('acc', 10.0) for kf in keyframes_data]
    has_custom_acceleration = any(acc != 10.0 for acc in existing_acc_values)

    # Generate acceleration variations if requested AND not already customized
    if auto_acceleration and not has_custom_acceleration:
        # Only auto-suggest if all values are at default (10.0)
        acc_variations = suggest_acceleration_variations(keyframes_data)
        print(f"  Auto-suggesting acceleration (all values were default 10.0)")
    elif has_custom_acceleration:
        # Preserve custom acceleration values
        acc_variations = existing_acc_values
        print(f"  Preserving custom acceleration values (range: {min(existing_acc_values):.1f}-{max(existing_acc_values):.1f})")
    else:
        # Use existing values from JSON
        acc_variations = existing_acc_values

    # Normalize base positions around 0.0 and add subtle variations
    base_positions = [kf['servos'].get('base', 0.0) for kf in keyframes_data]

    # Calculate offset to normalize to 0.0
    base_offset = base_positions[0]

    # Normalize all base positions relative to first position
    normalized_base = [b - base_offset for b in base_positions]

    # Check if variations are small enough to use base_pos variable
    max_variation = max(abs(b) for b in normalized_base)
    use_base_pos = max_variation <= 0.3  # Only use base_pos if variations are small

    # Add subtle lateral variations if base is mostly constant
    if use_base_pos and max_variation < 0.05:
        # Add expressive lateral movement (±0.3 max)
        for i in range(len(normalized_base)):
            if i % 3 == 0:
                normalized_base[i] += 0.05  # Slight right
            elif i % 3 == 1:
                normalized_base[i] -= 0.03  # Slight left
            elif i % 3 == 2:
                normalized_base[i] += 0.02  # Back to center-ish
            # Clamp to ±0.3
            normalized_base[i] = max(-0.3, min(0.3, normalized_base[i]))

    # Generate Python code
    code = f'''#!/usr/bin/env python3
"""
{description}

Generated from JSON by json_to_animation.py
Original file: {json_data.get('created', 'unknown')}
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class {class_name}(AnimationPlugin):
    """{description}"""

    @property
    def name(self) -> str:
        return "{name}"

    @property
    def description(self) -> str:
        return "{description}"

    def get_category(self) -> str:
        return "{category}"

    def get_keyframe_names(self) -> Optional[List[str]]:
        """Descriptive names for each keyframe."""
        return [
'''

    # Add keyframe names
    for i in range(len(keyframes_data)):
        code += f'            "Keyframe {i+1}",\n'

    code += '''        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        """
        Return keyframes and durations.

        Keyframe format: [base, shoulder, elbow, wrist, roll, acceleration, hand/antenna]
        - base: Base rotation (-90° to 90°)
        - shoulder: Shoulder joint (0° to 180°)
        - elbow: Elbow joint (0° to 180°)
        - wrist: Wrist joint (0° to 180°)
        - roll: Roll joint (-2.5 to -0.5)
        - acceleration: Movement speed (10.0 to 22.5)
        - hand/antenna: Eyebrow/antenna expression (0.5 to 2.6)
        """
'''

    # Add base_pos variable if using normalized base
    if use_base_pos:
        code += "        base_pos = 0.0\n        \n        keyframes = [\n"
    else:
        code += "        keyframes = [\n"

    # Add keyframes with proper formatting
    for i, kf in enumerate(keyframes_data):
        servos = kf['servos']
        shoulder = servos.get('shoulder', 0.0)
        elbow = servos.get('elbow', 0.0)
        wrist = servos.get('wrist', 0.0)
        roll = servos.get('roll', -1.5)
        acc = acc_variations[i]
        hand = hand_variations[i]

        # Use normalized base position
        if use_base_pos:
            base_val = normalized_base[i]
            if abs(base_val) < 0.01:
                # If very close to zero, just use base_pos
                code += f"            [base_pos, {shoulder:.2f}, {elbow:.2f}, {wrist:.2f}, {roll:.2f}, {acc:.1f}, {hand:.2f}],\n"
            else:
                # Add offset from base_pos
                sign = '+' if base_val >= 0 else ''
                code += f"            [base_pos {sign}{base_val:.2f}, {shoulder:.2f}, {elbow:.2f}, {wrist:.2f}, {roll:.2f}, {acc:.1f}, {hand:.2f}],\n"
        else:
            # Use absolute base value (for animations with large base variations)
            base = servos.get('base', 0.0)
            code += f"            [{base:.2f}, {shoulder:.2f}, {elbow:.2f}, {wrist:.2f}, {roll:.2f}, {acc:.1f}, {hand:.2f}],\n"

    code += "        ]\n\n        durations = ["
    code += ", ".join([f"{d:.2f}" for d in durations])
    code += "]\n\n        return keyframes, durations\n"

    return code


def main():
    parser = argparse.ArgumentParser(
        description='Convert JSON animation to Python plugin with hand/acceleration variations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview with auto-calculated durations and variations
  python3 json_to_animation.py animations/json/animation_hopping.json

  # Save to file
  python3 json_to_animation.py animations/json/animation_hopping.json -o hopping.py

  # Install to animation plugins directory
  python3 json_to_animation.py animations/json/animation_hopping.json --install

  # Disable auto-variations
  python3 json_to_animation.py animations/json/animation_hopping.json --no-auto-hand --no-auto-acc
        """
    )

    parser.add_argument(
        'json_file',
        help='Input JSON animation file'
    )

    parser.add_argument(
        '--output', '-o',
        help='Output Python file (prints to stdout if not specified)'
    )

    parser.add_argument(
        '--class-name', '-c',
        help='Custom class name (auto-generated if not specified)'
    )

    parser.add_argument(
        '--install', '-i',
        action='store_true',
        help='Install animation directly into LuxoPi animation_plugins directory'
    )

    parser.add_argument(
        '--no-auto-durations',
        action='store_true',
        help='Don\'t auto-calculate durations (use values from JSON)'
    )

    parser.add_argument(
        '--no-auto-hand',
        action='store_true',
        help='Don\'t auto-suggest hand/antenna variations'
    )

    parser.add_argument(
        '--no-auto-acc',
        action='store_true',
        help='Don\'t auto-suggest acceleration variations'
    )

    args = parser.parse_args()

    # Load JSON
    print(f"Loading {args.json_file}...")
    try:
        with open(args.json_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"✗ File not found: {args.json_file}")
        return 1
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON: {e}")
        return 1

    animation_name = data.get('name', 'custom_animation')
    print(f"✓ Loaded animation: {animation_name}")
    print(f"  Keyframes: {len(data.get('keyframes', []))}")
    print(f"  Category: {data.get('category', 'unknown')}")

    # Convert to Python
    print("\nConverting to Python plugin...")
    print(f"  Auto-calculate durations: {not args.no_auto_durations}")
    print(f"  Auto-suggest hand variations: {not args.no_auto_hand}")
    print(f"  Auto-suggest acceleration: {not args.no_auto_acc}")

    code = json_to_python_plugin(
        data,
        args.class_name,
        auto_durations=not args.no_auto_durations,
        auto_hand=not args.no_auto_hand,
        auto_acceleration=not args.no_auto_acc
    )

    if not code:
        print("✗ Conversion failed - no keyframes found")
        return 1

    class_name = args.class_name if args.class_name else to_class_name(animation_name)
    print("✓ Conversion successful")

    # Generate default output filename
    default_filename = f"animation_{animation_name.lower().replace(' ', '_')}.py"

    # Handle output
    if args.install:
        plugin_dir = Path('/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins')

        if not plugin_dir.exists():
            print(f"✗ Plugin directory not found: {plugin_dir}")
            return 1

        filepath = plugin_dir / default_filename

        if filepath.exists():
            print(f"⚠ File already exists: {filepath}")
            response = input("  Overwrite? (y/n): ").strip().lower()
            if response != 'y':
                print("✗ Installation cancelled")
                return 1

        with open(filepath, 'w') as f:
            f.write(code)

        print(f"✓ Animation installed to: {filepath}")
        print("\nNext steps:")
        print(f"1. Register in custom_animations.py:")
        print(f"   from .{default_filename[:-3]} import {class_name}")
        print(f"2. Rebuild: colcon build --packages-select luxo_behaviors")

    else:
        # Save to file (either specified or default)
        output_path = args.output if args.output else default_filename

        # Create animations/python directory if using default
        if not args.output:
            output_dir = Path('animations/python')
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / default_filename

        with open(output_path, 'w') as f:
            f.write(code)

        print(f"✓ Animation written to: {output_path}")
        print("\nTo install:")
        print(f"  python3 json_to_animation.py {args.json_file} --install")

    return 0


if __name__ == '__main__':
    exit(main())
