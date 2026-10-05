# Motion transport and simulator contract

Animation plans use one six-value internal frame:
`[base, shoulder, elbow, wrist, roll, acceleration]`. The last value is
transport metadata, never a joint position. The `urdf4` profile maps base,
shoulder, elbow, and wrist to the checked-in visualization joints
`base_to_L1`, `L1_to_L2`, `L2_to_L3`, and `L3_to_L4`. It omits roll because the
checked-in legacy URDF has no fifth actuator. The optional `roarm_m3` profile
uses the vendor order `base_link_to_link1`, `link1_to_link2`,
`link2_to_link3`, `link3_to_link4`, `link4_to_link5`, and
`link5_to_gripper_link`; roll maps to axis five and the gripper remains at its
feedback position or zero. Generic animation poses keep the conservative
roll range `[-2.5, -0.5]`; manual M3 poses are bounded by the vendor URDF
limits. Generic animations never command the gripper. Every plan is validated
for six-value shape, finite values, duration, and keyframe-name count before
execution.

On hardware, `RoArmHardwareInterface` validates safety conditions and encodes
targets for the RoArm serial protocol. In kinematic simulation,
`SimMotionController` is the sole publisher of `/joint_states`; it applies the
selected profile bounds and configured velocity/acceleration step limits.
`robot_state_publisher` consumes that one output stream. Gazebo simulation
instead leaves feedback ownership to Gazebo and routes animation targets
through the bounded command bridge. The simulation launch disables
`joint_state_publisher`, which previously could publish competing joint
positions.

Voice direction is accepted as a temporary base-joint override only after the
state manager grants `VOICE_FOLLOWING`. The controller requests that state at
the voice-following priority and requests completion when the estimator reports
quiet; it ignores voice targets in collision, escape, error, and shutdown states.
Animation targets remain intact underneath the override and resume after voice
following completes. The request path is asynchronous and never blocks a ROS
callback.

Both `SimMotionController` and the hardware animation target path consume the
same ROS-free `ReactiveAvoidance` projection. A warning requests a bounded
retreat on a configured axis (front: shoulder, sides: base by default); the
other joints hold their measured pose while the warning persists. These signs
preserve the pre-existing movement validator conventions and remain configurable;
they are not physically calibrated sensor-frame directions. A warning cannot
continue toward its sensor. Danger/contact, opposing side hazards, stale or
invalid coverage, an unconfigured retreat axis, or a retreat blocked by a joint
limit requests a hold. The sensor classifier publishes atomic
`/collision/sensor_status` JSON records with severity, validity and sample ages.
An optical clear cannot release a latched FSR contact: matching range and FSR
inputs must both be fresh, and the FSR must publish a release. Fresh clear must
persist through the dwell, then a new target is required; old animation targets
are not replayed after the hazard clears. Head-top touch remains a petting
input, separate from collision response.

This joint-space policy is deliberately conservative. It does not have camera,
range-sensor or FSR extrinsics, swept-volume collision geometry, or calibrated
obstacle surfaces, so it cannot guarantee that a configured retreat clears an
object. The dashboard/MuJoCo sensor scene can exercise the actual classifier and
policy consumers, but its simulated rays and measurements are not physical
calibration evidence. `/sim/motion_status` exposes the current state,
`avoidance_mode`, active directions, requested/adjusted target and positions.
`ESCAPE_MODE`, `ERROR`, and `SHUTDOWN` remain hard holds in the kinematic
controller.

The four-axis kinematic profile uses the checked-in URDF limits; the six-axis
M3 profile uses vendor URDF bounds for visualization and bounded manual input.
The simulated limiter defaults to 0.5 rad/s and 1.0 rad/s² in either profile.
Command trajectory state remains independent of physics feedback; feedback is
used for reporting and reactive holds rather than reseeding the limiter every
tick. A newly retargeted trajectory can still need time to brake. Joint bounds
take precedence at a hard limit, so these are simulator constraints rather
than a physical firmware performance claim. The hardware interface remains
responsible for physical-device bounds and serial firmware metadata. The shared browser graph currently starts
with `urdf4`; a six-axis deployment must select `roarm_m3` explicitly and pass
the native six-joint motion scenarios before it is treated as verified.

Hardware-free limiter tests cover named target validation, joint bounds,
velocity/acceleration limits, and reversal behavior. Animation cancellation and
the shared writer are tested separately. Voice status uses short, low-priority
presentation cues (`listening`, `acknowledge`, `thinking`, `speaking`,
`settle`) through the same action arbiter. Cues cannot replace a running
requested action, while explicit actions and collision handling can preempt
them. `USER_CONTROL` remains owned by the voice session until its actual idle
status and any primary action have completed; an animation result cannot end a
state owned by a different subsystem.

Run the offline checks with:

```sh
cd src/luxo_behaviors
python -m pytest -q
```
