"""Offline validation tests for dashboard event injection."""

import math

import pytest

from luxo_behaviors.simulator_protocol import (
    ANIMATION_NAMES, STATE_NAMES, camera_input_publications,
    event_fingerprint, normalize_event, normalize_vision_result,
    prune_expired_request_ids,
)
from luxo_behaviors.roarm_m3_kinematics import M3_JOINT_NAMES


def test_request_id_expiry_prunes_only_oldest_expired_prefix():
    from collections import OrderedDict

    cache = OrderedDict([
        ("old-1", ("hash-1", 1.0)),
        ("old-2", ("hash-2", 2.0)),
        ("live", ("hash-3", 8.0)),
    ])
    assert prune_expired_request_ids(cache, now=10.0, max_age=5.0) == 2
    assert list(cache) == ["live"]
    assert prune_expired_request_ids(cache, now=11.0, max_age=5.0) == 0


@pytest.mark.parametrize(
    "event,expected",
    [
        ({"type": "voice_command", "text": "  open spotify  "},
         {"type": "voice_command", "text": "open spotify"}),
        ({"type": "audio_direction", "degrees": 359},
         {"type": "audio_direction", "degrees": 359.0}),
        ({"type": "touch", "sensor": "head_top", "value": 180},
         {"type": "touch", "sensor": "head_top", "value": 180}),
        ({"type": "petting_zone", "zone": "top_front", "active": True},
         {"type": "petting_zone", "zone": "top_front", "active": True}),
        ({"type": "petting_zone", "zone": "antenna", "active": False},
         {"type": "petting_zone", "zone": "antenna", "active": False}),
        ({"type": "gesture", "gesture": "left"},
         {"type": "gesture", "gesture": "left"}),
        ({"type": "proximity", "value": 255},
         {"type": "proximity", "value": 255}),
        ({"type": "distance", "side": "right", "metres": 0.8},
         {"type": "distance", "side": "right", "metres": 0.8}),
        ({"type": "collision", "side": "front", "active": True},
         {"type": "collision", "side": "front", "active": True}),
        ({"type": "vision", "person_present": True, "emotion": "happy", "metres": 1.2},
         {"type": "vision", "person_present": True, "emotion": "happy", "metres": 1.2}),
    ],
)
def test_normalize_valid_simulator_inputs(event, expected):
    assert normalize_event(event) == expected


def test_camera_absence_does_not_get_overridden_by_emotion_or_distance_inputs():
    absent = normalize_event({
        "type": "vision", "person_present": False, "emotion": "happy", "metres": 1.2,
    })
    assert camera_input_publications(absent) == (("person_present", False),)
    present = normalize_event({
        "type": "vision", "person_present": True, "emotion": "happy", "metres": 1.2,
    })
    assert camera_input_publications(present) == (
        ("person_present", True), ("emotion", "happy"), ("distance", 1.2),
    )


def test_image_inference_result_selects_best_face_without_inventing_distance():
    result = normalize_vision_result({
        "person_present": True,
        "distance_meters": None,
        "faces": [
            {"confidence": 0.6, "emotion_confidence": 0.9, "emotion": "sad"},
            {"confidence": 0.95, "emotion_confidence": 0.7, "emotion": "happy"},
        ],
    })

    assert result == {
        "type": "vision_inference", "person_present": True, "emotion": "happy",
        "face_count": 2, "face_confidence": 0.95, "emotion_confidence": 0.7,
    }


def test_image_inference_absence_clears_person_without_emotion_or_distance():
    assert normalize_vision_result({
        "person_present": False, "distance_meters": None, "faces": [],
    }) == {
        "type": "vision_inference", "person_present": False,
        "emotion": None, "face_count": 0,
    }


@pytest.mark.parametrize("result", [
    {"person_present": True, "distance_meters": 1.2, "faces": []},
    {"person_present": True, "distance_meters": None, "faces": [{"emotion": "unknown", "confidence": 0.9, "emotion_confidence": 0.8}]},
    {"person_present": True, "distance_meters": None, "faces": [{"emotion": "happy", "confidence": float("nan"), "emotion_confidence": 0.8}]},
    {"person_present": False, "distance_meters": None, "faces": [{"emotion": "happy", "confidence": 0.9, "emotion_confidence": 0.8}]},
])
def test_invalid_or_metric_image_vision_results_are_rejected(result):
    with pytest.raises(ValueError):
        normalize_vision_result(result)


