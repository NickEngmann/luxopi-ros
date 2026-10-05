"""Validation and normalization for the local simulator dashboard API."""

import math
import re

from luxo_behaviors.roarm_m3_kinematics import M3_JOINT_LIMITS, M3_JOINT_NAMES


TOUCH_SENSORS = {"head_top", "head_left", "head_bottom", "head_right"}
DISTANCE_SIDES = {"left", "right"}
COLLISION_SIDES = {"front", "left", "right"}
GESTURES = {"left", "right", "up", "down", "near", "far", "none"}
EMOTIONS = {"neutral", "happy", "sad", "surprise", "anger"}
STATE_NAMES = {
    "IDLE", "ANIMATING", "VOICE_FOLLOWING", "COLLISION_AVOIDING", "RETURNING_HOME",
    "ESCAPE_MODE", "USER_CONTROL", "EMOTION_REACTING", "PETTING", "ERROR",
    "INITIALIZING", "SHUTDOWN",
}
MANUAL_JOINT_LIMITS = {
    "base_to_L1": (-3.14, 3.14),
    "L1_to_L2": (-1.570796, 1.570796),
    "L2_to_L3": (-0.78539815, 3.1415926),
    "L3_to_L4": (-2.3561942, 2.3561942),
}
ANIMATION_NAMES = {
    "folded_wiggle", "bouncy_wiggle", "sleepy_melt", "nod", "shake", "close", "stop",
    "gentle_sway", "curious_exploration", "breathing", "attentive_listening", "playful_bob",
    "scanning_watch", "settling_adjust", "dreamy_drift", "neck_stretch", "sleep",
    "yawning_stretch", "shoulder_shimmy", "look_around_casual", "contented_sigh",
    "head_bobbing", "tail_wag", "pondering", "excited", "sad", "playful", "startled",
    "curious", "think", "stretch", "dance", "idle",
}
LIGHT_COLORS = {"red", "orange", "yellow", "green", "cyan", "blue", "purple", "white"}
MAX_COMMAND_CHARS = 2000
MAX_EVENT_BYTES = 4096
MAX_AUDIO_BYTES = 8 * 1024 * 1024


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

    if kind == "audio_file":
        name = payload.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[0-9a-fA-F]{32}\.wav", name):
            raise ValueError("audio file must be a UUID WAV basename")
        return {"type": kind, "name": name}

    if kind == "animation":
        name = payload.get("name")
        if name not in ANIMATION_NAMES:
            raise ValueError("unknown animation")
        speed = _number(payload.get("speed", 1.0), "speed")
        if not 0.1 <= speed <= 2.0:
            raise ValueError("animation speed must be between 0.1 and 2.0")
        return {"type": kind, "name": name, "speed": speed}

    if kind == "cancel_animation":
        return {"type": kind}

    if kind == "state_request":
        state = payload.get("state")
        if state not in STATE_NAMES:
            raise ValueError("unknown Luxo state")
        return {"type": kind, "state": state}

    if kind == "manual_joint_target":
        positions = payload.get("positions")
        if not isinstance(positions, dict):
            raise ValueError("manual pose must specify all joint positions")
        supplied = set(positions)
        if supplied == set(MANUAL_JOINT_LIMITS):
            limits = MANUAL_JOINT_LIMITS
        elif supplied == set(M3_JOINT_NAMES):
            limits = M3_JOINT_LIMITS
        else:
            raise ValueError("manual pose must specify all four legacy or all six vendor joints")
        normalized = {}
        for name, bounds in limits.items():
            value = _number(positions[name], name)
            if not bounds[0] <= value <= bounds[1]:
                raise ValueError(f"{name} is outside its URDF limits")
            normalized[name] = value
        return {"type": kind, "positions": normalized}

    if kind == "light_control":
        return {"type": kind, "enabled": _boolean(payload.get("enabled"), "enabled")}

    if kind in {"brightness", "color_temperature"}:
        level = _number(payload.get("value"), "value")
        if not 0.0 <= level <= 1.0:
            raise ValueError(f"{kind} must be between 0.0 and 1.0")
        return {"type": kind, "value": level}

    if kind == "light_color":
        color = payload.get("color")
        if color not in LIGHT_COLORS:
            raise ValueError("unknown light color")
        return {"type": kind, "color": color}

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
