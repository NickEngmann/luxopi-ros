"""Execute the real ROS dispatch method without loading hardware/ROS drivers."""

import ast
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from luxo_behaviors.conversation_transport import SimulatedConversation


def dispatcher():
    path = Path(__file__).resolve().parents[1] / "luxo_behaviors/speech_bridge.py"
    tree = ast.parse(path.read_text())
    method = next(item for node in tree.body if isinstance(node, ast.ClassDef)
                  for item in node.body if isinstance(item, ast.FunctionDef) and item.name == "_dispatch_intent")
    namespace = dict(math=math, json=json, SimulatedConversation=SimulatedConversation,
                     String=SimpleNamespace, Bool=SimpleNamespace)
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
    output = []
    node = SimpleNamespace()
    for name in ("animations", "light_control", "brightness_control", "color_control", "color_temp_control", "music_request"):
        setattr(node, name, SimpleNamespace(publish=lambda msg, topic=name: output.append((topic, msg.data))))
    return lambda intent: namespace["_dispatch_intent"](node, intent), output


@pytest.mark.parametrize("intent", [
    {"kind": "brightness", "value": float("nan")}, {"kind": "brightness", "value": 2},
    {"kind": "brightness", "value": True}, {"kind": "light", "value": "on"},
    {"kind": "color", "value": []}, {"kind": [], "value": "dance"},
    {"kind": "animation", "value": "sudo reboot"}, None,
])
def test_malformed_or_out_of_range_intent_never_reaches_controls(intent):
    dispatch, output = dispatcher()
    assert dispatch(intent) is False
    assert output == []


def test_explicit_animation_and_lighting_intents_reach_existing_topic_formats():
    dispatch, output = dispatcher()
    for kind, value in [("animation", "dance"), ("light", True), ("brightness", 0.5), ("color", "purple"), ("color_temp", 1.0)]:
        assert dispatch({"kind": kind, "value": value})
    assert output == [
        ("animations", "dance"), ("light_control", True), ("brightness_control", "brightness:0.5"),
        ("color_control", "color:purple"), ("color_temp_control", "color_temp:1.0"),
    ]


def test_music_intent_is_forwarded_as_bounded_json_to_optional_adapter():
    dispatch, output = dispatcher()
    assert dispatch({"kind": "music", "value": {"operation": "play_media", "query": "jazz piano"}})
    assert output == [("music_request", '{"operation": "play_media", "query": "jazz piano"}')]
    assert not dispatch({"kind": "music", "value": {"operation": "shutdown"}})