def test_registered_animation_catalog_is_thirty_three_and_accepts_safe_speed():
    assert len(ANIMATION_NAMES) == 38
    assert normalize_event({"type": "animation", "name": "dance", "speed": 1.25}) == {
        "type": "animation",
        "name": "dance",
        "speed": 1.25,
    }


def test_dashboard_can_request_every_registered_simulator_state():
    assert len(STATE_NAMES) == 12
    for state in STATE_NAMES:
        assert normalize_event({"type": "state_request", "state": state})["state"] == state
    with pytest.raises(ValueError, match="registered simulator states"):
        normalize_event({"type": "state_request", "state": "NOT_A_STATE"})


@pytest.mark.parametrize("scale", [1, 2, 3])
def test_simulation_speed_accepts_only_supported_scales(scale):
    assert normalize_event({"type": "simulation_speed", "scale": scale}) == {
        "type": "simulation_speed", "scale": float(scale),
    }


@pytest.mark.parametrize("scale", [0, 1.5, 4, True, "2"])
def test_simulation_speed_rejects_unsupported_scales(scale):
    with pytest.raises(ValueError):
        normalize_event({"type": "simulation_speed", "scale": scale})


@pytest.mark.parametrize("enabled", [True, False])
def test_simulator_autonomy_toggle_requires_boolean(enabled):
    assert normalize_event({"type": "simulator_autonomy", "enabled": enabled}) == {
        "type": "simulator_autonomy", "enabled": enabled,
    }


def test_simulator_autonomy_rejects_non_boolean():
    with pytest.raises(ValueError):
        normalize_event({"type": "simulator_autonomy", "enabled": "false"})


@pytest.mark.parametrize("side", ["front", "left", "right"])
def test_simulator_sensor_fault_accepts_known_directions(side):
    assert normalize_event({"type": "sensor_fault", "side": side, "active": True}) == {
        "type": "sensor_fault", "side": side, "active": True,
    }


@pytest.mark.parametrize("event", [
    {"type": "sensor_fault", "side": "rear", "active": True},
    {"type": "sensor_fault", "side": "left", "active": 1},
])
def test_simulator_sensor_fault_rejects_invalid_values(event):
    with pytest.raises(ValueError):
        normalize_event(event)
    pose = {
        "base_to_L1": 0.1,
        "L1_to_L2": -0.2,
        "L2_to_L3": 0.3,
        "L3_to_L4": -0.4,
    }
    assert normalize_event({"type": "manual_joint_target", "positions": pose}) == {
        "type": "manual_joint_target",
        "positions": pose,
    }


def test_audio_file_event_accepts_only_uuid_wav_basename():
    name = "51a9e72134604bb5b4a8b5ec2ac249e7.wav"
    assert normalize_event({"type": "audio_file", "name": name}) == {
        "type": "audio_file",
        "name": name,
    }
    for invalid in ("../../recording.wav", "recording.wav", name + ".wav", "../" + name):
        with pytest.raises(ValueError):
            normalize_event({"type": "audio_file", "name": invalid})


def test_six_axis_manual_pose_requires_exact_vendor_names_and_limits():
    pose = {name: 0.0 for name in M3_JOINT_NAMES}
    pose["link5_to_gripper_link"] = 1.25
    normalized = normalize_event({"type": "manual_joint_target", "positions": pose})
    assert normalized["positions"] == pose
    pose["link5_to_gripper_link"] = 1.6
    with pytest.raises(ValueError, match="outside"):
        normalize_event({"type": "manual_joint_target", "positions": pose})
    pose.pop("link5_to_gripper_link")
    with pytest.raises(ValueError, match="four legacy or all six"):
        normalize_event({"type": "manual_joint_target", "positions": pose})


