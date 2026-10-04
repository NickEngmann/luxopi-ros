"""Deterministic scenarios against the actual state manager, without ROS devices.

Only transport/LED imports are omitted. State manager methods are unmodified.
"""
import ast
import pathlib
import threading
import time
import typing
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'src/luxo_behaviors/luxo_behaviors'


def make_manager():
    state_globals = {}
    exec((PACKAGE / 'state_machine.py').read_text(), state_globals)
    state = state_globals['LuxoState']
    tree = ast.parse((PACKAGE / 'state_manager_node.py').read_text())
    manager_class = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    class Logger:
        def __getattr__(self, name):
            return lambda *args: None
    class Node:
        def __init__(self, name):
            pass
        def get_logger(self):
            return Logger()
        def __getattr__(self, name):
            if name.startswith('create_'):
                return lambda *args, **kwargs: SimpleNamespace(publish=lambda msg: None)
            raise AttributeError(name)
    namespace = dict(vars(typing), Node=Node, threading=threading, time=time,
                     LuxoState=state, StateTransition=state_globals['StateTransition'],
                     QoSProfile=lambda **kw: kw,
                     QoSReliabilityPolicy=SimpleNamespace(RELIABLE=1),
                     QoSHistoryPolicy=SimpleNamespace(KEEP_LAST=1))
    for name in ('Bool', 'String', 'Header', 'Twist', 'DiagnosticArray',
                 'DiagnosticStatus', 'KeyValue', 'StateInfo', 'RequestStateTransition'):
        namespace[name] = SimpleNamespace
    exec(compile(ast.Module(body=[manager_class], type_ignores=[]), 'state_manager_node.py', 'exec'), namespace)
    manager = namespace['StateManagerNode']()
    return manager, state


def test_startup_and_all_advertised_states():
    manager, state = make_manager()
    assert manager.current_state == state.INITIALIZING
    manager._state_start_time -= 16
    manager.update()
    assert manager.current_state == state.IDLE
    # Each explicit entry is accompanied by recovery or terminal shutdown.
    for target in state:
        if target in (state.IDLE, state.INITIALIZING, state.SHUTDOWN):
            continue
        assert manager.transition_to(target, force=True)
        assert manager.current_state == target
        assert manager.transition_to(state.IDLE, force=True)
    assert manager.transition_to(state.SHUTDOWN)
    assert not manager.transition_to(state.IDLE)


def test_voice_heard_response_and_completion():
    manager, state = make_manager()
    manager.transition_to(state.IDLE)
    assert manager.request_state_transition(state.VOICE_FOLLOWING, 'voice_following', 75)
    assert manager.request_state_transition(state.USER_CONTROL, 'user_control', 80)
    assert manager.request_state_transition(state.ANIMATING, 'user_control', 80)
    assert manager.request_state_transition(state.IDLE, 'animation_command', 30, is_completion=True)
    assert manager.current_state == state.IDLE


def test_priority_denial_does_not_record_failed_interrupt():
    manager, state = make_manager()
    manager.transition_to(state.IDLE)
    assert manager.request_state_transition(state.USER_CONTROL, 'user_control', 80)
    assert not manager.request_state_transition(state.ANIMATING, 'idle', 30)
    assert manager.current_state == state.USER_CONTROL
    assert state.ANIMATING not in manager._interrupted_states


def test_dance_collision_preemption_and_recovery():
    manager, state = make_manager()
    manager.transition_to(state.IDLE)
    assert manager.request_state_transition(state.ANIMATING, 'animation', 40)
    assert manager.request_state_transition(state.COLLISION_AVOIDING, 'behavior_coordinator', 100)
    assert not manager.request_state_transition(state.IDLE, 'idle', 30)
    assert manager.request_state_transition(state.IDLE, 'behavior_coordinator', 100, is_completion=True)
    assert manager.current_state == state.ANIMATING
    assert manager._last_state_requester == 'animation'
    assert manager._get_current_priority() == 40


def test_petting_interrupt_returns_to_previous_behavior():
    manager, state = make_manager()
    manager.transition_to(state.IDLE)
    assert manager.request_state_transition(state.ANIMATING, 'animation', 40)
    assert manager.request_state_transition(state.PETTING, 'petting', 60)
    assert manager.request_state_transition(state.IDLE, 'petting', 60, is_completion=True)
    assert manager.current_state == state.ANIMATING


def test_invalid_service_state_is_rejected():
    manager, state = make_manager()
    response = manager.handle_transition_request(SimpleNamespace(requested_state='not_a_state'), SimpleNamespace())
    assert not response.success
    assert response.current_state == 'INITIALIZING'


def test_failed_high_priority_invalid_transition_leaves_no_return_record():
    manager, state = make_manager()
    manager.transition_to(state.IDLE)
    manager.request_state_transition(state.USER_CONTROL, 'user_control', 80)
    assert not manager.request_state_transition(state.EMOTION_REACTING, 'emotion', 90)
    assert state.EMOTION_REACTING not in manager._interrupted_states


def test_animation_shortcut_cannot_override_collision_or_escape():
    manager, state = make_manager()
    manager.transition_to(state.IDLE)
    manager.request_state_transition(state.ANIMATING, 'animation', 40)
    manager.request_state_transition(state.COLLISION_AVOIDING, 'behavior_coordinator', 100)
    assert not manager.request_state_transition(state.IDLE, 'animation_command', 30)
    manager.request_state_transition(state.ESCAPE_MODE, 'behavior_coordinator', 100)
    assert not manager.request_state_transition(state.IDLE, 'animation_command', 50)
