"""Small pure policy helpers for the isolated native ROS test runner."""
import subprocess


def motion_suite_timeout_seconds(*, full_animation_playlist, feasible_retiming, continuous_retiming):
    """Allow full safety-limited animation sweeps enough time to finish."""
    if full_animation_playlist and (feasible_retiming or continuous_retiming):
        return 3600
    return 500


def execute_with_timeout(command, log_path, timeout_seconds):
    """Run one suite and persist timeout evidence as well as ordinary output."""
    timed_out = False
    with open(log_path, "w", encoding="utf-8") as log:
        try:
            result = subprocess.run(
                command, stdout=log, stderr=subprocess.STDOUT, timeout=timeout_seconds
            )
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = 124
            log.write(f"\nNATIVE SUITE TIMED OUT after {timeout_seconds} seconds.\n")
    return exit_code, timed_out
