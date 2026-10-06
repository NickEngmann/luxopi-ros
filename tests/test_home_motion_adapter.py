"""Run actual motion-owner methods with the real limiter and simulated clocks."""
import ast
import json
from collections import deque
from pathlib import Path
from types import SimpleNamespace
import pytest
from luxo_behaviors.home_sequence import HomeSequence
from luxo_behaviors.joint_motion import JointMotionLimiter, ordered_joint_target
from luxo_behaviors.joint_profiles import joint_profile
from luxo_behaviors.reactive_avoidance import ReactiveAvoidance
from luxo_behaviors.sim_motion_rules import motion_is_frozen


def make_controller():
    source = Path('src/luxo_behaviors/luxo_behaviors/sim_motion_controller.py')
    tree = ast.parse(source.read_text())
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    methods = [n for n in klass.body if isinstance(n, ast.FunctionDef)
               and n.name in {'state_callback', 'state_info_callback', 'target_callback', 'publish_step'}]
    now = [0.0]
    def joint_message():
        return SimpleNamespace(header=SimpleNamespace(stamp=None))
    namespace = dict(time=SimpleNamespace(monotonic=lambda: now[0]),
                     HomeSequence=HomeSequence, ordered_joint_target=ordered_joint_target,
                     motion_is_frozen=motion_is_frozen, math=__import__('math'), json=json,
                     JointState=joint_message, String=lambda: SimpleNamespace())
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), namespace)
    names, limits = joint_profile('roarm_m3')
    node = SimpleNamespace(profile='roarm_m3', joint_names=names, joint_limits=limits,
        current_state='IDLE', manual_target=None, manual_target_received_at=None,
        animation_target=[0]*6, animation_intent_id='old-goal',
        animation_target_received_at=0.0, blocked_animation_intent_id=None,
        publish_feedback=True, measured_positions=[0]*6, measured_velocities=[0]*6,
        feedback_received_at=None, home_sequence=None, home_owner=None, retired_home_owners=deque(maxlen=128), home_received_at=None,
        home_completion_pending=False, home_warning_started=None, voice_active=False,
        voice_direction=None, last_tick=0.0, collision_active=dict(front=False,left=False,right=False),
        manual_target_rejected='', reactive_avoidance=ReactiveAvoidance(limits=limits),
        limiter=JointMotionLimiter(names, limits=limits), avoidance_mode='clear',
        avoidance_directions=[], get_clock=lambda: SimpleNamespace(now=lambda: SimpleNamespace(to_msg=lambda: 0)),
        get_logger=lambda: SimpleNamespace(warning=lambda *a: None))
    commands, statuses, completed = [], [], []
    node.joint_pub=SimpleNamespace(publish=commands.append)
    node.motion_status=SimpleNamespace(publish=lambda m: statuses.append(json.loads(m.data)))
    node._complete_home=lambda: completed.append(node.home_sequence.status) if node.home_sequence else None
    return node, namespace, now, commands, statuses, completed


def test_home_runs_both_stages_through_limiter_and_blocks_old_goal_on_exit():
    node, methods, now, commands, statuses, completed = make_controller()
    methods['state_callback'](node, SimpleNamespace(data='RETURNING_HOME'))
    methods['state_info_callback'](node, SimpleNamespace(current_state='RETURNING_HOME', requested_by='home_return:test'))
    for index in range(1, 1501):
        now[0]=index*0.02
        methods['publish_step'](node)
        if completed: break
    assert completed == ['completed']
    assert {s['home_stage'] for s in statuses} == {1, 2}
    assert node.limiter.positions == pytest.approx([0,-.85,1.3,1.4,-1.5,0], abs=.03)
    assert max(abs(v) for m in commands for v in m.velocity) <= .5
    methods['state_callback'](node, SimpleNamespace(data='IDLE'))
    held = list(node.animation_target)
    old = SimpleNamespace(name=node.joint_names, position=[0]*6,
                          header=SimpleNamespace(frame_id='old-goal'))
    methods['target_callback'](node, old)
    assert node.animation_target == held
    old.header.frame_id = 'new-goal'
    methods['target_callback'](node, old)
    assert node.animation_target == [0]*6


def test_sensor_hold_ends_home_without_resuming_an_obsolete_target():
    node, methods, now, commands, statuses, completed = make_controller()
    methods['state_callback'](node, SimpleNamespace(data='RETURNING_HOME'))
    methods['state_info_callback'](node, SimpleNamespace(current_state='RETURNING_HOME', requested_by='home_return:test'))
    node.reactive_avoidance.update_sensor('left', True, now[0], severity='danger', valid=True)
    now[0]=.02
    methods['publish_step'](node)
    assert completed == ['interrupted']
    assert statuses[-1]['home_reason'].startswith('hold_')
    assert statuses[-1]['motion_hold_requested']


def test_early_state_exit_discards_home_and_preserves_current_pose():
    node, methods, now, commands, statuses, completed = make_controller()
    methods['state_callback'](node, SimpleNamespace(data='RETURNING_HOME'))
    methods['state_info_callback'](node, SimpleNamespace(current_state='RETURNING_HOME', requested_by='home_return:test'))
    methods['state_callback'](node, SimpleNamespace(data='USER_CONTROL'))
    assert node.home_sequence is None
    assert node.animation_target == node.limiter.positions


def test_emergency_state_recovery_does_not_replay_old_animation():
    node, methods, now, commands, statuses, completed = make_controller()
    methods['state_callback'](node, SimpleNamespace(data='ERROR'))
    old = SimpleNamespace(name=node.joint_names, position=[1]*6,
                          header=SimpleNamespace(frame_id='old-goal'))
    methods['target_callback'](node, old)
    assert node.animation_target == [0]*6
    methods['state_callback'](node, SimpleNamespace(data='IDLE'))
    methods['target_callback'](node, old)
    assert node.animation_target == [0]*6


def test_safety_completion_cannot_restore_and_restart_retired_home():
    node, methods, now, commands, statuses, completed = make_controller()
    methods['state_callback'](node, SimpleNamespace(data='RETURNING_HOME'))
    info = SimpleNamespace(current_state='RETURNING_HOME', requested_by='home_return:first')
    methods['state_info_callback'](node, info)
    methods['state_callback'](node, SimpleNamespace(data='COLLISION_AVOIDING'))
    assert completed == ['interrupted']  # releases the suspended home lease
    methods['state_callback'](node, SimpleNamespace(data='RETURNING_HOME'))
    methods['state_info_callback'](node, info)
    assert node.home_sequence is None
    info.requested_by = 'home_return:new-intent'
    methods['state_info_callback'](node, info)
    assert node.home_sequence is not None


def test_stale_home_completion_cannot_release_a_replacement_home_lease():
    from luxo_behaviors.state_machine import StateTransitionPolicy, LuxoState
    decision = StateTransitionPolicy({}).decide(
        current_state=LuxoState.RETURNING_HOME, current_requester='home_return:new',
        current_priority=50, requested_state=LuxoState.IDLE,
        requesting_node='home_return:old', priority=50, completion=True)
    assert not decision['accepted']
    assert decision['reason'] == 'completion_owner_mismatch'
