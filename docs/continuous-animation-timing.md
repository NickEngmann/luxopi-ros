# Continuous animation timing

Continuous timing is an opt-in simulation path. The default remains per-stage
bounded easing while live regression checks are completed. Enable the prototype
with `LUXOPI_CONTINUOUS_ANIMATION_TIMING=true scripts/simulator.sh up -d` after
building the current base image. The same environment switch works with the
physics and full profiles. Hardware timing is unchanged.

The prototype preserves every authored waypoint and its name. Monotone per-axis
Hermite tangents pass smoothly through compatible stages, stop at extrema, and
preserve identical-pose holds. Local duration stretching followed by an analytic
global bound keeps commanded velocity at or below 0.5 rad/s and acceleration at
or below 1 rad/s². The sixth animation field remains acceleration metadata; it
never becomes a physical axis. Only the final pose must settle before action
success; intermediate poses are continuously traversed rather than independently
stopped. Cancellation and the shared sensor policy remain authoritative.

The reusable `scripts/mujoco_playlist.py --continuous` sweep exercised all 38
animations and 458 waypoints on the pinned six-axis model. In the 2026-10-05
isolated run, simulated duration was 977.88 seconds versus 1855.74 seconds for
the earlier stopped-waypoint sweep. Measured speed stayed below 0.487 rad/s,
all final poses settled within 0.00027 rad, no effort saturated, and no contacts
occurred in that free-space scene. Report:
`/tmp/luxopi-continuous-playlist-fixed.json`.

The sweep exposed an intermediate roll-clamping jump: applying authored pose
bounds to every interpolated sample could snap a measured zero roll directly
toward -0.5 rad. Simulation now clamps authored destinations, then permits the
bounded approach from the actual measured angle while retaining the full URDF
joint bounds. Actual hardware calibration, obstacle geometry, torque limits,
and motion tracking still require the robot. These results are synthetic physics
checks, not physical collision certification or Raspberry Pi performance data.

The live ROS motion runner passed 42 cases on 2026-10-05, including all 38
animations, cancellation, action preemption, direction-driven motion and
collision rejection. In the isolated continuous probe, dance took 36.859s and
nod took 28.684s; each animation finished with zero reported endpoint error and
settled velocity in the kinematic backend. Evidence is copied to
`/tmp/luxopi-continuous-evidence-in-progress/motion.json` on the host. The frozen
runtime was `178fb02`, before the subsequent once-per-goal safety grace and
bounded-warning changes; this run must not be described as testing those fixes.
The other eight suites are still running, so full conversation/dashboard
regression coverage remains pending. The continuous mode remains opt-in.
