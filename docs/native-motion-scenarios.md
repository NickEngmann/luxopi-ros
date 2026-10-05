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
- With `--all-animations`, every one of 38 actual registered plugins executes its
  complete trajectory at supported 2x speed, returning successful terminal result
  and feedback. Every observed joint remains finite and within the URDF limits.

The complete playlist has about 147 seconds of configured motion at 2x; service
handoff and observations add runtime. JSON evidence is emitted per scenario and
saved on success/failure. A pending or failed action is not counted as successful
feature coverage. Run against a controlled graph without unrelated random behavior
producers or duplicate joint-state publishers.

Actual native execution is recorded below. Physical motor braking, microphone
accuracy and acoustic recognition remain outside this suite.

## Integration checkpoint (2026-10-04)

The hardware-free suite now passes 203 tests using `PYTHON=python3.12 bash scripts/test_offline.sh`. Animation duration scaling is shared through a ROS-independent helper and applied once. Local speech bridge intents include validated lamp controls; the standalone speech scenario runner checks transcript, response, status and animation publications without audio playback.

The earlier 37-scenario native animation run exposed a double speed multiplier; that has been corrected, and the final native M3 checkpoint is below. Browser/physics validation are separate evidence. Direction estimation fixtures exercise the shared GCC-PHAT estimator, but do not establish physical microphone-array accuracy. No physical robot is attached.

Completed baseline2026-10-05 UTC:37/37 cases passed (33 complete original
plugins plus4core) in190.7s. Each action succeeded with feedback and finite
URDF-bounded actual joints;2x durations matched configured durations (for example
breathing7.03s vs6.70s expected). Cancel ended CANCELED, preemption ABORTED the
old goal without duplicate joint publishers, delayedPCM direction turned the
base, quiet restoredIDLE, collision priority rejectedvoice. Source SHA256 and
retained initial runner-failure evidence are in `feature-coverage.json`; host
report `/tmp/luxopi-final-20261005T025813Z/motion.json`. New cue plugins are
outside this original33 baseline and must be rerun from the updated manifest.

## Final six-joint native checkpoint

On 2026-10-05, 12:49–12:55 UTC, all eight suites passed on the isolated
RoArm M3 graph: 42 motion cases (38 complete plugins plus four core cases),
31 state assertions across all 12 states, 10 lamp checks, three vision checks,
seven raw-sensor checks, two voice-owned command cases, four voice-cue cases,
and two watchdog fault/recovery cases. The full motion playlist took 202.332s.
Cues followed listening, acknowledge, thinking, speaking and settle. A replacement
command retained ownership through the old goal's terminal callback; raw danger
distance aborted a noninterrupting cue.

Runtime label `9144558-final-M3-config`; production source SHA256:
`e917c6e279ec659073f4b43b16de208aa3c36b8af978c7eedb6ad75e4819790a`.
Host reports: `/tmp/luxopi-final-20261005T124956Z` and
`/tmp/luxopi-final-20261005T125404Z`. The latter summary reuses the passing
motion prefix only after checking identical production and runner hashes.
A failed test incorrectly used privileged priority 100 for ordinary ERROR
recovery; the corrected priority 30 test passed. Failed evidence was retained.
Production nodes were unchanged. Per-runner hashes and timings are in
`feature-coverage.json`.

Finite bounded six-joint feedback and successful action timing do not prove
endpoint tracking: a separate physics sweep observed substantial target lag
despite action completion. Later feasible-duration retiming and reactive obstacle
avoidance changes require new validation and are outside this checkpoint.
No physical hardware or audible audio was used.
