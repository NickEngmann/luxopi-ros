# Camera emotion simulation

`sim_camera_interaction` is a ROS-only detection adapter. It opens no DepthAI
camera, framebuffer, PyAudio device or OpenCV capture. The live
`CameraInteraction` and simulator both inherit `VisionReactionMixin`, so they
share the emotion buffer, minimum sample count, cooldown, repetition checks,
state gating and action callbacks.

Synthetic inputs are distinct from `/camera/*` outputs:

- `/sim/camera/emotion` String: `neutral`, `happy`, `sad`, `surprise`, `anger`.
- `/sim/camera/person_distance` Float32: valid distance strictly between 0.3
  and 4m.
- `/sim/camera/person_present` Bool: explicit presence or loss.

A stable injected detection supplies a 100ms observation cadence for at most
three seconds, enough for the same reaction buffer to evaluate. Explicit absence
clears the buffer, emotion and distance outputs. Presence expires after three
seconds. A dominant eligible emotion requests the actual `play_animation` action
with the live emotion mapping and distance-based speed. Each action goal carries
`trigger_source=emotion`, so the action server enters `EMOTION_REACTING`
deterministically instead of relying on a separate topic notification. Voice/user,
collision/escape, error and shutdown states block reactions. Startup cooldowns
are preserved. Person tracking fixtures do not invent face-bearing motion.

The legacy sad mapping referenced `droop`, which was never registered; it now
selects the implemented `sad` plugin. No registered animation was removed.

## Actual-pixel CPU reference

The dashboard can send a JPEG or PNG to an optional local OpenVINO CPU service.
It runs the pinned face detector and five-class emotion model, then routes the
selected face emotion and presence through the same `/sim/camera/*` topics and
shared reaction policy. The image is decoded and processed in memory, is limited
to 8 MiB and 20 megapixels, and is never written to disk. The HTTP service has no
published host port and is reachable only on the Compose network. Model artifacts
stay in a host cache mounted read-only.

Prepare the external model cache in the companion AI checkout:

```bash
cd /home/ubuntu/smarthome/luxopi/luxopi-ai
python3.12 -m venv .venv-vision
. .venv-vision/bin/activate
python -m pip install -r requirements-vision.txt
python scripts/download_vision_reference_models.py
```

Start the full simulator with the image inference service enabled:

```bash
cd /home/ubuntu/smarthome/.worktrees/luxopi-ros-modernized
scripts/simulator.sh --mode full --profile vision up -d --build
```

The optional profile mounts `~/.cache/luxopi-vision/omz-2023.0` read-only and
keeps inference on CPU. Choose a JPEG or PNG in the dashboard's “Run the camera
models on an image” control. The response reports a face count and selected
emotion; the dashboard also receives the actual ROS camera outputs. A detected
face is only a face above the detector threshold, not full-body person presence.
The reference returns no metric distance because monocular RGB cannot establish
range. Use the synthetic distance control or a calibrated depth sensor for
distance-dependent reaction speed.

This validates pixel decoding, model execution, ROS event routing and reaction
integration in simulation. It does not validate OAK-D neural execution, Hailo
acceleration, stereo range, camera color calibration or emotion accuracy on
household scenes. Exact model versions, licenses, input contracts and hashes are
in `docs/model-provenance/openvino-vision-reference.json` in the AI checkout.

`python3 -m pytest tests/test_vision_reactions.py -q` exercises shared dominance,
cooldown/repetition/safety gates, complete valid mapping, detection presence/loss,
invalid inputs and the shared implementation without importing native capture
SDKs. Full pixel-to-action evidence is recorded separately after running the
optional image service.

The dashboard upload path passed a browser end-to-end run on 2026-10-06: one
face image produced an anger reaction, `EMOTION_REACTING`, and measurable joint
motion; a blank image cleared person/emotion state without motion. The recorded
result is [vision-browser-e2e.json](validation/2026-10-06/vision-browser-e2e.json).
