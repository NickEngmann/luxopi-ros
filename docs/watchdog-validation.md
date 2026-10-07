# Watchdog monitoring contract

The watchdog consumes `StateInfo` on `/luxo/state_info` and action status on
`/play_animation/_action/status`. Joint positions are radians, and four-joint
messages are supported. Topic ages and thresholds are seconds; a missing initial
core state/joint heartbeat also times out after startup grace.

Sparse animation commands, indefinite idle, stationary sound bearings, manual
holds and collision safety holds do not imply a broken node. Executing action
status and core heartbeat timeouts remain monitored. Only bounded return-home and
escape states are checked for duration. A reentrant lock prevents recovery from
self-deadlocking; service readiness checks do not block ROS timer callbacks.

Simulation uses `monitor_only=true`: flags and `/watchdog/status` are observable,
but no state changes, restart attempts, or hardware recovery occur. Separate
`state_topic` and `joint_topic` parameters allow fault injection on isolated
probe topics without stopping the running graph. Node restart remains an explicit
unimplemented opt-in placeholder in the legacy hardware path.

Five dependency-light tests execute the actual constructor/callbacks/checks:
contracts, startup silence, recovery on real callbacks, four-joint motion,
normal idle/collision/manual stillness, and executing-action timeout. Native fault
transport validation is recorded separately by `run_watchdog_scenarios.py`.
System monitor unavailable readings are NaN rather than invented healthy CPU/RAM
or 45°C values; valid thermal readings remain millidegrees→Celsius conversion.
