"""Shared simulator launch defaults."""

from launch.substitutions import PythonExpression


def continuous_timing_default(use_hardware):
    """Enable bounded continuous timing for simulation, never for hardware."""
    return PythonExpression([
        "'false' if '", use_hardware, "' == 'true' else 'true'",
    ])
