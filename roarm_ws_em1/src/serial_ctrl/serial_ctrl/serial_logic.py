"""
Pure logic functions for serial control.

These functions are extracted from the ROS2 node to enable unit testing
without requiring ROS2, serial hardware, or external dependencies.
"""

import math


def posGet(radInput, direcInput, multiInput):
    """
    Calculate position value based on radius, direction, and multiplier.
    
    Args:
        radInput: Radius input in radians
        direcInput: Direction (-1 or 1)
        multiInput: Multiplier value
        
    Returns:
        int: Position value (2047 when radInput is 0, otherwise calculated)
    """
    if radInput == 0:
        return 2047
    else:
        getPos = int(2047 + (direcInput * radInput / math.pi * 2048 * multiInput) + 0.5)
        return getPos


def build_serial_command(base, shoulder, elbow, hand):
    """
    Build a JSON serial command for the robot arm.
    
    Args:
        base: Base joint angle
        shoulder: Shoulder joint angle
        elbow: Elbow joint angle
        hand: Hand joint angle (will have offset applied)
        
    Returns:
        str: JSON formatted command string with newline
    """
    # hand offset: +π (as in original code)
    data_dict = {
        'T': 102,
        'base': base,
        'shoulder': shoulder,
        'elbow': elbow,
        'hand': hand + math.pi,
        'spd': 0,
        'acc': 0
    }
    return json.dumps(data_dict) + "\n"
