"""Verified names, limits, and forward kinematics for the vendored RoArm-M3.

The first four application joints map to the vendor M3 base/shoulder/elbow/
wrist joints. M3 roll and gripper remain fixed at zero in the current app.
"""

import math


LUXO_TO_M3 = {
    "base_to_L1": "base_link_to_link1",
    "L1_to_L2": "link1_to_link2",
    "L2_to_L3": "link2_to_link3",
    "L3_to_L4": "link3_to_link4",
}

M3_JOINT_NAMES = (
    "base_link_to_link1",
    "link1_to_link2",
    "link2_to_link3",
    "link3_to_link4",
    "link4_to_link5",
    "link5_to_gripper_link",
)

M3_JOINT_LIMITS = {
    "base_link_to_link1": (-3.1416, 3.1416),
    "link1_to_link2": (-1.5708, 1.5708),
    "link2_to_link3": (-1.0, 2.95),
    "link3_to_link4": (-1.5708, 1.5708),
    "link4_to_link5": (-3.1416, 3.1416),
    "link5_to_gripper_link": (0.0, 1.5),
}


def map_luxo_joints_to_m3(joints):
    """Map app's four URDF joints to six vendor joints, clamped for preview.

    Roll and gripper are intentionally held at their vendor home value, zero.
    The input mapping is keyed by the checked-in application's joint names.
    """
    mapped = {name: 0.0 for name in M3_JOINT_NAMES}
    for source, target in LUXO_TO_M3.items():
        value = float(joints.get(source, 0.0))
        if not math.isfinite(value):
            raise ValueError("joint positions must be finite")
        lower, upper = M3_JOINT_LIMITS[target]
        mapped[target] = min(upper, max(lower, value))
    return mapped


def compute_m3_fk(joints):
    """Return link origins for the official vendor M3 xacro in world metres."""
    angles = {name: _finite(joints.get(name, 0.0)) for name in M3_JOINT_NAMES}
    base = _translation(0.0, 0.0, 0.0701)
    link1 = _matmul(base, _rotation_z(angles["base_link_to_link1"]))
    link2 = _joint(
        link1, (0.0, 0.0, 0.051959), (-1.5708, -1.5708, 0.0),
        angles["link1_to_link2"],
    )
    link3 = _joint(
        link2, (0.236815, 0.030002, 0.0), (0.0, 0.0, 1.5708),
        angles["link2_to_link3"],
    )
    link4 = _joint(
        link3, (0.0, -0.144586, 0.0), (0.0, 0.0, 0.0),
        angles["link3_to_link4"],
    )
    link5 = _joint(
        link4, (0.015147, -0.053653, 0.0), (1.5708, 1.5708, 0.0),
        angles["link4_to_link5"],
    )
    gripper = _joint(
        link5, (0.0, 0.018821, 0.052035), (-1.5708, -1.5708, 0.0),
        angles["link5_to_gripper_link"],
    )
    hand_tcp = _fixed(link5, (0.0, 0.0, 0.115428), (1.5708, -1.5708, 0.0))
    return {
        "base_link": _origin(base),
        "link1": _origin(link1),
        "link2": _origin(link2),
        "link3": _origin(link3),
        "link4": _origin(link4),
        "link5": _origin(link5),
        "gripper_link": _origin(gripper),
        "hand_tcp": _origin(hand_tcp),
    }


def _finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("joint positions must be finite")
    return value


def _translation(x, y, z):
    return ((1.0, 0.0, 0.0, x), (0.0, 1.0, 0.0, y), (0.0, 0.0, 1.0, z), (0.0, 0.0, 0.0, 1.0))


def _rotation_z(angle):
    c, s = math.cos(angle), math.sin(angle)
    return ((c, -s, 0.0, 0.0), (s, c, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))


def _rotation_rpy(roll, pitch, yaw):
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr, 0.0),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr, 0.0),
        (-sp, cp * sr, cp * cr, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


def _joint(parent, xyz, rpy, angle):
    return _matmul(
        _matmul(_matmul(parent, _translation(*xyz)), _rotation_rpy(*rpy)),
        _rotation_z(angle),
    )


def _fixed(parent, xyz, rpy):
    return _matmul(_matmul(parent, _translation(*xyz)), _rotation_rpy(*rpy))


def _matmul(left, right):
    return tuple(
        tuple(sum(left[row][k] * right[k][col] for k in range(4)) for col in range(4))
        for row in range(4)
    )


def _origin(transform):
    return tuple(transform[row][3] for row in range(3))
