#!/usr/bin/env python3
"""
Utility functions for serial_ctrl_py.py.

These functions contain the pure logic that can be tested without ROS2 dependencies.
"""

import json


def pos_get(rad_input: float, direc_input: int, multi_input: float) -> int:
    """
    Calculate position value from radius input.
    
    Args:
        rad_input: Radius input value in radians
        direc_input: Direction input (1 or -1)
        multi_input: Multiplier input
    
    Returns:
        Integer position value
    """
    if rad_input == 0:
        return 2047
    else:
        get_pos = int(2047 + (direc_input * rad_input / 3.1415926 * 2048 * multi_input) + 0.5)
        return get_pos


def build_serial_command(base: float, shoulder: float, elbow: float, hand: float) -> str:
    """
    Build a serial command JSON string from joint positions.
    
    Args:
        base: Base joint position
        shoulder: Shoulder joint position
        elbow: Elbow joint position
        hand: Hand joint position
    
    Returns:
        JSON string command for serial device
    """
    data = {
        'T': 102,
        'base': base,
        'shoulder': shoulder,
        'elbow': elbow,
        'hand': hand + 3.1415926,
        'spd': 0,
        'acc': 0
    }
    return json.dumps(data) + "\n"
