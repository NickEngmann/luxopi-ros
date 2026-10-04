"""Offline validation tests for dashboard event injection."""

import math

import pytest

from luxo_behaviors.simulator_protocol import ANIMATION_NAMES, normalize_event


@pytest.mark.parametrize(
    "event,expected",
    [
        ({"type": "voice_command", "text": "  open spotify  "},
         {"type": "voice_command", "text": "open spotify"}),
        ({"type": "audio_direction", "degrees": 359},
         {"type": "audio_direction", "degrees": 359.0}),
        ({"type": "touch", "sensor": "head_top", "value": 180},
         {"type": "touch", "sensor": "head_top", "value": 180}),
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


def test_registered_animation_catalog_is_thirty_three_and_accepts_safe_speed():
    assert len(ANIMATION_NAMES) == 33
    assert normalize_event({"type": "animation", "name": "dance", "speed": 1.25}) == {
        "type": "animation",
        "name": "dance",
        "speed": 1.25,
    }


@pytest.mark.parametrize(
    "event",
    [
        {"type": "animation", "name": "does_not_exist"},
        {"type": "animation", "name": "dance", "speed": 2.1},
        {"type": "brightness", "value": -0.1},
        {"type": "color_temperature", "value": 1.1},
        {"type": "light_color", "color": "infrared"},
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
        {"type": "gesture", "gesture": "wave_ros_command"},
        {"type": "proximity", "value": -1},
        {"type": "distance", "side": "front", "metres": 1},
        {"type": "distance", "side": "left", "metres": math.inf},
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
