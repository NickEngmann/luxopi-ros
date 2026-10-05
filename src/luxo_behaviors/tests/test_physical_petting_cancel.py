"""Exercise physical petting cancellation callbacks without hardware/ROS."""

import ast
import pathlib
from types import SimpleNamespace

from luxo_behaviors.state_machine import LuxoState


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "luxo_behaviors" / "petting_behavior.py"
METHODS = {
    "_stop_petting_session",
    "_petting_animation_goal_response_callback",
    "_petting_animation_result_callback",
}


class Deferred:
    def __init__(self, value=None):
        self.callback = None
        self.value = value

    def add_done_callback(self, callback):
        self.callback = callback


class GoalHandle:
    accepted = True

    def __init__(self):
        self.cancelled = 0
        self.result = Deferred()

    def cancel_goal_async(self):
        self.cancelled += 1
        return Deferred()

    def get_result_async(self):
        return self.result


def make_behavior():
    tree = ast.parse(SOURCE.read_text())
    klass = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name == "PettingBehavior")
    methods = [node for node in klass.body if isinstance(node, ast.FunctionDef)
               and node.name in METHODS]
    namespace = {"LuxoState": LuxoState}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(SOURCE), "exec"), namespace)
    behavior = SimpleNamespace(
        petting_active=False,
        petting_session_generation=2,
        petting_animation_active=True,
        petting_animation_goal_handle=None,
        petting_goal_generation=1,
        petting_cancel_requested=False,
        node=SimpleNamespace(get_logger=lambda: SimpleNamespace(info=lambda *_: None)),
        _check_petting_state_transition=lambda: None,
    )
    for name in METHODS:
        setattr(behavior, name, namespace[name].__get__(behavior))
    return behavior


def test_release_cancels_owned_physical_goal():
    behavior = make_behavior()
    handle = GoalHandle()
    behavior.petting_active = True
    behavior.petting_animation_goal_handle = handle

    behavior._stop_petting_session()

    assert not behavior.petting_active
    assert behavior.petting_session_generation == 3
    assert behavior.petting_cancel_requested
    assert handle.cancelled == 1


def test_goal_accepted_after_release_is_canceled_immediately():
    behavior = make_behavior()
    handle = GoalHandle()

    behavior._petting_animation_goal_response_callback(
        SimpleNamespace(result=lambda: handle), generation=1
    )

    assert handle.cancelled == 1
    assert handle.result.callback is not None


def test_old_physical_goal_result_cannot_clear_new_session_goal():
    behavior = make_behavior()
    current_handle = GoalHandle()
    behavior.petting_active = True
    behavior.petting_session_generation = 3
    behavior.petting_goal_generation = 3
    behavior.petting_animation_goal_handle = current_handle

    result = SimpleNamespace(status=5)
    behavior._petting_animation_result_callback(
        SimpleNamespace(result=lambda: result), generation=1
    )

    assert behavior.petting_animation_active
    assert behavior.petting_goal_generation == 3
    assert behavior.petting_animation_goal_handle is current_handle
