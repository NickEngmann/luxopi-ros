#!/usr/bin/env python3
"""
Convert Python animation plugins to JSON format.

This script takes Python animation classes and converts them to the JSON format
used by the animation recorder system.

Usage:
    python3 animation_to_json.py StretchingAnimation
    python3 animation_to_json.py --file /path/to/animation.py DancingAnimation
    python3 animation_to_json.py --all-commented  # Convert all commented animations
"""

import json
import argparse
import re
import importlib.util
import inspect
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def find_animation_files() -> List[Path]:
    """Find all animation plugin files."""
    plugin_dir = Path('/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins')
    return list(plugin_dir.glob('*_animations.py'))


def extract_commented_animation_code(file_path: Path, class_name: str) -> Optional[str]:
    """Extract commented-out animation class code from a file."""
    with open(file_path, 'r') as f:
        lines = f.readlines()

    # Find the start of the commented class
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f'# class {class_name}(AnimationPlugin):'):
            start_idx = i
            break

    if start_idx is None:
        return None

    # Find the end of the commented class (next uncommented line or next class)
    end_idx = len(lines)
    blank_line_count = 0
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]

        # Stop at next class (commented or uncommented)
        if line.strip().startswith('# class ') or line.strip().startswith('class '):
            end_idx = i
            break

        # Stop at end of commented section (uncommented non-blank line)
        if line.strip() and not line.strip().startswith('#'):
            end_idx = i
            break

        # Track blank lines - if we hit 2+ consecutive blank/empty comment lines, we're past the class
        if not line.strip() or line.strip() == '#':
            blank_line_count += 1
            if blank_line_count >= 2:
                end_idx = i - 1  # Go back before the blank lines
                break
        else:
            blank_line_count = 0

    # Extract and uncomment the lines
    uncommented_lines = []
    for line in lines[start_idx:end_idx]:
        # Remove leading '# ' or '#'
        if line.startswith('# '):
            uncommented_lines.append(line[2:])
        elif line.startswith('#'):
            uncommented_lines.append(line[1:])
        else:
            uncommented_lines.append(line)

    return ''.join(uncommented_lines)


def load_animation_class_from_code(code: str, class_name: str) -> Any:
    """Load an animation class from Python code string."""
    # Create a temporary module
    import types
    module = types.ModuleType('temp_animation')

    # Add required imports to the code
    full_code = """
from typing import List, Tuple, Optional
import random

class AnimationPlugin:
    pass

""" + code

    try:
        exec(full_code, module.__dict__)
        return getattr(module, class_name)
    except Exception as e:
        print(f"Error loading animation class: {e}")
        return None


def evaluate_base_expression(expr_str: str, base_pos: float = 0.0) -> float:
    """
    Evaluate base position expressions like 'base_pos +0.05' or 'base_pos -0.03'.

    Args:
        expr_str: String expression from keyframe list
        base_pos: Value of base_pos variable (default 0.0)

    Returns:
        Evaluated float value
    """
    # Handle simple floats
    try:
        return float(expr_str)
    except (ValueError, TypeError):
        pass

    # Handle expressions with base_pos
    if isinstance(expr_str, str):
        # Replace 'base_pos' with actual value
        expr_str = expr_str.replace('base_pos', str(base_pos))
        # Remove extra spaces around operators
        expr_str = re.sub(r'\s*([+\-])\s*', r'\1', expr_str)
        try:
            return eval(expr_str)
        except:
            return 0.0

    return float(expr_str)


