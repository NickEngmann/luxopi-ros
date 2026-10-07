# Behavior and adapter boundaries

LuxoPI remains an independent local robot. Speech recognition, validated command routing, LFM responses, and motion execution do not require Marisol or Home Assistant.

The Reachy work established useful boundaries: one owner for each state, one writer for motor targets, immediate interaction feedback, and explicit completion/cancellation feedback. Luxo applies those boundaries through its ROS action and state interfaces.

## Ownership

- Input adapters interpret speech, camera detections, direction estimates, touch, gestures, and simulator controls. They request behavior rather than writing motor targets.
- The state manager owns the robot's behavior state. Voice activity (listening, thinking, speaking, idle) is separate from motion state; a command animation must not end a live conversation session.
- The animation action server arbitrates and executes validated plans. Explicit commands, collision handling, manual control, and shutdown must take precedence over decorative conversational movements.
- The bounded motion controller is the sole command writer. In kinematic simulation it also publishes simulated joint feedback. In a physics backend, physics owns actual joint feedback; the controller sends bounded targets to that backend.
- The dashboard subscribes to state, motion results, recognized command text, response text, and lamp feedback. Its health endpoint checks required nodes and freshness, rather than merely reporting that the HTTP server responds.

The local speech service starts with the ROS bridge and signals readiness over
its private stderr channel only after ASR, LLM, and optional TTS initialization.
The bridge waits for that signal before considering the service warm, so the
first voice command does not race model loading. The public JSONL request and
response format remains unchanged.

## Optional Home Assistant adapter

The opt-in [smart-home integration module](smart-home-integrations.md) reports
coarse state and health, accepts allowlisted high-level HA events, and routes
typed music requests through Music Assistant. It must not publish motor
targets or force arbitrary state changes. The simulator's forced-state
controls remain a test interface, not a production integration API.

Home Assistant can own household entities and automations while Luxo continues to own its local motion, collision safety, sensors, and conversation session. Publish state transitions and coarse health to Home Assistant; keep high-rate joint telemetry and real-time control local. A lost connection must leave local safety and independent speech operation intact.

The adapter stays disabled until configured with deployment credentials and
validated against the chosen HA/MA instances. Physical timing, torque, camera
calibration, and microphone behavior still require the actual robot.

## Sensor-driven course adjustment

Obstacle handling must change the trajectory, rather than merely report a collision. The original hardware inputs are the left/right VL53 distance sensors, the APDS proximity sensor at the lamp head near the camera, and side/bottom force-sensitive contact sensors. Top-of-head touch remains a petting input. The physical side-touch wiring is crossed; `swap_touch_sides` makes that existing calibration explicit. APDS proximity is a relative reading, not a measured clearance in centimeters.

The [distance filter and unit boundary](sensor-filtering.md) must preserve sudden
close observations; smoothing must never turn an approaching obstacle into a
larger apparent clearance.

The hardware and simulator must use the same avoidance decision policy. A fresh warning may replace a target with a bounded retreat away from the affected side or a compact head posture. Contact, imminent danger, contradictory obstacles, or the absence of a feasible retreat must hold movement and interrupt the animation. Avoidance targets still pass through joint limits and velocity/acceleration limits; safety does not bypass the command owner. A hold request brakes under those limits; it does not teleport joint velocity to zero. Tests must bound stopping time and travel before checking the stationary hold. Sensor thresholds, detection latency, arm reach, and stopping distance must be calibrated together on the physical robot.

Releasing an obstacle requires fresh clear readings and hysteresis. A missing sensor update is not proof of clearance. An interrupted animation must not jump back to an obsolete target when the obstacle disappears; continued movement needs a new validated plan. Simulation checks must cover left, right, head proximity, contact, simultaneous obstacles, sensor dropout, and clear/replan behavior during an actual animation. Physical sensor orientation and safe retreat geometry must be calibrated when the robot is attached.
