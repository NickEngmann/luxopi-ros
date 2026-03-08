"""
Pure logic module for dynamic speed/acceleration adaptation.

This module contains the algorithms for calculating adaptive speed
and acceleration based on joint states, independent of ROS2 and hardware.
"""

import math
from typing import List, Dict, Tuple


class AdaptationEngine:
    """
    Engine for computing dynamic speed and acceleration values
    based on joint states and movement requirements.
    """
    
    # Configuration constants
    MAX_SPEED = 100.0  # Maximum speed value (0-255 scale)
    MAX_ACCEL = 50.0   # Maximum acceleration value (0-255 scale)
    BASE_SPEED = 20.0  # Base speed when joints are at target
    SPEED_FACTOR = 0.5  # How much distance affects speed
    ACCEL_FACTOR = 0.3  # How much velocity affects acceleration
    
    def __init__(self, max_speed: float = None, max_accel: float = None,
                 base_speed: float = None, speed_factor: float = None,
                 accel_factor: float = None):
        """
        Initialize the adaptation engine with optional configuration.
        
        Args:
            max_speed: Maximum speed value (default: MAX_SPEED)
            max_accel: Maximum acceleration value (default: MAX_ACCEL)
            base_speed: Base speed when at target (default: BASE_SPEED)
            speed_factor: Multiplier for distance-based speed (default: SPEED_FACTOR)
            accel_factor: Multiplier for velocity-based acceleration (default: ACCEL_FACTOR)
        """
        self.max_speed = max_speed if max_speed is not None else self.MAX_SPEED
        self.max_accel = max_accel if max_accel is not None else self.MAX_ACCEL
        self.base_speed = base_speed if base_speed is not None else self.BASE_SPEED
        self.speed_factor = speed_factor if speed_factor is not None else self.SPEED_FACTOR
        self.accel_factor = accel_factor if accel_factor is not None else self.ACCEL_FACTOR
        
        # Track previous positions for velocity calculation
        self._prev_positions: List[float] = []
        self._prev_time: float = 0.0
    
    def calculate_distance(self, current: List[float], target: List[float]) -> float:
        """
        Calculate the total distance from current to target positions.
        
        Args:
            current: List of current joint positions (in radians)
            target: List of target joint positions (in radians)
            
        Returns:
            Total Euclidean distance in joint space
        """
        if len(current) != len(target):
            raise ValueError(f"Position mismatch: {len(current)} vs {len(target)} joints")
        
        total_distance = 0.0
        for c, t in zip(current, target):
            diff = t - c
            total_distance += diff * diff
        
        return math.sqrt(total_distance)
    
    def calculate_velocity(self, current: List[float], prev_positions: List[List[float]], 
                          current_time: float, prev_time: float) -> float:
        """
        Calculate the average velocity based on position changes over time.
        
        Args:
            current: Current joint positions
            prev_positions: History of previous positions
            current_time: Current timestamp
            prev_time: Previous timestamp
            
        Returns:
            Average velocity (distance per unit time)
        """
        if not prev_positions or current_time <= prev_time:
            return 0.0
        
        total_velocity = 0.0
        for prev_pos in prev_positions[-5:]:  # Use last 5 samples for smoother velocity
            if len(current) != len(prev_pos):
                continue
            for c, p in zip(current, prev_pos):
                diff = c - p
                total_velocity += diff * diff
        
        total_velocity = math.sqrt(total_velocity)
        time_delta = current_time - prev_time
        
        return total_velocity / time_delta if time_delta > 0 else 0.0
    
    def compute_adaptive_speed(self, current: List[float], target: List[float],
                               velocity: float = 0.0) -> float:
        """
        Compute adaptive speed based on distance to target and current velocity.
        
        Speed decreases as we get closer to target (smooth approach)
        Speed decreases when velocity is high (prevent overshoot)
        
        Args:
            current: Current joint positions
            target: Target joint positions
            velocity: Current velocity (optional, defaults to 0)
            
        Returns:
            Adaptive speed value (0 to max_speed)
        """
        distance = self.calculate_distance(current, target)
        
        # Distance-based speed: slower when close to target
        distance_factor = max(0.1, 1.0 - (distance / 10.0))  # Normalize by expected max distance
        
        # Velocity-based speed reduction: slow down when moving fast
        velocity_factor = max(0.1, 1.0 - (velocity / 5.0))  # Normalize by expected max velocity
        
        # Combined speed calculation
        speed = self.base_speed * distance_factor * velocity_factor
        
        # Apply speed factor scaling
        speed = speed * self.speed_factor + self.base_speed * (1 - self.speed_factor)
        
        return min(speed, self.max_speed)
    
    def compute_adaptive_accel(self, current: List[float], target: List[float],
                               velocity: float, speed: float) -> float:
        """
        Compute adaptive acceleration based on movement dynamics.
        
        Acceleration increases when far from target
        Acceleration decreases when approaching target or moving fast
        
        Args:
            current: Current joint positions
            target: Target joint positions
            velocity: Current velocity
            speed: Current speed value
            
        Returns:
            Adaptive acceleration value (0 to max_accel)
        """
        distance = self.calculate_distance(current, target)
        
        # Distance-based acceleration: more accel when far from target
        distance_factor = min(1.0, distance / 2.0)  # Normalize
        
        # Velocity-based acceleration: reduce accel when moving fast
        velocity_factor = max(0.2, 1.0 - (velocity / 10.0))
        
        # Speed-based acceleration: reduce accel when speed is high
        speed_factor = max(0.3, 1.0 - (speed / (self.max_speed * 2)))
        
        # Combined acceleration calculation
        accel = self.max_accel * distance_factor * velocity_factor * speed_factor
        
        return min(accel, self.max_accel)
    
    def update_state(self, current: List[float], timestamp: float = None) -> None:
        """
        Update internal state with current positions for velocity calculation.
        
        Args:
            current: Current joint positions
            timestamp: Current timestamp (defaults to time.time())
        """
        import time
        if timestamp is None:
            timestamp = time.time()
        
        self._prev_positions.append(list(current))
        self._prev_time = timestamp
        
        # Keep only last 10 samples to avoid memory growth
        if len(self._prev_positions) > 10:
            self._prev_positions.pop(0)
    
    def reset_state(self) -> None:
        """
        Reset all internal state tracking.
        """
        self._prev_positions = []
        self._prev_time = 0.0
