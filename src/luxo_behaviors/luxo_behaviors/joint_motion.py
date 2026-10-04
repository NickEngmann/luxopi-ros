"""ROS-independent joint bounds and velocity/acceleration limiting."""

from __future__ import annotations

import math


URDF_JOINT_LIMITS = {
    "base_to_L1": (-3.14, 3.14),
    "L1_to_L2": (-1.570796, 1.570796),
    "L2_to_L3": (-0.78539815, 3.1415926),
    "L3_to_L4": (-2.3561942, 2.3561942),
}


def clamp_joint_positions(names, positions, limits=URDF_JOINT_LIMITS):
    """Return finite, bounded positions in the supplied joint order."""
    if len(names) != len(positions):
        raise ValueError("joint names and positions must have equal length")
    result = []
    for name, raw_value in zip(names, positions):
        value = float(raw_value)
        if not math.isfinite(value):
            raise ValueError(f"non-finite target for joint {name}")
        lower, upper = limits.get(name, (-math.inf, math.inf))
        result.append(min(upper, max(lower, value)))
    return result


def ordered_joint_target(names, positions, expected_names=tuple(URDF_JOINT_LIMITS)):
    """Validate a complete named target and return values in expected order."""
    if len(names) != len(positions) or len(names) != len(expected_names):
        raise ValueError("target must contain each expected joint exactly once")
    if len(set(names)) != len(names) or set(names) != set(expected_names):
        raise ValueError("target has duplicate or unexpected joint names")
    by_name = {}
    for name, raw_value in zip(names, positions):
        value = float(raw_value)
        if not math.isfinite(value):
            raise ValueError(f"non-finite target for joint {name}")
        by_name[name] = value
    return [by_name[name] for name in expected_names]


def format_target_positions(target_positions, joint_names, include_acceleration=False):
    """Format target positions and keep serial metadata off simulation topics."""
    positions = [float(value) for value in target_positions[:len(joint_names)]]
    positions.extend([0.0] * (len(joint_names) - len(positions)))
    if include_acceleration and len(target_positions) > 5:
        positions.append(float(target_positions[5]))
    return positions


class JointMotionLimiter:
    """Slew-limits a target while respecting per-joint position/velocity/accel.

    ``step`` is deterministic and uses caller-provided elapsed time so the same
    constraints can be exercised offline and by a ROS timer at runtime.
    """

    def __init__(self, joint_names, initial_positions=None, *,
                 limits=URDF_JOINT_LIMITS, max_velocity=0.5,
                 max_acceleration=1.0):
        self.joint_names = list(joint_names)
        if not self.joint_names:
            raise ValueError("at least one joint is required")
        self.limits = limits
        self.max_velocity = self._expand(max_velocity, "max_velocity")
        self.max_acceleration = self._expand(max_acceleration, "max_acceleration")
        initial = initial_positions or [0.0] * len(self.joint_names)
        if len(initial) != len(self.joint_names):
            raise ValueError("initial position count does not match joint names")
        self.positions = clamp_joint_positions(self.joint_names, initial, limits)
        self.velocities = [0.0] * len(self.joint_names)

    def _expand(self, value, name):
        values = [float(value)] * len(self.joint_names) if isinstance(value, (int, float)) else list(value)
        if len(values) != len(self.joint_names):
            raise ValueError(f"{name} count does not match joint names")
        if any(not math.isfinite(item) or item <= 0.0 for item in values):
            raise ValueError(f"{name} values must be finite and positive")
        return values

    def step(self, target_positions, dt):
        """Advance one bounded step toward a target and return the new pose."""
        if len(target_positions) != len(self.joint_names):
            raise ValueError("target position count does not match joint names")
        dt = float(dt)
        if not math.isfinite(dt) or dt <= 0.0:
            raise ValueError("dt must be finite and positive")
        targets = clamp_joint_positions(self.joint_names, target_positions, self.limits)
        for index, target in enumerate(targets):
            desired_velocity = (target - self.positions[index]) / dt
            desired_velocity = min(
                self.max_velocity[index],
                max(-self.max_velocity[index], desired_velocity),
            )
            velocity_delta = desired_velocity - self.velocities[index]
            max_velocity_delta = self.max_acceleration[index] * dt
            velocity = self.velocities[index] + min(
                max_velocity_delta, max(-max_velocity_delta, velocity_delta)
            )
            next_position = self.positions[index] + velocity * dt
            # Prevent numerical overshoot when the target is inside this step.
            if (target - self.positions[index]) * (target - next_position) <= 0.0:
                next_position = target
                velocity = 0.0
            self.positions[index] = next_position
            self.velocities[index] = velocity
        self.positions = clamp_joint_positions(self.joint_names, self.positions, self.limits)
        return list(self.positions)
