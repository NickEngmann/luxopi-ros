#!/usr/bin/env python3
"""Core logic for serial command building.

This module contains the pure logic components for building serial commands
without ROS2 dependencies, making it testable.
"""

import json
import math
from typing import Dict, Any


def build_serial_command(
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    hand: float = 0.0
) -> str:
    """Build a serial command with hand offset applied.
    
    Args:
        x: X position coordinate
        y: Y position coordinate  
        z: Z position coordinate
        hand: Hand angle value (will have pi offset added)
        
    Returns:
        JSON string representing the serial command
    """
    # Apply hand offset (add pi to hand value)
    hand_with_offset = hand + math.pi
    
    command = {
        "x": x,
        "y": y,
        "z": z,
        "hand": hand_with_offset
    }
    
    return json.dumps(command)


def parse_serial_command(command: str) -> Dict[str, float]:
    """Parse a serial command JSON string.
    
    Args:
        command: JSON string from serial command
        
    Returns:
        Dictionary with x, y, z, hand values
    """
    return json.loads(command)


def validate_command(command: Dict[str, Any]) -> bool:
    """Validate that a command has all required fields.
    
    Args:
        command: Dictionary containing command values
        
    Returns:
        True if command is valid, False otherwise
    """
    required_fields = ["x", "y", "z", "hand"]
    return all(field in command for field in required_fields)
