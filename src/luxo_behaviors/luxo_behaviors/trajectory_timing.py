"""Feasible durations for the animation server's piecewise cubic easing.

These are mathematical command bounds, not measured physical actuator specs.
The sixth animation frame field is acceleration metadata and is not an axis.
"""
import math


def feasible_cubic_duration(start, target, requested_duration, *, max_velocity,
                            max_acceleration, axes=5):
    """Bound peak speed (3*d/T) and acceleration (12*d/T²) per axis."""
    values = (float(requested_duration), float(max_velocity), float(max_acceleration))
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError('duration, velocity and acceleration must be finite and positive')
    duration, velocity, acceleration = values
    if not isinstance(axes, int) or isinstance(axes, bool) or axes < 1:
        raise ValueError('axes must be a positive integer')
    if len(start) < axes or len(target) < axes:
        raise ValueError('pose has fewer fields than the physical axes')
    for before, after in zip(start[:axes], target[:axes]):
        before, after = float(before), float(after)
        if not math.isfinite(before) or not math.isfinite(after):
            raise ValueError('joint positions must be finite')
        distance = abs(after-before)
        duration = max(duration, 3*distance/velocity,
                       math.sqrt(12*distance/acceleration))
    return duration


def retime_cubic_plan(start, frames, durations, *, speed_multiplier=1.0,
                      max_velocity=.5, max_acceleration=1.0, axes=5):
    """Apply requested speed, then lengthen each segment to feasible limits."""
    speed = float(speed_multiplier)
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError('speed multiplier must be finite and positive')
    frames, durations = tuple(frames), tuple(durations)
    if not frames or len(frames) != len(durations):
        raise ValueError('nonempty frames and matching durations are required')
    previous = start
    result = []
    for frame, duration in zip(frames, durations):
        result.append(feasible_cubic_duration(
            previous, frame, float(duration)/speed,
            max_velocity=max_velocity, max_acceleration=max_acceleration,
            axes=axes,
        ))
        previous = frame
    return tuple(result)
