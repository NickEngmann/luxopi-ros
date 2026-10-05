"""Exercise actual simulator petting callbacks without ROS transport."""

import ast
import pathlib
from types import SimpleNamespace


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "luxo_behaviors" / "sim_interaction_adapter.py"
METHODS = {
    "_state_cb", "_petting_cb", "_request_petting_state", "_petting_transition_result",
    "_start_petting_animation", "_petting_goal_response", "_petting_goal_result",
    "_finish_petting_goal", "_finish_petting_if_ready", "_petting_idle_result",
    "_stop_petting_session",
}


class Deferred:
    def __init__(self):
        self.callback = None

    def add_done_callback(self, callback):
        self.callback = callback

    def resolve(self, value):
        assert self.callback is not None
        self.callback(SimpleNamespace(result=lambda: value))


class FakeGoalHandle:
    accepted = True

    def __init__(self):
        self.cancel_calls = 0
        self.result = Deferred()

    def cancel_goal_async(self):
        self.cancel_calls += 1
        return Deferred()

    def get_result_async(self):
        return self.result


class FakeActionClient:
    def __init__(self):
        self.sent = []

    def server_is_ready(self):
        return True

    def send_goal_async(self, goal):
        deferred = Deferred()
        self.sent.append((goal, deferred))
        return deferred


def make_adapter():
    tree = ast.parse(SOURCE.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "SimInteractionAdapter")
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)
               and node.name in METHODS]

    class Goal:
        pass

    PlayAnimation = SimpleNamespace(Goal=Goal)

    namespace = {
        "time": SimpleNamespace(monotonic=lambda: 100.0),
        "parse_petting_event": lambda value: (
            value.split(":")[0], int(value.split(":")[1])
        ),
        "PlayAnimation": PlayAnimation,
        "PETTING_ANIMATION": "folded_wiggle",
        "SAFETY_STATES": {"COLLISION_AVOIDING", "ESCAPE_MODE", "ERROR", "SHUTDOWN"},
    }
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(SOURCE), "exec"), namespace)
    adapter = SimpleNamespace()
    for name in METHODS:
        setattr(adapter, name, namespace[name].__get__(adapter))
    adapter.current_state = "PETTING"
    adapter.petting_active = True
    adapter.petting_transition_pending = False
    adapter.petting_transition_generation = None
    adapter.petting_session_owned = True
    adapter.petting_idle_pending = False
    adapter.last_petting_event = None
    adapter.petting_goal_handle = None
    adapter.petting_goal_generation = None
    adapter.petting_goal_pending = False
    adapter.petting_animation_active = False
    adapter.petting_generation = 1
    adapter.petting_cancel_requested = False
    adapter.last_error = ""
    adapter.animation_client = FakeActionClient()
    adapter.state_requests = []
    adapter._request_state = lambda *args: adapter.state_requests.append(args)
    adapter._publish_status = lambda: None
    return adapter


def started_event():
    return SimpleNamespace(data="petting_started:80")


def stopped_event():
    return SimpleNamespace(data="petting_stopped:0")


def cancel_result():
    return SimpleNamespace(
        status=5,
        result=SimpleNamespace(success=False, message="goal canceled"),
    )


def test_release_cancels_active_goal_and_returns_to_idle_without_error():
    adapter = make_adapter()
    handle = FakeGoalHandle()
    adapter.petting_goal_handle = handle
    adapter.petting_goal_generation = 1
    adapter.petting_animation_active = True

    adapter._petting_cb(stopped_event())
    assert handle.cancel_calls == 1
    assert adapter.petting_animation_active
    assert not adapter.state_requests

    adapter._petting_goal_result(1, SimpleNamespace(result=lambda: cancel_result()))
    assert not adapter.petting_animation_active
    assert adapter.state_requests[0][0] == "IDLE"
    assert adapter.last_error == ""

    idle_callback = adapter.state_requests[0][-1]
    idle_callback(True, "returned to idle")
    assert not adapter.petting_session_owned


def test_timeout_uses_same_cancel_path_as_explicit_release():
    adapter = make_adapter()
    handle = FakeGoalHandle()
    adapter.petting_goal_handle = handle
    adapter.petting_goal_generation = 1
    adapter.petting_animation_active = True

    adapter._stop_petting_session()
    assert not adapter.petting_active
    assert adapter.petting_generation == 2
    assert handle.cancel_calls == 1
    assert adapter.petting_animation_active


def test_release_before_goal_acceptance_cancels_as_soon_as_handle_arrives():
    adapter = make_adapter()
    adapter.petting_goal_generation = 1
    adapter.petting_goal_pending = True
    adapter.petting_animation_active = True
    handle = FakeGoalHandle()

    adapter._petting_cb(stopped_event())
    assert not adapter.state_requests
    adapter._petting_goal_response(1, SimpleNamespace(result=lambda: handle))
    assert handle.cancel_calls == 1
    handle.result.resolve(cancel_result())

    assert adapter.state_requests[0][0] == "IDLE"
    assert adapter.last_error == ""


def test_release_before_state_grant_completes_after_grant_arrives():
    adapter = make_adapter()
    adapter.current_state = "IDLE"
    adapter.petting_transition_pending = True
    adapter.petting_transition_generation = 1

    adapter._petting_cb(stopped_event())
    adapter._petting_transition_result(1, True, "granted")
    assert not adapter.state_requests  # state topic has not caught up yet

    adapter._state_cb(SimpleNamespace(data="PETTING"))
    assert adapter.state_requests[0][0] == "IDLE"
    assert not adapter.petting_animation_active


def test_old_goal_completion_does_not_clear_a_new_petting_session():
    adapter = make_adapter()
    old_handle = FakeGoalHandle()
    adapter.petting_goal_handle = old_handle
    adapter.petting_goal_generation = 1
    adapter.petting_animation_active = True

    adapter._petting_cb(stopped_event())
    adapter._petting_cb(started_event())
    assert adapter.petting_active
    assert adapter.petting_generation == 3

    adapter._petting_goal_result(1, SimpleNamespace(result=lambda: cancel_result()))
    assert adapter.petting_active
    assert adapter.petting_animation_active
    assert adapter.petting_goal_pending
    assert len(adapter.animation_client.sent) == 1
    assert not adapter.state_requests
