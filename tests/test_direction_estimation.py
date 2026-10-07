"""Known-angle delayed PCM goes through the same estimator as live capture."""
import pathlib
import sys
import numpy as np
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'src/luxo_behaviors'))
from luxo_behaviors.direction_estimation import (
    DirectionActivity, circular_statistics, estimate_direction, robot_angle,
    synthesize_direction,
)

@pytest.mark.parametrize('channels', [4, 6])
@pytest.mark.parametrize('noise', [0.0, 0.02, 0.1])
@pytest.mark.parametrize('angle', [0, 1, 30, 60, 90, 120, 180, 240, 270, 330, 359])
def test_known_angle_delayed_voiced_pcm(angle, noise, channels):
    frames = synthesize_direction(angle, noise=noise, channels=channels, seed=angle+7)
    measured = estimate_direction(frames, channels=channels, direction_offset=250)
    error = (measured-angle+180)%360-180
    assert abs(error) < 2.0


def test_silent_reference_channels_do_not_corrupt_raw_mic_estimation():
    frames = synthesize_direction(60).reshape(-1, 6)
    frames[:, 0] = 32767
    frames[:, 5] = -32768
    assert abs(estimate_direction(frames.reshape(-1), direction_offset=250)-60) < 2
    frames[:, 1:5] = 0
    assert estimate_direction(frames.reshape(-1), direction_offset=250) is None


def test_subsample_resolution_improves_configured_array():
    angles = range(0, 360, 10)
    errors = {1: [], 16: []}
    for angle in angles:
        frames = synthesize_direction(angle)
        for interpolation in errors:
            measured = estimate_direction(frames, direction_offset=250, interp=interpolation)
            errors[interpolation].append(abs((measured-angle+180)%360-180))
    assert np.mean(errors[16]) < np.mean(errors[1])/3
    assert max(errors[16]) < 2


def test_circular_smoothing_wraparound_and_ambiguous_opposites():
    angle, spread = circular_statistics([359, 0, 1])
    assert min(angle, 360-angle) < .1
    assert spread < 2
    _, spread = circular_statistics([0, 180])
    assert spread > 60 and np.isfinite(spread)


def test_geometry_and_activity_timeout():
    assert robot_angle(0) == 0
    assert -100 < robot_angle(90) < -90
    activity = DirectionActivity(timeout=1.5)
    assert not activity.expire(0)
    activity.heard(5)
    assert not activity.expire(6.5)
    assert activity.expire(6.5001)
    assert not activity.active
    assert not activity.expire(7)


def test_incomplete_frames_rejected():
    with pytest.raises(ValueError):
        estimate_direction(np.ones(17))
