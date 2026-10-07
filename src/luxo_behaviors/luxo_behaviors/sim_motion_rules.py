"""ROS-free policy and pose validation for the simulated motion controller."""

import math

from luxo_behaviors.joint_motion import clamp_joint_positions, ordered_joint_target
from luxo_behaviors.joint_profiles import joint_profile
from luxo_behaviors.motion_policy import (
    cable_safe_voice_yaw, nearest_cable_safe_angle, normalize_direction_degrees,
    voice_direction_is_fresh, voice_overlay_allowed, voice_state_request_allowed,
)


MOTION_HOLD_STATES = {"INITIALIZING", "ESCAPE_MODE", "ERROR", "SHUTDOWN"}


def motion_is_frozen(state, collision_active):
    """Hold on latched emergency states; directional warnings use avoidance policy."""
    del collision_active  # direction/severity are handled atomically by ReactiveAvoidance
    return str(state).upper() in MOTION_HOLD_STATES


def inactive_voice_reconcile_due(state, voice_active, inactive_since, request_at,
                                 now, *, grace_seconds=0.25, retry_seconds=1.0):
    """Detect a voice state restored after its inactive signal already arrived."""
    if str(state).upper() != "VOICE_FOLLOWING" or voice_active or inactive_since is None:
        return False
    elapsed = float(now) - float(inactive_since)
    if elapsed < float(grace_seconds):
        return False
    return request_at is None or float(now) - float(request_at) >= float(retry_seconds)


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
