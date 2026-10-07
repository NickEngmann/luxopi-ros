"""Validation and normalization for the local simulator dashboard API."""

import math
import re
import hashlib
import json

from luxo_behaviors.roarm_m3_kinematics import M3_JOINT_LIMITS, M3_JOINT_NAMES
from luxo_behaviors.animation_capabilities import ANIMATION_NAMES
from luxo_behaviors.sim_interaction_rules import SIM_PETTING_ZONES


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
LIGHT_COLORS = {"red", "orange", "yellow", "green", "cyan", "blue", "purple", "white"}
MAX_COMMAND_CHARS = 2000
MAX_EVENT_BYTES = 4096
MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_VISION_IMAGE_BYTES = 8 * 1024 * 1024
MAX_REQUEST_ID_CHARS = 96
HEALTH_STALE_SECONDS = 3.0
REQUIRED_GRAPH_COMPONENTS = (
    "state_manager",
    "animation_command",
    "sim_motion_controller",
    "sim_direction_node",
    "speech_bridge",
    "robot_state_publisher",
    "simulator_dashboard",
)


def valid_joint_feedback(names, positions):
    """Require complete, finite feedback for one supported robot description."""
    if not isinstance(names, (list, tuple)) or not isinstance(positions, (list, tuple)):
        return False
    if len(names) != len(positions) or any(not isinstance(name, str) for name in names):
        return False
    if len(set(names)) != len(names):
        return False
    if set(names) == set(M3_JOINT_NAMES):
        limits = M3_JOINT_LIMITS
    elif set(names) == set(MANUAL_JOINT_LIMITS):
        limits = MANUAL_JOINT_LIMITS
    else:
        return False
    for name, value in zip(names, positions):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return False
        lower, upper = limits[name]
        if not lower - 0.02 <= value <= upper + 0.02:
            return False
    return True


def prune_expired_request_ids(request_ids, now, max_age=3600.0):
    """Expire oldest idempotency entries without copying the bounded cache.

    Entries are inserted with monotonic timestamps and never moved except on
    insertion, so expiration is a prefix scan and can stop at the first live
    entry. The caller must hold the cache's synchronization lock.
    """
    cutoff = now - max_age
    removed = 0
    while request_ids:
        _request_id, cached = next(iter(request_ids.items()))
        if cached[1] >= cutoff:
            break
        request_ids.popitem(last=False)
        removed += 1
    return removed


def camera_input_publications(event):
    """Do not synthesize emotion/distance after an explicit absent-person event."""
    if not event["person_present"]:
        return (("person_present", False),)
    return (
        ("person_present", True),
        ("emotion", event["emotion"]),
        ("distance", event["metres"]),
    )


def normalize_vision_result(result):
    """Reduce model output to a bounded, validated ROS event; RGB has no range."""
    if not isinstance(result, dict):
        raise ValueError("vision result must be an object")
    present = _boolean(result.get("person_present"), "person_present")
    if result.get("distance_meters") is not None:
        raise ValueError("RGB vision cannot supply metric distance")
    faces = result.get("faces")
    if not isinstance(faces, list) or len(faces) > 200:
        raise ValueError("vision faces must be a bounded list")
    if not present:
        if faces:
            raise ValueError("absent-person result cannot include faces")
        return {"type": "vision_inference", "person_present": False,
                "emotion": None, "face_count": 0}
    if not faces:
        raise ValueError("present-person result must include a face")

    candidates = []
    for face in faces:
        if not isinstance(face, dict) or face.get("emotion") not in EMOTIONS:
            raise ValueError("vision face has an unknown emotion")
        confidence = _number(face.get("confidence"), "face confidence")
        emotion_confidence = _number(face.get("emotion_confidence"), "emotion confidence")
        if not 0 <= confidence <= 1 or not 0 <= emotion_confidence <= 1:
            raise ValueError("vision confidence must be between 0 and 1")
        candidates.append((confidence, face["emotion"], emotion_confidence))
    face_confidence, emotion, emotion_confidence = max(candidates, key=lambda item: item[0])
    return {
        "type": "vision_inference",
        "person_present": True,
        "emotion": emotion,
        "face_count": len(faces),
        "face_confidence": face_confidence,
        "emotion_confidence": emotion_confidence,
    }


