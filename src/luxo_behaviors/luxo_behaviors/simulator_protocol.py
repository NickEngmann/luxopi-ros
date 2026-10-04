"""Validation and normalization for the local simulator dashboard API."""

import math


TOUCH_SENSORS = {"head_top", "head_left", "head_bottom", "head_right"}
DISTANCE_SIDES = {"left", "right"}
COLLISION_SIDES = {"front", "left", "right"}
GESTURES = {"left", "right", "up", "down", "near", "far", "none"}
EMOTIONS = {"neutral", "happy", "sad", "angry", "surprise", "fear", "disgust"}
MAX_COMMAND_CHARS = 2000
MAX_EVENT_BYTES = 4096


def normalize_event(payload):
    """Validate an event from the dashboard and return a typed plain dict.

    The return value deliberately contains only bounded built-in values so a
    UI request can never choose an arbitrary ROS topic or message type.
    """
    if not isinstance(payload, dict):
        raise ValueError("event must be a JSON object")

    kind = payload.get("type")
    if kind == "voice_command":
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("voice command text must be non-empty")
        text = text.strip()
        if len(text) > MAX_COMMAND_CHARS:
            raise ValueError("voice command is too long")
        return {"type": kind, "text": text}

    if kind == "audio_direction":
        angle = _number(payload.get("degrees"), "degrees")
        if not 0 <= angle <= 359:
            raise ValueError("microphone direction must be between 0 and 359 degrees")
        return {"type": kind, "degrees": angle}

    if kind == "voice_active":
        return {"type": kind, "active": _boolean(payload.get("active"), "active")}

    if kind == "touch":
        sensor = payload.get("sensor")
        if sensor not in TOUCH_SENSORS:
            raise ValueError("unknown touch sensor")
        value = _integer(payload.get("value"), "value")
        if not 0 <= value <= 255:
            raise ValueError("touch value must be between 0 and 255")
        return {"type": kind, "sensor": sensor, "value": value}

    if kind == "gesture":
        gesture = payload.get("gesture")
        if gesture not in GESTURES:
            raise ValueError("unknown gesture")
        return {"type": kind, "gesture": gesture}

    if kind == "proximity":
        value = _integer(payload.get("value"), "value")
        if not 0 <= value <= 255:
            raise ValueError("proximity must be between 0 and 255")
        return {"type": kind, "value": value}

    if kind == "distance":
        side = payload.get("side")
        if side not in DISTANCE_SIDES:
            raise ValueError("distance side must be left or right")
        metres = _number(payload.get("metres"), "metres")
        if not 0.01 <= metres <= 10:
            raise ValueError("distance must be between 0.01 and 10 metres")
        return {"type": kind, "side": side, "metres": metres}

    if kind == "collision":
        side = payload.get("side")
        if side not in COLLISION_SIDES:
            raise ValueError("collision side must be front, left, or right")
        active = _boolean(payload.get("active"), "active")
        return {"type": kind, "side": side, "active": active}

    if kind == "vision":
        present = _boolean(payload.get("person_present"), "person_present")
        emotion = payload.get("emotion", "neutral")
        if emotion not in EMOTIONS:
            raise ValueError("unknown emotion")
        metres = _number(payload.get("metres", 1.0), "metres")
        if not 0.1 <= metres <= 10:
            raise ValueError("person distance must be between 0.1 and 10 metres")
        return {
            "type": kind,
            "person_present": present,
            "emotion": emotion,
            "metres": metres,
        }

    raise ValueError("unsupported simulator event")


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _boolean(value, name):
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value
