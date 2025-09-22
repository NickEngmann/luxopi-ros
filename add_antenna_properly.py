#!/usr/bin/env python3
"""
Add antenna values as 7th element to animation keyframes while preserving formatting.
"""

import re
import os

def add_antenna_to_keyframe(line):
    """Add or update antenna value in a single keyframe line."""
    # Match lines that look like keyframes: [values], # comment
    match = re.match(r'^(\s+\[)(.*?)(\],?\s*)(#.*)?$', line)

    if not match:
        return line

    indent = match.group(1)
    values = match.group(2)
    closing = match.group(3)
    comment = match.group(4) if match.group(4) else ''

    # Split values and count them
    value_list = [v.strip() for v in values.split(',')]
    value_count = len(value_list)

    # Generate antenna value based on comment
    antenna_val = get_antenna_value(comment)

    # If it has 6 values, add antenna as 7th
    if value_count == 6:
        new_line = f"{indent}{values}, {antenna_val:.2f}{closing}{comment}\n"
        return new_line
    # If it has 7 values, update the antenna (7th value)
    elif value_count == 7:
        # Replace the last value with new antenna value
        value_list[-1] = f"{antenna_val:.2f}"
        new_values = ', '.join(value_list)
        new_line = f"{indent}{new_values}{closing}{comment}\n"
        return new_line

    return line

def get_antenna_value(comment):
    """Generate antenna value based on animation context in comment.
    Uses range 0.5 to 2.6 radians for realistic movement."""
    comment_lower = comment.lower() if comment else ''

    # Keywords for antenna movements using realistic range (0.5 to 2.6)
    if 'home' in comment_lower or 'start' in comment_lower:
        return 1.5  # Neutral home position (mid-range)
    elif 'alert' in comment_lower or 'attention' in comment_lower or 'listen' in comment_lower:
        return 2.3  # Alert and attentive (raised)
    elif 'curious' in comment_lower or 'question' in comment_lower or 'explore' in comment_lower:
        return 2.0  # Moderately raised for curiosity
    elif 'excited' in comment_lower or 'happy' in comment_lower or 'joy' in comment_lower or 'peak' in comment_lower:
        return 2.6  # Maximum for excitement
    elif 'sad' in comment_lower or 'droop' in comment_lower or 'depress' in comment_lower:
        return 0.5  # Minimum realistic position for sadness
    elif 'think' in comment_lower or 'ponder' in comment_lower:
        return 1.8  # Thoughtful mid-position
    elif 'relax' in comment_lower or 'rest' in comment_lower or 'settle' in comment_lower:
        return 0.9  # Relaxed low position
    elif 'sleep' in comment_lower or 'tired' in comment_lower:
        return 0.6  # Very low for sleep
    elif 'left' in comment_lower:
        return 1.4  # Mid-left tilt
    elif 'right' in comment_lower:
        return 1.6  # Mid-right tilt
    elif 'up' in comment_lower or 'rise' in comment_lower or 'launch' in comment_lower:
        return 2.4  # Raised up high
    elif 'down' in comment_lower or 'compress' in comment_lower or 'low' in comment_lower:
        return 0.7  # Low position
    elif 'wiggle' in comment_lower or 'bounce' in comment_lower:
        return 2.1  # Energetic mid-high
    elif 'shake' in comment_lower:
        return 1.3  # Mid shake position
    elif 'surprise' in comment_lower or 'startle' in comment_lower:
        return 2.5  # Near maximum for surprise
    elif 'victory' in comment_lower or 'proud' in comment_lower:
        return 2.5  # Very high for pride
    elif 'fear' in comment_lower or 'scared' in comment_lower:
        return 0.6  # Very low for fear
    elif 'angry' in comment_lower or 'mad' in comment_lower:
        return 2.2  # Raised in anger
    elif 'playful' in comment_lower or 'play' in comment_lower:
        return 2.0  # Playful mid-high
    else:
        # Default neutral-raised position
        return 1.5

def process_file(filepath):
    """Process a file to add antenna values."""
    with open(filepath, 'r') as f:
        lines = f.readlines()

    modified = False
    new_lines = []
    in_keyframes = False

    for i, line in enumerate(lines):
        # Check if we're entering a keyframes section
        if 'keyframes = [' in line:
            in_keyframes = True
            new_lines.append(line)
        # Check if we're leaving a keyframes section
        elif in_keyframes and line.strip() == ']':
            in_keyframes = False
            new_lines.append(line)
        # Process keyframe lines
        elif in_keyframes and '[' in line and ']' in line:
            new_line = add_antenna_to_keyframe(line)
            if new_line != line:
                modified = True
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    if modified:
        with open(filepath, 'w') as f:
            f.writelines(new_lines)
        print(f"Updated {filepath}")
        return True

    print(f"No changes needed in {filepath}")
    return False

def main():
    """Process all animation files."""
    files = [
        '/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins/idle_animations.py',
        '/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins/action_animations.py',
        '/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins/emotion_animations.py',
        '/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins/response_animations.py',
        '/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins/petting_animations.py'
    ]

    for filepath in files:
        if os.path.exists(filepath):
            process_file(filepath)

if __name__ == '__main__':
    main()