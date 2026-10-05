"""Actual server methods must observe feedback before reporting completion."""
import ast
import math
from pathlib import Path
from types import SimpleNamespace
import pytest
from luxo_behaviors.joint_profiles import (joint_profile, pose_to_animation_positions,
                                           animation_pose_for_profile)


def methods():
    tree = ast.parse(Path('src/luxo_behaviors/luxo_behaviors/animation_command.py').read_text())
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    body = [n for n in klass.body if isinstance(n, ast.FunctionDef)
            and n.name in {'sim_profile_feedback_callback', '_wait_for_simulated_pose',
                           '_refresh_collision_status'}]
    now = [1.0]
    clock = SimpleNamespace(monotonic=lambda: now[0],
                            sleep=lambda delta: now.__setitem__(0, now[0]+delta))
    ns = dict(time=clock, math=math, joint_profile=joint_profile,
              pose_to_animation_positions=pose_to_animation_positions,
              animation_pose_for_profile=animation_pose_for_profile)
    exec(compile(ast.Module(body=body, type_ignores=[]), '<animation>', 'exec'), ns)
    return ns, now


def test_feedback_is_measured_pose_and_gripper_not_acceleration():
    ns, _ = methods()
    obj = SimpleNamespace(joint_profile='roarm_m3', enable_feasible_retiming=True)
    names, _ = joint_profile('roarm_m3')
    msg = SimpleNamespace(name=list(names), position=[.2, .3, .4, .5, -.7, .6], velocity=[0]*6)
    ns['sim_profile_feedback_callback'](obj, msg)
    assert obj.current_positions == [.2, .3, .4, .5, -.7, 10]
    assert obj.current_gripper_position == .6
    assert obj.hardware_position_received


def test_completion_waits_for_settled_measured_pose():
    ns, now = methods()
    target = [.2, .3, .4, .5, -.7, 10]
    obj = SimpleNamespace(joint_profile='roarm_m3', current_gripper_position=.6,
                          collision_preempted=False,
                          _sim_feedback=(1.0, target[:5]+[.6], [0]*6))
    assert ns['_wait_for_simulated_pose'](obj, target, None)
    assert now[0] >= 1.06


def test_stale_feedback_cannot_report_success_and_danger_interrupts():
    ns, _ = methods()
    target = [.2, .3, .4, .5, -.7, 10]
    obj = SimpleNamespace(joint_profile='roarm_m3', current_gripper_position=.6,
                          collision_preempted=False,
                          _sim_feedback=(0.0, target[:5]+[.6], [0]*6))
    with pytest.raises(RuntimeError, match='did not settle'):
        ns['_wait_for_simulated_pose'](obj, target, None)
    obj.collision_preempted = True
    assert not ns['_wait_for_simulated_pose'](obj, target, None)


def test_warning_adjustment_requires_replan_instead_of_fault():
    ns, _ = methods()
    target = [.2, .3, .4, .5, -.7, 10]
    obj = SimpleNamespace(joint_profile='roarm_m3', current_gripper_position=.6,
                          collision_preempted=False, collision_status='warning',
                          get_logger=lambda: SimpleNamespace(warning=lambda _: None),
                          _sim_feedback=(0.0, target[:5]+[.6], [0]*6))
    assert not ns['_wait_for_simulated_pose'](obj, target, None)


@pytest.mark.parametrize('mode', ['hold_stale', 'hold_replan', 'hold_imminent', 'hold_blocked'])
def test_expected_safety_hold_interrupts_without_actuator_error(mode):
    ns, _ = methods()
    obj = SimpleNamespace(joint_profile='roarm_m3', current_gripper_position=0,
                          collision_preempted=False, _sim_feedback=None,
                          _sim_motion_status=(1.0, mode),
                          get_logger=lambda: SimpleNamespace(warning=lambda _: None))
    assert ns['_wait_for_simulated_pose'](obj, [.2, .3, .4, .5, -.7, 10], None) is False


def test_outer_warning_band_remains_warning_when_legacy_bool_is_false():
    ns, _ = methods()
    ns['collision_status_from_warnings'] = lambda legacy, warnings: legacy
    obj = SimpleNamespace(_legacy_collision_status='safe', _collision_warnings={'left': False},
                          _atomic_sensor_status={'left': {'active': False, 'severity': 'warning',
                                                         'valid': True}}, _goal_handle=None)
    ns['_refresh_collision_status'](obj)
    assert obj.collision_status == 'warning:left:warning'
