import pytest

from luxo_behaviors.simulator_protocol import (
    REQUIRED_GRAPH_COMPONENTS,
    summarize_simulator_health,
    valid_joint_feedback,
    MANUAL_JOINT_LIMITS,
)


def healthy_snapshot():
    return {
        "graph_nodes": list(REQUIRED_GRAPH_COMPONENTS),
        "state": "IDLE",
        "joint_names": list(MANUAL_JOINT_LIMITS),
        "positions": [0.0] * 4,
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


@pytest.mark.parametrize("state", ["ERROR", "SHUTDOWN", "INITIALIZING", "bogus", None])
def test_fresh_faulted_or_unready_state_is_not_healthy(state):
    snapshot = healthy_snapshot()
    snapshot["state"] = state
    health = summarize_simulator_health(snapshot, 10.0)
    assert not health["healthy"]
    assert "state_not_ready" in health["reasons"]


@pytest.mark.parametrize("positions", [[0.0], [0.0, 0.0, float("nan"), 0.0],
                                       [0.0, float("inf"), 0.0, 0.0],
                                       [100.0, 0.0, 0.0, 0.0],
                                       [False, 0.0, 0.0, 0.0]])
def test_malformed_feedback_does_not_report_healthy(positions):
    snapshot = healthy_snapshot()
    snapshot["positions"] = positions
    health = summarize_simulator_health(snapshot, 10.0)
    assert not health["healthy"]
    assert "invalid_joint_feedback" in health["reasons"]


def test_rejected_feedback_remains_unhealthy_until_valid_feedback_arrives():
    snapshot = healthy_snapshot()
    snapshot["_joint_feedback_valid"] = False
    assert not summarize_simulator_health(snapshot, 10.0)["healthy"]
    snapshot["_joint_feedback_valid"] = True
    assert summarize_simulator_health(snapshot, 10.0)["healthy"]


def test_joint_feedback_rejects_duplicate_names_and_accepts_reordered_complete_pose():
    names = list(MANUAL_JOINT_LIMITS)
    assert not valid_joint_feedback([names[0]] * 4, [0.0] * 4)
    assert valid_joint_feedback(list(reversed(names)), [0.0] * 4)
