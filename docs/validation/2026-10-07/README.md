# Hardware-free follow-up validation

The isolated MuJoCo build passed the [browser regression](browser-e2e-followup.json)
with 39 recorded scenarios in 161 seconds. It loaded all seven M3 meshes, showed
all 38 animations and 12 states, verified the six-axis FK, conversation feedback,
direction finding, collision hold/replan, sensor inputs, LEDs, randomized STL
colliders, and autonomous idle animation. The optional test that pauses a live
state-manager process was skipped. There were no page exceptions, console
errors, or failed HTTP requests.

The [wiring browser E2E](wiring-browser-e2e.json) passed both checks: four cable
strands rendered with finite geometry, and their distal endpoint moved 0.446 m
between two six-axis poses. Cable locations and slack remain visual estimates;
the physical route and safe bend radius have not been measured.

The run exposed a launch gap: MuJoCo declared synthetic idle/emotion controls
but did not pass them to the shared behavior graph. Forwarding those settings
started the autonomy node; float-typed launch parameters also prevent integer
environment values from crashing it. A separate offline check passed 595 tests
with one skipped. All browser and ROS graph tests ran in a disposable local
container with no hardware, physical audio, or camera access.
