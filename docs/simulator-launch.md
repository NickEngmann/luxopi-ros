# Hardware-free simulator

From this checkout run:

```sh
docker compose -f compose.simulator.yml up -d --build
```

Open http://127.0.0.1:8080. The dashboard runs a real ROS Jazzy graph with bounded simulated joints, the shared direction estimator, virtual lamp telemetry, sensor inputs and silent conversation previews. No serial, microphone, camera, audio or LED devices are mounted. The text backend defaults to deterministic simulation; this does not evaluate LFM inference accuracy. ROS discovery is isolated inside the container on domain 73.

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
