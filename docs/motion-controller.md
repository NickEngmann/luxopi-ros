# Motion transport and simulator contract

The animation server publishes named targets on `/joint_states_target` in both
modes. On hardware, `RoArmHardwareInterface` validates safety conditions and
encodes the target for the RoArm serial protocol. In simulation,
`SimMotionController` is the sole publisher of `/joint_states`; it applies the
same checked-in four-joint URDF bounds used by the animation server and limits
each output step by configured velocity and acceleration. `robot_state_publisher`
consumes that one output stream. The simulation launch disables
`joint_state_publisher`, which previously could publish a competing set of
joint positions.

Voice direction is accepted as a temporary base-joint override only after the
state manager grants `VOICE_FOLLOWING`. The controller requests that state at
the voice-following priority and requests completion when the estimator reports
quiet; it ignores voice targets in collision, escape, error, and shutdown states.
Animation targets remain intact underneath the override and resume after voice
following completes. The request path is asynchronous and never blocks a ROS
callback.

The simulator's current URDF contains four revolute joints with 0.5 rad/s
velocity limits. The physical RoArm exposes additional actuator/metadata fields
and uses hardware-specific base limits and firmware acceleration values. The
simulation limiter therefore validates the visualization/model axes, while the
hardware interface remains responsible for physical-device bounds and sensor
safety. Physical velocity/acceleration behavior must be checked against the
actual firmware transport before sharing simulator limits with that backend.

Hardware-free limiter tests cover named target validation, joint bounds,
velocity/acceleration limits, and reversal behavior. Animation cancellation and
the shared writer are tested separately. Run them with:

```sh
cd src/luxo_behaviors
python -m pytest -q
```
