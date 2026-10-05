"""ROS-free policy and pose validation for the simulated motion controller."""

from luxo_behaviors.joint_motion import clamp_joint_positions, ordered_joint_target
from luxo_behaviors.joint_profiles import joint_profile


MOTION_HOLD_STATES = {"COLLISION_AVOIDING", "ESCAPE_MODE", "ERROR", "SHUTDOWN"}


def motion_is_frozen(state, collision_active):
    """Hold simulated targets during a safety state or active collision warning."""
    return str(state).upper() in MOTION_HOLD_STATES or any(collision_active)


def validate_manual_pose(state, names, positions, profile="urdf4"):
    """Validate a user-control pose and return its URDF-clamped joint order."""
    if str(state).upper() != "USER_CONTROL":
        raise ValueError("manual pose requires USER_CONTROL state")
    expected_names, limits = joint_profile(profile)
    target = ordered_joint_target(names, positions, expected_names)
    return clamp_joint_positions(expected_names, target, limits)
