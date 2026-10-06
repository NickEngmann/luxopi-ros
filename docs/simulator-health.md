# Simulator readiness

`GET /healthz` returns HTTP 200 only when the required ROS graph is present,
state and joint feedback are fresh, the state is operational, and the latest
joint frame is valid. ERROR, INITIALIZING and SHUTDOWN return HTTP 503 even
when heartbeats continue. The JSON includes `reasons`, `state_ready`,
`joint_feedback_valid`, component presence and heartbeat ages.

Valid feedback has exactly the complete four-axis legacy or six-axis M3 names,
without duplicates, and finite positions inside the configured joint limits
(with a 0.02 rad feedback tolerance). Invalid frames do not replace the last
valid displayed pose or refresh its timestamp; the health flag stays false
until a valid frame arrives. Nonfinite values cannot reach dashboard JSON.

Offline tests in `tests/test_dashboard_feedback_health.py` exercise the actual
callback and health calculation. The browser suite additionally checks HTTP
503 and `state_not_ready` for each nonoperational state. The guarded
`scripts/restart_e2e.py` can pause the state-manager heartbeat and confirm stale
health, resume the same process, or terminate it and verify graph recovery.
Run fault tests exclusively against an owned simulator, never alongside an
animation, browser or speech test.

These checks establish simulator readiness, not hardware sensor health or
calibrated motor safety. Physical commissioning still needs the robot attached.
