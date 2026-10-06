"""Safe policy for routing synthetic APDS swipes to existing animations."""

from __future__ import annotations


GESTURE_ANIMATIONS = {
    "left": "look_around_casual",
    "right": "curious_exploration",
    "up": "neck_stretch",
    "down": "nod",
}
GESTURE_COOLDOWN_SECONDS = 1.0


def normalize_gesture(value):
    """Return one supported swipe name, or ``None`` for malformed input."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in GESTURE_ANIMATIONS else None


def gesture_block_reason(*, state, voice_status, primary_animation_active,
                         cue_active, petting_active, gesture_active,
                         last_started_at, now):
    """Explain why a swipe must not acquire animation ownership."""
    if state != "IDLE":
        return f"state:{state.lower()}"
    if voice_status != "idle":
        return f"voice:{voice_status}"
    if primary_animation_active or cue_active or petting_active or gesture_active:
        return "animation_busy"
    if last_started_at > 0.0 and now - last_started_at < GESTURE_COOLDOWN_SECONDS:
        return "cooldown"
    return ""
