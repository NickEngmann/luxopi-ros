# Hardware-free simulator

From any working directory run:

```sh
/home/ubuntu/smarthome/.worktrees/luxopi-ros-modernized/scripts/simulator.sh up -d --build
```

Open http://127.0.0.1:8080 locally or http://100.69.210.33:8080 from an authorized Tailscale peer. The host publishes port 8080 on `0.0.0.0`; the service has no authentication and is intended for your trusted LAN/tailnet. The dashboard runs a real ROS Jazzy graph with bounded simulated joints, the shared direction estimator, virtual lamp telemetry, sensor inputs and silent conversation previews. No serial, microphone, camera, audio or LED devices are mounted. The text backend defaults to deterministic simulation; this does not evaluate LFM inference accuracy. ROS discovery is isolated inside the container on domain 73.

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

The supplied GGUF, Moonshine model directories, and `voices/en_US-amy-low.onnx` with its JSON configuration must already exist in the AI checkout. All speech tests use supplied WAV files silently; this profile mounts no live audio devices.

An isolated combined-profile check on 2026-10-05 returned an actual LFM answer to “Why do plants need light?” in 1.019 seconds. A separate JSONL request with `synthesize: true` generated a real Piper WAV (16 kHz, 1.792 seconds) without playback. Ordinary dashboard requests currently show text and speaking previews; they do not automatically request a synthesized WAV.

Four supplied-WAV HTTP cases subsequently passed with actual Moonshine ASR, local intent/LLM processing, and ROS consumers: dance (72.853 seconds including the full retimed movement), blue lamp (1.778 seconds), 50% brightness (2.301 seconds), and a general question (3.366 seconds). Each returned to IDLE; the dance moved actual MuJoCo joint feedback and both lamp commands reached the lamp sink. Report: `/tmp/luxopi-full-audio-e2e.json`, production Python source SHA256 `e5f915e1e4779090e31f90834f5f34e0c268e882ddbcf4ca40dcbc412b91ccd6`. That prototype predates the final dashboard-unit and petting fixes, so it is separate evidence from the final default-profile regression suite. These synthetic host functional checks are not speech accuracy or CM4 latency estimates. The combined profile still needs a full browser regression run.

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

Verified on 2026-10-04: clean container build of all three ROS packages; HTTP command acceptance with recognized text and reply visible in dashboard state; four native motion/safety scenarios; ten native lamp scenarios. The lamp test exposed and verified a fix for stale color-temperature rendering. These checks do not replace full browser automation, all-animation timing, M3 physics or real hardware validation.

## Local LFM backend

For real, entirely local text inference, build the base image first, then the speech overlay:

```sh
export LUXOPI_AI_CHECKOUT=/home/ubuntu/smarthome/luxopi/luxopi-ai
# The hash-verified GGUF must already exist in that checkout's models directory.
docker compose -f compose.simulator.yml build
docker compose -f compose.simulator.yml -f compose.speech-simulator.yml up -d --build
```

The overlay compiles a pinned CPU llama.cpp server with native-only CPU extensions disabled, keeps the GGUF mounted read-only, and connects the ROS bridge to the local JSONL service. Validated animation/lamp commands bypass the language model. General questions use LFM2.5-230M. Responses and listening/thinking/speaking phases appear in the browser; audio playback remains disabled. This optional image also includes Piper and Moonshine for supplied-audio tests, without mounting live audio devices.

Browser regression checks (install the optional dependencies and Chromium first):

```sh
python3 -m pip install -r requirements-simulator-test.txt
python3 -m playwright install chromium
python3 scripts/browser_e2e.py --url http://127.0.0.1:8080
```

The checks change simulator state and save a JSON report and screenshot beneath `/tmp` by default. Run them on a dedicated simulator session.

Hardware Python utilities now use a separate `requirements-hardware.txt` with the v2 camera SDK pinned to 2.32.0.0. The actual v2 camera graph construction smoke test passed with that SDK on this arm64 host without opening a device. Simulation needs none of the optional camera/I2C/LED packages. The historical `INSTALL.sh` is not the simulator installation path.
