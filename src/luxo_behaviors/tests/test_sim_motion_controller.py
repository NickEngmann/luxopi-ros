import pytest

from luxo_behaviors.joint_motion import URDF_JOINT_LIMITS
from luxo_behaviors.joint_profiles import ROARM_M3_NAMES, ROARM_M3_LIMITS
from luxo_behaviors.sim_motion_rules import (
    motion_is_frozen, validate_manual_pose, validate_feedback,
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
