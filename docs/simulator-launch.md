# Hardware-free simulator

From any working directory run:

```sh
/home/ubuntu/smarthome/.worktrees/luxopi-ros-modernized/scripts/simulator.sh up -d --build
```

Open http://127.0.0.1:8080 locally or http://100.69.210.33:8080 from an authorized Tailscale peer. The host publishes port 8080 on `0.0.0.0`; the service has no authentication and is intended for your trusted LAN/tailnet. The dashboard runs a real ROS Jazzy graph with bounded simulated joints, the shared direction estimator, virtual lamp telemetry, sensor inputs and conversation feedback. No robot serial, camera, audio-output, or LED devices are mounted. The default text backend is deterministic and does not evaluate LFM inference accuracy. ROS discovery is isolated inside the container on domain 73.

## SSH access

The simulator stays in a detached container after your SSH session closes. Its restart policy also starts it after Docker/host restarts unless you explicitly stop it. Connect to this host using your existing SSH credentials:

```sh
ssh ubuntu@100.69.210.33
/home/ubuntu/smarthome/.worktrees/luxopi-ros-modernized/scripts/simulator.sh ps
/home/ubuntu/smarthome/.worktrees/luxopi-ros-modernized/scripts/simulator.sh logs --tail 100
```

For browser access through SSH, run this on your own computer, leave the connection open, then open http://127.0.0.1:18080:

```sh
ssh -N -L 18080:127.0.0.1:8080 ubuntu@100.69.210.33
```

The helper accepts `--mode base`, `--mode speech`, `--mode audio`, `--mode physics`, or `--mode full` before the Compose command. Speech/audio/full modes find a sibling `luxopi-ai` checkout, including the canonical sibling when invoked from a Git worktree. Set `LUXOPI_AI_CHECKOUT` to override that location. Each mode resolves its overlay files by absolute checkout path, including when invoked from another directory. Physics/full are optional development backends; consult their validation evidence before treating their motion as calibrated. Build the base image before speech or physics, and both optional images before full.

The helper resolves its checkout from its own location. Container launches use `/workspace`; installed UI modules, meshes, and animation assets resolve from their package locations rather than the SSH shell’s working directory. Relative Compose paths resolve against the checkout. SSH authentication uses your existing account; this change does not create credentials.

Run native behavior checks:

```sh
docker compose -f compose.simulator.yml exec -T simulator bash -c \
  'source /opt/ros/jazzy/setup.bash && source /workspace/install/setup.bash && python3 scripts/run_motion_scenarios.py'
docker compose -f compose.simulator.yml exec -T simulator bash -c \
  'source /opt/ros/jazzy/setup.bash && source /workspace/install/setup.bash && python3 scripts/run_lighting_scenarios.py'
```

Stop with `docker compose -f compose.simulator.yml down`. The image builds natively and the current ROS base tag can receive upstream updates; it is not a fully frozen dependency environment.

The default profile uses the six named M3 axes and pinned vendor visual geometry. The legacy four-axis model remains selectable for comparison. The default backend is bounded kinematics; the optional MuJoCo backend owns actual physics feedback and retains vendor inertias and collision meshes. Camera controls feed the shared behavior consumers; synthetic detections do not evaluate vision-model accuracy. Sensor warnings now constrain the trajectory through the same policy used by the hardware path. Physical mount transforms, sensor range and stopping margins still need calibration on the actual robot.

The M3 preview includes a four-strand articulated cable-harness proxy routed
from the base to the tool frame. Its service loops update with the live joint
angles, so cable movement can be inspected during simulated gestures and
direction turns. The route and bend radii are illustrative: the actual wire
paths must be measured before hardware collision or cable-life claims can be
made. `scripts/wiring_browser_e2e.py` checks that the rendered cable geometry
updates as the arm changes pose. The physics launch also forwards synthetic
idle/emotion timing arguments into the shared behavior graph; the browser E2E
verifies that autonomy can be paused and resumed through the dashboard.

The isolated MuJoCo replay exercised all 38 animations and 458 keyframes with mapped, retimed commands and actual endpoint settlement. All keyframes settled within 0.00053 rad in that run, with no effort saturation or joint-bound violations. This is a synthetic simulation result, not a hardware accuracy or performance measurement. See [virtual obstacle sensors](virtual-obstacle-sensors.md) for the optional world-ray fixture; enable it explicitly, and keep it disabled when injecting raw sensor tests.

