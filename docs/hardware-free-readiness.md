# Hardware-free readiness and commissioning boundary

The simulator runs the actual Jazzy state/action consumers, not a separate
animation mock. The public dashboard stays on `0.0.0.0:8080`; see
[launch and SSH access](simulator-launch.md). The optional full profile adds
local saved-WAV recognition, local LFM inference, silent Piper synthesis and
MuJoCo feedback. Luxo requires neither Marisol nor Home Assistant.

The completed software paths include all 38 animation plugins, all 12 states,
27 mapped voice IDs, explicit action ownership and cancellation, bounded manual
control, two-stage measured home return, direction-driven movement and quiet
return, lamp feedback, camera-behavior fixtures, swipe-driven actions, petting,
and sensor-driven retreat/hold/replan. A missing or invalid sensor observation
cannot clear a hazard. Continuous animation timing remains opt-in.

Recent end-to-end checks exposed two lifecycle defects: safety could stop home
motion without entering the collision state, and releasing a voice session
before its active cue finished could produce a false joint-settling ERROR.
Both have regression tests and corrected native runs. Invalid joint frames and
nonoperational FSM states now make readiness HTTP 503. Saved-audio queue
shutdown and failed speech synthesis clean up owned temporary files.

The versioned feature inventory and historical checkpoints are in
[feature coverage](feature-coverage.md). Their old durations and source hashes
remain scoped to those runs; they are not measurements of the current physical
robot. Latest runtime results are recorded separately rather than overwriting
failed evidence or combining unlike versions.

Hardware commissioning still needs microphone/acoustic direction and VAD
checks, real camera inference and calibration, physical sensor extrinsics and
thresholds, motor torque/stopping-distance calibration, and CM4/Hailo latency
measurements. Synthetic world obstacles affect sensor rays, not MuJoCo contact
geometry. Model construction or successful synthetic speech fixtures do not
establish real-world perception accuracy. No physical devices or audible audio
were used for these development checks.
