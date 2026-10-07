# Vision animation interrupted by a raw collision

This scenario closes a cross-feature gap: a camera-derived emotion must use the
real animation action, and a later sensor-classified danger must cancel that
action. Clearing the raw sensors must not resume the stale emotion goal.

Run it only against an isolated simulation graph (ROS domain 73, localhost
only). Start `luxo_system.launch.py` with `use_hardware:=false`,
`simulation_backend:=kinematic`, `joint_profile:=roarm_m3`,
`enable_sim_sensors:=true`, `enable_sim_vision:=true`, and
`enable_sim_interactions:=true`. Then run:

```bash
ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1 \
  python3 scripts/run_vision_collision_scenarios.py \
  --output /tmp/luxopi-vision-collision.json
```

The runner checks `EMOTION_REACTING`, the registered `sad` action and movement
in actual six-axis joint feedback. It then publishes repeated raw APDS9960
proximity readings of 255 while continuing safe side-range and explicit FSR-zero
samples. The collision classifier must report fresh front `danger`, the FSM
must enter `COLLISION_AVOIDING`, and the animation action must terminate as
canceled (ROS action status 6). Once raw sensors clear and the controller enters
`IDLE`/`hold_replan`, the runner confirms the canceled emotion does not move the
arm again without a new intent.

## Recorded result

On 2026-10-06, all three assertions passed in 11.94 seconds in the isolated
network-none `luxopi-sensor-e2e` container, using six canonical M3 joint names.
The sad reaction moved 0.0314 rad from its baseline. The runner observed the
action transition through accepted, executing and canceled statuses. Raw APDS
danger was valid with a 4 ms sample age and fresh explicit FSR coverage; the
action ended with status 6. Following clear, the FSM was `IDLE`, avoidance mode
was `hold_replan`, and measured joint drift over one second was 0 rad. The run used source revision
`a0fc5a8bdc556a81e5e3dc6353c19e2026071cb2`; installed hashes for the vision
adapter, shared vision policy, collision classifier, animation server,
interaction adapter, motion controller, and launch file matched that checkout.
The JSON report is in [`vision-collision-2026-10-06.json`](evidence/vision-collision-2026-10-06.json).

This is consumer-path integration evidence, not camera inference accuracy,
physical sensor calibration, real-world stopping distance, or collision-safety
certification.
