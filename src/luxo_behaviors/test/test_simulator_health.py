import pytest

from luxo_behaviors.simulator_protocol import (
    REQUIRED_GRAPH_COMPONENTS,
    summarize_simulator_health,
)


def healthy_snapshot():
    return {
        "graph_nodes": list(REQUIRED_GRAPH_COMPONENTS),
        "_state_received_monotonic": 9.8,
        "_joints_received_monotonic": 9.9,
    }


def test_health_ok_when_all_required_nodes_and_fresh_telemetry_are_present():
    health = summarize_simulator_health(healthy_snapshot(), now_monotonic=10.0)
    assert health["healthy"] is True
    assert health["missing_required"] == []
    assert health["state_age_seconds"] == pytest.approx(0.2)
    assert health["joint_state_age_seconds"] == pytest.approx(0.1)


def test_health_fails_when_any_required_component_is_missing():
    snapshot = healthy_snapshot()
    snapshot["graph_nodes"].remove("sim_motion_controller")
    health = summarize_simulator_health(snapshot, now_monotonic=10.0)
    assert health["healthy"] is False
    assert health["missing_required"] == ["sim_motion_controller"]


def test_health_fails_when_state_or_joint_telemetry_is_stale_or_absent():
    snapshot = healthy_snapshot()
    snapshot["_state_received_monotonic"] = 6.9
    assert summarize_simulator_health(snapshot, 10.0)["state_fresh"] is False
    del snapshot["_state_received_monotonic"]
    del snapshot["_joints_received_monotonic"]
    health = summarize_simulator_health(snapshot, 10.0)
    assert health["healthy"] is False
    assert health["state_age_seconds"] is None
    assert health["joint_state_age_seconds"] is None


def test_physics_health_requires_actual_feedback_engine():
    snapshot = healthy_snapshot()
    snapshot['simulation_backend'] = 'mujoco'
    assert summarize_simulator_health(snapshot, 10)['missing_required'] == ['mujoco_simulator']
    snapshot['graph_nodes'].append('mujoco_simulator')
    assert summarize_simulator_health(snapshot, 10)['healthy']
