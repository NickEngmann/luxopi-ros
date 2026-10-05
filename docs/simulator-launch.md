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

The helper accepts `--mode base`, `--mode speech`, `--mode audio`, `--mode physics`, or `--mode full` before the Compose command. Speech/audio/full modes require `LUXOPI_AI_CHECKOUT` to name the AI checkout. Each mode resolves its overlay files by absolute checkout path, including when invoked from another directory. Physics/full are optional development backends; consult their validation evidence before treating their motion as calibrated. Build the base image before speech or physics, and both optional images before full.

The helper resolves its checkout from its own location. Container launches use `/workspace`; installed UI modules, meshes, and animation assets resolve from their package locations rather than the SSH shell’s working directory. Relative Compose paths resolve against the checkout. SSH authentication uses your existing account; this change does not create credentials.

Run native behavior checks:

```sh
docker compose -f compose.simulator.yml exec -T simulator bash -c \
  'source /opt/ros/jazzy/setup.bash && source /workspace/install/setup.bash && python3 scripts/run_motion_scenarios.py'
docker compose -f compose.simulator.yml exec -T simulator bash -c \
  'source /opt/ros/jazzy/setup.bash && source /workspace/install/setup.bash && python3 scripts/run_lighting_scenarios.py'
```

Stop with `docker compose -f compose.simulator.yml down`. The image builds natively and the current ROS base tag can receive upstream updates; it is not a fully frozen dependency environment.

The visual model currently represents the legacy four-axis RoArm-M1. Six-axis M3 geometry, inertia, actuator mapping and physics validation remain separate work; do not treat the current viewer as verified M3 dynamics. Camera controls currently publish simulated detections; their complete shared behavior consumer still needs integration.

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