def summarize_simulator_health(snapshot, now_monotonic):
    """Return liveness and graph health using monotonic receipt timestamps."""
    present = set(snapshot.get("graph_nodes", []))
    state_received = snapshot.get("_state_received_monotonic")
    joints_received = snapshot.get("_joints_received_monotonic")
    state_age = None if state_received is None else max(0.0, now_monotonic - state_received)
    joints_age = None if joints_received is None else max(0.0, now_monotonic - joints_received)
    required = tuple(REQUIRED_GRAPH_COMPONENTS)
    if snapshot.get("simulation_backend") == "mujoco":
        required += ("mujoco_simulator",)
    components = {name: name in present for name in required}
    missing = [name for name, found in components.items() if not found]
    state_fresh = state_age is not None and state_age <= HEALTH_STALE_SECONDS
    joints_fresh = joints_age is not None and joints_age <= HEALTH_STALE_SECONDS
    state = snapshot.get("state")
    state_ready = state in STATE_NAMES - {"INITIALIZING", "ERROR", "SHUTDOWN"}
    joints_valid = bool(snapshot.get("_joint_feedback_valid", True)) and valid_joint_feedback(
        snapshot.get("joint_names", []), snapshot.get("positions", []))
    reasons = (["missing_components"] if missing else [])
    if not state_fresh:
        reasons.append("stale_state")
    if not joints_fresh:
        reasons.append("stale_joint_feedback")
    if not state_ready:
        reasons.append("state_not_ready")
    if not joints_valid:
        reasons.append("invalid_joint_feedback")
    return {
        "healthy": not reasons,
        "reasons": reasons,
        "state_ready": state_ready,
        "joint_feedback_valid": joints_valid,
        "node_count": len(present),
        "nodes": sorted(present),
        "components": components,
        "missing_required": missing,
        "state_age_seconds": state_age,
        "joint_state_age_seconds": joints_age,
        "state_fresh": state_fresh,
        "joint_state_fresh": joints_fresh,
        "stale_after_seconds": HEALTH_STALE_SECONDS,
    }


