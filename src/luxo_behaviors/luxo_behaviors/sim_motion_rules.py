"""ROS-free policy and pose validation for the simulated motion controller."""

import math

from luxo_behaviors.joint_motion import clamp_joint_positions, ordered_joint_target
from luxo_behaviors.joint_profiles import joint_profile


MOTION_HOLD_STATES = {"INITIALIZING", "ESCAPE_MODE", "ERROR", "SHUTDOWN"}
TWO_PI = 2.0 * math.pi
VOICE_DIRECTION_MAX_AGE = 2.0


def normalize_direction_degrees(direction):
    """Validate a DOA estimate and normalize it to the shortest signed angle."""
    try:
        angle = float(direction)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("direction must be a finite angle") from exc
    if not math.isfinite(angle) or abs(angle) > 360.0:
        raise ValueError("direction must be finite and within one revolution")
    return (angle + 180.0) % 360.0 - 180.0


def voice_direction_is_fresh(direction, received_at, now, *, max_age=VOICE_DIRECTION_MAX_AGE):
    """Return whether a finite, recent DOA estimate can drive motion."""
    if direction is None or received_at is None:
        return False
    try:
        angle = float(direction)
        age = float(now) - float(received_at)
        limit = float(max_age)
    except (TypeError, ValueError, OverflowError):
        return False
    return (math.isfinite(angle) and math.isfinite(age) and math.isfinite(limit) and limit >= 0.0
            and -0.05 <= age <= limit)


def voice_state_request_allowed(state):
    """DOA may own the FSM only from idle; it must not cancel another behavior."""
    name = getattr(state, "name", state)
    return str(name).upper() in {"IDLE", "VOICE_FOLLOWING"}


def voice_overlay_allowed(state):
    """DOA may steer base yaw during ordinary motion, never safety/manual/home."""
    name = getattr(state, "name", state)
    return str(name).upper() in {
        "VOICE_FOLLOWING", "ANIMATING", "PETTING", "EMOTION_REACTING"
    }


def nearest_cable_safe_angle(current, requested, lower, upper):
    """Choose the shortest equivalent yaw that stays inside cable-safe limits."""
    values = (current, requested, lower, upper)
    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError("angles and limits must be finite")
    current, requested, lower, upper = map(float, values)
    if lower >= upper or not lower <= current <= upper:
        raise ValueError("current yaw and ordered cable limits must be valid")
    center_turn = round((current - requested) / TWO_PI)
    candidates = []
    for turns in range(center_turn - 2, center_turn + 3):
        equivalent = requested + turns * TWO_PI
        candidates.append(min(upper, max(lower, equivalent)))
    return min(candidates, key=lambda angle: (abs(angle - current), abs(angle - requested)))


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
