import math

import pytest

from luxo_behaviors.joint_motion import URDF_JOINT_LIMITS
from luxo_behaviors.joint_profiles import ROARM_M3_NAMES, ROARM_M3_LIMITS
from luxo_behaviors.motion_policy import (
    cable_safe_voice_yaw, nearest_cable_safe_angle, normalize_direction_degrees,
    voice_direction_is_fresh, voice_overlay_allowed, voice_state_request_allowed,
)
from luxo_behaviors.sim_motion_rules import (
    inactive_voice_reconcile_due, motion_is_frozen,
    validate_manual_pose, validate_feedback,
)


def test_directional_collision_warnings_are_delegated_to_avoidance_policy():
    assert not motion_is_frozen("IDLE", (False, True, False))


def test_motion_holds_for_safety_states_after_sensor_clears():
    for state in ("ESCAPE_MODE", "ERROR", "SHUTDOWN"):
        assert motion_is_frozen(state, (False, False, False))
    assert not motion_is_frozen("COLLISION_AVOIDING", (False, False, False))


def test_motion_remains_available_in_ordinary_states_without_collision():
    for state in ("IDLE", "VOICE_FOLLOWING", "ANIMATING", "PETTING"):
        assert not motion_is_frozen(state, (False, False, False))


def test_inactive_voice_state_is_reconciled_after_collision_completion_race():
    assert not inactive_voice_reconcile_due("VOICE_FOLLOWING", False, 10.0, None, 10.1)
    assert inactive_voice_reconcile_due("VOICE_FOLLOWING", False, 10.0, None, 10.3)
    assert not inactive_voice_reconcile_due("VOICE_FOLLOWING", False, 10.0, 10.3, 10.8)
    assert inactive_voice_reconcile_due("VOICE_FOLLOWING", False, 10.0, 10.3, 11.31)
    assert not inactive_voice_reconcile_due("VOICE_FOLLOWING", True, 10.0, None, 20.0)
    assert not inactive_voice_reconcile_due("IDLE", False, 10.0, None, 20.0)


@pytest.mark.parametrize(("current", "requested", "expected"), [
    (math.radians(179), math.radians(-179), math.pi),
    (math.radians(-179), math.radians(179), -math.pi),
    (0.0, math.radians(270), math.radians(-90)),
    (math.radians(30), math.radians(40), math.radians(40)),
])
def test_voice_yaw_uses_shortest_cable_safe_equivalent(current, requested, expected):
    actual = nearest_cable_safe_angle(current, requested, -math.pi, math.pi)
    assert actual == pytest.approx(expected)
    assert -math.pi <= actual <= math.pi
    assert abs(actual - current) <= math.pi


def test_robot_and_simulator_share_cable_safe_voice_heading_projection():
    assert cable_safe_voice_yaw(math.radians(170), 190, -math.pi, math.pi) == pytest.approx(math.pi)
    assert cable_safe_voice_yaw(math.radians(-170), 190, -math.pi, math.pi) == pytest.approx(
        math.radians(-170)
    )


def test_voice_yaw_rejects_invalid_current_angle_or_limits():
    with pytest.raises(ValueError, match="current yaw"):
        nearest_cable_safe_angle(4.0, 0.0, -math.pi, math.pi)
    with pytest.raises(ValueError, match="finite"):
        nearest_cable_safe_angle(0.0, float("nan"), -math.pi, math.pi)


@pytest.mark.parametrize(("angle", "expected"), [
    (0, 0), (181, -179), (-181, 179), (360, 0), (240, -120),
])
def test_direction_estimates_are_normalized_to_short_signed_turn(angle, expected):
    assert normalize_direction_degrees(angle) == pytest.approx(expected)


@pytest.mark.parametrize("angle", [float("nan"), float("inf"), -float("inf"), 361, -361, "bad"])
def test_invalid_direction_estimates_are_rejected(angle):
    with pytest.raises(ValueError):
        normalize_direction_degrees(angle)