An optional [continuous timing prototype](continuous-animation-timing.md) preserves
waypoints while avoiding a full stop at each stage. Its separate physics sweep
halved playlist time approximately; live ROS regression coverage is tracked there.

Build the optional combined local speech/physics profile with:

```sh
scripts/simulator.sh build
scripts/simulator.sh --mode speech build
scripts/simulator.sh --mode physics build
scripts/simulator.sh --mode full up -d --build
```

The supplied GGUF, Moonshine model directories, and `voices/en_US-amy-low.onnx` with its JSON configuration must already exist in the AI checkout. The full profile accepts an explicit browser recording or a supplied WAV, sends it through local Moonshine and the normal ROS conversation graph, and makes locally synthesized Piper replies available in an audio player. The browser asks for microphone access only when Record is pressed. Browser microphone access requires HTTPS or a loopback origin; for remote SSH use, open the tunnel at `http://127.0.0.1:18080` as shown above. Replies play only when the user presses the player controls; tests do not play sound through host speakers.

An isolated combined-profile check on 2026-10-05 returned an actual LFM answer to “Why do plants need light?” in 1.019 seconds. A separate JSONL request with `synthesize: true` generated a real Piper WAV (16 kHz, 1.792 seconds) without playback. Ordinary dashboard requests currently show text and speaking previews; they do not automatically request a synthesized WAV.

Four supplied-WAV HTTP cases subsequently passed with actual Moonshine ASR, local intent/LLM processing, and ROS consumers: dance (72.853 seconds including the full retimed movement), blue lamp (1.778 seconds), 50% brightness (2.301 seconds), and a general question (3.366 seconds). Each returned to IDLE; the dance moved actual MuJoCo joint feedback and both lamp commands reached the lamp sink. Report: `/tmp/luxopi-full-audio-e2e.json`, production Python source SHA256 `e5f915e1e4779090e31f90834f5f34e0c268e882ddbcf4ca40dcbc412b91ccd6`. That prototype predates the final dashboard-unit and petting fixes, so it is separate evidence from the final default-profile regression suite. These synthetic host functional checks are not speech accuracy or CM4 latency estimates.

The final default-profile dashboard/browser run against source revision
`09b16820ba36469ee972198cac62fad312d707c2` passed all 28 scenarios in
109.7 seconds. It loaded all seven M3 mesh assets, exercised both robot views,
all 12 FSM state requests, six-axis manual feedback, the lamp sink, animation
cancellation, direction estimation, collision hold/clear/replan, and invalid
request handling. There were no page errors, console errors, or failed HTTP
requests. Report and screenshot: `/tmp/luxopi-browser-e2e-release.json` and
`/tmp/luxopi-browser-e2e-release.png`. The separate container-owned pause/restart
check also verified stale-state health failure and recovery after the state
manager restarted; see [paused-heartbeat health test](paused-heartbeat-health.md).
This run covers the default kinematic dashboard, not the optional combined
speech profile or calibrated physical sensors.

The 3D preview is 20% taller than before (312 px, 282 px on narrow screens) and
shows a fixed fake desk, matching five static desk collision
geometries in the MuJoCo scene. Hover any modeled mesh or added locator to see
its frame and role. The M3 hand TCP is marked as a virtual tool center. Three
collision/range sensor locators sit at the link2/link3 connector (left, right,
and rear-facing), with another at hand TCP. A three-optic Luxonis camera proxy
sits at the gripper end; it uses the published OAK-D Lite 91 × 28 × 17.5 mm
body size and 75 mm stereo baseline, since the checked-in code does not identify
the exact attached SKU. The locations and optical direction are placement
guides and need measuring against the real robot.

