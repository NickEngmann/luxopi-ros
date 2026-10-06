"""Home uses measured settling, preserves the gripper, and never replays a plan."""
import math
import pytest
from luxo_behaviors.home_sequence import HomeSequence
from luxo_behaviors.sim_motion_rules import motion_is_frozen


def test_two_stage_home_keeps_base_and_gripper_and_requires_measured_dwell():
    plan = HomeSequence('roarm_m3', [0.2, 0, 0, 0, 0, 0.7], 0)
    assert plan.target == pytest.approx([0.2, 0.5, 1.3, 1.4, -1.5, 0.7])
    assert plan.advance(plan.target, [0]*6, 0.1) == 'running'
    assert plan.advance(plan.target, [0]*6, 0.59) == 'running'
    assert plan.stage == 0
    plan.advance(plan.target, [0]*6, 0.61)
    assert plan.stage == 1
    assert plan.target == pytest.approx([0.2, -0.85, 1.3, 1.4, -1.5, 0.7])
    plan.advance(plan.target, [0]*6, 0.7)
    assert plan.advance(plan.target, [0]*6, 0.81) == 'completed'


def test_home_centers_base_near_joint_limit_and_supports_legacy_profile():
    plan = HomeSequence('roarm_m3', [3.1, 0, 0, 0, 0, 0.2], 0)
    assert plan.target[0] == 0
    legacy = HomeSequence('urdf4', [0.2, 0, 0, 0], 0)
    assert legacy.target == pytest.approx([0.2, 0.5, 1.3, 1.4])


def test_unsettled_or_stale_measurements_cannot_complete_home():
    plan = HomeSequence('roarm_m3', [0]*6, 0)
    plan.advance(plan.target, [0]*6, 0.1)
    plan.advance(plan.target, [0.5]*6, 0.8)
    assert plan.settled_since is None
    plan.advance(plan.target, [0]*6, 1, fresh=False)
    assert plan.stage == 0
    plan.advance(plan.target, [0]*6, 1.1)
    assert plan.advance(plan.target, [0]*6, 1.5) == 'running'
    assert plan.stage == 0
    assert plan.advance(plan.target, [0]*6, 31) == 'timed_out'


def test_interrupted_home_does_not_resume_after_sensor_clear():
    plan = HomeSequence('roarm_m3', [0]*6, 0)
    plan.interrupt('hold_stale')
    assert plan.advance(plan.target, [0]*6, 1) == 'interrupted'
    assert plan.reason == 'hold_stale'


@pytest.mark.parametrize('current', [[0]*5, [math.nan]*6, [math.inf]*6])
def test_home_rejects_incomplete_or_nonfinite_start_feedback(current):
    with pytest.raises(ValueError):
        HomeSequence('roarm_m3', current, 0)


def test_initializing_is_a_motion_hold_state():
    assert motion_is_frozen('INITIALIZING', ())