def test_direction_lease_rejects_missing_stale_future_and_nonfinite_data():
    assert voice_direction_is_fresh(-45, 9.5, 10.0)
    assert not voice_direction_is_fresh(None, 9.5, 10.0)
    assert not voice_direction_is_fresh(-45, None, 10.0)
    assert not voice_direction_is_fresh(-45, 7.9, 10.0)
    assert not voice_direction_is_fresh(-45, 10.1, 10.0)
    assert not voice_direction_is_fresh(float("nan"), 9.9, 10.0)


def test_doa_overlays_ordinary_animation_without_taking_fsm_ownership():
    for state in ("ANIMATING", "PETTING", "EMOTION_REACTING"):
        assert voice_overlay_allowed(state)
        assert not voice_state_request_allowed(state)
    assert voice_overlay_allowed("VOICE_FOLLOWING")
    assert voice_state_request_allowed("IDLE")
    assert voice_state_request_allowed("VOICE_FOLLOWING")
    for state in ("COLLISION_AVOIDING", "ESCAPE_MODE", "RETURNING_HOME", "USER_CONTROL", "ERROR"):
        assert not voice_overlay_allowed(state)
        assert not voice_state_request_allowed(state)


def test_manual_pose_requires_user_control_state():
    names = tuple(URDF_JOINT_LIMITS)
    with pytest.raises(ValueError, match="USER_CONTROL"):
        validate_manual_pose("IDLE", names, [0.0] * len(names))


def test_manual_pose_requires_exact_unique_joint_set_and_finite_values():
    names = tuple(URDF_JOINT_LIMITS)
    with pytest.raises(ValueError, match="each expected joint"):
        validate_manual_pose("USER_CONTROL", names[:-1], [0.0] * (len(names) - 1))
    duplicate_names = (names[0], names[0], names[2], names[3])
    with pytest.raises(ValueError, match="duplicate"):
        validate_manual_pose("USER_CONTROL", duplicate_names, [0.0] * len(names))
    with pytest.raises(ValueError, match="non-finite"):
        validate_manual_pose("USER_CONTROL", names, [0.0, 0.0, float("nan"), 0.0])


def test_manual_pose_clamps_each_joint_to_checked_in_urdf_bounds():
    names = tuple(URDF_JOINT_LIMITS)
    raw = [99.0, -99.0, 99.0, -99.0]
    actual = validate_manual_pose("USER_CONTROL", names, raw)
    expected = [
        URDF_JOINT_LIMITS[name][1 if value > 0 else 0]
        for name, value in zip(names, raw)
    ]
    assert actual == pytest.approx(expected)


def test_manual_m3_pose_uses_exact_six_axis_vendor_names_and_limits():
    raw = [99.0, -99.0, 99.0, -99.0, 99.0, 99.0]
    actual = validate_manual_pose("USER_CONTROL", ROARM_M3_NAMES, raw, "roarm_m3")
    expected = [ROARM_M3_LIMITS[name][1 if value > 0 else 0]
                for name, value in zip(ROARM_M3_NAMES, raw)]
    assert actual == pytest.approx(expected)


def test_manual_m3_pose_rejects_legacy_four_axis_names():
    names = tuple(URDF_JOINT_LIMITS)
    with pytest.raises(ValueError, match="each expected joint"):
        validate_manual_pose("USER_CONTROL", names, [0.0] * len(names), "roarm_m3")


def test_physics_feedback_is_validated_separately_from_command_trajectory():
    positions, velocities = validate_feedback(
        ROARM_M3_NAMES, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        [0.1, -0.2, 0.3, -0.4, 0.5, -0.6], "roarm_m3",
    )
    assert positions == pytest.approx([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    assert velocities == pytest.approx([0.1, -0.2, 0.3, -0.4, 0.5, -0.6])


def test_physics_feedback_rejects_malformed_nonfinite_velocity():
    with pytest.raises(ValueError, match="finite"):
        validate_feedback(
            ROARM_M3_NAMES, [0.0] * 6, [0.0, 0.0, float("nan"), 0.0, 0.0, 0.0],
            "roarm_m3",
        )
