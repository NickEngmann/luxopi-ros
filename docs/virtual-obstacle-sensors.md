# Virtual obstacle sensors

The optional MuJoCo launch can generate distinct sensor samples from a small
world-frame obstacle scene. `sim_world_sensors` follows `/joint_states`, runs
forward kinematics against the pinned RoArm-M3 model, raycasts from the
configured mount transforms, then publishes the same raw inputs consumed by
`collision_ros_node`:

- `/i2c/apds9960/proximity` (`Int16`, 0–255)
- `/i2c/vl53_left/distance` and `/i2c/vl53_right/distance` (`Float32`, cm)
- `/sim/world_sensor_status` (`String`, JSON diagnostics)
- `/touch_sensors/head_bottom`, `head_left`, and `head_right` (`UInt8`, explicit zero-contact samples)

The default `world_obstacles_json` is `[]`, so this producer returns maximum
range readings unless a test scene is configured. A bounded box/sphere scene
can be provided to `physics_simulator.launch.py`:

```bash
ros2 launch luxo_behaviors physics_simulator.launch.py \
  enable_world_sensor_fixture:=true \
  world_obstacles_json:='[{"name":"front_fixture","shape":"box","center_m":[0.15,0,0.61],"half_extents_m":[0.03,0.06,0.06]}]'
```

The container helper also accepts fixture configuration through environment
variables in physics/full modes:

```bash
LUXOPI_WORLD_SENSOR_FIXTURE=true \
LUXOPI_WORLD_OBSTACLES_JSON='[{"name":"front_fixture","shape":"box","center_m":[0.15,0,0.61],"half_extents_m":[0.03,0.06,0.06]}]' \
scripts/simulator.sh --mode physics up -d
```

Use `LUXOPI_SENSOR_MOUNTS_JSON` for custom mount transforms. Set these variables
again when recreating the container, or keep them in a private Compose environment
file. Do not enable the periodic fixture during tests that inject raw sensor samples.

Coordinates are metres in the M3 URDF world frame. Box dimensions are
half-extents. Scenes are limited to 32 named primitives with dimensions and
positions bounded to five metres. Rays are normalized and clipped to each
mount's configured `max_range_m`, which is limited to 1.2 m so synthetic side
readings remain within the collision adapter's accepted range.

Mounts can be changed with `sensor_mounts_json`, a JSON object with exactly
`front`, `left`, and `right` entries. Each entry specifies a vendor M3 link
`frame`, local `offset_m`, local `direction`, and `max_range_m`. The initial
fixture uses `gripper_link` for all three mounts, so rays rotate and translate
with the actual modeled end-effector pose. The vendor M3 model has no
body/head/camera frame; `gripper_link` is only an end-effector proxy, not a
claim that a camera or distance sensor is mounted there. These origins, their
directions, and the front proximity mapping are synthetic, uncalibrated test
values. The front ray maps distance
linearly to proximity over `front_proximity_range_m` (default 0.12 m); it does
not reproduce APDS9960 optics. Side outputs use ray distance in centimetres,
including zero on overlap so the classifier conservatively brakes. The fixture
does not emulate VL53 firmware noise or other invalid-return behavior.

Direct `physics_simulator.launch.py` keeps the producer opt-in with
`enable_world_sensor_fixture` (default `false`); the physics and full Compose
profiles enable it by default. `enable_sim_sensors=true` starts the regular
collision classifier and does not by itself enable synthetic rays.
The fixture also supplies fresh zero-contact FSR samples, since its geometric
scene does not model tactile contact. Required range/contact coverage therefore
remains strict; it is not silently disabled to make a range-only fixture work.
All raw publications stop on stale joint feedback, including these contact samples.
The separation prevents a periodic empty scene from clearing manual sensor
injections or other tests. A stale or missing six-joint feedback sample stops
new raw publications so the existing collision classifier's timeout path can
mark coverage unknown. The producer never publishes directly to collision
warnings or the motion controller: the regular classifier and reactive
avoidance consume the data. The fixture is useful for verifying the
sensor-to-behavior path and course correction; obstacle primitives affect rays
only, not MuJoCo contact physics. It is not evidence of real-world sensor
range, extrinsics, contact physics, or safe physical collision avoidance.

Joint feedback must contain the exact six vendor joint names, finite values,
and positions within the vendor URDF limits plus 0.02 rad tolerance. Rejected
frames do not refresh the fixture's feedback timeout. The focused node test
checks front/side classification, explicit fresh FSR-clear samples, invalid
feedback rejection, and stale-input expiry in an isolated ROS container.


The dashboard's Front/Left/Right virtual-obstacle buttons now hold raw range
readings through the standard sensor classifier while active, then send fresh
clear samples briefly after release so the collision state can recover. Orange
markers track the gripper and show which virtual sensor obstacle is active.
Dashboard dropout toggles stop the selected front/left/right ray at the
synthetic sensor source. Required sensor coverage then puts the real motion
controller into a named stale-coverage hold until the ray resumes. This is a
sensor stimulus, not a MuJoCo physical obstacle; use configured primitives to
test raycasts against geometry.
