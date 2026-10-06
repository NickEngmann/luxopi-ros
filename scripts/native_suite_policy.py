"""Small pure policy helpers for the isolated native ROS test runner."""


def motion_suite_timeout_seconds(*, full_animation_playlist, feasible_retiming, continuous_retiming):
    """Allow full safety-limited animation sweeps enough time to finish."""
    if full_animation_playlist and (feasible_retiming or continuous_retiming):
        return 3600
    return 500
