"""Geometry and derivative limits, independent of actuator simulation."""
import math
import random

import pytest
from luxo_behaviors.continuous_trajectory import ContinuousTrajectory
from luxo_behaviors.trajectory_timing import retime_cubic_plan


def test_preserves_waypoints_extrema_holds_and_metadata():
    frames = [[v, 0, 0, 0, 0, 9000] for v in (.1, .2, .2, .1, -.1)]
    plan = ContinuousTrajectory([0]*6, frames, [.1]*5)
    for i, frame in enumerate(frames):
        assert plan.segment(i, 1) == pytest.approx(frame)
        assert plan.segment(i, 0)[0] == pytest.approx(0 if i == 0 else frames[i-1][0])
        lo, hi = sorted((0 if i == 0 else frames[i-1][0], frame[0]))
        for k in range(101):
            assert lo-1e-12 <= plan.segment(i, k/100)[0] <= hi+1e-12
    assert all(plan.segment(2, k/100)[0] == pytest.approx(.2) for k in range(101))


def test_interior_velocity_continuity_and_rest_endpoints():
    plan = ContinuousTrajectory([0]*6, [[v]*5+[10] for v in (.1, .2, .3)], [.2]*3)
    for j in range(5):
        assert plan.coefficients[0][j][2] == pytest.approx(0)
        a,b,c,_ = plan.coefficients[-1][j]
        assert 3*a+2*b+c == pytest.approx(0)
    for i in range(2):
        a,b,c,_ = plan.coefficients[i][0]
        left = (3*a+2*b+c)/plan.durations[i]
        right = plan.coefficients[i+1][0][2]/plan.durations[i+1]
        assert left == pytest.approx(right)
        assert left > 0  # does not stop at every monotone waypoint


def test_analytic_limits_hold_for_random_multi_axis_paths():
    rng = random.Random(12)
    for _ in range(30):
        frames = [[rng.uniform(-1, 1) for _ in range(5)]+[10] for _ in range(8)]
        plan = ContinuousTrajectory([0]*6, frames, [rng.uniform(.05,.5) for _ in frames],
                                    speed_multiplier=1.35)
        for segment, duration in zip(plan.coefficients, plan.durations):
            for a,b,c,_ in segment:
                for k in range(101):
                    u = k/100
                    assert abs((3*a*u*u+2*b*u+c)/duration) <= .5+1e-9
                    assert abs((6*a*u+2*b)/duration**2) <= 1+1e-9


def test_dense_monotone_path_avoids_repeated_stops():
    frames = [[v/100, 0, 0, 0, 0, 10] for v in range(1,31)]
    plan = ContinuousTrajectory([0]*6, frames, [.05]*30)
    old = sum(retime_cubic_plan([0]*6, frames, [.05]*30))
    assert plan.total_duration < old*.5
    assert plan.sample(plan.total_duration)[0] == pytest.approx(frames[-1])


@pytest.mark.parametrize('value', [float('nan'), float('inf')])
def test_rejects_nonfinite_clock_or_fraction(value):
    plan = ContinuousTrajectory([0]*6, [[.1]*5+[10]], [.1])
    with pytest.raises(ValueError): plan.sample(value)
    with pytest.raises(ValueError): plan.segment(0, value)
