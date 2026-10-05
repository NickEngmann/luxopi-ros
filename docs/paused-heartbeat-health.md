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
ambiguous entrypoint guards. On 2026-10-05 the rebuilt default simulator at commit
`09b1682` passed the actual Docker-owned pause check: health returned HTTP 503
with a 3.182s stale state heartbeat while joint feedback stayed fresh; resuming the
same process restored HTTP 200 with a 0.025s state age, without a container
restart. Evidence: `/tmp/luxopi-latest-restart-e2e.json` on the development host.
The complete offline suite also passed 443 tests with one skip. This check
validates simulator monitoring and recovery, not physical robot recovery.
