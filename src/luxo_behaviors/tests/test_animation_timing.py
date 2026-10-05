import pytest

from luxo_behaviors.motion_control import scaled_duration


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
