# Detection-boundary camera simulation

`sim_camera_interaction` is a ROS-only detection adapter. It opens no DepthAI camera,
framebuffer, PyAudio device or OpenCV capture. The live `CameraInteraction` and the
simulator both inherit `VisionReactionMixin`: the existing buffer dominance,
minimum three samples, two-second collection window, five-second emotion cooldown,
three-second post-animation delay, repetition protection, state gating and action
callbacks are shared code, rather than an unrelated demonstration policy.

Inputs (distinct from real outputs):

- `/sim/camera/emotion` String: `neutral`, `happy`, `sad`, `surprise`, `anger`.
- `/sim/camera/person_distance` Float32: valid distance strictly between 0.3 and 4m.
- `/sim/camera/person_present` Bool: explicit presence/loss.

Outputs: `/camera/emotion`, `/camera/person_distance`, `/camera/person_present`.
A stable injected detection supplies a 100ms observation cadence for at most three
seconds, enough for the same reaction buffer to evaluate. Inject again for continued
observations. Presence expires after three seconds, and explicit absence clears the
buffer. This is detection simulation, not synthetic images or neural inference.

A dominant eligible emotion requests the actual `play_animation` action using the
live emotion mapping and distance-based speed. The action server determines
`EMOTION_REACTING` using `/animation_trigger_source=emotion`. Current voice/user,
collision/escape, error and shutdown states block reactions. Startup cooldowns are
preserved; a just-started node may ignore its first detection until five seconds have
passed. Raw person tracking outputs indicate presence/distance; they do not fabricate
face-bearing motion absent a real bearing estimate.

The legacy sad mapping referenced `droop`, which was never registered as an
animation; it now selects the implemented `sad` plugin. No registered animation
was removed. Live model inference/weights and capture pipeline remain unchanged;
the live pipeline additionally emits explicit `/camera/person_present` visibility.

`python3 -m pytest tests/test_vision_reactions.py -q` exercises shared dominance,
cooldown/repetition/safety gates, complete valid mapping, detection presence/loss,
invalid inputs and shared implementation/no native-capture-import contracts.
Native ROS validation must observe `EMOTION_REACTING`, a real animation action and
joint updates after eligible detections, plus person outputs, not simply input-topic
echo. Physical camera accuracy, stereo calibration and model latency remain unknown.
