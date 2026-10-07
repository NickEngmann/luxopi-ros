"""Regression tests for launch configuration passed into the dashboard."""

import importlib.util
from pathlib import Path

from launch import LaunchContext
from launch.substitutions import LaunchConfiguration
from luxo_behaviors.launch_options import continuous_timing_default


def test_dashboard_receives_selected_simulation_backend():
    launch_file = Path(__file__).parents[1] / "launch/luxo_system.launch.py"
    spec = importlib.util.spec_from_file_location("luxo_system_launch", launch_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    context = LaunchContext()
    context.launch_configurations["simulation_backend"] = "mujoco"
    backend = module._simulator_dashboard_parameters()["simulation_backend"]

    assert context.perform_substitution(backend) == "mujoco"


def test_continuous_timing_defaults_on_only_for_simulation():
    context = LaunchContext()
    timing_default = continuous_timing_default(LaunchConfiguration("use_hardware"))

    context.launch_configurations["use_hardware"] = "false"
    assert context.perform_substitution(timing_default) == "true"

    context.launch_configurations["use_hardware"] = "true"
    assert context.perform_substitution(timing_default) == "false"


def test_all_simulator_launch_paths_use_the_shared_default():
    package = Path(__file__).parents[1]
    system_source = (package / "launch/luxo_system.launch.py").read_text()
    physics_source = (package / "launch/physics_simulator.launch.py").read_text()
    compose_source = (package.parents[1] / "compose.simulator.yml").read_text()
    entrypoint_source = (package.parents[1] / "docker/simulator-entrypoint.sh").read_text()

    assert "default_value=continuous_timing_default(use_hardware)" in system_source
    assert 'continuous_timing_default(LaunchConfiguration("use_hardware"))' in physics_source
    assert 'LUXOPI_CONTINUOUS_ANIMATION_TIMING:-true' in compose_source
    assert 'LUXOPI_CONTINUOUS_ANIMATION_TIMING:-true' in entrypoint_source
    # The hardware launch node receives neither simulation-only retiming flag.
    hardware_block = system_source.split("hardware_animation_node = Node(", 1)[1].split(
        "# Animation command node (simulation version)", 1
    )[0]
    assert "enable_feasible_retiming" not in hardware_block
    assert "enable_continuous_retiming" not in hardware_block
