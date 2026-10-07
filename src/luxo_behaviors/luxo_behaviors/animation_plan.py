"""ROS-free contract for deterministic animation motion plans.

Animation keyframes use one fixed internal layout everywhere:
``base, shoulder, elbow, wrist, roll, acceleration``. Acceleration is command
metadata and is never a joint position. A backend maps the first five axes to
its hardware profile and holds any extra actuator (such as the M3 gripper).
"""

import math


POSE_AXES = ("base", "shoulder", "elbow", "wrist", "roll", "acceleration")
PLAN_SANITY_BOUNDS = (
    (-math.pi, math.pi),
    (-1.8, 0.5),
    (0.0, 2.2),
    (-0.1, 2.0),
    (-3.1, -0.5),
    (5.0, 30.0),
)
MAX_STEP_DURATION_SECONDS = 30.0


def validate_animation_plan(keyframes, durations, keyframe_names=None):
    """Return immutable numeric plan data or raise a specific validation error."""
    try:
        frames = tuple(tuple(float(value) for value in frame) for frame in keyframes)
        steps = tuple(float(value) for value in durations)
    except (TypeError, ValueError) as exc:
        raise ValueError("keyframes and durations must be numeric sequences") from exc

    if not frames or len(frames) != len(steps):
        raise ValueError("plan must have at least one frame and matching durations")
    if any(len(frame) != len(POSE_AXES) for frame in frames):
        raise ValueError("each frame must be [base, shoulder, elbow, wrist, roll, acceleration]")
    for frame_index, frame in enumerate(frames):
        for axis, value, (lower, upper) in zip(POSE_AXES, frame, PLAN_SANITY_BOUNDS):
            if not math.isfinite(value):
                raise ValueError(f"frame {frame_index} has non-finite {axis}")
            if not lower <= value <= upper:
                raise ValueError(f"frame {frame_index} {axis} outside plan sanity bounds")
    for step_index, duration in enumerate(steps):
        if not math.isfinite(duration) or not 0.0 < duration <= MAX_STEP_DURATION_SECONDS:
            raise ValueError(f"step {step_index} duration must be finite and in (0, 30] seconds")
    if keyframe_names is not None and len(keyframe_names) != len(frames):
        raise ValueError("keyframe names must match frame count")
    return frames, steps
