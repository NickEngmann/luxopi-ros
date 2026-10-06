import pytest

from luxo_behaviors.motion_control import scaled_duration
from luxo_behaviors.sim_interaction_rules import animation_state_for
from luxo_behaviors.state_machine import LuxoState


@pytest.mark.parametrize(
    ("nominal", "speed", "expected"),
    [(8.05, 2.0, 4.025), (3.0, 1.0, 3.0), (4.0, 0.5, 8.0)],
)
def test_animation_speed_scales_nominal_duration_once(nominal, speed, expected):
    assert scaled_duration(nominal, speed) == pytest.approx(expected)


@pytest.mark.parametrize("speed", [0.0, 0.09, 2.01, float("nan"), float("inf")])
def test_invalid_animation_speed_uses_normal_speed(speed):
    assert scaled_duration(3.0, speed) == pytest.approx(3.0)


def test_negative_duration_is_clamped_to_zero():
    assert scaled_duration(-1.0, 2.0) == 0.0


def test_petting_animation_keeps_petting_as_state_owner():
    assert animation_state_for("petting") is LuxoState.PETTING
    assert animation_state_for("idle") is LuxoState.ANIMATING
    assert animation_state_for("idle", "emotion") is LuxoState.EMOTION_REACTING


@pytest.mark.parametrize("category", ["action", "emotion", "idle", "petting"])
def test_emotion_trigger_owns_emotion_reacting_state(category):
    assert animation_state_for(category, "emotion") is LuxoState.EMOTION_REACTING
