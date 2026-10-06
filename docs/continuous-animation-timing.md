# Continuous animation timing

Continuous feasible timing is now the default for the simulator, including the
kinematic and MuJoCo profiles. It preserves each authored waypoint while
streaming one bounded trajectory through the path, and reports action success
only after the final measured pose settles. To select the explicit
stopped-waypoint simulator path, set
`LUXOPI_CONTINUOUS_ANIMATION_TIMING=false` before using
`scripts/simulator.sh up -d`. Direct simulation launches also default to
continuous timing. The hardware launch branch does not receive either
simulation retiming parameter and keeps its existing timing unchanged.

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

The frozen `123025b` continuous profile passed all nine native suites on
2026-10-06, including all 38 animation actions with feasible-duration and
endpoint-settling assertions. The full motion playlist took 1030.763 seconds;
dance took 36.89 seconds and nod 28.66 seconds. Each finished with zero
measured endpoint error and zero settled velocity in the six-axis kinematic
profile. A 31-scenario browser run on the same graph passed, including a fresh
transcript/reply pair, all 12 state controls, manual six-axis motion, sensors,
collision recovery and readiness errors. Reports:
`/tmp/luxopi-continuous-full-final-20261006T033824Z/summary.json` and
`/tmp/luxopi-continuous-browser-e2e-final.json`; the companion provenance file
links the resumed suite's matching source hash to the original runtime report.

The shorter stopped-waypoint runner reported dance at 4.48 seconds and nod at 2.96
seconds, but did not assert measured endpoint error or settled velocity. Those
action durations only reflect the authored timeline; they are not a valid
comparison of completed physical motion. The continuous profile takes longer
because it observes the 0.5 rad/s and 1 rad/s² bounds and waits for the final
pose to settle. The full free-space MuJoCo sweep also exercised all 38 paths at
500 Hz with 0.487 rad/s maximum measured velocity, zero saturated effort steps,
zero contacts, and settled endpoint error below 0.00027 rad. It completed in
977.88 simulated seconds versus 1855.74 seconds for the stopped-waypoint sweep.
These are simulator measurements; real actuator tracking, safe limits and
obstacle clearance still need hardware commissioning.

Planning is not the animation bottleneck: an isolated native benchmark over
all 458 waypoints measured 0.434 ms mean and 0.946 ms maximum to construct a
continuous plan. Long expressive animations therefore reflect the configured
motion bounds and authored travel, not a blocking planning step. Short cues
such as listen, acknowledge and speaking complete in roughly 2.4–3.3 seconds.

## Completed current regression scopes

A frozen `123025b` probe passed all nine native suites on 2026-10-06 UTC,
including all 38 full animation actions with endpoint-settling checks. The
motion portion took 1030.763s. Report:
`/tmp/luxopi-continuous-full-final-20261006T033824Z/summary.json`.
Production SHA256:
`3fa237efa2ea61752de1826acf0bc1408d8883efff76a486512d585adf2ac8b7`.
The failed lamp run assumed an untouched default color temperature; explicit
white selection and temperature setup corrected that test. Resumption reused
only the verified identical-source/runner passing motion and state prefix.

A separate probe using the later `8e8ba06` lifecycle fixes passed all nine core
suites in continuous mode, source SHA256
`0d2010c269222458f40200f304c8d0e3b173a0d1a0a9d366b9af8378f1d03f2c`.
Report: `/tmp/luxopi-continuous-latest-native-final/summary.json`. This later
run covers four core motion cases and the new ownership behavior; it must not
be represented as rerunning the full 38-plugin playlist on that source.
Continuous feasible timing is the simulator default. The explicit
`LUXOPI_CONTINUOUS_ANIMATION_TIMING=false` setting selects the older
stopped-waypoint path for comparison. The hardware animation path receives
neither simulation retiming parameter and remains unchanged.