def normalize_event(payload):
    """Validate an event from the dashboard and return a typed plain dict.

    The return value deliberately contains only bounded built-in values so a
    UI request can never choose an arbitrary ROS topic or message type.
    """
    if not isinstance(payload, dict):
        raise ValueError("event must be a JSON object")

    kind = payload.get("type")
    request_id = payload.get("request_id")
    if request_id is not None and (
        not isinstance(request_id, str)
        or not 1 <= len(request_id) <= MAX_REQUEST_ID_CHARS
        or re.fullmatch(r"[A-Za-z0-9_.:-]+", request_id) is None
    ):
        raise ValueError("request_id must be 1..96 safe identifier characters")
    if kind == "voice_command":
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("voice command text must be non-empty")
        text = text.strip()
        if len(text) > MAX_COMMAND_CHARS:
            raise ValueError("voice command is too long")
        return _with_request_id({"type": kind, "text": text}, request_id)

    if kind == "audio_file":
        name = payload.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[0-9a-fA-F]{32}\.wav", name):
            raise ValueError("audio file must be a UUID WAV basename")
        return _with_request_id({"type": kind, "name": name}, request_id)

    if kind == "animation":
        name = payload.get("name")
        if name not in ANIMATION_NAMES:
            raise ValueError("unknown animation")
        speed = _number(payload.get("speed", 1.0), "speed")
        if not 0.1 <= speed <= 2.0:
            raise ValueError("animation speed must be between 0.1 and 2.0")
        return _with_request_id({"type": kind, "name": name, "speed": speed}, request_id)

    if kind == "cancel_animation":
        return _with_request_id({"type": kind}, request_id)

    if kind == "state_request":
        state = payload.get("state")
        if state not in STATE_NAMES:
            raise ValueError("state must be one of the registered simulator states")
        return _with_request_id({"type": kind, "state": state}, request_id)

    if kind == "simulation_speed":
        speed = _number(payload.get("scale"), "simulation speed")
        if speed not in (1.0, 2.0, 3.0):
            raise ValueError("simulation speed must be 1x, 2x, or 3x")
        return _with_request_id({"type": kind, "scale": speed}, request_id)

    if kind == "simulator_autonomy":
        return _with_request_id({"type": kind, "enabled": _boolean(payload.get("enabled"), "autonomy enabled")}, request_id)

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
        return _with_request_id({"type": kind, "positions": normalized}, request_id)

    if kind == "light_control":
        return _with_request_id({"type": kind, "enabled": _boolean(payload.get("enabled"), "enabled")}, request_id)

    if kind in {"brightness", "color_temperature"}:
        level = _number(payload.get("value"), "value")
        if not 0.0 <= level <= 1.0:
            raise ValueError(f"{kind} must be between 0.0 and 1.0")
        return _with_request_id({"type": kind, "value": level}, request_id)

    if kind == "light_color":
        color = payload.get("color")
        if color not in LIGHT_COLORS:
            raise ValueError("unknown light color")
        return _with_request_id({"type": kind, "color": color}, request_id)

    if kind == "audio_direction":
        angle = _number(payload.get("degrees"), "degrees")
        if not 0 <= angle <= 359:
            raise ValueError("microphone direction must be between 0 and 359 degrees")
        return _with_request_id({"type": kind, "degrees": angle}, request_id)

    if kind == "voice_active":
        return _with_request_id({"type": kind, "active": _boolean(payload.get("active"), "active")}, request_id)

    if kind == "touch":
        sensor = payload.get("sensor")
        if sensor not in TOUCH_SENSORS:
            raise ValueError("unknown touch sensor")
        value = _integer(payload.get("value"), "value")
        if not 0 <= value <= 255:
            raise ValueError("touch value must be between 0 and 255")
        return _with_request_id({"type": kind, "sensor": sensor, "value": value}, request_id)

    if kind == "petting_zone":
        zone = payload.get("zone")
        if zone not in SIM_PETTING_ZONES:
            raise ValueError("unknown simulated petting zone")
        return _with_request_id({"type": kind, "zone": zone,
                "active": _boolean(payload.get("active"), "active")}, request_id)

    if kind == "gesture":
        gesture = payload.get("gesture")
        if gesture not in GESTURES:
            raise ValueError("unknown gesture")
        return _with_request_id({"type": kind, "gesture": gesture}, request_id)

    if kind == "proximity":
        value = _integer(payload.get("value"), "value")
        if not 0 <= value <= 255:
            raise ValueError("proximity must be between 0 and 255")
        return _with_request_id({"type": kind, "value": value}, request_id)

    if kind == "distance":
        side = payload.get("side")
        if side not in DISTANCE_SIDES:
            raise ValueError("distance side must be left or right")
        metres = _number(payload.get("metres"), "metres")
        if not 0 <= metres <= 1.2:
            raise ValueError("distance must be between 0 and 1.2 metres")
        return _with_request_id({"type": kind, "side": side, "metres": metres}, request_id)

    if kind == "collision":
        side = payload.get("side")
        if side not in COLLISION_SIDES:
            raise ValueError("collision side must be front, left, or right")
        active = _boolean(payload.get("active"), "active")
        return _with_request_id({"type": kind, "side": side, "active": active}, request_id)

    if kind == "sensor_fault":
        side = payload.get("side")
        if side not in COLLISION_SIDES:
            raise ValueError("sensor fault side must be front, left, or right")
        active = _boolean(payload.get("active"), "active")
        return _with_request_id({"type": kind, "side": side, "active": active}, request_id)

    if kind == "vision":
        present = _boolean(payload.get("person_present"), "person_present")
        emotion = payload.get("emotion", "neutral")
        if emotion not in EMOTIONS:
            raise ValueError("unknown emotion")
        metres = _number(payload.get("metres", 1.0), "metres")
        if not 0.1 <= metres <= 10:
            raise ValueError("person distance must be between 0.1 and 10 metres")
        return _with_request_id({
            "type": kind,
            "person_present": present,
            "emotion": emotion,
            "metres": metres,
        }, request_id)

    raise ValueError("unsupported simulator event")


def _with_request_id(event, request_id):
    if request_id is not None:
        event["request_id"] = request_id
    return event


def event_fingerprint(event):
    """Stable digest for idempotency; request IDs themselves are excluded."""
    payload = {key: value for key, value in event.items() if key != "request_id"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
