import pytest

from luxo_behaviors.reactive_avoidance import ReactiveAvoidance
from luxo_behaviors.joint_profiles import ROARM_M3_NAMES, ROARM_M3_LIMITS


def policy(retreats=None):
    return ReactiveAvoidance(
        limits=ROARM_M3_LIMITS,
        retreats=retreats,
        escape_step=0.08,
        stale_after=0.5,
        clear_dwell=0.25,
    )


def warn(motion, direction, now, *, severity="warning", valid=True):
    motion.update_sensor(direction, True, now, severity=severity, valid=valid)


def clear(motion, direction, now, *, valid=True):
    motion.update_sensor(direction, False, now, severity="safe", valid=valid)


def decision(motion, current, requested, now, received=None):
    return motion.adjust_target(
        current, requested, ROARM_M3_NAMES, now=now,
        target_received_at=received,
    )


def test_left_warning_redirects_toward_configured_retreat_within_joint_limits():
    motion = policy()
    current = [0.0, 0.0, 0.5, 0.0, 0.0, 0.0]
    warn(motion, "left", 1.0)
    requested = [-0.4, 0.1, 0.7, 0.0, 0.0, 0.0]  # legacy leftward yaw
    result = decision(motion, current, requested, 1.01)
    assert result["mode"] == "adjust"
    assert result["target"][0] == pytest.approx(0.08)
    assert result["target"][0] >= current[0]
    assert all(ROARM_M3_LIMITS[name][0] <= value <= ROARM_M3_LIMITS[name][1]
               for name, value in zip(ROARM_M3_NAMES, result["target"]))
    assert result["target"][2] == pytest.approx(current[2])
    assert result["target"][1] == pytest.approx(current[1])
    assert result["target"][4:] == current[4:]


def test_right_and_front_warning_use_their_configured_axes():
    current = [0.0, 0.2, 0.5, 0.0, 0.0, 0.0]
    motion = policy()
    warn(motion, "right", 1.0)
    result = decision(motion, current, [0.4, 0.2, 0.5, 0.0, 0.0, 0.0], 1.01)
    assert result["target"][0] == pytest.approx(-0.08)

    motion = policy()
    warn(motion, "front", 1.0)
    result = decision(motion, current, [0.0, -0.4, 0.5, 0.0, 0.0, 0.0], 1.01)
    assert result["target"][1] == pytest.approx(0.28)


def test_front_warning_holds_unmapped_axes_instead_of_extending_toward_sensor():
    current = [0.0, 0.2, 0.5, 0.1, -0.2, 0.0]
    motion = policy()
    warn(motion, "front", 1.0)
    # The requested extension/wrist/roll motion is not geometrically certified.
    result = decision(motion, current, [0.0, -0.4, 0.7, 0.5, 0.8, 1.0], 1.01)
    assert result["mode"] == "adjust"
    assert result["target"] == pytest.approx([0.0, 0.28, 0.5, 0.1, -0.2, 0.0])


def test_reversed_calibration_is_used_and_empty_calibration_holds():
    current = [0.0, 0.2, 0.5, 0.0, 0.0, 0.0]
    reversed_motion = policy({"left": {"axis": "base", "sign": -1}})
    warn(reversed_motion, "left", 1.0)
    result = decision(reversed_motion, current, [0.4, 0.2, 0.5, 0.0, 0.0, 0.0], 1.01)
    assert result["target"][0] == pytest.approx(-0.08)

    unconfigured = policy({})
    warn(unconfigured, "left", 1.0)
    result = decision(unconfigured, current, [-0.4, 0.2, 0.5, 0.0, 0.0, 0.0], 1.01)
    assert result["mode"] == "hold_unconfigured"
    assert result["target"] == current


def test_imminent_contact_and_conflicting_sides_hold_current_pose():
    current = [0.0, 0.2, 0.5, 0.0, 0.0, 0.0]
    motion = policy()
    warn(motion, "front", 1.0, severity="danger")
    result = decision(motion, current, [0.0, -0.3, 0.5, 0.0, 0.0, 0.0], 1.01)
    assert result["mode"] == "hold_imminent"
    assert result["target"] == current

    motion = policy()
    warn(motion, "left", 1.0)
    warn(motion, "right", 1.0)
    result = decision(motion, current, [0.1, 0.2, 0.5, 0.0, 0.0, 0.0], 1.01)
    assert result["mode"] == "hold_blocked"
    assert result["target"] == current


