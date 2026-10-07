# Hardware-free validation artifacts

These are saved JSON reports from silent, isolated LuxoPI simulator checks.
They contain synthetic fixtures and simulator telemetry, not household audio or
backup archives. Keeping them here makes the evidence survive temporary-file
cleanup. Original logs and failed attempts remain local under `/tmp`.

Each native report includes its production source and runner hashes. The full
continuous report uses a verified passing motion/state prefix; its provenance
manifest links the frozen `123025b` source to the original run. The later core
reports test the `8e8ba06` lifecycle changes and do not repeat that full playlist.
The final UI reports additionally test persistent lighting drafts, actual
color-temperature acknowledgement, and explicit health reasons.

Browser reports record one optional in-browser heartbeat test as skipped; the
separate guarded pause and restart reports verify that fault path. Count that
entry as skipped, not as another executed behavior test. All other recorded
checks passed without page, console or failed HTTP-request errors.

The guarded health check ([health-heartbeat-pause-e2e.json](health-heartbeat-pause-e2e.json))
paused only the identified state-manager process inside the isolated simulator:
`/healthz` returned 503 with `stale_state`, then returned healthy after that
same process resumed. The container recovery check
([container-restart-recovery-e2e.json](container-restart-recovery-e2e.json))
terminated that simulator-only process and verified Compose restarted the
container and restored all required graph nodes and fresh state/joint telemetry.
The final broad browser regression
([final-browser-regression-e2e.json](final-browser-regression-e2e.json))
passed 39 recorded scenarios with no page errors, console errors, or failed
requests. It verifies retained autonomy status on initial dashboard join and
after container restart; the separate health-pause report executes the
optional heartbeat-fault case.

The dashboard control report ([dashboard-controls-e2e.json](dashboard-controls-e2e.json))
contains 107 passing cases. In addition to the full button/FSM sweep, it checks
that refresh restores latched touch, petting, and obstacle inputs so the first
click releases them, then drops each front/left/right range stream and verifies
the motion controller names that stale sensor in its safety hold before fresh
simulated ray samples restore coverage.

The expanded dashboard report ([dashboard-animation-race-e2e.json](dashboard-animation-race-e2e.json))
contains 108 passing cases. It additionally queues an animation start and
cancel before the ROS action acknowledgment, verifies that the accepted goal
is canceled, and waits for every state-selector request to appear in live FSM
telemetry before resetting to idle. This caught and fixed a real lost-cancel
race in the dashboard's asynchronous action handling.

The expanded browser regression ([mujoco-browser-edge-regression-e2e.json](mujoco-browser-edge-regression-e2e.json))
has 38 passing recorded cases: 37 executed and one optional heartbeat-pause
case skipped. It verifies the 3D sensor hover targets while motion is paused,
the stale-coverage/fresh-intent recovery path, APDS and emotion inputs, random
STL collider release, and autonomous idle movement after pause/resume. Page,
console, and request error counts were zero.

Home and gesture reports observe actual joint feedback and completed action or
state transitions. Speech fixtures use real local models but do not measure
human recognition accuracy. None of these files establishes physical sensor
calibration, safe real-world stopping distance, or CM4/Hailo latency.

The final MuJoCo checks also include the real image-upload→OpenVINO→ROS emotion
reaction flow (`vision-browser-e2e.json`) and eight touch/petting/collision
scenarios (`petting-zones-mujoco-e2e.json`). The positive face image entered
`EMOTION_REACTING` with 0.0285 rad maximum joint displacement in 3.111 seconds;
the blank image cleared mood to IDLE. Each simulated head-top, top-front, and
antenna/hand-gripper pad moved the model and returned to IDLE. The latter two
remain simulation compatibility pads; the report does not establish real pad
placement or wiring.

The live-activity regression report ([live-animation-e2e.json](live-animation-e2e.json)) verifies that the full MuJoCo profile autonomously starts an idle animation, that a single antenna-pad click sustains and moves the real petting animation before a second click releases it, and that a held virtual side obstacle reaches the collision classifier and produces a bounded retreat. These browser checks use joint feedback as evidence that the rendered mesh has moved; simulated sensor geometry is not physical calibration.
The same live run also produced a synthetic surprise observation; the shared camera consumer selected and executed the registered curious animation.

## Full live simulator round

The current MuJoCo rebuild was exercised with the 38-action motion playlist,
11 avoidance and hold/replan scenarios
([avoidance-current-e2e.json](avoidance-current-e2e.json)), eight touch and
petting cases ([petting-current-e2e.json](petting-current-e2e.json)), four
direction gestures ([gesture-current-e2e.json](gesture-current-e2e.json)), 20 dashboard/browser checks
([browser-current-e2e.json](browser-current-e2e.json)), and 102 package tests.
All recorded live runs passed. The browser report had no page exceptions,
console errors, or failed HTTP requests. The package tests ran on ROS domain 74
to keep their fixtures isolated from the live dashboard and simulator on
domain 73. The autonomous idle driver was restored after the tests.

