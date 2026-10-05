# Raw obstacle avoidance scenarios

The source-only `scripts/run_avoidance_scenarios.py` exercises the shared reactive
policy through actual raw ROS sensor inputs, controller output and state messages.
Run exclusively on a rebuilt controlled simulator graph:

```
ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1 python3 scripts/run_avoidance_scenarios.py --output /tmp/luxopi-avoidance.json
```

It requires `/collision/sensor_status` validity telemetry and `/sim/motion_status`
policy decisions. Cases cover side/front warning redirection, imminent distance
and contact hold, conflicting side hold, sensor dropout after warning, fresh clear
without replaying an old target, and movement after a fresh target. Each observed
joint must be finite and within the configured four/six-axis profile limits.

Status: all 11 native cases passed on 2026-10-05, 13:47 UTC in 25.843s. No physical stopping-distance, sensor calibration, collision-free
trajectory or endpoint-tracking claim follows from these scenarios. Retreat signs
are explicit configuration and must be physically calibrated before hardware use.

Runtime `c9c8fbb-intent-fix`, production source SHA256
`336e59b285d1139439c0b0633e5394cbffe4bad4f14eeca927c62a7d2b077714`.
Runner SHA256 `46b2d70ba6d0c3e1d8512f0ff56e3a7650fcdbdb8fb9b5db5e32ee3ffd2f766b`.
Report copied to host `/tmp/luxopi-reactive-avoidance-intent-fixed.json`.
Actual dance yaw reversed under a fresh matching warning while its action stayed
running; subsequent danger aborted it. Hold cases verify bounded braking before
stationary feedback, with .5rad/s and 1rad/s² simulation caps. Fresh clear did
not replay an old target; a newly identified manual intent resumed movement.

Retained failed evidence includes the initial strict immediate-freeze assumption,
and the real old-target replay regression before stable intent IDs were added.
This 11-case suite is now included in the nine-suite aggregate, whose new complete
retimed execution is still pending. Earlier eight-suite results retain their exact
runtime scope. The separate raw-sensor runner timed out waiting 20s for petting release to
return IDLE. Continuing the slow retimed petting action after the hand is gone
is a responsiveness regression; an owned-goal cancellation fix is pending. The
20s check is retained, and this timeout is not a passing new raw-sensor result.
