import pytest

from luxo_behaviors.joint_profiles import (
    ANIMATION_ROLL_LIMIT,
    ROARM_M3_LIMITS,
    ROARM_M3_NAMES,
    URDF4_NAMES,
    animation_pose_for_profile,
    joint_profile,
    pose_to_animation_positions,
)


def test_default_profile_preserves_existing_four_axis_urdf_mapping():
    names, pose = animation_pose_for_profile([0.1, -0.2, 0.3, 0.4, -1.2, 25.0], "urdf4")
    assert names == URDF4_NAMES
    assert pose == pytest.approx([0.1, -0.2, 0.3, 0.4])


def test_m3_profile_maps_roll_and_holds_current_gripper_without_acceleration():
    names, pose = animation_pose_for_profile(
        [0.1, -0.2, 0.3, 0.4, -1.2, 25.0], "roarm_m3", gripper_position=0.7
    )
    assert names == ROARM_M3_NAMES
    assert pose == pytest.approx([0.1, -0.2, 0.3, 0.4, -1.2, 0.7])


def test_m3_animation_roll_retains_the_existing_conservative_range():
    names, pose = animation_pose_for_profile(
        [0.0, 0.0, 0.0, 0.0, -3.0, 12.0], "roarm_m3"
    )
    assert names == ROARM_M3_NAMES
    assert pose[4] == pytest.approx(ANIMATION_ROLL_LIMIT[0])
    assert pose[5] == pytest.approx(0.0)


def test_profile_limits_are_vendored_m3_bounds_and_invalid_profile_rejects():
    names, limits = joint_profile("m3")
    assert names == ROARM_M3_NAMES
    assert limits == ROARM_M3_LIMITS
    with pytest.raises(ValueError, match="unsupported joint profile"):
        joint_profile("unknown")


def test_animation_acceleration_metadata_is_finite_but_not_a_joint_axis():
    names, pose = animation_pose_for_profile(
        [0.1, -0.2, 0.3, 0.4, -1.2, 25.0], "urdf4"
    )
    assert len(names) == len(pose) == 4
    with pytest.raises(ValueError, match="finite"):
        animation_pose_for_profile([0.1, -0.2, 0.3, 0.4, -1.2, float("nan")], "urdf4")


def test_pose_to_animation_preserves_roll_but_separates_acceleration_metadata():
    positions = [0.1, -0.2, 0.3, 0.4, -1.4, 1.2]
    result = pose_to_animation_positions(ROARM_M3_NAMES, positions, acceleration=17.0)
    assert result == pytest.approx([0.1, -0.2, 0.3, 0.4, -1.4, 17.0])


def test_pose_to_animation_rejects_unknown_or_duplicate_joint_names():
    with pytest.raises(ValueError, match="unique"):
        pose_to_animation_positions(("base", "base"), [0.0, 0.0])
    with pytest.raises(ValueError, match="supported profile"):
        pose_to_animation_positions(("base",), [0.0])


def test_simulated_approach_from_measured_roll_does_not_jump_to_recipe_bound():
    from luxo_behaviors.joint_profiles import animation_pose_for_profile
    pose = [0, 0, 0, 0, -.1, 10]
    _, recipe = animation_pose_for_profile(pose, 'roarm_m3')
    _, approach = animation_pose_for_profile(pose, 'roarm_m3', enforce_animation_roll=False)
    assert recipe[4] == -.5
    assert approach[4] == -.1
    _, bounded = animation_pose_for_profile([0, 0, 0, 0, 50, 10], 'roarm_m3',
                                           enforce_animation_roll=False)
    assert bounded[4] == 3.1416
