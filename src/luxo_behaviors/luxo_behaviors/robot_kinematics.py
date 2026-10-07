"""Forward kinematics for the four revolute joints in roarm.urdf.

This is a kinematic visualization helper, not a dynamics or collision model.
Joint origins and axes match the checked-in URDF. The terminal visual extent is
derived from the L4 STL Z bounds (0.4807606..0.5586106 m) and its URDF visual
origin (-0.49076 m), giving a 0.0678506 m tip extent from the wrist frame.
"""

import math


JOINT_LIMITS = {
    "base_to_L1": (-3.14, 3.14),
    "L1_to_L2": (-1.570796, 1.570796),
    "L2_to_L3": (-0.78539815, 3.1415926),
    "L3_to_L4": (-2.3561942, 2.3561942),
}

L4_TIP_EXTENT_M = 0.5586106181144714 - 0.49076


def compute_urdf_fk(joints):
    """Return pivot positions and tool tip for a mapping of URDF joint angles.

    Missing joint positions default to zero. Returned points are in the URDF
    base_link frame and use meters.
    """
    base = _angle(joints.get("base_to_L1", 0.0))
    shoulder = _angle(joints.get("L1_to_L2", 0.0))
    elbow = _angle(joints.get("L2_to_L3", 0.0))
    wrist = _angle(joints.get("L3_to_L4", 0.0))

    shoulder_frame = (0.0, 0.0, 0.03796)
    elbow_offset = _rotate_base(
        base, _rotate_y(shoulder, (0.03, 0.0, 0.23682))
    )
    elbow_frame = _add(shoulder_frame, elbow_offset)
    wrist_offset = _rotate_base(
        base, _rotate_y(shoulder + elbow, (0.0, 0.0, 0.21599))
    )
    wrist_frame = _add(elbow_frame, wrist_offset)
    tip_offset = _rotate_base(
        base, _rotate_y(shoulder + elbow + wrist, (0.0, 0.0, L4_TIP_EXTENT_M))
    )
    tip = _add(wrist_frame, tip_offset)
    return {
        "shoulder": shoulder_frame,
        "elbow": elbow_frame,
        "wrist": wrist_frame,
        "tip": tip,
    }


def _angle(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("joint positions must be finite")
    return value


def _rotate_y(angle, vector):
    x, y, z = vector
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return cosine * x + sine * z, y, -sine * x + cosine * z


def _rotate_base(angle, vector):
    x, y, z = vector
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return cosine * x - sine * y, sine * x + cosine * y, z


def _add(left, right):
    return tuple(a + b for a, b in zip(left, right))