Two animated, hovering pixel-ring guides sit near hand TCP: 60 pixels at 157.5 mm
diameter and 16 pixels at 44.5 mm. Those sizes follow the [60-pixel ring
reference](https://www.adafruit.com/product/1768) and [16-pixel ring
reference](https://www.adafruit.com/product/2856). The LED colors and effects are
rendered from the existing `/luxo/light_state` state-manager telemetry, including
solid, breathing, spinning, and bouncing patterns. The rings are code-generated
3D geometry so individual LEDs can animate; they are floating placement guides,
not measured CAD mounts. The front/left/right virtual sensor
controls place a randomly chosen checked-in STL prop (`crate`, `wedge`, `can`,
`cone`, or `rock`) on the desk and feed the ordinary range-classifier inputs.
In MuJoCo, each held stimulus also enables a matching conservative box collider
under its rendered STL; the mesh remains the visible prop and the collider is
an approximation for contact tests. Releasing the control removes the prop and
disables its collider. The tabletop itself is collidable.
`scripts/generate_simulator_prop_stls.py` recreates the small ASCII STL set.

The sensor/camera/ring hover and LED rendering run passed all 30 browser E2E
scenarios against MuJoCo in 90.2 seconds. The expanded 2026-10-06 regression run
passed 38/38 browser scenarios in 226.9 seconds with zero page, console, or
request errors. It verifies all twelve state options, a single APDS9960
proximity send entering and clearing collision recovery, an emotion event
driving a complete animation, an uncanceled animation completing, and automatic
idle movement after quiet. It also confirms live state-manager telemetry changes
both rendered LED rings to the reported RGB color. The [browser report](validation/2026-10-06/behavior-regression-browser-e2e.json)
and [31/31 state ownership/recovery scenarios](validation/2026-10-06/behavior-regression-state-e2e.json)
are checked in. The desk/prop browser run and Marisol Talk API audio benchmark are
recorded in [the desk validation report](validation/2026-10-06/hover-desk-stl-browser-e2e.json)
and [Marisol Talk benchmark](validation/2026-10-06/marisol-talk-benchmark.json).
The latter sends five locally Piper-synthesized commands sequentially through
Marisol's `/api/talk/turn`; it checks ASR transcript and response latency, drops
the generated reply audio, and does not play any audio. Its five exact matches
are an API/path smoke benchmark (ASR 0.16–0.34 s; full request mean 1.51 s,
p95 1.785 s), not an estimate of accuracy on human speech.
The full local browser-microphone → Moonshine → command → Piper WAV path also
passed with “Please dance” recognized exactly and an idle return in 6.31 s;
the test now requires a new response-audio ID so old dashboard state cannot
make a later recording appear to pass. See
[the browser speech result](validation/2026-10-06/local-browser-speech-e2e.json).
An additional Marisol Talk run used three Kokoro voices (Bella, UK Emma, and
low-breathy Nicole) at 0.9–1.1× speed. All three “Please turn the lamp on”
transcripts were exact; request latency averaged 1.63 s. The voices were
synthesized by Marisol's own preview API, so this broadens voice coverage but
is still a synthetic pipeline check; see
[the multivoice results](validation/2026-10-06/marisol-multivoice-benchmark.json).

The dashboard now has a 1×/2×/3× clock selector. It speeds the MuJoCo integration,
animation timelines, and autonomous idle/emotion timers together while keeping
the physics integration step fixed for numerical stability. Select 2× or 3× in
the header to run longer scenarios sooner; CPU load can limit the achieved wall
clock speed. A measured E2E confirmed 1.00×, 2.00×, and 3.00× simulated seconds
per wall second; see the [time-scale report](validation/2026-10-06/simulator-time-scale-e2e.json).
The `simulator_autonomy` event can temporarily pause synthetic idle activity
for deterministic tests; pausing also cancels an idle action already in flight
and clears a synthetic person-presence cue. The motion controller reconciles a
late restored `VOICE_FOLLOWING` state after its inactive signal, so collision
completion cannot leave a finished voice session stuck active. The dedicated
[dashboard control E2E report](validation/2026-10-06/dashboard-controls-e2e.json)
records 107 passing browser scenarios, including every enabled button, all
twelve forceable FSM states and IDLE recovery, all sensor inputs, every light
color, action cancellation, both views, each clock scale, and refresh-safe
touch, petting, and obstacle toggles. Front/left/right range dropouts each
triggered a named stale-coverage hold and recovered after fresh ray samples
resumed; the controller then kept motion at `hold_replan` until a fresh target
arrived. The physics profile now starts the MuJoCo-mounted synthetic range
sensors by default, which keeps required front/left/right coverage live and
makes the dropouts traverse the same classifier and motion-policy path used by
the virtual obstacle scene. WAV upload and microphone controls were verified
disabled in the silent physics-only profile.
The combined MuJoCo browser suite passed 22 scenarios in 88.7 seconds,
including seven-mesh loading, live-frame hover labels, command/reply text,
direction finding, collision stop/clear, and a randomized desk STL whose
matching physics collider was observed enabled then released. Browser console
and request errors were zero. The full package tests passed 278/278. These
deterministic E2E checks ran with autonomous idle animation temporarily off;
the service was restored to its normal autonomous setting afterward and a
live `neck_stretch` idle animation was observed with `/healthz` healthy.

The combined local speech + MuJoCo profile was subsequently rebuilt from
`862486a80b532ebd093d6733c0467615229559df` and passed 27 browser scenarios in
116.1 seconds with `--expected-backend mujoco`. The dashboard reported
`MuJoCo M3 dynamics · measured ROS joint states`; six-axis feedback changed
during motion, and the conversation, lamp, direction, collision hold/replan,
manual pose, all FSM requests, and request validation scenarios passed. There
were no page, console, or failed HTTP requests. Report and screenshot:
`/tmp/luxopi-browser-e2e-combined-mujoco.json` and
`/tmp/luxopi-browser-e2e-combined-mujoco.png`. Supplied-WAV recognition remains
covered by the separate silent four-case run above; this browser suite does not
measure speech accuracy or play synthesized audio.

The expanded default MuJoCo browser regression now passes 38 recorded cases
(37 executed and one optional state-heartbeat pause case skipped), with no page
exceptions, console errors, or failed requests. It covers sensor hover labels,
the collision-stop/fresh-intent recovery path, a single APDS event, emotion
animation, randomized STL collider release, and autonomous idle motion after a
clean pause/resume. The [saved report](validation/2026-10-06/mujoco-browser-edge-regression-e2e.json)
records per-scenario evidence. The default physics profile also keeps the
synthetic ray fixture enabled; raw-input tests can mute an individual ray with
the dashboard dropout toggle.

Verified on 2026-10-04: clean container build of all three ROS packages; HTTP command acceptance with recognized text and reply visible in dashboard state; four native motion/safety scenarios; ten native lamp scenarios. The lamp test exposed and verified a fix for stale color-temperature rendering. These checks do not replace full browser automation, all-animation timing, M3 physics or real hardware validation.

## Local LFM backend

For real, entirely local text inference, build the base image first, then the speech overlay:

```sh
export LUXOPI_AI_CHECKOUT=/home/ubuntu/smarthome/luxopi/luxopi-ai
# The hash-verified GGUF must already exist in that checkout's models directory.
docker compose -f compose.simulator.yml build
docker compose -f compose.simulator.yml -f compose.speech-simulator.yml up -d --build
```

The overlay compiles a pinned CPU llama.cpp server with native-only CPU extensions disabled, keeps the GGUF mounted read-only, and connects the ROS bridge to the local JSONL service. Validated animation/lamp commands bypass the language model. General questions use LFM2.5-230M. Responses and listening/thinking/speaking phases appear in the browser. The `full` profile also includes Piper and Moonshine, so browser or supplied audio can exercise speech-to-speech locally; generated response WAVs are retained in a bounded local cache for the browser player. Nothing is played automatically or routed to a physical speaker.

Browser regression checks (install the optional dependencies and Chromium first):

```sh
python3 -m pip install -r requirements-simulator-test.txt
python3 -m playwright install chromium
python3 scripts/browser_e2e.py --url http://127.0.0.1:8080
python3 scripts/dashboard_controls_e2e.py --url http://127.0.0.1:8080
python3 scripts/simulator_time_scale_e2e.py --url http://127.0.0.1:8080
python3 scripts/simulator_boundary_e2e.py --url http://127.0.0.1:8080 \
  --output docs/validation/$(date -u +%F)/simulator-boundary-e2e.json
```

The boundary suite stresses concurrent request retries (exactly-once enqueue
within the one-hour replay window and 1,024-ID cache), request-ID conflicts, bounded ingress audit
retention, concurrent queue load/drain, invalid API payloads, inclusive sensor
and DOA limits, all four touch input edges, and simultaneous left/right hazard
clearance. `GET /api/diagnostics` exposes graph health plus aggregate accepted,
duplicate, rejected, queue-full, queue-depth, and recent-event metadata; the
audit ring stores at most 100 metadata-only entries. Request IDs are optional,
limited to 96 safe characters, and should be stable across retries. Reusing one
for a different payload returns HTTP 409. Replay IDs and diagnostic counters
are process-local and clear when the dashboard restarts. The ID cap and expiry
bound memory use; deployments requiring retry protection across restarts need
persistent request storage. These are software-simulator checks; they do not
calibrate physical sensors or establish the arm's real stopping distance.

The 2026-10-06 live boundary run passed 22 cases, including 16 concurrent copies
of one request, 0°/359° direction inputs, all four touch sensors at 0 and 255,
left+right collision hold/recovery, malformed payload rejection, and simulator
cleanup. The broader Chromium sweep passed 39 scenarios with no browser or
request errors, the control sweep passed 108/108, and a 1,024-request flood
drained with the graph healthy. All flood requests returned HTTP 202, so this
does not prove the 64-slot queue's HTTP 429 full-queue branch. Simulated clock
ratios were 1.00×, 2.01× and 3.00×. Reports:
[boundary E2E](validation/2026-10-06/simulator-boundary-e2e.json),
[browser](validation/2026-10-06/boundary-browser-e2e.json),
[controls](validation/2026-10-06/boundary-dashboard-controls-e2e.json),
[queue flood](validation/2026-10-06/boundary-queue-stress-e2e.json), and
[clock sweep](validation/2026-10-06/boundary-simulator-time-scale-e2e.json).

To verify the browser microphone → ASR → response → WAV-player path without
opening a host audio device, provide a recognizable WAV fixture and run:

```sh
python3 scripts/browser_audio_e2e.py --input-wav /path/to/speech.wav \
  --expected-text "dance" --url http://127.0.0.1:8080
```

The test feeds the fixture to Chromium's fake microphone, records through the
same browser controls, checks the recognized text and reply, and fetches the
Piper WAV. It verifies the audio asset without playing it. Both left and right
side-warning retreats are checked against the M3 robot frame: positive base
yaw turns the forward gripper left (+Y), so a left-side obstacle retreats with
negative yaw and a right-side obstacle with positive yaw. The retreat is a
small avoidance adjustment, not a full route planner; sensor mounts still need
physical calibration before using these directions on the robot.

The checks change simulator state and save a JSON report and screenshot beneath `/tmp` by default. Run them on a dedicated simulator session.

Hardware Python utilities now use a separate `requirements-hardware.txt` with the v2 camera SDK pinned to 2.32.0.0. The actual v2 camera graph construction smoke test passed with that SDK on this arm64 host without opening a device. Simulation needs none of the optional camera/I2C/LED packages. The historical `INSTALL.sh` is not the simulator installation path.

## Autonomous live motion

The physics and full MuJoCo profiles turn on `sim_activity_driver` by default, so the model
starts an idle animation after seven seconds at rest and rotates among the
registered idle-animation library. Synthetic person/emotion events use the
same simulated-camera topics and shared emotion reaction path. Configure the
behavior with `LUXOPI_SIM_AUTONOMY`, `LUXOPI_SIM_IDLE_AFTER`,
`LUXOPI_SIM_IDLE_INTERVAL`, and `LUXOPI_SIM_EMOTION_INTERVAL`; autonomy is off
for the minimal and hardware launch profiles. See
[the live activity E2E report](validation/2026-10-06/live-animation-e2e.json).

The final native MuJoCo simulator sweep on 2026-10-07 passed all nine suites:
complete animation/motion inventory, state transitions, lights, vision, sensor
reactions, voice-triggered motion/cues, watchdog recovery, and 11 avoidance
cases. The sensor and avoidance runners pause autonomous world-generated
sensor updates while injecting controlled readings, preventing races between
two publishers. Combined results are in
[the final native suite report](validation/2026-10-07/native-full-suite.json).
The adjacent intermediate summaries retain the initial failing runs that led
to the isolation fixes; the combined report records the final rerun results.
