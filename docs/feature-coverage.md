# Feature retention and evidence matrix

The machine-readable companion `feature-coverage.json` inventories 38 actual animation plugins, 12 states, and 27 mapped DFRobot command IDs. `python3 scripts/check_feature_contract.py` rejects renamed/removed or otherwise changed inventory until reviewed. `resource/voice_command.md` describes the vendor recognition catalog; parking, QR, line tracking and other catalog entries do not imply an implemented LuxoPI behavior.

`python3 -m pytest tests/test_feature_contract.py -q` executes every registered animation plugin to generate a finite six-value trajectory with matching positive durations, and executes real lamp and gesture callbacks against a recorded output sink. All 47 cases pass. Animation generation does not prove ROS action completion, joint-following, collision cancellation or physical mechanics. Lamp sink calls prove consumer execution but do not establish electrical brightness.

| Feature | Offline consumer evidence | ROS integration status | Physical/model evidence |
|---|---|---|---|
| animations | trajectory-generation | motion-agent native action suite pending | unvalidated |
| voice_direction | actual delayed PCM→GCC angle | native joint-turn pending | unvalidated |
| voice_conversation | offline model+bridge | native speech consumer pending | unvalidated |
| collision | actual callback classification | native controller collision pending | unvalidated |
| touch_petting | state interruption only | raw touch→petting motion pending | unvalidated |
| gestures | actual passthrough callback | no gesture-motion consumer exists | unvalidated |
| vision_emotion | injected message only pending | vendor inference unmeasured | unvalidated |
| vision_person_distance | no inference claim | consumer behavior pending | unvalidated |
| lamp_on_off | actual callback+LED sink | native visual pending | unvalidated |
| brightness | actual callback+LED sink | native visual pending | unvalidated |
| color_temperature | actual callback+LED sink | native visual pending | unvalidated |
| color | all8actual RGBW colors | native visual pending | unvalidated |
| manual_interaction | physical UART/torque feature; simulator equivalent pending | native controller pending | unvalidated |
| watchdog | timer recovery pending | fault recovery pending | unvalidated |
| states | all12 actual state methods | native service scenarios pending | unvalidated |

Registered plugin names: attentive_listening, bouncy_wiggle, breathing, close, contented_sigh, curious, curious_exploration, dance, dreamy_drift, excited, folded_wiggle, gentle_sway, head_bobbing, idle, look_around_casual, neck_stretch, nod, playful, playful_bob, pondering, sad, scanning_watch, settling_adjust, shake, shoulder_shimmy, sleep, sleepy_melt, startled, stop, stretch, tail_wag, think, yawning_stretch.

Coverage must be advanced only from actual observed consumer output: an accepted action with successful terminal result and joint updates, a service result/state transition, an emitted collision result from raw sensor callbacks, a lamp sink/aura change, or a transcript/response event from the speech bridge. Publishing an input topic and receiving a dashboard echo is not consumer evidence.

Native simulator scenarios run only with `ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1`, using a controlled graph. The motion and dashboard suites are separate from this manifest. Their observed results should update the ROS-status fields once run; pending fields are intentional and do not represent successful integration.

Unvalidated physical features include microphone wiring/acoustic VAD accuracy, actual motor torque adaptation, real stopping distance, LEDs/speaker electronics, camera stereo calibration and vendor neural-network inference. Delayed-array direction fixtures exercise the shared estimator, but room acoustics and real source locations are not established.

Native environment check: the feature, direction, collision-fault and state
suites also passed together inside the arm64 `ros:jazzy-ros-base` container:
**134 passed in 1.91 seconds**. Sources were staged under
`/tmp/luxopi-feature-smoke`, leaving the running ROS graph untouched. This checks
native imports and deterministic consumer logic; it does not advance ROS action,
service transport, dashboard rendering or physical-model evidence statuses.
