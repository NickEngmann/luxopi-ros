"""Offline validation tests for dashboard event injection."""

import math

import pytest

from luxo_behaviors.simulator_protocol import (
    ANIMATION_NAMES, STATE_NAMES, camera_input_publications, normalize_event,
)
from luxo_behaviors.roarm_m3_kinematics import M3_JOINT_NAMES


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


def test_registered_animation_catalog_is_thirty_three_and_accepts_safe_speed():
    assert len(ANIMATION_NAMES) == 38
    assert normalize_event({"type": "animation", "name": "dance", "speed": 1.25}) == {
        "type": "animation",
        "name": "dance",
        "speed": 1.25,
    }


def test_all_twelve_fsm_states_and_four_joint_manual_pose_are_supported():
    assert len(STATE_NAMES) == 12
    assert normalize_event({"type": "state_request", "state": "ERROR"}) == {
        "type": "state_request",
        "state": "ERROR",
    }
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
