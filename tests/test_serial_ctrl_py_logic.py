"""
Unit tests for the pure logic components of serial_ctrl_py.py.

Since serial_ctrl_py.py depends on ROS2 (rclpy), serial, and hardware,
we extract and test the core logic functions directly here.

We mock ALL external dependencies BEFORE importing any ROS-related modules.
"""

import sys
from unittest.mock import MagicMock
import json
import math

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


# === PURE LOGIC FUNCTIONS ===

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

class TestPosGet:
    """Tests for the posGet function."""
    
    def test_posGet_zero_radius_returns_2047(self):
        """When radInput is 0, posGet should always return 2047 regardless of other params."""
        assert posGet(0, 1, 1) == 2047
        assert posGet(0, -1, 1) == 2047
        assert posGet(0, 1, 2.5) == 2047
        assert posGet(0, 0, 100) == 2047
        assert posGet(0, -100, 0.5) == 2047
    
    def test_posGet_positive_radius(self):
        """Test typical positive radius values."""
        # Example: radInput=1.57 (π/2), direc=1, multi=1 → should be ~3071
        result = posGet(1.57, 1, 1)
        assert 3070 <= result <= 3072  # allow rounding tolerance
    
    def test_posGet_negative_radius(self):
        """Test negative radius (inverse direction)."""
        result = posGet(1.57, -1, 1)
        assert 1022 <= result <= 1024  # ~2047 - 1024
    
    def test_posGet_full_positive_range(self):
        """Test with full positive radius (π radians)."""
        result = posGet(3.1415926, 1, 1)
        # Should be approximately 2047 + 2048 = 4095
        assert 4093 <= result <= 4097
    
    def test_posGet_full_negative_range(self):
        """Test with full negative radius (-π radians)."""
        result = posGet(-3.1415926, 1, 1)
        # Should be approximately 2047 - 2048 = -1
        assert -5 <= result <= 5
    
    def test_posGet_with_multiplier(self):
        """Test posGet with different multipliers."""
        # With multi=2, should be roughly double the offset
        result = posGet(1.57, 1, 2)
        assert 4090 <= result <= 4095
    
    def test_posGet_small_positive_value(self):
        """Test with very small positive radius."""
        result = posGet(0.01, 1, 1)
        # Should be slightly above 2047 (0.01 rad * 2048/π ≈ 6.5)
        assert 2053 <= result <= 2056
    
    def test_posGet_small_negative_value(self):
        """Test with very small negative radius."""
        result = posGet(-0.01, 1, 1)
        # Should be slightly below 2047
        assert 2040 <= result <= 2047
    
    def test_posGet_extreme_multiplier(self):
        """Test with large multiplier value."""
        result = posGet(1.57, 1, 10)
        # Should be significantly larger
        assert 12000 <= result <= 13000
    
    def test_posGet_negative_direction(self):
        """Test with negative direction input."""
        result = posGet(1.57, -1, 1)
        # Should be below 2047
        assert 1000 <= result <= 1050
    
    def test_posGet_boundary_conditions(self):
        """Test boundary conditions for posGet."""
        # Test with very small non-zero value
        result1 = posGet(0.0001, 1, 1)
        assert 2047 <= result1 <= 2048
        
        # Test with very large value
        result2 = posGet(10.0, 1, 1)
        assert 8000 <= result2 <= 9000


class TestBuildSerialCommand:
    """Tests for the build_serial_command function."""
    
    def test_build_serial_command_structure(self):
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
    
    def test_build_serial_command_with_nonzero_hand(self):
        """Verify hand offset is applied correctly."""
        cmd = build_serial_command(0.0, 0.0, 0.0, 1.0)
        parsed = json.loads(cmd.strip())
        assert parsed['hand'] == 1.0 + 3.1415926
    
    def test_build_serial_command_all_axes(self):
        """Test command with all axes having values."""
        cmd = build_serial_command(1.0, 2.0, 3.0, 4.0)
        parsed = json.loads(cmd.strip())
        assert parsed['base'] == 1.0
        assert parsed['shoulder'] == 2.0
        assert parsed['elbow'] == 3.0
        assert parsed['hand'] == 4.0 + 3.1415926
    
    def test_build_serial_command_negative_values(self):
        """Test command with negative values."""
        cmd = build_serial_command(-1.0, -2.0, -3.0, -4.0)
        parsed = json.loads(cmd.strip())
        assert parsed['base'] == -1.0
        assert parsed['shoulder'] == -2.0
        assert parsed['elbow'] == -3.0
        assert parsed['hand'] == -4.0 + 3.1415926
    
    def test_build_serial_command_zero_values(self):
        """Test command with all zero values."""
        cmd = build_serial_command(0, 0, 0, 0)
        parsed = json.loads(cmd.strip())
        assert parsed['base'] == 0
        assert parsed['shoulder'] == 0
        assert parsed['elbow'] == 0
        assert parsed['hand'] == 3.1415926
    
    def test_build_serial_command_float_precision(self):
        """Test command with floating point precision."""
        cmd = build_serial_command(0.123456789, 0.987654321, 0.555555555, 0.333333333)
        parsed = json.loads(cmd.strip())
        assert abs(parsed['base'] - 0.123456789) < 1e-6
        assert abs(parsed['shoulder'] - 0.987654321) < 1e-6
        assert abs(parsed['elbow'] - 0.555555555) < 1e-6
        assert abs(parsed['hand'] - (0.333333333 + 3.1415926)) < 1e-6
    
    def test_build_serial_command_json_validity(self):
        """Test that the output is valid JSON."""
        cmd = build_serial_command(1.0, 2.0, 3.0, 4.0)
        # Should not raise an exception
        parsed = json.loads(cmd.strip())
        assert isinstance(parsed, dict)
        assert 'T' in parsed
        assert 'base' in parsed
        assert 'shoulder' in parsed
        assert 'elbow' in parsed
        assert 'hand' in parsed
        assert 'spd' in parsed
        assert 'acc' in parsed
    
    def test_build_serial_command_newline_termination(self):
        """Test that command ends with newline."""
        cmd = build_serial_command(1.0, 2.0, 3.0, 4.0)
        assert cmd.endswith('\n')
        assert not cmd.endswith('\n\n')  # Should only have one newline
    
    def test_build_serial_command_constant_fields(self):
        """Test that constant fields are always correct."""
        for _ in range(5):
            cmd = build_serial_command(1.0, 2.0, 3.0, 4.0)
            parsed = json.loads(cmd.strip())
            assert parsed['T'] == 102
            assert parsed['spd'] == 0
            assert parsed['acc'] == 0


