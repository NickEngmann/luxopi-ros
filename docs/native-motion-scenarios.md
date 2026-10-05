# Native ROS action and direction scenarios

After launching the controlled full simulator graph and sourcing its workspace:

```
ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1 python3 scripts/run_motion_scenarios.py --all-animations --output /tmp/luxopi-motion-scenarios.json
```

The runner refuses other discovery settings. It uses real ROS action/service clients
and subscribes to actual joint/target/state messages; no hardware nodes or audible
playback are created. It executes:

- Dance acceptance, action feedback and observed actual-joint movement.
- Explicit cancellation with terminal `CANCELED`; after draining buffered messages,
  target values must remain stationary. Hold-message publishing may continue.
- Replacement goal preemption: old final state `preempted`, new action succeeds,
  feedback handoff is ordered, and each actual/target topic has only one publisher.
  The existing server reports superseded goals as `ABORTED` with `preempted` result;
  explicit client cancellation has the distinct `CANCELED` status.
- Silent synthetic multichannel audio through the shared direction estimator, a
  granted `VOICE_FOLLOWING` state and observed base-angle movement; quiet timeout
  restores IDLE. A collision-priority state must reject subsequent voice motion.
- With `--all-animations`, every one of 33 actual registered plugins executes its
  complete trajectory at supported 2x speed, returning successful terminal result
  and feedback. Every observed joint remains finite and within the URDF limits.

The complete playlist has about 147 seconds of configured motion at 2x; service
handoff and observations add runtime. JSON evidence is emitted per scenario and
saved on success/failure. A pending or failed action is not counted as successful
feature coverage. Run against a controlled graph without unrelated random behavior
producers or duplicate joint-state publishers.

The script has been syntax-checked; actual native ROS execution remains pending
until the integrated simulator launch is ready. Physical motor braking, actual
microphone accuracy and acoustic speech recognition are outside this suite.

## Integration checkpoint (2026-10-04)

The hardware-free suite now passes 203 tests using `PYTHON=python3.12 bash scripts/test_offline.sh`. Animation duration scaling is shared through a ROS-independent helper and applied once. Local speech bridge intents include validated lamp controls; the standalone speech scenario runner checks transcript, response, status and animation publications without audio playback.

The earlier 37-scenario native animation run exposed a double speed multiplier; that has been corrected, but final native timing and browser E2E reruns are still pending. The current visual/kinematic model is the legacy four-axis RoArm model, not a validated six-axis M3 physics model. Direction estimation fixtures exercise the shared GCC-PHAT estimator, but do not establish physical microphone-array accuracy. No physical robot is attached.
