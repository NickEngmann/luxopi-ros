"""
Unit tests for the AdaptationEngine class in adaptation_logic.py.

These tests verify the dynamic speed/acceleration adaptation algorithms
work correctly without requiring ROS2 or hardware.
"""

import pytest
import math

# Import the AdaptationEngine directly
import sys
sys.path.insert(0, 'src/serial_ctrl/serial_ctrl')

from adaptation_logic import AdaptationEngine


class TestAdaptationEngine:
    """Tests for the AdaptationEngine class."""
    
    def test_default_initialization(self):
        """Test that default values are set correctly."""
        engine = AdaptationEngine()
        assert engine.max_speed == 100.0
        assert engine.max_accel == 50.0
        assert engine.base_speed == 20.0
        assert engine.speed_factor == 0.5
        assert engine.accel_factor == 0.3
    
    def test_custom_initialization(self):
        """Test that custom values can be set."""
        engine = AdaptationEngine(
            max_speed=200.0,
            max_accel=100.0,
            base_speed=30.0,
            speed_factor=0.7,
            accel_factor=0.4
        )
        assert engine.max_speed == 200.0
        assert engine.max_accel == 100.0
        assert engine.base_speed == 30.0
        assert engine.speed_factor == 0.7
        assert engine.accel_factor == 0.4
    
    def test_calculate_distance_zero(self):
        """Test distance calculation when positions are identical."""
        engine = AdaptationEngine()
        current = [0.0, 0.0, 0.0, 0.0]
        target = [0.0, 0.0, 0.0, 0.0]
        distance = engine.calculate_distance(current, target)
        assert distance == 0.0
    
    def test_calculate_distance_nonzero(self):
        """Test distance calculation with non-zero positions."""
        engine = AdaptationEngine()
        current = [0.0, 0.0, 0.0, 0.0]
        target = [1.0, 1.0, 1.0, 1.0]
        distance = engine.calculate_distance(current, target)
        expected = math.sqrt(4.0)  # sqrt(1^2 + 1^2 + 1^2 + 1^2)
        assert abs(distance - expected) < 0.0001
    
    def test_calculate_distance_partial(self):
        """Test distance calculation with partial movement."""
        engine = AdaptationEngine()
        current = [0.0, 0.0, 0.0, 0.0]
        target = [0.5, 0.5, 0.0, 0.0]
        distance = engine.calculate_distance(current, target)
        expected = math.sqrt(0.5**2 + 0.5**2)  # sqrt(0.25 + 0.25)
        assert abs(distance - expected) < 0.0001
    
    def test_calculate_velocity_zero_delta(self):
        """Test velocity calculation with zero time delta."""
        engine = AdaptationEngine()
        current = [0.5, 0.5, 0.5, 0.5]
        prev_positions = [[0.5, 0.5, 0.5, 0.5]]
        current_time = 1.0
        prev_time = 1.0  # Same time = zero delta
        velocity = engine.calculate_velocity(current, prev_positions, current_time, prev_time)
        assert velocity == 0.0
    
    def test_calculate_velocity_nonzero(self):
        """Test velocity calculation with non-zero time delta."""
        engine = AdaptationEngine()
        current = [1.0, 1.0, 1.0, 1.0]
        prev_positions = [[0.0, 0.0, 0.0, 0.0]]
        current_time = 1.1  # 100ms later
        prev_time = 1.0
        velocity = engine.calculate_velocity(current, prev_positions, current_time, prev_time)
        assert velocity > 0.0
    
    def test_compute_adaptive_speed_at_target(self):
        """Test adaptive speed when at target (distance = 0)."""
        engine = AdaptationEngine()
        current = [0.0, 0.0, 0.0, 0.0]
        target = [0.0, 0.0, 0.0, 0.0]
        
        speed = engine.compute_adaptive_speed(current, target)
        
        # When at target, speed should be at base speed (distance_factor = 1.0)
        assert speed == engine.base_speed
    
    def test_compute_adaptive_speed_far_from_target(self):
        """Test adaptive speed when far from target."""
        engine = AdaptationEngine()
        current = [0.0, 0.0, 0.0, 0.0]
        target = [1.0, 1.0, 1.0, 1.0]
        
        speed = engine.compute_adaptive_speed(current, target)
        
        # Speed should be closer to base speed when far from target
        assert speed > engine.base_speed * 0.5
        assert speed <= engine.max_speed
    
    def test_compute_adaptive_speed_with_velocity(self):
        """Test adaptive speed with high velocity (should reduce speed)."""
        engine = AdaptationEngine()
        current = [0.5, 0.5, 0.5, 0.5]
        target = [1.0, 1.0, 1.0, 1.0]
        velocity = 6.0  # High velocity (above threshold)
        
        speed = engine.compute_adaptive_speed(current, target, velocity)
        
        # High velocity should reduce speed
        assert speed < engine.base_speed
    
    def test_compute_adaptive_accel_at_target(self):
        """Test adaptive acceleration when at target."""
        engine = AdaptationEngine()
        current = [0.0, 0.0, 0.0, 0.0]
        target = [0.0, 0.0, 0.0, 0.0]
        speed = engine.base_speed
        velocity = 0.0
        
        accel = engine.compute_adaptive_accel(current, target, velocity, speed)
        
        # When at target, acceleration should be minimal
        assert accel < engine.max_accel * 0.5
    
    def test_compute_adaptive_accel_far_from_target(self):
        """Test adaptive acceleration when far from target."""
        engine = AdaptationEngine()
        current = [0.0, 0.0, 0.0, 0.0]
        target = [2.0, 2.0, 2.0, 2.0]  # Far from target
        speed = engine.base_speed
        velocity = 0.0
        
        accel = engine.compute_adaptive_accel(current, target, velocity, speed)
        
        # Far from target should give higher acceleration
        assert accel > engine.max_accel * 0.5
        assert accel <= engine.max_accel
    
    def test_update_state(self):
        """Test that state is updated correctly."""
        engine = AdaptationEngine()
        current = [0.5, 0.5, 0.5, 0.5]
        
        engine.update_state(current, 1.0)
        
        assert len(engine._prev_positions) == 1
        assert engine._prev_positions[0] == [0.5, 0.5, 0.5, 0.5]
        assert engine._prev_time == 1.0
    
    def test_update_state_limits_history(self):
        """Test that state history is limited to 10 samples."""
        engine = AdaptationEngine()
        
        # Add 15 samples
        for i in range(15):
            current = [float(i), float(i), float(i), float(i)]
            engine.update_state(current, float(i))
        
        # Should only have last 10 samples
        assert len(engine._prev_positions) == 10
        # Last sample should be from i=14
        assert engine._prev_positions[-1] == [14.0, 14.0, 14.0, 14.0]
    
    def test_reset_state(self):
        """Test that state is reset correctly."""
        engine = AdaptationEngine()
        current = [0.5, 0.5, 0.5, 0.5]
        engine.update_state(current, 1.0)
        
        engine.reset_state()
        
        assert len(engine._prev_positions) == 0
        assert engine._prev_time == 0.0
    
    def test_calculate_distance_mismatch(self):
        """Test that distance calculation raises error for mismatched sizes."""
        engine = AdaptationEngine()
        current = [0.0, 0.0]
        target = [0.0, 0.0, 0.0]
        
        with pytest.raises(ValueError):
            engine.calculate_distance(current, target)


