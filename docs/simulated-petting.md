# Simulated petting and touch safety

The simulator keeps touch-for-petting separate from touch-for-collision. The
current I²C manager publishes `UInt8` pressure states on
`/touch_sensors/head_top`, `head_left`, `head_right`, and `head_bottom`.
`head_top` is the classifier's petting input; a value greater than 1 emits
`/collision/petting_events` and enters the shared `PETTING` state with the real
`folded_wiggle` action. Releasing it emits `petting_stopped:0`, cancels the
active goal, and returns to `IDLE`. Left, right, and bottom remain FSR collision
inputs and never start petting. With the deployed default
`swap_touch_sides:=true`, `head_left` reports right danger, `head_right` reports
left danger, and `head_bottom` reports front danger. APDS proximity and VL53
range topics remain obstacle sensors, separate from all touch events.

The simulator also provides two explicit, simulation-only petting pads:
`/sim/petting_zones/top_front` and `/sim/petting_zones/antenna` (`Bool`). The
dashboard's Top/front and Antenna/hand-gripper buttons press and release these
inputs. `sim_interaction_adapter` aggregates them with the current `head_top`
petting event and sends them through the same PETTING state and
`folded_wiggle` action lifecycle. If multiple pads are held, releasing one does
not stop the session until the final pad releases. These simulation inputs do
not publish collision signals or bypass the animation/action controller.

The extra pad names follow historical hardware mapping in commit
`5607d60ac4fd98aefb6901f99b818d99675e765d` (2025-10-26): MPR121 channel 3 was
named `top_front` and channel 4 `antenna`, both marked for petting; channels
0–2 were collision pads. The current I²C implementation uses different topic
names, so the simulation topics are compatibility fixtures, not proof that the
current board exposes those channels. “Antenna / hand-gripper” is a UI label for
the historical pad; its physical position and wiring must be confirmed on the
robot. The M3 URDF does not define tactile pad frames, a head, or a gripper touch
sensor. The existing four `head_*` inputs are also topic names, not calibrated
physical mounting coordinates.

The camera controls distinguish injected values from read-only `/camera/*`
outputs. An explicit absent-person injection publishes only person loss; it
does not follow it with emotion or distance messages that would recreate
presence. Person loss clears the camera emotion buffer and the dashboard clears
stale emotion/distance output. The emotion reaction remains the same shared
reaction path; this simulator profile does not run pixel inference.

## Native validation

In an isolated network-none container, run `luxo_system.launch.py` with
`use_hardware:=false`, `simulation_backend:=kinematic`,
`joint_profile:=roarm_m3`, `enable_sim_sensors:=true`,
`enable_sim_interactions:=true`, `enable_sim_vision:=true`, and dashboard port
8091. Enable the voice bridge as well so simulated direction finding is present
for the dashboard's required-component health check. Then run:

```bash
ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1 \
  python3 scripts/run_petting_zone_scenarios.py \
  --dashboard http://127.0.0.1:8091 \
  --output /tmp/luxopi-petting-zones.json
```

The runner checks top-touch classifier start/stop, both historical simulation
pads, overlapping pad release behavior, all three current side/bottom collision
channels, and camera presence loss through the dashboard event endpoint. It
requires actual state/action/joint telemetry; input-topic publication alone is
not a pass. Hardware pad mapping, pressure calibration, tactile geometry and
camera inference accuracy remain unvalidated.

The recorded ROS E2E report in [simulated-petting-e2e.json](simulated-petting-e2e.json)
contains 8 passing scenarios: each petting path moved the six-axis simulator
joints by more than 0.015 rad and returned to `IDLE`; all three FSR contacts
entered and cleared collision state with the configured side mapping;
overlapping simulated pads released independently; and person absence left
emotion and distance outputs empty without starting an emotion animation. The
graph health endpoint was healthy during this run.
