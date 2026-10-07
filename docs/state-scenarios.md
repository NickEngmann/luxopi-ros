# State and recovery scenario coverage

Offline: `python3 -m pytest tests/test_state_scenarios.py -q`.
This suite executes the actual state-manager class and default transition methods,
substituting only ROS transport and absent LEDs. It tests startup auto-transition,
all 12 state entries, terminal shutdown, voice/capture/response state sequence,
priority rejection, animation/collision recovery, petting interruption/recovery,
and invalid service input. Two original defects were reproduced: collision allowed
low-priority idle requests to take over, and interrupted-state recovery was gated
on a stack that was never populated.

ROS transport: after building/source the workspace and launching a simulator state
manager, run:

```
ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1 python3 scripts/run_state_scenarios.py
```

The harness refuses other discovery settings and emits a JSON record with each
service result/state and elapsed milliseconds. It checks normal requests, denied
requests, interruption completion and explicit recovery, finishing in IDLE.
Run against a controlled simulator graph, with automatic/random behavior producers
paused; unrelated priority requests can legitimately change expected state results.

Coverage limits: voice scenarios check state contracts, not ASR or TTS. Touch and
collision cases request their resulting state directly; they do not claim sensor
classification coverage. Dance checks animation state lifecycle; trajectory/action
and all animation plugin execution belong to the motion simulator suite. Forced
entries show explicit state support, not that every sensor path reaches every state.
No physical movement, acoustic accuracy, speaker playback, electrical LED timing,
or actual collision stopping distance is validated by this suite.
