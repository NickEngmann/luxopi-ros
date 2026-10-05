import math
import pytest
from luxo_behaviors.trajectory_timing import feasible_cubic_duration, retime_cubic_plan


def test_cubic_derivatives_obey_limits_even_at_high_requested_speed():
    before = [0]*5+[10]
    after = [1, -.6, .25, 0, -.2, 200]
    duration, = retime_cubic_plan(before, [after], [.2], speed_multiplier=3)
    for x, y in zip(before[:5], after[:5]):
        # Analytic maxima for cubic ease-in-out.
        assert 3*abs(y-x)/duration <= .5+1e-12
        assert 12*abs(y-x)/duration**2 <= 1+1e-12
    assert duration == 6


def test_acceleration_metadata_is_never_retimed_as_a_joint():
    assert feasible_cubic_duration([0]*5+[1], [0]*5+[1000], .5,
                                  max_velocity=.5, max_acceleration=1) == .5


def test_slow_request_preserved_and_segment_start_updated():
    assert retime_cubic_plan([0]*5, [[.1]*5, [.2]*5], [3, 3]) == (3, 3)
    assert retime_cubic_plan([0]*5, [[1]*5, [1]*5], [.1, .1])[1] == .1


@pytest.mark.parametrize('value', [0, -1, math.nan, math.inf])
def test_invalid_bounds_fail(value):
    with pytest.raises(ValueError):
        feasible_cubic_duration([0]*5, [1]*5, 1,
                                max_velocity=value, max_acceleration=1)