def test_contact_holds_all_direct_commands_until_fresh_release_and_new_target():
    motion = policy()
    current = [0.0, 0.2, 0.5, 0.0, 0.0, 0.0]
    warn(motion, "front", 1.0, severity="contact", valid=False)
    result = decision(motion, current, [0.0, 0.5, 0.8, 0.2, 0.4, 0.0], 1.01)
    assert result["mode"] == "hold_stale"
    assert result["target"] == current

    clear(motion, "front", 1.1, valid=False)  # another sensor cannot clear FSR
    result = decision(motion, current, [0.0, 0.5, 0.8, 0.2, 0.4, 0.0], 1.2)
    assert result["mode"] == "hold_stale"

    clear(motion, "front", 1.3, valid=True)  # fresh FSR release and valid range
    result = decision(motion, current, [0.0, 0.5, 0.8, 0.2, 0.4, 0.0], 1.6, received=1.55)
    assert result["mode"] == "hold_replan"
    result = decision(motion, current, [0.0, 0.5, 0.8, 0.2, 0.4, 0.0], 1.6, received=1.56)
    assert result["mode"] == "clear"


def test_joint_limit_without_escape_room_holds_instead_of_claiming_adjustment():
    motion = policy()
    current = [ROARM_M3_LIMITS[ROARM_M3_NAMES[0]][1], 0.2, 0.5, 0.0, 0.0, 0.0]
    warn(motion, "left", 1.0)
    result = decision(motion, current, [current[0] - 0.4, *current[1:]], 1.01)
    assert result["mode"] == "hold_no_safe_projection"
    assert result["target"] == current


def test_invalid_and_stale_sensor_after_warning_never_resume_as_clear():
    motion = policy()
    current = [0.0, 0.2, 0.5, 0.0, 0.0, 0.0]
    warn(motion, "left", 1.0)
    # Classifier timeout emits inactive but invalid: it must keep the hazard latched.
    clear(motion, "left", 1.1, valid=False)
    result = decision(motion, current, [0.2, *current[1:]], 1.2)
    assert result["mode"] == "hold_stale"
    assert result["target"] == current

    # Even silence after a warning becomes unknown coverage, not a clear.
    result = decision(motion, current, [0.2, *current[1:]], 2.0)
    assert result["mode"] == "hold_stale"

    clear(motion, "left", 2.01, valid=True)
    result = decision(motion, current, [0.2, *current[1:]], 2.1, received=2.05)
    assert result["mode"] == "adjust"
    result = decision(motion, current, [0.2, *current[1:]], 2.4, received=2.05)
    assert result["mode"] == "hold_replan"
    result = decision(motion, current, [0.2, *current[1:]], 2.4, received=2.35)
    assert result["mode"] == "clear"


def test_clear_hysteresis_requires_a_fresh_post_clear_target():
    motion = policy()
    current = [0.0, 0.2, 0.5, 0.0, 0.0, 0.0]
    warn(motion, "left", 1.0)
    clear(motion, "left", 1.1)
    result = decision(motion, current, [0.2, *current[1:]], 1.2, received=1.15)
    assert result["mode"] == "adjust"  # still executing only the retreat vector
    result = decision(motion, current, [0.2, *current[1:]], 1.4, received=1.15)
    assert result["mode"] == "hold_replan"  # old keyframe cannot resume
    result = decision(motion, current, [0.2, *current[1:]], 1.4, received=1.35)
    assert result["mode"] == "hold_replan"  # equal to the clear edge is not fresh
    result = decision(motion, current, [0.2, *current[1:]], 1.4, received=1.36)
    assert result["mode"] == "clear"


@pytest.mark.parametrize("retreats", [
    {"left": {"axis": "shoulder", "sign": 1}},
    {"left": {"axis": "base", "sign": 0}},
    {"unknown": {"axis": "base", "sign": 1}},
])
def test_invalid_retreat_configuration_is_rejected(retreats):
    with pytest.raises(ValueError):
        policy(retreats)