class TestAdaptationEngineIntegration:
    """Integration tests for the AdaptationEngine."""
    
    def test_realistic_robot_scenario(self):
        """Test with a realistic robot movement scenario."""
        engine = AdaptationEngine()
        
        # Initial state: robot at rest at target
        current = [0.0, 0.0, 0.0, 0.0]
        target = [0.0, 0.0, 0.0, 0.0]
        
        speed = engine.compute_adaptive_speed(current, target)
        
        # Should be minimal speed when at target
        assert speed < engine.base_speed
        
        # Robot starts moving towards target
        current = [0.1, 0.1, 0.1, 0.1]
        prev_positions = [[0.0, 0.0, 0.0, 0.0]]
        current_time = 0.1
        prev_time = 0.0
        
        velocity = engine.calculate_velocity(current, prev_positions, current_time, prev_time)
        assert velocity > 0.0
        
        # Speed should be reduced due to distance to target
        speed = engine.compute_adaptive_speed(current, target, velocity)
        assert speed < engine.base_speed
    
    def test_velocity_calculation_consistency(self):
        """Test that velocity calculations are consistent."""
        engine = AdaptationEngine()
        
        # Same positions should give same velocity
        current = [0.5, 0.5, 0.5, 0.5]
        prev_positions = [[0.0, 0.0, 0.0, 0.0]]
        current_time = 1.1
        prev_time = 1.0
        
        velocity1 = engine.calculate_velocity(current, prev_positions, current_time, prev_time)
        velocity2 = engine.calculate_velocity(current, prev_positions, current_time, prev_time)
        
        assert velocity1 == velocity2
    
    def test_distance_calculation_consistency(self):
        """Test that distance calculations are consistent."""
        engine = AdaptationEngine()
        
        # Same positions should give same distance
        current = [0.5, 0.5, 0.5, 0.5]
        target = [1.0, 1.0, 1.0, 1.0]
        
        distance1 = engine.calculate_distance(current, target)
        distance2 = engine.calculate_distance(current, target)
        
        assert distance1 == distance2
    
    def test_adaptive_values_workflow(self):
        """Test the complete adaptive values workflow."""
        engine = AdaptationEngine()
        
        # Simulate a complete movement cycle
        current = [0.0, 0.0, 0.0, 0.0]
        target = [0.5, 0.5, 0.5, 0.5]
        
        # Step 1: Calculate initial speed
        speed = engine.compute_adaptive_speed(current, target)
        assert speed > 0
        
        # Step 2: Update state
        engine.update_state(current, 0.0)
        
        # Step 3: Move to new position
        current = [0.1, 0.1, 0.1, 0.1]
        engine.update_state(current, 0.1)
        
        # Step 4: Calculate velocity
        prev_positions = [[0.0, 0.0, 0.0, 0.0]]
        velocity = engine.calculate_velocity(current, prev_positions, 0.1, 0.0)
        assert velocity > 0
        
        # Step 5: Calculate new speed with velocity
        speed = engine.compute_adaptive_speed(current, target, velocity)
        assert speed > 0
        
        # Step 6: Calculate acceleration
        accel = engine.compute_adaptive_accel(current, target, velocity, speed)
        assert accel > 0
        
        # Step 7: Verify bounds
        assert 0 <= speed <= engine.max_speed
        assert 0 <= accel <= engine.max_accel


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