def animation_to_json(animation_class: Any, node: Any = None, category: str = None) -> Dict[str, Any]:
    """
    Convert an animation class to JSON format.

    Args:
        animation_class: AnimationPlugin class (not instance)
        node: Optional ROS node (required for AnimationPlugin classes)
        category: Optional category override

    Returns:
        Dictionary in JSON animation format
    """
    # Create instance (with node if needed)
    if node is not None:
        instance = animation_class(node)
    else:
        # Try without node first (for legacy support)
        try:
            instance = animation_class()
        except TypeError:
            # Need a node, create a mock one
            class MockLogger:
                def info(self, msg): pass
                def error(self, msg): pass
                def warn(self, msg): pass
                def debug(self, msg): pass

            class MockNode:
                def get_logger(self):
                    return MockLogger()

            instance = animation_class(MockNode())

    # Get animation data
    name = instance.name
    description = instance.description
    if category is None:
        category = instance.get_category() if hasattr(instance, 'get_category') else 'custom'

    # Get keyframes and durations
    keyframes_data, durations = instance.get_keyframes()

    # Get keyframe names if available
    keyframe_names = None
    if hasattr(instance, 'get_keyframe_names'):
        keyframe_names = instance.get_keyframe_names()

    # Convert keyframes to JSON format
    json_keyframes = []

    for i, (keyframe, duration) in enumerate(zip(keyframes_data, durations)):
        # Keyframe format: [base, shoulder, elbow, wrist, roll, acceleration, hand/antenna]
        # Need to handle base_pos expressions
        base_val = keyframe[0]
        if not isinstance(base_val, (int, float)):
            # It's an expression, evaluate it with base_pos = 0.0
            base_val = evaluate_base_expression(str(base_val), 0.0)

        keyframe_dict = {
            "servos": {
                "base": float(base_val),
                "shoulder": float(keyframe[1]),
                "elbow": float(keyframe[2]),
                "wrist": float(keyframe[3]),
                "hand": float(keyframe[6]),  # hand/antenna is at index 6
                "roll": float(keyframe[4]),
                "spd": 0,
                "acc": float(keyframe[5])
            },
            "timing": 1.0,
            "duration": float(duration)
        }

        json_keyframes.append(keyframe_dict)

    # Build final JSON structure
    json_data = {
        "name": name,
        "description": description,
        "category": category,
        "created": datetime.now().isoformat(),
        "keyframes": json_keyframes,
        "keyframe_count": len(json_keyframes)
    }

    # Add keyframe names if available
    if keyframe_names:
        for i, kf_name in enumerate(keyframe_names):
            if i < len(json_keyframes):
                json_keyframes[i]["name"] = kf_name

    return json_data


def save_json(json_data: Dict[str, Any], output_dir: Path = None) -> Path:
    """Save JSON data to file."""
    if output_dir is None:
        output_dir = Path('/home/pi/luxopi-ros/dev/animations/json')

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    name = json_data['name']
    filename = f"animation_{name}.json"
    filepath = output_dir / filename

    # Write JSON
    with open(filepath, 'w') as f:
        json.dump(json_data, f, indent=2)

    return filepath


def find_commented_animations() -> List[tuple]:
    """Find all commented-out animation classes."""
    animations = []

    for file_path in find_animation_files():
        with open(file_path, 'r') as f:
            content = f.read()

        # Find commented class definitions
        pattern = r'^# class (\w+Animation)\(AnimationPlugin\):'
        matches = re.finditer(pattern, content, re.MULTILINE)

        for match in matches:
            class_name = match.group(1)
            animations.append((file_path, class_name))

    return animations


