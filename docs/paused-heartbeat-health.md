# Paused heartbeat health check

Run `python3 scripts/restart_e2e.py --pause-state --container NAME --url
http://127.0.0.1:8080 --output /tmp/luxopi-paused-health.json` only while the
owned simulator graph is exclusively free of other tests.

The existing image/Compose/no-device/network/domain/port guards remain required.
The script uses Docker exec to pause the single installed ROS state-manager
entrypoint inside the container PID namespace. It expects health503 with a stale
state heartbeat, resumes that exact PID/start-time identity in a finally block,
then expects health200 without a container restart. Reused PID, replacement
container or unexpected restart fails the check; no host PID is signalled.

Six dependency-light tests pass, including failed-check cleanup, reused PID and
ambiguous entrypoint guards. Actual container fault execution remains pending;
these tests do not claim that health503/recovery has been observed yet.