The M3 preview had a real visual bug: Three.js `XYZ` Euler composition did not
match the vendor URDF fixed-axis roll/pitch/yaw frames, displacing link 3 onward
and the hand. The display now uses the matching `ZYX` composition. The live
browser test compares all eight rendered link/end-effector origins with the
vendor FK at the same six measured joint values, within 0.1 mm
([browser-current-e2e.json](browser-current-e2e.json)). The gripper asset is a
single rigid visual, so its finger aperture is not animated independently; the
application holds the sixth (gripper) joint at its home angle during generic
animations. A close-up preview screenshot is saved as
[browser-current-e2e.png](browser-current-e2e.png).

The obstacle run uncovered and fixed a physics-status issue: a hold previously
reported its internal command limiter state instead of waiting for measured
MuJoCo position and velocity to settle. A new hold now begins from fresh
measured positions and velocities, uses a stationary latched target, and only
reports frozen after the measured body and command trajectory settle. Stop
distance in MuJoCo includes the torque-limited servo's small tracking transient;
these simulated stopping bounds do not establish physical braking performance.

The final raw sensor-to-motion run
([avoidance-final-regression-e2e.json](avoidance-final-regression-e2e.json))
passed all 11 scenarios, including warning redirects on each axis, danger and
two-sided holds, contact, stale-sensor dropout, fresh-clear replanning, and an
active animation that continues under warning and aborts on danger. The fixture
publisher was disabled for this run so the test's injected raw ranges were the
only sensor source. The controller now keeps the collision-avoidance state
aligned with the severity policy's clear dwell; legacy Bool edges cannot drop
the state while an atomic warning remains latched. The dashboard controls suite
was also rerun: all 108 scenarios passed, but it recorded one transient browser
`Failed to fetch` error during the long sweep. The simulator health endpoint
was healthy after cleanup. A subsequent full browser regression
([browser-doa-regression-e2e.json](browser-doa-regression-e2e.json)) passed all
39 recorded scenarios with zero page errors, console errors, or failed requests;
it included estimator input through the Sound Direction panel and confirmed
the simulator healthy with 15 graph nodes afterward.

The existing DOA path is now explicitly covered for cable-safe motion. A
synthetic ReSpeaker array feeds the shared GCC-PHAT estimator, whose corrected
angle drives the shared motion controller; base yaw selects the shortest
equivalent target within its ±180° vendor range. The 170° wraparound and quiet
recovery case is recorded by the motion scenario suite. See
[direction-estimation.md](../../direction-estimation.md) for calibration
limits: these tests do not validate the physical ReSpeaker wiring, room
acoustics, or the assembled robot's actual cable routing.
The dedicated native ROS report
([doa-cable-safe-motion-e2e.json](doa-cable-safe-motion-e2e.json)) passed
source-to-motion, +170° seam wraparound, quiet-to-IDLE, and collision-priority
checks. At a 170° microphone angle, the estimated robot target was −171.26°;
from +170.08° yaw, simulated motion chose +179.96° (about a 10° turn) within
the vendor's ±180° joint limits. The rebuilt package suite passed 282 tests
with one hardware-dependent sensor-node test skipped.

The follow-up DOA ownership regression
([doa-animation-overlay-e2e.json](doa-animation-overlay-e2e.json)) passed its
four native ROS scenarios: normal audio-to-motion and quiet recovery, shortest
cable-safe turn, a synthetic speaker turn as a dance action starts, and collision
priority. During the dance, base yaw followed DOA while the FSM remained
ANIMATING, the remaining animation joints continued moving, the action completed
successfully, and the FSM returned to IDLE. The focused motion-policy tests now
pass 29 cases, including invalid/stale angles and state ownership. This report
uses synthetic audio in MuJoCo only; no physical robot or speaker was involved.
The latest full ROS package run reported 295 passed and one failure in the
synthetic sensor-node test `test_actual_m3_feedback_generates_front_and_side_raw_samples_and_stales_out`;
that same test passed when rerun alone, so it appears to be fixture interference
in the combined suite rather than a DOA regression.

The Marisol Talk audio run
([talk-api-audio-e2e.json](talk-api-audio-e2e.json)) generated four command and
question WAVs via Marisol `/api/talk/say`, checked the same WAVs with
`/api/talk/turn`, then uploaded them to the current LuxoPi full simulator's
`/api/audio`. LuxoPi recognized all four, returned a reply, exercised dance,
lamp color and brightness consumers, answered a question, and returned each
turn to IDLE. First transcript averaged 0.53 s and first response averaged
0.99 s; full turn time averaged 13.45 s because it includes the complete dance
animation (38.08 s). Marisol's own ASR was exact on three of four clips; it
heard “Please dance” as “Plays dance,” while LuxoPi heard it exactly. No reply
audio was played. The separate four-angle report
([doa-talk-angle-sweep-e2e.json](doa-talk-angle-sweep-e2e.json)) measured
0°, 90°, 180° and 270° through synthetic six-channel audio and the same
estimator/motion path; all four yaw targets settled within 0.35° and returned
to IDLE. These generated fixtures validate software integration, not human
recognition, real room acoustics or physical microphone direction accuracy.
