"""ROS-free policy and pose validation for the simulated motion controller."""

import math

from luxo_behaviors.joint_motion import clamp_joint_positions, ordered_joint_target
from luxo_behaviors.joint_profiles import joint_profile


MOTION_HOLD_STATES = {"INITIALIZING", "ESCAPE_MODE", "ERROR", "SHUTDOWN"}


def motion_is_frozen(state, collision_active):
    """Hold on latched emergency states; directional warnings use avoidance policy."""
    del collision_active  # direction/severity are handled atomically by ReactiveAvoidance
    return str(state).upper() in MOTION_HOLD_STATES


def validate_manual_pose(state, names, positions, profile="urdf4"):
    """Validate a user-control pose and return its URDF-clamped joint order."""
    if str(state).upper() != "USER_CONTROL":
        raise ValueError("manual pose requires USER_CONTROL state")
    expected_names, limits = joint_profile(profile)
    target = ordered_joint_target(names, positions, expected_names)
    return clamp_joint_positions(expected_names, target, limits)


def validate_feedback(names, positions, velocities, profile="urdf4"):
    """Validate named physics feedback without mutating a command trajectory."""
    expected_names, limits = joint_profile(profile)
    measured = ordered_joint_target(names, positions, expected_names)
    measured = clamp_joint_positions(expected_names, measured, limits)
    if velocities:
        measured_velocity = ordered_joint_target(names, velocities, expected_names)
        if any(not math.isfinite(value) for value in measured_velocity):
            raise ValueError("joint velocities must be finite")
    else:
        measured_velocity = None
    return measured, measured_velocity
