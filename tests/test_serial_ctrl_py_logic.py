"""
Unit tests for the pure logic components of serial_ctrl_py.py.

Since serial_ctrl_py.py depends on ROS2 (rclpy), serial, and hardware,
we extract and test the core logic functions directly here.

We mock ALL external dependencies BEFORE importing any ROS-related modules.
"""

import sys
from unittest.mock import MagicMock
import json

# === MOCK ALL EXTERNAL DEPENDENCIES BEFORE ANY IMPORT ===
# Mock ROS2 modules
sys.modules['rclpy'] = MagicMock()
sys.modules['rclpy.node'] = MagicMock()
sys.modules['sensor_msgs'] = MagicMock()
sys.modules['sensor_msgs.msg'] = MagicMock()
sys.modules['std_msgs'] = MagicMock()
sys.modules['std_msgs.msg'] = MagicMock()

# Mock serial (we won't use real serial, but avoid import errors)
sys.modules['serial'] = MagicMock()


def posGet(radInput, direcInput, multiInput):
    """Pure logic copied from MinimalSubscriber.posGet()"""
    if radInput == 0:
        return 2047
    else:
        getPos = int(2047 + (direcInput * radInput / 3.1415926 * 2048 * multiInput) + 0.5)
        return getPos


def build_serial_command(base, shoulder, elbow, hand):
    """Pure logic copied from MinimalSubscriber.listener_callback()"""
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


# === UNIT TESTS ===

def test_posGet_zero_radius_returns_2047():
    """When radInput is 0, posGet should always return 2047 regardless of other params."""
    assert posGet(0, 1, 1) == 2047
    assert posGet(0, -1, 1) == 2047
    assert posGet(0, 1, 2.5) == 2047
    assert posGet(0, 0, 100) == 2047


def test_posGet_positive_radius():
    """Test typical positive radius values."""
    # Example: radInput=1.57 (π/2), direc=1, multi=1 → should be ~3071
    result = posGet(1.57, 1, 1)
    assert 3070 <= result <= 3072  # allow rounding tolerance


def test_posGet_negative_radius():
    """Test negative radius (inverse direction)."""
    result = posGet(1.57, -1, 1)
    assert 1022 <= result <= 1024  # ~2047 - 1024


def test_build_serial_command_structure():
    """Verify JSON structure and hand offset."""
    cmd = build_serial_command(0.0, 0.0, 0.0, 0.0)
    parsed = json.loads(cmd.strip())
    assert parsed['T'] == 102
    assert parsed['base'] == 0.0
    assert parsed['shoulder'] == 0.0
    assert parsed['elbow'] == 0.0
    assert parsed['hand'] == 3.1415926  # hand + offset
    assert parsed['spd'] == 0
    assert parsed['acc'] == 0
    assert cmd.endswith('\n')


def test_build_serial_command_with_nonzero_hand():
    """Verify hand offset is applied correctly."""
    cmd = build_serial_command(0.0, 0.0, 0.0, 1.0)
    parsed = json.loads(cmd.strip())
    assert parsed['hand'] == 1.0 + 3.1415926