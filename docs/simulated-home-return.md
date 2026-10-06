# Measured home return in simulation

`RETURNING_HOME` now runs the existing physical two-stage recipe through the
same bounded motion writer. The recipe constants are shared with the hardware
coordinator; hardware timing and behavior are unchanged. Simulation is
deterministic: preserve base heading unless it is within 0.5 rad of a limit,
preserve the M3 gripper, settle at stage one for 0.5s, then settle at stage two.
The final pose must be within 0.03 rad with velocity below 0.03 rad/s for 0.1s.
A 30s feedback deadline ends an unreachable home plan normally.

The dashboard starts this behavior with the unique `home_return:<UUID>` state owner;
the controller completes only that owner's lease. Direct simulator state-service
callers wanting automatic home completion must use a fresh requester beginning with `home_return:` too. The controller reads the authoritative `/luxo/state_info` owner before starting.
A late completion cannot release a replacement home or manual command; retired
home leases are held instead of restarted if a safety-state restoration arrives. Explicit state reset,
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
rejection. Four HTTP end-to-end cases also passed on both the native ROS
kinematic graph and the MuJoCo graph: measured two-stage settling, contact
interruption without automatic replay, a fresh home request, and replacement
manual ownership surviving an old completion. Reports are retained locally in
`/tmp/luxopi-home-native.json` and `/tmp/luxopi-final-full-home.json`.

The first native run exposed a missing RETURNING_HOME safety transition.
The state machine now permits collision avoidance and escape to interrupt home;
its ownership tests verify clearing the interruption cannot restore the retired
home lease. The failed report was preserved before the corrected run.
These tests do not establish
that the recipe avoids every real obstacle or calibrate physical sensor placement.
