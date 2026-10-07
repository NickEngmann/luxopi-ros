# Simulated gesture behavior

In simulation, APDS9960 swipe strings pass from `/i2c/apds9960/gesture` through
`collision_ros_node` on `/gestures`. `sim_interaction_adapter` routes an accepted
swipe to the existing `PlayAnimation` action; the normal animation planner and
joint controller produce the motion. The adapter accepts gestures only while
the FSM and voice session are idle and no action owns motion. It applies a
one-second debounce, and collision or voice activity cancels its animation.

| Swipe | Animation |
|---|---|
| left | `look_around_casual` |
| right | `curious_exploration` |
| up | `neck_stretch` |
| down | `nod` |

Run the end-to-end check against an isolated ROS simulator graph with
`ROS_DOMAIN_ID=73` and `ROS_LOCALHOST_ONLY=1`:

```bash
python3 scripts/run_gesture_motion_scenarios.py
```

The runner supplies safe synthetic range and no-contact samples, injects each
swipe, and verifies the passthrough topic, selected animation, measured joint
movement, action completion, and return to `IDLE`. On source
`55b4dea1207764a794ac222e84d18672a6a50f68`, all four scenarios passed in the
network-none `luxopi-sensor-e2e` container. Maximum observed per-scenario joint
deltas were left 2.0 rad, right 0.75 rad, up 0.75 rad, and down 1.0 rad.

These results prove only the software path with synthetic swipe input and the
kinematic controller. They do not validate APDS9960 detection, physical sensor
orientation, or safe real-robot gesture behavior. The swipes select existing
animation motifs; they are not a calibrated directional gaze or steering
model.
