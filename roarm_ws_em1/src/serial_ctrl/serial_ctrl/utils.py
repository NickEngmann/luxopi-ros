"""
Pure logic utilities for serial_ctrl.

This module contains the core logic functions extracted from MinimalSubscriber
to make them testable without ROS2 dependencies.
"""

import json


def posGet(radInput, direcInput, multiInput):
    """
    Convert joint angle in radians to position value for serial communication.
    
    Args:
        radInput: Joint angle in radians
        direcInput: Direction multiplier (typically 1 or -1)
        multiInput: Multiplier for scaling
    
    Returns:
        Integer position value (0-4095 range)
    """
    if radInput == 0:
        return 2047
    else:
        getPos = int(2047 + (direcInput * radInput / 3.1415926 * 2048 * multiInput) + 0.5)
        return getPos


def posToRad(posValue, direcInput, multiInput):
    """
    Convert position value back to radians (inverse of posGet).
    
    Args:
        posValue: Position value from serial device
        direcInput: Direction multiplier
        multiInput: Multiplier for scaling
    
    Returns:
        Angle in radians
    """
    if posValue == 2047:
        return 0.0
    
    # Inverse of: getPos = 2047 + (direcInput * radInput / 3.1415926 * 2048 * multiInput)
    offset = posValue - 2047
    radInput = (offset * 3.1415926) / (direcInput * 2048 * multiInput)
    return radInput


def build_serial_command(base, shoulder, elbow, hand):
    """
    Build JSON command for serial communication.
    
    Args:
        base: Base joint angle in radians
        shoulder: Shoulder joint angle in radians
        elbow: Elbow joint angle in radians
        hand: Hand joint angle in radians
    
    Returns:
        JSON string with newline terminator
    """
    # hand offset: +3.1415926 (as in original code)
    data_dict = {
        'T': 102,
        'base': base,
        'shoulder': shoulder,
        'elbow': elbow,
        'hand': hand + 3.1415926,
        'spd': 0,
        'acc': 0
    }
    return json.dumps(data_dict) + "\n"


def parse_serial_command(command_str):
    """
    Parse JSON command from serial device.
    
    Args:
        command_str: JSON string received from serial device
    
    Returns:
        Dictionary with parsed values
    """
    # Remove newline if present
    clean_str = command_str.strip()
    return json.loads(clean_str)


def validate_joint_angle(angle_rad):
    """
    Validate that a joint angle is within reasonable range.
    
    Args:
        angle_rad: Joint angle in radians
    
    Returns:
        Tuple of (is_valid, message)
    """
    # Reasonable range: -pi to pi for most joints
    if angle_rad < -3.1415926 or angle_rad > 3.1415926:
        return False, f"Angle {angle_rad} out of range [-pi, pi]"
    return True, "Valid angle"


def validate_serial_command(command_dict):
    """
    Validate a serial command dictionary.
    
    Args:
        command_dict: Dictionary from parse_serial_command
    
    Returns:
        Tuple of (is_valid, message)
    """
    required_keys = ['T', 'base', 'shoulder', 'elbow', 'hand', 'spd', 'acc']
    for key in required_keys:
        if key not in command_dict:
            return False, f"Missing required key: {key}"
    
    if command_dict['T'] != 102:
        return False, f"Invalid command type: {command_dict['T']}"
    
    return True, "Valid command"
