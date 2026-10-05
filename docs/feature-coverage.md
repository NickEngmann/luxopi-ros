# Feature retention and evidence matrix

The machine-readable companion `feature-coverage.json` inventories 38 actual animation plugins, 12 states, and 27 mapped DFRobot command IDs. `python3 scripts/check_feature_contract.py` rejects renamed/removed or otherwise changed inventory until reviewed. `resource/voice_command.md` describes the vendor recognition catalog; parking, QR, line tracking and other catalog entries do not imply an implemented LuxoPI behavior.

`python3 -m pytest tests/test_feature_contract.py -q` executes every registered animation plugin to generate a finite six-value trajectory with matching positive durations, and executes real lamp and gesture callbacks against a recorded output sink. All 47 cases pass. Animation generation does not prove ROS action completion, joint-following, collision cancellation or physical mechanics. Lamp sink calls prove consumer execution but do not establish electrical brightness.

| Feature | Actual native ROS evidence | Physical/model scope |
|---|---|---|
| animations | passed: original33 full actions at2x plus cancellation/preemption/finite joint limit checks | unvalidated |
| voice_direction | passed: synthesized delayedPCM through shared estimator to VOICE_FOLLOWING/base joint turn and quiet IDLE | unvalidated |
| voice_conversation | passed: supplied-WAV HTTP→actual Moonshine tiny→boundedintent/localLFM→transcript/response/motion/lamp;4functional fixtures returnIDLE | unvalidated |
| collision | passed: raw distance classifier causes COLLISION_AVOIDING,20 actualjoint hold frames, restores USER_CONTROL | unvalidated |
| touch_petting | passed: raw top touch→PETTING→folded_wiggle action475joint frames and releaseIDLE; all3side/bottom outputs | unvalidated |
| gestures | passed: left/right/up/down actual /gestures passthrough; no movement consumer exists | unvalidated |
| vision_emotion | passed: injected detection→shared sad policy→EMOTION_REACTING→real sad action259joint frames; neural inference not tested | unvalidated |
| vision_person_distance | passed:1.2m detection output, explicit person loss and3s stale expiry; no neural inference claim | unvalidated |
| lamp_on_off | passed: actual virtual lamp off/on telemetry | unvalidated |
| brightness | passed: actual virtual brightness0.25→0.5 | unvalidated |
| color_temperature | passed: actual virtual warm1.0 andneutral0.5 RGBW | unvalidated |
| color | passed: actual virtual red/blue/green/white RGBW; all8colors offline | unvalidated |
| manual_interaction | passed: USER_CONTROL manual joint target produces actual controller motion; torque/UART unvalidated | unvalidated |
| watchdog | passed: integrated monitor-only node; isolated native missing heartbeat fault then fresh4joint+IDLE clears fault | unvalidated |
| states | passed:28 real service assertions across12 states,priority/restoration/recovery/invalid/terminal guards | unvalidated |

Registered plugin names: attentive_listening, bouncy_wiggle, breathing, close, contented_sigh, curious, curious_exploration, dance, dreamy_drift, excited, folded_wiggle, gentle_sway, head_bobbing, idle, look_around_casual, neck_stretch, nod, playful, playful_bob, pondering, sad, scanning_watch, settling_adjust, shake, shoulder_shimmy, sleep, sleepy_melt, startled, stop, stretch, tail_wag, think, yawning_stretch.

Coverage must be advanced only from actual observed consumer output: an accepted action with successful terminal result and joint updates, a service result/state transition, an emitted collision result from raw sensor callbacks, a lamp sink/aura change, or a transcript/response event from the speech bridge. Publishing an input topic and receiving a dashboard echo is not consumer evidence.

Native simulator scenarios run only with `ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1`, using a controlled graph. The motion and dashboard suites are separate from this manifest. The matrix now records the completed native baseline; subsequent new capabilities require another native run.

Unvalidated physical features include microphone wiring/acoustic VAD accuracy, actual motor torque adaptation, real stopping distance, LEDs/speaker electronics, camera stereo calibration and vendor neural-network inference. Delayed-array direction fixtures exercise the shared estimator, but room acoustics and real source locations are not established.

Native environment check: the feature, direction, collision-fault and state
suites also passed together inside the arm64 `ros:jazzy-ros-base` container:
**134 passed in 1.91 seconds**. Sources were staged under
`/tmp/luxopi-feature-smoke`, leaving the running ROS graph untouched. This checks
native imports and deterministic consumer logic; it does not advance ROS action,
service transport, dashboard rendering or physical-model evidence statuses.

## Completed native baseline

On 2026-10-05 UTC the healthy isolated arm64 Jazzy Compose graph passed 37
motion cases (33 complete original plugins plus4 core scenarios) in190.7s,28
service assertions across12 states,10 lamp changes,3 vision checks,7 raw sensor
checks,2 voice-ownership checks and2 watchdog fault/recovery checks. Requested
2x animation speed was verified against full configured durations.

The runtime source SHA256 was
`bb04a2c9849831237f9c236df5b612dc0555fbc15a044bc2db4cae1787c8a8d5`
(runtimee34f4d7). Production nodes were unchanged during the suite. Script-only
corrections waited for action subscriber state caches, compared Float32 distances
with tolerance, and preserved the existing crossed side-touch calibration. Initial
failed test runs were retained alongside passing evidence, rather than discarded.
Reports were copied to host `/tmp/luxopi-final-20261005T025813Z` and
`/tmp/luxopi-final-20261005T030502Z` before any rebuild. This is consumer/transport
evidence, not room-acoustic recognition reliability or physical motion accuracy.

Side FSR topics retain the legacy wiring calibration: raw `head_left` produces a
right collision and `head_right` a left collision. `swap_touch_sides=true` names
that default explicitly; false selects matching logical channels. Physical channel
orientation needs verification on the actual robot before changing the default.

## Supplied-audio functional HTTP check

`python3 scripts/audio_e2e.py --url http://127.0.0.1:8081 --fixtures DIR`
passed4 fixtures through the actual local Moonshine tiny streaming recognizer,
bounded command parser or LFM2.5-230M, and ROS consumers. Piper generated WAVs
were uploaded as `audio/wav`; no microphone or playback device was opened. Dance
completed with actual joint movement in8.77s; blue lamp reached the actual RGBW
sink in1.53s; brightness changed0.25→0.5 in1.65s; the plant question received a
local-model response in1.84s. These totals include HTTP polling and action/speech
completion; they are not Pi latency or recognition accuracy measurements. All
four scenarios released ownership and returnedIDLE. UploadedUUID WAVs were
removed from the shared directory after processing.

The original synthetic brightness clip produced the erroneous transcript
`10% set brightness to50%.` and correctly did not execute the command. Its
failed report is retained; a polite equivalent synthesized at0.85x speed
recognized cleanly. Three synthetic variants were inspected to pick that
functional fixture. This sensitivity is an explicit limitation, not evidence
that recognition is reliable across human speakers. Numeric `50%` and spoken
`fiftypercent` are accepted as the same fixture meaning; extraneous prefixes
remain failures. Reports: `/tmp/luxopi-audio-http-e2e.json` and
`/tmp/luxopi-audio-http-e2e-initial-failure.json`; image
`sha256:13195690b9e95ff783366087cc0f4ef79091266aaf076ab1e1f4c61a3abaa100`.
