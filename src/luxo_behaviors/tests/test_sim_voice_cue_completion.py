"""Keep USER_CONTROL until an in-flight visual cue finishes its joint path."""

import ast
import pathlib
from types import SimpleNamespace


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "luxo_behaviors" / "sim_interaction_adapter.py"


def make_adapter():
    tree = ast.parse(SOURCE.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "SimInteractionAdapter")
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)
               and node.name in {"_finish_voice_state", "_voice_idle_result"}]
    namespace = {}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(SOURCE), "exec"), namespace)
    adapter = SimpleNamespace()
    for name in ("_finish_voice_state", "_voice_idle_result"):
        setattr(adapter, name, namespace[name].__get__(adapter))
    adapter.current_state = "USER_CONTROL"
    adapter.voice_session_owned = True
    adapter.voice_idle_pending = False
    adapter.primary_animation_active = False
    adapter.cue_active = True
    adapter.voice_generation = 7
    adapter.state_requests = []
    adapter._request_state = lambda *args: adapter.state_requests.append(args)
    adapter.last_error = ""
    return adapter


def test_idle_status_waits_for_active_cue_before_releasing_voice_state():
    adapter = make_adapter()

    adapter._finish_voice_state()
    assert adapter.state_requests == []
    assert not adapter.voice_idle_pending
    assert adapter.voice_session_owned

    adapter.cue_active = False
    adapter._finish_voice_state()
    assert adapter.voice_idle_pending
    assert len(adapter.state_requests) == 1
    state, requester, priority, completion, callback = adapter.state_requests[0]
    assert (state, requester, priority, completion) == ("IDLE", "user_control", 80, True)

    callback(True, "released after cue")
    assert not adapter.voice_session_owned
    assert not adapter.voice_idle_pending
    assert adapter.last_error == ""
