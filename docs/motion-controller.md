# Motion transport and simulator contract

Animation plans use one six-value internal frame:
`[base, shoulder, elbow, wrist, roll, acceleration]`. The last value is
transport metadata, never a joint position. The `urdf4` profile maps the first
four axes to the checked-in visualization URDF. The optional `roarm_m3` profile
uses the six canonical vendor joint names and maps roll to the fifth axis; the
gripper remains at measured feedback or zero. Hardware commands retain their
existing conservative roll range. Every plan is validated for shape, finite
values, duration, and keyframe-name count before execution.

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

The simulation controller also consumes the ROS collision warning outputs. A
warning immediately holds its current joint target while the state manager
enters `COLLISION_AVOIDING`; `ESCAPE_MODE`, `ERROR`, and `SHUTDOWN` likewise
hold simulated motion. Clearing all warnings requests the ordinary idle
completion transition. This deliberately conservative simulated hold checks
the arbitration boundary only; it does not model the physical escape trajectory
or establish a hardware safety guarantee. `/sim/motion_status` exposes the
state, active warning directions, target, current positions, and hold status.

The simulator's current URDF contains four revolute joints with 0.5 rad/s
velocity limits. The physical RoArm exposes additional actuator/metadata fields
and uses hardware-specific base limits and firmware acceleration values. The
simulation limiter therefore validates the visualization/model axes, while the
hardware interface remains responsible for physical-device bounds and sensor
safety. Physical velocity/acceleration behavior must be checked against the
actual firmware transport before sharing simulator limits with that backend.

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