class TestIntegration:
    """Integration tests combining posGet and build_serial_command."""
    
    def test_posGet_to_serial_command_flow(self):
        """Test the flow from posGet calculation to serial command."""
        # Simulate a typical robot position
        base_rad = 1.57
        shoulder_rad = 0.785
        elbow_rad = -0.785
        hand_rad = 3.1415926
        
        # Calculate positions using posGet
        base_pos = posGet(base_rad, 1, 1)
        shoulder_pos = posGet(shoulder_rad, 1, 1)
        elbow_pos = posGet(elbow_rad, 1, 1)
        hand_pos = posGet(hand_rad, 1, 1)
        
        # Build serial command (note: hand offset is applied in build_serial_command)
        cmd = build_serial_command(base_pos, shoulder_pos, elbow_pos, hand_pos)
        parsed = json.loads(cmd.strip())
        
        # Verify the command contains the calculated positions
        assert parsed['base'] == base_pos
        assert parsed['shoulder'] == shoulder_pos
        assert parsed['elbow'] == elbow_pos
        # Hand should have the offset applied
        assert parsed['hand'] == hand_pos + 3.1415926
    
    def test_zero_position_command(self):
        """Test command when all joints are at zero position."""
        cmd = build_serial_command(0, 0, 0, 0)
        parsed = json.loads(cmd.strip())
        assert parsed['base'] == 0
        assert parsed['shoulder'] == 0
        assert parsed['elbow'] == 0
        assert parsed['hand'] == 3.1415926  # offset applied
    
    def test_max_position_command(self):
        """Test command with maximum expected positions."""
        # Simulate maximum positions
        max_pos = 4095
        cmd = build_serial_command(max_pos, max_pos, max_pos, max_pos)
        parsed = json.loads(cmd.strip())
        assert parsed['base'] == max_pos
        assert parsed['shoulder'] == max_pos
        assert parsed['elbow'] == max_pos
        assert parsed['hand'] == max_pos + 3.1415926
    
    def test_min_position_command(self):
        """Test command with minimum expected positions."""
        # Simulate minimum positions
        min_pos = -1
        cmd = build_serial_command(min_pos, min_pos, min_pos, min_pos)
        parsed = json.loads(cmd.strip())
        assert parsed['base'] == min_pos
        assert parsed['shoulder'] == min_pos
        assert parsed['elbow'] == min_pos
        assert parsed['hand'] == min_pos + 3.1415926


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_very_small_angle(self):
        """Test with very small angle input."""
        result = posGet(0.00001, 1, 1)
        assert 2047 <= result <= 2048
    
    def test_very_large_angle(self):
        """Test with very large angle input."""
        result = posGet(100.0, 1, 1)
        # 100 rad * 2048/π ≈ 65200, so 2047 + 65200 ≈ 67247
        assert 67000 <= result <= 67500
    
    def test_pi_exact(self):
        """Test with exact π value."""
        result = posGet(math.pi, 1, 1)
        assert 4093 <= result <= 4097
    
    def test_negative_pi(self):
        """Test with -π value."""
        result = posGet(-math.pi, 1, 1)
        assert -5 <= result <= 5
    
    def test_half_pi(self):
        """Test with π/2 value."""
        result = posGet(math.pi / 2, 1, 1)
        assert 3070 <= result <= 3072
    
    def test_quarter_pi(self):
        """Test with π/4 value."""
        result = posGet(math.pi / 4, 1, 1)
        # π/4 rad * 2048/π = 512, so 2047 + 512 = 2559
        assert 2558 <= result <= 2561
    
    def test_three_quarter_pi(self):
        """Test with 3π/4 value."""
        result = posGet(3 * math.pi / 4, 1, 1)
        # 3π/4 rad * 2048/π = 1536, so 2047 + 1536 = 3583
        assert 3582 <= result <= 3585
    
    def test_direction_negative(self):
        """Test with negative direction."""
        result = posGet(math.pi, -1, 1)
        assert -5 <= result <= 5
    
    def test_multiplier_zero(self):
        """Test with zero multiplier."""
        result = posGet(1.57, 1, 0)
        assert 2047 <= result <= 2048
    
    def test_multiplier_one(self):
        """Test with multiplier of 1."""
        result = posGet(1.57, 1, 1)
        assert 3070 <= result <= 3072
    
    def test_multiplier_two(self):
        """Test with multiplier of 2."""
        result = posGet(1.57, 1, 2)
        assert 4090 <= result <= 4095
    
    def test_multiplier_half(self):
        """Test with multiplier of 0.5."""
        result = posGet(1.57, 1, 0.5)
        assert 2559 <= result <= 2562


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
