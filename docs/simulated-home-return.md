# Measured home return in simulation

`RETURNING_HOME` now runs the existing physical two-stage recipe through the
same bounded motion writer. The recipe constants are shared with the hardware
coordinator; hardware timing and behavior are unchanged. Simulation is
deterministic: preserve base heading unless it is within 0.5 rad of a limit,
preserve the M3 gripper, settle at stage one for 0.5s, then settle at stage two.
The final pose must be within 0.03 rad with velocity below 0.03 rad/s for 0.1s.
A 30s feedback deadline ends an unreachable home plan normally.

The dashboard starts this behavior with the dedicated `home_return` state owner;
the controller completes only that owner's lease. Direct simulator state-service
callers wanting automatic home completion must use that requester too. A foreign
completion cannot release a replacement manual command. Explicit state reset,
contact/danger, invalid or missing required sensor coverage, stale physics feedback,
and a warning retreat lasting 2s stop the old home plan. Fresh clear evidence
cannot resurrect that plan; a new request is needed.

A home plan owns motor targets while active. Old animation heartbeats are ignored,
and the interrupted action sees the exclusive owner and terminates without
ERROR. On exit the measured pose becomes the held target; only a new animation
intent or explicit manual command can move again. INITIALIZING is also a motion
hold, and emergency-state recovery cannot replay an old animation target.

Offline tests execute the actual controller methods with the real joint limiter,
checking both stages, sensor interruption, replacement control and old-goal
rejection. Native ROS/physics validation is pending. These tests do not establish
that the recipe avoids every real obstacle or calibrate physical sensor placement.
