"""
Serial command builder for Luxo robotic arm control.

This module provides pure logic functions for building serial commands
to control the robotic arm, including configurable speed and acceleration.
"""

import json
from typing import Dict, List, Optional

# Constants
DEFAULT_SPEED = 0
DEFAULT_ACCELERATION = 0
HAND_OFFSET = 3.1415926  # π radians
MAX_JOINT_VALUE = 2047
MIN_JOINT_VALUE = 0


def calculate_position(rad_input: float, direc_input: float, multi_input: float) -> int:
    """
    Calculate joint position from radius input.
    
    Args:
        rad_input: Radius value in radians
        direc_input: Direction (1 or -1)
        multi_input: Multiplier factor
        
    Returns:
        Calculated position value (0-4095 range)
    """
    if rad_input == 0:
        return MAX_JOINT_VALUE
    else:
        get_pos = int(MAX_JOINT_VALUE + 
                      (direc_input * rad_input / 3.1415926 * 2048 * multi_input) + 0.5)
        return get_pos


def validate_joint_states(positions: List[float]) -> bool:
    """
    Validate that joint positions are within acceptable range.
    
    Args:
        positions: List of joint position values
        
    Returns:
        True if all positions are valid, False otherwise
    """
    if not positions or len(positions) != 4:
        return False
    
    for pos in positions:
        if not isinstance(pos, (int, float)):
            return False
        if pos < -3.1415926 * 2 or pos > 3.1415926 * 2:
            return False
    return True


def build_serial_command(
    base: float,
    shoulder: float,
    elbow: float,
    hand: float,
    speed: Optional[int] = None,
    acceleration: Optional[int] = None,
    hand_offset: float = HAND_OFFSET
) -> str:
    """
    Build a serial command JSON string for robotic arm control.
    
    Args:
        base: Base joint position in radians
        shoulder: Shoulder joint position in radians
        elbow: Elbow joint position in radians
        hand: Hand joint position in radians
        speed: Motion speed (default: DEFAULT_SPEED)
        acceleration: Motion acceleration (default: DEFAULT_ACCELERATION)
        hand_offset: Offset to apply to hand joint (default: π)
        
    Returns:
        JSON string with command data, ending with newline
    """
    if speed is None:
        speed = DEFAULT_SPEED
    if acceleration is None:
        acceleration = DEFAULT_ACCELERATION
    
    data_dict: Dict[str, float] = {
        'T': 102,
        'base': float(base),
        'shoulder': float(shoulder),
        'elbow': float(elbow),
        'hand': float(hand) + hand_offset,
        'spd': int(speed),
        'acc': int(acceleration)
    }
    
    return json.dumps(data_dict) + "\n"


def build_serial_command_from_positions(
    positions: List[float],
    speed: Optional[int] = None,
    acceleration: Optional[int] = None,
    hand_offset: float = HAND_OFFSET
) -> str:
    """
    Build a serial command from a list of joint positions.
    
    Args:
        positions: List of [base, shoulder, elbow, hand] positions in radians
        speed: Motion speed (default: DEFAULT_SPEED)
        acceleration: Motion acceleration (default: DEFAULT_ACCELERATION)
        hand_offset: Offset to apply to hand joint (default: π)
        
    Returns:
        JSON string with command data, ending with newline
        
    Raises:
        ValueError: If positions list is invalid
    """
    if not validate_joint_states(positions):
        raise ValueError("Invalid joint positions: must be list of 4 numeric values")
    
    return build_serial_command(
        base=positions[0],
        shoulder=positions[1],
        elbow=positions[2],
        hand=positions[3],
        speed=speed,
        acceleration=acceleration,
        hand_offset=hand_offset
    )


def parse_serial_command(command: str) -> Dict:
    """
    Parse a serial command string into a dictionary.
    
    Args:
        command: JSON string ending with newline
        
    Returns:
        Dictionary containing parsed command data
        
    Raises:
        ValueError: If command is malformed
    """
    if not command.endswith('\n'):
        raise ValueError("Command must end with newline")
    
    try:
        return json.loads(command.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed command: {e}")


def create_motion_profile(
    start_positions: List[float],
    end_positions: List[float],
    steps: int = 10,
    speed: int = 50,
    acceleration: int = 25
) -> List[str]:
    """
    Create a motion profile with intermediate positions.
    
    Args:
        start_positions: Starting [base, shoulder, elbow, hand] positions
        end_positions: Ending [base, shoulder, elbow, hand] positions
        steps: Number of intermediate steps (default: 10)
        speed: Motion speed (default: 50)
        acceleration: Motion acceleration (default: 25)
        
    Returns:
        List of serial command strings for each step
        
    Raises:
        ValueError: If position lists are invalid
    """
    if not validate_joint_states(start_positions) or not validate_joint_states(end_positions):
        raise ValueError("Invalid start or end positions")
    
    if steps < 1:
        raise ValueError("Steps must be at least 1")
    
    commands = []
    for i in range(steps + 1):
        progress = i / steps
        current_positions = [
            start_positions[j] + (end_positions[j] - start_positions[j]) * progress
            for j in range(4)
        ]
        commands.append(build_serial_command_from_positions(
            current_positions,
            speed=speed,
            acceleration=acceleration
        ))
    
    return commands
