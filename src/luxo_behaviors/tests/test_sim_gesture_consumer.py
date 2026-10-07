"""Test the simulation gesture callback's real action-routing methods offline."""

import ast
import pathlib
from types import SimpleNamespace

from luxo_behaviors.sim_gesture_rules import GESTURE_ANIMATIONS, gesture_block_reason


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "luxo_behaviors" / "sim_interaction_adapter.py"
METHODS = {
    "_gesture_cb", "_gesture_goal_response", "_gesture_goal_result",
    "_finish_gesture_goal", "_cancel_gesture_animation",
}


class Deferred:
    def __init__(self):
        self.callback = None

    def add_done_callback(self, callback):
        self.callback = callback

    def resolve(self, value):
        assert self.callback is not None
        self.callback(SimpleNamespace(result=lambda: value))


class GoalHandle:
    accepted = True

    def __init__(self):
        self.cancel_calls = 0
        self.result = Deferred()

    def get_result_async(self):
        return self.result

    def cancel_goal_async(self):
        self.cancel_calls += 1
        return Deferred()


class ActionClient:
    def __init__(self):
        self.sent = []

    def server_is_ready(self):
        return True

    def send_goal_async(self, goal):
        response = Deferred()
        self.sent.append((goal, response))
        return response


def make_adapter(clock):
    tree = ast.parse(SOURCE.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "SimInteractionAdapter")
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)
               and node.name in METHODS]

    class Goal:
        pass

    namespace = {
        "time": SimpleNamespace(monotonic=lambda: clock[0]),
        "PlayAnimation": SimpleNamespace(Goal=Goal),
        "GESTURE_ANIMATIONS": GESTURE_ANIMATIONS,
        "gesture_block_reason": gesture_block_reason,
        "normalize_gesture": lambda value: (
            value.strip().lower() if isinstance(value, str)
            and value.strip().lower() in GESTURE_ANIMATIONS else None
        ),
    }
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(SOURCE), "exec"), namespace)
    adapter = SimpleNamespace()
    for name in METHODS:
        setattr(adapter, name, namespace[name].__get__(adapter))
    adapter.current_state = "IDLE"
    adapter.voice_status = "idle"
    adapter.primary_animation_active = False
    adapter.cue_active = False
    adapter.petting_active = False
    adapter.gesture_animation_active = False
    adapter.gesture_goal_pending = False
    adapter.gesture_generation = 0
    adapter.gesture_goal_handle = None
    adapter.gesture_last_started_at = 0.0
    adapter.last_gesture = ""
    adapter.gesture_animation = ""
    adapter.gesture_status = "idle"
    adapter.gesture_error = ""
    adapter.gesture_last_ignored = ""
    adapter.animation_client = ActionClient()
    adapter._publish_status = lambda: None
    return adapter


def test_swipe_is_routed_into_a_validated_animation_action():
    adapter = make_adapter([100.0])
    adapter._gesture_cb(SimpleNamespace(data="LEFT"))

    assert len(adapter.animation_client.sent) == 1
    goal, response = adapter.animation_client.sent[0]
    assert goal.animation_name == "look_around_casual"
    assert goal.speed_multiplier == 1.5
    assert goal.allow_interruption is False
    assert goal.use_hardware_feedback is False
    assert adapter.gesture_animation_active and adapter.gesture_goal_pending

    handle = GoalHandle()
    response.resolve(handle)
    assert adapter.gesture_goal_handle is handle
    assert not adapter.gesture_goal_pending
    handle.result.resolve(SimpleNamespace(
        status=4,
        result=SimpleNamespace(success=True, final_state="completed", message="done"),
    ))
    assert not adapter.gesture_animation_active
    assert adapter.gesture_status == "completed"


def test_unknown_busy_voice_safety_and_cooldown_inputs_do_not_start_actions():
    clock = [100.0]
    adapter = make_adapter(clock)
    adapter._gesture_cb(SimpleNamespace(data="diagonal"))
    assert adapter.animation_client.sent == []

    adapter.voice_status = "thinking"
    adapter._gesture_cb(SimpleNamespace(data="left"))
    assert adapter.animation_client.sent == []
    adapter.voice_status = "idle"
    adapter.current_state = "COLLISION_AVOIDING"
    adapter._gesture_cb(SimpleNamespace(data="right"))
    assert adapter.animation_client.sent == []

    adapter.current_state = "IDLE"
    adapter._gesture_cb(SimpleNamespace(data="up"))
    assert adapter.animation_client.sent[0][0].animation_name == "neck_stretch"
    clock[0] = 100.5
    adapter.gesture_animation_active = False
    adapter.gesture_goal_pending = False
    adapter._gesture_cb(SimpleNamespace(data="down"))
    assert len(adapter.animation_client.sent) == 1
    assert adapter.gesture_last_ignored == "down:cooldown"


def test_safety_state_cancels_owned_gesture_goal_without_clearing_future_goal():
    adapter = make_adapter([100.0])
    handle = GoalHandle()
    adapter.gesture_generation = 3
    adapter.gesture_goal_handle = handle
    adapter.gesture_animation_active = True
    adapter._cancel_gesture_animation("state:error")

    assert handle.cancel_calls == 1
    assert adapter.gesture_generation == 4
    assert not adapter.gesture_animation_active
    assert adapter.gesture_status == "preempted"
    assert adapter.gesture_error == "state:error"
