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
