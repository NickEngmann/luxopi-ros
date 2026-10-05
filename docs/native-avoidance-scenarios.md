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

Status: syntax checked; native execution pending coordinated rebuild and exclusive
graph ownership. No physical stopping-distance, sensor calibration, collision-free
trajectory or endpoint-tracking claim follows from these scenarios. Retreat signs
are explicit configuration and must be physically calibrated before hardware use.
