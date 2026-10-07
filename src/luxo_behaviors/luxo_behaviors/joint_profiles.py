"""Explicit mapping between animation poses and the checked-in robot profiles."""

import math

from luxo_behaviors.joint_motion import URDF_JOINT_LIMITS, clamp_joint_positions


URDF4_NAMES = tuple(URDF_JOINT_LIMITS)
ROARM_M3_NAMES = (
    "base_link_to_link1",
    "link1_to_link2",
    "link2_to_link3",
    "link3_to_link4",
    "link4_to_link5",
    "link5_to_gripper_link",
)

# Bounds come from the vendor RoArm-M3 URDF; animation roll retains the
# existing conservative range used by hardware_interface.py.
ROARM_M3_LIMITS = {
    ROARM_M3_NAMES[0]: (-3.1416, 3.1416),
    ROARM_M3_NAMES[1]: (-1.5708, 1.5708),
    ROARM_M3_NAMES[2]: (-1.0, 2.95),
    ROARM_M3_NAMES[3]: (-1.5708, 1.5708),
    ROARM_M3_NAMES[4]: (-3.1416, 3.1416),
    ROARM_M3_NAMES[5]: (0.0, 1.5),
}
ANIMATION_ROLL_LIMIT = (-2.5, -0.5)


def joint_profile(profile):
    """Return the exact names and bounds for a supported profile."""
    name = str(profile).lower()
    if name in {"urdf4", "legacy4", "legacy"}:
        return URDF4_NAMES, URDF_JOINT_LIMITS
    if name in {"roarm_m3", "m3", "m3_6"}:
        return ROARM_M3_NAMES, ROARM_M3_LIMITS
    raise ValueError(f"unsupported joint profile: {profile}")


def animation_pose_for_profile(positions, profile, *, gripper_position=0.0,
                               enforce_animation_roll=True):
    """Map internal [base, shoulder, elbow, wrist, roll, accel] to pose axes.

    Acceleration is actuator metadata, never a JointState position. The M3
    gripper is held at its supplied current value (or zero before feedback).
    """
    names, limits = joint_profile(profile)
    if len(positions) < 5:
        raise ValueError("animation pose must provide base, shoulder, elbow, wrist, and roll")
    numeric_positions = [float(value) for value in positions]
    if any(not math.isfinite(value) for value in numeric_positions):
        raise ValueError("animation pose values must be finite")
    pose = numeric_positions[:5]
    if len(names) == 6:
        pose.append(float(gripper_position))
        if not math.isfinite(pose[-1]):
            raise ValueError("gripper position must be finite")
        if enforce_animation_roll:
            pose[4] = min(ANIMATION_ROLL_LIMIT[1], max(ANIMATION_ROLL_LIMIT[0], pose[4]))
    else:
        pose = pose[:len(names)]
    return names, clamp_joint_positions(names, pose, limits)


def pose_to_animation_positions(names, positions, *, acceleration=10.0):
    """Map a complete 4/6-axis state back to animation pose plus metadata."""
    if len(names) != len(positions):
        raise ValueError("joint names and positions must have equal length")
    numeric_positions = [float(value) for value in positions]
    if any(not math.isfinite(value) for value in numeric_positions):
        raise ValueError("joint positions must be finite")
    indexed = dict(zip(names, numeric_positions))
    if len(indexed) != len(names):
        raise ValueError("joint names must be unique")
    if set(names) == set(URDF4_NAMES):
        pose = [indexed[name] for name in URDF4_NAMES] + [-1.5]
    elif set(names) == set(ROARM_M3_NAMES):
        pose = [indexed[name] for name in ROARM_M3_NAMES[:5]]
    else:
        raise ValueError("joint state does not match a supported profile")
    acceleration = float(acceleration)
    if not math.isfinite(acceleration):
        raise ValueError("acceleration must be finite")
    pose.append(acceleration)
    return pose