def load_active_animation_class(file_path: Path, class_name: str) -> Optional[type]:
    """Load an active (uncommented) animation class from a file."""
    import importlib.util
    import inspect

    try:
        # Load the module
        spec = importlib.util.spec_from_file_location("temp_module", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the class
        if hasattr(module, class_name):
            animation_class = getattr(module, class_name)
            # Verify it's an animation class
            if inspect.isclass(animation_class) and hasattr(animation_class, 'get_keyframes'):
                return animation_class
    except Exception as e:
        # Failed to load as active class
        pass

    return None


def convert_animation(file_path: Path, class_name: str, output_dir: Path = None) -> Optional[Path]:
    """Convert an animation (commented or active) to JSON."""
    print(f"Converting {class_name} from {file_path.name}...")

    animation_class = None

    # Try loading as active class first
    animation_class = load_active_animation_class(file_path, class_name)
    if animation_class:
        print(f"  Found active class {class_name}")
    else:
        # Try extracting as commented code
        code = extract_commented_animation_code(file_path, class_name)
        if code:
            print(f"  Found commented class {class_name}")
            animation_class = load_animation_class_from_code(code, class_name)

    if not animation_class:
        print(f"  ✗ Could not find or load class {class_name}")
        return None

    # Convert to JSON (animation_to_json will create mock node if needed)
    try:
        json_data = animation_to_json(animation_class)
    except Exception as e:
        print(f"  ✗ Error converting {class_name}: {e}")
        import traceback
        traceback.print_exc()
        return None

    # Save JSON
    filepath = save_json(json_data, output_dir)
    print(f"  ✓ Saved to: {filepath}")
    print(f"    Name: {json_data['name']}")
    print(f"    Category: {json_data['category']}")
    print(f"    Keyframes: {json_data['keyframe_count']}")
    print()

    return filepath


# Alias for backward compatibility
def convert_commented_animation(file_path: Path, class_name: str, output_dir: Path = None) -> Optional[Path]:
    """Convert a commented animation to JSON (deprecated - use convert_animation)."""
    return convert_animation(file_path, class_name, output_dir)


def main():
    parser = argparse.ArgumentParser(
        description='Convert Python animation classes (active or commented) to JSON format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert a specific animation (active or commented)
  python3 animation_to_json.py StartledJumpAnimation

  # Convert all commented animations
  python3 animation_to_json.py --all-commented

  # Convert from specific file (works with both active and commented classes)
  python3 animation_to_json.py --file emotion_animations.py StartledJumpAnimation

  # Specify output directory
  python3 animation_to_json.py --output /path/to/output StartledJumpAnimation
        """
    )

    parser.add_argument(
        'class_name',
        nargs='?',
        help='Animation class name to convert (e.g., StretchingAnimation)'
    )

    parser.add_argument(
        '--file', '-f',
        help='Specific animation file to search (default: search all)'
    )

    parser.add_argument(
        '--all-commented', '-a',
        action='store_true',
        help='Convert all commented-out animations'
    )

    parser.add_argument(
        '--output', '-o',
        help='Output directory (default: animations/json/)'
    )

    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else None

    if args.all_commented:
        print("Finding all commented animations...\n")
        animations = find_commented_animations()

        if not animations:
            print("No commented animations found.")
            return 0

        print(f"Found {len(animations)} commented animation(s):\n")
        for file_path, class_name in animations:
            print(f"  - {class_name} in {file_path.name}")
        print()

        # Convert all
        successful = 0
        for file_path, class_name in animations:
            if convert_commented_animation(file_path, class_name, output_dir):
                successful += 1

        print(f"✓ Converted {successful}/{len(animations)} animations")
        return 0

    elif args.class_name:
        # Convert specific animation
        if args.file:
            # Search specific file
            file_path = Path(args.file)
            if not file_path.is_absolute():
                file_path = Path('/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins') / file_path

            if not file_path.exists():
                print(f"✗ File not found: {file_path}")
                return 1

            result = convert_animation(file_path, args.class_name, output_dir)
        else:
            # Search all files (try both active and commented)
            found = False
            result = None
            for file_path in find_animation_files():
                # Try loading as active class first
                if load_active_animation_class(file_path, args.class_name):
                    result = convert_animation(file_path, args.class_name, output_dir)
                    found = True
                    break
                # Try extracting as commented code
                elif extract_commented_animation_code(file_path, args.class_name):
                    result = convert_animation(file_path, args.class_name, output_dir)
                    found = True
                    break

            if not found:
                print(f"✗ Animation class '{args.class_name}' not found in any animation files")
                print("  (Searched for both active and commented classes)")
                return 1

        return 0 if result else 1

    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    exit(main())
