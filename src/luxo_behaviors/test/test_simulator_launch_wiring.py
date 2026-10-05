"""Regression tests for launch configuration passed into the dashboard."""

import importlib.util
from pathlib import Path

from launch import LaunchContext


def test_dashboard_receives_selected_simulation_backend():
    launch_file = Path(__file__).parents[1] / "launch/luxo_system.launch.py"
    spec = importlib.util.spec_from_file_location("luxo_system_launch", launch_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    context = LaunchContext()
    context.launch_configurations["simulation_backend"] = "mujoco"
    backend = module._simulator_dashboard_parameters()["simulation_backend"]

    assert context.perform_substitution(backend) == "mujoco"
