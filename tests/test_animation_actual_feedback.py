"""Actual server methods must observe feedback before reporting completion."""
import ast
import math
from pathlib import Path
from types import SimpleNamespace
import pytest
from luxo_behaviors.joint_profiles import (joint_profile, pose_to_animation_positions,
                                           animation_pose_for_profile)
from luxo_behaviors.state_machine import LuxoState


def methods():
    tree = ast.parse(Path('src/luxo_behaviors/luxo_behaviors/animation_command.py').read_text())
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    body = [n for n in klass.body if isinstance(n, ast.FunctionDef)
            and n.name in {'publish_joint_states_target', 'sim_profile_feedback_callback', '_wait_for_simulated_pose',
                           '_refresh_collision_status', 'sim_motion_status_callback',
                           '_safety_interrupt_reason'}]
    now = [1.0]
    clock = SimpleNamespace(monotonic=lambda: now[0],
                            sleep=lambda delta: now.__setitem__(0, now[0]+delta))
    ns = dict(time=clock, math=math, json=__import__('json'), joint_profile=joint_profile,
              pose_to_animation_positions=pose_to_animation_positions,
              animation_pose_for_profile=animation_pose_for_profile,
              LuxoState=LuxoState,
              JointState=lambda: SimpleNamespace(header=SimpleNamespace()),
              format_target_positions=lambda *_args, **_kwargs: [0.0] * 4)
    exec(compile(ast.Module(body=body, type_ignores=[]), '<animation>', 'exec'), ns)
    return ns, now


def server_obj(ns, **fields):
    obj = SimpleNamespace(**fields)
    obj._safety_interrupt_reason = lambda started: ns['_safety_interrupt_reason'](obj, started)
    return obj


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
    obj = server_obj(ns, joint_profile='roarm_m3', current_gripper_position=.6,
                     collision_preempted=False,
                     _sim_feedback=(1.0, target[:5]+[.6], [0]*6))
    assert ns['_wait_for_simulated_pose'](obj, target, None)
    assert now[0] >= 1.06


def test_stale_feedback_cannot_report_success_and_danger_interrupts():
    ns, _ = methods()
    target = [.2, .3, .4, .5, -.7, 10]
    obj = server_obj(ns, joint_profile='roarm_m3', current_gripper_position=.6,
                     collision_preempted=False,
                     _sim_feedback=(0.0, target[:5]+[.6], [0]*6))
    with pytest.raises(RuntimeError, match='did not settle'):
        ns['_wait_for_simulated_pose'](obj, target, None)
    obj.collision_preempted = True
    assert not ns['_wait_for_simulated_pose'](obj, target, None)


def test_warning_adjustment_requires_replan_instead_of_fault():
    ns, _ = methods()
    target = [.2, .3, .4, .5, -.7, 10]
    obj = server_obj(ns, joint_profile='roarm_m3', current_gripper_position=.6,
                     collision_preempted=False, collision_status='warning',
                     get_logger=lambda: SimpleNamespace(warning=lambda _: None),
                     _sim_feedback=(0.0, target[:5]+[.6], [0]*6))
    assert not ns['_wait_for_simulated_pose'](obj, target, None)


@pytest.mark.parametrize('mode', ['hold_stale', 'hold_replan', 'hold_imminent', 'hold_blocked'])
def test_expected_safety_hold_interrupts_without_actuator_error(mode):
    ns, _ = methods()
    obj = server_obj(ns, joint_profile='roarm_m3', current_gripper_position=0,
                     collision_preempted=False, enable_feasible_retiming=True,
                     _sim_feedback=None,
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


def test_motion_hold_interrupt_has_controller_receipt_grace():
    ns, now = methods()
    obj = server_obj(ns, enable_feasible_retiming=True,
                     _sim_motion_status=(1.0, 'hold_replan', None),
                     collision_preempted=False)
    assert ns['_safety_interrupt_reason'](obj, 1.0) is None
    now[0] = 1.149
    assert ns['_safety_interrupt_reason'](obj, 1.0) is None
    now[0] = 1.151
    assert 'hold_replan' in ns['_safety_interrupt_reason'](obj, 1.0)


def test_short_stages_cannot_restart_the_per_goal_safety_grace():
    ns, now = methods()
    obj = server_obj(ns, enable_feasible_retiming=True,
                     _safety_intent_started=1.0,
                     _sim_motion_status=(1.0, 'hold_stale', None),
                     collision_preempted=False)
    for index in range(40):
        now[0] = 1.151 + index * .01
        obj._sim_motion_status = (now[0], 'hold_stale', None)
        # A fresh stage starts every 10 ms. Grace belongs to the goal's first
        # target, so none of these stage boundaries may defer interruption.
        reason = ns['_safety_interrupt_reason'](obj, now[0] - .01)
        assert 'hold_stale' in reason


def test_warning_adjustment_has_a_bounded_motion_demonstration_window():
    ns, now = methods()
    obj = server_obj(ns, enable_feasible_retiming=True,
                     _sim_motion_status=(2.9, 'adjust', 1.0),
                     collision_preempted=False)
    now[0] = 2.999
    assert ns['_safety_interrupt_reason'](obj, 1.0) is None
    now[0] = 3.0
    assert 'retreat was applied' in ns['_safety_interrupt_reason'](obj, 1.0)


def test_adjustment_timer_survives_repeated_status_publications():
    ns, now = methods()
    obj = SimpleNamespace(_sim_motion_status=None)
    ns['sim_motion_status_callback'](obj, SimpleNamespace(data='{"avoidance_mode":"adjust"}'))
    start = obj._sim_motion_status[2]
    now[0] += .05
    ns['sim_motion_status_callback'](obj, SimpleNamespace(data='{"avoidance_mode":"adjust"}'))
    assert obj._sim_motion_status[2] == start


def test_delayed_animation_idle_cleanup_does_not_override_new_state_owner():
    ns, _ = methods()

    class Stamp:
        def __init__(self, seconds):
            self.nanoseconds = int(seconds * 1e9)

        def __sub__(self, other):
            return SimpleNamespace(nanoseconds=self.nanoseconds - other.nanoseconds)

        def to_msg(self):
            return self.nanoseconds

    now = Stamp(10.0)
    requested = []
    sources = []
    obj = SimpleNamespace(
        should_publish=True,
        get_clock=lambda: SimpleNamespace(now=lambda: now),
        is_animating=False,
        movement_source='animation',
        last_animation_end_time=Stamp(6.0),
        publish_movement_source=lambda: sources.append(obj.movement_source),
        get_current_state=lambda: LuxoState.USER_CONTROL,
        request_state_transition=lambda state, **kwargs: requested.append((state, kwargs)),
        joint_profile='urdf4',
        use_hardware_joint_names=False,
        joint_names=['base_to_L1', 'L1_to_L2', 'L2_to_L3', 'L3_to_L4'],
        target_positions=[0.0] * 4,
        current_gripper_position=0.0,
        enforce_joint_limits=False,
        publish_target=False,
        joint_publisher=SimpleNamespace(publish=lambda _message: None),
        get_logger=lambda: SimpleNamespace(debug=lambda *_args: None, error=lambda *_args: None),
        _target_intent_id='test',
    )
    ns['publish_joint_states_target'](obj)
    assert obj.movement_source == 'idle'
    assert sources == ['idle']
    assert requested == []
