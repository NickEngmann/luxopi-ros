# Behavior and adapter boundaries

LuxoPI remains an independent local robot. Speech recognition, validated command routing, LFM responses, and motion execution do not require Marisol or Home Assistant.

The Reachy work established useful boundaries: one owner for each state, one writer for motor targets, immediate interaction feedback, and explicit completion/cancellation feedback. Luxo applies those boundaries through its ROS action and state interfaces.

## Ownership

- Input adapters interpret speech, camera detections, direction estimates, touch, gestures, and simulator controls. They request behavior rather than writing motor targets.
- The state manager owns the robot's behavior state. Voice activity (listening, thinking, speaking, idle) is separate from motion state; a command animation must not end a live conversation session.
- The animation action server arbitrates and executes validated plans. Explicit commands, collision handling, manual control, and shutdown must take precedence over decorative conversational movements.
- The bounded motion controller is the sole command writer. In kinematic simulation it also publishes simulated joint feedback. In Gazebo, physics owns actual joint feedback; the controller sends bounded targets through the physics bridge.
- The dashboard subscribes to state, motion results, recognized command text, response text, and lamp feedback. Its health endpoint checks required nodes and freshness, rather than merely reporting that the HTTP server responds.

## Future Home Assistant adapter

A future adapter should translate authenticated smart-home requests into the same validated behavior/action requests. It should expose capabilities and report accepted, running, completed, rejected, or cancelled results. It must not publish motor targets or force arbitrary state changes. The simulator's forced-state controls are a test interface, not a production integration API.

Home Assistant can own household entities and automations while Luxo continues to own its local motion, collision safety, sensors, and conversation session. Publish state transitions and coarse health to Home Assistant; keep high-rate joint telemetry and real-time control local. A lost connection must leave local safety and independent speech operation intact.

No Home Assistant credentials, transport, or dependency are introduced by this architecture cleanup. Physical timing, torque, camera calibration, and microphone behavior still require the actual robot.
