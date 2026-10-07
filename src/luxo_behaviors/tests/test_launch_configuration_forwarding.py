"""Catch launch-layer arguments declared but not forwarded into the shared graph."""

import ast
from pathlib import Path


def test_physics_launch_forwards_synthetic_autonomy_controls():
    source = Path(__file__).parents[1] / "launch" / "physics_simulator.launch.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    forwarded = set()
    declared = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "DeclareLaunchArgument" and node.args:
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    declared.add(node.args[0].value)
            if node.func.id == "IncludeLaunchDescription":
                for keyword in node.keywords:
                    if keyword.arg == "launch_arguments" and isinstance(keyword.value, ast.Call):
                        mapping = keyword.value.func.value if isinstance(keyword.value.func, ast.Attribute) else None
                        if isinstance(mapping, ast.Dict):
                            for key in mapping.keys:
                                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                                    forwarded.add(key.value)
    expected = {"enable_sim_autonomy", "sim_idle_after", "sim_idle_interval", "sim_emotion_interval"}
    assert expected <= declared
    assert expected <= forwarded, f"physics launch dropped shared graph arguments: {expected - forwarded}"


def test_sim_activity_parameters_are_explicitly_float_typed():
    source = Path(__file__).parents[1] / "launch" / "luxo_system.launch.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    typed = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "ParameterValue":
            continue
        if (node.args and isinstance(node.args[0], ast.Call)
                and isinstance(node.args[0].func, ast.Name)
                and node.args[0].func.id == "LaunchConfiguration"
                and node.args[0].args and isinstance(node.args[0].args[0], ast.Constant)):
            if any(keyword.arg == "value_type" and isinstance(keyword.value, ast.Name)
                   and keyword.value.id == "float" for keyword in node.keywords):
                typed.add(node.args[0].args[0].value)
    assert {"sim_idle_after", "sim_idle_interval", "sim_emotion_interval"} <= typed


def test_robot_launch_connects_real_ai_events_and_excludes_sim_fixtures():
    source = Path(__file__).parents[1] / "launch" / "robot_stack.launch.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    mappings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "IncludeLaunchDescription":
            continue
        for keyword in node.keywords:
            value = keyword.value
            if keyword.arg == "launch_arguments" and isinstance(value, ast.Call):
                mapping = value.func.value if isinstance(value.func, ast.Attribute) else None
                if isinstance(mapping, ast.Dict):
                    mappings.append({key.value: val for key, val in zip(mapping.keys, mapping.values)
                                     if isinstance(key, ast.Constant)})
    assert len(mappings) == 1
    arguments = mappings[0]
    assert {"use_hardware", "enable_speech_bridge", "speech_event_socket",
            "enable_smart_home_bridge"} <= arguments.keys()
    for fixture in ("enable_simulator_dashboard", "enable_sim_sensors",
                    "enable_sim_vision", "enable_sim_interactions",
                    "enable_sim_autonomy"):
        assert isinstance(arguments[fixture], ast.Constant)
        assert arguments[fixture].value == "false"
