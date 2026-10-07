"""ROS-free motion policies shared by the hardware and simulator paths."""

import math


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


def cable_safe_voice_yaw(current, direction_degrees, lower, upper):
    """Project a ReSpeaker heading onto the nearest reachable cable-safe yaw."""
    direction = normalize_direction_degrees(direction_degrees)
    return nearest_cable_safe_angle(current, math.radians(direction), lower, upper)