@pytest.mark.parametrize(
    "event",
    [
        {"type": "animation", "name": "does_not_exist"},
        {"type": "animation", "name": "dance", "speed": 2.1},
        {"type": "brightness", "value": -0.1},
        {"type": "color_temperature", "value": 1.1},
        {"type": "light_color", "color": "infrared"},
        {"type": "state_request", "state": "NOT_A_STATE"},
        {"type": "manual_joint_target", "positions": {"base_to_L1": 99}},
    ],
)
def test_animation_and_light_controls_reject_invalid_values(event):
    with pytest.raises(ValueError):
        normalize_event(event)


@pytest.mark.parametrize(
    "event",
    [
        None,
        [],
        {"type": "voice_command", "text": "  "},
        {"type": "voice_command", "text": "x" * 2001},
        {"type": "audio_direction", "degrees": math.nan},
        {"type": "audio_direction", "degrees": 360},
        {"type": "touch", "sensor": "../../topic", "value": 180},
        {"type": "touch", "sensor": "head_left", "value": True},
        {"type": "petting_zone", "zone": "head_left", "active": True},
        {"type": "petting_zone", "zone": "antenna", "active": "yes"},
        {"type": "gesture", "gesture": "wave_ros_command"},
        {"type": "proximity", "value": -1},
        {"type": "distance", "side": "front", "metres": 1},
        {"type": "distance", "side": "left", "metres": math.inf},
        {"type": "distance", "side": "left", "metres": 1.21},
        {"type": "collision", "side": "rear", "active": True},
        {"type": "collision", "side": "left", "active": "yes"},
        {"type": "vision", "person_present": 1, "emotion": "happy"},
        {"type": "vision", "person_present": False, "emotion": "unknown"},
        {"type": "arbitrary_topic", "topic": "/roarm/animation_command"},
    ],
)
def test_rejects_invalid_or_unbounded_simulator_input(event):
    with pytest.raises(ValueError):
        normalize_event(event)


@pytest.mark.parametrize("event", [
    {"type": "animation", "name": "dance", "speed": 0.1},
    {"type": "animation", "name": "dance", "speed": 2.0},
    {"type": "simulation_speed", "scale": 1.0},
    {"type": "simulation_speed", "scale": 3.0},
    {"type": "audio_direction", "degrees": 0},
    {"type": "audio_direction", "degrees": 359},
    {"type": "touch", "sensor": "head_right", "value": 0},
    {"type": "touch", "sensor": "head_right", "value": 255},
    {"type": "proximity", "value": 0},
    {"type": "proximity", "value": 255},
    {"type": "distance", "side": "left", "metres": 0},
    {"type": "distance", "side": "right", "metres": 1.2},
    {"type": "vision", "person_present": True, "emotion": "neutral", "metres": 0.1},
    {"type": "vision", "person_present": False, "emotion": "happy", "metres": 10},
    {"type": "brightness", "value": 0},
    {"type": "brightness", "value": 1},
    {"type": "color_temperature", "value": 0},
    {"type": "color_temperature", "value": 1},
])
def test_numeric_controls_accept_exact_documented_boundaries(event):
    assert normalize_event(event)["type"] == event["type"]


@pytest.mark.parametrize("request_id", ["a", "x" * 96, "deploy:echo-2.1_test"])
def test_request_ids_accept_bounded_safe_identifiers(request_id):
    event = normalize_event({"type": "light_control", "enabled": True, "request_id": request_id})
    assert event["request_id"] == request_id


@pytest.mark.parametrize("request_id", ["", "x" * 97, "../secret", "id with spaces", "id\nnext", 12, True])
def test_request_ids_reject_empty_oversized_or_unsafe_values(request_id):
    with pytest.raises(ValueError, match="request_id"):
        normalize_event({"type": "light_control", "enabled": True, "request_id": request_id})


def test_idempotency_fingerprint_is_stable_and_ignores_request_id():
    first = normalize_event({"type": "light_color", "color": "purple", "request_id": "attempt-1"})
    retry = normalize_event({"type": "light_color", "color": "purple", "request_id": "attempt-1"})
    changed = normalize_event({"type": "light_color", "color": "blue", "request_id": "attempt-1"})
    assert event_fingerprint(first) == event_fingerprint(retry)
    assert event_fingerprint(first) != event_fingerprint(changed)
